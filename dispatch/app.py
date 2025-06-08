import os
import json
from flask import Flask, request, render_template, redirect, url_for, jsonify, make_response, Response
from flask_executor import Executor
from services import * # Import all service functions
from services import add_feed as add_feed_function  # Import with alias to avoid name conflict
from services.feed_service import refresh_all_feed_favicons  # Import refresh function
from model import Session, RssFeed  # Import Session and RssFeed for test compatibility
from datetime import datetime # Make sure datetime is imported

app = Flask(__name__)
executor = Executor(app)
app.config["EXECUTOR_TYPE"] = "thread"

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/rss_database.db")

# Template filter for time delta - uses the service function for consistency
@app.template_filter()
def entry_timedetla(input_datetime):
    from services.content_service import entry_timedetla as service_timedetla
    return service_timedetla(input_datetime)


# Renamed from newindex, route changed from /new to /
@app.route("/")
def index():
    template = "index.html" # Renamed from new-index.html
    return render_template(template, theme=get_theme("default"), feeds=get_all_feeds())

# Renamed from newentries, route changed from /newentries/<feed_id>
@app.route("/entries/<feed_id>")
def entries(feed_id):
    page = int(request.args.get("page", default=1))
    entries_per_page = 20
    entries = get_feed_entries_by_feed_id(feed_id, page, entries_per_page)

    if feed_id == "all":
        feed = {"title": "All Feeds", "id": "all", "favicon_path": None}
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
    return render_template("entries.html", entries=entries, feed=feed,
                         theme=get_theme("default"), next_page=next_page)

# Renamed from newentry, route changed from /newentry/<entry_id>
@app.route("/entry/<entry_id>")
def entry(entry_id):
    template = "entry.html" # Renamed from new-entry.html
    entry = get_feed_entry_by_id(entry_id)
    if not entry:
        return "Entry not found", 404
    feed = get_feed_by_id(entry.feed_id)
    read_status = True
    mark_entry_as_read(entry_id, read_status) # Mark as read when viewed
    return render_template(template, entry=entry, feed=feed, theme=get_theme("default"))

# Renamed from newrefresh, route changed from /newrefresh/<feed_id>
@app.route("/refresh/<feed_id>", methods=["POST"])
def refresh(feed_id):
    # Get the referrer URL to determine where to redirect back to
    referrer = request.referrer if request.referrer else "/"

    # Store the timestamp when the refresh was requested
    refresh_timestamp = datetime.now().isoformat()

    # Helper function to determine where to redirect based on referrer
    def get_redirect_url():
        if 'entry/' in referrer:
            try:
                # Extract entry_id from referrer URL
                entry_id = referrer.split('entry/')[-1].split('?')[0].split('#')[0]
                return redirect(url_for('entry', entry_id=entry_id))
            except Exception:
                # If something goes wrong with entry parsing, fall back to feed page
                return redirect(url_for('entries', feed_id=feed_id))
        elif feed_id == "all":
            return redirect(url_for('index'))
        else:
            return redirect(url_for('entries', feed_id=feed_id))

    # Check if this is an HTMX request
    is_htmx = request.headers.get('HX-Request')

    try:
        if feed_id == "all":
            # Check if task is already running
            if f"refresh_all" in executor.futures._futures:
                print(f"Task refresh_all is already running")
                if is_htmx:
                    # For HTMX, return a response that triggers a client-side redirect
                    response = make_response("")
                    response.headers['HX-Redirect'] = url_for('index')
                    return response
                return get_redirect_url()

            executor.submit_stored("refresh_all", add_rss_entries_for_all_feeds)
            print(f"Started task refresh_all")
            if is_htmx:
                # For HTMX, return a response that triggers a client-side redirect
                response = make_response("")
                response.headers['HX-Redirect'] = url_for('index')
                return response
            return redirect(url_for('index'))
        else:
            # Validate feed_id exists
            try:
                feed_id_int = int(feed_id)  # Make sure it's a valid integer if numeric
            except ValueError:
                print(f"Invalid feed_id format: {feed_id}")
                if is_htmx:
                    # For HTMX, return a response that triggers a client-side redirect
                    response = make_response("")
                    if feed_id == "all":
                        response.headers['HX-Redirect'] = url_for('index')
                    else:
                        response.headers['HX-Redirect'] = url_for('entries', feed_id=feed_id)
                    return response
                return get_redirect_url()

            # Check if task is already running
            if f"refresh_{feed_id}" in executor.futures._futures:
                print(f"Task refresh_{feed_id} is already running")
                if is_htmx:
                    # For HTMX, return a response that triggers a client-side redirect
                    response = make_response("")
                    response.headers['HX-Redirect'] = url_for('entries', feed_id=feed_id)
                    return response
                return get_redirect_url()

            # Ensure feed_id is passed correctly if the function expects it
            try:
                executor.submit_stored(f"refresh_{feed_id}", add_rss_entries_for_feed, feed_id)
                print(f"Started task refresh_{feed_id}")
            except Exception as e:
                print(f"Error starting refresh task for feed {feed_id}: {str(e)}")

            # Handle response based on request type
            if is_htmx:
                # For HTMX, return a response that triggers a client-side redirect
                response = make_response("")
                response.headers['HX-Redirect'] = url_for('entries', feed_id=feed_id)
                return response
            # Redirect back to appropriate page
            return get_redirect_url()

    except ValueError as e:
        # This occurs when a task with the same key already exists
        print(f"ValueError in refresh route: {str(e)}")
        if is_htmx:
            # For HTMX, return a response that triggers a client-side redirect
            response = make_response("")
            if feed_id == "all":
                response.headers['HX-Redirect'] = url_for('index')
            else:
                response.headers['HX-Redirect'] = url_for('entries', feed_id=feed_id)
            return response
        return get_redirect_url()
    except Exception as e:
        # Catch any other exceptions
        print(f"Unexpected error in refresh route: {str(e)}")
        if is_htmx:
            # For HTMX, return a response that triggers a client-side redirect
            response = make_response("")
            if feed_id == "all":
                response.headers['HX-Redirect'] = url_for('index')
            else:
                response.headers['HX-Redirect'] = url_for('entries', feed_id=feed_id)
            return response
        return get_redirect_url()
    # Note: We're using redirects which will cause a full page refresh
    # and show the updated content after the background task is queued.

