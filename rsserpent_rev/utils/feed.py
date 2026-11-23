import copy
import hashlib
import time
from calendar import timegm
from datetime import UTC, datetime
from io import BytesIO

import feedgen
import feedparser
import regex
from feedgen.feed import FeedGenerator
from feedparser import FeedParserDict

from ..models import QueryString

MAX_PATTERN_LENGTH = 512
FILTER_TIMEOUT = 0.05
FILTER_FIELDS = ("title", "description", "category")


class FeedFilterError(ValueError):
    """A filter is invalid or exceeded its time budget."""

    too_long = f"Regular expression exceeds {MAX_PATTERN_LENGTH} characters"
    invalid_pattern = "Invalid regular expression"
    timeout = "Feed filtering exceeded its time budget"


class FeedParseError(ValueError):
    """Downloaded bytes do not contain a usable RSS or Atom feed."""

    invalid_feed = "Upstream returned an invalid RSS or Atom feed."


def _date(source: FeedParserDict, field: str) -> datetime | None:
    value = source.get(field)
    return datetime.fromtimestamp(timegm(value), UTC) if value is not None else None


def _authors(source: FeedParserDict) -> list[dict[str, str]]:
    authors = []
    for author in source.get("authors", []):
        name = author.get("name") or author.get("email")
        if name:
            details = {"name": name}
            if email := author.get("email"):
                details["email"] = email
            if uri := author.get("href"):
                details["uri"] = uri
            authors.append(details)
    return authors


def parse_feed(body: bytes, *, base_url: str) -> FeedGenerator:
    """Parse downloaded RSS or Atom bytes and resolve relative URLs against base_url.

    The parser reads only the provided bytes. Use the download's final URL as
    the base for relative links and as a fallback channel link.
    """
    if not isinstance(body, bytes):
        raise FeedParseError(FeedParseError.invalid_feed)
    parsed = feedparser.parse(
        BytesIO(body),
        response_headers={"content-location": base_url},
        resolve_relative_uris=True,
        sanitize_html=True,
    )
    source = parsed.feed
    if not parsed.get("version", "").startswith(("rss", "atom")) or not source.get("title"):
        raise FeedParseError(FeedParseError.invalid_feed)

    fg = FeedGenerator()
    fg.title(source.title)
    fg.description(source.get("subtitle") or source.title)
    fg.id(source.get("id") or source.get("link") or base_url)
    fg.link(href=source.get("link") or base_url, rel="alternate")
    if authors := _authors(source):
        fg.author(authors)
    feed_published = _date(source, "published_parsed")
    feed_updated = _date(source, "updated_parsed") or feed_published
    parsed_at = datetime.now(UTC)
    fg.updated(feed_updated or parsed_at)
    if feed_published is not None:
        fg.pubDate(feed_published)

    for item in parsed.entries:
        content = next((part for part in item.get("content", []) if part.get("value")), None)
        summary = item.get("summary")
        if not (item.get("title") or summary or content):
            raise FeedParseError(FeedParseError.invalid_feed)
        entry = fg.add_entry(order="append")
        if title := item.get("title"):
            entry.title(title)
        if summary:
            entry.description(summary, isSummary=True)
        if content:
            content_type = content.get("type", "text/plain")
            entry.content(
                content.value, type={"text/html": "html", "text/plain": "text"}.get(content_type, content_type)
            )
            if not (item.get("title") or summary):
                entry.description(content.value)
        if link := item.get("link"):
            entry.link(href=link, rel="alternate")
        if identifier := item.get("id"):
            entry.guid(identifier, permalink=bool(item.get("guidislink")))
        if authors := _authors(item):
            entry.author(authors)
        for tag in item.get("tags", []):
            if term := tag.get("term"):
                entry.category(term=term, scheme=tag.get("scheme"), label=tag.get("label"))
        if enclosure := next((value for value in item.get("enclosures", []) if value.get("href")), None):
            entry.enclosure(
                enclosure.href, enclosure.get("length", 0), enclosure.get("type", "application/octet-stream")
            )
        published = _date(item, "published_parsed")
        if published is not None:
            entry.published(published)
        entry.updated(_date(item, "updated_parsed") or published or feed_updated or parsed_at)
    return fg


def compile_filters(qs: QueryString) -> dict[str, regex.Pattern[str]]:
    patterns = {}
    for field in FILTER_FIELDS:
        for condition in ("include", "exclude"):
            name = f"{field}_{condition}"
            value = getattr(qs, name)
            if value is None:
                continue
            if len(value) > MAX_PATTERN_LENGTH:
                raise FeedFilterError(FeedFilterError.too_long)
            try:
                patterns[name] = regex.compile(value, regex.VERSION0)
            except (regex.error, RecursionError) as exception:
                raise FeedFilterError(FeedFilterError.invalid_pattern) from exception
    return patterns


def filter_fg(
    fg: feedgen.feed.FeedGenerator,
    qs: QueryString,
    *,
    patterns: dict[str, regex.Pattern[str]] | None = None,
) -> None:
    if patterns is None:
        patterns = compile_filters(qs)
    if not (patterns or qs.date_before or qs.date_after or qs.limit is not None):
        return

    deadline = time.monotonic() + FILTER_TIMEOUT

    def remaining() -> float:
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise FeedFilterError(FeedFilterError.timeout)
        return seconds

    def matches(entry: feedgen.entry.FeedEntry) -> bool:
        remaining()
        date = entry.pubDate()
        if qs.date_before is not None and (date is None or date >= qs.date_before):
            return False
        if qs.date_after is not None and (date is None or date <= qs.date_after):
            return False

        for name, pattern in patterns.items():
            field, _, condition = name.partition("_")
            values: list[str | None]
            if field == "category":
                values = [category["term"] for category in (entry.category() or ())]
            elif field == "title":
                values = [entry.title()]
            else:
                values = [entry.description()]
            found = any(value is not None and pattern.search(value, timeout=remaining()) for value in values)
            if found != (condition == "include"):
                return False
        return True

    entries: list[feedgen.entry.FeedEntry] = []
    try:
        for entry in fg.entry():
            if qs.limit is not None and len(entries) >= qs.limit:
                break
            if matches(entry):
                entries.append(entry)
    except TimeoutError as exception:
        raise FeedFilterError(FeedFilterError.timeout) from exception
    fg.entry(entries, replace=True)


def gen_ids_for(fg: feedgen.feed.FeedGenerator, *, atom: bool = False) -> None:
    if not fg.id():
        fg.id(hashlib.md5(fg.title().encode()).hexdigest())
    entries = []
    for entry in fg.entry():
        missing_atom_title = atom and not entry.title()
        missing_atom_content = (
            atom and not entry.content() and not any(link.get("rel") == "alternate" for link in (entry.link() or ()))
        )
        if not entry.id() or missing_atom_title or missing_atom_content:
            entry = copy.copy(entry)
        if not entry.id():
            hash_content = (entry.title() or "") + (entry.description() or "")
            entry.id(hashlib.md5(hash_content.encode()).hexdigest())
        if missing_atom_title:
            entry.title(entry.description() or "Untitled")
        if missing_atom_content:
            entry.content(entry.description() or entry.title())
        entries.append(entry)
    fg.entry(entries, replace=True)
