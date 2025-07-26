import atexit
import os
import time
from datetime import datetime

import requests
from flask import (
    Flask,
    Response,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_executor import Executor
from models import RssFeed, Session
from services import *
from services import add_feed as add_feed_function
from services.feed_service import (
    get_all_tags,
    get_feeds_by_tag,
    refresh_all_feed_favicons,
    update_feed_tags,
)
from services.scheduler_service import (
    get_scheduler_status,
    reschedule_feeds,
    schedule_jobs_on_first_request,
    start_scheduler,
    stop_scheduler,
)

app = Flask(__name__)
executor = Executor(app)
app.config["EXECUTOR_TYPE"] = "thread"

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/rss_database.db")

_startup_time = time.time()
_first_request_handled = False

scheduler = None
try:
    scheduler = start_scheduler(lazy=True)
    print("✅ Lazy background feed scheduler started - full initialization deferred until first request")
except Exception as e:
    print(f"⚠️  Failed to start lazy background scheduler: {e}")
    print("   Manual feed refresh will still work")


def cleanup_scheduler():
    if scheduler:
        try:
            stop_scheduler()
            print("✅ Background scheduler stopped gracefully")
        except Exception as e:
            print(f"⚠️  Error stopping scheduler: {e}")

atexit.register(cleanup_scheduler)


def monitor_performance(route_name):
    """Decorator to monitor route performance."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                end_time = time.perf_counter()
                duration = (end_time - start_time) * 1000
                print(f"🚀 Route '{route_name}' completed in {duration:.1f}ms")
                return result
            except Exception as e:
                end_time = time.perf_counter()
                duration = (end_time - start_time) * 1000
                print(f"❌ Route '{route_name}' failed after {duration:.1f}ms: {e}")
                raise
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator


def handle_first_request():
    """Initialize expensive operations on first request."""
    global _first_request_handled
    if not _first_request_handled:
        startup_duration = (time.time() - _startup_time) * 1000
        print(f"🎯 First request received {startup_duration:.1f}ms after startup")


        try:
            schedule_jobs_on_first_request()
            print("✅ Lazy scheduler fully initialized on first request")
        except Exception as e:
            print(f"⚠️  Error during lazy scheduler initialization: {e}")

        _first_request_handled = True


@app.template_filter()
def entry_timedetla(input_datetime):
    from services.content_service import entry_timedetla as service_timedetla
    return service_timedetla(input_datetime)


@app.template_filter()
def short_time_ago(input_datetime):
    from services.content_service import short_time_ago as service_short_time_ago
    return service_short_time_ago(input_datetime)


@app.template_filter()
def get_feed_timestamp_class(feed):
    from services.content_service import (
        get_feed_timestamp_class as service_get_feed_timestamp_class,
    )
    unread_count = getattr(feed, 'unread_count', 0)
    last_unread_date = getattr(feed, 'last_unread_entry_date', None)
    return service_get_feed_timestamp_class(unread_count, last_unread_date)


@app.template_filter()
def get_feed_timestamp_color(feed):
    from services.content_service import (
        get_feed_timestamp_color as service_get_feed_timestamp_color,
    )
    unread_count = getattr(feed, 'unread_count', 0)
    last_unread_date = getattr(feed, 'last_unread_entry_date', None)
    return service_get_feed_timestamp_color(unread_count, last_unread_date)





@app.route("/")
@monitor_performance("index")
def index():
    handle_first_request()

    template = "index.html"

    sort_by = get_feed_sort_preference()
    all_tags = get_all_tags()
    feeds = get_all_feeds(sort_by)

    return render_template(template, theme=get_theme("default"), feeds=feeds, current_sort=sort_by, all_tags=all_tags)


@app.route("/entries/<feed_id>")
@monitor_performance("entries")
def entries(feed_id):
    page = int(request.args.get("page", default=1))
    entries_per_page = 20
    entries = get_feed_entries_by_feed_id(feed_id, page, entries_per_page)

    if feed_id == "all":
        feed = {"title": "All Feeds", "id": "all", "favicon_path": None}
    elif feed_id.startswith("tag:"):
        # Redirect to the tag all entries route
        tag_name = feed_id[4:]  # Remove "tag:" prefix
        return redirect(url_for('tag_all_entries', tag_name=tag_name))
    else:
        feed = get_feed_by_id(feed_id)

    # Check if this is an HTMX request for infinite scroll
    if request.headers.get('HX-Request'):
        # Return just the entry cards for HTMX requests
        if entries:
            # Check if there might be more entries by seeing if we got a full page
            has_more = len(entries) == entries_per_page
            next_page = page + 1 if has_more else None
            return render_template('entry-cards-partial.html',
                                 entries=entries,
                                 feed=feed,
                                 next_page=next_page)
        else:
            # No more entries - return empty content
            return ""

    # Regular page load - return full page
    has_more = len(entries) == entries_per_page
    next_page = page + 1 if has_more else None
    all_tags = get_all_tags()
    return render_template("entries.html", entries=entries, feed=feed,
                         theme=get_theme("default"), next_page=next_page, all_tags=all_tags)

@app.route("/entry/<entry_id>")
@monitor_performance("entry")
def entry(entry_id):
    template = "entry.html"
    entry = get_feed_entry_by_id(entry_id)
    if not entry:
        return "Entry not found", 404
    feed = get_feed_by_id(entry.feed_id)
    read_status = True
    mark_entry_as_read(entry_id, read_status)
    all_tags = get_all_tags()
    return render_template(template, entry=entry, feed=feed, theme=get_theme("default"), all_tags=all_tags)

@app.route("/refresh/<feed_id>", methods=["POST"])
def refresh(feed_id):
    referrer = request.referrer if request.referrer else "/"

    def get_redirect_url():
        if 'entry/' in referrer:
            try:
                entry_id = referrer.split('entry/')[-1].split('?')[0].split('#')[0]
                return redirect(url_for('entry', entry_id=entry_id))
            except Exception:
                return redirect(url_for('entries', feed_id=feed_id))
        elif feed_id == "all":
            return redirect(url_for('index'))
        else:
            return redirect(url_for('entries', feed_id=feed_id))

    is_htmx = request.headers.get('HX-Request')

    try:
        if feed_id == "all":
            if "refresh_all" in executor.futures._futures:
                print("Task refresh_all is already running")
                if is_htmx:
                    response = make_response("")
                    response.headers['HX-Redirect'] = url_for('index')
                    return response
                return get_redirect_url()

            executor.submit_stored("refresh_all", add_rss_entries_for_all_feeds)
            print("Started task refresh_all")
            if is_htmx:
                response = make_response("")
                response.headers['HX-Redirect'] = url_for('index')
                return response
            return redirect(url_for('index'))
        else:
            try:
                int(feed_id)
            except ValueError:
                print(f"Invalid feed_id format: {feed_id}")
                if is_htmx:
                    response = make_response("")
                    if feed_id == "all":
                        response.headers['HX-Redirect'] = url_for('index')
                    else:
                        response.headers['HX-Redirect'] = url_for('entries', feed_id=feed_id)
                    return response
                return get_redirect_url()

            if f"refresh_{feed_id}" in executor.futures._futures:
                print(f"Task refresh_{feed_id} is already running")
                if is_htmx:
                    response = make_response("")
                    response.headers['HX-Redirect'] = url_for('entries', feed_id=feed_id)
                    return response
                return get_redirect_url()

            try:
                executor.submit_stored(f"refresh_{feed_id}", add_rss_entries_for_feed, feed_id)
                print(f"Started task refresh_{feed_id}")
            except Exception as e:
                print(f"Error starting refresh task for feed {feed_id}: {e!s}")

            if is_htmx:
                response = make_response("")
                response.headers['HX-Redirect'] = url_for('entries', feed_id=feed_id)
                return response
            return get_redirect_url()

    except ValueError as e:
        print(f"ValueError in refresh route: {e!s}")
        if is_htmx:
            response = make_response("")
            if feed_id == "all":
                response.headers['HX-Redirect'] = url_for('index')
            else:
                response.headers['HX-Redirect'] = url_for('entries', feed_id=feed_id)
            return response
        return get_redirect_url()
    except Exception as e:
        print(f"Unexpected error in refresh route: {e!s}")
        if is_htmx:
            response = make_response("")
            if feed_id == "all":
                response.headers['HX-Redirect'] = url_for('index')
            else:
                response.headers['HX-Redirect'] = url_for('entries', feed_id=feed_id)
            return response
        return get_redirect_url()

@app.route("/settings")
@monitor_performance("settings")
def settings():
    template = "settings.html"
    all_tags = get_all_tags()
    return render_template(template, feeds=get_all_feeds(), theme=get_theme("default"), all_tags=all_tags)

@app.route("/upload_opml", methods=["POST"])
@monitor_performance("upload_opml")
def upload_opml():
    if 'opml_file' not in request.files:
        return "<div class='feedback-message error'>No file selected</div>"

    uploaded_file = request.files["opml_file"]

    if not uploaded_file.filename or uploaded_file.filename == '':
        return "<div class='feedback-message error'>No file selected</div>"

    if not uploaded_file.filename.endswith('.opml'):
        return "<div class='feedback-message error'>Please select an OPML file</div>"

    try:
        executor.submit_stored("opml_import", add_feeds_from_opml, uploaded_file)
        return "<div class='feedback-message success'>Processing OPML file... <em>Please refresh the page in a few moments to see the new feeds.</em></div>"
    except Exception as e:
        return f"<div class='feedback-message error'>Error processing OPML file: {e!s}</div>"


@app.route("/add_feed", methods=["POST"])
@monitor_performance("add_feed")
def add_feed_route():
    feed_url = request.form.get("feed_url", "").strip()

    if not feed_url:
        return "<div class='feedback-message error'>Please enter a feed URL</div>"

    if not (feed_url.startswith('http://') or feed_url.startswith('https://')):
        feed_url = 'https://' + feed_url

    try:
        session = Session()
        existing_feed = session.query(RssFeed).filter_by(url=feed_url).first()
        session.close()

        if existing_feed:
            return f"<div class='feedback-message warning'>Feed already exists: {existing_feed.title}</div>"

        executor.submit_stored(f"feed_add_{feed_url}", add_feed_function, feed_url)
        return f"<div class='feedback-message success'>Adding feed: {feed_url}... <em>Please refresh the page in a few moments to see the new feed.</em></div>"

    except Exception as e:
        return f"<div class='feedback-message error'>Error adding feed: {e!s}</div>"


@app.route("/delete_feed/<feed_id>")
def delete_feed(feed_id):
    remove_feed(feed_id)
    return "", 200


@app.route("/set_theme", methods=["POST"])
@monitor_performance("set_theme")
def set_theme():
    theme_name = request.form["theme"]
    theme = get_theme(theme_name)
    template = "theme.html"
    return render_template(template, theme=theme)


@app.route("/set_default_theme", methods=["POST"])
@monitor_performance("set_default_theme")
def route_set_default_theme():
    theme_name = request.form["theme"]
    success = set_default_theme(theme_name)
    if success:
        theme = get_theme(theme_name)
    else:
        theme = get_theme("default")
    template = "theme.html"
    return render_template(template, theme=theme)


@app.route("/set_feed_sort", methods=["POST"])
@monitor_performance("set_feed_sort")
def set_feed_sort():
    """Set the feed sorting preference and return updated feed list."""
    sort_by = request.form.get("sort_by", "title")
    set_feed_sort_preference(sort_by)
    feeds = get_all_feeds(sort_by)
    return render_template("feed-list-partial.html", feeds=feeds, current_sort=sort_by)


@app.route("/toggle_feed_pin/<feed_id>", methods=["POST"])
@monitor_performance("toggle_feed_pin")
def toggle_feed_pin_route(feed_id):
    """Toggle the pinned status of a feed."""
    pinned = toggle_feed_pin(feed_id)
    if pinned is not None:
        sort_by = get_feed_sort_preference()
        feeds = get_all_feeds(sort_by)
        return render_template("feed-list-partial.html", feeds=feeds, current_sort=sort_by)
    else:
        return "Error toggling pin status", 500


@app.route("/mark_all_read/<feed_id>", methods=["POST"])
@monitor_performance("mark_all_read")
def mark_all_read_route(feed_id):
    """Mark all entries in a feed as read."""
    try:
        if feed_id != "all":
            feed_id = int(feed_id)

        mark_feed_entries_as_read(feed_id, True)

        if feed_id == "all":
            feed_name = "All Feeds"
        else:
            feed = get_feed_by_id(feed_id)
            feed_name = feed.title if feed else "Unknown Feed"

        return f'<span style="color: #28a745;">✓ All entries in "{feed_name}" marked as read</span>'
    except Exception as e:
        print(f"Error marking entries as read: {e}")
        return '<span style="color: #dc3545;">✗ Error marking entries as read</span>', 500


@app.route("/toggle_feed_pin_entries/<feed_id>", methods=["POST"])
@monitor_performance("toggle_feed_pin_entries")
def toggle_feed_pin_entries_route(feed_id):
    """Toggle the pinned status of a feed from entries page."""
    try:
        pinned = toggle_feed_pin(feed_id)
        if pinned is not None:
            feed = get_feed_by_id(feed_id)
            if feed:
                return render_template("pin-status-partial.html", feed=feed)
            else:
                return "Feed not found", 404
        else:
            return "Error toggling pin status", 500
    except Exception as e:
        print(f"Error toggling pin status: {e}")
        return "Error toggling pin status", 500


@app.route("/fetch_full_article/<entry_id>", methods=["POST"])
@monitor_performance("fetch_full_article")
def fetch_full_article_route(entry_id):
    """Fetch the full article content from the original URL."""
    try:
        entry = get_feed_entry_by_id(entry_id)
        if not entry:
            return '<div class="fetch-error-message"><span style="color: #dc3545;">✗ Entry not found</span></div>', 404

        if not entry.link:
            return '<div class="fetch-error-message"><span style="color: #dc3545;">✗ No link available for this entry</span></div>', 400

        article = get_remote_content(entry.link, entry_id)

        if article:
            updated_entry = get_feed_entry_by_id(entry_id)
            return render_template("entry-content-partial.html", entry=updated_entry)
        else:
            return f'<div class="fetch-error-message"><span style="color: #dc3545;">✗ Failed to fetch content from {entry.link}</span><br><small>The website may be blocking requests or the content may not be accessible.</small></div>', 500

    except requests.exceptions.Timeout:
        return '<div class="fetch-error-message"><span style="color: #dc3545;">✗ Request timed out</span><br><small>The website took too long to respond.</small></div>', 500
    except requests.exceptions.ConnectionError:
        return '<div class="fetch-error-message"><span style="color: #dc3545;">✗ Connection failed</span><br><small>Could not connect to the website.</small></div>', 500
    except Exception as e:
        print(f"Error fetching full article: {e}")
        return '<div class="fetch-error-message"><span style="color: #dc3545;">✗ Error fetching article content</span><br><small>An unexpected error occurred.</small></div>', 500


@app.route("/favicon/<int:feed_id>")
def serve_favicon(feed_id):
    """Serve favicon from database."""
    session = Session()
    try:
        feed = session.query(RssFeed).filter_by(id=feed_id).first()
        if feed and feed.favicon_data:
            response = Response(
                feed.favicon_data,
                mimetype=feed.favicon_mime_type or 'image/x-icon'
            )
            response.headers['Cache-Control'] = 'public, max-age=3600'
            return response
        else:
            return '', 404
    finally:
        session.close()


@app.route("/refresh_favicons", methods=["POST"])
@monitor_performance("refresh_favicons")
def refresh_favicons():
    """Refresh all feed favicons."""
    try:
        future = executor.submit(refresh_all_feed_favicons)
        task_id = f"refresh_favicons_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        executor.futures._futures[task_id] = future

        return f"""
        <div class="refresh_status success">
            <p><strong>✓ Favicon refresh started!</strong></p>
            <p>Task ID: {task_id}</p>
            <p>This may take a few moments to complete...</p>
            <div id="status_check" hx-get="/refresh_status/{task_id}" hx-trigger="every 2s" hx-swap="innerHTML"></div>
        </div>
        """
    except Exception as e:
        return f"""
        <div class="refresh_status error">
            <p><strong>✗ Failed to start favicon refresh</strong></p>
            <p>Error: {e!s}</p>
        </div>
        """, 500


@app.route("/refresh_status/<task_id>")
def refresh_status(task_id):
    """Check the status of a favicon refresh task."""
    try:
        if task_id not in executor.futures._futures:
            return '<p>Task not found</p>'

        future = executor.futures._futures[task_id]

        if future.done():
            try:
                result = future.result()
                if isinstance(result, tuple) and len(result) == 2:
                    success_count, total_count = result
                    return f"""
                    <div class="refresh_status success">
                        <p><strong>✓ Refresh completed!</strong></p>
                        <p>Successfully updated {success_count} out of {total_count} feeds</p>
                    </div>
                    """
                else:
                    return f"""
                    <div class="refresh_status success">
                        <p><strong>✓ Refresh completed!</strong></p>
                        <p>Result: {result}</p>
                    </div>
                    """
            except Exception as e:
                return f"""
                <div class="refresh_status error">
                    <p><strong>✗ Refresh failed</strong></p>
                    <p>Error: {e!s}</p>
                </div>
                """
        else:
            return '<p>⏳ Refresh in progress...</p>'

    except Exception as e:
        return f'<p>Error checking status: {e!s}</p>'

# Helper function to clean up tasks
def cleanup_tasks():
    """Clean up completed tasks from the executor after they've been displayed."""
    try:
        current_time = datetime.now()
        for key in list(executor.futures._futures.keys()):
            try:
                future = executor.futures._futures[key]
                if future and future.done():
                    if not hasattr(future, '_completion_time'):
                        future._completion_time = current_time
                        print(f"Task {key} completed, marking completion time")
                    else:
                        time_since_completion = (current_time - future._completion_time).total_seconds()
                        if time_since_completion > 30:
                            executor.futures._futures.pop(key, None)
                            print(f"Cleaned up completed task: {key} (completed {time_since_completion:.1f}s ago)")
            except Exception as e:
                print(f"Error cleaning up task {key}: {e}")
    except Exception as e:
        print(f"Error in task cleanup: {e}")

# Register a cleanup handler for completed tasks
@app.after_request
def cleanup_completed_tasks(response):
    """Global after_request handler to clean up completed tasks."""
    try:
        if hasattr(app, 'cleanup_counter'):
            app.cleanup_counter += 1
            if app.cleanup_counter % 50 != 0:
                return response
        else:
            app.cleanup_counter = 1

        cleanup_tasks()
    except Exception as e:
        print(f"Error in task cleanup: {e}")
    return response

@app.route("/task_status", methods=["GET"])
def task_status():
    """Returns the status of all running background tasks."""
    tasks = {}

    all_feeds_key = "refresh_all"
    if all_feeds_key in executor.futures._futures:
        future = executor.futures._futures[all_feeds_key]
        tasks[all_feeds_key] = {
            "running": not future.done(),
            "completed": future.done(),
            "success": future.done() and not future.exception(),
            "error": str(future.exception()) if future.done() and future.exception() else None,
            "feed_id": "all",
            "start_time": datetime.now().isoformat(),
            "task_type": "refresh_all"
        }

    for key in list(executor.futures._futures.keys()):
        if key.startswith("refresh_") and key != "refresh_all":
            future = executor.futures._futures[key]
            feed_id = key.split("refresh_")[1]

            feed_title = None
            try:
                session = Session()
                feed = session.query(RssFeed).filter_by(id=feed_id).first()
                if feed:
                    feed_title = feed.title
                session.close()
            except Exception:
                pass

            tasks[key] = {
                "feed_id": feed_id,
                "feed_title": feed_title,
                "running": not future.done(),
                "completed": future.done(),
                "success": future.done() and not future.exception(),
                "error": str(future.exception()) if future.done() and future.exception() else None,
                "start_time": datetime.now().isoformat(),
                "task_type": "refresh_feed"
            }

    return jsonify({
        "tasks": tasks,
        "timestamp": datetime.now().isoformat(),
        "active_task_count": len([t for t in tasks.values() if t["running"]]),
        "completed_task_count": len([t for t in tasks.values() if t["completed"]])
    })


@app.route("/tag/<tag_name>")
def tag_entries(tag_name):
    """Show feed list for all feeds with a specific tag."""
    feeds_with_tag = get_feeds_by_tag(tag_name)

    most_recent_unread = None
    all_latest_titles = []
    for feed in feeds_with_tag:
        if hasattr(feed, 'last_unread_entry_date') and feed.last_unread_entry_date:
            if most_recent_unread is None or feed.last_unread_entry_date > most_recent_unread:
                most_recent_unread = feed.last_unread_entry_date
        if hasattr(feed, 'latest_entry_titles') and feed.latest_entry_titles:
            all_latest_titles.extend(feed.latest_entry_titles)

    unique_titles = []
    for title in all_latest_titles:
        if title not in unique_titles:
            unique_titles.append(title)
        if len(unique_titles) >= 3:
            break

    tag_feed = {
        "title": tag_name,
        "id": f"tag:{tag_name}",
        "favicon_path": None,
        "unread_count": sum(feed.unread_count for feed in feeds_with_tag),
        "last_unread_entry_date": most_recent_unread,
        "latest_entry_titles": unique_titles
    }

    feeds = [tag_feed] + feeds_with_tag

    all_tags = get_all_tags()
    return render_template("index.html", feeds=feeds, theme=get_theme("default"),
                         all_tags=all_tags, current_sort="title")


@app.route("/entries/tag:<tag_name>")
def tag_all_entries(tag_name):
    """Show all entries for feeds with a specific tag."""
    page = int(request.args.get("page", default=1))
    entries_per_page = 20

    feeds_with_tag = get_feeds_by_tag(tag_name)

    if not feeds_with_tag:
        entries = []
    else:
        feed_ids = [feed.id for feed in feeds_with_tag]
        entries = get_feed_entries_by_feed_id("all", page, entries_per_page, feed_ids=feed_ids)

    feed = {"title": tag_name, "id": f"tag:{tag_name}", "favicon_path": None}

    if request.headers.get('HX-Request'):
        if entries:
            has_more = len(entries) == entries_per_page
            next_page = page + 1 if has_more else None
            return render_template('entry-cards-partial.html',
                                 entries=entries,
                                 feed=feed,
                                 next_page=next_page)
        else:
            return ""

    has_more = len(entries) == entries_per_page
    next_page = page + 1 if has_more else None
    all_tags = get_all_tags()
    return render_template("entries.html", entries=entries, feed=feed,
                         theme=get_theme("default"), next_page=next_page, all_tags=all_tags)


@app.route("/update_feed_tags/<feed_id>", methods=["POST"])
@monitor_performance("update_feed_tags")
def update_feed_tags_route(feed_id):
    """Update the tags for a specific feed."""
    tags_string = request.form.get("tags", "").strip()

    success = update_feed_tags(feed_id, tags_string)

    if success:
        sort_by = get_feed_sort_preference()
        feeds = get_all_feeds(sort_by)
        return render_template("settings-feed-table-partial.html", feeds=feeds)
    else:
        return "Error updating tags", 500


@app.route("/scheduler_status")
@monitor_performance("scheduler_status")
def scheduler_status():
    """Get the status of the background scheduler and its jobs."""
    try:
        status = get_scheduler_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500


@app.route("/scheduler_reschedule", methods=["POST"])
@monitor_performance("scheduler_reschedule")
def scheduler_reschedule():
    """Reschedule all feed refresh jobs (useful after adding/removing feeds)."""
    try:
        reschedule_feeds()
        return jsonify({"message": "Feed refresh jobs rescheduled successfully", "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500


@app.route("/performance_stats")
@monitor_performance("performance_stats")
def performance_stats():
    """Get performance statistics for the application."""
    try:
        startup_duration = (time.time() - _startup_time) * 1000

        scheduler_status = get_scheduler_status()

        session = Session()
        try:
            feed_count = session.query(RssFeed).count()
            entry_count = session.query(RssEntry).count()
            unread_count = session.query(RssEntry).filter_by(read=False).count()
        finally:
            session.close()

        stats = {
            'startup_time_ms': startup_duration,
            'first_request_handled': _first_request_handled,
            'database_stats': {
                'total_feeds': feed_count,
                'total_entries': entry_count,
                'total_unread': unread_count
            },
            'scheduler_stats': scheduler_status,
            'performance_optimizations': {
                'lazy_scheduler': True,
                'optimized_feed_queries': True,
                'batch_database_operations': True,
                'database_indexes': True
            }
        }

        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500




if __name__ == "__main__":
    if "sqlite:///" in DATABASE_URL:
        db_path = DATABASE_URL.split("///")[1]
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes", "on")
    app.run(debug=debug, host="0.0.0.0", port=port)
