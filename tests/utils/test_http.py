import httpx
import pytest

from rsserpent_rev.utils.http import Browser, HTTPClient


@pytest.mark.live
async def test_browser() -> None:
    """Test if the `Browser` context manager works properly."""
    async with Browser() as browser:
        await browser.goto("https://httpbin.org/html")
        assert "Herman Melville - Moby-Dick" in await browser.content()


async def test_http_client() -> None:
    async def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["Referer"] == "https://example.org"
        assert request.headers["Host"] == "example.org"
        return httpx.Response(200, json={"title": "Fixture"})

    async with HTTPClient(transport=httpx.MockTransport(respond)) as client:
        response = await client.get("https://example.org/feed")
    assert response.json() == {"title": "Fixture"}
