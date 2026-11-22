from importlib.metadata import EntryPoint

import pytest
from starlette.testclient import TestClient

from rsserpent_rev.main import create_app
from rsserpent_rev.models import Feed, Plugin
from rsserpent_rev.plugins import externals
from rsserpent_rev.plugins.builtin import plugin as example
from rsserpent_rev.plugins.externals import PluginLoadError


async def provider() -> Feed:
    return {"title": "Example", "link": "https://example.org", "description": "Test feed"}


def make_plugin(name: str, path: str) -> Plugin:
    return example.model_copy(update={"name": name, "routers": {path: provider}})


def test_discovery_uses_plugin_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    first = EntryPoint("legacy", "test.first:plugin", "rsserpent.plugin")
    second = EntryPoint("legacy", "test.second:plugin", "rsserpent.plugin")
    objects = {
        first: make_plugin("rsserpent-plugin-first", "/first"),
        second: make_plugin("rsserpent-plugin-second", "/second"),
    }
    monkeypatch.setattr(externals, "entry_points", lambda *, group: [second, first] if group == first.group else [])
    monkeypatch.setattr(EntryPoint, "load", lambda entry: objects[entry])
    monkeypatch.delenv("RSSERPENT_ENABLE_EXAMPLES", raising=False)

    app = create_app()
    assert app.state.plugins == [objects[first], objects[second]]
    with TestClient(app) as client:
        assert client.get("/first").status_code == 200
        assert client.get("/second.atom").status_code == 200
        assert client.get("/_/example").status_code == 404

    objects[second] = make_plugin(objects[first].name, "/second")
    with pytest.raises(PluginLoadError, match=r"Duplicate plugin name.*test\.first:plugin.*test\.second:plugin"):
        create_app()


def test_rejects_non_plugin_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = EntryPoint("broken", "test.broken:plugin", "rsserpent.plugin")
    monkeypatch.setattr(externals, "entry_points", lambda **_: [entry])
    monkeypatch.setattr(EntryPoint, "load", lambda _: object())
    with pytest.raises(PluginLoadError, match=r"Expected a Plugin instance.*test\.broken:plugin"):
        create_app()


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
