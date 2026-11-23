import argparse
import os
from pathlib import Path
from tempfile import TemporaryFile

from ._server import serve
from .plugins.config import PluginConfig, PluginLoadError, parse_config, read_config_bytes
from .plugins.install import prepare_plugin_environment

CONTAINER_CONFIG = Path("/etc/rsserpent/rsserpent.toml")


def main() -> None:
    parser = argparse.ArgumentParser(prog="rsserpent")
    parser.add_argument("--config", type=Path, help="Path to the plugin TOML file.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--container", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    path = args.config
    if path is None and args.container and CONTAINER_CONFIG.exists():
        path = CONTAINER_CONFIG

    try:
        body = read_config_bytes(path) if path is not None else b""
        config = parse_config(body, path) if path is not None else PluginConfig()
        if args.container and path is not None and config.requirements:
            python = prepare_plugin_environment(config.requirements)
            os.environ["PATH"] = os.pathsep.join((str(python.parent), os.environ.get("PATH", "")))
            os.environ["VIRTUAL_ENV"] = str(python.parent.parent)
            # Pass the same bytes to the new interpreter without exposing values in argv.
            with TemporaryFile() as snapshot:
                snapshot.write(body)
                snapshot.seek(0)
                descriptor = snapshot.fileno()
                os.set_inheritable(descriptor, True)
                os.execv(
                    python,
                    [str(python), "-m", "rsserpent_rev._server", args.host, str(args.port), str(descriptor), str(path)],
                )
        serve(config, host=args.host, port=args.port)
    except PluginLoadError as exception:
        raise SystemExit(str(exception)) from None


if __name__ == "__main__":
    main()
