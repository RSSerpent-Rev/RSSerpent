# Install Plugins

## Deployment templates

!!!warning
    Be careful not to mistake **`rsserpent.txt`** for `requirements.txt`.

The default template doesn't do much. In order to unleash the full power of RSSerpent, you will need to add RSSerpent plugins to the `rsserpent.txt` file.

You could clone the repository to edit `rsserpent.txt` locally, or you could just use the GitHub web interface if you are not familiar with [git](https://git-scm.com/).

Several things to note when writing `rsserpent.txt`:

- It's the same as writing `requirements.txt` for any Python project;
- Do not modify `requirements.txt`, only edit `rsserpent.txt`. GitHub Actions will be in charge of automatically updating `requirements.txt` and deploying your instance;
- By *automatically* it means every week or every time you commit changes to the repository;
- It's recommended to not specify versions so that [GitHub Actions](https://github.com/features/actions) could automatically updates them;

    ```python
    # PyPI
    rsserpent
    # Git
    rsserpent-plugin-bilibili @ git+https://github.com/RSSerpent-Rev/RSSerpent-plugin-bilibili.git
    ```

- If you do need a specific version of some dependency, you could always pin its version with:

    ```python
    # PyPI
    rsserpent==0.1.4
    # Git
    rsserpent-plugin-bilibili @ git+https://github.com/RSSerpent-Rev/RSSerpent-plugin-bilibili.git@0609c0bd466e5d19fbb13078d9b93e0134b8c5bd
    ```

## Docker

The default image contains the core service. `docker compose up --build` builds
the example with the pinned Bilibili plugin.

For a custom image, put a plugin requirements file under `docker/requirements/`.
Pin all extra runtime packages and use full commits for Git dependencies.
Keep the core and its locked dependencies in `poetry.lock`.
Remove the old `/app/rsserpent.txt` volume mount from the service.

```sh
docker build --build-arg RSSERPENT_PLUGIN_REQUIREMENTS=custom.txt -t rsserpent-local .
```

Use `--target browser` if a plugin needs Chromium. The browser and its system
dependencies are installed during the build. The published browser image uses
the name `ghcr.io/rsserpent-rev/rsserpent-browser`.

For local development outside Docker, run `poetry run playwright install chromium`
before using a browser plugin. Enable the optional integration tests with
`poetry run pytest --live -m live`.
