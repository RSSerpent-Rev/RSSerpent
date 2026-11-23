# Create an independent plugin

Use `uv init --lib my-rss-plugin` to create a Python package. In its `pyproject.toml`, use `requires-python = ">=3.14,<3.16"` and add `rsserpent-rev>=0.3,<0.4` to the project dependencies. Add the following code to `src/my_rss_plugin/__init__.py`.

```python
from rsserpent_rev.models import Entry, Feed, Plugin


async def provider() -> Feed:
    return Feed(
        title="Example",
        link="https://example.org/",
        entries=[Entry(title="First update")],
    )


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

A provider uses `Feed(title=..., link=..., entries=[...])`. Each `Entry` needs a title, summary, or body. Leave `entries` empty when there are no items. Set `content_type="html"` for an HTML body. The default body type is plain text. Use a time-zone-aware `datetime` for `published_at` or `updated_at`. The core omits missing publication dates and supplies the update time required by Atom.

Use `Entry.id` for a stable source identifier, especially if updates share the same URL. An absolute identifier such as a URL or URN is used as given. The core converts a local ID into a stable URN. Without an explicit ID, the core uses the article link and falls back to a deterministic ID based on the content. For upstream feeds and special format extensions, a provider can return a `FeedGenerator` directly. See [Retrieve data](data.md).

## Declare parameters and settings

Add the following to the same module to define typed parameters, settings and a shared HTTP client.

```python
from typing import Literal

from pydantic import BaseModel, Field
from rsserpent_rev.models import Entry, Feed, FeedRoute
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
    return Feed(
        title=context.settings.title,
        link="https://example.org/",
        description="Recent posts",
        entries=[Entry(title=entry["title"]) for entry in entries[:count]],
    )


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

Model fields named in the path are path parameters. Other fields are query parameters. Providers receive the validated values as keyword arguments. Use field names, simple scalar values, `Literal` choices, defaults and Pydantic constraints. Mark a default with `document_default` only when it can appear in public documentation. Use `plugin_settings` and `plugin_env` in the deployment TOML to set instance values. A catch-all path uses `format` for the core output format. Standard feed filters remain available.

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
.venv/bin/rsserpent check --config rsserpent.toml
.venv/bin/python -m rsserpent_rev --config rsserpent.toml
```

Check `/my-feed`, `/my-feed.rss` and `/my-feed.atom`. See the [route guide](../../usage/router.md) to implement providers with URL parameters.

`rsserpent check` imports the installed plugins and checks settings, route conflicts, parameters and examples. It exits nonzero on failure. For a typed route, the check validates example values against the parameter model. For a function route, it checks the path, parameter names and required fields without evaluating provider annotations. With the typed example, use `/my-feed/release.rss` and `/my-feed/release.atom` for a live request.

## Test offline

Install the `rsserpent-rev[test]` extra and pytest in your development environment. This test uses the application lifespan and calls the same RSS and Atom routes as a subscriber.

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

The fixture transport supplies responses for the context client. For an independent downloader, supply fixtures in its client factory or lifespan. Use a normal Starlette test client if your test needs several plugins.

## Publish

Publish the wheel to an index such as PyPI, share the artifact or make the package installable from a fixed Git commit. Give users both the package installation requirement and the Python module name. Users enter both values in their deployment TOML. Test your package in the official container before you publish it. See [Install and enable plugins](../../deployment/plugin.md).
