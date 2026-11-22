import json
import re
import sys
from pathlib import Path


def canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.lower())


if __name__ == "__main__":
    baseline = Path(sys.argv[1]).read_text().splitlines()
    core = {canonical_name(line.split("==", 1)[0]) for line in baseline}
    report = json.loads(Path(sys.argv[2]).read_text())
    installed = {canonical_name(item["metadata"]["name"]) for item in report["install"]}
    overlap = core & installed
    if overlap:
        sys.exit(f"Plugin requirements replace core dependencies: {sorted(overlap)}")
