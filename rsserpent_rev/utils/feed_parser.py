import datetime

import feedparser
from feedgen.feed import FeedGenerator


def to_feedgen(feed: feedparser.util.FeedParserDict) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title(feed.get("feed").get("title"))
    fg.link(href=feed.get("feed").get("link"))
    fg.description(feed.get("feed").get("description"))
    fg.language(feed.get("feed").get("language"))
    fg.copyright(feed.get("feed").get("rights"))
    fg.managingEditor(feed.get("feed").get("managingEditor"))
    fg.webMaster(feed.get("feed").get("webMaster"))
    fg.lastBuildDate(feed.get("feed").get("updated"))
    fg.generator(feed.get("feed").get("generator"))
    fg.docs(feed.get("feed").get("docs"))
    fg.ttl(feed.get("feed").get("ttl"))
    if feed.get("feed").get("image"):
        fg.image(
            url=feed.get("feed").get("image").get("url"),
            title=feed.get("feed").get("image").get("title"),
            link=feed.get("feed").get("image").get("link"),
            width=feed.get("feed").get("image").get("width"),
            height=feed.get("feed").get("image").get("height"),
            description=feed.get("feed").get("image").get("description"),
        )
    if feed.get("feed").get("category"):
        for category in feed.get("feed").get("category"):
            fg.category(category.get("term"), domain=category.get("scheme"))

    for entry in feed.get("entries"):
        fe = fg.add_entry()
        fe.title(entry.get("title"))
        fe.link(href=entry.get("link"))
        fe.description(entry.get("summary"))
        fe.author(entry.get("author"))
        fe.comments(entry.get("comments"))
        if entry.get("enclosures"):
            for enclosure in entry.get("enclosures"):
                fe.enclosure(
                    url=enclosure.get("href"),
                    length=enclosure.get("length"),
                    type=enclosure.get("type"),
                )
        if entry.get("id"):
            fe.guid(entry.get("id"), permalink=True)
        if entry.get("published"):
            fe.pubDate(entry.get("published"))
        else:
            fe.pubDate(datetime.datetime.now(datetime.UTC))
        if entry.get("source"):
            fe.source(title=entry.get("source").get("title"), url=entry.get("source").get("href"))
        if entry.get("category"):
            for category in entry.get("category"):
                fe.category(category.get("term"), domain=category.get("scheme"))
        if entry.get("content"):
            fe.content(entry.get("content")[0].get("value"))
    return fg
