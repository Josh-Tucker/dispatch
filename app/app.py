import asyncio
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.routing import Route, Mount
from starlette.templating import Jinja2Templates
from views import *
import uvicorn


templates = Jinja2Templates(directory="templates")
templates.env.filters["entry_timedetla"] = format_time_delta_or_date


def homepage(request):
    template = "index.html"
    context = {"request": request}
    return templates.TemplateResponse(template, context)


def feeds(request):
    template = "feeds.html"
    context = {"request": request, "rss_feeds": get_all_feeds()}
    return templates.TemplateResponse(template, context)

def update_feed(request):
    template = "refresh_button.html"
    feed_id = request.path_params["feed_id"]
    print(feed_id)
    if feed_id == "all":
        add_rss_entries_for_all_feeds()
    else:
        add_rss_entries("feed_id")
    context = {"request": request}
    return templates.TemplateResponse(template, context)

def entries(request):
    template = "entries.html"
    feed_id = request.path_params["feed_id"]
    page = int(request.query_params.get('page', default=1))
    next_page = page + 1
    entries = get_feed_entries_by_feed_id(feed_id, page)
    if len(entries) == 0:
        return Response()
    if feed_id == "all":
        feed = {"title": "All Feeds", "id": "all"}
    else:
        feed = get_feed_by_id(feed_id)
    context = {"request": request, "rss_entries": entries, "rss_feed": feed, "next_page":next_page}
    return templates.TemplateResponse(template, context)


def entry(request):
    template = "entry.html"
    entry_id = request.path_params["entry_id"]
    entry = get_feed_entry_by_id(entry_id)
    feed = get_feed_by_id(entry.feed_id)
    context = {"request": request, "rss_entry": entry, "rss_feed": feed}
    return templates.TemplateResponse(template, context)


def error(request):
    """
    An example error. Switch the `debug` setting to see either tracebacks or 500 pages.
    """
    raise RuntimeError("Oh no")


def not_found(request: Request, exc: HTTPException):
    """
    Return an HTTP 404 page.
    """
    template = "404.html"
    context = {"request": request}
    return templates.TemplateResponse(template, context, status_code=404)


def server_error(request: Request, exc: HTTPException):
    """
    Return an HTTP 500 page.
    """
    template = "500.html"
    context = {"request": request}
    return templates.TemplateResponse(template, context, status_code=500)


routes = [
    Route("/", homepage),
    Route("/error", error),
    Route("/feeds", feeds),
    Route("/entries/{feed_id}", entries),
    Route("/update_feed/{feed_id}", update_feed),
    Route("/entry/{entry_id}", entry),
    Mount("/static", app=StaticFiles(directory="static"), name="static"),
]

exception_handlers = {404: not_found, 500: server_error}

app = Starlette(debug=False, routes=routes, exception_handlers=exception_handlers)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