# Renamed from newsettings, route changed from /newsettings
@app.route("/settings")
def settings():
    template = "settings.html" # Renamed from new-settings.html
    return render_template(template, feeds=get_all_feeds(), theme=get_theme("default"))

# --- Routes kept for settings functionality ---

@app.route("/upload_opml", methods=["POST"])
def upload_opml():
    if 'opml_file' not in request.files:
        return "<div class='feedback-message error'>No file selected</div>"

    uploaded_file = request.files["opml_file"]

    if not uploaded_file.filename or uploaded_file.filename == '':
        return "<div class='feedback-message error'>No file selected</div>"

    if not uploaded_file.filename.endswith('.opml'):
        return "<div class='feedback-message error'>Please select an OPML file</div>"

    try:
        # Submit background task to process OPML
        executor.submit_stored("opml_import", add_feeds_from_opml, uploaded_file)
        return "<div class='feedback-message success'>Processing OPML file... <em>Please refresh the page in a few moments to see the new feeds.</em></div>"
    except Exception as e:
        return f"<div class='feedback-message error'>Error processing OPML file: {str(e)}</div>"


@app.route("/add_feed", methods=["POST"])
def add_feed_route():
    feed_url = request.form.get("feed_url", "").strip()

    if not feed_url:
        return "<div class='feedback-message error'>Please enter a feed URL</div>"

    # Basic URL validation
    if not (feed_url.startswith('http://') or feed_url.startswith('https://')):
        feed_url = 'https://' + feed_url

    try:
        # Check if feed already exists
        session = Session()
        existing_feed = session.query(RssFeed).filter_by(url=feed_url).first()
        session.close()

        if existing_feed:
            return f"<div class='feedback-message warning'>Feed already exists: {existing_feed.title}</div>"

        # Submit background task to add the feed
        executor.submit_stored(f"feed_add_{feed_url}", add_feed_function, feed_url)
        return f"<div class='feedback-message success'>Adding feed: {feed_url}... <em>Please refresh the page in a few moments to see the new feed.</em></div>"

    except Exception as e:
        return f"<div class='feedback-message error'>Error adding feed: {str(e)}</div>"


