from importlib.metadata import entry_points
from typing import cast

from ..models import Plugin

# https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/#using-package-metadata
plugins = [cast(Plugin, ep.load()) for ep in entry_points(group="rsserpent.plugin")]

__all__ = ("plugins",)
