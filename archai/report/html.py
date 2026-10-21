"""HTML report + compliance_graph.json writer."""

from __future__ import annotations

from collections import Counter
from typing import Any

from jinja2 import Environment, select_autoescape

from archai.schemas import STATUSES

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>ARCHAI compliance report</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:2rem auto;max-width:1100px;color:#222}
.banner{background:#fff3cd;border:1px solid #e0c36a;padding:.6rem 1rem;border-radius:6px}
table{border-collapse:collapse;width:100%;margin:1rem 0}
th,td{border:1px solid #ddd;padding:.4rem .6rem;text-align:left;vertical-align:top;font-size:.9rem}
th{background:#f4f4f4}
.PASS{background:#d8f3dc}.FAIL{background:#f8d7da}
.MISSING_METRIC{background:#fff3cd}.CANNOT_CHECK{background:#e2e3e5}
.q{color:#555;font-style:italic}
.chips span{display:inline-block;margin-right:.6rem;padding:.2rem .6rem;border-radius:4px}
</style></head><body>
<h1>ARCHAI compliance report</h1>
{% if banner %}<p class="banner">{{ banner }}</p>{% endif %}
<p>Regulation: <strong>{{ regulation.title }}</strong>
 (source: {{ regulation.source }}) &middot; Model: {{ model }}</p>
<p class="chips">{% for s in statuses %}<span class="{{ s }}">{{ s }}: {{ counts[s] }}</span>{% endfor %}
<span>Total checks: {{ results|length }}</span></p>
{% for oid, rows in grouped %}
<h2>{{ oid }}</h2>
<table><thead><tr><th>Article</th><th>Quoted text</th><th>Metric</th><th>Measured</th>
<th>Required</th><th>Status</th></tr></thead><tbody>
{% for r in rows %}<tr class="{{ r.status }}">
<td>Article {{ r.article }}, clause {{ r.clause }}<br>{{ r.article_title }}</td>
<td class="q">&ldquo;{{ r.quote }}&rdquo;</td>
<td>{{ r.metric or "-" }}</td>
<td>{{ r.measured if r.measured is not none else "-" }}{% if r.measured is not none %} {{ r.unit or "" }}{% endif %}</td>
<td>{{ r.required or "-" }}</td>
<td><strong>{{ r.status }}</strong><br>{{ r.message }}</td></tr>
{% endfor %}</tbody></table>
{% endfor %}
<p>Generated deterministically; the language model is never the source of truth.</p>
</body></html>
"""


def summarize(results: list[dict[str, Any]]) -> dict[str, int]:
    c = Counter(r["status"] for r in results)
    return {s: c.get(s, 0) for s in STATUSES}


def render_html(
    results: list[dict[str, Any]],
    regulation: dict[str, Any],
    model: str = "unknown",
    banner: str | None = None,
) -> str:
    env = Environment(autoescape=select_autoescape(default=True))
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        groups.setdefault(r["object_id"], []).append(r)
    return env.from_string(TEMPLATE).render(
        results=results,
        regulation=regulation,
        model=model,
        banner=banner,
        statuses=STATUSES,
        counts=summarize(results),
        grouped=list(groups.items()),
    )


def compliance_graph(
    graph: dict[str, Any], metrics: dict[str, Any], results: list[dict[str, Any]]
) -> dict[str, Any]:
    """Rule graph + metrics + per-check results in one JSON document."""
    return {
        "regulation": graph["regulation"],
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "metrics": metrics,
        "results": results,
        "summary": summarize(results),
    }
