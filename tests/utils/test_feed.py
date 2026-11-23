from datetime import UTC, datetime
from urllib.request import OpenerDirector
from xml.etree import ElementTree

import pytest
from starlette.testclient import TestClient

from rsserpent_rev.main import create_app
from rsserpent_rev.models import Feed
from rsserpent_rev.plugins.builtin import plugin as builtin_plugin
from rsserpent_rev.utils import FeedParseError, parse_feed

BASE = "https://example.net/news/feed.xml"
NS = {"a": "http://www.w3.org/2005/Atom"}
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:news</id><title>News</title><updated>2025-03-01T12:00:00Z</updated>
  <link href="./"/><author><name>Writer</name><uri>../writer</uri></author>
  <entry><id>urn:entry</id><title>First</title><link href="post"/>
    <published>2025-02-01T12:00:00Z</published><updated>2025-02-02T12:00:00Z</updated></entry>
  <entry><id>urn:second</id><title>Second</title><summary>Text</summary></entry>
</feed>"""
RSS = b"""<rss version="2.0"><channel><title>News</title><link>./</link><description>Posts</description>
  <item><title>News one</title><link>one</link><guid isPermaLink="false">item-1</guid></item>
  <item><title>News two</title><link>two</link><guid isPermaLink="false">item-2</guid></item>
</channel></rss>"""


def test_parse_atom() -> None:
    feed = parse_feed(ATOM, base_url=BASE)
    root = ElementTree.fromstring(feed.atom_str())
    assert root.findtext("a:id", namespaces=NS) == "urn:news"
    assert root.findtext("a:author/a:name", namespaces=NS) == "Writer"
    assert root.findtext("a:author/a:uri", namespaces=NS) == "https://example.net/writer"
    entries = root.findall("a:entry", NS)
    first, second = entries
    assert first.findtext("a:id", namespaces=NS) == "urn:entry"
    link = first.find("a:link", NS)
    assert link is not None and link.get("href") == "https://example.net/news/post"
    assert first.findtext("a:published", namespaces=NS) == "2025-02-01T12:00:00+00:00"
    assert first.findtext("a:updated", namespaces=NS) == "2025-02-02T12:00:00+00:00"
    assert second.findtext("a:published", namespaces=NS) is None
    assert second.findtext("a:updated", namespaces=NS) == "2025-03-01T12:00:00+00:00"


def test_undated_feed_routes() -> None:
    async def provider() -> Feed:
        return parse_feed(RSS, base_url=BASE)

    plugin = builtin_plugin.model_copy(update={"routers": {"/_/parsed": provider}})
    with TestClient(create_app([plugin])) as client:
        rss = ElementTree.fromstring(client.get("/_/parsed.rss").content)
        items = rss.findall("./channel/item")
        assert [item.findtext("guid") for item in items] == ["item-1", "item-2"]
        assert items[0].findtext("link") == "https://example.net/news/one"
        assert all(item.find("pubDate") is None for item in items)
        before = datetime.now(UTC)
        atom = ElementTree.fromstring(client.get("/_/parsed.atom").content)
        after = datetime.now(UTC)
        entries = atom.findall("a:entry", NS)
        assert len(entries) == 2
        assert all(entry.find("a:published", NS) is None for entry in entries)
        updated = {entry.findtext("a:updated", namespaces=NS) for entry in entries}
        (timestamp,) = updated
        assert timestamp is not None and before <= datetime.fromisoformat(timestamp) <= after
        filtered = client.get("/_/parsed.atom", params={"date_after": "2000-01-01T00:00:00Z"})
        assert ElementTree.fromstring(filtered.content).findall("a:entry", NS) == []


def test_parse_empty_feed_with_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbid(*args: object, **kwargs: object) -> None:
        pytest.fail("parse_feed attempted network access")

    monkeypatch.setattr(OpenerDirector, "open", forbid)
    body = b"""<!DOCTYPE rss SYSTEM "https://example.net/feed.dtd">
      <rss version="2.0"><channel><title>Empty</title><description>Empty</description>
      <link>https://example.net/</link></channel></rss>"""
    assert parse_feed(body, base_url=BASE).entry() == []
    with pytest.raises(FeedParseError, match="invalid RSS or Atom") as error:
        parse_feed(b"https://example.net/private-body", base_url=BASE)
    assert "private-body" not in str(error.value)


def test_invalid_feed_from_provider() -> None:
    async def provider() -> Feed:
        return parse_feed(b"<html>Not feed data</html>", base_url=BASE)

    plugin = builtin_plugin.model_copy(update={"routers": {"/_/parsed": provider}})
    with TestClient(create_app([plugin])) as client:
        assert client.get("/_/parsed.rss").status_code == 502
