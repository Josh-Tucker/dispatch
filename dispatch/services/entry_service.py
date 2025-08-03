import concurrent.futures
import random
import time
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser
from models import RssEntry, RssFeed, Session
from readabilipy import simple_json_from_html_string
from sqlalchemy import desc
from sqlalchemy.orm import joinedload

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SessionType


def _fetch_feed_with_caching(feed: RssFeed) -> tuple[bool, str, dict | None]:
    """
    Fetch RSS feed content with HTTP caching support.

    Args:
        feed: The RssFeed object to fetch

    Returns:
        tuple: (success, message, parsed_feed_data)
    """
    try:
        headers = {}
        if feed.etag:
            headers["If-None-Match"] = feed.etag
        if feed.last_modified:
            headers["If-Modified-Since"] = feed.last_modified

        try:
            head_response = requests.head(feed.url or "", headers=headers, timeout=15)

            if head_response.status_code == 304:
                print(f"Feed {feed.title} not modified (304) - skipping")
                return True, "Feed not modified", None

            if (
                head_response.status_code == 200
                and "content-length" in head_response.headers
                and feed.content_length is not None
            ):
                try:
                    head_content_length = int(head_response.headers["content-length"])
                    if head_content_length == feed.content_length:
                        print(
                            f"Feed {feed.title} content length unchanged "
                            f"({head_content_length} bytes) - skipping"
                        )
                        return True, "Feed content length unchanged", None
                except (ValueError, TypeError):
                    pass

        except requests.exceptions.RequestException:
            pass

        try:
            response = requests.get(feed.url or "", headers=headers, timeout=15)

            if response.status_code == 304:
                print(f"Feed {feed.title} not modified (304) - skipping")
                return True, "Feed not modified", None

            if hasattr(response, "status_code") and response.status_code >= 400:  # type: ignore[attr-defined]
                print(f"HTTP error {response.status_code} for feed {feed.title}")
                return False, f"HTTP error {response.status_code}", None

            if "etag" in response.headers:
                feed.etag = response.headers["etag"]
            if "last-modified" in response.headers:
                feed.last_modified = response.headers["last-modified"]

            current_content_length = len(response.content)
            if "content-length" in response.headers:
                try:
                    feed.content_length = int(response.headers["content-length"])
                except (ValueError, TypeError):
                    feed.content_length = current_content_length
            else:
                feed.content_length = current_content_length

            parsed_feed = feedparser.parse(response.content)

        except requests.exceptions.RequestException as req_error:
            print(f"Request error for feed {feed.title}: {req_error}")
            parsed_feed = feedparser.parse(feed.url)

        if hasattr(parsed_feed, "status") and parsed_feed.status >= 400:
            print(f"HTTP error {parsed_feed.status} for feed {feed.title}")
            return False, f"HTTP error {parsed_feed.status}", None

        return True, "Feed fetched successfully", parsed_feed

    except Exception as parse_error:
        print(f"Parse error for feed {feed.title}: {parse_error}")
        return False, f"Parse error: {parse_error}", None


def _process_feed_entry(entry_data, feed_id: int, session: "SessionType") -> bool:
    """
    Process a single feed entry and add it to the database if it's new.

    Args:
        entry_data: Entry object from feedparser with attributes like title, link, etc.
        feed_id: ID of the feed this entry belongs to
        session: Database session to use

    Returns:
        bool: True if entry was added, False if skipped (already exists or error)
    """
    try:
        existing_entry = (
            session.query(RssEntry)
            .filter_by(feed_id=feed_id, link=entry_data.link)
            .first()
        )

        if existing_entry:
            return False

        published_date = None
        if hasattr(entry_data, "published"):
            try:
                published_date = parser.parse(entry_data.published)
            except Exception as date_error:
                print(f"Date parse error for entry {entry_data.title}: {date_error}")
                published_date = datetime.now()
        else:
            published_date = datetime.now()

        description = ""
        if hasattr(entry_data, "summary"):
            description = entry_data.summary
        elif hasattr(entry_data, "description"):
            description = entry_data.description

        content = ""
        if (
            hasattr(entry_data, "content")
            and entry_data.content
            and len(entry_data.content) > 0
        ):
            content = entry_data.content[0].get("value", "")
        elif hasattr(entry_data, "summary_detail") and hasattr(
            entry_data.summary_detail, "value"
        ):
            content = entry_data.summary_detail.value
        else:
            content = description

        author = ""
        if hasattr(entry_data, "author"):
            author = entry_data.author

        guid = ""
        if hasattr(entry_data, "guid"):
            guid = entry_data.guid
        elif hasattr(entry_data, "id"):
            guid = entry_data.id

        rss_entry = RssEntry(
            feed_id=feed_id,
            title=entry_data.title,
            link=entry_data.link,
            description=description,
            content=content,
            published=published_date,
            author=author,
            guid=guid,
        )

        session.add(rss_entry)
        return True

    except Exception as entry_error:
        print(
            f"Error processing entry {getattr(entry_data, 'title', 'Unknown')}: "
            f"{entry_error}"
        )
        return False


