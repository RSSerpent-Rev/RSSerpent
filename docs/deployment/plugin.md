# Deploy with plugins

The official image reads a TOML file at `/etc/rsserpent/rsserpent.toml`. Create `rsserpent.toml` with the packages to install and the Python modules to enable.

```toml
plugin_requirements = ["my-rss-plugin==0.1.0"]
plugins = ["my_rss_plugin"]
```

Use a requirement for each package you need. Each enabled module must export a `plugin` object. Use packages and Git repositories you trust.

Run Docker from the directory that contains the TOML file.

```sh
docker run -d --name rsserpent -p 8000:8000 \
  --mount "type=bind,source=$PWD/rsserpent.toml,target=/etc/rsserpent/rsserpent.toml,readonly" \
  ghcr.io/rsserpent-rev/rsserpent:main
```

Open [the route list](http://localhost:8000/all_routes). If your plugin defines `/my-feed`, subscribe to `/my-feed.rss` or `/my-feed.atom`. When you use the Compose file from the repository, edit `docker/rsserpent.toml` and run `docker compose up -d`.

## Install from Git

Use a full commit SHA. For a package in a repository subdirectory, add `#subdirectory=` followed by the path to the directory that contains its `pyproject.toml`.

```toml
plugin_requirements = [
  "my-rss-plugin @ git+https://github.com/OWNER/my-rss-plugin.git@COMMIT_SHA#subdirectory=plugins/my-rss-plugin",
]
plugins = ["my_rss_plugin"]
```

## Enable an official plugin

Add the official package requirement and list the modules you want to enable. Use the [official module table](https://github.com/RSSerpent-Rev/rsserpent-plugins#official-modules) to find their names.

```toml
plugin_requirements = [
  "rsserpent-plugins @ git+https://github.com/RSSerpent-Rev/rsserpent-plugins.git@5f13e7549843a13baa37dc3a3b09bf437b6305d1",
]
plugins = ["rsserpent_plugins.bilibili"]
```

For plugins that use Chromium, use `ghcr.io/rsserpent-rev/rsserpent-browser:main` in the same Docker command. When you publish a plugin, test that its Python packages and required system libraries work in the image.

## Configure plugin settings

Use the enabled module name as the table key. `plugin_settings` sets fields defined by the plugin. `plugin_env` maps each field to a required environment variable and overrides the same TOML field. Pass the named variable to Docker with `--env MY_RSS_TOKEN` or add it to the Compose service environment. Keep access tokens in environment variables.

```toml
[plugin_settings.my_private_plugin]
title = "Announcements"

[plugin_env.my_private_plugin]
token = "MY_RSS_TOKEN"
```

## Restart and diagnose

For a local configuration check, install the plugin packages in your development environment and run `rsserpent check --config rsserpent.toml`.

The container installs the configured packages before it starts the web server. It uses the core image's package versions as constraints. A conflict stops startup. Read `docker logs rsserpent` to identify a requirement or module that failed.

Package downloads require network access when the cache lacks the artifacts. A new container can need to download packages again. An empty configuration starts the core and skips all plugin installation.

After editing the TOML, remove the old container with `docker rm -f rsserpent` and run the Docker command again. With Compose, run `docker compose up -d --force-recreate`.
