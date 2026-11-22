from typing import Any

import httpx
from playwright.async_api import async_playwright
from playwright.async_api._generated import Page


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
