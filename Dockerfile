ARG PYTHON_IMAGE=python:3.14.10-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b
FROM ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d AS uv
FROM ${PYTHON_IMAGE} AS build

WORKDIR /app
ENV LC_ALL=C \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY README.md LICENSE pyproject.toml uv.lock ./
RUN uv sync --locked --no-default-groups --group deploy --no-install-project
COPY rsserpent_rev/ rsserpent_rev/
RUN uv sync --locked --no-default-groups --group deploy --no-editable

ARG RSSERPENT_PLUGIN_REQUIREMENTS=core.txt
COPY docker/requirements/ /tmp/rss-plugins/
RUN uv pip list --format freeze > /tmp/core-constraints.txt \
    && uv pip freeze > /tmp/core-installed.txt \
    && uv pip install --strict --constraint /tmp/core-constraints.txt \
        --find-links /tmp/rss-plugins -r "/tmp/rss-plugins/${RSSERPENT_PLUGIN_REQUIREMENTS}" \
    && uv pip freeze > /tmp/plugin-installed.txt \
    && sort -o /tmp/core-installed.txt /tmp/core-installed.txt \
    && sort -o /tmp/plugin-installed.txt /tmp/plugin-installed.txt \
    && comm -23 /tmp/core-installed.txt /tmp/plugin-installed.txt > /tmp/replaced.txt \
    && if [ -s /tmp/replaced.txt ]; then cat /tmp/replaced.txt >&2; exit 1; fi \
    && uv pip check

FROM ${PYTHON_IMAGE} AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"
COPY --from=build /app/.venv/ .venv/
EXPOSE 8000
CMD ["uvicorn", "rsserpent_rev:app", "--host", "0.0.0.0"]

FROM runtime AS browser
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
RUN playwright install --with-deps chromium && rm -rf /var/lib/apt/lists/*

FROM runtime AS core
