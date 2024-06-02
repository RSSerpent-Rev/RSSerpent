import copy
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

import arrow
import feedgen
import feedgen.feed
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette.templating import _TemplateResponse as TemplateResponse

from .log import logger
from .models import Feed, Item, Plugin, ProviderFn
from .plugins import plugins
from .utils import fetch_data

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.autoescape = True
templates.env.globals["arrow"] = arrow


async def exception_handler(request: Request, exception: Exception) -> TemplateResponse:
    """Return an HTML web page for displaying the current exception."""
    tb = traceback.format_exc()
    for path in sys.path:
        tb, _ = re.subn(rf'(?<=File "){re.escape(path)}[/\\]', "", tb)
    return templates.TemplateResponse(
        "exception.html.jinja",
        {
            "exception": exception,
            "request": request,
            "traceback": tb,
        },
    )


def startup() -> None:
    """Install Chromium on start-up."""
    if sys.platform == "linux" and "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/tmp"  # pragma: is_not_linux
    logger.info(f"Running on {sys.platform}")
    logger.info(f"Installing Chromium at {os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}")
    subprocess.run("playwright install chromium".split())


async def index(request: Request) -> TemplateResponse:
    """Return the index HTML web page."""
    return templates.TemplateResponse("index.html.jinja", {"request": request})


routes = [Route("/", endpoint=index)]


def filter_fg(fg: feedgen.feed.FeedGenerator, request: Request) -> feedgen.feed.FeedGenerator:
    p = request.query_params
    new_entry = [
        entry
        for entry in fg.entry()
        if ("title_include" not in p or re.search(p["title_include"], entry.title()))
        and ("title_exclude" not in p or not re.search(p["title_exclude"], entry.title()))
        and ("description_include" not in p or re.search(p["description_include"], entry.description()))
        and ("description_exclude" not in p or not re.search(p["description_exclude"], entry.description()))
    ]
    if "limit" in p:
        new_entry = new_entry[: int(p["limit"])]
    fg.entry(new_entry, replace=True)
    return fg


for plugin in plugins:
    for path, provider in plugin.routers.items():

        async def endpoint(request: Request, plugin: Plugin = plugin, provider: ProviderFn = provider) -> Response:
            """Return an RSS feed of XML format."""
            data = await fetch_data(provider, request.path_params, dict(request.query_params))
            if isinstance(data, dict):
                rss20_feed = Feed(**data)
                if "items" in data:
                    rss20_feed.items = [Item(**item) for item in data["items"]]
                rss20_feed.apply_defaults(plugin)
                fg = copy.copy(rss20_feed.to_feedgen())
                fg = filter_fg(fg, request)
                return Response(content=fg.rss_str(pretty=True), media_type="application/xml")
            else:
                fg = copy.copy(data)
                fg = filter_fg(fg, request)
                return Response(content=fg.atom_str(pretty=True), media_type="application/atom+xml")

        routes.append(Route(path, endpoint=endpoint))


async def all_routes(request: Request) -> TemplateResponse:
    """Return all available routes."""
    return templates.TemplateResponse(
        "all_routes.html.jinja",
        {"plugins": plugins, "request": request},
    )


routes.append(Route("/all_routes", endpoint=all_routes))

app = Starlette(
    debug=bool(os.environ.get("DEBUG")),
    exception_handlers={Exception: exception_handler},
    on_startup=[startup],
    routes=routes,
)
