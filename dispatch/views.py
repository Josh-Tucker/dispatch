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

from starlette.responses import JSONResponse

async def add_feed(feed_url):
    session = Session()
    try:
        existing_feed = session.query(RssFeed).filter_by(url=feed_url).first()

        if existing_feed:
            session.close()
            return JSONResponse({"message": f"Feed with URL '{feed_url}' already exists in the database."}, status_code=409)

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
                return JSONResponse({"error": f"Error downloading favicon image: '{favicon_url}' {e}"}, status_code=500)
            except Exception as e:
                print(f"Error saving favicon image: '{favicon_url}' {e}")
                favicon_path = None
                return JSONResponse({"error": f"Error saving favicon image: '{favicon_url}' {e}"}, status_code=500)
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
        await session.commit()
        return JSONResponse({"status": "success", "message": f"New feed added with URL '{feed_url}'."}, status_code=201)
    except Exception as exc:
        await session.rollback()
        return JSONResponse({"status": "error", "message": f"An error occurred while processing feed: '{feed_url}': {exc}"}, status_code=500)



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
        await session.commit()
    session.close()


async def add_rss_entries_for_all_feeds():
    print("adding feed items")
    session = Session()
    feeds = session.query(RssFeed).all()

    for feed in feeds:
        print("adding entries for" + feed.title)
        await add_rss_entries(feed.id)


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



async def mark_rss_entry_as_read(entry_id, read_status=True):
async def mark_rss_entry_as_read(entry_id, read_status=True):
    session = Session()
    rss_entry = session.query(RssEntry).filter_by(id=entry_id).first()

    if rss_entry:
        rss_entry.read = read_status
        await session.commit()
        await session.commit()
        await session.commit()
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
