from xml.etree import ElementTree

import arrow
from feedgen.feed import FeedGenerator
from starlette.testclient import TestClient

from rsserpent_rev.main import ATOM_MIMETYPE, RSS_MIMETYPE, create_app
from rsserpent_rev.models import Feed, ProviderFn
from rsserpent_rev.plugins.builtin import plugin
from rsserpent_rev.utils import cached


def client_for(path: str, provider: ProviderFn) -> TestClient:
    return TestClient(create_app([plugin.model_copy(update={"routers": {path: provider}})]))


def test_catchall_keeps_source_url() -> None:
    seen = []

    async def provider(url: str) -> Feed:
        seen.append(url)
        return {"title": "Example", "link": "https://example.org", "description": "Example feed"}

    client = client_for("/_/proxy/{url:path}", provider)
    rss = client.get("/_/proxy/https://example.org/news.rss%3Fpage=1")
    atom = client.get("/_/proxy/https://example.org/news.atom", params={"format": "atom"})
    assert seen == ["https://example.org/news.rss?page=1", "https://example.org/news.atom"]
    assert rss.headers["Content-Type"] == RSS_MIMETYPE
    assert ElementTree.fromstring(rss.content).tag == "rss"
    assert atom.headers["Content-Type"] == ATOM_MIMETYPE
    assert ElementTree.fromstring(atom.content).tag == "{http://www.w3.org/2005/Atom}feed"


def test_optional_model_fields() -> None:
    async def provider() -> Feed:
        return {
            "title": "Example",
            "link": "https://example.org",
            "description": "Example feed",
            "items": [{"title": "Title only"}, {"description": "Description only"}],
        }

    client = client_for("/_/optional", provider)
    response = client.get("/_/optional.rss", params={"description_exclude": "Description"})
    items = ElementTree.fromstring(response.content).findall("./channel/item")
    assert [item.findtext("title") for item in items] == ["Title only"]
    assert items[0].find("link") is None
    response = client.get("/_/optional.atom")
    assert response.status_code == 200
    assert len(ElementTree.fromstring(response.content).findall("{http://www.w3.org/2005/Atom}entry")) == 2


def test_filter_preserves_cached_source() -> None:
    feed = FeedGenerator()
    feed.title("Cached")
    feed.link(href="https://example.org")
    feed.description("Example feed")
    feed.add_entry().description("No date")
    dated = feed.add_entry()
    dated.title("Dated entry")
    dated.pubDate(arrow.get("2020-01-01T00:00:00Z").datetime)

    @cached
    async def provider() -> FeedGenerator:
        return feed

    client = client_for("/_/cached", provider)
    filtered = client.get("/_/cached", params={"date_after": "2019-01-01T00:00:00Z"})
    assert len(ElementTree.fromstring(filtered.content).findall("./channel/item")) == 1
    assert len(ElementTree.fromstring(client.get("/_/cached?limit=0").content).findall("./channel/item")) == 0
    assert client.get("/_/cached?limit=-1").status_code == 400
    assert len(ElementTree.fromstring(client.get("/_/cached").content).findall("./channel/item")) == 2
    assert len(feed.entry()) == 2
    assert all(item.id() is None for item in feed.entry())
