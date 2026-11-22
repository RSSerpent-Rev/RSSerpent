import sys
from pathlib import Path
from types import ModuleType

import pytest
from starlette.testclient import TestClient

from rsserpent_rev.main import create_app
from rsserpent_rev.models import Feed, Plugin
from rsserpent_rev.plugins.builtin import plugin as example
from rsserpent_rev.plugins.config import PluginLoadError


async def provider() -> Feed:
    return {"title": "Example", "link": "https://example.org", "description": "Test feed"}


def make_plugin(name: str, path: str) -> Plugin:
    return example.model_copy(update={"name": name, "routers": {path: provider}})


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "rsserpent.toml"
    monkeypatch.setenv("RSSERPENT_CONFIG", str(path))
    return path


def test_config_selects_modules_in_order(config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("first", "second", "unlisted"):
        module = ModuleType(name)
        module.__dict__["plugin"] = make_plugin(f"rsserpent-plugin-{name}", f"/{name}")
        monkeypatch.setitem(sys.modules, name, module)

    config.write_text('plugins = ["second", "first"]')
    app = create_app()
    assert [plugin.name for plugin in app.state.plugins] == ["rsserpent-plugin-second", "rsserpent-plugin-first"]
    with TestClient(app) as client:
        assert client.get("/first").status_code == 200
        assert client.get("/second.atom").status_code == 200
        assert client.get("/unlisted").status_code == 404

    sys.modules["second"].__dict__["plugin"] = make_plugin("rsserpent-plugin-first", "/second")
    with pytest.raises(PluginLoadError, match=r"Duplicate plugin name.*second.*first"):
        create_app()


@pytest.mark.parametrize("content", ["", "plugins = []"])
def test_empty_configuration(config: Path, content: str) -> None:
    config.write_text(content)
    assert not create_app().state.plugins


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
    ],
)
def test_rejects_invalid_configuration(config: Path, content: str | None, error: str) -> None:
    if content is not None:
        config.write_text(content)
    with pytest.raises(PluginLoadError, match=error) as caught:
        create_app()
    assert str(config) in str(caught.value)


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
