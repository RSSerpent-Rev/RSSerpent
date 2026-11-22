#!/bin/sh
set -eu

version=$(uv version --short)
if [ "$#" -gt 1 ]; then
    printf 'Usage: %s [version]\n' "$0" >&2
    exit 2
fi
if [ "$#" -eq 1 ]; then
    version=$1
fi
printf 'Prepare release %s? [y/n] ' "$version"
read -r answer
case "$answer" in
    [Yy]*) ;;
    *) exit 0 ;;
esac

uv version "$version"
version=$(uv version --short)
uv run --locked --no-sync python - "$version" <<'PY'
import sys
from pathlib import Path

changelog = Path("CHANGELOG.md")
content = changelog.read_text()
if "## Unreleased\n" in content:
    changelog.write_text(content.replace("## Unreleased\n", f"## {sys.argv[1]}\n", 1))
PY
git diff HEAD -- pyproject.toml uv.lock CHANGELOG.md
git add -- pyproject.toml uv.lock CHANGELOG.md
git commit -v
git tag "$version"
