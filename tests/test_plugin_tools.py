import sys
from pathlib import Path
from types import ModuleType
from typing import Literal
from xml.etree import ElementTree

import httpx
import pytest
from pydantic import BaseModel, Field

from rsserpent_rev import cli
from rsserpent_rev.models import Entry, Feed, FeedRoute, Plugin
from rsserpent_rev.testing import plugin_test_client
from rsserpent_rev.utils import get_plugin_context


class Parameters(BaseModel):
    board: Literal["public"]


class Settings(BaseModel):
    title: str = Field(min_length=1)


def sample_plugin() -> Plugin:
    async def provider(board: str) -> Feed:
        context = get_plugin_context()
        assert isinstance(context.settings, Settings) and context.http is not None
        response = await context.http.get_json("https://example.org/items", params={"board": board}, timeout=2)
        return Feed(
            title=context.settings.title,
            description="Entries",
            link="https://example.org/",
            entries=[Entry(title=item) for item in response],
        )

    return Plugin.model_validate(
        {
            "name": "rsserpent-plugin-fixture",
            "author": {"name": "Author", "email": "author@example.org", "link": "https://example.org/"},
            "repository": "https://example.org/",
            "prefix": "/fixture",
            "routers": {"/fixture": FeedRoute(provider, Parameters)},
            "settings_model": Settings,
            "http_client": True,
        }
    )


def test_test_client_runs_real_routes() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.params["board"] == "public" and request.extensions["timeout"]["read"] == 2
        return httpx.Response(200, json=["Fixture item"])

    with plugin_test_client(
        sample_plugin(), settings={"title": "Fixture"}, transport=httpx.MockTransport(respond)
    ) as client:
        rss = ElementTree.fromstring(client.get("/fixture.rss?board=public").content)
        atom = ElementTree.fromstring(client.get("/fixture.atom?board=public").content)
        assert rss.findtext("./channel/item/title") == "Fixture item"
        assert atom.findtext("{*}entry/{*}title") == "Fixture item"

    for upstream, expected in ((httpx.Response(200, json=[]), 200), (httpx.Response(503), 502)):
        with plugin_test_client(
            sample_plugin(),
            settings={"title": "Fixture"},
            transport=httpx.MockTransport(lambda request, response=upstream: response),
        ) as client:
            response = client.get("/fixture.rss?board=public")
            assert response.status_code == expected
            if expected == 200:
                assert ElementTree.fromstring(response.content).find("./channel/item") is None


@pytest.mark.parametrize("mode", ["valid", "example", "conflict", "settings", "missing"])
def test_check_reuses_application_setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    mode: str,
) -> None:
    def forbid() -> None:
        pytest.fail("The configuration check started a plugin resource.")

    base = sample_plugin().model_copy(update={"http_client": forbid, "lifespan": forbid})
    match mode:
        case "example":
            base.route_docs["/fixture"] = {
                "summary": "Example",
                "examples": [{"label": "Bad", "query": {"board": "wrong"}}],
            }
        case "conflict":
            base.routers["/all_routes"] = base.routers["/fixture"]
    module = ModuleType("fixture_plugin")
    module.__dict__["plugin"] = base
    if mode != "missing":
        monkeypatch.setitem(sys.modules, module.__name__, module)
    config = tmp_path / "rsserpent.toml"
    title = "" if mode == "settings" else "Fixture"
    config.write_text(
        'plugins = ["fixture_plugin"]\nplugin_requirements = ["uninstalled-fixture-package"]\n'
        f'[plugin_settings.fixture_plugin]\ntitle = "{title}"\n'
    )
    monkeypatch.setattr(sys, "argv", ["rsserpent", "check", "--config", str(config)])
    if mode == "valid":
        cli.main()
        assert "Checked 1 plugins and 1 feed routes." in capsys.readouterr().out
    else:
        with pytest.raises(SystemExit) as stopped:
            cli.main()
        assert stopped.value.code == 1
        content = capsys.readouterr().err + caplog.text
        clue = {
            "example": "Invalid parameter: board",
            "conflict": "conflicts with",
            "settings": "title (invalid)",
            "missing": "Cannot import plugin fixture_plugin",
        }[mode]
        assert clue in content
