# 配置插件并部署

官方镜像从 `/etc/rsserpent/rsserpent.toml` 读取配置。创建 `rsserpent.toml`，填入要安装的包和要启用的 Python 模块。

```toml
plugin_requirements = ["my-rss-plugin==0.1.0"]
plugins = ["my_rss_plugin"]
```

每个需要安装的包写一条依赖。每个启用的模块必须导出 `plugin` 对象。请选择你信任的包和 Git 仓库。

在 TOML 所在目录启动容器。

```sh
docker run -d --name rsserpent -p 8000:8000 \
  --mount "type=bind,source=$PWD/rsserpent.toml,target=/etc/rsserpent/rsserpent.toml,readonly" \
  ghcr.io/rsserpent-rev/rsserpent:main
```

打开[路由列表](http://localhost:8000/all_routes)确认插件已启用。如果插件定义了 `/my-feed`，可以订阅 `/my-feed.rss` 或 `/my-feed.atom`。使用仓库中的 Compose 文件时，编辑 `docker/rsserpent.toml`，然后运行 `docker compose up -d`。

## 从 Git 安装

使用完整的提交 SHA。包位于仓库的子目录时，在地址末尾加上 `#subdirectory=` 和包含它的 `pyproject.toml` 的目录路径。

```toml
plugin_requirements = [
  "my-rss-plugin @ git+https://github.com/OWNER/my-rss-plugin.git@COMMIT_SHA#subdirectory=plugins/my-rss-plugin",
]
plugins = ["my_rss_plugin"]
```

## 启用官方插件

加上官方聚合包的依赖，并列出要启用的模块。模块名称见[官方插件模块表](https://github.com/RSSerpent-Rev/rsserpent-plugins#official-modules)。

```toml
plugin_requirements = [
  "rsserpent-plugins @ git+https://github.com/RSSerpent-Rev/rsserpent-plugins.git@5f13e7549843a13baa37dc3a3b09bf437b6305d1",
]
plugins = ["rsserpent_plugins.bilibili"]
```

插件需要 Chromium 时，把 Docker 命令中的镜像换成 `ghcr.io/rsserpent-rev/rsserpent-browser:main`。发布插件前，请用目标镜像验证 Python 依赖和所需系统库。

## 填写插件设置

配置表以启用的模块名为键。`plugin_settings` 填写插件声明的字段。`plugin_env` 把字段映射到必需的环境变量，优先于 TOML 中的同名字段。通过 `--env MY_RSS_TOKEN` 把变量传入 Docker，或将它加入 Compose 服务的环境配置。访问令牌适合通过环境变量传入。

```toml
[plugin_settings.my_private_plugin]
title = "Announcements"

[plugin_env.my_private_plugin]
token = "MY_RSS_TOKEN"
```

## 重启与排查

在本地检查配置时，先在开发环境安装插件包，再运行 `rsserpent check --config rsserpent.toml`。

容器在启动 Web 服务前安装配置中的包，并按镜像内的核心依赖版本检查冲突。遇到冲突时，容器退出。用 `docker logs rsserpent` 查看失败的依赖或模块。

缓存缺少对应包时，下载需要联网。重建容器时也可能重新下载。空配置启动纯核心，跳过插件安装。

修改 TOML 后，用 `docker rm -f rsserpent` 移除旧容器，再运行启动命令。用 Compose 部署时，运行 `docker compose up -d --force-recreate`。
