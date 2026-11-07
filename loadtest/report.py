"""p95 of the load test against RNF-04 (US-47, T-47.1).

    python -m loadtest.report loadtest/results/before_stats.csv
    python -m loadtest.report loadtest/results/before_stats.csv loadtest/results/after_stats.csv

Reads the *_stats.csv that Locust writes with --csv and prints, for the consumption endpoint: requests, failures,
median, p95, p99 and whether p95 meets the target (500 ms). With two files it also prints the change.
"""

import csv
import sys

ENDPOINT = "/me/consumption/daily"
TARGET_P95_MS = 500


def endpoint_stats(path: str, name: str = ENDPOINT) -> dict:
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["Name"] == name:
                return {"requests": int(row["Request Count"]), "failures": int(row["Failure Count"]),
                        "median": float(row["50%"]), "p95": float(row["95%"]), "p99": float(row["99%"]),
                        "rps": float(row["Requests/s"])}
    raise SystemExit(f"{name} not found in {path}")


def line(label: str, s: dict) -> str:
    verdict = "meets" if s["p95"] <= TARGET_P95_MS else "MISSES"
    return (f"{label}: {s['requests']:,} requests, {s['failures']} failures, {s['rps']:.1f} req/s, "
            f"median {s['median']:.0f} ms, p95 {s['p95']:.0f} ms, p99 {s['p99']:.0f} ms -> {verdict} RNF-04 "
            f"(p95 <= {TARGET_P95_MS} ms)")


def main(paths: list[str]) -> None:
    stats = [endpoint_stats(p) for p in paths]
    for label, s in zip(["before", "after"] if len(stats) == 2 else ["result"], stats):
        print(line(label, s))
    if len(stats) == 2:
        before, after = stats
        print(f"p95 {before['p95']:.0f} -> {after['p95']:.0f} ms ({after['p95'] / before['p95'] - 1:+.0%})")


if __name__ == "__main__":
    main(sys.argv[1:])
