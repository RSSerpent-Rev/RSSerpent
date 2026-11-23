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
.venv/bin/python -m rsserpent_rev --config rsserpent.toml
```

访问 `/my-feed`、`/my-feed.rss` 和 `/my-feed.atom` 验证输出。带 URL 参数的 provider 写法见[路由文档](../../usage/router.zh.md)。

## 发布

你可以发布 wheel 到 PyPI 等包索引、直接分发 wheel，或让用户从固定 Git 提交安装。发布时同时提供安装依赖和 Python 模块名。用户把这两个值写进自己的部署 TOML。发布前，用官方镜像验证插件依赖和订阅。详见[安装与启用插件](../../deployment/plugin.zh.md)。