@app.route("/delete_feed/<feed_id>") # Changed to DELETE method for RESTfulness, requires JS/HTMX change
def delete_feed(feed_id):
    # Assuming remove_feed handles potential errors (e.g., feed not found)
    remove_feed(feed_id)
    # For HTMX, returning an empty response with 200 OK is often used
    # when the target element is removed by hx-target="closest tr" hx-swap="outerHTML"
    # If the settings page should be fully re-rendered by HTMX:
    # return render_template("settings.html", feeds=get_all_feeds(), theme=get_theme("default"))
    # Let's assume the HTMX will handle removal, return empty OK
    return "", 200


@app.route("/set_theme", methods=["POST"])
def set_theme():
    theme_name = request.form["theme"]
    theme = get_theme(theme_name)
    template = "theme.html" # Keep this as it targets the style block
    return render_template(template, theme=theme)


@app.route("/set_default_theme", methods=["POST"])
def route_set_default_theme():
    theme_name = request.form["theme"]
    set_default_theme(theme_name)
    theme = get_theme(theme_name)
    template = "theme.html" # Keep this as it targets the style block
    return render_template(template, theme=theme)


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
            # Cache for 1 hour
            response.headers['Cache-Control'] = 'public, max-age=3600'
            return response
        else:
            # Return 404 if no favicon found
            return '', 404
    finally:
        session.close()


@app.route("/refresh_favicons", methods=["POST"])
def refresh_favicons():
    """Refresh all feed favicons."""
    try:
        # Run the refresh in background
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
            <p>Error: {str(e)}</p>
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
                    <p>Error: {str(e)}</p>
                </div>
                """
        else:
            return '<p>⏳ Refresh in progress...</p>'
            
    except Exception as e:
        return f'<p>Error checking status: {str(e)}</p>'

# Helper function to clean up tasks
def cleanup_tasks():
    """Clean up completed tasks from the executor after they've been displayed."""
    try:
        current_time = datetime.now()
        # Get all done futures and remove them if they've been complete for more than 30 seconds
        for key in list(executor.futures._futures.keys()):
            try:
                future = executor.futures._futures[key]
                if future and future.done():
                    # Check if this task has a completion timestamp
                    if not hasattr(future, '_completion_time'):
                        # Set completion time when we first detect it's done
                        future._completion_time = current_time
                        print(f"Task {key} completed, marking completion time")
                    else:
                        # Check if enough time has passed since completion
                        time_since_completion = (current_time - future._completion_time).total_seconds()
                        if time_since_completion > 30:  # 30 seconds grace period
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
        # Only run cleanup occasionally to avoid overhead on every request
        if hasattr(app, 'cleanup_counter'):
            app.cleanup_counter += 1
            if app.cleanup_counter % 50 != 0:  # Only clean up every 50 requests
                return response
        else:
            app.cleanup_counter = 1

        cleanup_tasks()
    except Exception as e:
        print(f"Error in task cleanup: {e}")
    return response

@app.route("/task_status", methods=["GET"])
def task_status():
    """
    Returns the status of all running background tasks.
    Used for UI feedback on refresh operations.
    """
    tasks = {}

    # Check for all feeds refresh
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

    # Check for individual feed refreshes
    for key in list(executor.futures._futures.keys()):
        if key.startswith("refresh_") and key != "refresh_all":
            future = executor.futures._futures[key]
            feed_id = key.split("refresh_")[1]

            # Attempt to get feed title
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

# --- Removed old routes ---
# /
# /feeds
# /update_feed/<feed_id>
# /get-result
# /entries/<feed_id> (old version)
# /entry/<entry_id> (old version)
# /feed_read/<feed_id>
# /entry_read/<entry_id>/<read_status>
# /fetch_content/<entry_id>
# /settings (old version)

if __name__ == "__main__":
    # Ensure the 'data' directory exists if using SQLite default path
    # Ensure the database directory exists if using SQLite
    if "sqlite:///" in DATABASE_URL:
        db_path = DATABASE_URL.split("///")[1]
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

    port = int(os.environ.get("PORT", 5000))
    # Set debug=True for development, False for production
    app.run(debug=True, host="0.0.0.0", port=port)
