FROM python:3.12-slim

# Copy
WORKDIR /app
COPY rsserpent_rev rsserpent_rev
RUN pip install poetry

COPY README.md LICENSE pyproject.toml poetry.lock ./

# RUN poetry config virtualenvs.create false

# Dependencies
RUN poetry install

# Install git
RUN apt-get update && apt-get install -y git

COPY scripts/docker-entrypoint.sh /

ENV PYTHONUNBUFFERED=1

# Run
EXPOSE 8000
ENTRYPOINT [ "/docker-entrypoint.sh" ]
CMD [ "poetry", "run", "uvicorn", "rsserpent:app", "--host", "0.0.0.0" ]
