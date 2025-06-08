import feedparser
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from models import RssFeed, RssEntry, Session
from sqlalchemy import desc
from dateutil import parser
from datetime import datetime, timedelta
from readabilipy import simple_json_from_html_string
import concurrent.futures
from functools import partial


def add_rss_entries(feed_id):
    """
    Fetches and adds RSS entries for a specific feed to the database.
    Attempts to process feeds even if parsing exceptions occur.

    Args:
        feed_id: The ID of the RSS feed to process

    Returns:
        tuple: (success_flag, message)
    """
    session = Session()
    try:
        feed = session.query(RssFeed).filter_by(id=feed_id).first()
        
        if not feed:
            session.close()
            return False, f"Feed with ID {feed_id} not found"

        print(f"Processing feed: {feed.title}")
        
        try:
            parsed_feed = feedparser.parse(feed.url)
            
            if hasattr(parsed_feed, 'status') and parsed_feed.status >= 400:
                print(f"HTTP error {parsed_feed.status} for feed {feed.title}")
                session.close()
                return False, f"HTTP error {parsed_feed.status}"
                
        except Exception as parse_error:
            print(f"Parse error for feed {feed.title}: {parse_error}")
            session.close()
            return False, f"Parse error: {parse_error}"

        entries_added = 0
        
        for entry in parsed_feed.entries:
            try:
                # Check if entry already exists
                existing_entry = session.query(RssEntry).filter_by(
                    feed_id=feed_id, link=entry.link
                ).first()
                
                if existing_entry:
                    continue

                # Parse published date
                published_date = None
                if hasattr(entry, 'published'):
                    try:
                        published_date = parser.parse(entry.published)
                    except Exception as date_error:
                        print(f"Date parse error for entry {entry.title}: {date_error}")
                        published_date = datetime.now()
                else:
                    published_date = datetime.now()

                # Get description/summary
                description = ""
                if hasattr(entry, 'summary'):
                    description = entry.summary
                elif hasattr(entry, 'description'):
                    description = entry.description

                # Get author
                author = ""
                if hasattr(entry, 'author'):
                    author = entry.author

                # Create new entry
                rss_entry = RssEntry(
                    feed_id=feed_id,
                    title=entry.title,
                    link=entry.link,
                    description=description,
                    published=published_date,
                    author=author,
                )
                
                session.add(rss_entry)
                entries_added += 1
                
            except Exception as entry_error:
                print(f"Error processing entry {getattr(entry, 'title', 'Unknown')}: {entry_error}")
                continue

        # Note: last_new_article_found is now calculated dynamically based on latest entry published date
        
        session.commit()
        print(f"Added {entries_added} new entries for feed: {feed.title}")
        
        session.close()
        return True, f"Added {entries_added} entries"
        
    except Exception as e:
        session.rollback()
        session.close()
        print(f"Error processing feed {feed_id}: {e}")
        return False, f"Error: {e}"


def add_rss_entries_for_feed(feed_id):
    """
    Fetches and adds RSS entries for a specific feed to the database.
    
    Args:
        feed_id: The ID of the RSS feed to process

    Returns:
        tuple: (success_flag, message)
    """
    print(f"Refreshing feed with ID: {feed_id}")
    return add_rss_entries(feed_id)


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
    feeds = session.query(RssFeed).all()
    feed_ids = [feed.id for feed in feeds]
    session.close()
    
    if not feed_ids:
        print("No feeds found to process")
        return []

    print(f"Processing {len(feed_ids)} feeds with {max_workers} workers")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create partial function with the add_rss_entries function
        process_func = partial(add_rss_entries)
        
        # Submit all tasks
        future_to_feed_id = {
            executor.submit(process_func, feed_id): feed_id 
            for feed_id in feed_ids
        }
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_feed_id):
            feed_id = future_to_feed_id[future]
            try:
                success, message = future.result()
                results.append({
                    'feed_id': feed_id,
                    'success': success,
                    'message': message
                })
                print(f"Feed {feed_id}: {message}")
            except Exception as exc:
                print(f"Feed {feed_id} generated an exception: {exc}")
                results.append({
                    'feed_id': feed_id,
                    'success': False,
                    'message': f"Exception: {exc}"
                })
    
    successful_feeds = sum(1 for result in results if result['success'])
    print(f"Completed processing {len(feed_ids)} feeds. {successful_feeds} successful.")
    
    return results


def get_all_feed_entries():
    session = Session()
    entries = session.query(RssEntry).order_by(RssEntry.published.desc()).all()
    session.close()
    return entries


def get_feed_entry_by_id(entry_id):
    session = Session()

    entry = session.query(RssEntry).filter_by(id=entry_id).first()
    if entry:
        # Ensure attributes are loaded before session close
        _ = entry.id, entry.title, entry.read
        session.expunge(entry)
    session.close()
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

        session.commit()
        session.close()
    except Exception as e:
        session.rollback()
        session.close()
        print(f"Error updating entry: {e}")


def get_remote_content(url, entry_id):
    try:
        response = requests.get(url)
        response.raise_for_status()
        article = simple_json_from_html_string(response.text, use_readability=True)
        entry = get_feed_entry_by_id(entry_id)

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
        print(f"RSS Entry with ID {entry_id} not found.")


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

    print(
        f"All RSS entries for feed ID {feed_id} marked as {'read' if read_status else 'unread'}."
    )