from typing import Any

path = "/_/example"


async def provider() -> dict[str, Any]:
    """Define a basic example data provider function."""
    return {
        "title": "Example",
        "link": "https://example.com",
        "description": "An example rsserpent plugin.",
        "items": [{"title": "Example Title", "description": "Example Description", "link": "https://example.com"}],
    }
