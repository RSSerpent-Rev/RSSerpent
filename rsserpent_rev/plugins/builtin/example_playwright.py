from pyquery import PyQuery

from ...models import Entry, Feed
from ...utils import Browser

path = "/_/example/playwright"


async def provider() -> Feed:
    """Define a basic example data provider function."""
    async with Browser() as browser:
        await browser.goto("https://httpbin.org/html")
        content = await browser.content()
    dom = PyQuery(content)
    return Feed(
        title="Example",
        link="https://example.com",
        description="An example rsserpent plugin.",
        entries=[Entry(title=dom("h1").text(), summary=dom("div > p").text())],
    )
