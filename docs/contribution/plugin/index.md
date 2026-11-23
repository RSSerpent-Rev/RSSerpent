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
    route_docs={
        "/my-feed": {
            "summary": "Example updates",
            "description": "Follow the latest announcements.",
            "examples": [{"label": "Latest five entries", "query": {"limit": "5"}}],
        },
    },
)
```

## Document a route

To document a feed on the instance's `/all_routes` page, pass `route_docs` to `Plugin`. Use the same path key as in `routers`.

Each entry needs a `summary`. You can add a plain-text `description` and `parameters`, a mapping from parameter names to descriptions. For each example, provide a `label` and any `path` or `query` values as strings. For instance, use `"path": {"uid": "297786973"}` for a route with `{uid}`. List values that are safe to publish. The page derives parameter names and required fields from the registered route and the provider signature. It builds the RSS and Atom example links and skips examples with invalid path values or missing required parameters. View startup logs for skipped entries. Without `route_docs`, the page shows the registered paths, detectable parameters and any provider docstring.

## Test with RSSerpent

Save the module name in `rsserpent.toml`. Build the core wheel from the matching RSSerpent checkout if you need a local core artifact. Run the following from the plugin project.

```toml
plugins = ["my_rss_plugin"]
```

```sh
uv build --wheel
uv venv --python 3.14
uv pip install /path/to/rsserpent_rev-0.3.0-py3-none-any.whl dist/*.whl uvicorn
.venv/bin/python -m rsserpent_rev --config rsserpent.toml
```

Check `/my-feed`, `/my-feed.rss` and `/my-feed.atom`. See the [route guide](../../usage/router.md) to implement providers with URL parameters.

## Publish

Publish the wheel to an index such as PyPI, share the artifact or make the package installable from a fixed Git commit. Give users both the package installation requirement and the Python module name. Users enter both values in their deployment TOML. Test your package in the official container before you publish it. See [Install and enable plugins](../../deployment/plugin.md).
