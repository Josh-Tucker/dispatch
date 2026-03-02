import logging
import mimetypes
from datetime import datetime
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from models import RssEntry, RssFeed, Session, Settings
from sqlalchemy import desc, func
from .utils import db_retry

logger = logging.getLogger(__name__)


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
            parsed_url = urlparse(feed_url)
            return f"{parsed_url.scheme}://{parsed_url.netloc}/favicon.ico"

        favicon_url = icon_link.get("href")
        if favicon_url and not favicon_url.startswith('http'):
            parsed_url = urlparse(feed_url)
            if favicon_url.startswith('//'):
                favicon_url = f"{parsed_url.scheme}:{favicon_url}"
            elif favicon_url.startswith('/'):
                favicon_url = f"{parsed_url.scheme}://{parsed_url.netloc}{favicon_url}"
            else:
                favicon_url = urljoin(feed_url, favicon_url)

        return favicon_url
    except Exception as e:
        logger.warning(f"Favicon URL lookup failed — {e}")
        return None


def download_and_store_favicon(feed_url):
    """Download favicon and return binary data and MIME type."""
    favicon_url = get_favicon_url(feed_url)
    if not favicon_url:
        return None, None

    try:
        favicon_response = requests.get(favicon_url, timeout=10)
        if favicon_response.status_code == 200:
            content_type = favicon_response.headers.get('content-type', '')
            if content_type:
                mime_type = content_type.split(';')[0].strip()
            else:
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
                        mime_type = 'image/x-icon'

            return favicon_response.content, mime_type
    except Exception as e:
        logger.warning(f"Favicon download failed: {favicon_url} — {e}")

    return None, None


def add_feed(feed_url):
    logger.debug(f"add_feed: {feed_url}")
    with Session() as session:
        try:
            existing_feed = session.query(RssFeed).filter_by(url=feed_url).first()
            if existing_feed:
                return

            feed = feedparser.parse(feed_url)

            favicon_data, favicon_mime_type = download_and_store_favicon(feed.feed.link or feed_url)

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
            if favicon_data:
                logger.info(f'Feed added: "{rss_feed.title}" ({len(favicon_data)} bytes favicon, {favicon_mime_type})')
            else:
                logger.info(f'Feed added: "{rss_feed.title}"')
        except Exception as e:
            session.rollback()
            logger.error(f"Feed add failed: {feed_url} — {e}")


def refresh_feed_favicon(feed_id):
    """Refresh the favicon for a specific feed."""
    with Session() as session:
        try:
            feed = session.query(RssFeed).filter_by(id=feed_id).first()
            if not feed:
                logger.warning(f"Favicon refresh skipped — feed id={feed_id} not found")
                return False

            favicon_data, favicon_mime_type = download_and_store_favicon(feed.link or feed.url)

            if favicon_data:
                feed.favicon_data = favicon_data
                feed.favicon_mime_type = favicon_mime_type
                session.commit()
                logger.info(f'Favicon refreshed: "{feed.title}" ({len(favicon_data)} bytes, {favicon_mime_type})')
                return True
            else:
                logger.warning(f'Favicon fetch failed: "{feed.title}"')
                return False

        except Exception as e:
            session.rollback()
            logger.error(f"Favicon refresh failed: feed id={feed_id} — {e}")
            return False


def refresh_all_feed_favicons():
    """Refresh favicons for all feeds."""
    with Session() as session:
        try:
            feeds = session.query(RssFeed).all()
            success_count = 0

            for feed in feeds:
                logger.debug(f'Refreshing favicon: "{feed.title}"')

                favicon_data, favicon_mime_type = download_and_store_favicon(feed.link or feed.url)

                if favicon_data:
                    feed.favicon_data = favicon_data
                    feed.favicon_mime_type = favicon_mime_type
                    success_count += 1
                    logger.info(f'Favicon updated: "{feed.title}" ({len(favicon_data)} bytes, {favicon_mime_type})')
                else:
                    logger.warning(f'Favicon fetch failed: "{feed.title}"')

            session.commit()
            logger.info(f"Favicon refresh completed: {success_count}/{len(feeds)} feeds updated")
            return success_count, len(feeds)

        except Exception as e:
            session.rollback()
            logger.error(f"Favicon refresh failed — {e}")
            return 0, 0


@db_retry(max_retries=3)
def remove_feed(feed_id):
    with Session() as session:
        feed = session.query(RssFeed).filter_by(id=feed_id).first()
        if feed:
            session.query(RssEntry).filter_by(feed_id=feed_id).delete()
            session.delete(feed)
            session.commit()
            logger.info(f'Feed removed: "{feed.title}"')
        else:
            logger.warning(f"Feed removal skipped — feed id={feed_id} not found")


