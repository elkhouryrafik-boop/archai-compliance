"""Command line: ``archai demo|extract|metrics|check|report|index``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from archai import __version__
from archai.check.evaluator import evaluate


def _cmd_metrics(args: argparse.Namespace) -> int:
    from archai.metrics.rhino3dm_reader import read_model

    doc = read_model(Path(args.model))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"{len(doc['buildings'])} buildings -> {out}")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    graph = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    results = evaluate(graph["rules"], metrics)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {"regulation": graph.get("regulation"), "metrics": metrics, "results": results}
    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(json.dumps(counts, sort_keys=True))
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    from archai.pipeline import run_demo

    info = run_demo(Path(args.out))
    print(json.dumps(info["summary"], sort_keys=True))
    print(f"{info['checks']} checks -> {Path(args.out) / 'report.html'}")
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    if args.llm:
        from archai.llm import extract_with_llm  # optional path, needs OPENAI_API_KEY

        graph = extract_with_llm(Path(args.source))
    else:
        from archai.extract import extract_rules

        graph = extract_rules(Path(args.source))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    print(f"{len(graph['rules'])} rules -> {out}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from archai.report import render_html

    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    reg = data.get("regulation") or {"title": "Unknown regulation", "source": "-"}
    model = (data.get("metrics") or {}).get("model", "unknown")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(data["results"], reg, model=model), encoding="utf-8")
    print(f"report -> {out}")
    return 0


def _cmd_index(args: argparse.Namespace) -> int:
    from archai.index.build import build_index

    n = build_index(Path(args.source), Path(args.db), embeddings=args.embeddings)
    print(f"indexed {n} chunks into {args.db}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="archai", description=__doc__)
    p.add_argument("--version", action="version", version=f"archai {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demo", help="run the end-to-end demo")
    d.add_argument("--offline", action="store_true", help="no network, no API key")
    d.add_argument("--out", default="out/demo")
    d.set_defaults(func=_cmd_demo)

    e = sub.add_parser("extract", help="regulation (md/pdf) -> rule graph JSON")
    e.add_argument("source")
    e.add_argument("--out", default="out/rule_graph.json")
    e.add_argument("--llm", choices=["openai"], help="optional LLM extractor")
    e.set_defaults(func=_cmd_extract)

    m = sub.add_parser("metrics", help=".3dm -> metrics JSON")
    m.add_argument("model")
    m.add_argument("--out", default="out/metrics.json")
    m.set_defaults(func=_cmd_metrics)

    c = sub.add_parser("check", help="rule graph + metrics -> check results JSON")
    c.add_argument("--rules", required=True)
    c.add_argument("--metrics", required=True)
    c.add_argument("--out", default="out/results.json")
    c.set_defaults(func=_cmd_check)

    r = sub.add_parser("report", help="results JSON -> HTML report")
    r.add_argument("--results", required=True)
    r.add_argument("--out", default="out/report.html")
    r.set_defaults(func=_cmd_report)

    i = sub.add_parser("index", help="build optional ChromaDB index at runtime")
    i.add_argument("source")
    i.add_argument("--db", default="out/chroma")
    i.add_argument("--embeddings", choices=["default", "openai"], default="default")
    i.set_defaults(func=_cmd_index)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))
