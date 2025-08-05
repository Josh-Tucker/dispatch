import mimetypes
from typing import Any
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from models import RssEntry, RssFeed, Session, Settings
from sqlalchemy import desc, func


def get_favicon_url(feed_url: str) -> str | None:
    if "http" not in feed_url:
        feed_url = "http://" + feed_url

    try:
        page = requests.get(feed_url, timeout=10)
        soup = BeautifulSoup(page.text, features="lxml")

        icon_link = soup.find("link", rel="shortcut icon")
        if icon_link is None:
            icon_link = soup.find("link", rel="icon")

        if icon_link is None:
            parsed_url = urlparse(feed_url)
            return f"{parsed_url.scheme}://{parsed_url.netloc}/favicon.ico"

        favicon_url = None
        if icon_link and hasattr(icon_link, "get"):
            favicon_url = getattr(icon_link, "href", None)
        if favicon_url:
            # Handle case where favicon_url might be a list
            if isinstance(favicon_url, list):
                favicon_url = favicon_url[0] if favicon_url else None

            if (
                favicon_url
                and isinstance(favicon_url, str)
                and not favicon_url.startswith("http")
            ):
                parsed_url = urlparse(feed_url)
                if favicon_url.startswith("//"):
                    favicon_url = f"{parsed_url.scheme}:{favicon_url}"
                elif favicon_url.startswith("/"):
                    favicon_url = (
                        f"{parsed_url.scheme}://{parsed_url.netloc}{favicon_url}"
                    )
                else:
                    favicon_url = urljoin(feed_url, favicon_url)

        return favicon_url
    except Exception as e:
        print(f"Error getting favicon URL: {e}")
        return None


def download_and_store_favicon(feed_url: str) -> tuple[bytes | None, str | None]:
    """Download favicon and return binary data and MIME type."""
    favicon_url = get_favicon_url(feed_url)
    if not favicon_url or not isinstance(favicon_url, str):
        return None, None

    try:
        favicon_response = requests.get(favicon_url, timeout=10)
        if favicon_response.status_code == 200:
            content_type = favicon_response.headers.get("content-type", "")
            if content_type:
                mime_type = content_type.split(";")[0].strip()
            else:
                mime_type, _ = (
                    mimetypes.guess_type(favicon_url)
                    if isinstance(favicon_url, str)
                    else (None, None)
                )
                if not mime_type and isinstance(favicon_url, str):
                    favicon_url_lower = favicon_url.lower()
                    if favicon_url_lower.endswith(".ico"):
                        mime_type = "image/x-icon"
                    elif favicon_url_lower.endswith(".png"):
                        mime_type = "image/png"
                    elif favicon_url_lower.endswith((".jpg", ".jpeg")):
                        mime_type = "image/jpeg"
                    elif favicon_url_lower.endswith(".svg"):
                        mime_type = "image/svg+xml"
                    else:
                        mime_type = "image/x-icon"

            return favicon_response.content, mime_type
    except Exception as e:
        print(f"Error downloading favicon from {favicon_url}: {e}")

    return None, None


def add_feed(feed_url: str) -> None:
    print(feed_url)
    session = Session()
    try:
        existing_feed = session.query(RssFeed).filter_by(url=feed_url).first()

        if existing_feed:
            session.close()
            return

        feed = feedparser.parse(feed_url)

        # Safely access feedparser attributes
        feed_info = getattr(feed, "feed", {})
        feed_link = (
            getattr(feed_info, "link", None)
            if hasattr(feed_info, "link")
            else feed_info.get("link")
        )
        feed_title = (
            getattr(feed_info, "title", None)
            if hasattr(feed_info, "title")
            else feed_info.get("title")
        )
        feed_description = (
            getattr(feed_info, "description", None)
            if hasattr(feed_info, "description")
            else feed_info.get("description")
        )

        favicon_data, favicon_mime_type = download_and_store_favicon(
            feed_link or feed_url
        )

        rss_feed = RssFeed(
            url=feed_url,
            title=feed_title,
            link=feed_link,
            description=feed_description,
            favicon_data=favicon_data,
            favicon_mime_type=favicon_mime_type,
        )

        session.add(rss_feed)
        session.commit()

        # Capture title before closing session to avoid detached instance error
        feed_title = rss_feed.title

        session.close()
        print(f"Feed added: {feed_title}")
        if favicon_data:
            print(
                f"Favicon stored in database ({len(favicon_data)} bytes, "
                f"{favicon_mime_type})"
            )
    except Exception as e:
        session.rollback()
        session.close()
        print(f"Error adding feed: {e}")


