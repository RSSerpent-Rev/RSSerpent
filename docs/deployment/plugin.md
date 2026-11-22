# Install and enable plugins

Install plugins in the same Python environment as RSSerpent 0.3. Use CPython 3.14 or 3.15. The [official plugin repository](https://github.com/RSSerpent-Rev/rsserpent-plugins) builds one `rsserpent-plugins` wheel for all ten official modules. Third-party plugins can use their own wheels, Git repositories or PyPI packages.

In `rsserpent.toml`, list the Python modules to enable. Each module must export a `plugin` object:

```toml
plugins = ["rsserpent_plugins.bilibili", "my_rss_plugin"]
```

```sh
RSSERPENT_CONFIG=rsserpent.toml .venv/bin/uvicorn rsserpent_rev:app
```

Without `RSSERPENT_CONFIG` or with an empty list, the app starts with no plugin routes. Only list modules whose code you trust. To migrate an installed third-party plugin, use the module name before `:plugin` in its old entry point. For the official plugins, install the aggregate wheel and use the corresponding modules under `rsserpent_plugins`. Existing feed URLs work after you enable the corresponding module. For built-in examples, list `rsserpent_rev.plugins.builtin` in place of the old `RSSERPENT_ENABLE_EXAMPLES` switch.

## Build a Docker image

For the default Compose example, run this command from the core checkout:

```sh
docker compose up --build
```

Compose installs the official plugins from a fixed Git commit and mounts `docker/rsserpent.toml` read-only. The example enables Bilibili. For another setup, put the plugin package requirements in `docker/requirements/custom.txt` and the module names in a TOML file.

```sh
RSSERPENT_PLUGIN_REQUIREMENTS=custom.txt RSSERPENT_CONFIG_FILE=./my-config.toml docker compose up --build
```

The image installs packages at build time and checks that they work with the locked core. The application loads the configured modules at startup. Run `docker build --target core .` for a core-only image. For plugins that require Chromium, use `--target browser` and the appropriate plugin requirements and runtime configuration. Outside Docker, install Chromium with `uv run --locked playwright install chromium`.
