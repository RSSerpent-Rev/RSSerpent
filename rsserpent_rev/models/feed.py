import re
from typing import TYPE_CHECKING, Annotated, Literal, Self
from uuid import NAMESPACE_URL, uuid5

from feedgen.feed import FeedGenerator
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

if TYPE_CHECKING:
    HttpUrl = str
else:
    from pydantic import HttpUrl


type NonEmptyText = Annotated[str, StringConstraints(min_length=1)]
type Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _identifier(value: str, namespace: str) -> str:
    if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9+.-]*:\S+", value):
        return value
    return uuid5(NAMESPACE_URL, repr((namespace, value))).urn


class Entry(BaseModel):
    """An entry that the core can publish as RSS or Atom."""

    model_config = ConfigDict(extra="forbid")

    title: NonEmptyText | None = None
    link: HttpUrl | None = None
    id: Identifier | None = None
    summary: NonEmptyText | None = None
    author: NonEmptyText | None = None
    categories: list[NonEmptyText] = Field(default_factory=list)
    content: NonEmptyText | None = None
    content_type: Literal["text", "html"] = "text"
    published_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        if not any(value and value.strip() for value in (self.title, self.summary, self.content)):
            message = "An entry needs a title, summary, or content."
            raise ValueError(message)
        return self


class Feed(BaseModel):
    """The subscription data returned by a provider."""

    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    link: HttpUrl
    description: NonEmptyText | None = None
    id: Identifier | None = None
    published_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None
    entries: list[Entry] = Field(default_factory=list)

    def to_feedgen(self) -> FeedGenerator:
        feed = FeedGenerator()
        feed.title(self.title)
        link = str(self.link)
        feed.link(href=link, rel="alternate")
        feed.description(self.description or self.title)
        if self.id is not None:
            feed.id(_identifier(self.id, link))

        update = self.updated_at or self.published_at or feed.updated()
        feed.pubDate(self.published_at)
        feed.updated(update)

        if any(data.author for data in self.entries):
            feed.load_extension("dc", atom=False)
        for data in self.entries:
            entry = feed.add_entry(order="append")
            entry.title(data.title)
            if data.id is not None:
                entry.id(_identifier(data.id, feed.id() or link))
            if data.link is not None:
                entry.link(href=str(data.link), rel="alternate")
            entry.summary(data.summary, type="text")
            entry.content(data.content, type=data.content_type)
            if data.author:
                entry.author(name=data.author)
                entry.dc.dc_creator(data.author)
            for category in data.categories:
                entry.category(term=category)
            entry.published(data.published_at)
            entry.updated(data.updated_at or data.published_at or update)
        return feed
