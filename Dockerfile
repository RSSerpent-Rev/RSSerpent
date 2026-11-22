ARG PYTHON_IMAGE=python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2
FROM ${PYTHON_IMAGE} AS build

WORKDIR /app
ENV POETRY_VIRTUALENVS_IN_PROJECT=true \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install poetry==1.8.2

COPY README.md LICENSE pyproject.toml poetry.lock ./
RUN poetry install --only main,deploy --no-root --no-interaction
COPY rsserpent_rev/ rsserpent_rev/
RUN poetry build -f wheel && .venv/bin/python -m pip install --no-deps dist/*.whl

ARG RSSERPENT_PLUGIN_REQUIREMENTS=core.txt
COPY docker/requirements/ /tmp/rss-plugins/
COPY scripts/verify-plugin-install.py /tmp/
RUN .venv/bin/python -m pip list --format=freeze > /tmp/rss-core-installed.txt \
    && .venv/bin/python -m pip install --no-deps --report /app/.venv/plugin-install.json \
        --find-links /tmp/rss-plugins -r "/tmp/rss-plugins/${RSSERPENT_PLUGIN_REQUIREMENTS}" \
    && python /tmp/verify-plugin-install.py /tmp/rss-core-installed.txt .venv/plugin-install.json \
    && .venv/bin/python -m pip check

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
