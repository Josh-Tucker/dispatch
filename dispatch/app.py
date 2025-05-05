import os
from flask import Flask, request, render_template, redirect, url_for
from flask_executor import Executor
from views import *
from datetime import datetime
import logging

app = Flask(__name__)
executor = Executor(app)
app.config["EXECUTOR_TYPE"] = "thread"
DATABASE_URL = "sqlite:///data/rss_database.db"
ENTRIES_PER_PAGE = 20

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


@app.template_filter()
def entry_timedetla(input_datetime):
    now = datetime.now()
    delta = now - input_datetime

    if delta.total_seconds() < 59 * 30:
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} min{'s' if minutes != 1 else ''} ago"
    elif delta.total_seconds() < 59 * 60:
        return "less than an hour ago"
    elif delta.total_seconds() < 59 * 60 * 24:
        hours = int(delta.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif delta.total_seconds() < 59 * 60 * 24 * 30:  #
        days = int(delta.total_seconds() / (3600 * 24))
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif delta.total_seconds() < 59 * 60 * 24 * 365:
        months = int(delta.total_seconds() / (3600 * 24 * 30))
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        years = int(delta.total_seconds() / (3600 * 24 * 365))
        return f"{years} year{'s' if years != 1 else ''} ago"


@app.route("/")
def index():
    template = "index.html"
    return render_template(template, theme=get_theme("default"), feeds=get_all_feeds())


# Route for the initial full page load
@app.route("/entries/<feed_id>")
def entries(feed_id):
    page = 1  # Initial load is always page 1
    template = "entries.html"

    # Fetch the first page of entries
    entries_page = get_feed_entries_by_feed_id(
        feed_id, page=page, entries_per_page=ENTRIES_PER_PAGE
    )

    # Determine if there are more pages beyond page 1
    has_more_pages = len(entries_page) == ENTRIES_PER_PAGE
    next_page = page + 1 if has_more_pages else None

    # Get feed info
    if feed_id == "all":
        feed = {"title": "All Feeds", "id": "all", "favicon_path": None}
    else:
        feed = get_feed_by_id(feed_id)  # Ensure this function is robust

    # Render the full page template
    return render_template(
        template,
        entries=entries_page,  # Pass the first page entries
        feed=feed,
        feed_id=feed_id,
        theme=get_theme("default"),
        next_page=next_page,  # Pass info needed for the first trigger
        has_more_pages=has_more_pages,
    )


@app.route("/entries/<feed_id>/page")
def entries_page_partial(feed_id):
    page = request.args.get("page", 1, type=int)
    template = "entries-partial.html"

    entries_page = get_feed_entries_by_feed_id(
        feed_id, page=page, entries_per_page=ENTRIES_PER_PAGE
    )

    has_more_pages = len(entries_page) == ENTRIES_PER_PAGE
    next_page = page + 1 if has_more_pages else None

    return render_template(
        template,
        entries=entries_page,
        feed_id=feed_id,
        next_page=next_page,
        has_more_pages=has_more_pages,
    )


@app.route("/entry/<entry_id>")
def entry(entry_id):
    template = "entry.html"
    entry = get_feed_entry_by_id(entry_id)
    feed = get_feed_by_id(entry.feed_id)
    read_status = True
    mark_entry_as_read(entry_id, read_status)
    return render_template(template, entry=entry, feed=feed, theme=get_theme("default"))


@app.route("/refresh/<feed_id>", methods=["POST"])
def refresh(feed_id):
    if feed_id == "all":
        executor.submit_stored("refresh_all", add_rss_entries_for_all_feeds)

        return redirect(url_for("index"))
    else:
        executor.submit_stored(f"refresh_{feed_id}", add_rss_entries_for_feed, feed_id)
        return redirect(url_for("entries", feed_id=feed_id))


@app.route("/settings")
def settings():
    template = "settings.html"
    return render_template(template, feeds=get_all_feeds(), theme=get_theme("default"))


@app.route("/upload_opml", methods=["POST"])
def upload_opml():
    template = "settings.html"
    uploaded_file = request.files["opml_file"]
    if uploaded_file and uploaded_file.filename != "":
        executor.submit_stored("opml_import", add_feeds_from_opml, uploaded_file)
    return render_template(template, feeds=get_all_feeds(), theme=get_theme("default"))


@app.route("/add_feed", methods=["POST"])
def add_feed():
    template = "settings.html"
    feed_url = request.form["feed_url"]
    if feed_url:
        executor.submit_stored("feed_add", add_feed, feed_url)
    return render_template(template, feeds=get_all_feeds(), theme=get_theme("default"))


@app.route("/delete_feed/<feed_id>")
def delete_feed(feed_id):
    remove_feed(feed_id)
    return "", 200


@app.route("/set_theme", methods=["POST"])
def set_theme():
    theme_name = request.form["theme"]
    theme = get_theme(theme_name)
    template = "theme.html"
    return render_template(template, theme=theme)


@app.route("/set_default_theme", methods=["POST"])
def route_set_default_theme():
    theme_name = request.form["theme"]
    set_default_theme(theme_name)
    theme = get_theme(theme_name)
    template = "theme.html"
    return render_template(template, theme=theme)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
