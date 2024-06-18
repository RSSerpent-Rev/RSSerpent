import copy
import hashlib
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


def filter_fg(fg: feedgen.feed.FeedGenerator, request: Request) -> None:
    p = request.query_params
    new_entry = [
        entry
        for entry in fg.entry()
        if ("title_include" not in p or re.search(p["title_include"], entry.title()))
        and ("title_exclude" not in p or not re.search(p["title_exclude"], entry.title()))
        and ("description_include" not in p or re.search(p["description_include"], entry.description()))
        and ("description_exclude" not in p or not re.search(p["description_exclude"], entry.description()))
        and (
            "category_include" not in p
            or any(re.search(p["category_include"], category["term"]) for category in entry.category())
        )
        and (
            "category_exclude" not in p
            or not any(re.search(p["category_exclude"], category["term"]) for category in entry.category())
        )
    ]
    if "limit" in p:
        new_entry = new_entry[: int(p["limit"])]
    fg.entry(new_entry, replace=True)


def gen_ids(fg: feedgen.feed.FeedGenerator) -> None:
    if not fg.id():
        fg.id(hashlib.md5(fg.title().encode()).hexdigest())
    for entry in fg.entry():
        if not entry.id():
            hash_content = entry.title() + entry.description()
            entry.id(hashlib.md5(hash_content.encode()).hexdigest())


for plugin in plugins:
    for path, provider in plugin.routers.items():

        async def endpoint(request: Request, plugin: Plugin = plugin, provider: ProviderFn = provider) -> Response:
            """Return an RSS feed of XML format."""
            path_params = request.path_params
            for key, value in request.path_params.items():
                if isinstance(value, str) and (value.endswith(".rss") or value.endswith(".atom")):
                    path_params[key] = value[:-5]
            data = await fetch_data(provider, request.path_params, dict(request.query_params))
            if isinstance(data, dict):
                rss20_feed = Feed(**data)
                if "items" in data:
                    rss20_feed.items = [Item(**item) for item in data["items"]]
                rss20_feed.apply_defaults(plugin)
                fg = copy.copy(rss20_feed.to_feedgen())
                filter_fg(fg, request)
                if request.url.path.endswith(".atom"):
                    gen_ids(fg)
                    return Response(
                        content=fg.atom_str(pretty=True).decode("UTF-8"),
                        media_type="application/atom+xml;charset=utf-8",
                    )
                return Response(
                    content=fg.rss_str(pretty=True).decode("UTF-8"), media_type="application/xml;charset=utf-8"
                )
            else:
                fg = copy.copy(data)
                filter_fg(fg, request)
                if request.url.path.endswith(".rss"):
                    return Response(
                        content=fg.rss_str(pretty=True).decode("UTF-8"), media_type="application/xml;charset=utf-8"
                    )
                return Response(content=fg.atom_str(pretty=True), media_type="application/atom+xml;charset=utf-8")

        routes.append(Route(path, endpoint=endpoint))
        routes.append(Route(path + ".rss", endpoint=endpoint))
        routes.append(Route(path + ".atom", endpoint=endpoint))


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
