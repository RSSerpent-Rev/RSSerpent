from typing import Literal

import pytest
from pydantic import BaseModel, Field
from starlette.testclient import TestClient

from rsserpent_rev.main import create_app
from rsserpent_rev.models import Entry, Feed, FeedRoute
from rsserpent_rev.plugins.builtin import plugin as builtin_plugin
from rsserpent_rev.plugins.config import PluginLoadError
from rsserpent_rev.utils import cached


class Parameters(BaseModel):
    article: int = Field(ge=1)
    view: Literal["full", "short"]
    count: Literal[1, 2] = Field(1, json_schema_extra={"document_default": True})
    rating: float | None = Field(None, ge=0, le=5)
    omitted: str = "not_for_public_documentation"


def test_typed_route() -> None:
    calls = []

    @cached
    async def provider(article: int, view: str, count: int, rating: float | None, omitted: str) -> Feed:
        calls.append((article, view, count, rating, omitted))
        return Feed(
            title=f"Article {article}",
            description="Fixture",
            link="https://example.net/",
            entries=[Entry(title="Entry")],
        )

    path = "/_/article/{article:int}"
    plugin = builtin_plugin.model_copy(
        update={
            "routers": {path: FeedRoute(provider, parameters=Parameters)},
            "route_docs": {
                path: {
                    "summary": "Find an article",
                    "examples": [
                        {"label": "Valid example", "path": {"article": "7"}, "query": {"view": "short"}},
                        {"label": "Invalid example", "path": {"article": "7"}, "query": {"view": "other"}},
                    ],
                }
            },
        }
    )
    app = create_app([plugin])
    with TestClient(app) as client:
        invalid = [
            ("/_/article/0", {"view": "short"}, "article"),
            ("/_/article/7", {"view": "other"}, "view"),
            ("/_/article/7", {}, "view"),
            ("/_/article/7", {"view": "full", "rating": "5.1"}, "rating"),
            ("/_/article/7", {"view": "full", "rating": "bad"}, "rating"),
            ("/_/article/7", {"view": "full", "rating": "-1"}, "rating"),
        ]
        for url, query, field in invalid:
            response = client.get(url, params=query)
            assert response.status_code == 400 and field in response.text
        assert not calls
        response = client.get("/_/article/7.atom?article=9&view=short&limit=0&count=2")
        assert response.status_code == 200
        assert "Article 7" in response.text and "<entry>" not in response.text
        assert calls == [(7, "short", 2, None, "not_for_public_documentation")]
        assert client.get("/_/article/7?view=short&count=2").status_code == 200
        assert len(calls) == 1

        catalog = client.get("/all_routes").text
        assert "full / short" in catalog and "Default <code>1</code>" in catalog
        assert "not_for_public_documentation" not in catalog
        assert "Valid example" in catalog and "Invalid example" not in catalog
        assert any("Invalid parameter: view" in message for message in app.state.diagnostics)


def test_typed_catch_all_without_annotation_evaluation() -> None:
    class CatchAll(BaseModel):
        url: str

    def annotation() -> type[str]:
        pytest.fail("provider annotation was evaluated")

    async def provider(url: annotation()) -> Feed:  # type: ignore[valid-type]
        return Feed(title=url, description="Fixture", link="https://example.net/")

    plugin = builtin_plugin.model_copy(update={"routers": {"/_/path/{url:path}": FeedRoute(provider, CatchAll)}})
    with TestClient(create_app([plugin])) as client:
        response = client.get("/_/path/a/b?format=atom")
        assert response.status_code == 200 and "<title>a/b</title>" in response.text


def test_route_definition_checks_provider_signature() -> None:
    async def provider(article: int) -> Feed:
        pytest.fail(f"provider called for {article}")

    plugin = builtin_plugin.model_copy(
        update={"routers": {"/_/article/{article:int}": FeedRoute(provider, Parameters)}}
    )
    with pytest.raises(PluginLoadError, match=r"Invalid provider parameters.*view"):
        create_app([plugin])
