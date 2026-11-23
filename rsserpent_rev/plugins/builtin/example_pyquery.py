from typing import Any

from ...utils import HTTPClient

path = "/_/example/pyquery"


async def provider() -> dict[str, Any]:
    """Define a basic example data provider function."""
    async with HTTPClient() as client:
        dom = await client.get_html("https://httpbin.org/html")
    return {
        "title": "Example",
        "link": "https://example.com",
        "description": "An example rsserpent plugin.",
        "items": [{"title": dom("h1").text(), "description": dom("div > p").text()}],
    }