def refresh_feed_favicon(feed_id: int) -> bool:
    """Refresh the favicon for a specific feed."""
    session = Session()
    try:
        feed = session.query(RssFeed).filter_by(id=feed_id).first()
        if not feed:
            print(f"Feed with ID {feed_id} not found.")
            return False

        favicon_data, favicon_mime_type = download_and_store_favicon(
            feed.link or feed.url
        )

        if favicon_data:
            feed.favicon_data = favicon_data
            feed.favicon_mime_type = favicon_mime_type
            session.commit()
            print(
                f"Favicon refreshed for feed: {feed.title} "
                f"({len(favicon_data)} bytes, {favicon_mime_type})"
            )
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


def refresh_all_feed_favicons() -> dict[str, int]:
    """Refresh favicons for all feeds."""
    session = Session()
    try:
        feeds = session.query(RssFeed).all()
        success_count = 0

        for feed in feeds:
            print(f"Refreshing favicon for: {feed.title}")

            favicon_data, favicon_mime_type = download_and_store_favicon(
                feed.link or feed.url
            )

            if favicon_data:
                feed.favicon_data = favicon_data
                feed.favicon_mime_type = favicon_mime_type
                success_count += 1
                print(f"  ✓ Updated ({len(favicon_data)} bytes, {favicon_mime_type})")
            else:
                print("  ✗ Could not fetch favicon")

        session.commit()
        print(f"Favicon refresh completed: {success_count}/{len(feeds)} feeds updated")
        return success_count, len(feeds)

    except Exception as e:
        session.rollback()
        print(f"Error refreshing all favicons: {e}")
        return 0, 0
    finally:
        session.close()


def remove_feed(feed_id: int) -> None:
    session = Session()

    try:
        feed = session.query(RssFeed).filter_by(id=feed_id).first()
        if feed:
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


def _get_feed_counts(
    session: Session, feed_ids: list[int]
) -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
    """Get unread, total, and read counts for feeds."""
    unread_counts_query = (
        session.query(RssEntry.feed_id, func.count(RssEntry.id).label("unread_count"))
        .filter(RssEntry.feed_id.in_(feed_ids))
        .filter(~RssEntry.read)
        .group_by(RssEntry.feed_id)
        .all()
    )
    unread_counts = {row[0]: row[1] for row in unread_counts_query}

    total_counts_query = (
        session.query(RssEntry.feed_id, func.count(RssEntry.id).label("total_count"))
        .filter(RssEntry.feed_id.in_(feed_ids))
        .group_by(RssEntry.feed_id)
        .all()
    )
    total_counts = {row[0]: row[1] for row in total_counts_query}

    read_counts_query = (
        session.query(RssEntry.feed_id, func.count(RssEntry.id).label("read_count"))
        .filter(RssEntry.feed_id.in_(feed_ids))
        .filter(RssEntry.read.is_(True))
        .group_by(RssEntry.feed_id)
        .all()
    )
    read_counts = {row[0]: row[1] for row in read_counts_query}

    return unread_counts, total_counts, read_counts


def _get_latest_entry_dates(session: Session, feed_ids: list[int]) -> dict[int, Any]:
    """Get latest entry dates for feeds."""
    latest_entries_subquery = (
        session.query(
            RssEntry.feed_id, func.max(RssEntry.published).label("latest_published")
        )
        .filter(RssEntry.feed_id.in_(feed_ids))
        .group_by(RssEntry.feed_id)
        .subquery()
    )

    latest_entries_query = (
        session.query(RssEntry.feed_id, RssEntry.published)
        .join(
            latest_entries_subquery,
            (RssEntry.feed_id == latest_entries_subquery.c.feed_id)
            & (RssEntry.published == latest_entries_subquery.c.latest_published),
        )
        .all()
    )
    return {row[0]: row[1] for row in latest_entries_query}


def _get_latest_unread_dates(session: Session, feed_ids: list[int]) -> dict[int, Any]:
    """Get latest unread entry dates for feeds."""
    latest_unread_subquery = (
        session.query(
            RssEntry.feed_id,
            func.max(RssEntry.published).label("latest_unread_published"),
        )
        .filter(RssEntry.feed_id.in_(feed_ids))
        .filter(~RssEntry.read)
        .group_by(RssEntry.feed_id)
        .subquery()
    )

    latest_unread_query = (
        session.query(RssEntry.feed_id, RssEntry.published)
        .join(
            latest_unread_subquery,
            (RssEntry.feed_id == latest_unread_subquery.c.feed_id)
            & (RssEntry.published == latest_unread_subquery.c.latest_unread_published),
        )
        .filter(~RssEntry.read)
        .all()
    )
    return {int(row[0]): row[1] for row in latest_unread_query}


