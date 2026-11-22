# Install plugins

Use uv with CPython 3.14 or 3.15. A plugin is a Python package with an `rsserpent.plugin` entry point. Install it in the same environment as the core before starting the service.

## Select an official plugin

The [official plugin repository](https://github.com/RSSerpent-Rev/rsserpent-plugins) is an independent uv workspace. A fixed Git commit and a subdirectory select one release:

```text
rsserpent-plugin-bilibili @ git+https://github.com/RSSerpent-Rev/rsserpent-plugins.git@<commit>#subdirectory=plugins/bilibili
```

Replace `<commit>` with the full published Git commit. Install this requirement with `uv pip install` in the service environment. Use a compatible core 0.2.x release or install its wheel. Third-party plugins that publish the same entry point work with their existing package names and repository URLs.

## Build a Docker image

Place the requirement in a file under `docker/requirements/`. Set `RSSERPENT_PLUGIN_REQUIREMENTS` to the filename at build time:

```sh
RSSERPENT_PLUGIN_REQUIREMENTS=custom.txt docker compose up --build
```

For a build outside Compose:

```sh
docker build --build-arg RSSERPENT_PLUGIN_REQUIREMENTS=custom.txt -t rsserpent-local .
```

The core and its dependencies come from `uv.lock`. The image installs plugins and checks their dependencies during the build. The service starts without downloading packages. Remove the old `/app/rsserpent.txt` volume mount if your deployment still has it. The default Compose example uses the reachable Bilibili commit in its original repository until the official workspace is published.

For plugins that require Chromium, add `--target browser` to the build command. The published browser image is `ghcr.io/rsserpent-rev/rsserpent-browser`. For local use outside Docker, install Chromium with `uv run --locked playwright install chromium`.
