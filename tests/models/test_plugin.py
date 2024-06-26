import asyncio
from collections.abc import Awaitable, Callable
from functools import partial, wraps
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis.provisional import urls
from hypothesis.strategies import builds, dictionaries, functions, just, text
from pydantic import ValidationError

from rsserpent_rev.models.plugin import Persona, Plugin, PluginModelError, ProviderFn
from tests.conftest import Times


def to_async(fn: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
    """Convert a synchronous function to an async one.

    Derived from https://stackoverflow.com/a/50450553.
    """

    @wraps(fn)
    async def async_fn(*args: tuple[Any, ...], **kwds: dict[str, Any]) -> Any:
        loop = asyncio.get_event_loop()
        partial_fn = partial(fn, *args, **kwds)
        return await loop.run_in_executor(None, partial_fn)

    return async_fn


class TestPlugin:
    """Test the `Plugin` class."""

    @settings(max_examples=Times.SOME)
    @given(
        name=text(),
        author=builds(Persona),
        repository=urls(),
        prefix=just("/prefix"),
        routers=dictionaries(
            text().map(lambda s: f"/prefix/{s}"),
            functions().map(to_async),
            min_size=1,
        ),
    )
    def test_name_validation(
        self,
        name: str,
        author: Persona,
        repository: str,
        prefix: str,
        routers: dict[str, ProviderFn],
    ) -> None:
        """Test if the `Plugin` class validates `name` properly."""

        with pytest.raises(ValidationError) as e:
            Plugin.model_validate(
                {
                    "name": name,
                    "author": author,
                    "repository": repository,
                    "prefix": prefix,
                    "routers": routers,
                }
            )

        assert PluginModelError.unexpected_plugin_name in str(e)

    @settings(max_examples=Times.SOME)
    @given(
        name=text().map(lambda s: f"rsserpent-plugin-{s}"),
        author=builds(Persona),
        repository=urls(),
        prefix=just("/prefix"),
        routers=dictionaries(text().map(lambda s: f"/prefix/{s}"), functions(), min_size=1),
    )
    def test_routers_validation(
        self,
        name: str,
        author: Persona,
        repository: str,
        prefix: str,
        routers: dict[str, ProviderFn],
    ) -> None:
        """Test if the `Plugin` class validates `routers` properly."""
        with pytest.raises(ValidationError) as e:
            Plugin.model_validate(
                {
                    "name": name,
                    "author": author,
                    "repository": repository,
                    "prefix": prefix,
                    "routers": routers,
                }
            )
        assert e is not None
        assert PluginModelError.provider_not_async in str(e)

        with pytest.raises(ValidationError) as e:
            Plugin.model_validate(
                {
                    "name": name,
                    "author": author,
                    "repository": repository,
                    "prefix": prefix,
                    "routers": {},
                }
            )
        assert e is not None
        assert PluginModelError.empty_router in str(e)

    @settings(max_examples=Times.SOME)
    @given(
        name=text().map(lambda s: f"rsserpent-plugin-{s}"),
        author=builds(Persona),
        repository=urls(),
        prefix=just("/prefix"),
        routers=dictionaries(text(), functions().map(to_async), min_size=1),
    )
    def test_validation(
        self,
        name: str,
        author: Persona,
        repository: str,
        prefix: str,
        routers: dict[str, ProviderFn],
    ) -> None:
        """Test if the `@model_validator` of `Item` class works properly."""
        with pytest.raises(ValidationError) as e:
            Plugin.model_validate(
                {
                    "name": name,
                    "author": author,
                    "repository": repository,
                    "prefix": prefix,
                    "routers": routers,
                }
            )

        assert e is not None
        assert PluginModelError.unexpected_router_path_prefix in str(e)

    @settings(max_examples=Times.SOME)
    @given(
        name=text().map(lambda s: f"rsserpent-plugin-{s}"),
        author=builds(Persona),
        repository=urls(),
        prefix=just("/prefix"),
        routers=dictionaries(text().map(lambda s: f"/prefix/{s}.atom"), functions().map(to_async), min_size=1),
    )
    def test_suffix_validation_atom(
        self,
        name: str,
        author: Persona,
        repository: str,
        prefix: str,
        routers: dict[str, ProviderFn],
    ) -> None:
        """Test if the `@model_validator` of `Item` class works properly."""
        with pytest.raises(ValidationError) as e:
            Plugin.model_validate(
                {
                    "name": name,
                    "author": author,
                    "repository": repository,
                    "prefix": prefix,
                    "routers": routers,
                }
            )
        assert e is not None
        assert PluginModelError.unexpected_router_path_suffix in str(e)

    @settings(max_examples=Times.SOME)
    @given(
        name=text().map(lambda s: f"rsserpent-plugin-{s}"),
        author=builds(Persona),
        repository=urls(),
        prefix=just("/prefix"),
        routers=dictionaries(text().map(lambda s: f"/prefix/{s}.rss"), functions().map(to_async), min_size=1),
    )
    def test_suffix_validation_rss(
        self,
        name: str,
        author: Persona,
        repository: str,
        prefix: str,
        routers: dict[str, ProviderFn],
    ) -> None:
        """Test if the `@model_validator` of `Item` class works properly."""
        with pytest.raises(ValidationError) as e:
            Plugin.model_validate(
                {
                    "name": name,
                    "author": author,
                    "repository": repository,
                    "prefix": prefix,
                    "routers": routers,
                }
            )

        assert e is not None
        assert PluginModelError.unexpected_router_path_suffix in str(e)
