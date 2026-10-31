"""Tag verification script (US-28, T-28.1). No AWS needed."""

import json

import pytest

from scripts.check_tags import check_aws, check_state, problems, read_json

GOOD = {"Project": "voltiagrid", "Environment": "dev", "Owner": "p3-devops", "Component": "network", "ManagedBy": "terraform"}


def resource(address, tags=None, taggable=True, mode="managed"):
    values = {"id": "x"}
    if taggable:
        values["tags_all"] = tags
    return {"address": address, "mode": mode, "values": values}


def state(root_resources, children=()):
    return {"values": {"root_module": {"resources": root_resources, "child_modules": list(children)}}}


def test_policy_tags_pass():
    assert problems(GOOD) == []


@pytest.mark.parametrize("key", ["Project", "Environment", "Owner", "Component"])
def test_each_required_tag_is_checked(key):
    tags = {k: v for k, v in GOOD.items() if k != key}
    assert problems(tags) == [f"missing {key}"]


def test_values_outside_the_policy_fail():
    tags = {**GOOD, "Project": "other", "Owner": "carlos"}
    assert problems(tags) == ["Project=other not allowed", "Owner=carlos not allowed"]


def test_empty_component_fails():
    assert problems({**GOOD, "Component": ""}) == ["missing Component"]


def test_state_walks_child_modules_and_skips_untaggable():
    doc = state(
        [resource("aws_s3_bucket.ok", GOOD)],
        [{"address": "module.network", "resources": [
            resource("module.network.aws_vpc.this", {**GOOD, "Owner": None}),
            resource("module.network.aws_route_table_association.a", taggable=False),
            resource("module.network.data.aws_region.current", mode="data"),
        ], "child_modules": [{"resources": [resource("module.network.module.x.aws_subnet.a", {})]}]}],
    )
    failures, checked, skipped = check_state(doc)
    assert checked == 3 and skipped == 1
    assert [a for a, _ in failures] == ["module.network.aws_vpc.this", "module.network.module.x.aws_subnet.a"]


def test_empty_state_has_nothing_to_check():
    assert check_state({}) == ([], 0, 0)


class FakeTagging:
    def __init__(self, items):
        self.items = items

    def get_paginator(self, name):
        assert name == "get_resources"
        return self

    def paginate(self, TagFilters):
        assert TagFilters == [{"Key": "Project", "Values": ["voltiagrid"]}]
        yield {"ResourceTagMappingList": self.items}


def test_live_check_reports_bad_arns():
    items = [
        {"ResourceARN": "arn:ok", "Tags": [{"Key": k, "Value": v} for k, v in GOOD.items()]},
        {"ResourceARN": "arn:bad", "Tags": [{"Key": "Project", "Value": "voltiagrid"}]},
    ]
    failures, checked = check_aws(FakeTagging(items))
    assert checked == 2
    assert failures == [("arn:bad", ["missing Environment", "missing Owner", "missing Component"])]


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16"])
def test_reads_json_written_by_powershell(tmp_path, encoding):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"values": {}}), encoding=encoding)
    assert read_json(path) == {"values": {}}
