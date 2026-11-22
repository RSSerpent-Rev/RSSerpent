from ..models import Plugin
from .builtin import plugin as builtin_plugin
from .externals import load_plugins

__all__ = ("plugins",)


def __getattr__(name: str) -> list[Plugin]:
    if name == "plugins":
        return [builtin_plugin, *(plugin for plugin, _ in load_plugins())]
    raise AttributeError(name)