def _attach_feed_stats(feeds, session):
    """Batch-load stats onto a list of feed objects using efficient grouped queries."""
    if not feeds:
        return

    feed_ids = [feed.id for feed in feeds]

    unread_counts = dict(
        session.query(RssEntry.feed_id, func.count(RssEntry.id))
        .filter(RssEntry.feed_id.in_(feed_ids), RssEntry.read == False)
        .group_by(RssEntry.feed_id)
        .all()
    )
    total_counts = dict(
        session.query(RssEntry.feed_id, func.count(RssEntry.id))
        .filter(RssEntry.feed_id.in_(feed_ids))
        .group_by(RssEntry.feed_id)
        .all()
    )
    read_counts = dict(
        session.query(RssEntry.feed_id, func.count(RssEntry.id))
        .filter(RssEntry.feed_id.in_(feed_ids), RssEntry.read is True)
        .group_by(RssEntry.feed_id)
        .all()
    )

    latest_entries_subquery = (
        session.query(RssEntry.feed_id, func.max(RssEntry.published).label('latest_published'))
        .filter(RssEntry.feed_id.in_(feed_ids))
        .group_by(RssEntry.feed_id)
        .subquery()
    )
    latest_entry_dates = dict(
        session.query(RssEntry.feed_id, RssEntry.published)
        .join(latest_entries_subquery,
              (RssEntry.feed_id == latest_entries_subquery.c.feed_id) &
              (RssEntry.published == latest_entries_subquery.c.latest_published))
        .all()
    )

    latest_unread_subquery = (
        session.query(RssEntry.feed_id, func.max(RssEntry.published).label('latest_unread_published'))
        .filter(RssEntry.feed_id.in_(feed_ids), RssEntry.read == False)
        .group_by(RssEntry.feed_id)
        .subquery()
    )
    latest_unread_dates = dict(
        session.query(RssEntry.feed_id, RssEntry.published)
        .join(latest_unread_subquery,
              (RssEntry.feed_id == latest_unread_subquery.c.feed_id) &
              (RssEntry.published == latest_unread_subquery.c.latest_unread_published))
        .filter(RssEntry.read == False)
        .all()
    )

    latest_titles_rows = (
        session.query(RssEntry.feed_id, RssEntry.title, RssEntry.published)
        .filter(RssEntry.feed_id.in_(feed_ids), RssEntry.title.isnot(None))
        .order_by(RssEntry.feed_id, desc(RssEntry.published))
        .all()
    )
    latest_titles = {}
    for fid, title, _published in latest_titles_rows:
        if fid not in latest_titles:
            latest_titles[fid] = []
        if len(latest_titles[fid]) < 3:
            latest_titles[fid].append(title)

    for feed in feeds:
        feed.unread_count = unread_counts.get(feed.id, 0)
        feed.last_new_article_found = latest_entry_dates.get(feed.id)
        feed.last_unread_entry_date = latest_unread_dates.get(feed.id)
        feed.latest_entry_titles = latest_titles.get(feed.id, [])
        total = total_counts.get(feed.id, 0)
        read = read_counts.get(feed.id, 0)
        feed.read_frequency = (read / total) if total > 0 else 0.0
        feed.frequency_data = get_feed_frequency_data(feed.id) if feed.id != "all" else []


def get_all_feeds(sort_by="title"):
    session = Session()
    try:
        feeds = session.query(RssFeed).order_by(desc(RssFeed.pinned)).all()

        if not feeds:
            all_feed = RssFeed(id="all", title="All Feeds")
            all_feed.unread_count = 0
            all_feed.last_unread_entry_date = None
            all_feed.latest_entry_titles = []
            all_feed.read_frequency = 0.0
            return [all_feed]

        _attach_feed_stats(feeds, session)

        if sort_by == "title":
            feeds.sort(key=lambda f: (not f.pinned, f.title or ""))
        elif sort_by == "last_updated":
            feeds.sort(key=lambda f: (not f.pinned, f.last_new_article_found or datetime.min), reverse=True)
        elif sort_by == "frequency_read":
            feeds.sort(key=lambda f: (not f.pinned, f.read_frequency), reverse=True)
        else:
            feeds.sort(key=lambda f: (not f.pinned, f.title or ""))

        all_feed = RssFeed(id="all", title="All Feeds")
        all_feed.unread_count = sum(feed.unread_count for feed in feeds)
        all_feed.last_unread_entry_date = max(
            (feed.last_unread_entry_date for feed in feeds if feed.last_unread_entry_date),
            default=None,
        )
        global_latest_query = (
            session.query(RssEntry.title)
            .filter(RssEntry.title.isnot(None))
            .order_by(desc(RssEntry.published))
            .limit(3)
            .all()
        )
        all_feed.latest_entry_titles = [title[0] for title in global_latest_query]
        all_feed.read_frequency = 0.0

        return [all_feed] + feeds

    except Exception as e:
        logger.error(f"Feed list query failed — {e}")
        try:
            with Session() as fallback_session:
                feeds = fallback_session.query(RssFeed).order_by(desc(RssFeed.pinned), RssFeed.title).all()
                for feed in feeds:
                    feed.unread_count = 0
                    feed.last_new_article_found = None
                    feed.last_unread_entry_date = None
                    feed.latest_entry_titles = []
                    feed.read_frequency = 0.0
                    feed.frequency_data = []

                all_feed = RssFeed(id="all", title="All Feeds")
                all_feed.unread_count = 0
                all_feed.last_unread_entry_date = None
                all_feed.latest_entry_titles = []
                all_feed.read_frequency = 0.0

                return [all_feed] + feeds
        except Exception as e2:
            logger.error(f"Feed list fallback query failed — {e2}")
            return []
    finally:
        session.close()


