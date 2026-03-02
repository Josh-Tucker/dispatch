import concurrent.futures
import random
import time
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING, Any
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

CIRCUIT_BREAKER_THRESHOLD = 5


def _build_cache_headers(feed: RssFeed) -> dict[str, str]:
    """Build HTTP caching headers for feed request."""
    headers = {}
    if feed.etag:
        headers["If-None-Match"] = feed.etag
    if feed.last_modified:
        headers["If-Modified-Since"] = feed.last_modified
    return headers


def _check_head_response_cache(
    head_response: requests.Response, feed: RssFeed
) -> tuple[bool, str] | None:
    """Check HEAD response for cache status. Returns tuple or None to continue."""
    if head_response.status_code == 304:
        print(f"Feed {feed.title} not modified (304) - skipping")
        return True, "Feed not modified"

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
                return True, "Feed content length unchanged"
        except (ValueError, TypeError):
            pass

    return None


def _update_feed_cache_info(feed: RssFeed, response: requests.Response) -> None:
    """Update feed cache information from response headers."""
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


def _update_feed_url_if_redirected(feed: RssFeed, response: requests.Response) -> None:
    """If the feed permanently redirected, update the stored URL to the final URL."""
    if response.url and response.url != feed.url and response.history:
        first_status = response.history[0].status_code
        if first_status == 301:
            print(
                f"Feed {feed.title} permanently moved: {feed.url} -> {response.url}"
            )
            feed.url = response.url


def _fetch_feed_with_caching(feed: RssFeed) -> tuple[bool, str, dict | None]:
    """
    Fetch RSS feed content with HTTP caching support.

    Returns:
        tuple: (success, message, parsed_feed_data)
    """
    try:
        headers = _build_cache_headers(feed)

        try:
            head_response = requests.head(feed.url or "", headers=headers, timeout=15)
            cache_result = _check_head_response_cache(head_response, feed)
            if cache_result:
                return cache_result[0], cache_result[1], None
        except requests.exceptions.RequestException:
            pass

        try:
            response = requests.get(feed.url or "", headers=headers, timeout=15)

            if response.status_code == 304:
                print(f"Feed {feed.title} not modified (304) - skipping")
                return True, "Feed not modified", None

            if response.status_code >= 400:
                print(f"HTTP error {response.status_code} for feed {feed.title}")
                return False, f"HTTP error {response.status_code}", None

            _update_feed_cache_info(feed, response)
            _update_feed_url_if_redirected(feed, response)
            parsed_feed = feedparser.parse(response.content)

        except requests.exceptions.RequestException as req_error:
            print(f"Request error for feed {feed.title}: {req_error}")
            parsed_feed = feedparser.parse(feed.url)

        if hasattr(parsed_feed, "status") and getattr(parsed_feed, "status", 0) >= 400:
            status = getattr(parsed_feed, "status", 0)
            print(f"HTTP error {status} for feed {feed.title}")
            return False, f"HTTP error {status}", None

        return True, "Feed fetched successfully", parsed_feed

    except Exception as parse_error:
        print(f"Parse error for feed {feed.title}: {parse_error}")
        return False, f"Parse error: {parse_error}", None


