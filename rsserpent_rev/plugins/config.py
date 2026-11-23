import os
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path

from pydantic import BaseModel, ValidationError

from ..models import Plugin


class PluginLoadError(RuntimeError):
    """A configured plugin or route cannot be registered."""


@dataclass(frozen=True, slots=True)
class PluginConfig:
    modules: tuple[str, ...] = ()
    requirements: tuple[str, ...] = ()
    settings: dict[str, dict[str, object]] = field(default_factory=dict, repr=False)
    environment: dict[str, dict[str, str]] = field(default_factory=dict)
    path: Path | None = field(default=None, compare=False)

    def settings_for(self, module: str, model: type[BaseModel] | None) -> BaseModel | None:
        raw = dict(self.settings.get(module, {}))
        environment = self.environment.get(module, {})
        if model is None:
            if raw or environment:
                message = f"Plugin {module} does not declare a settings model."
                raise PluginLoadError(message)
            return None

        for name, variable in environment.items():
            if name not in model.model_fields:
                message = f"Unknown settings field {name!r} for plugin {module}."
                raise PluginLoadError(message)
            value = os.environ.get(variable)
            if value is None:
                message = f"Plugin {module} requires environment variable {variable} for settings field {name!r}."
                raise PluginLoadError(message)
            raw[name] = value

        try:
            return model.model_validate(raw, extra="forbid", by_alias=False, by_name=True)
        except ValidationError as exception:
            errors = []
            for error in exception.errors(include_input=False, include_context=False, include_url=False):
                # Custom validation messages and nested input keys can carry configuration values.
                location = error["loc"]
                field_name = location[0] if location and location[0] in raw.keys() | model.model_fields.keys() else None
                reason = {"missing": "missing", "extra_forbidden": "unknown field"}.get(error["type"], "invalid")
                errors.append(f"{field_name or 'settings'} ({reason})")
            message = f"Invalid settings for plugin {module}: {', '.join(errors)}."
            raise PluginLoadError(message) from None
        except Exception:
            message = f"Settings validation failed for plugin {module}."
            raise PluginLoadError(message) from None


def read_config_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exception:
        message = f"Cannot read plugin configuration {str(path)!r}: {exception.strerror}"
        raise PluginLoadError(message) from None


def read_config(path: Path) -> PluginConfig:
    return parse_config(read_config_bytes(path), path)


def parse_config(body: bytes, path: Path) -> PluginConfig:
    try:
        config = tomllib.loads(body.decode())
    except UnicodeDecodeError:
        message = f"Cannot read plugin configuration {str(path)!r}: expected UTF-8."
        raise PluginLoadError(message) from None
    except tomllib.TOMLDecodeError as exception:
        message = (
            f"Cannot read plugin configuration {str(path)!r} at line {exception.lineno}, column {exception.colno}."
        )
        raise PluginLoadError(message) from None

    names = config.get("plugins", [])
    if not isinstance(names, list):
        message = f"In {str(path)!r}, plugins must be an array of Python module names."
        raise PluginLoadError(message)

    seen: set[str] = set()
    for name in names:
        if not isinstance(name, str) or not all(part.isidentifier() for part in name.split(".")):
            message = f"Invalid plugin module in {str(path)!r}. Use a dotted Python module name."
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
    settings = config.get("plugin_settings", {})
    environment = config.get("plugin_env", {})
    for key, tables in (("plugin_settings", settings), ("plugin_env", environment)):
        if not isinstance(tables, dict) or any(not isinstance(table, dict) for table in tables.values()):
            message = f"In {str(path)!r}, {key} must contain tables keyed by enabled plugin module."
            raise PluginLoadError(message)
        if unknown := tables.keys() - seen:
            message = f"In {str(path)!r}, {key} refers to an unconfigured module: {min(unknown)!r}."
            raise PluginLoadError(message)
    for module, table in environment.items():
        for name, variable in table.items():
            if not isinstance(variable, str) or not variable.isascii() or not variable.isidentifier():
                message = f"In {str(path)!r}, {module}.{name} must refer to an environment variable name."
                raise PluginLoadError(message)
    return PluginConfig(tuple(names), tuple(requirements), settings, environment, path)


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
