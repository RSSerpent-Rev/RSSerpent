import copy
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import replace
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

from .http import HTTPClient
from .log import logger
from .models import Feed, FeedRoute, Plugin, ProviderFn, QueryString
from .plugins.config import PluginConfig, PluginLoadError
from .plugins.documentation import FeedRouteGroup, document_feed
from .utils import fetch_data, filter_fg, gen_ids_for
from .utils.context import PluginContext, plugin_context
from .utils.feed import FeedFilterError, FeedParseError, compile_filters
from .utils.parameters import RouteParameters
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
    plugin: Plugin,
    provider: ProviderFn,
    *,
    parameters: RouteParameters | None = None,
    atom: bool = False,
    path_format: bool = False,
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
        contexts = getattr(request.state, "plugin_contexts", request.app.state.plugin_contexts)
        try:
            with provider_resource.set(resources.get(plugin.name)), plugin_context.set(contexts[plugin.name]):
                if parameters is None:
                    data = await fetch_data(provider, request.path_params, query_params)
                else:
                    data = await provider(**parameters.bind(request.path_params, query_params))
        except ProviderInputError as exception:
            raise HTTPException(400, str(exception)) from exception
        if isinstance(data, Feed):
            fg = data.to_feedgen()
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
            if isinstance(data, Feed) and not fg.author():
                fg.author(name=plugin.author.name)
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


def create_app(
    plugins: Sequence[Plugin] = (),
    *,
    sources: Sequence[str] | None = None,
    config: PluginConfig | None = None,
) -> Starlette:
    if config is not None:
        sources = config.modules
    if sources is None:
        sources = [f"configured plugin {index} ({plugin.name})" for index, plugin in enumerate(plugins, 1)]
    config = config or PluginConfig()
    active_plugins: list[Plugin] = []
    active_sources: dict[str, str] = {}
    plugin_contexts: dict[str, PluginContext] = {}
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
        settings = config.settings_for(source, plugin.settings_model)
        plugin_contexts[plugin.name] = PluginContext(logger.getChild(plugin.name), settings)
        active_plugins.append(plugin)

    @asynccontextmanager
    async def lifespan(_application: Starlette) -> AsyncIterator[dict[str, object]]:
        async with AsyncExitStack() as stack:
            resources: dict[str, object] = {}
            contexts = {}
            for plugin in active_plugins:
                resource = None
                if plugin.lifespan is not None:
                    resource = await stack.enter_async_context(plugin.lifespan())
                    resources[plugin.name] = resource
                client = None
                if plugin.http_client is True:
                    client = (
                        resource if isinstance(resource, HTTPClient) else await stack.enter_async_context(HTTPClient())
                    )
                elif callable(plugin.http_client):
                    client = await stack.enter_async_context(plugin.http_client())
                contexts[plugin.name] = replace(plugin_contexts[plugin.name], http=client)
            yield {"plugin_resources": resources, "plugin_contexts": contexts}

    routes = [Route("/", endpoint=index), Route("/all_routes", endpoint=all_routes)]
    route_sources = {route.path_regex.pattern: (route.path, "RSSerpent core") for route in routes}
    feed_routes_by_plugin: dict[str, list[FeedRouteGroup]] = {}
    diagnostics: list[str] = []
    for plugin in active_plugins:
        source = active_sources[plugin.name]
        groups: list[FeedRouteGroup] = []
        for path in plugin.route_docs.keys() - plugin.routers.keys():
            diagnostics.append(f"{source}: Route documentation for unknown path {path!r}.")
        for path, declaration in plugin.routers.items():
            uses_format_query = ":path}" in path
            parameters = None
            if isinstance(declaration, FeedRoute):
                provider = declaration.provider
                try:
                    parameters = RouteParameters(
                        declaration, Route(path, provider), uses_format_query=uses_format_query
                    )
                except (TypeError, ValueError) as exception:
                    message = f"Invalid provider parameters for {path!r} in {source}: {exception}"
                    raise PluginLoadError(message) from exception
            else:
                provider = declaration
            if uses_format_query:
                feed_routes = [
                    Route(path, endpoint=feed_endpoint(plugin, provider, parameters=parameters, path_format=True))
                ]
            else:
                rss_endpoint = feed_endpoint(plugin, provider, parameters=parameters)
                feed_routes = [
                    Route(path + ".atom", endpoint=feed_endpoint(plugin, provider, parameters=parameters, atom=True)),
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
            group = document_feed(feed_routes, provider, plugin.route_docs.get(path), uses_format_query, parameters)
            groups.append(group)
            diagnostics.extend(f"{source} {path}: {message}" for message in group.diagnostics)
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
    for diagnostic in diagnostics:
        logger.warning("%s", diagnostic)
    application.state.diagnostics = diagnostics
    application.state.plugin_contexts = plugin_contexts
    application.state.plugins = active_plugins
    application.state.feed_routes = feed_routes_by_plugin
    return application
