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
from readabilipy import simple_json_from_html_string
import concurrent.futures
from functools import partial


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
    if "http" not in feed_url:
        feed_url = "http://" + feed_url

    page = requests.get(feed_url)
    soup = BeautifulSoup(page.text, features="lxml")

    icon_link = soup.find("link", rel="shortcut icon")
    if icon_link is None:
        icon_link = soup.find("link", rel="icon")

    if icon_link is None:
        return urljoin(feed_url, "/favicon.ico")
    else:
        icon_href = icon_link.get("href")
        if not icon_href.startswith(("http://", "https://")):
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
        favicon_url = feed.feed.get("image", {}).get(
            "url", get_favicon_url(feed.feed.get("link", feed_url))
        )

        is_svg_string = "<svg" in favicon_url

        if is_svg_string:
            favicon_path = None
        elif favicon_url:
            try:
                response = requests.get(favicon_url, stream=True)
                response.raise_for_status()

                file_extension = os.path.splitext(urlparse(favicon_url).path)[1]
                if not file_extension:
                    file_extension = ".png"

                filename = (
                    hashlib.md5(favicon_url.encode()).hexdigest() + file_extension
                )
                filepath = os.path.join("static", "img", filename)
                favicon_path = "/img/" + filename

                with open(filepath, "wb") as file:
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
            favicon_path=favicon_path,
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
    """
    Fetches and adds RSS entries for a specific feed to the database.
    Attempts to process feeds even if parsing exceptions occur.

    Args:
        feed_id: The ID of the RSS feed to process

    Returns:
        tuple: (success_flag, message)
    """
    session = None

    try:
        # Create a new database session
        session = Session()

        # Fetch the feed with the specified ID
        feed = session.query(RssFeed).filter_by(id=feed_id).first()

        # Return early if feed doesn't exist
        if not feed:
            session.close()
            return False, f"Feed with ID {feed_id} not found in database"

        # Update timestamp for last fetch attempt
        feed.last_fetch_attempt = datetime.utcnow()
        session.commit()

        # Parse the feed data
        feed_data = feedparser.parse(feed.url)

        # Note the bozo exception but continue processing
        bozo_message = ""
        if hasattr(feed_data, 'bozo_exception') and feed_data.bozo_exception:
            bozo_message = f"Warning: Feed has parse errors ({str(feed_data.bozo_exception)[:100]}...)"
            feed.last_fetch_error = str(feed_data.bozo_exception)[:255]
            session.commit()
            # Continue processing instead of returning early

        # Track how many entries were added
        entries_added = 0

        # Process each entry in the feed if entries exist
        if hasattr(feed_data, 'entries') and feed_data.entries:
            for entry in feed_data.entries:
                # Skip entries without links since we use the link as a unique identifier
                if not entry.get('link'):
                    continue

                # Check if entry already exists
                existing_entry = session.query(RssEntry).filter_by(link=entry.link).first()
                if existing_entry:
                    continue

                # Determine content based on available fields
                content = ""
                if entry.get("content"):
                    if isinstance(entry.content, list) and len(entry.content) > 0:
                        content = entry.content[0].value
                    else:
                        content = str(entry.content)
                elif entry.get("summary"):
                    content = entry.summary
                elif entry.get("description"):
                    content = entry.description

                # Parse publication date
                published_date = datetime.utcnow()  # Default to current time
                for date_field in ['published', 'updated', 'pubDate', 'created']:
                    if entry.get(date_field):
                        try:
                            published_date = parser.parse(entry[date_field])
                            break
                        except (ValueError, TypeError):
                            continue

                # Create new entry
                new_entry = RssEntry(
                    feed_id=feed.id,
                    title=entry.get("title", "Untitled"),
                    link=entry.get("link", ""),
                    description=entry.get("summary", ""),
                    content=content,
                    published=published_date,
                    author=entry.get("author", ""),
                    guid=entry.get("id", entry.get("link", "")),
                    read=False
                )

                session.add(new_entry)
                entries_added += 1

            # Update feed metadata only if we succeeded in adding entries or there were no new entries
            feed.last_updated = datetime.utcnow()

            # Only clear error if we didn't encounter a bozo exception
            if not bozo_message:
                feed.last_fetch_error = None

            # Commit all changes
            session.commit()

            success_message = f"Successfully added {entries_added} new entries to feed '{feed.title}'"
            if bozo_message:
                return True, f"{success_message} ({bozo_message})"
            return True, success_message
        else:
            # No entries found but we still update the last_updated timestamp
            feed.last_updated = datetime.utcnow()
            session.commit()

            if bozo_message:
                return True, f"No new entries found. {bozo_message}"
            return True, "No new entries found in feed"

    except requests.RequestException as e:
        # Handle network-related errors
        if session and 'feed' in locals() and feed:
            feed.last_fetch_error = f"Network error: {str(e)[:255]}"
            session.commit()
        return False, f"Network error while fetching feed: {str(e)}"

    except Exception as e:
        # Handle all other errors
        if session:
            session.rollback()
            if 'feed' in locals() and feed:
                try:
                    feed.last_fetch_error = str(e)[:255]
                    session.commit()
                except:
                    pass
        return False, f"Error processing feed: {str(e)}"

    finally:
        # Ensure session is closed even if exceptions occur
        if session:
            session.close()


