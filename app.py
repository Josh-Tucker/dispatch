import asyncio
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.staticfiles import StaticFiles
from starlette.routing import Route, Mount
from sse_starlette.sse import EventSourceResponse

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


async def numbers(minimum, maximum):
    for i in range(minimum, maximum + 1):
        await asyncio.sleep(0.9)
        yield dict(data=i)

async def update_all_feeds(request):
    generator = numbers(1, 5)
    lastfeed = add_rss_entries_for_all_feeds()
    return EventSourceResponse(lastfeed)

def update_feed(request):
    template = "feeds.html"
    udd_rss_entries_for_all_feeds()
    context = {"request": request}
    return HTTPResponse()

def entries(request):
    template = "entries.html"
    feed_id = request.path_params["feed_id"]
    entries = get_feed_entries_by_feed_id(feed_id)
    feed = get_feed_by_id(feed_id)
    context = {"request": request, "rss_entries": entries, "rss_feed": feed}
    return templates.TemplateResponse(template, context)


def all_entries(request):
    template = "entries.html"
    entries = get_all_feed_entries()
    feed = {"title": "All Feeds"}
    context = {"request": request, "rss_entries": entries, "rss_feed": feed}
    return templates.TemplateResponse(template, context)


def entry(request):
    template = "entry.html"
    entry_id = request.path_params["entry_id"]
    entry = get_feed_entry_by_id(entry_id)
    context = {"request": request, "rss_entry": entry}
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
    Route("/entries", all_entries),
    Route("/entries/{feed_id}", entries),
    Route("/update_feed", update_all_feeds),
    Route("/update_feed/{feed_id}", update_feed),
    Route("/entry/{entry_id}", entry),
    Mount("/static", app=StaticFiles(directory="static"), name="static"),
]

exception_handlers = {404: not_found, 500: server_error}

app = Starlette(debug=False, routes=routes, exception_handlers=exception_handlers)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
