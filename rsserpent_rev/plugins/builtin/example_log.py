from rsserpent_rev.log import get_logger

from ...models import Entry, Feed

path = "/_/example/log"

logger = get_logger()


async def provider() -> Feed:
    """Define a basic example data provider function."""
    logger.info("Example plugin is called.")
    return Feed(
        title="Example",
        link="https://example.com",
        description="An example rsserpent plugin.",
        entries=[Entry(title="Example Title", summary="Example Description")],
    )