def get_feed_by_id(feed_id):
    with Session() as session:
        feed = session.query(RssFeed).filter_by(id=feed_id).first()
        if feed:
            _attach_feed_stats([feed], session)
            session.expunge(feed)
        return feed


@db_retry(max_retries=3)
def toggle_feed_pin(feed_id):
    """Toggle the pinned status of a feed."""
    with Session() as session:
        feed = session.query(RssFeed).filter_by(id=feed_id).first()
        if feed:
            feed.pinned = not feed.pinned
            session.commit()
            logger.info(f'Feed {"pinned" if feed.pinned else "unpinned"}: "{feed.title}"')
            return feed.pinned
        logger.warning(f"Feed pin toggle skipped — feed id={feed_id} not found")
        return None


def get_feed_sort_preference():
    """Get the current feed sorting preference from settings."""
    with Session() as session:
        setting = Settings.get_setting(session, "feed_sort_by")
        return setting if setting else "title"


@db_retry(max_retries=3)
def set_feed_sort_preference(sort_by):
    """Set the feed sorting preference in settings."""
    with Session() as session:
        Settings.set_setting(session, "feed_sort_by", sort_by)
        session.commit()
        logger.info(f"Feed sort preference updated: {sort_by}")
        return True


def get_feed_frequency_data(feed_id, weeks=12):
    """Get frequency data for sparkline graph showing posts per week over time."""
    from datetime import datetime, timedelta

    from sqlalchemy import func

    with Session() as session:
        try:
            # Calculate date range (last N weeks)
            end_date = datetime.now()
            start_date = end_date - timedelta(weeks=weeks)

            # Use SQL to group by week and count entries efficiently
            weekly_counts = session.query(
                func.strftime('%Y-%W', RssEntry.published).label('week'),
                func.count(RssEntry.id).label('count')
            ).filter(
                RssEntry.feed_id == feed_id,
                RssEntry.published >= start_date,
                RssEntry.published <= end_date
            ).group_by(func.strftime('%Y-%W', RssEntry.published)).all()

            # Convert to dict for easy lookup
            week_counts = dict(weekly_counts)

            # Generate frequency data for each week
            frequency_data = []
            current_week_start = start_date

            for week_num in range(weeks):
                week_key = current_week_start.strftime('%Y-%W')
                count = week_counts.get(week_key, 0)
                frequency_data.append(count)
                current_week_start += timedelta(days=7)

            return frequency_data

        except Exception as e:
            logger.error(f"Frequency data query failed: feed id={feed_id} — {e}")
            return [0] * weeks


def parse_tags_string(tags_string):
    """Parse a comma-separated string of tags into a list."""
    if not tags_string:
        return []
    return [tag.strip() for tag in tags_string.split(',') if tag.strip()]


def format_tags_list(tags_list):
    """Format a list of tags into a comma-separated string."""
    if not tags_list:
        return None
    return ', '.join(tag.strip() for tag in tags_list if tag.strip())


def get_all_tags():
    """Get all unique tags from all feeds."""
    with Session() as session:
        feeds = session.query(RssFeed).filter(RssFeed.tags.isnot(None)).all()
        all_tags = set()
        for feed in feeds:
            if feed.tags:
                tags = parse_tags_string(feed.tags)
                all_tags.update(tags)
        return sorted(all_tags)


def get_feeds_by_tag(tag):
    """Get all feeds that have a specific tag."""
    with Session() as session:
        feeds = session.query(RssFeed).filter(RssFeed.tags.like(f'%{tag}%')).all()
        # Filter to ensure exact tag match (not substring)
        matching_feeds = [
            feed for feed in feeds
            if feed.tags and tag in parse_tags_string(feed.tags)
        ]
        _attach_feed_stats(matching_feeds, session)
        for feed in matching_feeds:
            session.expunge(feed)
        return matching_feeds


@db_retry(max_retries=3)
def update_feed_tags(feed_id, tags_string):
    """Update the tags for a specific feed."""
    with Session() as session:
        feed = session.query(RssFeed).filter_by(id=feed_id).first()
        if feed:
            feed.tags = format_tags_list(parse_tags_string(tags_string)) if tags_string else None
            session.commit()
            logger.info(f'Tags updated: "{feed.title}" → {feed.tags}')
            return True
        logger.warning(f"Tag update skipped — feed id={feed_id} not found")
        return False
