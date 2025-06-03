import os
import json
from flask import Flask, request, render_template, redirect, url_for, jsonify
from flask_executor import Executor
from views import * # Assuming views.py contains all necessary db/logic functions like get_theme, get_all_feeds, etc.
from datetime import datetime # Make sure datetime is imported

app = Flask(__name__)
executor = Executor(app)
app.config["EXECUTOR_TYPE"] = "thread"

DATABASE_URL = "sqlite:///data/rss_database.db" # Keep if needed by views.py, otherwise remove

# Keep the template filter as it's used in new-entry-card.html (soon to be entry-card.html)
@app.template_filter()
def entry_timedetla(input_datetime):
    now = datetime.now()
    delta = now - input_datetime

    if delta.total_seconds() < 59 * 30:  # Less than 30 minutes
        minutes = int(delta.total_seconds() / 60) # Corrected calculation
        return f"{minutes} min{'s' if minutes != 1 else ''} ago"
    elif delta.total_seconds() < 59 * 60:  # Less than 1 hour
        return "0 hours ago" # Or perhaps "< 1 hour ago"
    elif delta.total_seconds() < 59 * 60 * 24:  # Less than 24 hours
        hours = int(delta.total_seconds() / 3600) # Corrected calculation
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif delta.total_seconds() < 59 * 60 * 24 * 30:  # Less than 30 days
        days = int(delta.total_seconds() / (3600 * 24)) # Corrected calculation
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif delta.total_seconds() < 59 * 60 * 24 * 365:  # Less than 1 year
        months = int(delta.total_seconds() / (3600 * 24 * 30)) # Corrected calculation
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        years = int(delta.total_seconds() / (3600 * 24 * 365)) # Added years
        return f"{years} year{'s' if years != 1 else ''} ago" # Or use strftime as before: input_datetime.strftime("%Y-%m-%d")


# Renamed from newindex, route changed from /new to /
@app.route("/")
def index():
    template = "index.html" # Renamed from new-index.html
    return render_template(template, theme=get_theme("default"), feeds=get_all_feeds())

# Renamed from newentries, route changed from /newentries/<feed_id>
@app.route("/entries/<feed_id>")
def entries(feed_id):
    template = "entries.html" # Renamed from new-entries.html
    # Note: Pagination logic might need adding back if desired, the original newentries didn't have it
    # page = int(request.args.get("page", default=1))
    # next_page = page + 1
    # For now, get all entries for the feed
    entries = get_feed_entries_by_feed_id(feed_id) # Removed page argument
    if feed_id == "all":
        feed = {"title": "All Feeds", "id": "all", "favicon_path": None} # Added favicon_path for consistency
    else:
        feed = get_feed_by_id(feed_id)
    return render_template(template, entries=entries, feed=feed, theme=get_theme("default")) # Renamed fee=feed

# Renamed from newentry, route changed from /newentry/<entry_id>
@app.route("/entry/<entry_id>")
def entry(entry_id):
    template = "entry.html" # Renamed from new-entry.html
    entry = get_feed_entry_by_id(entry_id)
    feed = get_feed_by_id(entry.feed_id)
    read_status = True
    mark_entry_as_read(entry_id, read_status) # Mark as read when viewed
    return render_template(template, entry=entry, feed=feed, theme=get_theme("default"))

# Renamed from newrefresh, route changed from /newrefresh/<feed_id>
@app.route("/refresh/<feed_id>", methods=["POST"])
def refresh(feed_id):
    # Get the referrer URL to determine where to redirect back to
    referrer = request.referrer if request.referrer else "/"
    
    # Run a cleanup to remove any completed tasks before starting new ones
    try:
        cleanup_tasks()
    except Exception as e:
        print(f"Error cleaning up tasks before refresh: {e}")
    
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
    
    try:
        if feed_id == "all":
            # Check if task is already running
            if f"refresh_all" in executor.futures._futures:
                print(f"Task refresh_all is already running")
                return get_redirect_url()
                
            executor.submit_stored("refresh_all", add_rss_entries_for_all_feeds)
            print(f"Started task refresh_all")
            return redirect(url_for('index'))
        else:
            # Validate feed_id exists
            try:
                feed_id_int = int(feed_id)  # Make sure it's a valid integer if numeric
            except ValueError:
                print(f"Invalid feed_id format: {feed_id}")
                return get_redirect_url()
                
            # Check if task is already running
            if f"refresh_{feed_id}" in executor.futures._futures:
                print(f"Task refresh_{feed_id} is already running")
                return get_redirect_url()
            
            # Ensure feed_id is passed correctly if the function expects it
            try:
                executor.submit_stored(f"refresh_{feed_id}", add_rss_entries_for_feed, feed_id)
                print(f"Started task refresh_{feed_id}")
            except Exception as e:
                print(f"Error starting refresh task for feed {feed_id}: {str(e)}")
            
            # Redirect back to appropriate page
            return get_redirect_url()
            
    except ValueError as e:
        # This occurs when a task with the same key already exists
        print(f"ValueError in refresh route: {str(e)}")
        return get_redirect_url()
    except Exception as e:
        # Catch any other exceptions
        print(f"Unexpected error in refresh route: {str(e)}")
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
    template = "settings.html" # Use the renamed settings template
    uploaded_file = request.files["opml_file"]
    if uploaded_file and uploaded_file.filename != '':
        # Consider adding error handling for file processing
        executor.submit_stored("opml_import", add_feeds_from_opml, uploaded_file)
        # Give background task time to start, then refresh settings page
        # A better approach might involve HTMX swapping or JS polling
        # For simplicity now, just re-render the settings page
        # Ideally, wait for the executor task or provide feedback
    return render_template(template, feeds=get_all_feeds(), theme=get_theme("default"))


@app.route("/add_feed", methods=["POST"])
def add_feed():
    template = "settings.html" # Use the renamed settings template
    feed_url = request.form["feed_url"]
    if feed_url:
        # Consider adding error handling/validation for the URL
        executor.submit_stored("feed_add", add_feed, feed_url)
        # Re-render settings page after submitting task (similar caveat as upload_opml)
    return render_template(template, feeds=get_all_feeds(), theme=get_theme("default"))


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

# Helper function to clean up tasks
def cleanup_tasks():
    """Clean up completed tasks from the executor."""
    try:
        # Get all done futures and remove them
        for key in list(executor.futures._futures.keys()):
            try:
                future = executor.futures._futures[key]
                if future and future.done():
                    executor.futures._futures.pop(key, None)
                    print(f"Cleaned up completed task: {key}")
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
            if app.cleanup_counter % 5 != 0:  # Only clean up every 5 requests
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
    # Run a cleanup before checking status to remove completed tasks
    try:
        cleanup_tasks()
    except Exception as e:
        print(f"Error cleaning up tasks before status check: {e}")
        
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
    # if "sqlite:///" in DATABASE_URL:
    #     db_path = DATABASE_URL.split("///")[1]
    #     db_dir = os.path.dirname(db_path)
    #     if db_dir and not os.path.exists(db_dir):
    #         os.makedirs(db_dir)

    port = int(os.environ.get("PORT", 5000))
    # Set debug=True for development, False for production
    app.run(debug=True, host="0.0.0.0", port=port)
