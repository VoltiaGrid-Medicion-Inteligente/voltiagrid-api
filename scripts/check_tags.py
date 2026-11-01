"""Tag verification for the AWS infrastructure (US-28, T-28.1).

Checks the tagging policy (docs: AWS account and access) on every taggable resource:

    Project     = voltiagrid
    Environment = dev | prod | shared
    Owner       = p1-backend | p2-data | p3-devops | p4-analytics
    Component   = any non-empty value

Two sources, use both after an apply:

    python -m scripts.check_tags --stack infra/envs/dev      # Terraform state: every managed resource
    python -m scripts.check_tags --stack infra/envs/data
    python -m scripts.check_tags --aws                       # live account: everything tagged Project=voltiagrid

--stack runs `terraform show -json` and keeps the output in memory (the state contains generated secrets,
so it is never written to a file). Exit code 1 if any resource breaks the policy.
"""

import argparse
import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

REQUIRED = {
    "Project": {"voltiagrid"},
    "Environment": {"dev", "prod", "shared"},
    "Owner": {"p1-backend", "p2-data", "p3-devops", "p4-analytics"},
    "Component": None,  # free text, must exist and not be empty
}


def problems(tags: dict | None) -> list[str]:
    """What is wrong with a resource's tags; empty list if it follows the policy."""
    tags = tags or {}
    found = []
    for key, allowed in REQUIRED.items():
        value = tags.get(key)
        if not value:
            found.append(f"missing {key}")
        elif allowed is not None and value not in allowed:
            found.append(f"{key}={value} not allowed")
    return found


def walk_modules(module: dict) -> Iterator[dict]:
    yield from module.get("resources", [])
    for child in module.get("child_modules", []):
        yield from walk_modules(child)


def check_state(state: dict) -> tuple[list[tuple[str, list[str]]], int, int]:
    """(failures, checked, not taggable) for a `terraform show -json` document."""
    root = state.get("values", {}).get("root_module", {})
    failures, checked, skipped = [], 0, 0
    for res in walk_modules(root):
        if res.get("mode") != "managed":
            continue
        values = res.get("values") or {}
        if "tags_all" not in values:
            skipped += 1  # resource type without tags (rules, associations, random_password...)
            continue
        checked += 1
        issues = problems(values.get("tags_all"))
        if issues:
            failures.append((res["address"], issues))
    return failures, checked, skipped


def check_aws(client) -> tuple[list[tuple[str, list[str]]], int]:
    """Live check with the Resource Groups Tagging API: every resource tagged Project=voltiagrid."""
    failures, checked = [], 0
    paginator = client.get_paginator("get_resources")
    for page in paginator.paginate(TagFilters=[{"Key": "Project", "Values": ["voltiagrid"]}]):
        for item in page["ResourceTagMappingList"]:
            checked += 1
            tags = {t["Key"]: t["Value"] for t in item.get("Tags", [])}
            issues = problems(tags)
            if issues:
                failures.append((item["ResourceARN"], issues))
    return failures, checked


def read_json(path: Path) -> dict:
    """Reads JSON written by Windows PowerShell too (UTF-16 or UTF-8 with BOM)."""
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return json.loads(raw.decode("utf-16"))
    return json.loads(raw.decode("utf-8-sig"))


def terraform_state(stack: str) -> dict:
    result = subprocess.run(["terraform", f"-chdir={stack}", "show", "-json"],
                            capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        sys.exit(f"terraform show failed for {stack}:\n{result.stderr}")
    return json.loads(result.stdout)


def report(title: str, failures: list[tuple[str, list[str]]], checked: int, skipped: int | None = None) -> bool:
    extra = f", {skipped} without tag support" if skipped is not None else ""
    print(f"{title}: {checked} resources checked{extra}, {len(failures)} with problems")
    for address, issues in failures:
        print(f"  FAIL {address}: {', '.join(issues)}")
    return not failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the tagging policy on the infrastructure")
    parser.add_argument("--stack", action="append", default=[], help="Terraform folder, e.g. infra/envs/dev")
    parser.add_argument("--state", type=Path, help="file with `terraform show -json` output")
    parser.add_argument("--aws", action="store_true", help="check the live account with the tagging API")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    if not (args.stack or args.state or args.aws):
        parser.error("use --stack, --state or --aws")

    ok = True
    for stack in args.stack:
        failures, checked, skipped = check_state(terraform_state(stack))
        ok &= report(stack, failures, checked, skipped)
    if args.state:
        failures, checked, skipped = check_state(read_json(args.state))
        ok &= report(str(args.state), failures, checked, skipped)
    if args.aws:
        import boto3  # only needed for the live check

        failures, checked = check_aws(boto3.client("resourcegroupstaggingapi", region_name=args.region))
        ok &= report(f"AWS {args.region}", failures, checked)
        if checked == 0:
            print("  Nothing tagged Project=voltiagrid was found: is the stack applied in this region?")
            ok = False

    print("OK: every resource follows the tagging policy." if ok else "Tagging policy NOT met.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
