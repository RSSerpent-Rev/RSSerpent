# 安装插件

## 其他部署模板

!!!warning
    注意不要混淆 **`rsserpent.txt`** 和 `requirements.txt`。

默认的模板功能并不丰富，你需要将添加你需要的 RSSerpent 插件到 `rsserpent.txt` 文件中。你可以使用 [git](https://git-scm.com/) 将仓库克隆到本地以编辑 `rsserpent.txt`，或者也可以使用 GitHub 网页进行编辑。

编写 `rsserpent.txt` 时的一些注意事项：

- 编写 `rsserpent.txt` 和为任何 Python 项目编写 `requirements.txt` 是一样的；
- 不要修改 `requirements.txt`，你只应该修改 `rsserpent.txt`。GitHub Actions 会负责自动更新你的 `requirements.txt` 并部署实例；
- 每周一次，或者每次你修改仓库内容并提交时，会进行自动更新/部署；
- 我们推荐你在 `rsserpent.txt` 中不要指定任何版本，这样 [GitHub Actions](https://github.com/features/actions) 能帮助你自动将依赖更新到最新版；

    ```python
    # PyPI
    rsserpent
    # Git
    rsserpent-plugin-bilibili @ git+https://github.com/RSSerpent-Rev/RSSerpent-plugin-bilibili.git
    ```

- 如果你确认你需要使用某个特定版本（而非最新）的依赖，你可以：

    ```python
    # PyPI
    rsserpent==0.1.4
    # Git
    rsserpent-plugin-bilibili @ git+https://github.com/RSSerpent-Rev/RSSerpent-plugin-bilibili.git@0609c0bd466e5d19fbb13078d9b93e0134b8c5bd
    ```

## Docker

默认镜像包含核心服务。`docker compose up --build` 会构建带有固定版本 Bilibili 插件的示例。

自定义镜像时，把插件清单放在 `docker/requirements/`。为所有额外的运行依赖固定版本，Git 依赖使用完整提交号。
核心及其依赖由 `poetry.lock` 管理。迁移旧部署时，移除服务对 `/app/rsserpent.txt` 的挂载。

```sh
docker build --build-arg RSSERPENT_PLUGIN_REQUIREMENTS=custom.txt -t rsserpent-local .
```

需要 Chromium 的插件使用 `--target browser`。构建时会安装浏览器和系统依赖。
发布的浏览器镜像名为 `ghcr.io/rsserpent-rev/rsserpent-browser`。

在 Docker 之外本地开发时，使用浏览器插件前先运行 `poetry run playwright install chromium`。
通过 `poetry run pytest --live -m live` 运行可选的联网和浏览器测试。
