from pydantic import AwareDatetime, BaseModel


class QueryString(BaseModel):
    """Data model for the query string of a URL."""

    title_include: str | None = None
    title_exclude: str | None = None
    description_include: str | None = None
    description_exclude: str | None = None
    category_include: str | None = None
    category_exclude: str | None = None
    date_before: AwareDatetime | None = None
    date_after: AwareDatetime | None = None
    limit: int | None = None
