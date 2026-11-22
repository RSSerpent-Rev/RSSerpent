from collections.abc import Iterator
from pathlib import Path

import pytest
import regex
from starlette.testclient import TestClient

from rsserpent_rev.main import create_app
from rsserpent_rev.utils import feed


def test_examples_opt_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("RSSERPENT_CONFIG", raising=False)
    monkeypatch.setenv("RSSERPENT_ENABLE_EXAMPLES", "true")
    assert TestClient(create_app()).get("/_/example").status_code == 404
    config = tmp_path / "rsserpent.toml"
    config.write_text('plugins = ["rsserpent_rev.plugins.builtin"]\n')
    monkeypatch.setenv("RSSERPENT_CONFIG", str(config))
    enabled = TestClient(create_app())
    assert enabled.get("/_/example").status_code == 200
    assert enabled.get("/_/example/1001").status_code == 400


@pytest.mark.parametrize("pattern", ["[", "a" * 513])
def test_invalid_pattern(client: TestClient, pattern: str) -> None:
    assert client.get("/_/example", params={"title_include": pattern}).status_code == 400


def test_filter_budget(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    ticks: Iterator[float] = iter([0, 1])
    monkeypatch.setattr(feed, "time", type("Clock", (), {"monotonic": lambda: next(ticks)}))
    response = client.get("/_/example/10", params={"title_include": "Example"})
    assert response.status_code == 400
    assert "time budget" in response.text


def test_regex_engine_enforces_timeout() -> None:
    with pytest.raises(TimeoutError):
        regex.compile("Example").search("Example", timeout=0)
