import feedparser
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from models import RssFeed, RssEntry, Session, Settings
from sqlalchemy import func, desc, case
import hashlib
import os
import mimetypes


def get_favicon_url(feed_url):
    if "http" not in feed_url:
        feed_url = "http://" + feed_url

    try:
        page = requests.get(feed_url, timeout=10)
        soup = BeautifulSoup(page.text, features="lxml")

        icon_link = soup.find("link", rel="shortcut icon")
        if icon_link is None:
            icon_link = soup.find("link", rel="icon")

        if icon_link is None:
            # Try default favicon location
            parsed_url = urlparse(feed_url)
            return f"{parsed_url.scheme}://{parsed_url.netloc}/favicon.ico"

        favicon_url = icon_link.get("href")
        if favicon_url and not favicon_url.startswith('http'):
            # Make relative URLs absolute
            parsed_url = urlparse(feed_url)
            if favicon_url.startswith('//'):
                favicon_url = f"{parsed_url.scheme}:{favicon_url}"
            elif favicon_url.startswith('/'):
                favicon_url = f"{parsed_url.scheme}://{parsed_url.netloc}{favicon_url}"
            else:
                favicon_url = urljoin(feed_url, favicon_url)
        
        return favicon_url
    except Exception as e:
        print(f"Error getting favicon URL: {e}")
        return None


def download_and_store_favicon(feed_url):
    """Download favicon and return binary data and MIME type."""
    favicon_url = get_favicon_url(feed_url)
    if not favicon_url:
        return None, None
    
    try:
        favicon_response = requests.get(favicon_url, timeout=10)
        if favicon_response.status_code == 200:
            # Determine MIME type
            content_type = favicon_response.headers.get('content-type', '')
            if content_type:
                mime_type = content_type.split(';')[0].strip()
            else:
                # Guess MIME type from URL or content
                mime_type, _ = mimetypes.guess_type(favicon_url)
                if not mime_type:
                    if favicon_url.lower().endswith('.ico'):
                        mime_type = 'image/x-icon'
                    elif favicon_url.lower().endswith('.png'):
                        mime_type = 'image/png'
                    elif favicon_url.lower().endswith('.jpg') or favicon_url.lower().endswith('.jpeg'):
                        mime_type = 'image/jpeg'
                    elif favicon_url.lower().endswith('.svg'):
                        mime_type = 'image/svg+xml'
                    else:
                        mime_type = 'image/x-icon'  # Default fallback
            
            return favicon_response.content, mime_type
    except Exception as e:
        print(f"Error downloading favicon from {favicon_url}: {e}")
    
    return None, None


def add_feed(feed_url):
    print(feed_url)
    session = Session()
    try:
        existing_feed = session.query(RssFeed).filter_by(url=feed_url).first()

        if existing_feed:
            session.close()
            return

        feed = feedparser.parse(feed_url)

        # Download and store favicon in database
        favicon_data, favicon_mime_type = download_and_store_favicon(feed.feed.link or feed_url)

        # Add the feed to the database
        rss_feed = RssFeed(
            url=feed_url,
            title=feed.feed.title,
            link=feed.feed.link,
            description=feed.feed.description,
            favicon_data=favicon_data,
            favicon_mime_type=favicon_mime_type,
        )

        session.add(rss_feed)
        session.commit()
        session.close()
        print(f"Feed added: {rss_feed.title}")
        if favicon_data:
            print(f"Favicon stored in database ({len(favicon_data)} bytes, {favicon_mime_type})")
    except Exception as e:
        session.rollback()
        session.close()
        print(f"Error adding feed: {e}")


def refresh_feed_favicon(feed_id):
    """Refresh the favicon for a specific feed."""
    session = Session()
    try:
        feed = session.query(RssFeed).filter_by(id=feed_id).first()
        if not feed:
            print(f"Feed with ID {feed_id} not found.")
            return False

        # Download new favicon
        favicon_data, favicon_mime_type = download_and_store_favicon(feed.link or feed.url)
        
        if favicon_data:
            feed.favicon_data = favicon_data
            feed.favicon_mime_type = favicon_mime_type
            session.commit()
            print(f"Favicon refreshed for feed: {feed.title} ({len(favicon_data)} bytes, {favicon_mime_type})")
            return True
        else:
            print(f"Could not fetch favicon for feed: {feed.title}")
            return False
            
    except Exception as e:
        session.rollback()
        print(f"Error refreshing favicon for feed {feed_id}: {e}")
        return False
    finally:
        session.close()


