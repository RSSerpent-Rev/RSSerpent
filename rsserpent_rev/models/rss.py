from typing import TYPE_CHECKING, Any

import arrow
from arrow import Arrow
from pydantic import BaseModel, Field, root_validator

if TYPE_CHECKING:
    AnyUrl = str
    HttpUrl = str
else:
    from pydantic import AnyUrl, HttpUrl


class RSSModelError(ValueError):
    """Exception for `Feed` model validation error."""

    empty_title_and_description = "at least one of <title> or <description> must be present."


class Category(BaseModel):
    """Data model for the `<category>` field in an RSS 2.0 feed."""

    name: str
    domain: HttpUrl | None


class Enclosure(BaseModel):
    """Data model for the `<enclosure>` field in an RSS 2.0 feed."""

    length: int = 0
    type: str
    url: AnyUrl


class Guid(BaseModel):
    """Data model for the `<guid>` field in an RSS 2.0 feed."""

    is_perma_link: bool = True
    value: str


class Image(BaseModel):
    """Data model for the `<image>` field in an RSS 2.0 feed."""

    url: HttpUrl
    title: str
    link: HttpUrl
    width: int | None = 88
    height: int | None = 31
    description: str | None


class Source(BaseModel):
    """Data model for the `<source>` field in an RSS 2.0 feed."""

    name: str
    url: HttpUrl | None


class Item(BaseModel):
    """Data model for the `<item>` field in an RSS 2.0 feed."""

    title: str | None
    link: HttpUrl | None
    description: str | None
    author: str | None
    categories: list[Category] | None
    comments: HttpUrl | None
    enclosure: Enclosure | None
    guid: Guid | None
    pub_date: Arrow | None
    source: Source | None

    class Config:  # noqa: D106
        arbitrary_types_allowed = True

    @root_validator
    def validate(  # type: ignore[override]
        cls, # noqa: N805
        values: dict[str, Any],  # noqa: N805
    ) -> dict[str, Any]:
        """Ensure at least one of `<title>` or `<description>` is present."""
        title, description = values.get("title"), values.get("description")
        if title is None and description is None:
            raise RSSModelError(RSSModelError.empty_title_and_description)
        return values


class Feed(BaseModel):
    """Data model for RSS 2.0 feeds.

    See specification at https://www.rssboard.org/rss-specification.
    Note that some rarely used fields are not implemented:
    * `<cloud>`
    * `<rating>`
    * `<textInput>`
    * `<skipHours>`
    * `<skipDays>`
    """

    title: str
    link: HttpUrl
    description: str
    language: str | None
    copyright: str | None
    managing_editor: str | None
    web_master: str | None
    pub_date: Arrow | None = Field(default_factory=arrow.utcnow)
    last_build_date: Arrow | None = Field(default_factory=arrow.utcnow)
    categories: list[Category] | None
    generator: str | None = __package__.split(".")[0]
    docs: HttpUrl | None = "https://www.rssboard.org/rss-specification"
    ttl: int | None = 60
    image: Image | None
    items: list[Item] | None

    class Config:  # noqa: D106
        arbitrary_types_allowed = True
