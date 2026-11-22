# 安装与启用插件

使用 CPython 3.14 或 3.15，将插件安装在 RSSerpent 0.3 所在的 Python 环境中。[官方插件仓库](https://github.com/RSSerpent-Rev/rsserpent-plugins)将 10 个官方插件构建为一个 `rsserpent-plugins` wheel。第三方插件可以从各自的 wheel、Git 仓库或 PyPI 安装。

在 `rsserpent.toml` 中列出要启用的 Python 模块。每个模块必须导出 `plugin` 对象。

```toml
plugins = ["rsserpent_plugins.bilibili", "my_rss_plugin"]
```

```sh
RSSERPENT_CONFIG=rsserpent.toml .venv/bin/uvicorn rsserpent_rev:app
```

未设置 `RSSERPENT_CONFIG` 或列表为空时，应用不注册插件路由。请只配置信任的模块。迁移已安装的第三方插件时，取原入口中 `:plugin` 前面的模块名即可。迁移官方插件时，安装聚合 wheel，再配置 `rsserpent_plugins` 下的对应模块。启用后仍可使用原有订阅 URL。内置示例通过 `rsserpent_rev.plugins.builtin` 启用，替代原来的 `RSSERPENT_ENABLE_EXAMPLES` 开关。

## 构建 Docker 镜像

如需运行默认 Compose 示例，在核心目录运行：

```sh
docker compose up --build
```

Compose 从固定的 Git 提交安装官方插件，并只读挂载 `docker/rsserpent.toml`。示例配置启用 Bilibili。自定义部署时，将插件安装依赖写入 `docker/requirements/custom.txt`，在 TOML 文件中列出实际要加载的模块。

```sh
RSSERPENT_PLUGIN_REQUIREMENTS=custom.txt RSSERPENT_CONFIG_FILE=./my-config.toml docker compose up --build
```

镜像在构建时安装依赖并检查它们与锁定的核心兼容。应用在启动时加载配置的模块。用 `docker build --target core .` 构建纯核心镜像。需要 Chromium 时，选择 `--target browser` 并提供相应的插件依赖和运行配置。在 Docker 之外用 `uv run --locked playwright install chromium` 安装 Chromium。
