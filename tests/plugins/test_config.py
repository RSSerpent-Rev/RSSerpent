import os
import sys
from functools import partial, update_wrapper, wraps
from inspect import Parameter, Signature
from pathlib import Path
from types import ModuleType
from urllib.parse import urlencode

import pytest
from starlette.testclient import TestClient

from rsserpent_rev import __main__ as launcher
from rsserpent_rev import main
from rsserpent_rev.main import ATOM_MIMETYPE, RSS_MIMETYPE, create_app
from rsserpent_rev.models import Feed, Plugin, ProviderFn
from rsserpent_rev.plugins.builtin import plugin as example
from rsserpent_rev.plugins.config import PluginConfig, PluginLoadError, load_plugins, read_config


async def provider() -> Feed:
    return {"title": "Example", "link": "https://example.org", "description": "Test feed"}


def make_plugin(name: str, path: str) -> Plugin:
    return example.model_copy(update={"name": name, "routers": {path: provider}})


@pytest.fixture
def config(tmp_path: Path) -> Path:
    return tmp_path / "rsserpent.toml"


def test_config_selects_modules_in_order(config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("first", "second", "unlisted"):
        module = ModuleType(name)
        module.__dict__["plugin"] = make_plugin(f"rsserpent-plugin-{name}", f"/{name}")
        monkeypatch.setitem(sys.modules, name, module)

    config.write_text('plugins = ["second", "first"]')
    modules = read_config(config).modules
    app = create_app(load_plugins(modules, config), sources=modules)
    assert [plugin.name for plugin in app.state.plugins] == ["rsserpent-plugin-second", "rsserpent-plugin-first"]
    with TestClient(app) as client:
        assert client.get("/first").status_code == 200
        assert client.get("/second.atom").status_code == 200
        assert client.get("/unlisted").status_code == 404
        catalog = client.get("/all_routes").text
        assert "/first.rss" in catalog
        assert "/second.atom" in catalog
        assert "/unlisted" not in catalog

    sys.modules["second"].__dict__["plugin"] = make_plugin("rsserpent-plugin-first", "/second")
    with pytest.raises(PluginLoadError, match=r"Duplicate plugin name.*second.*first"):
        create_app(load_plugins(modules, config), sources=modules)


@pytest.mark.parametrize("content", ["", "plugins = []"])
def test_empty_configuration(config: Path, content: str) -> None:
    config.write_text(content)
    assert read_config(config) == PluginConfig()


@pytest.mark.parametrize(
    ("content", "error"),
    [
        (None, "Cannot read plugin configuration"),
        ("plugins = [", "Cannot read plugin configuration"),
        ("plugins = 1", "must be an array"),
        ("plugins = [true]", "Invalid plugin module"),
        ('plugins = ["example:plugin"]', "Invalid plugin module"),
        ('plugins = ["missing_plugin", "missing_plugin"]', "Duplicate plugin module"),
        ('plugins = ["missing_plugin"]', "Cannot import plugin.*missing_plugin"),
        ('plugins = ["types"]', "Expected types.*to export a Plugin"),
        ("plugin_requirements = true", "plugin_requirements must be an array"),
        ("plugin_requirements = [1]", "plugin_requirements must be an array"),
        ('plugin_requirements = [" -r /tmp/other.txt"]', "plugin_requirements must be an array"),
        ('plugin_requirements = ["--index-url=https://example.org"]', "plugin_requirements must be an array"),
        ('plugin_requirements = ["first\\nsecond"]', "plugin_requirements must be an array"),
    ],
)
def test_rejects_invalid_configuration(config: Path, content: str | None, error: str) -> None:
    if content is not None:
        config.write_text(content)
    with pytest.raises(PluginLoadError, match=error) as caught:
        load_plugins(read_config(config).modules, config)
    assert str(config) in str(caught.value)


def test_import_has_no_application_instance() -> None:
    assert not hasattr(main, "app")


def test_container_passes_modules_from_the_same_config(config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config.write_text('plugins = ["first"]\nplugin_requirements = ["first-dist==1.2.3"]\n')
    interpreter = config.parent / "venv" / "bin" / "python"

    def prepare(requirements: tuple[str, ...]) -> Path:
        assert requirements == ("first-dist==1.2.3",)
        config.write_text('plugins = ["second"]\n')
        return interpreter

    def execv(program: Path, args: list[str]) -> None:
        assert program == interpreter
        assert args == [str(interpreter), "-m", "rsserpent_rev._server", "127.0.0.1", "8000", "first"]
        raise SystemExit(0)

    monkeypatch.setattr(launcher, "prepare_plugin_environment", prepare)
    monkeypatch.setattr(os, "execv", execv)
    monkeypatch.setattr(sys, "argv", ["rsserpent", "--container", "--config", str(config)])
    monkeypatch.setenv("VIRTUAL_ENV", "test")
    monkeypatch.setenv("PATH", "test")
    with pytest.raises(SystemExit) as stopped:
        launcher.main()
    assert stopped.value.code == 0


def test_rejects_equal_route_shapes() -> None:
    first = make_plugin("rsserpent-plugin-first", "/feed/{path}")
    second = make_plugin("rsserpent-plugin-second", "/feed/{name:str}")
    with pytest.raises(PluginLoadError, match=r"second.*first"):
        create_app([first, second])


def test_rejects_a_route_that_replaces_a_core_page() -> None:
    plugin = make_plugin("rsserpent-plugin-conflicting", "/all_routes")
    with pytest.raises(PluginLoadError, match=r"/all_routes.*RSSerpent core"):
        create_app([plugin])


def test_legacy_proxy_remains_disabled() -> None:
    proxy = make_plugin("rsserpent-plugin-rss-proxy", "/proxy")
    app = create_app([proxy])
    assert not app.state.plugins
    assert TestClient(app).get("/proxy").status_code == 404


def test_route_catalog_omits_disabled_plugins_and_describes_catch_all_routes() -> None:
    proxy = make_plugin("rsserpent-plugin-proxy", "/proxy/{url:path}")
    disabled = make_plugin("rsserpent-plugin-disabled", "/disabled").model_copy(update={"enabled": lambda: False})
    response = TestClient(create_app([proxy, disabled])).get("/all_routes")
    assert response.status_code == 200
    assert "<code>/proxy/{url:path}</code>" in response.text
    assert "?format=atom" in response.text
    assert "/proxy/{url:path}.atom" not in response.text
    assert "/disabled" not in response.text


def test_route_documentation_examples(caplog: pytest.LogCaptureFixture) -> None:
    calls = []

    async def documented(user_id: int, search: str, token: str = "private-default") -> Feed:
        calls.append((user_id, search, token))
        return await provider()

    path = "/docs-feed/{user_id:int}"
    plugin = example.model_copy(
        update={
            "routers": {path: documented},
            "route_docs": {
                path: {
                    "summary": "<Featured feed>",
                    "description": "Recent posts.",
                    "parameters": {"user_id": "Account ID", "search": "Search phrase"},
                    "examples": [
                        {"label": "Sample search", "path": {"user_id": "17"}, "query": {"search": "A & B#"}},
                        {"label": "Missing query", "path": {"user_id": "17"}},
                        {"label": "Bad path value", "path": {"user_id": "text"}, "query": {"search": "A"}},
                        {"label": "Unexpected query", "path": {"user_id": "17"}, "query": {"extra": "A"}},
                    ],
                },
            },
        },
    )
    with TestClient(create_app([plugin]), root_path="/feeds") as client:
        page = client.get("/feeds/all_routes").text
        assert "&lt;Featured feed&gt;" in page and "Recent posts." in page
        assert "Account ID" in page and "Search phrase" in page
        assert "Path parameters" in page and "Query parameters" in page
        assert "private-default" not in page
        assert "Sample search" in page
        assert "Missing query" not in page and "Bad path value" not in page and "Unexpected query" not in page
        assert "route documentation example 2" in caplog.text
        assert not calls
        for suffix, mime in (("rss", RSS_MIMETYPE), ("atom", ATOM_MIMETYPE)):
            url = f"/feeds/docs-feed/17.{suffix}?{urlencode({'search': 'A & B#'})}"
            assert f'href="http://testserver{url}"' in page
            assert client.get(url).headers["content-type"] == mime
        assert calls == [(17, "A & B#", "private-default")] * 2


def test_catch_all_example_preserves_upstream_query() -> None:
    seen = []

    async def proxy_feed(url: str) -> Feed:
        seen.append(url)
        return await provider()

    path = "/documented-proxy/{url:path}"
    upstream = "https://example.org/feed?a=1&b=two"
    plugin = example.model_copy(
        update={
            "routers": {path: proxy_feed},
            "route_docs": {
                path: {
                    "summary": "Local test feed",
                    "examples": [{"label": "Upstream sample", "path": {"url": upstream}}],
                },
            },
        },
    )
    with TestClient(create_app([plugin])) as client:
        page = client.get("/all_routes").text
        assert not seen
        link = "/documented-proxy/https%3A//example.org/feed%3Fa%3D1%26b%3Dtwo"
        assert f'href="http://testserver{link}?format=atom"' in page
        assert client.get(f"{link}?format=atom").headers["content-type"] == ATOM_MIMETYPE
        assert seen == [upstream]


def test_example_must_match_the_registered_route() -> None:
    path = "/documents/{item:uuid}"
    plugin = example.model_copy(
        update={
            "routers": {path: provider},
            "route_docs": {
                path: {
                    "summary": "Document updates",
                    "examples": [{"label": "Invalid UUID", "path": {"item": "not-a-uuid"}}],
                },
            },
        },
    )
    page = TestClient(create_app([plugin])).get("/all_routes").text
    assert "Document updates" in page
    assert "Invalid UUID" not in page


@pytest.mark.parametrize("wrapped", [False, True])
def test_route_documentation_does_not_evaluate_annotations(wrapped: bool) -> None:
    calls = []

    def annotation() -> type[str]:
        calls.append("evaluated")
        return str

    async def deferred(prefix: annotation(), query: annotation(), optional: int = 1) -> annotation():  # type: ignore[valid-type]
        pytest.fail("The route catalog invoked the provider")

    @wraps(deferred)
    async def decorated(*args: str, **kwargs: int) -> Feed:
        pytest.fail("The route catalog invoked the provider wrapper")

    plugin = example.model_copy(update={"routers": {"/deferred": partial(decorated if wrapped else deferred, "bound")}})
    page = TestClient(create_app([plugin])).get("/all_routes")
    assert page.status_code == 200
    assert "<code>query</code> &middot; required" in page.text
    assert "<code>optional</code> &middot; optional" in page.text
    assert "<code>prefix</code>" not in page.text
    assert calls == []


@pytest.mark.parametrize("kind", ["declared", "wrapped_partial"])
def test_documentation_uses_the_runtime_signature(kind: str) -> None:
    async def keyword_provider(**fields: str) -> Feed:
        assert fields["query"] == "example"
        return await provider()

    async def explicit_provider(query: str) -> Feed:
        assert query == "example"
        return await provider()

    target: ProviderFn
    if kind == "declared":
        keyword_provider.__dict__["__signature__"] = Signature(
            [Parameter("query", Parameter.KEYWORD_ONLY, annotation=str)]
        )
        target = partial(keyword_provider)
    else:
        target = update_wrapper(partial(explicit_provider, query="bound"), explicit_provider)

    path = "/signature"
    plugin = example.model_copy(
        update={
            "routers": {path: target},
            "route_docs": {
                path: {
                    "summary": "Signature sample",
                    "examples": [
                        {"label": "Complete example", "query": {"query": "example"}},
                        {"label": "Missing required field"},
                    ],
                },
            },
        },
    )
    with TestClient(create_app([plugin])) as client:
        page = client.get("/all_routes").text
        assert "<code>query</code> &middot; required" in page
        assert "Missing required field" not in page
        assert 'href="http://testserver/signature.rss?query=example"' in page
        assert client.get("/signature.rss?query=example").status_code == 200
        assert client.get("/signature.rss").status_code == 400
