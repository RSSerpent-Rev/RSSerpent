import os
import sys
from pathlib import Path

from starlette.applications import Starlette

from .main import create_app
from .plugins.config import PluginConfig, PluginLoadError, load_plugins, parse_config


def configured_app(config: PluginConfig) -> Starlette:
    return create_app(load_plugins(config.modules, config.path), config=config)


def serve(config: PluginConfig, *, host: str, port: int) -> None:
    import uvicorn

    uvicorn.run(configured_app(config), host=host, port=port)


if __name__ == "__main__":
    host, port, descriptor, path = sys.argv[1:]
    try:
        with os.fdopen(int(descriptor), "rb") as snapshot:
            config = parse_config(snapshot.read(), Path(path))
        serve(config, host=host, port=int(port))
    except PluginLoadError as exception:
        raise SystemExit(str(exception)) from None
