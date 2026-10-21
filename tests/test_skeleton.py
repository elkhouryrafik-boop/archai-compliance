from archai.check.evaluator import evaluate
from archai.cli import build_parser
from archai.metrics.compute import building_metrics, parse_layer, polygon_area

RULE = {
    "id": "C2.1",
    "article": "C2",
    "text": "Height shall not exceed 21 m.",
    "metric": "height_m",
    "operator": "<=",
    "value": 21.0,
    "unit": "m",
}


def test_status_values():
    m = {"buildings": [{"id": "A", "height_m": 24.5}, {"id": "B", "height_m": 14.0}, {"id": "C"}]}
    st = {r["object_id"]: r["status"] for r in evaluate([RULE], m)}
    assert st == {"A": "FAIL", "B": "PASS", "C": "MISSING_METRIC"}


def test_cannot_check():
    r = dict(RULE, metric=None)
    assert evaluate([r], {"buildings": [{"id": "A"}]})[0]["status"] == "CANNOT_CHECK"


def test_metrics():
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert polygon_area(sq) == 100
    assert parse_layer("BLDG_A::MASS") == ("A", "MASS")
    assert building_metrics("A", sq, 2, [(0, 0, 0), (0, 0, 6)], 400)["far"] == 0.5


def test_parser():
    args = build_parser().parse_args(["check", "--rules", "a", "--metrics", "b"])
    assert args.command == "check"
