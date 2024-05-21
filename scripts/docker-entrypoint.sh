#!/bin/sh
set -e

if [ -f /app/rsserpent.txt ]; then
    poetry run pip install -r /app/rsserpent.txt --no-cache-dir
fi

exec "$@"
