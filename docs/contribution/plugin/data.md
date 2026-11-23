# Retrieve data

## JSON and HTML

`HTTPClient` is an asynchronous HTTPX client with default `Host` and `Referer` headers. Use `get_json()` for JSON and `get_html()` for CSS queries with PyQuery. Both methods use the client's default request settings. Pass HTTPX options to override them for one request.

```python
from rsserpent_rev.utils import HTTPClient


async with HTTPClient() as client:
    data = await client.get_json(
        "https://example.org/api/posts",
        params={"page": 1},
        headers={"Accept": "application/json"},
        timeout=5,
    )
    page = await client.get_html("https://example.org/news", follow_redirects=True)
    titles = [heading.text() for heading in page("article h2").items()]
```

The helpers check the HTTP status before parsing. A timeout returns HTTP 504 from the feed route. A bad upstream status or a decoding error returns HTTP 502. Catch `UpstreamDecodeError` in the provider to handle a decoding error yourself. HTML links keep the values from the page.

Set `http_client=True` on `Plugin` and use `get_plugin_context().http` to reuse a connection pool. You can provide a client factory with your own headers, authentication or HTTPX transport. Use `get()`, `request()` or `stream()` when you need the response itself, such as handling HTTP 304, reading headers, controlling encoding or limiting the response size. You can also use your own downloader and manage it in the plugin's `lifespan`. See [Create an independent plugin](index.md).

## RSS and Atom

Pass downloaded bytes and the final URL to `parse_feed()`. The parser uses the URL to resolve relative links and as a fallback channel link. It reads only the given bytes. You can return the resulting `FeedGenerator` directly from a provider.

```python
import asyncio

from rsserpent_rev.utils import HTTPClient, parse_feed


async with HTTPClient() as client:
    response = (await client.get("https://example.org/feed.xml")).raise_for_status()
feed = await asyncio.to_thread(parse_feed, response.content, base_url=str(response.url))
```

The parser keeps source IDs, author information and publication dates when provided. It uses the primary link, first inline content and first enclosure when it must choose one. An undated entry keeps its publication date empty. Atom requires an update date, so the parser uses the entry date, the feed date or the time of parsing, in that order. Date filters still use the publication date. A feed with a title and zero entries is valid. Catch `FeedParseError` if you want to handle invalid input yourself.

## Browser

Use `Browser` when the site needs JavaScript to render the content. Deploy the plugin with the [Chromium image](../../deployment/plugin.md).

```python
from pyquery import PyQuery

from rsserpent_rev.utils import Browser


async with Browser() as browser:
    await browser.goto("https://example.org/news")
    page = PyQuery(await browser.content())
    title = page("h1").text()
```
