from json import JSONDecodeError
from typing import Any

import httpx
from lxml.etree import ParserError
from playwright.async_api import async_playwright
from playwright.async_api._generated import Page
from pyquery import PyQuery


class Browser:
    """Wrap playwright browser as a context manager."""

    async def __aenter__(self) -> Page:
        """Enter the context manager."""
        self.context = await async_playwright().start()
        self.browser = await self.context.chromium.launch()
        return await self.browser.new_page()

    async def __aexit__(self, *_: Any) -> None:
        """Leave the context manager."""
        await self.browser.close()
        await self.context.stop()


class HTTPClient(httpx.AsyncClient):
    """Wrap `httpx.AsyncClient` with default headers."""

    def build_request(self, *args: Any, **kwds: Any) -> httpx.Request:
        """Set the default Referer for requests."""
        request = super().build_request(*args, **kwds)
        url = request.url
        request.headers.setdefault("Host", url.host)
        request.headers.setdefault("Referer", f"{url.scheme}://{url.host}")
        return request

    async def get_json(self, url: str | httpx.URL, **options: Any) -> Any:
        """Make a GET request and decode a successful response as JSON."""
        response = (await self.get(url, **options)).raise_for_status()
        try:
            return response.json()
        except JSONDecodeError, UnicodeDecodeError:
            raise UpstreamDecodeError(UpstreamDecodeError.invalid_json) from None

    async def get_html(self, url: str | httpx.URL, **options: Any) -> PyQuery:
        """Make a GET request and parse a successful response for CSS queries."""
        response = (await self.get(url, **options)).raise_for_status()
        try:
            return PyQuery(response.text, parser="html")
        except ParserError, ValueError:
            raise UpstreamDecodeError(UpstreamDecodeError.invalid_html) from None


class UpstreamDecodeError(httpx.HTTPError):
    """A successful upstream response could not be decoded."""

    invalid_json = "Upstream returned invalid JSON."
    invalid_html = "Upstream returned invalid HTML."
