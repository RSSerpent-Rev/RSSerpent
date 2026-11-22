import os
import tomllib
from importlib import import_module
from pathlib import Path

from ..models import Plugin


class PluginLoadError(RuntimeError):
    """A configured plugin or route cannot be registered."""


def load_plugins() -> list[tuple[Plugin, str]]:
    config = os.environ.get("RSSERPENT_CONFIG")
    if config is None:
        return []

    try:
        with Path(config).open("rb") as file:
            names = tomllib.load(file).get("plugins", [])
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exception:
        message = f"Cannot read plugin configuration {config!r}: {exception}"
        raise PluginLoadError(message) from exception

    if not isinstance(names, list):
        message = f"In {config!r}, plugins must be an array of Python module names."
        raise PluginLoadError(message)

    seen: set[str] = set()
    for name in names:
        if not isinstance(name, str) or not all(part.isidentifier() for part in name.split(".")):
            message = f"Invalid plugin module {name!r} in {config!r}."
            raise PluginLoadError(message)
        if name in seen:
            message = f"Duplicate plugin module {name!r} in {config!r}."
            raise PluginLoadError(message)
        seen.add(name)

    plugins = []
    for name in names:
        source = f"{name} (in {config!r})"
        try:
            plugin = getattr(import_module(name), "plugin", None)
        except Exception as exception:
            message = f"Cannot import plugin {source}: {exception}"
            raise PluginLoadError(message) from exception
        if not isinstance(plugin, Plugin):
            message = f"Expected {source} to export a Plugin instance as 'plugin'."
            raise PluginLoadError(message)
        plugins.append((plugin, source))
    return plugins
