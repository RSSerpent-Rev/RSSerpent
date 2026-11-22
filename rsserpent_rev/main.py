import copy
import os
import subprocess
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import arrow
import httpx
from feedgen.feed import FeedGenerator
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette.templating import _TemplateResponse as TemplateResponse

from .log import logger
from .models import Plugin, ProviderFn, QueryString, RSSFeed
from .plugins.builtin import plugin as builtin_plugin
from .plugins.externals import plugins as external_plugins
from .utils import fetch_data, filter_fg, gen_ids_for
from .utils.feed import FeedFilterError, compile_filters
from .utils.provider import ProviderInputError

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.autoescape = True
templates.env.globals["arrow"] = arrow

ATOM_MIMETYPE = "application/atom+xml;charset=utf-8"
RSS_MIMETYPE = "application/xml;charset=utf-8"


class MainError(Exception):
    """Exception for `Main` class."""

    unexpected_data_type = "unexpected data type."


async def exception_handler(_request: Request, exception: Exception) -> Response:
    """Log the error and return a safe response."""
    logger.error("Feed request failed", exc_info=exception)
    if isinstance(exception, httpx.TimeoutException):
        return PlainTextResponse("Gateway Timeout", status_code=504)
    if isinstance(exception, httpx.HTTPError):
        return PlainTextResponse("Bad Gateway", status_code=502)
    return PlainTextResponse("Internal Server Error", status_code=500)


def env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def startup() -> None:
    """Install Chromium on start-up."""
    if sys.platform == "linux" and "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/tmp"  # pragma: is_not_linux
    logger.info(f"Running on {sys.platform}")
    logger.info(f"Installing Chromium at {os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}")
    subprocess.run(["playwright", "install", "chromium"])


async def index(request: Request) -> TemplateResponse:
    """Return the index HTML web page."""
    return templates.TemplateResponse(request, "index.html.jinja")


def feed_endpoint(
    plugin: Plugin, provider: ProviderFn, *, atom: bool = False, path_format: bool = False
) -> Callable[[Request], Awaitable[Response]]:
    async def endpoint(request: Request) -> Response:
        """Return an RSS feed of XML format."""
        query_params = dict(request.query_params)
        output_format = query_params.pop("format", "rss") if path_format else ("atom" if atom else "rss")
        if output_format not in {"rss", "atom"}:
            raise HTTPException(400, "Invalid feed format")
        try:
            qs = QueryString.model_validate(query_params)
            patterns = compile_filters(qs)
        except ValidationError as exception:
            raise HTTPException(400, "Invalid query parameters") from exception
        except FeedFilterError as exception:
            raise HTTPException(400, str(exception)) from exception
        try:
            data = await fetch_data(provider, request.path_params, query_params)
        except ProviderInputError as exception:
            raise HTTPException(400, str(exception)) from exception
        if isinstance(data, dict):
            feed = RSSFeed.model_validate(data)
            fg = feed.to_feedgen()
        elif isinstance(data, RSSFeed):
            feed = copy.copy(data)
            fg = feed.to_feedgen()
        elif isinstance(data, FeedGenerator):
            fg = copy.copy(data)
        else:
            raise MainError(MainError.unexpected_data_type)
        try:
            filter_fg(fg, qs, patterns=patterns)
        except FeedFilterError as exception:
            raise HTTPException(400, str(exception)) from exception
        fg.generator(plugin.name, uri=str(plugin.repository))
        if fg.managingEditor() is None:
            fg.managingEditor(f"{plugin.author.email} ({plugin.author.name})")
        if fg.webMaster() is None:
            fg.webMaster(f"{plugin.author.email} ({plugin.author.name})")
        gen_ids_for(fg, atom=output_format == "atom")
        if output_format == "atom":
            return Response(content=fg.atom_str(pretty=True), media_type=ATOM_MIMETYPE)
        return Response(content=fg.rss_str(pretty=True), media_type=RSS_MIMETYPE)

    return endpoint


async def all_routes(request: Request) -> TemplateResponse:
    """Return all available routes."""
    return templates.TemplateResponse(
        request,
        "all_routes.html.jinja",
        {"plugins": request.app.state.plugins},
    )


def create_app(plugins: list[Plugin] | None = None) -> Starlette:
    if plugins is None:
        plugins = list(external_plugins)
        if env_enabled("RSSERPENT_ENABLE_EXAMPLES"):
            plugins.insert(0, builtin_plugin)

    routes = [Route("/", endpoint=index), Route("/all_routes", endpoint=all_routes)]
    for plugin in plugins:
        for path, provider in plugin.routers.items():
            if ":path}" in path:
                routes.append(Route(path, endpoint=feed_endpoint(plugin, provider, path_format=True)))
            else:
                routes.append(Route(path + ".atom", endpoint=feed_endpoint(plugin, provider, atom=True)))
                rss_endpoint = feed_endpoint(plugin, provider)
                routes.extend(Route(path + suffix, endpoint=rss_endpoint) for suffix in (".rss", ""))

    application = Starlette(
        debug=env_enabled("DEBUG"),
        exception_handlers={Exception: exception_handler, httpx.HTTPError: exception_handler},
        on_startup=[startup],
        routes=routes,
    )
    application.state.plugins = plugins
    return application


app = create_app()
