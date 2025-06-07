import feedparser
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from model import RssFeed, RssEntry, Session
from sqlalchemy import func, desc
import hashlib
import os


def get_favicon_url(feed_url):
    if "http" not in feed_url:
        feed_url = "http://" + feed_url

    page = requests.get(feed_url)
    soup = BeautifulSoup(page.text, features="lxml")

    icon_link = soup.find("link", rel="shortcut icon")
    if icon_link is None:
        icon_link = soup.find("link", rel="icon")

    if icon_link is None:
        return None

    return icon_link.get("href")


def add_feed(feed_url):
    print(feed_url)
    session = Session()
    try:
        existing_feed = session.query(RssFeed).filter_by(url=feed_url).first()

        if existing_feed:
            session.close()
            return

        feed = feedparser.parse(feed_url)

        favicon_url = get_favicon_url(feed.feed.link)
        favicon_path = None

        if favicon_url:
            try:
                favicon_response = requests.get(favicon_url)
                if favicon_response.status_code == 200:
                    # Create the static/img directory if it doesn't exist
                    img_dir = os.path.join("static", "img")
                    os.makedirs(img_dir, exist_ok=True)

                    # Generate a unique filename for the favicon
                    parsed_url = urlparse(feed_url)
                    domain = parsed_url.netloc or parsed_url.path
                    favicon_filename = f"favicon_{hashlib.md5(domain.encode()).hexdigest()}.ico"
                    favicon_path = os.path.join("img", favicon_filename)
                    full_favicon_path = os.path.join("static", favicon_path)

                    # Save the favicon
                    with open(full_favicon_path, "wb") as f:
                        f.write(favicon_response.content)
                        print(f"Saved favicon for {feed.feed.title} to {full_favicon_path}")
            except Exception as e:
                print(f"Error downloading favicon: {e}")

        # Add the feed to the database
        rss_feed = RssFeed(
            url=feed_url,
            title=feed.feed.title,
            link=feed.feed.link,
            description=feed.feed.description,
            favicon_path=favicon_path,
        )

        session.add(rss_feed)
        session.commit()
        session.close()
        print(f"Feed added: {rss_feed.title}")
    except Exception as e:
        session.rollback()
        session.close()
        print(f"Error adding feed: {e}")


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


def get_all_feeds():
    session = Session()
    total_unread_count = (
        session.query(func.count(RssEntry.id)).filter(RssEntry.read == False).scalar()
    )
    print(total_unread_count)
    all_feed = RssFeed(id="all", title="All Feeds")
    feeds = session.query(RssFeed).all()
    for feed in feeds:
        feed.unread_count = feed.get_unread_count(session)
        # Calculate the latest published date from entries for this feed
        latest_entry = session.query(RssEntry).filter_by(feed_id=feed.id).order_by(desc(RssEntry.published)).first()
        feed.last_new_article_found = latest_entry.published if latest_entry else None
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
    session.close()
    return feed