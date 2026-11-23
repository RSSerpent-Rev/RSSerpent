from starlette.exceptions import HTTPException

from ...models import Entry, Feed

path = "/_/example/{n:int}"
MAX_EXAMPLE_ITEMS = 1000


async def provider(n: int) -> Feed:
    # """Define a example data provider function with arguments."""
    """Define a example data provider function with arguments.

    Args:
        n (int): The number of items to generate.

    Returns:
        Feed: The subscription data.
    """

    if n > MAX_EXAMPLE_ITEMS:
        raise HTTPException(400, f"The example supports at most {MAX_EXAMPLE_ITEMS} items")
    return Feed(
        title="Example",
        link="https://example.com",
        description="An example rsserpent plugin.",
        id="urn:rsserpent:example",
        entries=[
            Entry(
                title=f"Example Title {i}",
                summary=f"Example Description {i}",
                id=str(i),
                categories=[f"example{i % 2}"],
            )
            for i in range(1, n + 1)
        ],
    )
