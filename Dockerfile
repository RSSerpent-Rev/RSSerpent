FROM python:3.10-slim

# Copy
WORKDIR /app
COPY rsserpent rsserpent
RUN pip install poetry

COPY README.md LICENSE pyproject.toml poetry.lock ./

# Dependencies
RUN poetry install

# Install git
RUN apt-get update && apt-get install -y git

COPY scripts/docker-entrypoint.sh /

RUN poetry config virtualenvs.create false

ENV PYTHONUNBUFFERED=1

# Run
EXPOSE 8000
ENTRYPOINT [ "/docker-entrypoint.sh" ]
CMD [ "poetry", "run", "uvicorn", "rsserpent:app", "--host", "0.0.0.0" ]
