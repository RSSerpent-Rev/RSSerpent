import argparse
import sys
from pathlib import Path

from ._server import configured_app
from .plugins.config import PluginLoadError, read_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="rsserpent")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Check plugin configuration and routes.")
    check.add_argument("--config", type=Path, required=True, help="Path to the plugin TOML file.")
    args = parser.parse_args()

    try:
        app = configured_app(read_config(args.config))
    except PluginLoadError as exception:
        check.exit(1, f"{exception}\n")
    if app.state.diagnostics:
        check.exit(1, f"Check failed with {len(app.state.diagnostics)} route diagnostics.\n")
    count = sum(len(routes) for routes in app.state.feed_routes.values())
    sys.stdout.write(f"Checked {len(app.state.plugins)} plugins and {count} feed routes.\n")
