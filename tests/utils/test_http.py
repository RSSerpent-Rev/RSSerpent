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


async def test_content_helpers() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        match request.url.path:
            case "/json":
                assert request.url.params["q"] == "fixture"
                assert request.headers["X-Source"] == "test"
                assert request.extensions["timeout"]["read"] == 2
                return httpx.Response(200, json=["entry"])
            case "/redirect":
                return httpx.Response(302, headers={"Location": "/html"})
            case "/html":
                return httpx.Response(200, text='<article><a href="post">Entry</a></article>')
            case "/cached":
                return httpx.Response(304)
            case _:
                return httpx.Response(200, content=b"stream")

    async with HTTPClient(transport=httpx.MockTransport(respond)) as client:
        assert await client.get_json(
            "https://example.org/json", params={"q": "fixture"}, headers={"X-Source": "test"}, timeout=2
        ) == ["entry"]
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_html("https://example.org/redirect")
        dom = await client.get_html("https://example.org/redirect", follow_redirects=True)
        assert dom("article a").attr("href") == "post"
        assert (await client.get("https://example.org/cached")).status_code == 304
        async with client.stream("GET", "https://example.org/stream") as response:
            assert await response.aread() == b"stream"