def _process_feed_entry(entry_data: Any, feed_id: int, session: "SessionType") -> bool:
    """
    Process a single feed entry and add it to the database if it's new.

    Deduplication checks GUID first (stable RSS/Atom identifier), then falls
    back to link. Entries missing both are skipped.

    Returns:
        bool: True if entry was added, False if skipped (already exists or error)
    """
    try:
        guid = ""
        if hasattr(entry_data, "guid"):
            guid = entry_data.guid
        elif hasattr(entry_data, "id"):
            guid = entry_data.id

        link = getattr(entry_data, "link", None) or ""

        if not guid and not link:
            print(
                f"Skipping entry with no guid or link: "
                f"{getattr(entry_data, 'title', 'Unknown')}"
            )
            return False

        # Prefer GUID for deduplication; fall back to link
        if guid:
            existing_entry = (
                session.query(RssEntry)
                .filter_by(feed_id=feed_id, guid=guid)
                .first()
            )
        else:
            existing_entry = (
                session.query(RssEntry)
                .filter_by(feed_id=feed_id, link=link)
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

        rss_entry = RssEntry(
            feed_id=feed_id,
            title=getattr(entry_data, "title", None),
            link=link or None,
            description=description,
            content=content,
            published=published_date,
            author=author,
            guid=guid or None,
        )

        session.add(rss_entry)
        return True

    except Exception as entry_error:
        print(
            f"Error processing entry {getattr(entry_data, 'title', 'Unknown')}: "
            f"{entry_error}"
        )
        return False


def _record_fetch_success(feed: RssFeed, session: "SessionType") -> None:
    """Reset error counters and record a successful fetch timestamp."""
    now = datetime.utcnow()
    feed.last_fetch_at = now
    feed.last_success_at = now
    feed.consecutive_errors = 0
    feed.last_error = None


def _record_fetch_failure(feed: RssFeed, message: str, session: "SessionType") -> None:
    """Increment error counter and store the error message."""
    feed.last_fetch_at = datetime.utcnow()
    feed.consecutive_errors = (feed.consecutive_errors or 0) + 1
    feed.last_error = message


def add_rss_entries_for_feed(feed_id: int, max_retries: int = 3) -> tuple[bool, str]:
    """
    Adds RSS entries from a specific feed to the database.
    Attempts to process feeds even if parsing exceptions occur.

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

            if feed.is_muted:
                session.close()
                return True, "Feed is muted — skipping"

            print(f"Processing feed: {feed.title}")

            success, message, parsed_feed = _fetch_feed_with_caching(feed)

            if not success:
                _record_fetch_failure(feed, message, session)
                session.commit()
                session.close()
                return False, message

            if parsed_feed is None:
                # 304 / cache hit — counts as success
                _record_fetch_success(feed, session)
                session.commit()
                session.close()
                return True, message

            entries_added = 0
            entries = getattr(parsed_feed, "entries", [])
            for entry in entries:
                if _process_feed_entry(entry, feed_id, session):
                    entries_added += 1

            _record_fetch_success(feed, session)
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
    """Alias for add_rss_entries_for_feed for backward compatibility."""
    return add_rss_entries_for_feed(feed_id, max_retries)


def add_rss_entries_for_all_feeds(max_workers: int = 3) -> list[dict[str, Any]]:
    """
    Process all RSS feeds in parallel, adding new entries to the database.
    Feeds that are muted or have hit the circuit-breaker threshold are skipped.

    Returns:
        list: Results of processing each feed (success/failure status and messages)
    """
    print(
        f"Adding feed items with {max_workers} workers (reduced for SQLite stability)"
    )

    session = Session()
    feeds = session.query(RssFeed).all()
    feed_ids = [feed.id for feed in feeds]
    muted_or_broken = {
        feed.id
        for feed in feeds
        if feed.is_muted
        or (feed.consecutive_errors or 0) >= CIRCUIT_BREAKER_THRESHOLD
    }
    session.close()

    if not feed_ids:
        print("No feeds found to process")
        return []

    active_ids = [fid for fid in feed_ids if fid not in muted_or_broken]
    skipped_count = len(feed_ids) - len(active_ids)
    if skipped_count:
        print(
            f"Skipping {skipped_count} muted/broken feed(s) "
            f"(circuit breaker threshold: {CIRCUIT_BREAKER_THRESHOLD})"
        )
    print(f"Processing {len(active_ids)} feeds with {max_workers} workers")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        process_func = partial(add_rss_entries_for_feed)

        future_to_feed_id = {
            executor.submit(process_func, feed_id): feed_id
            for feed_id in active_ids
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

    # Add skipped entries to results
    for feed_id in muted_or_broken:
        results.append(
            {"feed_id": feed_id, "success": True, "message": "Skipped (muted/broken)"}
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


def update_entry(entry_id: int, article: dict[str, Any]) -> None:
    session = Session()
    try:
        entry = session.query(RssEntry).filter_by(id=entry_id).first()

        if entry is None:
            print(f"Entry with ID {entry_id} not found")
            return

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


def get_remote_content(url: str, entry_id: int) -> dict[str, Any] | None:
    try:
        response = requests.get(url)
        response.raise_for_status()
        article = simple_json_from_html_string(response.text, use_readability=True)
        get_feed_entry_by_id(entry_id)

        content = article.get("content", "") or ""
        soup = BeautifulSoup(content, "html.parser")

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
