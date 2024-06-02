import os
import re
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

import arrow
import feedgen
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette.templating import _TemplateResponse as TemplateResponse

from .log import logger
from .models import Feed, Plugin, ProviderFn
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


async def rss20(request: Request, plugin: Plugin, data: dict[str:Any]) -> TemplateResponse:
    p = request.query_params
    include_condi = ["description_include", "title_include"]
    exclude_condi = ["description_exclude", "title_exclude"]

    data["items"] = [
        item
        for item in data["items"]
        if all(p.get(cond) is None or re.search(p[cond], item[cond.split("_")[0]]) for cond in include_condi)
        and all(p.get(cond) is None or not re.search(p[cond], item[cond.split("_")[0]]) for cond in exclude_condi)
    ]
    if "limit" in request.query_params:
        data["items"] = data["items"][: int(request.query_params["limit"])]
    return templates.TemplateResponse(
        "rss.xml.jinja",
        {"data": Feed(**data), "plugin": plugin, "request": request},
        media_type="application/xml",
    )


for plugin in plugins:
    for path, provider in plugin.routers.items():

        async def endpoint(
            request: Request, plugin: Plugin = plugin, provider: ProviderFn = provider
        ) -> TemplateResponse:
            """Return an RSS feed of XML format."""
            data = await fetch_data(provider, request.path_params, dict(request.query_params))
            if isinstance(data, dict):
                return await rss20(request, plugin, data.copy())
            feed: feedgen.feed.FeedGenerator = data
            return Response(content=feed.atom_str(pretty=True), media_type="application/atom+xml")

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
