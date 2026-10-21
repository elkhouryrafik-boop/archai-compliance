"""Deterministic extractor: Markdown/PDF regulation -> rule graph."""

import pytest
from jsonschema import validate

from archai.extract import extract_rules
from archai.extract.deterministic import _canon_unit, _clauses, _rule_from_clause
from archai.schemas import RULE_GRAPH_SCHEMA


@pytest.fixture(scope="module")
def graph(reg_md):
    return extract_rules(reg_md)


@pytest.fixture(scope="module")
def by_id(graph):
    return {r["id"]: r for r in graph["rules"]}


def _rule(text, art="C9", clause="9.1"):
    return _rule_from_clause({"id": art, "title": "T"}, {"clause": clause, "text": text})


def test_graph_is_schema_valid(graph):
    validate(graph, RULE_GRAPH_SCHEMA)


def test_regulation_title_and_fictional_flag(graph):
    assert "DreamTown" in graph["regulation"]["title"]
    assert graph["regulation"]["fictional"] is True


def test_eight_articles(graph):
    assert [a["id"] for a in graph["regulation"]["articles"]] == [f"C{i}" for i in range(1, 9)]


def test_definitions_are_not_rules(by_id):
    assert not any(k.startswith("C1-") for k in by_id)


def test_height_rule(by_id):
    r = by_id["C2-2.1"]
    assert (r["metric"], r["operator"], r["value"], r["unit"], r["zone"]) == (
        "height_m",
        "<=",
        21.0,
        "m",
        "R2",
    )


def test_floors_rule(by_id):
    r = by_id["C2-2.2"]
    assert (r["metric"], r["value"], r["unit"]) == ("floors", 6.0, "floors")


def test_far_rule(by_id):
    r = by_id["C3-3.1"]
    assert (r["metric"], r["operator"], r["value"]) == ("far", "<=", 2.0)


def test_coverage_rule(by_id):
    r = by_id["C3-3.2"]
    assert (r["metric"], r["value"], r["unit"]) == ("site_coverage_pct", 45.0, "%")


def test_setback_rules_use_lower_bound(by_id):
    assert by_id["C4-4.1"]["operator"] == ">=" and by_id["C4-4.1"]["value"] == 5.0
    assert by_id["C4-4.2"]["metric"] == "side_setback_m" and by_id["C4-4.2"]["value"] == 3.0


def test_plot_area_unit_canonicalised(by_id):
    r = by_id["C5-5.1"]
    assert (r["metric"], r["unit"], r["value"]) == ("plot_area_m2", "m2", 600.0)


def test_parking_and_frontage(by_id):
    assert by_id["C6-6.1"]["metric"] == "parking_spaces_per_100m2_gfa"
    assert by_id["C7-7.1"]["metric"] == "active_frontage_pct"


def test_subjective_clause_has_no_metric(by_id):
    r = by_id["C8-8.1"]
    assert r["metric"] is None and r["operator"] is None and r["value"] is None


def test_every_rule_quotes_its_clause_text(graph):
    assert all(r["text"] and r["article"] in r["id"] for r in graph["rules"])


def test_graph_edges_reference_existing_nodes(graph):
    ids = {n["id"] for n in graph["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in graph["edges"])


def test_pdf_extraction_matches_markdown(reg_md, graph):
    g = extract_rules(reg_md.with_suffix(".pdf"))
    keep = ("id", "metric", "operator", "value", "unit")
    assert [{k: r[k] for k in keep} for r in g["rules"]] == [
        {k: r[k] for k in keep} for r in graph["rules"]
    ]


def test_at_most_pattern():
    r = _rule("Building height shall be at most 12 m.")
    assert r["operator"] == "<=" and r["value"] == 12.0


def test_not_less_than_pattern():
    r = _rule("The plot area shall be not less than 250 m².")
    assert r["operator"] == ">=" and r["unit"] == "m2"


def test_decimal_value():
    assert _rule("The floor area ratio shall not exceed 1.75.")["value"] == 1.75


def test_shall_without_number_is_cannot_check_rule():
    r = _rule("Height shall be reasonable.")
    assert r is not None and r["metric"] is None


def test_clause_without_shall_dropped():
    assert _rule("Height is measured from the ground.") is None


def test_continuation_lines_are_joined():
    text = "# T\n\n## Article C1 - X\n\n1.1 Height shall not\nexceed 9 m.\n"
    _, arts = _clauses(text)
    assert arts[0]["clauses"][0]["text"] == "Height shall not exceed 9 m."


def test_unit_canonicalisation():
    assert _canon_unit("m²") == "m2" and _canon_unit("Storeys") == "floors"
    assert _canon_unit(None) is None
