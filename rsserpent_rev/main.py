import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

import arrow
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route
from starlette.templating import Jinja2Templates, _TemplateResponse as TemplateResponse
from starlette.responses import PlainTextResponse

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
    print("Running on", sys.platform)
    print(f"Installing Chromium at {os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}")
    subprocess.run("playwright install chromium".split())


async def index(request: Request) -> TemplateResponse:
    """Return the index HTML web page."""
    return templates.TemplateResponse("index.html.jinja", {"request": request})


routes = [Route("/", endpoint=index)]


for plugin in plugins:
    for path, provider in plugin.routers.items():

        async def endpoint(
            request: Request, plugin: Plugin = plugin, provider: ProviderFn = provider
        ) -> TemplateResponse:
            """Return an RSS feed of XML format."""
            data = await fetch_data(
                provider, request.path_params, dict(request.query_params)
            )
            return templates.TemplateResponse(
                "rss.xml.jinja",
                {"data": Feed(**data), "plugin": plugin, "request": request},
                media_type="application/xml",
            )

        routes.append(Route(path, endpoint=endpoint))

async def all_routes(request: Request) -> PlainTextResponse:
    """Return all available routes."""
    all_routes = list(map(lambda x: x.routers, plugins))
    all_routes = [item for sublist in all_routes for item in sublist]
    return PlainTextResponse('\n'.join(all_routes))

routes.append(Route("/all_routes", endpoint=all_routes))

app = Starlette(
    debug=bool(os.environ.get("DEBUG")),
    exception_handlers={Exception: exception_handler},
    on_startup=[startup],
    routes=routes,
)
