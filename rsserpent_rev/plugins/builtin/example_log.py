from typing import Any

from rsserpent_rev.log import get_logger

path = "/_/example/log"

logger = get_logger()


async def provider() -> dict[str, Any]:
    """Define a basic example data provider function."""
    logger.info("Example plugin is called.")
    return {
        "title": "Example",
        "link": "https://example.com",
        "description": "An example rsserpent plugin.",
        "items": [{"title": "Example Title", "description": "Example Description"}],
    }
