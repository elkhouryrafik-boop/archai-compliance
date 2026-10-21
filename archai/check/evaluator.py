"""Deterministic rule evaluator (ported from the Stage-7 comparison logic).

Statuses: PASS / FAIL / MISSING_METRIC / CANNOT_CHECK. Every result carries the
rule's article id and quoted text so the report can cite it.
"""

from __future__ import annotations

from typing import Any

from archai.schemas import CANNOT_CHECK, FAIL, MISSING_METRIC, PASS

# unit -> (dimension, factor to canonical unit); canonical: m, m2, pct, count
_UNITS: dict[str, tuple[str, float]] = {
    "m": ("length", 1.0),
    "metre": ("length", 1.0),
    "metres": ("length", 1.0),
    "meter": ("length", 1.0),
    "meters": ("length", 1.0),
    "cm": ("length", 0.01),
    "mm": ("length", 0.001),
    "ft": ("length", 0.3048),
    "m2": ("area", 1.0),
    "sqm": ("area", 1.0),
    "m²": ("area", 1.0),
    "ha": ("area", 10000.0),
    "%": ("pct", 1.0),
    "pct": ("pct", 1.0),
    "percent": ("pct", 1.0),
    "": ("count", 1.0),
    "floors": ("count", 1.0),
    "storeys": ("count", 1.0),
    "spaces": ("count", 1.0),
    "ratio": ("count", 1.0),
}

_OPS = ("<=", ">=", "<", ">", "=", "range")


def normalise(value: float, unit: str | None) -> tuple[str, float] | None:
    """Return (dimension, value in canonical unit) or None for an unknown unit."""
    key = (unit or "").strip().lower()
    if key not in _UNITS:
        return None
    dim, factor = _UNITS[key]
    return dim, value * factor


def _compare(measured: float, rule: dict[str, Any]) -> tuple[bool, str] | None:
    op, val, vmax = rule.get("operator"), rule.get("value"), rule.get("value_max")
    if val is None:
        return None
    if op == "<=":
        return measured <= val, f"<= {val:g}"
    if op == ">=":
        return measured >= val, f">= {val:g}"
    if op == "<":
        return measured < val, f"< {val:g}"
    if op == ">":
        return measured > val, f"> {val:g}"
    if op == "=":
        return abs(measured - val) < 1e-9, f"= {val:g}"
    if op == "range" and vmax is not None:
        return val <= measured <= vmax, f"[{val:g}, {vmax:g}]"
    return None


def _result(
    rule: dict[str, Any], obj: str, status: str, measured: Any, required: str, message: str
) -> dict[str, Any]:
    return {
        "object_id": obj,
        "rule_id": rule["id"],
        "article": rule.get("article"),
        "article_title": rule.get("article_title"),
        "clause": rule.get("clause"),
        "quote": rule.get("text"),
        "metric": rule.get("metric"),
        "status": status,
        "measured": measured,
        "required": required,
        "unit": rule.get("unit"),
        "message": message,
    }


def check_rule(rule: dict[str, Any], obj_id: str, values: dict[str, Any]) -> dict[str, Any]:
    """Check one rule against one object's metrics (numbers in canonical units)."""
    metric = rule.get("metric")
    if not metric or rule.get("operator") not in _OPS:
        return _result(
            rule, obj_id, CANNOT_CHECK, None, "", "Rule has no machine-checkable metric/operator"
        )
    if normalise(1.0, rule.get("unit")) is None:
        return _result(rule, obj_id, CANNOT_CHECK, None, "", f"Unknown unit '{rule.get('unit')}'")
    norm_rule = dict(rule)
    for k in ("value", "value_max"):
        if rule.get(k) is not None:
            norm_rule[k] = normalise(rule[k], rule.get("unit"))[1]  # type: ignore[index]
    raw = values.get(metric)
    if raw is None or isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return _result(rule, obj_id, MISSING_METRIC, None, "", f"Metric '{metric}' not available")
    cmp = _compare(float(raw), norm_rule)
    if cmp is None:
        return _result(rule, obj_id, CANNOT_CHECK, raw, "", "Incomplete rule thresholds")
    ok, req = cmp
    return _result(
        rule, obj_id, PASS if ok else FAIL, raw, req, "Complies" if ok else "Does not comply"
    )


def evaluate(rules: list[dict[str, Any]], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply every rule to every building; site-level metrics sit under building metrics."""
    site = metrics.get("site", {}) or {}
    results: list[dict[str, Any]] = []
    for b in metrics.get("buildings", []):
        values = {**site, **{k: v for k, v in b.items() if k != "id"}}
        zone = b.get("zone") or site.get("zone")
        for rule in rules:
            if rule.get("zone") and zone and rule["zone"] != zone:
                continue
            results.append(check_rule(rule, b["id"], values))
    return results
