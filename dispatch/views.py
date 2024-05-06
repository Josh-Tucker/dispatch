import xml.etree.ElementTree as ET
import feedparser
import opml
import requests
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from model import *
from dateutil import parser
import dateutil.parser
from datetime import datetime, timedelta
from sqlalchemy import desc
import hashlib

def add_feeds_from_opml(opml_file):

    opml_data = opml.parse(opml_file)

    for outline in opml_data:
        try:
            add_feed(outline.xmlUrl)

        except Exception as e:
            print(f"An error occurred: {e}")

def article_date_format(date: str) -> str:
    return dateutil.parser.parse(date).strftime("%d %b %Y")


def article_long_date_format(date: str) -> str:
    return dateutil.parser.parse(date).strftime("%A, %B, %d, %Y")


def get_favicon_url(feed_url):
    if 'http' not in feed_url:
        feed_url = 'http://' + feed_url

    page = requests.get(feed_url)
    soup = BeautifulSoup(page.text, features="lxml")

    icon_link = soup.find("link", rel="shortcut icon")
    if icon_link is None:
        icon_link = soup.find("link", rel="icon")

    if icon_link is None:
        return urljoin(feed_url, '/favicon.ico')
    else:
        icon_href = icon_link.get("href")
        if not icon_href.startswith(('http://', 'https://')):
            icon_href = urljoin(feed_url, icon_href)
        return icon_href


def add_feed(feed_url):
    print(feed_url)
    session = Session()
    try:
        existing_feed = session.query(RssFeed).filter_by(url=feed_url).first()

        if existing_feed:
            session.close()

        feed = feedparser.parse(feed_url)
        favicon_url = feed.feed.get("image", {}).get("url", get_favicon_url(feed.feed.get("link", feed_url)))

        is_svg_string = '<svg' in favicon_url

        if is_svg_string:
            favicon_path = None
        elif favicon_url:
            try:
                response = requests.get(favicon_url, stream=True)
                response.raise_for_status()

                file_extension = os.path.splitext(urlparse(favicon_url).path)[1]
                if not file_extension:
                    file_extension = ".png" 

                filename = hashlib.md5(favicon_url.encode()).hexdigest() + file_extension
                filepath = os.path.join("static", "img", filename)
                favicon_path = "/img/" + filename

                with open(filepath, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)

            except requests.RequestException as e:
                print(f"Error downloading favicon image: '{favicon_url}' {e}")
                favicon_path = None
            except Exception as e:
                print(f"Error saving favicon image: '{favicon_url}' {e}")
                favicon_path = None
        else:
            favicon_path = None

        published_str = feed.feed.get("published", "")
        published_date = parser.parse(published_str) if published_str else None

        new_feed = RssFeed(
            url=feed_url.strip(),
            title=feed.feed.get("title", feed.feed.get("link", "")),
            link=feed.feed.get("link", ""),
            description=feed.feed.get("description", ""),
            published=published_date,
            favicon_path=favicon_path
        )

        session.add_all([new_feed])
        session.commit()
    except Exception as exc:
        session.rollback()


def remove_feed(feed_id):
    session = Session()

    try:
        feed = session.query(RssFeed).filter_by(id=feed_id).first()
        if feed:
            # Delete all associated entries
            session.query(RssEntry).filter_by(feed_id=feed_id).delete()
            session.delete(feed)
            session.commit()
            
            return True, "Feed and associated entries have been successfully removed."
        else:
            return False, "Feed not found."

    except Exception as e:
        # Rollback the transaction if an error occurs
        session.rollback()
        return False, str(e)

    finally:
        session.close()


def add_rss_entries(feed_id):
    try:
        session = Session()
        feed = session.query(RssFeed).filter_by(id=feed_id).first()

        if not feed:
            print(
                "RSS feed not found in the database. Please add the feed to the database first."
            )
        else:
            feed_data = feedparser.parse(feed.url)
            for entry in feed_data.entries:
                existing_entry = session.query(RssEntry).filter_by(link=entry.link).first()
                if not existing_entry:
                    if entry.get("content"):
                        content = entry.get("content")[0]["value"]
                    elif entry.get("summary"):
                        content = entry.get("summary")
                    elif entry.get("link"):
                        content = entry.get("link")

                    published_str = entry.get("published", "")
                    published_date = parser.parse(published_str) if published_str else datetime.utcnow()

                    new_entry = RssEntry(
                        feed_id=feed.id,
                        title=entry.get("title", ""),
                        link=entry.get("link", ""),
                        description=entry.get("summary", ""),
                        content=content,
                        published=published_date,
                        author=entry.get("author", ""),
                        guid=entry.get("guid", ""),
                    )
                    session.add(new_entry)
                    feed.last_updated = datetime.utcnow()
            session.commit()
        session.close()
    except Exception as e:
        print(f"An error occurred: {e}")


def add_rss_entries_for_all_feeds():
    print("adding feed items")
    session = Session()
    feeds = session.query(RssFeed).all()

    for feed in feeds:
        print("adding entries for" + feed.title)
        add_rss_entries(feed.id)


def get_all_feeds():
    session = Session()
    total_unread_count = session.query(func.count(RssEntry.id)).filter(RssEntry.read == False).scalar()
    print(total_unread_count)
    all_feed = RssFeed(id='all', title='All Feeds')
    feeds = session.query(RssFeed).all()
    for feed in feeds:
        feed.unread_count = feed.get_unread_count(session)
    all_feed.unread_count = total_unread_count
    feeds = [all_feed] + feeds
    session.close()
    return feeds


def get_all_feed_entries():
    session = Session()
    entries = session.query(RssEntry).order_by(RssEntry.published.desc()).all()
    session.close()
    return entries


def get_feed_by_id(feed_id):
    session = Session()
    feed = session.query(RssFeed).filter_by(id=feed_id).first()
    feed.unread_count = feed.get_unread_count(session)
    session.close()
    return feed

def get_feed_entry_by_id(entry_id):
    session = Session()

    entry = session.query(RssEntry).filter_by(id=entry_id).first()
    entry.read = True
    session.commit()
    session.close()
    entry = session.query(RssEntry).filter_by(id=entry_id).first()
    return entry


def get_feed_entries_by_feed_id(feed_id, page=1, entries_per_page=10):
    session = Session()

    query = session.query(RssEntry)

    if feed_id == "all":
        query = query.order_by(desc(RssEntry.published)).limit(entries_per_page).offset((page - 1) * entries_per_page)

    else:
        query = query.filter_by(feed_id=feed_id).order_by(desc(RssEntry.published)).limit(entries_per_page).offset((page - 1) * entries_per_page)

    entries = query.all()

    session.close()
    return entries



def mark_entry_as_read(entry_id, read_status=True):
    session = Session()
    entry = session.query(RssEntry).filter_by(id=entry_id).first()

    if entry:
        entry.read = read_status
        session.commit()
        session.close()
        print(
            f"RSS Entry with ID {entry_id} marked as {'read' if read_status else 'unread'}."
        )
    else:
        session.close()
        print(f"RSS Entry with ID {entry_id} not found in the database.")

def mark_feed_entries_as_read(feed_id, read_status=True):
    session = Session()
    if feed_id == "all":
        rss_entries = session.query(RssEntry)
    else:
        rss_entries = session.query(RssEntry).filter_by(feed_id=feed_id).all()

    for entry in rss_entries:
        entry.read = read_status

    session.commit()
    session.close()

    if read_status:
        print(f"All entries in the feed {feed_id} marked as read.")
    else:
        print(f"All entries in the feed {feed_id} marked as unread.")


