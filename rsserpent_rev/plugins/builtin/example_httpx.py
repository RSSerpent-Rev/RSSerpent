from ...models import Entry, Feed
from ...utils import HTTPClient

path = "/_/example/httpx"


async def provider() -> Feed:
    """Define a basic example data provider function."""
    async with HTTPClient() as client:
        data = await client.get_json("https://httpbin.org/ip")
        ip = data["origin"]
    return Feed(
        title=f"{ip}",
        link="https://example.com",
        description="An example rsserpent plugin.",
        entries=[Entry(title="Example Title", summary="Example Description")],
    )
