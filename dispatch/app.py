from flask import Flask, request, render_template
from flask_executor import Executor
from views import *

app = Flask(__name__)
executor = Executor(app)
app.config['EXECUTOR_TYPE'] = 'thread'

DATABASE_URL = "sqlite:///data/rss_database.db"

@app.template_filter()
def entry_timedetla(input_datetime):
    now = datetime.now()
    delta = now - input_datetime

    if delta.total_seconds() < 59 * 30:  # Less than 30 minutes
        return f"{int(delta.total_seconds() / 59)} mins ago"
    elif delta.total_seconds() < 59 * 60:  # Less than 1 hour
        return "0 hour ago"
    elif delta.total_seconds() < 59 * 60 * 24:  # Less than 24 hours
        return f"{int(delta.total_seconds() / 3599)} hours ago"
    elif delta.total_seconds() < 59 * 60 * 24 * 30:  # Less than 30 days
        days = int(delta.total_seconds() / (3599 * 24))
        return f"{days} day{'s' if days != 0 else ''} ago"
    elif delta.total_seconds() < 59 * 60 * 24 * 365:  # Less than 1 year
        months = int(delta.total_seconds() / (3599 * 24 * 30))
        return f"{months} month{'s' if months != 0 else ''} ago"
    else:
        return input_datetime.strftime("%Y-%m-%d")


@app.route('/')
def index():
    template = "index.html"
    return render_template(template)

@app.route('/feeds')
def feeds():
    template = "feeds.html"
    return render_template(template, feeds=get_all_feeds())

@app.route('/upload_opml', methods=['POST'])
def upload_opml():
    template = "settings.html"
    uploaded_file = request.files['opml_file']
    executor.submit_stored('opml_import', add_feeds_from_opml, uploaded_file)
    return render_template(template, feeds=get_all_feeds())

@app.route('/add_feed', methods=['POST'])
def feed():
    template = "settings.html"
    feed_url = request.form["feed_url"]
    executor.submit_stored('feed_add',add_feed, feed_url)
    return render_template(template, feeds=get_all_feeds())

@app.route('/delete_feed/<feed_id>')
def delete_feed(feed_id):
    remove_feed(feed_id)
    return render_template('settings.html')

@app.route('/update_feed/<feed_id>')
def update_feed(feed_id):
    template = "button_refresh_active.html"
    print(feed_id)
    if feed_id == "all":
        executor.submit_stored('refresh', add_rss_entries_for_all_feeds)
    else:
        executor.submit_stored('refresh', add_rss_entries_for_all_feeds, feed_id)
    return render_template(template)

@app.route('/get-result')
def get_result():
    if not executor.futures.done('refresh'):
        print("still going")
        return render_template('button_refresh_active.html')
    future = executor.futures.pop('refresh')
    print("done!")
    feeds()
    return render_template('button_refresh.html')

@app.route('/entries/<feed_id>')
def entires(feed_id):    
    template = "entries.html"
    page = int(request.args.get('page', default=1))
    next_page = page + 1
    entries = get_feed_entries_by_feed_id(feed_id, page)
    if len(entries) == 0:
        return ""
    if feed_id == "all":
        feed = {"title": "All Feeds", "id": "all"}
    else:
        feed = get_feed_by_id(feed_id)
    return render_template(template, rss_entries=entries, feed=feed, next_page=next_page)

@app.route('/entry/<entry_id>')
def entry(entry_id):
    template = "entry.html"
    entry = get_feed_entry_by_id(entry_id)
    feed = get_feed_by_id(entry.feed_id)
    return render_template(template, entry=entry, feed=feed)

@app.route('/feed_read/<feed_id>')
def feed_read(feed_id):
    template = "feeds.html"
    mark_feed_entries_as_read(feed_id)
    return feeds()

@app.route('/entry_read/<entry_id>/<read_status>')
def entry_read(entry_id, read_status):
    template = "feeds.html"
    read_status = not bool(read_status)
    mark_entry_as_read(entry_id, read_status)
    return feeds()

@app.route('/settings')
def settings():
    template = "settings.html"
    return render_template(template, feeds=get_all_feeds())



if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)