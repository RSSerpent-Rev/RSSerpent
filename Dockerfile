FROM python:3.12-slim

# Install git, for third-party plugins
RUN apt-get update && apt-get install -y git
RUN apt-get clean

WORKDIR /app
RUN pip install poetry

COPY README.md LICENSE pyproject.toml poetry.lock ./

# RUN poetry config virtualenvs.create false

# Dependencies
RUN poetry install --only main,deploy --no-root --no-directory

# Copy
COPY rsserpent_rev rsserpent_rev

RUN poetry install --only main

RUN poetry cache clear pypi --all
COPY scripts/docker-entrypoint.sh /

ENV PYTHONUNBUFFERED=1
ENV PIP_ARGS="--no-cache-dir --upgrade --upgrade-strategy eager"

# Run
EXPOSE 8000
ENTRYPOINT [ "/docker-entrypoint.sh" ]
CMD [ "poetry", "run", "uvicorn", "rsserpent_rev:app", "--host", "0.0.0.0" ]
