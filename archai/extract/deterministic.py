"""Deterministic extractor: structured Markdown/PDF regulation -> rule graph JSON.

Understands ``Article C<n> - <title>`` headings, numbered clauses (``2.1 ...``) and the
"shall not exceed N unit" / "shall be at least N unit" patterns. Clauses with a ``shall``
but no machine-checkable pattern become rules with ``metric: null`` (reported as
CANNOT_CHECK); purely definitional clauses are kept as text only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from jsonschema import validate

from archai.schemas import RULE_GRAPH_SCHEMA

ARTICLE_RE = re.compile(r"^(?:#+\s*)?Article\s+(C\d+)\s*[-–—:]\s*(.+?)\s*$", re.IGNORECASE)
CLAUSE_RE = re.compile(r"^(\d+)\.(\d+)\s+(.*\S)\s*$")
ZONE_RE = re.compile(r"\bIn zone ([A-Z]\d)\b")
UPPER_RE = re.compile(
    r"\b(?:shall not exceed|shall not be more than|at most|maximum of)\s+", re.IGNORECASE
)
LOWER_RE = re.compile(
    r"\b(?:shall be at least|at least|not less than|minimum of)\s+", re.IGNORECASE
)
NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(m²|m2|m|%|floors?|storeys?|spaces?)?", re.IGNORECASE)

# (pattern on the clause text, metric, default unit) - first match wins
CONCEPTS: list[tuple[str, str, str]] = [
    (r"number of (?:floors|storeys)", "floors", "floors"),
    (r"\bheight\b", "height_m", "m"),
    (r"floor area ratio|\bFAR\b", "far", ""),
    (r"site coverage", "site_coverage_pct", "%"),
    (r"front setback", "front_setback_m", "m"),
    (r"side setback", "side_setback_m", "m"),
    (r"plot area", "plot_area_m2", "m2"),
    (r"\bparking\b", "parking_spaces_per_100m2_gfa", "spaces"),
    (r"active frontage", "active_frontage_pct", "%"),
]

_UNIT_CANON = {
    "m²": "m2",
    "floor": "floors",
    "storey": "floors",
    "storeys": "floors",
    "space": "spaces",
}


def _canon_unit(u: str | None) -> str | None:
    if u is None:
        return None
    u = u.lower()
    return _UNIT_CANON.get(u, u)


def read_text(source: Path) -> str:
    if source.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n".join((p.extract_text() or "") for p in PdfReader(str(source)).pages)
    return source.read_text(encoding="utf-8")


def _clauses(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Split text into articles and clauses (continuation lines are joined)."""
    title = "Untitled regulation"
    fictional = False
    articles: list[dict[str, Any]] = []
    cur_art: dict[str, Any] | None = None
    cur_cl: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.strip().lstrip(">").strip()
        if not line:
            cur_cl = None
            continue
        if line.startswith("# ") and not articles:
            title = line[2:].strip()
            fictional = "fictional" in title.lower()
            continue
        m = ARTICLE_RE.match(line)
        if m:
            cur_art = {"id": m.group(1).upper(), "title": m.group(2), "clauses": []}
            articles.append(cur_art)
            cur_cl = None
            continue
        c = CLAUSE_RE.match(line)
        if c and cur_art is not None:
            cur_cl = {"clause": f"{c.group(1)}.{c.group(2)}", "text": c.group(3)}
            cur_art["clauses"].append(cur_cl)
        elif cur_cl is not None:
            cur_cl["text"] += " " + line
    return {"title": title, "fictional": fictional}, articles


def _rule_from_clause(art: dict[str, Any], cl: dict[str, Any]) -> dict[str, Any] | None:
    text = cl["text"]
    if not re.search(r"\bshall\b", text, re.IGNORECASE):
        return None  # definition / descriptive clause
    rule: dict[str, Any] = {
        "id": f"{art['id']}-{cl['clause']}",
        "article": art["id"],
        "article_title": art["title"],
        "clause": cl["clause"],
        "text": text,
        "concept": None,
        "zone": None,
        "metric": None,
        "operator": None,
        "value": None,
        "value_max": None,
        "unit": None,
    }
    z = ZONE_RE.search(text)
    if z:
        rule["zone"] = z.group(1)
    op, m_op = None, UPPER_RE.search(text)
    if m_op:
        op = "<="
    else:
        m_op = LOWER_RE.search(text)
        if m_op:
            op = ">="
    metric = next(((mt, u) for pat, mt, u in CONCEPTS if re.search(pat, text, re.IGNORECASE)), None)
    if not (op and metric and m_op):
        return rule
    num = NUM_RE.match(text[m_op.end() :])
    if not num:
        return rule
    rule.update(
        concept=metric[0],
        metric=metric[0],
        operator=op,
        value=float(num.group(1)),
        unit=_canon_unit(num.group(2)) or metric[1],
    )
    return rule


def extract_rules(source: Path) -> dict[str, Any]:
    """Return a schema-valid rule graph (regulation, rules, nodes, edges)."""
    reg, articles = _clauses(read_text(source))
    rules = [r for a in articles for c in a["clauses"] if (r := _rule_from_clause(a, c))]
    nodes: list[dict[str, str]] = [
        {"id": a["id"], "type": "article", "label": a["title"]} for a in articles
    ]
    edges: list[dict[str, str]] = []
    seen: set[str] = set()
    for r in rules:
        nodes.append({"id": r["id"], "type": "rule", "label": r["text"]})
        edges.append({"source": r["article"], "target": r["id"], "relation": "contains"})
        if r["metric"]:
            if r["metric"] not in seen:
                seen.add(r["metric"])
                nodes.append({"id": r["metric"], "type": "metric", "label": r["metric"]})
            edges.append({"source": r["id"], "target": r["metric"], "relation": "constrains"})
    graph = {
        "regulation": {
            **reg,
            "source": source.name,
            "articles": [{"id": a["id"], "title": a["title"]} for a in articles],
        },
        "rules": rules,
        "nodes": nodes,
        "edges": edges,
    }
    validate(graph, RULE_GRAPH_SCHEMA)
    return graph
