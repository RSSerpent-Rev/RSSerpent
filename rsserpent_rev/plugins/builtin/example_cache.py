from ...models import Entry, Feed
from ...utils import cached

count = 0
path = "/_/example/cache"


@cached
async def provider() -> Feed:
    # """Define a basic example data provider function with `@cached`."""
    """Define a basic example data provider function with `@cached`.

    Returns:
        Feed: The subscription data.
    """

    global count
    count += 1
    return Feed(
        title=f"Example {count}",
        link="https://example.com",
        description="An example rsserpent plugin.",
        entries=[Entry(title="Example Title", summary="Example Description")],
    )