def add_rss_entries_for_feed(feed_id):
    """
    Fetches and adds RSS entries for a specific feed to the database.
    
    Args:
        feed_id: The ID of the RSS feed to process

    Returns:
        tuple: (success_flag, message)
    """
    print(f"Refreshing feed with ID: {feed_id}")
    result = add_rss_entries(feed_id)
    return result


def add_rss_entries_for_all_feeds(max_workers=10):
    """
    Process all RSS feeds in parallel, adding new entries to the database.

    Args:
        max_workers: Maximum number of worker threads to use for parallel processing

    Returns:
        list: Results of processing each feed (success/failure status and messages)
    """
    print("Adding feed items in parallel")
    session = Session()

    try:
        # Get all feeds from the database
        feeds = session.query(RssFeed).all()
        feed_ids = [feed.id for feed in feeds]
        feed_titles = {feed.id: feed.title for feed in feeds}
    finally:
        # Make sure to close the session after getting the feeds
        session.close()

    results = []

    # Use a ThreadPoolExecutor to process feeds in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Start the load operations and mark each future with its feed_id
        future_to_feed = {
            executor.submit(add_rss_entries, feed_id): feed_id
            for feed_id in feed_ids
        }

        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_feed):
            feed_id = future_to_feed[future]
            try:
                success, message = future.result()
                print(f"Feed '{feed_titles.get(feed_id, feed_id)}': {message}")
                results.append((feed_id, success, message))
            except Exception as exc:
                print(f"Feed '{feed_titles.get(feed_id, feed_id)}' generated an exception: {exc}")
                results.append((feed_id, False, f"Exception occurred: {exc}"))

    # Count and report results
    successful_feeds = sum(1 for _, success, _ in results if success)
    print(f"Completed processing {len(results)} feeds. {successful_feeds} successful, {len(results) - successful_feeds} failed.")

    return results


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


def update_entry(entry_id, article):
    session = Session()
    try:
        # Fetch the RssEntry object for the given entry_id
        entry = session.query(RssEntry).filter_by(id=entry_id).first()

        # Update the RssEntry object with the fetched content
        entry.content = article["content"]
        if not entry.published and "published" in article:
            entry.published = parser.parse(article["published"])
        if not entry.author and "author" in article:
            entry.author = article["author"]

        # Commit the changes to the database
        session.commit()

    finally:
        session.close()


def get_remote_content(url, entry_id):
    try:
        response = requests.get(url)
        response.raise_for_status()
        article = simple_json_from_html_string(response.text, use_readability=True)
        entry = get_feed_entry_by_id(entry_id)

        soup = BeautifulSoup(article["content"], "html.parser")

        for a in soup.find_all("a", href=True):
            if not a["href"].startswith("http"):
                a["href"] = urljoin(entry.link, a["href"])

        for img in soup.find_all("img", src=True):
            if not img["src"].startswith("http"):
                img["src"] = urljoin(entry.link, img["src"])

        article["content"] = str(soup)

        entry.content = article["content"]
        if not entry.published and "published" in article:
            entry.published = parser.parse(article["published"])
        if not entry.author and "author" in article:
            entry.author = article["author"]

        return entry

    except requests.RequestException as e:
        print(f"Error fetching remote content: {e}")
        return None


def get_feed_entries_by_feed_id(feed_id, page=1, entries_per_page=10):
    session = Session()

    query = session.query(RssEntry)

    if feed_id == "all":
        query = (
            query.order_by(desc(RssEntry.published))
            .limit(entries_per_page)
            .offset((page - 1) * entries_per_page)
        )

    else:
        query = (
            query.filter_by(feed_id=feed_id)
            .order_by(desc(RssEntry.published))
            .limit(entries_per_page)
            .offset((page - 1) * entries_per_page)
        )

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

def get_theme(theme_name):
    themes = [
        {
            "name": "light",
            "primary_colour": "#f582ae",
            "text_colour": "#172c66",
            "highlight_colour": "#8bd3dd",
            "background_colour": "#fef6e4",
        },
        {
            "name": "dark",
            "primary_colour": "#ff5277",
            "text_colour": "#ffffff",
            "highlight_colour": "#43a9a3",
            "background_colour": "#0e141b",
        },
        {
            "name": "clean",
            "primary_colour": "#ff335f",
            "text_colour": "#373a3c",
            "highlight_colour": "#43a9a3",
            "background_colour": "#ffffff",
        },
        {
            "name": "new",
            "primary_colour": "#ff335f",
            "text_colour": "#1e1e1e",
            "highlight_colour": "#43a9a3",
            "background_colour": "#fffcf2",
        }
    ]

    if theme_name == "default":
        session = Session()
        theme_name = Settings.get_setting(session, "theme")
        if not theme_name:
            theme_name = "light"
            Settings.set_setting(session, "theme", theme_name)

        session.close()

    for theme in themes:
        if theme["name"] == theme_name:
            return theme

    return None

def set_default_theme(theme_name):
    session = Session()
    Settings.set_setting(session, "theme", theme_name)
    session.commit()
    session.close()
