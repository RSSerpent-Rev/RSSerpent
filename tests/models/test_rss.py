from hypothesis import given, infer, settings

from rsserpent_rev.models.rss import Item, RSSModelError
from tests.conftest import Times


class TestItem:
    """Test the `Item` class."""

    @settings(max_examples=Times.THOROUGH)
    @given(title=infer, description=infer)
    def test_validation(self, title: str | None, description: str | None) -> None:
        """Test if the `@model_validator` of `Item` class works properly."""
        try:
            Item.model_validate({"title": title, "description": description})
        except Exception as e:
            if title is None and description is None:
                assert RSSModelError.empty_title_and_description in str(e)
