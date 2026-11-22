import copy
import hashlib
import time

import feedgen
import regex

from ..models import QueryString

MAX_PATTERN_LENGTH = 512
FILTER_TIMEOUT = 0.05
FILTER_FIELDS = ("title", "description", "category")


class FeedFilterError(ValueError):
    """A filter is invalid or exceeded its time budget."""

    too_long = f"Regular expression exceeds {MAX_PATTERN_LENGTH} characters"
    invalid_pattern = "Invalid regular expression"
    timeout = "Feed filtering exceeded its time budget"


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
