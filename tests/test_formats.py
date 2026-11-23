from datetime import UTC, datetime
from xml.etree import ElementTree

import arrow
import pytest
from feedgen.feed import FeedGenerator
from pydantic import ValidationError
from starlette.testclient import TestClient

from rsserpent_rev.main import ATOM_MIMETYPE, RSS_MIMETYPE, create_app
from rsserpent_rev.models import Entry, Feed, ProviderFn
from rsserpent_rev.plugins.builtin import plugin
from rsserpent_rev.utils import cached


def client_for(path: str, provider: ProviderFn) -> TestClient:
    return TestClient(create_app([plugin.model_copy(update={"routers": {path: provider}})]))


def test_catchall_keeps_source_url() -> None:
    seen = []

    async def provider(url: str) -> Feed:
        seen.append(url)
        return Feed(title="Example", link="https://example.org", description="Example feed")

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
        return Feed(
            title="Example",
            link="https://example.org",
            description="Example feed",
            entries=[Entry(title="Title only"), Entry(summary="Description only")],
        )

    client = client_for("/_/optional", provider)
    response = client.get("/_/optional.rss", params={"description_exclude": "Description"})
    items = ElementTree.fromstring(response.content).findall("./channel/item")
    assert [item.findtext("title") for item in items] == ["Title only"]
    assert items[0].find("link") is None
    response = client.get("/_/optional.atom")
    assert response.status_code == 200
    assert len(ElementTree.fromstring(response.content).findall("{http://www.w3.org/2005/Atom}entry")) == 2


def test_item_author_name_in_rss_and_atom() -> None:
    async def provider() -> Feed:
        return Feed(
            title="Example",
            link="https://example.org",
            entries=[Entry(title="One", author="Creator")],
        )

    client = client_for("/_/authors", provider)
    rss = ElementTree.fromstring(client.get("/_/authors.rss").content)
    assert rss.findtext("./channel/item/{http://purl.org/dc/elements/1.1/}creator") == "Creator"
    atom = ElementTree.fromstring(client.get("/_/authors.atom").content)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    assert atom.findtext("./atom:entry/atom:author/atom:name", namespaces=namespace) == "Creator"


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


def test_date_filter_requires_a_publication_date() -> None:
    async def provider() -> Feed:
        return Feed(
            title="Example",
            link="https://example.org",
            description="Example feed",
            entries=[
                Entry(title="No date"),
                Entry(title="Null date", published_at=None),
                Entry(title="Dated", published_at=datetime(2020, 1, 1, tzinfo=UTC)),
            ],
        )

    client = client_for("/_/dates", provider)
    default = client.get("/_/dates.rss")
    items = ElementTree.fromstring(default.content).findall("./channel/item")
    assert [item.findtext("pubDate") for item in items] == [None, None, "Wed, 01 Jan 2020 00:00:00 +0000"]
    default_atom = client.get("/_/dates.atom")
    assert len(ElementTree.fromstring(default_atom.content).findall("{http://www.w3.org/2005/Atom}entry")) == 3

    for key, bound in (("date_before", "2021-01-01T00:00:00Z"), ("date_after", "2019-01-01T00:00:00Z")):
        response = client.get("/_/dates.rss", params={key: bound})
        assert response.status_code == 200
        titles = ElementTree.fromstring(response.content).findall("./channel/item/title")
        assert [title.text for title in titles] == ["Dated"]


def test_explicit_guid_and_optional_channel_publication() -> None:
    async def provider() -> FeedGenerator:
        feed = FeedGenerator()
        feed.title("Example feed")
        feed.link(href="https://example.org/")
        feed.description("Example feed")
        entry = feed.add_entry()
        entry.title("One")
        entry.guid("post-1", permalink=False)
        return feed

    with client_for("/_/guid", provider) as client:
        response = client.get("/_/guid.rss")
        assert response.status_code == 200
        root = ElementTree.fromstring(response.content)
        assert root.find("./channel/pubDate") is None
        guid = root.find("./channel/item/guid")
        assert guid is not None and guid.text == "post-1" and guid.get("isPermaLink") == "false"


