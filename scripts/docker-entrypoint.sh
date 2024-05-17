#!/bin/sh
set -e

if [ -f /app/rsserpent.txt ]; then
    poetry run pip install -r /app/rsserpent.txt
fi

exec "$@"
