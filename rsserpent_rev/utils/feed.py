import hashlib
import re

import feedgen

from ..models import QueryString


def filter_fg(fg: feedgen.feed.FeedGenerator, qs: QueryString) -> None:
    new_entry = [
        entry
        for entry in fg.entry()
        if (qs.title_include is None or re.search(qs.title_include, entry.title()))
        and (qs.title_exclude is None or not re.search(qs.title_exclude, entry.title()))
        and (qs.description_include is None or re.search(qs.description_include, entry.description()))
        and (qs.description_exclude is None or not re.search(qs.description_exclude, entry.description()))
        and (
            qs.category_include is None
            or any(re.search(qs.category_include, category["term"]) for category in entry.category())
        )
        and (
            qs.category_exclude is None
            or not any(re.search(qs.category_exclude, category["term"]) for category in entry.category())
        )
        and (qs.date_before is None or entry.pubDate() < qs.date_before)
        and (qs.date_after is None or entry.pubDate() > qs.date_after)
    ]
    if qs.limit:
        new_entry = new_entry[: int(qs.limit)]
    fg.entry(new_entry, replace=True)


def gen_ids_for(fg: feedgen.feed.FeedGenerator) -> None:
    if not fg.id():
        fg.id(hashlib.md5(fg.title().encode()).hexdigest())
    for entry in fg.entry():
        if not entry.id():
            hash_content = entry.title() + entry.description()
            entry.id(hashlib.md5(hash_content.encode()).hexdigest())
