from ...models import Entry, Feed

path = "/_/example"


async def provider() -> Feed:
    """Define a basic example data provider function."""
    return Feed(
        title="Example",
        link="https://example.com",
        description="An example rsserpent plugin.",
        entries=[Entry(title="Example Title", summary="Example Description", link="https://example.com")],
    )
