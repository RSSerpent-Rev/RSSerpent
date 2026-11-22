# 安装插件

使用 uv 和 CPython 3.14 或 3.15。插件是带有 `rsserpent.plugin` 入口的 Python 包。启动服务前，将插件安装在核心所在的环境中。

## 选装官方插件

[官方插件仓库](https://github.com/RSSerpent-Rev/rsserpent-plugins)使用独立的 uv workspace。完整 Git 提交和子目录共同指定一个插件版本。

```text
rsserpent-plugin-bilibili @ git+https://github.com/RSSerpent-Rev/rsserpent-plugins.git@<commit>#subdirectory=plugins/bilibili
```

把 `<commit>` 替换为已发布的完整 Git 提交。用 `uv pip install` 将该依赖安装到服务环境。核心需使用兼容的 0.2.x 分发版或 wheel。声明同一入口的第三方插件可以继续使用原包名和仓库地址。

## 构建 Docker 镜像

把插件依赖写到 `docker/requirements/` 下的文件，构建时用 `RSSERPENT_PLUGIN_REQUIREMENTS` 指定文件名。

```sh
RSSERPENT_PLUGIN_REQUIREMENTS=custom.txt docker compose up --build
```

也可以直接构建。

```sh
docker build --build-arg RSSERPENT_PLUGIN_REQUIREMENTS=custom.txt -t rsserpent-local .
```

镜像从 `uv.lock` 安装核心及其依赖，并在构建时安装和检查插件。服务启动时无需下载依赖。旧部署如仍挂载 `/app/rsserpent.txt`，请移除该挂载。官方 workspace 发布前，Compose 默认示例继续使用原 Bilibili 仓库中已能取得的固定提交。

需要 Chromium 的插件可在构建命令加上 `--target browser`。对应的发布镜像为 `ghcr.io/rsserpent-rev/rsserpent-browser`。本地直接运行时，用 `uv run --locked playwright install chromium` 安装 Chromium。
