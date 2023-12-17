import xml.etree.ElementTree as ET
import feedparser
import opml
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from model import *
from dateutil import parser
import dateutil.parser
from datetime import datetime, timedelta


def add_feeds_from_opml(opml_file):
    try:
        opml_data = opml.parse(opml_file)

        for outline in opml_data:
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
    session = Session()
    existing_feed = session.query(RssFeed).filter_by(url=feed_url).first()

    if existing_feed:
        session.close()
        print(f"Feed with URL '{feed_url}' already exists in the database.")
        return

    feed = feedparser.parse(feed_url)
    favicon_url = feed.feed.get("image", {}).get("url", get_favicon_url(feed.feed.get("link", feed_url)))

    published_str = feed.feed.get("published", "")
    published_date = parser.parse(published_str) if published_str else None

    new_feed = RssFeed(
        url=feed_url,
        title=feed.feed.get("title", feed.feed.get("link", "")),
        link=feed.feed.get("link", ""),
        description=feed.feed.get("description", ""),
        published=published_date,
        favicon_url=favicon_url
    )

    session.add(new_feed)
    session.commit()
    session.close()
    print(f"New feed added with URL '{feed_url}'.")


def add_rss_entries(feed_id):
    session = Session()
    rss_feed = session.query(RssFeed).filter_by(id=feed_id).first()

    if not rss_feed:
        print(
            "RSS feed not found in the database. Please add the feed to the database first."
        )
    else:
        feed = feedparser.parse(rss_feed.url)
        for entry in feed.entries:
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

                rss_entry = RssEntry(
                    feed_id=rss_feed.id,
                    title=entry.get("title", ""),
                    link=entry.get("link", ""),
                    description=entry.get("summary", ""),
                    content=content,
                    published=published_date,
                    author=entry.get("author", ""),
                    guid=entry.get("guid", ""),
                )
                session.add(rss_entry)
                rss_feed.last_updated = datetime.utcnow()
        session.commit()
    session.close()


def add_rss_entries_for_all_feeds():
    print("adding feed items")
    session = Session()
    feeds = session.query(RssFeed).all()

    for feed in feeds:
        print("adding entries for" + feed.title)
        add_rss_entries(feed.id)


def get_all_feeds():
    session = Session()
    all_feed = RssFeed(id='all', title='All Feeds')
    feeds = [all_feed] + session.query(RssFeed).all()
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
    session.close()
    return feed


def get_feed_entry_by_id(entry_id):
    session = Session()
    entry = session.query(RssEntry).filter_by(id=entry_id).first()
    session.close()
    return entry


def get_feed_entries_by_feed_id(feed_id):
    session = Session()
    entries = session.query(RssEntry).filter_by(feed_id=feed_id).order_by(RssEntry.published.desc()).all()
    session.close()
    return entries


def mark_rss_entry_as_read(entry_id, read_status=True):
    session = Session()
    rss_entry = session.query(RssEntry).filter_by(id=entry_id).first()

    if rss_entry:
        rss_entry.read = read_status
        session.commit()
        session.close()
        print(
            f"RSS Entry with ID {entry_id} marked as {'read' if read_status else 'unread'}."
        )
    else:
        session.close()
        print(f"RSS Entry with ID {entry_id} not found in the database.")

def format_time_delta_or_date(input_datetime):
    now = datetime.now()
    delta = now - input_datetime

    if delta.total_seconds() < 60 * 30:  # Less than 30 minutes
        return f"{int(delta.total_seconds() / 60)} mins ago"
    elif delta.total_seconds() < 60 * 60:  # Less than 1 hour
        return "1 hour ago"
    elif delta.total_seconds() < 60 * 60 * 24:  # Less than 24 hours
        return f"{int(delta.total_seconds() / 3600)} hours ago"
    elif delta.total_seconds() < 60 * 60 * 24 * 30:  # Less than 30 days
        days = int(delta.total_seconds() / (3600 * 24))
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif delta.total_seconds() < 60 * 60 * 24 * 365:  # Less than 1 year
        months = int(delta.total_seconds() / (3600 * 24 * 30))
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        return input_datetime.strftime("%Y-%m-%d")