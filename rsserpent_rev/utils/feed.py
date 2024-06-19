import hashlib
import re

import feedgen
from starlette.requests import Request


def filter_fg(fg: feedgen.feed.FeedGenerator, request: Request) -> None:
    p = request.query_params
    new_entry = [
        entry
        for entry in fg.entry()
        if ("title_include" not in p or re.search(p["title_include"], entry.title()))
        and ("title_exclude" not in p or not re.search(p["title_exclude"], entry.title()))
        and ("description_include" not in p or re.search(p["description_include"], entry.description()))
        and ("description_exclude" not in p or not re.search(p["description_exclude"], entry.description()))
        and (
            "category_include" not in p
            or any(re.search(p["category_include"], category["term"]) for category in entry.category())
        )
        and (
            "category_exclude" not in p
            or not any(re.search(p["category_exclude"], category["term"]) for category in entry.category())
        )
    ]
    if "limit" in p:
        new_entry = new_entry[: int(p["limit"])]
    fg.entry(new_entry, replace=True)


def gen_ids_for(fg: feedgen.feed.FeedGenerator) -> None:
    if not fg.id():
        fg.id(hashlib.md5(fg.title().encode()).hexdigest())
    for entry in fg.entry():
        if not entry.id():
            hash_content = entry.title() + entry.description()
            entry.id(hashlib.md5(hash_content.encode()).hexdigest())
