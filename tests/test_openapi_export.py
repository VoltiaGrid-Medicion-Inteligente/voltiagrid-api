"""US-12 (T-12.2): every API contract is exported and the committed copy matches the code."""

import json

from scripts.export_openapi import APIS, export, stale


def test_export_writes_one_valid_file_per_api(tmp_path):
    written = export(tmp_path)
    assert sorted(p.name for p in written) == sorted(f"{name}.json" for name in APIS)
    for path in written:
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert spec["openapi"].startswith("3.")
        assert spec["paths"]


def test_a_changed_contract_is_detected(tmp_path):
    export(tmp_path)
    (tmp_path / "control-center.json").write_text("{}\n", encoding="utf-8")
    assert stale(tmp_path) == ["control-center"]


def test_committed_contracts_are_up_to_date():
    assert stale() == [], "run: python -m scripts.export_openapi and commit docs/openapi/"