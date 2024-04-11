import asyncio
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from starlette.requests import Request
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.routing import Route, Mount
from starlette.templating import Jinja2Templates
from starlette.config import Config
from starlette.datastructures import CommaSeparatedStrings, Secret
from views import *
import uvicorn

config = Config(".env")

DEBUG = config('DEBUG', cast=bool, default=False)
PORT = config('PORT', cast=int)
DATABASE_URL = config('DATABASE_URL')


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

def settings(request):
    template = "settings.html"
    context = {"request": request, "rss_feeds": get_all_feeds()}
    return templates.TemplateResponse(template, context)

# async def add_feed(request):
#     print(request)
#     feed_url = request
#     print(feed_url)
#     try:
#         response = await add_feed(feed_url)
#         print(response)
#         if response.status_code == 201:
#             print("201")
#             return HTMLResponse(f"<div class='success-message'>{response.body.decode()}</div>")
#         elif response.status_code == 409:
#             print("409")
#             return HTMLResponse(f"<div class='error-message'>{response.body.decode()}</div>")
#         else:
#             print("error adding feed")
#             print(response.error)
#             return HTMLResponse(f"<div class='error-message'>An error occurred while adding the feed: {response.body.decode()}</div>")
#     except Exception as e:
#         print(e)
#         return HTMLResponse(f"<div class='error-message'>An error occurred: {e}</div>")

async def add_feed(request: Request):
    data = await request.json()
    rss_url = data.get('rss_url')
    if rss_url:
        print(rss_url)
        # Process the RSS feed URL here (e.g., validate, add to database)
        return JSONResponse({"status": "success", "message": "RSS feed added successfully"})
    else:
        return JSONResponse({"status": "error", "message": "RSS URL is required"})


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
    Route("/settings", settings),
    Route("/add_feed", add_feed, methods=["POST"]),
    Mount("/static", app=StaticFiles(directory="static"), name="static"),
]

exception_handlers = {404: not_found, 500: server_error}

app = Starlette(debug=False, routes=routes, exception_handlers=exception_handlers)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
