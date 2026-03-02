import concurrent.futures
import logging
import random
import time
from datetime import datetime
from functools import partial
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser
from models import RssEntry, RssFeed, Session
from readabilipy import simple_json_from_html_string
from sqlalchemy import desc
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)


def add_rss_entries_for_feed(feed_id, max_retries=3):
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
                return False, f"Feed with ID {feed_id} not found"

            logger.debug(f'Processing feed: "{feed.title}"')

            try:
                headers = {}
                if feed.etag:
                    headers['If-None-Match'] = feed.etag
                if feed.last_modified:
                    headers['If-Modified-Since'] = feed.last_modified

                try:
                    head_response = requests.head(feed.url, headers=headers, timeout=15)

                    if head_response.status_code == 304:
                        logger.debug(f'Feed not modified (HEAD 304): "{feed.title}"')
                        feed.last_error = None
                        feed.last_error_date = None
                        session.commit()
                        return True, "Feed not modified"

                    if (head_response.status_code == 200 and
                        'content-length' in head_response.headers and
                        feed.content_length is not None):
                        try:
                            head_content_length = int(head_response.headers['content-length'])
                            if head_content_length == feed.content_length:
                                logger.debug(f'Feed content length unchanged ({head_content_length} bytes): "{feed.title}"')
                                feed.last_error = None
                                feed.last_error_date = None
                                session.commit()
                                return True, "Feed content length unchanged"
                        except (ValueError, TypeError):
                            pass

                except requests.exceptions.RequestException:
                    pass

                try:
                    response = requests.get(feed.url, headers=headers, timeout=30)

                    if response.status_code == 304:
                        logger.debug(f'Feed not modified (GET 304): "{feed.title}"')
                        feed.last_error = None
                        feed.last_error_date = None
                        session.commit()
                        return True, "Feed not modified"

                    if response.status_code >= 400:
                        msg = f"HTTP error {response.status_code}"
                        logger.warning(f'Feed fetch failed ({response.status_code}): "{feed.title}"')
                        feed.last_error = msg
                        feed.last_error_date = datetime.now()
                        session.commit()
                        return False, msg

                    if 'etag' in response.headers:
                        feed.etag = response.headers['etag']
                    if 'last-modified' in response.headers:
                        feed.last_modified = response.headers['last-modified']

                    current_content_length = len(response.content)
                    if 'content-length' in response.headers:
                        try:
                            feed.content_length = int(response.headers['content-length'])
                        except (ValueError, TypeError):
                            feed.content_length = current_content_length
                    else:
                        feed.content_length = current_content_length

                    parsed_feed = feedparser.parse(response.content)

                except requests.exceptions.RequestException as req_error:
                    logger.warning(f'Feed request failed, falling back to direct parse: "{feed.title}" — {req_error}')
                    parsed_feed = feedparser.parse(feed.url)

                if hasattr(parsed_feed, 'status') and parsed_feed.status >= 400:
                    msg = f"HTTP error {parsed_feed.status}"
                    logger.warning(f'Feed parse failed ({parsed_feed.status}): "{feed.title}"')
                    feed.last_error = msg
                    feed.last_error_date = datetime.now()
                    session.commit()
                    return False, msg

            except Exception as parse_error:
                msg = f"Parse error: {parse_error}"
                logger.error(f'Feed parse error: "{feed.title}" — {parse_error}')
                feed.last_error = msg
                feed.last_error_date = datetime.now()
                session.commit()
                return False, msg

            entries_added = 0

            for entry in parsed_feed.entries:
                try:
                    existing_entry = session.query(RssEntry).filter_by(
                        feed_id=feed_id, link=entry.link
                    ).first()

                    if existing_entry:
                        continue

                    published_date = None
                    if hasattr(entry, 'published'):
                        try:
                            published_date = parser.parse(entry.published)
                        except Exception as date_error:
                            logger.debug(f"Date parse error for entry '{getattr(entry, 'title', entry.link)}' — {date_error}")
                            published_date = datetime.now()
                    else:
                        published_date = datetime.now()

                    description = ""
                    if hasattr(entry, 'summary'):
                        description = entry.summary
                    elif hasattr(entry, 'description'):
                        description = entry.description

                    content = ""
                    if hasattr(entry, 'content') and entry.content and len(entry.content) > 0:
                        content = entry.content[0].get('value', '')
                    elif hasattr(entry, 'summary_detail') and hasattr(entry.summary_detail, 'value'):
                        content = entry.summary_detail.value
                    else:
                        content = description

                    title = getattr(entry, 'title', None)
                    if not title:
                        raw = BeautifulSoup(content or description, 'html.parser').get_text()
                        words = raw.split()
                        title = (' '.join(words[:8]) + '…') if len(words) > 8 else ' '.join(words)
                        title = title or None

                    author = ""
                    if hasattr(entry, 'author'):
                        author = entry.author

                    guid = ""
                    if hasattr(entry, 'guid'):
                        guid = entry.guid
                    elif hasattr(entry, 'id'):
                        guid = entry.id

                    rss_entry = RssEntry(
                        feed_id=feed_id,
                        title=title,
                        link=entry.link,
                        description=description,
                        content=content,
                        published=published_date,
                        author=author,
                        guid=guid,
                    )

                    session.add(rss_entry)
                    entries_added += 1

                except Exception as entry_error:
                    logger.warning(f"Entry skipped: {getattr(entry, 'title', 'Unknown')} — {entry_error}")
                    continue

            feed.last_error = None
            feed.last_error_date = None
            session.commit()
            logger.info(f'Feed refreshed: "{feed.title}" ({entries_added} new entries)')

            return True, f"Added {entries_added} entries"

        except Exception as e:
            session.rollback()

            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2 + random.uniform(0, 1)
                logger.warning(
                    f"Database locked for feed id={feed_id} — "
                    f"retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"Feed processing failed: feed id={feed_id} — {e}")
                try:
                    with Session() as err_session:
                        err_feed = err_session.query(RssFeed).filter_by(id=feed_id).first()
                        if err_feed:
                            err_feed.last_error = str(e)
                            err_feed.last_error_date = datetime.now()
                            err_session.commit()
                except Exception:
                    pass
                return False, f"Error: {e}"
        finally:
            session.close()

    return False, "Max retries exceeded"


def add_rss_entries(feed_id, max_retries=3):
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


def add_rss_entries_for_all_feeds(max_workers=3):
    """
    Process all RSS feeds in parallel, adding new entries to the database.

    Args:
        max_workers: Maximum number of worker threads to use for parallel processing (reduced for SQLite)

    Returns:
        list: Results of processing each feed (success/failure status and messages)
    """
    logger.info(f"Starting feed refresh with {max_workers} workers")

    with Session() as session:
        feeds = session.query(RssFeed).all()
        feed_ids = [feed.id for feed in feeds]

    if not feed_ids:
        logger.info("No feeds found to process")
        return []

    logger.debug(f"Processing {len(feed_ids)} feeds with {max_workers} workers")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        process_func = partial(add_rss_entries_for_feed)

        future_to_feed_id = {
            executor.submit(process_func, feed_id): feed_id
            for feed_id in feed_ids
        }

        for future in concurrent.futures.as_completed(future_to_feed_id):
            feed_id = future_to_feed_id[future]
            try:
                success, message = future.result()
                results.append({
                    'feed_id': feed_id,
                    'success': success,
                    'message': message
                })
                logger.debug(f"Feed id={feed_id}: {message}")
            except Exception as exc:
                logger.error(f"Feed processing exception: feed id={feed_id} — {exc}")
                results.append({
                    'feed_id': feed_id,
                    'success': False,
                    'message': f"Exception: {exc}"
                })

    successful_feeds = sum(1 for result in results if result['success'])
    logger.info(f"Feed refresh completed: {successful_feeds}/{len(feed_ids)} successful")

    return results


def get_all_feed_entries():
    with Session() as session:
        return session.query(RssEntry).order_by(RssEntry.published.desc()).all()


def get_feed_entry_by_id(entry_id, max_retries=3):
    for attempt in range(max_retries):
        with Session() as session:
            try:
                entry = session.query(RssEntry).options(joinedload(RssEntry.feed)).filter_by(id=entry_id).first()
                if entry:
                    _ = entry.id, entry.title, entry.read
                    session.expunge(entry)
                return entry
            except Exception as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 0.5 + random.uniform(0, 0.2)
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Entry query failed: entry id={entry_id} — {e}")
                    return None
    return None


def update_entry(entry_id, article):
    with Session() as session:
        try:
            entry = session.query(RssEntry).filter_by(id=entry_id).first()

            entry.content = article["content"]
            if not entry.published and "published" in article:
                entry.published = parser.parse(article["published"])
            if not entry.author and "author" in article:
                entry.author = article["author"]

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Entry update failed: entry id={entry_id} — {e}")


def get_remote_content(url, entry_id):
    try:
        response = requests.get(url)
        response.raise_for_status()
        article = simple_json_from_html_string(response.text, use_readability=True)
        get_feed_entry_by_id(entry_id)

        soup = BeautifulSoup(article["content"], "html.parser")

        for a in soup.find_all("a", href=True):
            if not a["href"].startswith("http"):
                a["href"] = urljoin(url, a["href"])

        for img in soup.find_all("img", src=True):
            if not img["src"].startswith("http"):
                img["src"] = urljoin(url, img["src"])

        article["content"] = str(soup)
        update_entry(entry_id, article)

        return article
    except Exception as e:
        logger.error(f"Remote content fetch failed: {url} — {e}")
        return None


def get_feed_entries_by_feed_id(feed_id, page=1, entries_per_page=10, max_retries=3, feed_ids=None):
    for attempt in range(max_retries):
        with Session() as session:
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

                return entries
            except Exception as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 0.5 + random.uniform(0, 0.2)
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Entries query failed: feed id={feed_id} — {e}")
                    return []
    return []


def mark_entry_as_read(entry_id, read_status=True, max_retries=3):
    for attempt in range(max_retries):
        with Session() as session:
            try:
                entry = session.query(RssEntry).filter_by(id=entry_id).first()

                if entry:
                    entry.read = read_status
                    session.commit()
                    logger.debug(f"Entry marked as {'read' if read_status else 'unread'}: entry id={entry_id}")
                    return
                else:
                    logger.warning(f"Mark-read skipped — entry id={entry_id} not found")
                    return
            except Exception as e:
                session.rollback()
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 0.5 + random.uniform(0, 0.2)
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Mark-read failed: entry id={entry_id} — {e}")
                    return


def mark_feed_entries_as_read(feed_id, read_status=True, max_retries=3):
    for attempt in range(max_retries):
        with Session() as session:
            try:
                if feed_id == "all":
                    rss_entries = session.query(RssEntry).all()
                else:
                    rss_entries = session.query(RssEntry).filter_by(feed_id=feed_id).all()

                for entry in rss_entries:
                    entry.read = read_status

                session.commit()
                logger.info(f"All entries marked as {'read' if read_status else 'unread'}: feed id={feed_id}")
                return
            except Exception as e:
                session.rollback()
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 0.5 + random.uniform(0, 0.2)
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Mark-all-read failed: feed id={feed_id} — {e}")
                    return
