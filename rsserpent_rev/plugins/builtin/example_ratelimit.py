from ...models import Entry, Feed
from ...utils import ratelimit

path = "/_/example/ratelimit"


@ratelimit(calls=1)
async def provider() -> Feed:
    """Define a basic example data provider function with rate limit."""
    return Feed(
        title="Example",
        link="https://example.com",
        description="An example rsserpent plugin.",
        entries=[Entry(title="Example Title", summary="Example Description")],
    )
