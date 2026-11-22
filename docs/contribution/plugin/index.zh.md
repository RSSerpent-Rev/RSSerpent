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
)
```

## 在 RSSerpent 中测试

在 `rsserpent.toml` 中填写模块名。如果需要本地核心 wheel，先从对应的 RSSerpent 源码构建。以下命令在插件项目目录运行。

```toml
plugins = ["my_rss_plugin"]
```

```sh
uv build --wheel
uv venv --python 3.14
uv pip install /path/to/rsserpent_rev-0.3.0-py3-none-any.whl dist/*.whl uvicorn
RSSERPENT_CONFIG=rsserpent.toml .venv/bin/uvicorn rsserpent_rev:app
```

访问 `/my-feed`、`/my-feed.rss` 和 `/my-feed.atom` 验证输出。带 URL 参数的 provider 写法见[路由文档](../../usage/router.zh.md)。

## 发布

你可以发布 wheel 到 PyPI 等包索引、直接分发 wheel，或让用户从固定 Git 提交安装。发布时同时提供安装依赖和 Python 模块名。用户将包安装在 RSSerpent 环境中，然后把模块加入自己的配置。详见[安装与启用插件](../../deployment/plugin.zh.md)。
