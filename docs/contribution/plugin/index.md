# Create an independent plugin

Use `uv init --lib my-rss-plugin` to create a Python package. In its `pyproject.toml`, use `requires-python = ">=3.14,<3.16"` and add `rsserpent-rev>=0.3,<0.4` to the project dependencies. Add the following code to `src/my_rss_plugin/__init__.py`.

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

## Test with RSSerpent

Save the module name in `rsserpent.toml`. Build the core wheel from the matching RSSerpent checkout if you need a local core artifact. Run the following from the plugin project.

```toml
plugins = ["my_rss_plugin"]
```

```sh
uv build --wheel
uv venv --python 3.14
uv pip install /path/to/rsserpent_rev-0.3.0-py3-none-any.whl dist/*.whl uvicorn
RSSERPENT_CONFIG=rsserpent.toml .venv/bin/uvicorn rsserpent_rev:app
```

Check `/my-feed`, `/my-feed.rss` and `/my-feed.atom`. See the [route guide](../../usage/router.md) to implement providers with URL parameters.

## Publish

Publish the wheel to an index such as PyPI, share the artifact or make the package installable from a fixed Git commit. Give users both the package installation requirement and the Python module name. They install the package in their RSSerpent environment and add that module to their own configuration. See [Install and enable plugins](../../deployment/plugin.md).
