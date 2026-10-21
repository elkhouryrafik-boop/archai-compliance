"""Metrics path: .3dm (rhino3dm) -> metrics JSON -> checker; Rhino 8 script hygiene."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from archai.check.evaluator import evaluate
from archai.cli import main
from archai.extract import extract_rules
from archai.metrics import compute
from archai.metrics.rhino3dm_reader import read_model

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "examples"


def test_3dm_metrics_equal_committed_json():
    expected = json.loads((EX / "metrics.sample.json").read_text(encoding="utf-8"))
    assert read_model(EX / "sample-site.3dm") == expected


def test_site_area_and_zone_from_3dm():
    doc = read_model(EX / "sample-site.3dm")
    assert doc["site"] == {"zone": "R2", "plot_area_m2": 9600.0}


def test_missing_mass_variant_has_no_height():
    doc = read_model(EX / "sample-site-missing.3dm")
    b = {x["id"]: x for x in doc["buildings"]}
    assert "height_m" not in b["BLDG_B"]
    assert b["BLDG_A"]["height_m"] == 24.5


def test_missing_mass_variant_yields_missing_metric_rows():
    graph = extract_rules(ROOT / "corpus" / "dreamtown" / "regulation.md")
    results = evaluate(graph["rules"], read_model(EX / "sample-site-missing.3dm"))
    hits = [r for r in results if r["object_id"] == "BLDG_B" and r["metric"] == "height_m"]
    assert hits and all(r["status"] == "MISSING_METRIC" for r in hits)
    full = evaluate(graph["rules"], read_model(EX / "sample-site.3dm"))
    assert any(
        r["object_id"] == "BLDG_B" and r["metric"] == "height_m" and r["status"] == "PASS"
        for r in full
    )


def test_cli_metrics_writes_json(tmp_path):
    out = tmp_path / "m.json"
    assert main(["metrics", str(EX / "sample-site.3dm"), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == read_model(EX / "sample-site.3dm")


def test_unreadable_model_raises(tmp_path):
    bad = tmp_path / "bad.3dm"
    bad.write_bytes(b"not a 3dm file")
    with pytest.raises(ValueError):
        read_model(bad)


@pytest.mark.parametrize(
    "value,expected",
    [("floors=7", 7), ("7", 7), (4, 4), ("x", None), ("height=7", None), (None, None)],
)
def test_parse_floors(value, expected):
    assert compute.parse_floors(value) == expected


def test_parse_layer_convention():
    assert compute.parse_layer("SITE::BOUNDARY") == ("SITE", "BOUNDARY")
    assert compute.parse_layer("BLDG_A::MASS") == ("A", "MASS")
    assert compute.parse_layer("BLDG_A::OTHER") is None
    assert compute.parse_layer("Default") is None


def test_assemble_without_site_has_no_far():
    doc = compute.assemble_metrics(
        "m", {"A": {"footprint": [(0, 0), (10, 0), (10, 10), (0, 10)], "floors": "floors=3"}}
    )
    b = doc["buildings"][0]
    assert b["footprint_area_m2"] == 100.0 and b["gross_floor_area_m2"] == 300.0
    assert "far" not in b and "site_coverage_pct" not in b


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_rhino_scripts_import_only_rhino_stdlib_and_compute():
    allowed = {
        "Rhino",
        "scriptcontext",
        "json",
        "os",
        "sys",
        "archai.metrics.compute",
        "archai.metrics.rhino8_script",
    }
    for f in (ROOT / "archai/metrics/rhino8_script.py", ROOT / "rhino/archai_extract_metrics.py"):
        assert _imports(f) <= allowed, (f.name, _imports(f) - allowed)


def test_compute_has_no_rhino_dependency():
    assert not (_imports(ROOT / "archai/metrics/compute.py") & {"Rhino", "rhino3dm"})


def test_3dm_files_carry_no_personal_strings():
    for name in ("sample-site.3dm", "sample-site-missing.3dm"):
        raw = (EX / name).read_bytes()
        text = raw.decode("latin-1") + raw.decode("utf-16le", "ignore")
        assert not re.search(r"(?i)[a-z]:\\[a-z]", text)
