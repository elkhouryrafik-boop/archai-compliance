"""Deterministic evaluator."""

import json

import pytest

from archai.check.evaluator import check_rule, evaluate, normalise
from archai.extract import extract_rules


def rule(**kw):
    base = {
        "id": "R",
        "article": "C1",
        "clause": "1.1",
        "text": "quoted",
        "metric": "height_m",
        "operator": "<=",
        "value": 21.0,
        "unit": "m",
    }
    base.update(kw)
    return base


@pytest.mark.parametrize(
    "op,val,measured,status",
    [
        ("<=", 21, 21, "PASS"),
        ("<=", 21, 21.01, "FAIL"),
        (">=", 5, 5, "PASS"),
        (">=", 5, 4.99, "FAIL"),
        ("<", 10, 10, "FAIL"),
        ("<", 10, 9.9, "PASS"),
        (">", 10, 10, "FAIL"),
        (">", 10, 10.1, "PASS"),
        ("=", 3, 3, "PASS"),
        ("=", 3, 3.5, "FAIL"),
    ],
)
def test_operators(op, val, measured, status):
    r = check_rule(rule(operator=op, value=val), "B", {"height_m": measured})
    assert r["status"] == status


def test_range_operator():
    r = rule(operator="range", value=2, value_max=4)
    assert check_rule(r, "B", {"height_m": 3})["status"] == "PASS"
    assert check_rule(r, "B", {"height_m": 5})["status"] == "FAIL"


def test_range_without_max_is_cannot_check():
    r = rule(operator="range", value=2)
    assert check_rule(r, "B", {"height_m": 3})["status"] == "CANNOT_CHECK"


def test_missing_metric():
    assert check_rule(rule(), "B", {})["status"] == "MISSING_METRIC"


def test_none_metric_value_is_missing():
    assert check_rule(rule(), "B", {"height_m": None})["status"] == "MISSING_METRIC"


def test_non_numeric_metric_is_missing():
    assert check_rule(rule(), "B", {"height_m": "tall"})["status"] == "MISSING_METRIC"
    assert check_rule(rule(), "B", {"height_m": True})["status"] == "MISSING_METRIC"


def test_no_metric_cannot_check():
    assert check_rule(rule(metric=None), "B", {})["status"] == "CANNOT_CHECK"


def test_no_operator_cannot_check():
    assert check_rule(rule(operator=None), "B", {"height_m": 1})["status"] == "CANNOT_CHECK"


def test_unknown_unit_cannot_check():
    r = check_rule(rule(unit="furlong"), "B", {"height_m": 1})
    assert r["status"] == "CANNOT_CHECK" and "furlong" in r["message"]


def test_missing_value_cannot_check():
    assert check_rule(rule(value=None), "B", {"height_m": 1})["status"] == "CANNOT_CHECK"


def test_unit_conversion_of_rule_threshold():
    # 2100 cm == 21 m, measured 22 m -> FAIL
    assert check_rule(rule(value=2100, unit="cm"), "B", {"height_m": 22})["status"] == "FAIL"


def test_normalise_units():
    assert normalise(1, "ha") == ("area", 10000.0)
    assert normalise(1, "furlong") is None
    assert normalise(5, None) == ("count", 5.0)


def test_result_cites_article_and_quote():
    r = check_rule(rule(), "BLDG_X", {"height_m": 30})
    assert (r["article"], r["clause"], r["quote"], r["object_id"]) == (
        "C1",
        "1.1",
        "quoted",
        "BLDG_X",
    )
    assert r["measured"] == 30 and r["required"] == "<= 21"


def test_evaluate_one_row_per_building_per_rule():
    m = {"buildings": [{"id": "A", "height_m": 1}, {"id": "B", "height_m": 2}]}
    assert len(evaluate([rule(), rule(id="R2")], m)) == 4


def test_zone_filter_skips_other_zones():
    m = {"site": {"zone": "R1"}, "buildings": [{"id": "A", "height_m": 99}]}
    assert evaluate([rule(zone="R2")], m) == []


def test_zone_rule_applies_when_zone_matches_or_unknown():
    m = {"site": {"zone": "R2"}, "buildings": [{"id": "A", "height_m": 99}]}
    assert evaluate([rule(zone="R2")], m)[0]["status"] == "FAIL"
    m2 = {"buildings": [{"id": "A", "height_m": 99}]}
    assert evaluate([rule(zone="R2")], m2)[0]["status"] == "FAIL"


def test_site_metrics_visible_to_buildings():
    r = rule(metric="plot_area_m2", operator=">=", value=600, unit="m2")
    m = {"site": {"plot_area_m2": 9600}, "buildings": [{"id": "A"}]}
    assert evaluate([r], m)[0]["status"] == "PASS"


def test_building_value_overrides_site_value():
    m = {"site": {"height_m": 1}, "buildings": [{"id": "A", "height_m": 50}]}
    assert evaluate([rule()], m)[0]["status"] == "FAIL"


def test_no_buildings_no_results():
    assert evaluate([rule()], {"buildings": []}) == []


def test_sample_expectations(reg_md, metrics_json):
    metrics = json.loads(metrics_json.read_text("utf-8"))
    res = evaluate(extract_rules(reg_md)["rules"], metrics)
    st = {(r["object_id"], r["rule_id"]): r["status"] for r in res}
    assert st[("BLDG_A", "C2-2.1")] == "FAIL"
    assert st[("BLDG_A", "C2-2.2")] == "FAIL"
    assert st[("BLDG_B", "C2-2.1")] == "PASS"
    assert st[("BLDG_B", "C2-2.2")] == "PASS"
    assert st[("BLDG_A", "C8-8.1")] == "CANNOT_CHECK"
    assert st[("BLDG_A", "C4-4.1")] == "MISSING_METRIC"
