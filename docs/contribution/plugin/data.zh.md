# 获取数据

## JSON 和 HTML

`HTTPClient` 是带默认 `Host` 和 `Referer` 请求头的异步 HTTPX 客户端。用 `get_json()` 读取 JSON，用 `get_html()` 返回可做 CSS 查询的 PyQuery 对象。这两个方法沿用客户端的请求设置。你可以传入 HTTPX 选项覆盖某次请求。

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

便捷方法先检查 HTTP 状态，再解析响应。上游超时使订阅路由返回 HTTP 504。上游状态异常或解码失败返回 HTTP 502。需要在 provider 里处理解码失败时，可以捕获 `UpstreamDecodeError`。HTML 中的链接保留网页给出的原值。

在 `Plugin` 中设 `http_client=True`，用 `get_plugin_context().http` 复用连接池。你可以提供自己的客户端工厂来设置请求头、认证或 HTTPX 传输层。需要处理 HTTP 304、读取响应头、指定编码或限制响应体积时，可直接用 `get()`、`request()` 或 `stream()`。也可以在插件的 `lifespan` 中管理自选的下载器。见[开发独立插件](index.zh.md)。

## RSS 和 Atom

把下载后的字节和最终 URL 传给 `parse_feed()`。解析器只读取这些字节，使用 URL 解析相对链接，也把它用作缺少频道链接时的默认值。provider 可直接返回得到的 `FeedGenerator`。

```python
import asyncio

from rsserpent_rev.utils import HTTPClient, parse_feed


async with HTTPClient() as client:
    response = (await client.get("https://example.org/feed.xml")).raise_for_status()
feed = await asyncio.to_thread(parse_feed, response.content, base_url=str(response.url))
```

解析器保留来源提供的 ID、作者和发布时间。需要选取单个字段时，使用主链接、第一段内嵌内容和第一个附件。来源缺少条目发布时间时，输出也省略发布时间。Atom 必需的更新时间依次取条目日期、订阅源日期和解析时间，日期过滤仍按条目发布时间执行。有标题的空订阅可正常返回。需要自定义解析失败的处理时，可以捕获 `FeedParseError`。

## 浏览器

网页需要执行 JavaScript 时，使用 `Browser`，部署时选用[带 Chromium 的镜像](../../deployment/plugin.zh.md)。

```python
from pyquery import PyQuery

from rsserpent_rev.utils import Browser


async with Browser() as browser:
    await browser.goto("https://example.org/news")
    page = PyQuery(await browser.content())
    title = page("h1").text()
```
