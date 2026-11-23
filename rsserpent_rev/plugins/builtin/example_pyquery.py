from ...models import Entry, Feed
from ...utils import HTTPClient

path = "/_/example/pyquery"


async def provider() -> Feed:
    """Define a basic example data provider function."""
    async with HTTPClient() as client:
        dom = await client.get_html("https://httpbin.org/html")
    return Feed(
        title="Example",
        link="https://example.com",
        description="An example rsserpent plugin.",
        entries=[Entry(title=dom("h1").text(), summary=dom("div > p").text())],
    )
