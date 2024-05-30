from .builtin import plugin as builtin_plugin
from .externals import plugins as external_plugins

plugins = [builtin_plugin, *external_plugins]

for p in plugins:
    print(f"Loaded plugin: {p.name}, routers: {p.routers}")

__all__ = ("plugins",)
