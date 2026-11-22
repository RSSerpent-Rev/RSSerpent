import shutil
import subprocess
import sys
from pathlib import Path

from .config import PluginLoadError

RUNTIME_DIR = Path("/tmp/rsserpent-runtime")


def installed_requirements(interpreter: str) -> set[str]:
    output = subprocess.check_output(["uv", "pip", "freeze", "--python", interpreter], text=True)
    return set(output.splitlines())


def prepare_plugin_environment(requirements: tuple[str, ...]) -> Path:
    seed = Path(sys.prefix)
    environment = RUNTIME_DIR / "venv"
    constraints = RUNTIME_DIR / "constraints.txt"
    interpreter = environment / Path(sys.executable).relative_to(seed)

    try:
        if RUNTIME_DIR.exists():
            shutil.rmtree(RUNTIME_DIR)
        RUNTIME_DIR.mkdir(mode=0o700)
        baseline = installed_requirements(sys.executable)
        constraints.write_bytes(
            subprocess.check_output(["uv", "pip", "list", "--format", "freeze", "--python", sys.executable])
        )
        shutil.copytree(seed, environment, symlinks=True)
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--no-sources",
                "--strict",
                "--python",
                str(interpreter),
                "--constraint",
                str(constraints),
                "--",
                *requirements,
            ],
            check=True,
        )
        subprocess.run(["uv", "pip", "check", "--python", str(interpreter)], check=True)
        installed = installed_requirements(str(interpreter))
    except (OSError, subprocess.CalledProcessError) as exception:
        message = "Could not prepare plugin dependencies. Check the installer output and plugin_requirements."
        raise PluginLoadError(message) from exception

    if not baseline <= installed:
        message = "Plugin dependencies changed packages from the core image. Check plugin_requirements."
        raise PluginLoadError(message)
    return interpreter
