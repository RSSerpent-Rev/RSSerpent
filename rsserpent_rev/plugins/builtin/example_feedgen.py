from feedgen.feed import FeedGenerator

from ...utils import cached
from rsserpent_rev.models.plugin import Feed

path = "/_/example/feedgen"


@cached
async def provider() -> Feed:
    """Define a basic example data provider function."""
    fg = FeedGenerator()
    fg.id("http://lernfunk.de/media/654321")
    fg.title("Some Testfeed")
    fg.author({"name": "John Doe", "email": "john@example.de"})
    fg.link(href="http://example.com", rel="alternate")
    fg.logo("http://ex.com/logo.jpg")
    fg.subtitle("This is a cool feed!")
    fg.link(href="http://larskiesow.de/test.atom", rel="self")
    fg.language("en")
    fe = fg.add_entry()
    fe.id("http://lernfunk.de/media/654322")
    fe.title("A second test")
    fe.link(href="http://example.com/2", rel="alternate")
    fe.content("And here the content")
    fe = fg.add_entry()
    fe.id("http://lernfunk.de/media/654323")
    fe.title("A third test")
    fe.link(href="http://example.com/3", rel="alternate")
    fe.content("And here the content")
    return fg