def test_atom_adds_author_for_low_level_feed_generator() -> None:
    async def provider() -> FeedGenerator:
        feed = FeedGenerator()
        feed.id("urn:feed")
        feed.title("Example feed")
        feed.link(href="https://example.org/")
        feed.description("Example feed")
        entry = feed.add_entry()
        entry.id("urn:entry")
        entry.title("Entry")
        entry.link(href="https://example.org/entry")
        return feed

    with client_for("/_/author", provider) as client:
        atom = ElementTree.fromstring(client.get("/_/author.atom").content)
        author = atom.find("./{*}author")
        assert author is not None
        assert author.findtext("{*}name") == "queensferryme"
        assert author.findtext("{*}email") == "queensferry.me@gmail.com"


def test_rss_text_is_escaped_once() -> None:
    async def provider() -> Feed:
        return Feed(
            title="Example",
            link="https://example.org/",
            entries=[Entry(title="Special", summary="A & B < C")],
        )

    with client_for("/_/escaping", provider) as client:
        rss = ElementTree.fromstring(client.get("/_/escaping.rss").content)
        assert rss.findtext("./channel/item/description") == "A & B < C"


def test_default_id_uses_article_link() -> None:
    async def provider() -> Feed:
        return Feed(
            title="Example",
            link="https://example.org/",
            entries=[
                Entry(title="Announcement", link="https://example.org/1"),
                Entry(title="Announcement", link="https://example.org/2"),
            ],
        )

    with client_for("/_/default-id", provider) as client:
        root = ElementTree.fromstring(client.get("/_/default-id.rss").content)
        assert [guid.text for guid in root.findall("./channel/item/guid")] == [
            "https://example.org/1",
            "https://example.org/2",
        ]


def test_typed_feed_keeps_identity_and_content_type() -> None:
    title = "First title"
    publication = datetime(2024, 1, 1, tzinfo=UTC)
    update = datetime(2024, 1, 2, tzinfo=UTC)

    async def provider() -> Feed:
        return Feed(
            title="Typed feed",
            link="https://example.org/news",
            updated_at=update,
            entries=[
                Entry(title=title, link="https://example.org/one", published_at=publication, summary="An update"),
                Entry(
                    id="urn:example:two",
                    link="https://example.org/two",
                    summary="A summary",
                    content="<p>Full text</p>",
                    content_type="html",
                ),
                Entry(content="<b>literal text</b>"),
                Entry(id="upstream-123", title="Opaque source ID", link="https://example.org/opaque"),
            ],
        )

    with client_for("/_/typed", provider) as client:
        rss = ElementTree.fromstring(client.get("/_/typed.rss").content)
        items = rss.findall("./channel/item")
        ids = [item.findtext("guid") for item in items]
        assert ids[:2] == ["https://example.org/one", "urn:example:two"]
        assert ids[2] is not None and ids[2].startswith("urn:uuid:")
        assert ids[3] is not None and ids[3].startswith("urn:uuid:") and ids[3] != ids[2]
        assert items[1].findtext("description") == "A summary"
        assert items[1].findtext("{http://purl.org/rss/1.0/modules/content/}encoded") == "<p>Full text</p>"
        assert items[2].findtext("description") == "<b>literal text</b>"
        assert rss.find("./channel/pubDate") is None

        title = "Corrected title"
        atom = ElementTree.fromstring(client.get("/_/typed.atom").content)
        entries = atom.findall("{*}entry")
        assert [entry.findtext("{*}id") for entry in entries] == ids
        assert entries[0].findtext("{*}title") == title
        assert entries[0].findtext("{*}published") == publication.isoformat()
        assert entries[0].findtext("{*}updated") == publication.isoformat()
        assert entries[1].find("{*}published") is None
        assert entries[1].findtext("{*}updated") == update.isoformat()
        html = entries[1].find("{*}content")
        text = entries[2].find("{*}content")
        assert html is not None and html.get("type") == "html" and html.text == "<p>Full text</p>"
        assert text is not None and text.get("type") == "text" and text.text == "<b>literal text</b>"

        filtered = client.get("/_/typed.rss", params={"description_include": "literal text"})
        assert len(ElementTree.fromstring(filtered.content).findall("./channel/item")) == 1


def test_entry_validation() -> None:
    with pytest.raises(ValidationError, match="title, summary, or content"):
        Entry()
    with pytest.raises(ValidationError, match="timezone"):
        Entry(title="No timezone", published_at=datetime.fromisoformat("2024-01-01T00:00:00"))
