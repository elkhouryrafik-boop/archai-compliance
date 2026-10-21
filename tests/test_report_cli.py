"""Report rendering, pipeline and CLI."""

import json

from archai.cli import main
from archai.pipeline import run_demo
from archai.report import compliance_graph, render_html, summarize

REG = {"title": "T", "source": "s"}
RES = [
    {
        "object_id": "BLDG_<A>",
        "rule_id": "C2-2.1",
        "article": "C2",
        "article_title": "Building height",
        "clause": "2.1",
        "quote": "Height shall not exceed 21 m.",
        "metric": "height_m",
        "status": "FAIL",
        "measured": 24.5,
        "required": "<= 21",
        "unit": "m",
        "message": "Does not comply",
    },
    {
        "object_id": "BLDG_B",
        "rule_id": "C8-8.1",
        "article": "C8",
        "article_title": "Design",
        "clause": "8.1",
        "quote": "Respect character.",
        "metric": None,
        "status": "CANNOT_CHECK",
        "measured": None,
        "required": "",
        "unit": None,
        "message": "n/a",
    },
]


def test_summarize_counts_all_statuses():
    assert summarize(RES) == {"PASS": 0, "FAIL": 1, "MISSING_METRIC": 0, "CANNOT_CHECK": 1}


def test_html_cites_article_and_quote():
    html = render_html(RES, REG)
    assert "Article C2, clause 2.1" in html and "Height shall not exceed 21 m." in html


def test_html_escapes_markup():
    html = render_html(RES, REG)
    assert "BLDG_<A>" not in html and "BLDG_&lt;A&gt;" in html


def test_html_banner_optional():
    assert "BANNERTEXT" in render_html(RES, REG, banner="BANNERTEXT")
    assert 'class="banner"' not in render_html(RES, REG)


def test_compliance_graph_shape():
    g = compliance_graph({"regulation": {"title": "T"}, "nodes": [], "edges": []}, {"m": 1}, RES)
    assert set(g) == {"regulation", "nodes", "edges", "metrics", "results", "summary"}
    assert g["summary"]["FAIL"] == 1


def test_run_demo_writes_all_outputs(tmp_path):
    info = run_demo(tmp_path / "o")
    for name in ("rule_graph.json", "results.json", "compliance_graph.json", "report.html"):
        assert (tmp_path / "o" / name).is_file()
    assert info["checks"] == sum(info["summary"].values())
    assert info["summary"]["FAIL"] >= 2 and info["summary"]["PASS"] >= 2


def test_demo_report_banner_says_fictional(tmp_path):
    run_demo(tmp_path)
    assert "DreamTown is fictional" in (tmp_path / "report.html").read_text("utf-8")


def test_demo_is_deterministic(tmp_path):
    run_demo(tmp_path / "a")
    run_demo(tmp_path / "b")
    a = (tmp_path / "a" / "results.json").read_text("utf-8")
    assert a == (tmp_path / "b" / "results.json").read_text("utf-8")


def test_cli_demo_offline_exit_zero(tmp_path, capsys):
    assert main(["demo", "--offline", "--out", str(tmp_path)]) == 0
    assert "checks ->" in capsys.readouterr().out


def test_cli_extract_check_report_chain(tmp_path, reg_md, metrics_json, capsys):
    rg, rs, rp = tmp_path / "g.json", tmp_path / "r.json", tmp_path / "r.html"
    assert main(["extract", str(reg_md), "--out", str(rg)]) == 0
    args = ["check", "--rules", str(rg), "--metrics", str(metrics_json), "--out", str(rs)]
    assert main(args) == 0
    counts = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert counts["FAIL"] >= 2
    assert main(["report", "--results", str(rs), "--out", str(rp)]) == 0
    assert "Article C2" in rp.read_text("utf-8")


def test_demo_runs_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert main(["demo", "--offline", "--out", str(tmp_path)]) == 0
