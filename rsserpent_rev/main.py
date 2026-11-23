import copy
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import cast

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
from .plugins.config import PluginLoadError
from .plugins.documentation import FeedRouteGroup, document_feed
from .utils import fetch_data, filter_fg, gen_ids_for
from .utils.feed import FeedFilterError, FeedParseError, compile_filters
from .utils.provider import ProviderInputError, provider_resource

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
    if isinstance(exception, (httpx.HTTPError, FeedParseError)):
        return PlainTextResponse("Bad Gateway", status_code=502)
    return PlainTextResponse("Internal Server Error", status_code=500)


async def http_exception_handler(_request: Request, exception: Exception) -> Response:
    error = cast(HTTPException, exception)
    if error.status_code >= 500:
        logger.error("Feed request failed", exc_info=exception)
    if error.status_code in {204, 304}:
        return Response(status_code=error.status_code, headers=error.headers)
    return PlainTextResponse(error.detail, status_code=error.status_code, headers=error.headers)


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
        resources = getattr(request.state, "plugin_resources", {})
        try:
            with provider_resource.set(resources.get(plugin.name)):
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
        {"plugins": request.app.state.plugins, "feed_routes": request.app.state.feed_routes},
    )


def create_app(plugins: Sequence[Plugin] = (), *, sources: Sequence[str] | None = None) -> Starlette:
    if sources is None:
        sources = [f"configured plugin {index} ({plugin.name})" for index, plugin in enumerate(plugins, 1)]
    active_plugins: list[Plugin] = []
    active_sources: dict[str, str] = {}
    for plugin, source in zip(plugins, sources, strict=True):
        if plugin.enabled is not None:
            if not plugin.enabled():
                continue
        elif plugin.name == "rsserpent-plugin-rss-proxy":
            # Earlier proxy releases do not restrict upstream destinations.
            continue
        if plugin.name in active_sources:
            message = f"Duplicate plugin name {plugin.name!r}: {active_sources[plugin.name]} and {source}."
            raise PluginLoadError(message)
        active_sources[plugin.name] = source
        active_plugins.append(plugin)

    @asynccontextmanager
    async def lifespan(_application: Starlette) -> AsyncIterator[dict[str, dict[str, object]]]:
        async with AsyncExitStack() as stack:
            resources = {}
            for plugin in active_plugins:
                if plugin.lifespan is not None:
                    resources[plugin.name] = await stack.enter_async_context(plugin.lifespan())
            yield {"plugin_resources": resources}

    routes = [Route("/", endpoint=index), Route("/all_routes", endpoint=all_routes)]
    route_sources = {route.path_regex.pattern: (route.path, "RSSerpent core") for route in routes}
    feed_routes_by_plugin: dict[str, list[FeedRouteGroup]] = {}
    for plugin in active_plugins:
        source = active_sources[plugin.name]
        groups: list[FeedRouteGroup] = []
        for path in plugin.route_docs.keys() - plugin.routers.keys():
            logger.warning("Ignoring route documentation for unknown path %s in %s", path, plugin.name)
        for path, provider in plugin.routers.items():
            uses_format_query = ":path}" in path
            if uses_format_query:
                feed_routes = [Route(path, endpoint=feed_endpoint(plugin, provider, path_format=True))]
            else:
                rss_endpoint = feed_endpoint(plugin, provider)
                feed_routes = [
                    Route(path + ".atom", endpoint=feed_endpoint(plugin, provider, atom=True)),
                    Route(path + ".rss", endpoint=rss_endpoint),
                    Route(path, endpoint=rss_endpoint),
                ]
            for route in feed_routes:
                # Parameter names do not change the set of paths a route matches.
                shape = re.sub(r"\(\?P<[^>]+>", "(?:", route.path_regex.pattern)
                if shape in route_sources:
                    previous_path, previous_source = route_sources[shape]
                    message = (
                        f"Route {route.path!r} from {source} conflicts with {previous_path!r} from {previous_source}."
                    )
                    raise PluginLoadError(message)
                route_sources[shape] = (route.path, source)
                routes.append(route)
            groups.append(document_feed(feed_routes, provider, plugin.route_docs.get(path), uses_format_query))
        feed_routes_by_plugin[plugin.name] = groups
        logger.info("Loaded plugin %s from %s", plugin.name, source)

    application = Starlette(
        exception_handlers={
            Exception: exception_handler,
            HTTPException: http_exception_handler,
            httpx.HTTPError: exception_handler,
            FeedParseError: exception_handler,
        },
        lifespan=lifespan,
        routes=routes,
    )
    application.state.plugins = active_plugins
    application.state.feed_routes = feed_routes_by_plugin
    return application
