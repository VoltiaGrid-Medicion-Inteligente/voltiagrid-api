"""Export the OpenAPI contract of every API to docs/openapi/ (US-12, T-12.2).

    python -m scripts.export_openapi           # write the files
    python -m scripts.export_openapi --check   # fail if a committed file is out of date (CI)

Every PR that changes an endpoint must run this and commit the updated JSON,
so the contract change is visible in the PR diff.
"""

import argparse
import json
import sys
from pathlib import Path

from app.api.control_center.main import app as control_center
from app.api.customer_consumption.main import app as customer_consumption
from app.api.network_inventory.main import app as network_inventory

OUT_DIR = Path("docs/openapi")
APIS = {
    "customer-consumption": customer_consumption,
    "control-center": control_center,
    "network-inventory": network_inventory,
}


def render(app) -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def export(out_dir: Path = OUT_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, app in APIS.items():
        path = out_dir / f"{name}.json"
        path.write_text(render(app), encoding="utf-8", newline="\n")
        written.append(path)
    return written


def stale(out_dir: Path = OUT_DIR) -> list[str]:
    """Names of the contracts whose committed file differs from the code."""
    result = []
    for name, app in APIS.items():
        path = out_dir / f"{name}.json"
        if not path.exists() or path.read_text(encoding="utf-8") != render(app):
            result.append(name)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only check, do not write")
    args = parser.parse_args(argv)

    if args.check:
        outdated = stale()
        if outdated:
            print(f"Out of date: {', '.join(outdated)}. Run: python -m scripts.export_openapi", file=sys.stderr)
            return 1
        print("OpenAPI contracts are up to date.")
        return 0

    for path in export():
        print(f"written {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
