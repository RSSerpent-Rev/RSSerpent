import re
from ipaddress import ip_address
from types import ModuleType

import httpx
import pytest
from hypothesis import given, settings
from hypothesis.strategies import integers
from starlette.testclient import TestClient

from rsserpent_rev.main import ATOM_MIMETYPE, RSS_MIMETYPE, create_app
from rsserpent_rev.plugins.builtin import example_cache, example_httpx, example_pyquery
from rsserpent_rev.plugins.builtin import plugin as builtin_plugin
from rsserpent_rev.utils import HTTPClient
from rsserpent_rev.utils.cache import get_cache
from rsserpent_rev.utils.ratelimit import RateLimitError
from tests.conftest import Times


def test_example_feedgen(client: TestClient) -> None:
    """Test the `/_/example/feedgen` route."""
    response = client.get("/_/example/feedgen.atom")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == ATOM_MIMETYPE
    assert response.text.count("<entry>") == 2
    assert "<title>Some Testfeed</title>" in response.text


def test_example_log(client: TestClient) -> None:
    """Test the `/_/example` route."""
    response = client.get("/_/example/log")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 1
    assert "<title>Example</title>" in response.text


def test_example(client: TestClient) -> None:
    """Test the `/_/example` route."""
    response = client.get("/_/example")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 1
    assert "<title>Example</title>" in response.text

    response = client.get("/_/example.rss")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == 1
    assert "<title>Example</title>" in response.text

    response = client.get("/_/example.atom")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == ATOM_MIMETYPE
    assert response.text.count("<entry>") == 1
    assert "<title>Example</title>" in response.text


def test_example_cached(client: TestClient) -> None:
    """Test the `/_/example/cache` route."""
    response1 = client.get("/_/example/cache")
    assert "<title>Example 1</title>" in response1.text
    response2 = client.get("/_/example/cache")
    assert "<title>Example 1</title>" in response2.text

    cache = get_cache(example_cache.provider)
    if cache is not None:
        cache.clear()
    response3 = client.get("/_/example/cache")
    assert "<title>Example 2</title>" in response3.text


@pytest.mark.live
def test_example_httpx(client: TestClient) -> None:
    """Test the `/_/example/httpx` route."""
    response = client.get("/_/example/httpx")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE

    match = re.search("<title>(.*)</title>", response.text)
    assert match is not None
    ip_address(match.group(1))


@pytest.mark.live
def test_example_playwright(client: TestClient) -> None:
    """Test the `/_/example/playwright` route."""
    response = client.get("/_/example/playwright")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert "<title>Herman Melville - Moby-Dick</title>" in response.text


@pytest.mark.live
def test_example_pyquery(client: TestClient) -> None:
    """Test the `/_/example/pyquery` route."""
    response = client.get("/_/example/pyquery")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert "<title>Herman Melville - Moby-Dick</title>" in response.text


def test_example_ratelimit(client: TestClient) -> None:
    """Test the `/_example/ratelimit` route."""
    assert client.get("/_/example/ratelimit").status_code == 200
    with pytest.raises(RateLimitError):
        client.get("/_/example/ratelimit")


@settings(max_examples=Times.SOME)
@given(n=integers(min_value=1, max_value=10))
def test_example_with_args(client: TestClient, n: int) -> None:
    """Test the `/_/example/{n:int}` route."""
    response = client.get(f"/_/example/{n}")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert response.text.count("<item>") == n


@pytest.mark.parametrize(
    ("module", "body", "title"),
    [
        (example_httpx, '{"origin": "192.0.2.4"}', "192.0.2.4"),
        (example_pyquery, "<h1>Article</h1><div><p>Summary</p></div>", "Article"),
    ],
)
def test_content_example(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, module: ModuleType, body: str, title: str
) -> None:
    def make_client() -> HTTPClient:
        return HTTPClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body)))

    monkeypatch.setattr(module, "HTTPClient", make_client)
    for suffix in (".rss", ".atom"):
        response = client.get(module.path + suffix)
        assert response.status_code == 200
        assert f"<title>{title}</title>" in response.text


@pytest.mark.parametrize(("mode", "status"), [("decode", 502), ("status", 502), ("timeout", 504)])
def test_content_example_error(monkeypatch: pytest.MonkeyPatch, mode: str, status: int) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if mode == "timeout":
            message = "upstream timeout"
            raise httpx.ReadTimeout(message, request=request)
        return httpx.Response(503 if mode == "status" else 200, text="private response body")

    monkeypatch.setattr(example_httpx, "HTTPClient", lambda: HTTPClient(transport=httpx.MockTransport(respond)))
    with TestClient(create_app([builtin_plugin])) as client:
        response = client.get(example_httpx.path)
        assert response.status_code == status
        assert "private response body" not in response.text
