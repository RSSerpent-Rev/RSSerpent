# 开发独立插件

用 `uv init --lib my-rss-plugin` 创建 Python 包。在项目的 `pyproject.toml` 中设置 `requires-python = ">=3.14,<3.16"`，将 `rsserpent-rev>=0.3,<0.4` 加入项目依赖。将以下代码写入 `src/my_rss_plugin/__init__.py`。

```python
from rsserpent_rev.models import Feed, Plugin


async def provider() -> Feed:
    return {
        "title": "Example",
        "link": "https://example.org/",
        "description": "Example updates",
        "items": [{"title": "First update"}],
    }


plugin = Plugin(
    name="rsserpent-plugin-example",
    author={"name": "Your name", "email": "you@example.org", "link": "https://example.org/"},
    repository="https://example.org/my-rss-plugin",
    prefix="/my-feed",
    routers={"/my-feed": provider},
    route_docs={
        "/my-feed": {
            "summary": "示例更新",
            "description": "订阅最新公告。",
            "examples": [{"label": "最近五条", "query": {"limit": "5"}}],
        },
    },
)
```

## 声明参数和设置

在同一模块中追加以下代码，声明类型化参数、插件设置和可复用的 HTTP 客户端。

```python
from typing import Literal

from pydantic import BaseModel, Field
from rsserpent_rev.models import Feed, FeedRoute
from rsserpent_rev.utils import get_plugin_context


class Settings(BaseModel):
    title: str = "Announcements"


class Parameters(BaseModel):
    topic: Literal["news", "release"]
    count: int = Field(5, ge=1, le=20, json_schema_extra={"document_default": True})


async def announcements(topic: str, count: int) -> Feed:
    context = get_plugin_context()
    assert isinstance(context.settings, Settings) and context.http is not None
    entries = await context.http.get_json("https://example.org/api/posts", params={"topic": topic})
    return {
        "title": context.settings.title,
        "link": "https://example.org/",
        "description": "Recent posts",
        "items": [{"title": entry["title"]} for entry in entries[:count]],
    }


plugin = Plugin(
    name=plugin.name,
    author=plugin.author,
    repository=plugin.repository,
    prefix=plugin.prefix,
    routers={"/my-feed/{topic}": FeedRoute(announcements, parameters=Parameters)},
    route_docs={
        "/my-feed/{topic}": {
            "summary": "Recent announcements",
            "examples": [{"label": "Releases", "path": {"topic": "release"}}],
        },
    },
    settings_model=Settings,
    http_client=True,
)
```

模型中与路径变量同名的字段取自路径，其余字段取自查询字符串。provider 以关键字参数接收校验后的值。可声明标量类型、`Literal` 枚举、默认值和 Pydantic 约束。仅对可公开的默认值标记 `document_default`。在部署 TOML 中用 `plugin_settings` 和 `plugin_env` 提供实例设置。捕获整段路径的路由由核心使用 `format` 控制输出格式，通用过滤参数照常可用。

## 编写路由文档

要在实例的 `/all_routes` 页面说明某个订阅，把 `route_docs` 传给 `Plugin`。键使用 `routers` 中对应的路径。

每条文档要填写 `summary`。还可以添加纯文本 `description` 和从参数名到说明的 `parameters` 映射。示例要填写 `label`，用字符串填写需要的 `path` 和 `query` 值。比如路由含有 `{uid}` 时，可以写 `"path": {"uid": "297786973"}`。示例只填可公开的值。页面从已注册的路由和 provider 签名读取参数名及必填状态，再生成 RSS 和 Atom 链接。缺少必填值或路径不匹配的示例会跳过，可查看启动日志。不提供 `route_docs` 时，页面显示实际路径、可推断的参数和已有的 provider 文档字符串。

## 在 RSSerpent 中测试

在 `rsserpent.toml` 中填写模块名。如果需要本地核心 wheel，先从对应的 RSSerpent 源码构建。以下命令在插件项目目录运行。

```toml
plugins = ["my_rss_plugin"]
```

```sh
uv build --wheel
uv venv --python 3.14
uv pip install /path/to/rsserpent_rev-0.3.0-py3-none-any.whl dist/*.whl uvicorn
.venv/bin/rsserpent check --config rsserpent.toml
.venv/bin/python -m rsserpent_rev --config rsserpent.toml
```

访问 `/my-feed`、`/my-feed.rss` 和 `/my-feed.atom` 验证输出。带 URL 参数的 provider 写法见[路由文档](../../usage/router.zh.md)。

`rsserpent check` 在当前环境导入已安装的插件，检查配置、路由冲突、参数和文档示例。失败时以非零状态退出。类型化路由按参数模型校验示例值。普通函数路由检查路径、参数名称和必填项，检查过程不求值 provider 注解。需要实际发送请求时，以上述类型化插件的 `/my-feed/release.rss` 和 `/my-feed/release.atom` 为准。

## 离线测试

在开发环境中安装 `rsserpent-rev[test]` 扩展和 pytest。以下测试会执行应用的 lifespan，并调用订阅者使用的 RSS 和 Atom 路由。

```python
from xml.etree import ElementTree

import httpx
from my_rss_plugin import plugin
from rsserpent_rev.testing import plugin_test_client


def upstream(request: httpx.Request) -> httpx.Response:
    assert request.url.params["topic"] == "release"
    return httpx.Response(200, json=[{"title": "Version 1"}])


def test_feed() -> None:
    with plugin_test_client(
        plugin,
        settings={"title": "Announcements"},
        transport=httpx.MockTransport(upstream),
    ) as client:
        rss = ElementTree.fromstring(client.get("/my-feed/release.rss").content)
        atom = ElementTree.fromstring(client.get("/my-feed/release.atom").content)
        assert rss.findtext("./channel/item/title") == "Version 1"
        assert atom.findtext("{*}entry/{*}title") == "Version 1"
```

固定响应由传输层提供给上下文客户端。使用独立下载器时，可在客户端工厂或 lifespan 中注入响应。需要同时测试多个插件时，可以直接使用 Starlette 的 TestClient。

## 发布

你可以发布 wheel 到 PyPI 等包索引、直接分发 wheel，或让用户从固定 Git 提交安装。发布时同时提供安装依赖和 Python 模块名。用户把这两个值写进自己的部署 TOML。发布前，用官方镜像验证插件依赖和订阅。详见[安装与启用插件](../../deployment/plugin.zh.md)。
