import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel, field_validator
from starlette.applications import Starlette
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from rsserpent_rev.main import create_app
from rsserpent_rev.models import Feed, Plugin
from rsserpent_rev.plugins.builtin import plugin as example
from rsserpent_rev.plugins.config import PluginLoadError, read_config
from rsserpent_rev.utils import HTTPClient, cached, get_plugin_context
from rsserpent_rev.utils.provider import provider_resource


class Settings(BaseModel):
    title: str
    limit: int = 3

    @field_validator("title")
    @classmethod
    def forbid_long_titles(cls, value: str) -> str:
        if len(value) > 20:
            raise ValueError(value)
        return value


def test_plugin_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def provider() -> Feed:
        context = get_plugin_context()
        settings = context.settings
        assert isinstance(settings, Settings)
        assert settings.limit == 3
        assert context.logger.name.endswith(example.name)
        return {"title": settings.title, "link": "https://example.net", "description": "Fixture"}

    plugin = example.model_copy(update={"routers": {"/_/context": provider}, "settings_model": Settings})
    path = tmp_path / "rsserpent.toml"
    path.write_text(
        'plugins = ["demo.plugin"]\n'
        '[plugin_settings."demo.plugin"]\ntitle = "TOML title"\n'
        '[plugin_env."demo.plugin"]\ntitle = "RSS_TEST_TITLE"\n'
    )
    monkeypatch.setenv("RSS_TEST_TITLE", "From environment")
    with TestClient(create_app([plugin], config=read_config(path))) as client:
        assert "From environment" in client.get("/_/context").text
        assert "From environment" not in client.get("/all_routes").text
        assert "TOML title" not in client.get("/all_routes").text

    secret = "private_configuration_value"
    monkeypatch.setenv("RSS_TEST_TITLE", secret)
    with pytest.raises(PluginLoadError, match=r"demo.plugin: title \(invalid\)") as caught:
        create_app([plugin], config=read_config(path))
    assert secret not in str(caught.value)
    assert caught.value.__suppress_context__
    monkeypatch.delenv("RSS_TEST_TITLE")
    with pytest.raises(PluginLoadError, match="RSS_TEST_TITLE"):
        create_app([plugin], config=read_config(path))

    path.write_text('plugins = ["demo.plugin"]\n[plugin_settings."demo.plugin"]\ntitle="Entry"\nextra="private"\n')
    with pytest.raises(PluginLoadError, match=r"extra \(unknown field\)") as caught:
        create_app([plugin], config=read_config(path))
    assert "private" not in str(caught.value)
    with pytest.raises(RuntimeError, match="while a feed provider"):
        get_plugin_context()


@pytest.mark.parametrize("key", ["plugin_settings", "plugin_env"])
def test_settings_tables_require_configured_modules(tmp_path: Path, key: str) -> None:
    path = tmp_path / "rsserpent.toml"
    path.write_text(f'plugins = ["demo.plugin"]\n[{key}."other.plugin"]\nfield = "secret_unused_setting_test_value"\n')
    with pytest.raises(PluginLoadError, match="unconfigured module") as caught:
        read_config(path)
    assert "secret_unused_setting_test_value" not in str(caught.value)


def test_reuses_existing_lifespan_client() -> None:
    clients = []

    @asynccontextmanager
    async def resources() -> AsyncIterator[HTTPClient]:
        async with HTTPClient(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as http:
            clients.append(http)
            yield http

    async def provider() -> Feed:
        assert get_plugin_context().http is provider_resource.get() is clients[0]
        return {"title": "Fixture", "link": "https://example.net", "description": "Fixture"}

    plugin = example.model_copy(
        update={"routers": {"/_/context": provider}, "http_client": True, "lifespan": resources}
    )
    with TestClient(create_app([plugin])) as client:
        assert client.get("/_/context").status_code == 200
        assert client.get("/_/context.atom").status_code == 200
    assert len(clients) == 1 and clients[0].is_closed


def test_closes_started_clients_when_startup_fails() -> None:
    clients = []

    @asynccontextmanager
    async def pool() -> AsyncIterator[HTTPClient]:
        async with HTTPClient() as http:
            clients.append(http)
            yield http

    def fail() -> AsyncIterator[HTTPClient]:
        pytest.fail("Failed to open pool")

    first = example.model_copy(update={"http_client": pool})
    disabled = example.model_copy(update={"enabled": lambda: False, "http_client": fail})
    second = example.model_copy(
        update={
            "name": "rsserpent-plugin-second",
            "routers": {"/second": next(iter(example.routers.values()))},
            "http_client": fail,
        }
    )
    with (
        pytest.raises(pytest.fail.Exception, match="Failed to open pool"),
        TestClient(create_app([first, disabled, second])),
    ):
        pytest.fail("Unexpected successful startup")
    assert len(clients) == 1 and clients[0].is_closed


async def test_cache_isolates_concurrent_calls_by_app_and_plugin() -> None:
    tags = ("first", "second", "other")
    calls: list[str] = []
    ready = asyncio.Event()
    release = asyncio.Event()

    @cached
    async def provider() -> Feed:
        http = get_plugin_context().http
        assert http is not None
        data = await http.get_json("https://example.net/")
        return {"title": data["title"], "link": "https://example.net", "description": "Fixture"}

    def plugin(tag: str, path: str) -> Plugin:
        async def respond(request: httpx.Request) -> httpx.Response:
            calls.append(tag)
            if set(calls) == set(tags):
                ready.set()
            await release.wait()
            return httpx.Response(200, json={"title": tag})

        return example.model_copy(
            update={
                "name": f"rsserpent-plugin-{tag if tag != 'other' else 'first'}",
                "routers": {path: provider},
                "http_client": lambda: HTTPClient(transport=httpx.MockTransport(respond)),
            }
        )

    async def client(stack: AsyncExitStack, app: Starlette) -> httpx.AsyncClient:
        lifespan = await stack.enter_async_context(app.router.lifespan_context(app))

        async def with_state(scope: Scope, receive: Receive, send: Send) -> None:
            scope["state"] = lifespan
            await app(scope, receive, send)

        return await stack.enter_async_context(
            httpx.AsyncClient(transport=httpx.ASGITransport(app=with_state), base_url="http://test")
        )

    async with AsyncExitStack() as stack:
        first = await client(stack, create_app([plugin("first", "/feed"), plugin("second", "/second")]))
        second = await client(stack, create_app([plugin("other", "/feed")]))
        async with asyncio.TaskGroup() as group:
            responses = [
                group.create_task(first.get("/feed")),
                group.create_task(first.get("/feed.atom")),
                group.create_task(first.get("/second")),
                group.create_task(second.get("/feed")),
            ]
            try:
                await asyncio.wait_for(ready.wait(), timeout=2)
            finally:
                release.set()
        assert sorted(calls) == sorted(tags)
        for response, tag in zip(responses, ("first", *tags), strict=True):
            assert f"<title>{tag}</title>" in response.result().text
        assert "<title>other</title>" in (await second.get("/feed.atom")).text
        assert "<title>second</title>" in (await first.get("/second")).text
        assert len(calls) == 3