def _get_latest_titles(session: Session, feed_ids: list[int]) -> dict[int, list[str]]:
    """Get latest entry titles for feeds."""
    latest_titles_query = (
        session.query(RssEntry.feed_id, RssEntry.title, RssEntry.published)
        .filter(RssEntry.feed_id.in_(feed_ids))
        .filter(RssEntry.title.isnot(None))
        .order_by(RssEntry.feed_id, desc(RssEntry.published))
        .all()
    )

    latest_titles = {}
    for feed_id, title, _published in latest_titles_query:
        if feed_id not in latest_titles:
            latest_titles[feed_id] = []
        if len(latest_titles[feed_id]) < 3:
            latest_titles[feed_id].append(title)

    return latest_titles


def get_all_feeds(sort_by: str = "title") -> list[RssFeed]:
    session = Session()

    try:
        feeds = session.query(RssFeed).order_by(desc(RssFeed.pinned)).all()

        if not feeds:
            all_feed = RssFeed(id="all", title="All Feeds")
            all_feed.unread_count = 0
            all_feed.last_unread_entry_date = None
            all_feed.latest_entry_titles = []
            all_feed.read_frequency = 0.0
            session.close()
            return [all_feed]

        feed_ids = [feed.id for feed in feeds]

        # Get all feed statistics using helper functions
        unread_counts, total_counts, read_counts = _get_feed_counts(session, feed_ids)
        latest_entry_dates = _get_latest_entry_dates(session, feed_ids)
        latest_unread_dates = _get_latest_unread_dates(session, feed_ids)
        latest_titles = _get_latest_titles(session, feed_ids)

        total_unread_count = sum(unread_counts.values())

        for feed in feeds:
            feed.unread_count = unread_counts.get(feed.id, 0)
            feed.last_new_article_found = latest_entry_dates.get(int(feed.id), None)
            feed.last_unread_entry_date = latest_unread_dates.get(feed.id, None)
            feed.latest_entry_titles = latest_titles.get(feed.id, [])

            total_count = total_counts.get(feed.id, 0)
            read_count = read_counts.get(feed.id, 0)
            if total_count > 0:
                feed.read_frequency = (read_count / total_count) * 100
            else:
                feed.read_frequency = 0.0

        all_feed = RssFeed(id="all", title="All Feeds")
        all_feed.unread_count = total_unread_count
        all_feed.last_unread_entry_date = None
        all_feed.latest_entry_titles = []
        all_feed.read_frequency = 0.0

        session.close()
        return [all_feed, *feeds]

    except Exception as e:
        session.close()
        print(f"Error fetching feeds: {e}")

        try:
            feeds = session.query(RssFeed).order_by(desc(RssFeed.pinned)).all()
            for feed in feeds:
                feed.unread_count = 0
                feed.last_unread_entry_date = None
                feed.latest_entry_titles = []
                feed.read_frequency = 0.0

            all_feed = RssFeed(id="all", title="All Feeds")
            all_feed.unread_count = 0
            all_feed.last_unread_entry_date = None
            all_feed.latest_entry_titles = []
            all_feed.read_frequency = 0.0

            return [all_feed, *feeds]
        except Exception as e2:
            print(f"Fallback also failed: {e2}")
            return []


def get_feed_by_id(feed_id: int) -> RssFeed | None:
    session = Session()
    feed = session.query(RssFeed).filter_by(id=feed_id).first()
    if feed:
        feed.unread_count = feed.get_unread_count(session)
        # Calculate the latest published date from entries for this feed
        latest_entry = (
            session.query(RssEntry)
            .filter_by(feed_id=feed.id)
            .order_by(desc(RssEntry.published))
            .first()
        )
        feed.last_new_article_found = latest_entry.published if latest_entry else None
        # Calculate the latest unread entry date for this feed
        latest_unread_entry = (
            session.query(RssEntry)
            .filter_by(feed_id=feed.id, read=False)
            .order_by(desc(RssEntry.published))
            .first()
        )
        feed.last_unread_entry_date = (
            latest_unread_entry.published if latest_unread_entry else None
        )
        # Get latest entry titles for preview (last 3 entries)
        latest_entries = (
            session.query(RssEntry)
            .filter_by(feed_id=feed.id)
            .order_by(desc(RssEntry.published))
            .limit(3)
            .all()
        )
        feed.latest_entry_titles = [
            entry.title for entry in latest_entries if entry.title
        ]
        feed.read_frequency = feed.get_read_frequency(session)
        # Add frequency data for sparkline graph
        feed.frequency_data = get_feed_frequency_data(feed.id)
    session.close()
    return feed


def toggle_feed_pin(feed_id: int) -> bool | None:
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


def get_feed_sort_preference() -> str:
    """Get the current feed sorting preference from settings."""
    session = Session()
    try:
        setting = Settings.get_setting(session, "feed_sort_by")
        return setting if setting else "title"
    finally:
        session.close()


def set_feed_sort_preference(sort_by: str) -> bool:
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


