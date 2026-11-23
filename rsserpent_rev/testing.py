from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial

import httpx
from starlette.testclient import TestClient

from .main import create_app
from .models import Plugin
from .plugins.config import PluginConfig
from .utils import HTTPClient


@contextmanager
def plugin_test_client(
    plugin: Plugin, *, settings: dict[str, object] | None = None, transport: httpx.MockTransport | None = None
) -> Iterator[TestClient]:
    """Run one plugin's subscription routes with normal application lifespan.

    Pass a transport to replace the plugin context's HTTP client with a fixture
    client. Custom clients from the plugin's own lifespan use their own fixtures.
    """
    if transport is not None:
        plugin = plugin.model_copy(update={"http_client": partial(HTTPClient, transport=transport)})
    config = PluginConfig(modules=("test_plugin",), settings={"test_plugin": settings or {}})
    with TestClient(create_app([plugin], config=config)) as client:
        yield client
