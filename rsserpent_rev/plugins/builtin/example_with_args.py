from typing import Any

from starlette.exceptions import HTTPException

path = "/_/example/{n:int}"
MAX_EXAMPLE_ITEMS = 1000


async def provider(n: int) -> dict[str, Any]:
    # """Define a example data provider function with arguments."""
    """Define a example data provider function with arguments.

    Args:
        n (int): The number of items to generate.

    Returns:
        Dict[str, Any]: A dictionary containing the feed data.
    """

    if n > MAX_EXAMPLE_ITEMS:
        raise HTTPException(400, f"The example supports at most {MAX_EXAMPLE_ITEMS} items")
    return {
        "title": "Example",
        "link": "https://example.com",
        "description": "An example rsserpent plugin.",
        "id": "example",
        "items": [
            {
                "title": f"Example Title {i}",
                "description": f"Example Description {i}",
                "id": i,
                "categories": [{"name": f"example{i % 2}"}],
            }
            for i in range(1, n + 1)
        ],
    }
