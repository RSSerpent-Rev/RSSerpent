from typing import Any, Dict
import feedparser
from ...utils import cached

path = "/_/proxy/{url:path}"


@cached
async def provider(url: str) -> Dict[str, Any]:
    """Return the latest news from the given RSS feed."""
    feed = feedparser.parse(url)
    items = list(map(lambda x: {
        "title": x.title,
        "description": x.summary,
        "link": x.link,
        "pub_date": x.published,
    }, feed.entries))
    return {
        "title": feed.feed.title,
        "link": feed.feed.link,
        "description": feed.feed.description,
        "items": items,
    }