def refresh_all_feed_favicons():
    """Refresh favicons for all feeds."""
    session = Session()
    try:
        feeds = session.query(RssFeed).all()
        success_count = 0
        
        for feed in feeds:
            print(f"Refreshing favicon for: {feed.title}")
            
            # Download new favicon
            favicon_data, favicon_mime_type = download_and_store_favicon(feed.link or feed.url)
            
            if favicon_data:
                feed.favicon_data = favicon_data
                feed.favicon_mime_type = favicon_mime_type
                success_count += 1
                print(f"  ✓ Updated ({len(favicon_data)} bytes, {favicon_mime_type})")
            else:
                print(f"  ✗ Could not fetch favicon")
        
        session.commit()
        print(f"Favicon refresh completed: {success_count}/{len(feeds)} feeds updated")
        return success_count, len(feeds)
        
    except Exception as e:
        session.rollback()
        print(f"Error refreshing all favicons: {e}")
        return 0, 0
    finally:
        session.close()


def remove_feed(feed_id):
    session = Session()

    try:
        feed = session.query(RssFeed).filter_by(id=feed_id).first()
        if feed:
            # Delete all associated entries
            session.query(RssEntry).filter_by(feed_id=feed_id).delete()
            session.delete(feed)
            session.commit()

            print(f"Feed and associated entries deleted: {feed.title}")
        else:
            print(f"Feed with ID {feed_id} not found.")

    except Exception as e:
        session.rollback()
        print(f"Error deleting feed: {e}")
    finally:
        session.close()


def get_all_feeds(sort_by="title"):
    session = Session()
    total_unread_count = (
        session.query(func.count(RssEntry.id)).filter(RssEntry.read == False).scalar()
    )
    print(total_unread_count)
    all_feed = RssFeed(id="all", title="All Feeds")
    
    # Get feeds with sorting logic - pinned feeds always first
    if sort_by == "title":
        feeds = session.query(RssFeed).order_by(
            desc(RssFeed.pinned),
            RssFeed.title
        ).all()
    elif sort_by == "last_updated":
        feeds = session.query(RssFeed).order_by(
            desc(RssFeed.pinned),
            desc(RssFeed.last_updated)
        ).all()
    elif sort_by == "frequency_read":
        # This will be calculated in Python since it requires complex aggregation
        feeds = session.query(RssFeed).order_by(desc(RssFeed.pinned)).all()
    else:
        feeds = session.query(RssFeed).order_by(
            desc(RssFeed.pinned),
            RssFeed.title
        ).all()
    
    for feed in feeds:
        feed.unread_count = feed.get_unread_count(session)
        # Calculate the latest published date from entries for this feed
        latest_entry = session.query(RssEntry).filter_by(feed_id=feed.id).order_by(desc(RssEntry.published)).first()
        feed.last_new_article_found = latest_entry.published if latest_entry else None
        # Calculate read frequency for sorting
        feed.read_frequency = feed.get_read_frequency(session)
    
    # If sorting by frequency, do the final sort in Python
    if sort_by == "frequency_read":
        # Separate pinned and unpinned feeds
        pinned_feeds = [f for f in feeds if f.pinned]
        unpinned_feeds = [f for f in feeds if not f.pinned]
        # Sort each group by read frequency
        pinned_feeds.sort(key=lambda x: x.read_frequency, reverse=True)
        unpinned_feeds.sort(key=lambda x: x.read_frequency, reverse=True)
        feeds = pinned_feeds + unpinned_feeds
    
    all_feed.unread_count = total_unread_count
    session.close()
    return [all_feed] + feeds


def get_feed_by_id(feed_id):
    session = Session()
    feed = session.query(RssFeed).filter_by(id=feed_id).first()
    if feed:
        feed.unread_count = feed.get_unread_count(session)
        # Calculate the latest published date from entries for this feed
        latest_entry = session.query(RssEntry).filter_by(feed_id=feed.id).order_by(desc(RssEntry.published)).first()
        feed.last_new_article_found = latest_entry.published if latest_entry else None
        feed.read_frequency = feed.get_read_frequency(session)
    session.close()
    return feed


def toggle_feed_pin(feed_id):
    """Toggle the pinned status of a feed."""
    session = Session()
    try:
        feed = session.query(RssFeed).filter_by(id=feed_id).first()
        if feed:
            feed.pinned = not feed.pinned
            session.commit()
            print(f"Feed '{feed.title}' {'pinned' if feed.pinned else 'unpinned'}")
            return feed.pinned
        else:
            print(f"Feed with ID {feed_id} not found.")
            return None
    except Exception as e:
        session.rollback()
        print(f"Error toggling feed pin: {e}")
        return None
    finally:
        session.close()


def get_feed_sort_preference():
    """Get the current feed sorting preference from settings."""
    session = Session()
    try:
        setting = Settings.get_setting(session, "feed_sort_by")
        return setting if setting else "title"
    finally:
        session.close()


def set_feed_sort_preference(sort_by):
    """Set the feed sorting preference in settings."""
    session = Session()
    try:
        Settings.set_setting(session, "feed_sort_by", sort_by)
        session.commit()
        print(f"Feed sort preference set to: {sort_by}")
        return True
    except Exception as e:
        session.rollback()
        print(f"Error setting feed sort preference: {e}")
        return False
    finally:
        session.close()