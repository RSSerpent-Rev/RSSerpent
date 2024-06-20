import copy
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

import arrow
from feedgen.feed import FeedGenerator
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette.templating import _TemplateResponse as TemplateResponse

from .log import logger
from .models import Feed, Plugin, ProviderFn, QueryString
from .plugins import plugins
from .utils import fetch_data, filter_fg, gen_ids_for

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.autoescape = True
templates.env.globals["arrow"] = arrow

ATOM_MIMETYPE = "application/atom+xml;charset=utf-8"
RSS_MIMETYPE = "application/xml;charset=utf-8"


class MainError(Exception):
    """Exception for `Main` class."""

    unexpected_data_type = "unexpected data type."


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


for plugin in plugins:
    for path, provider in plugin.routers.items():

        async def endpoint(request: Request, plugin: Plugin = plugin, provider: ProviderFn = provider) -> Response:
            """Return an RSS feed of XML format."""
            qs = QueryString.model_validate(dict(request.query_params)) if request.query_params else None
            path_params = copy.copy(request.path_params)
            for key, value in request.path_params.items():
                if isinstance(value, str) and (value.endswith(".rss") or value.endswith(".atom")):
                    path_params[key] = value[:-4] if value.endswith(".rss") else value[:-5]
            data = await fetch_data(provider, path_params, dict(request.query_params))
            if isinstance(data, dict):
                feed = Feed.model_validate(data)
                feed.populate_defaults_with(plugin)
                fg = feed.to_feedgen()
            elif isinstance(data, Feed):
                feed = copy.copy(data)
                feed.populate_defaults_with(plugin)
                fg = feed.to_feedgen()
            elif isinstance(data, FeedGenerator):
                fg = copy.copy(data)
            else:
                raise MainError(MainError.unexpected_data_type)
            gen_ids_for(fg)
            if qs:
                filter_fg(fg, qs)
            fg.generator(plugin.name)
            if request.url.path.endswith(".atom"):
                return Response(content=fg.atom_str(pretty=True), media_type=ATOM_MIMETYPE)
            return Response(content=fg.rss_str(pretty=True), media_type=RSS_MIMETYPE)

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
