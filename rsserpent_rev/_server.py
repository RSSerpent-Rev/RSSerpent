import sys
from collections.abc import Sequence

import uvicorn

from .main import create_app
from .plugins.config import PluginLoadError, load_plugins


def serve(modules: Sequence[str], *, host: str, port: int) -> None:
    uvicorn.run(create_app(load_plugins(modules), sources=modules), host=host, port=port)


if __name__ == "__main__":
    host, port, *modules = sys.argv[1:]
    try:
        serve(modules, host=host, port=int(port))
    except PluginLoadError as exception:
        raise SystemExit(str(exception)) from None
