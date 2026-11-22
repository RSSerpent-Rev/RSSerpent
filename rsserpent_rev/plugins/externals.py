from importlib.metadata import EntryPoint, entry_points

from ..models import Plugin


class PluginLoadError(RuntimeError):
    """An entry point or active route cannot be registered."""


def entry_source(entry: EntryPoint) -> str:
    distribution = entry.dist
    name = distribution.name if distribution is not None else "unknown distribution"
    return f"{name} ({entry.name} = {entry.value})"


def load_plugins() -> list[tuple[Plugin, str]]:
    plugins = []
    for entry in sorted(entry_points(group="rsserpent.plugin"), key=entry_source):
        source = entry_source(entry)
        try:
            plugin = entry.load()
        except Exception as exception:
            message = f"Cannot load plugin entry point from {source}."
            raise PluginLoadError(message) from exception
        if not isinstance(plugin, Plugin):
            message = f"Expected a Plugin instance from {source}."
            raise PluginLoadError(message)
        plugins.append((plugin, source))
    return plugins
