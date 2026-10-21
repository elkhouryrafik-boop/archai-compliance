"""Offline end-to-end pipeline: extract -> metrics -> check -> report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from archai.check.evaluator import evaluate
from archai.extract import extract_rules
from archai.report import compliance_graph, render_html, summarize

BANNER = "Synthetic sample - DreamTown is fictional. No real regulation, site or client data."


def repo_root() -> Path:
    """Checkout root (contains corpus/ and examples/)."""
    return Path(__file__).resolve().parents[1]


def run_demo(
    out: Path, regulation: Path | None = None, metrics: Path | None = None
) -> dict[str, Any]:
    root = repo_root()
    regulation = regulation or root / "corpus" / "dreamtown" / "regulation.md"
    metrics = metrics or root / "examples" / "metrics.sample.json"
    for p in (regulation, metrics):
        if not p.exists():
            raise FileNotFoundError(f"{p} not found (run the demo from a repository checkout)")
    out.mkdir(parents=True, exist_ok=True)

    graph = extract_rules(regulation)
    (out / "rule_graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")

    m = json.loads(metrics.read_text(encoding="utf-8"))
    results = evaluate(graph["rules"], m)
    (out / "results.json").write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
    (out / "compliance_graph.json").write_text(
        json.dumps(compliance_graph(graph, m, results), indent=2), encoding="utf-8"
    )
    html = render_html(results, graph["regulation"], model=m.get("model", "unknown"), banner=BANNER)
    (out / "report.html").write_text(html, encoding="utf-8")
    return {"summary": summarize(results), "checks": len(results), "out": str(out)}
