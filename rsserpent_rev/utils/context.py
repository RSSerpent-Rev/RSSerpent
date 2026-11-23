from contextvars import ContextVar
from dataclasses import dataclass, field
from logging import Logger

from pydantic import BaseModel

from ..http import HTTPClient


@dataclass(frozen=True, slots=True)
class PluginContext:
    """Resources for the plugin that owns the current feed route."""

    logger: Logger
    settings: BaseModel | None = field(default=None, repr=False)
    http: HTTPClient | None = field(default=None, repr=False)
    _cache_scope: object = field(default_factory=object, init=False, repr=False, compare=False)


plugin_context = ContextVar[PluginContext | None]("plugin_context", default=None)


def get_plugin_context() -> PluginContext:
    """Return the active plugin context from a feed provider."""
    context = plugin_context.get()
    if context is None:
        message = "A plugin context is available only while a feed provider runs."
        raise RuntimeError(message)
    return context
