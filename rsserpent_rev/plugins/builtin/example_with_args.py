from typing import Any

path = "/_/example/{n:int}"


async def provider(n: int) -> dict[str, Any]:
    # """Define a example data provider function with arguments."""
    """Define a example data provider function with arguments.

    Args:
        n (int): The number of items to generate.

    Returns:
        Dict[str, Any]: A dictionary containing the feed data.
    """

    return {
        "title": "Example",
        "link": "https://example.com",
        "description": "An example rsserpent plugin.",
        "items": [{"title": f"Example Title {i}", "description": f"Example Description {i}"} for i in range(1, n + 1)],
    }
