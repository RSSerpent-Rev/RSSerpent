from typing import Any
from xml.etree import ElementTree

import httpx
import pytest
from starlette.exceptions import HTTPException
from starlette.testclient import TestClient

from rsserpent_rev import main
from rsserpent_rev.models import Feed, ProviderFn
from rsserpent_rev.plugins.builtin import plugin as builtin_plugin
from rsserpent_rev.utils import fetch_data


@pytest.fixture
def error_client() -> TestClient:
    return TestClient(main.create_app([builtin_plugin]), raise_server_exceptions=False)


def test_valid_feed(error_client: TestClient) -> None:
    response = error_client.get("/_/example.rss")
    assert response.status_code == 200
    assert ElementTree.fromstring(response.content).tag == "rss"


def test_invalid_query(error_client: TestClient) -> None:
    response = error_client.get("/_/example", params={"limit": "unknown"})
    assert response.status_code == 400
    assert "unknown" not in response.text


@pytest.mark.parametrize("query", [{"amount": "unknown"}, {}])
def test_provider_bad_input(error_client: TestClient, monkeypatch: pytest.MonkeyPatch, query: dict[str, str]) -> None:
    async def provider(amount: int) -> dict[str, int]:
        pytest.fail(f"provider called with {amount}")

    async def dispatch(_provider: ProviderFn, path_params: dict[str, Any], query_params: dict[str, str]) -> Feed:
        return await fetch_data(provider, path_params, query_params)

    monkeypatch.setattr(main, "fetch_data", dispatch)
    assert error_client.get("/_/example", params=query).status_code == 400


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (HTTPException(status_code=404, detail="Not found"), 404),
        (httpx.ConnectError("internal upstream host"), 502),
        (httpx.ReadTimeout("internal upstream host"), 504),
        (ValueError("internal provider failure"), 500),
    ],
)
def test_provider_error(
    error_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    status: int,
) -> None:
    async def fail(*_args: Any) -> Feed:
        raise error

    monkeypatch.setattr(main, "fetch_data", fail)
    response = error_client.get("/_/example")
    assert response.status_code == status
    assert "internal upstream host" not in response.text
    assert "internal provider failure" not in response.text
    assert "Traceback" not in response.text
    if status == 500:
        assert "internal provider failure" in caplog.text
        assert "Traceback" in caplog.text


def test_invalid_provider_output(error_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fetch(*_args: Any) -> Feed:
        return {"title": "Invalid"}

    monkeypatch.setattr(main, "fetch_data", fetch)
    assert error_client.get("/_/example").status_code == 500


@pytest.mark.parametrize("value", ["0", "false", ""])
def test_disabled_debug(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("DEBUG", value)
    assert not main.create_app([]).debug
