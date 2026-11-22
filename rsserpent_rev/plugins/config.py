import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

from ..models import Plugin


class PluginLoadError(RuntimeError):
    """A configured plugin or route cannot be registered."""


@dataclass(frozen=True, slots=True)
class PluginConfig:
    modules: tuple[str, ...] = ()
    requirements: tuple[str, ...] = ()


def read_config(path: Path) -> PluginConfig:
    try:
        with path.open("rb") as file:
            config = tomllib.load(file)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exception:
        message = f"Cannot read plugin configuration {str(path)!r}: {exception}"
        raise PluginLoadError(message) from exception

    names = config.get("plugins", [])
    if not isinstance(names, list):
        message = f"In {str(path)!r}, plugins must be an array of Python module names."
        raise PluginLoadError(message)

    seen: set[str] = set()
    for name in names:
        if not isinstance(name, str) or not all(part.isidentifier() for part in name.split(".")):
            message = f"Invalid plugin module {name!r} in {str(path)!r}."
            raise PluginLoadError(message)
        if name in seen:
            message = f"Duplicate plugin module {name!r} in {str(path)!r}."
            raise PluginLoadError(message)
        seen.add(name)

    requirements = config.get("plugin_requirements", [])
    if not isinstance(requirements, list) or any(
        not isinstance(item, str)
        or not item.strip()
        or item.lstrip().startswith("-")
        or any(character in item for character in "\r\n\0")
        for item in requirements
    ):
        message = f"In {str(path)!r}, plugin_requirements must be an array of individual package requirements."
        raise PluginLoadError(message)
    return PluginConfig(tuple(names), tuple(requirements))


def load_plugins(names: Sequence[str], path: Path | None = None) -> list[Plugin]:
    plugins = []
    for name in names:
        source = f"{name} (in {str(path)!r})" if path else name
        try:
            plugin = getattr(import_module(name), "plugin", None)
        except Exception as exception:
            message = f"Cannot import plugin {source}: {exception}"
            raise PluginLoadError(message) from exception
        if not isinstance(plugin, Plugin):
            message = f"Expected {source} to export a Plugin instance as 'plugin'."
            raise PluginLoadError(message)
        plugins.append(plugin)
    return plugins