def get_feed_frequency_data(feed_id: int, weeks: int = 12) -> list[int]:
    """Get frequency data for sparkline graph showing posts per week over time."""
    session = Session()
    try:
        from datetime import datetime, timedelta

        from sqlalchemy import func

        # Calculate date range (last N weeks)
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=weeks)

        # Use SQL to group by week and count entries efficiently
        weekly_counts = (
            session.query(
                func.strftime("%Y-%W", RssEntry.published).label("week"),
                func.count(RssEntry.id).label("count"),
            )
            .filter(
                RssEntry.feed_id == feed_id,
                RssEntry.published >= start_date,
                RssEntry.published <= end_date,
            )
            .group_by(func.strftime("%Y-%W", RssEntry.published))
            .all()
        )

        # Convert to dict for easy lookup
        week_counts = {row[0]: row[1] for row in weekly_counts}

        # Generate frequency data for each week
        frequency_data = []
        current_week_start = start_date

        for _week_num in range(weeks):
            week_key = current_week_start.strftime("%Y-%W")
            count = week_counts.get(week_key, 0)
            frequency_data.append(count)
            current_week_start += timedelta(days=7)

        return frequency_data

    except Exception as e:
        print(f"Error getting frequency data for feed {feed_id}: {e}")
        return [0] * weeks
    finally:
        session.close()


def parse_tags_string(tags_string: str | None) -> list[str]:
    """Parse a comma-separated string of tags into a list."""
    if not tags_string:
        return []
    return [tag.strip() for tag in tags_string.split(",") if tag.strip()]


def format_tags_list(tags_list: list[str] | None) -> str | None:
    """Format a list of tags into a comma-separated string."""
    if not tags_list:
        return None
    return ", ".join(tag.strip() for tag in tags_list if tag.strip())


def get_all_tags() -> list[str]:
    """Get all unique tags from all feeds."""
    session = Session()
    try:
        feeds = session.query(RssFeed).filter(RssFeed.tags.isnot(None)).all()
        all_tags = set()
        for feed in feeds:
            if feed.tags:
                tags = parse_tags_string(feed.tags)
                all_tags.update(tags)
        return sorted(all_tags)
    finally:
        session.close()


def get_feeds_by_tag(tag: str) -> list[RssFeed]:
    """Get all feeds that have a specific tag."""
    session = Session()
    try:
        feeds = session.query(RssFeed).filter(RssFeed.tags.like(f"%{tag}%")).all()
        # Filter to ensure exact tag match (not substring)
        matching_feeds = []
        for feed in feeds:
            if feed.tags:
                feed_tags = parse_tags_string(feed.tags)
                if tag in feed_tags:
                    feed.unread_count = feed.get_unread_count(session)
                    # Calculate the latest published date from entries for this feed
                    latest_entry = (
                        session.query(RssEntry)
                        .filter_by(feed_id=feed.id)
                        .order_by(desc(RssEntry.published))
                        .first()
                    )
                    feed.last_new_article_found = (
                        latest_entry.published if latest_entry else None
                    )
                    # Calculate the latest unread entry date for this feed
                    latest_unread_entry = (
                        session.query(RssEntry)
                        .filter_by(feed_id=feed.id, read=False)
                        .order_by(desc(RssEntry.published))
                        .first()
                    )
                    feed.last_unread_entry_date = (
                        latest_unread_entry.published if latest_unread_entry else None
                    )
                    # Get latest entry titles for preview (last 3 entries)
                    latest_entries = (
                        session.query(RssEntry)
                        .filter_by(feed_id=feed.id)
                        .order_by(desc(RssEntry.published))
                        .limit(3)
                        .all()
                    )
                    feed.latest_entry_titles = [
                        entry.title for entry in latest_entries if entry.title
                    ]
                    feed.read_frequency = feed.get_read_frequency(session)
                    # Add frequency data for sparkline graph
                    feed.frequency_data = get_feed_frequency_data(feed.id)
                    matching_feeds.append(feed)
        return matching_feeds
    finally:
        session.close()


def update_feed_tags(feed_id: int, tags_string: str) -> bool:
    """Update the tags for a specific feed."""
    session = Session()
    try:
        feed = session.query(RssFeed).filter_by(id=feed_id).first()
        if feed:
            # Clean up the tags string
            if tags_string:
                tags_list = parse_tags_string(tags_string)
                feed.tags = format_tags_list(tags_list)
            else:
                feed.tags = None
            session.commit()
            print(f"Tags updated for feed '{feed.title}': {feed.tags}")
            return True
        else:
            print(f"Feed with ID {feed_id} not found.")
            return False
    except Exception as e:
        session.rollback()
        print(f"Error updating feed tags: {e}")
        return False
    finally:
        session.close()
