import re

import pytest
from hypothesis import given, settings
from hypothesis.strategies import integers
from pydantic import IPvAnyAddress
from starlette.testclient import TestClient

from rsserpent_rev.main import ATOM_MIMETYPE, RSS_MIMETYPE
from rsserpent_rev.plugins.builtin import example_cache
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


def test_example_httpx(client: TestClient) -> None:
    """Test the `/_/example/httpx` route."""
    response = client.get("/_/example/httpx")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE

    match = re.search("<title>(.*)</title>", response.text)
    assert match is not None
    assert IPvAnyAddress._validate(match.group(1)) is not None


def test_example_playwright(client: TestClient) -> None:
    """Test the `/_/example/playwright` route."""
    response = client.get("/_/example/playwright")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == RSS_MIMETYPE
    assert "<title>Herman Melville - Moby-Dick</title>" in response.text


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