def add_rss_entries_for_feed(feed_id: int, max_retries: int = 3) -> tuple[bool, str]:
    """
    Adds RSS entries from a specific feed to the database.
    Attempts to process feeds even if parsing exceptions occur.

    Args:
        feed_id: The ID of the RSS feed to process
        max_retries: Maximum number of retry attempts for database operations

    Returns:
        tuple: (success_flag, message)
    """
    for attempt in range(max_retries):
        session = Session()
        try:
            feed = session.query(RssFeed).filter_by(id=feed_id).first()
            if not feed:
                session.close()
                return False, f"Feed with ID {feed_id} not found"

            print(f"Processing feed: {feed.title}")

            success, message, parsed_feed = _fetch_feed_with_caching(feed)
            if not success or parsed_feed is None:
                session.close()
                return success, message

            entries_added = 0
            for entry in parsed_feed.entries:
                if _process_feed_entry(entry, feed_id, session):
                    entries_added += 1

            session.commit()
            print(f"Added {entries_added} new entries for feed: {feed.title}")

            session.close()
            return True, f"Added {entries_added} entries"

        except Exception as e:
            session.rollback()
            session.close()

            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2 + random.uniform(0, 1)
                print(
                    f"Database locked for feed {feed_id}, retrying in {wait_time:.1f} "
                    f"seconds (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)
                continue
            else:
                print(f"Error processing feed {feed_id}: {e}")
                return False, f"Error: {e}"

    return False, "Max retries exceeded"


def add_rss_entries(feed_id: int, max_retries: int = 3) -> tuple[bool, str]:
    """
    Fetches and adds RSS entries for a specific feed to the database.
    This is an alias for add_rss_entries_for_feed for backward compatibility.

    Args:
        feed_id: The ID of the RSS feed to process
        max_retries: Maximum number of retry attempts for database operations

    Returns:
        tuple: (success_flag, message)
    """
    return add_rss_entries_for_feed(feed_id, max_retries)


def add_rss_entries_for_all_feeds(max_workers: int = 3) -> list[dict]:
    """
    Process all RSS feeds in parallel, adding new entries to the database.

    Args:
        max_workers: Maximum number of worker threads to use for parallel processing
                    (reduced for SQLite)

    Returns:
        list: Results of processing each feed (success/failure status and messages)
    """
    print(
        f"Adding feed items with {max_workers} workers (reduced for SQLite stability)"
    )

    session = Session()
    feeds = session.query(RssFeed).all()
    feed_ids = [feed.id for feed in feeds]
    session.close()

    if not feed_ids:
        print("No feeds found to process")
        return []

    print(f"Processing {len(feed_ids)} feeds with {max_workers} workers")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        process_func = partial(add_rss_entries_for_feed)

        future_to_feed_id = {
            executor.submit(process_func, feed_id): feed_id for feed_id in feed_ids
        }

        for future in concurrent.futures.as_completed(future_to_feed_id):
            feed_id = future_to_feed_id[future]
            try:
                success, message = future.result()
                results.append(
                    {"feed_id": feed_id, "success": success, "message": message}
                )
                print(f"Feed {feed_id}: {message}")
            except Exception as exc:
                print(f"Feed {feed_id} generated an exception: {exc}")
                results.append(
                    {
                        "feed_id": feed_id,
                        "success": False,
                        "message": f"Exception: {exc}",
                    }
                )

    successful_feeds = sum(1 for result in results if result["success"])
    print(f"Completed processing {len(feed_ids)} feeds. {successful_feeds} successful.")

    return results


def get_all_feed_entries() -> list[RssEntry]:
    session = Session()
    entries = session.query(RssEntry).order_by(RssEntry.published.desc()).all()
    session.close()
    return entries


def get_feed_entry_by_id(entry_id: int, max_retries: int = 3) -> RssEntry | None:
    for attempt in range(max_retries):
        session = Session()
        try:
            entry = (
                session.query(RssEntry)
                .options(joinedload(RssEntry.feed))
                .filter_by(id=entry_id)
                .first()
            )
            if entry:
                _ = entry.id, entry.title, entry.read
                session.expunge(entry)
            session.close()
            return entry
        except Exception as e:
            session.close()
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 0.5 + random.uniform(0, 0.2)
                time.sleep(wait_time)
                continue
            else:
                print(f"Error getting entry {entry_id}: {e}")
                return None
    return None


def update_entry(entry_id: int, article: dict) -> None:
    session = Session()
    try:
        entry = session.query(RssEntry).filter_by(id=entry_id).first()

        entry.content = article["content"]
        if not entry.published and "published" in article:
            entry.published = parser.parse(article["published"])
        if not entry.author and "author" in article:
            entry.author = article["author"]

        session.commit()
        session.close()
    except Exception as e:
        session.rollback()
        session.close()
        print(f"Error updating entry: {e}")


def get_remote_content(url: str, entry_id: int) -> dict | None:
    try:
        response = requests.get(url)
        response.raise_for_status()
        article = simple_json_from_html_string(response.text, use_readability=True)
        get_feed_entry_by_id(entry_id)

        soup = BeautifulSoup(article.get("content", ""), "html.parser")

        for a in soup.find_all("a", href=True):
            if not a["href"].startswith("http"):
                a["href"] = urljoin(url, a["href"])

        for img in soup.find_all("img", src=True):
            if not img["src"].startswith("http"):
                img["src"] = urljoin(url, img["src"])

        article["content"] = str(soup)  # type: ignore[assignment]
        update_entry(entry_id, article)

        return article
    except Exception as e:
        print(f"Error fetching remote content: {e}")
        return None


def get_feed_entries_by_feed_id(
    feed_id: int | str,
    page: int = 1,
    entries_per_page: int = 10,
    max_retries: int = 3,
    feed_ids: list[int] | None = None,
) -> list[RssEntry]:
    for attempt in range(max_retries):
        session = Session()
        try:
            query = session.query(RssEntry).options(joinedload(RssEntry.feed))

            if feed_ids:
                query = (
                    query.filter(RssEntry.feed_id.in_(feed_ids))
                    .order_by(desc(RssEntry.published))
                    .limit(entries_per_page)
                    .offset((page - 1) * entries_per_page)
                )
            elif feed_id == "all":
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

            for entry in entries:
                session.expunge(entry)

            session.close()
            return entries
        except Exception as e:
            session.close()
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 0.5 + random.uniform(0, 0.2)
                time.sleep(wait_time)
                continue
            else:
                print(f"Error getting entries for feed {feed_id}: {e}")
                return []
    return []


def mark_entry_as_read(
    entry_id: int, read_status: bool = True, max_retries: int = 3
) -> None:
    for attempt in range(max_retries):
        session = Session()
        try:
            entry = session.query(RssEntry).filter_by(id=entry_id).first()

            if entry:
                entry.read = read_status
                session.commit()
                session.close()
                print(
                    f"RSS Entry with ID {entry_id} marked as "
                    f"{'read' if read_status else 'unread'}."
                )
                return
            else:
                session.close()
                print(f"RSS Entry with ID {entry_id} not found.")
                return
        except Exception as e:
            session.rollback()
            session.close()
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 0.5 + random.uniform(0, 0.2)
                time.sleep(wait_time)
                continue
            else:
                print(f"Error marking entry {entry_id} as read: {e}")
                return


def mark_feed_entries_as_read(
    feed_id: int | str, read_status: bool = True, max_retries: int = 3
) -> None:
    for attempt in range(max_retries):
        session = Session()
        try:
            if feed_id == "all":
                rss_entries = session.query(RssEntry).all()
            else:
                rss_entries = session.query(RssEntry).filter_by(feed_id=feed_id).all()

            for entry in rss_entries:
                entry.read = read_status

            session.commit()
            session.close()

            print(
                f"All RSS entries for feed ID {feed_id} marked as "
                f"{'read' if read_status else 'unread'}."
            )
            return
        except Exception as e:
            session.rollback()
            session.close()
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 0.5 + random.uniform(0, 0.2)
                time.sleep(wait_time)
                continue
            else:
                print(f"Error marking feed {feed_id} entries as read: {e}")
                return
