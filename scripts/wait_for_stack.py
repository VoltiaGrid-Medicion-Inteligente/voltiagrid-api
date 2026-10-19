"""Wait until every API of the local stack answers /health (US-14, T-14.3).

    python scripts/wait_for_stack.py              # default timeout 180 s
    python scripts/wait_for_stack.py --timeout 300

Used by `make up`. Works the same on Windows, macOS and Linux (only the standard library).
"""

import argparse
import sys
import time
import urllib.error
import urllib.request

SERVICES = {
    "api-customer-consumption": "http://localhost:8001/health",
    "api-network-inventory": "http://localhost:8003/health",
}


def is_up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for the local stack")
    parser.add_argument("--timeout", type=int, default=180, help="seconds")
    args = parser.parse_args()

    pending = dict(SERVICES)
    deadline = time.monotonic() + args.timeout
    while pending and time.monotonic() < deadline:
        for name, url in list(pending.items()):
            if is_up(url):
                print(f"  ok  {name}  {url}")
                del pending[name]
        if pending:
            time.sleep(3)

    if pending:
        print(f"Not ready after {args.timeout} s: {', '.join(pending)}. Run: make logs", file=sys.stderr)
        return 1
    print("Stack ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
