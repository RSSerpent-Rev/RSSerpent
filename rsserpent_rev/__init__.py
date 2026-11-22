import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.applications import Starlette

    from .main import app as app

if sys.implementation.name != "cpython" or sys.version_info[:2] not in {(3, 14), (3, 15)}:
    message = "RSSerpent supports CPython 3.14 and 3.15."
    raise RuntimeError(message)

__all__ = ("app",)


def __getattr__(name: str) -> Starlette:
    # Plugins can import the models before the app loads configured modules.
    if name == "app":
        from .main import app

        return app
    raise AttributeError(name)
