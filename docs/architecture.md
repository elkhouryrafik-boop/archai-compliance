# Architecture

Package `archai/`:

| Module | Job |
|---|---|
| `extract/deterministic.py` | Markdown or PDF regulation to a rule graph. Finds numbered clauses and "shall not exceed / at least N unit" patterns. Each rule keeps its article id, clause number and quoted text. |
| `llm.py` | Optional extractor for other documents. `OPENAI_API_KEY` from the environment, schema-validated output, up to 2 retries. Not imported by the offline path. |
| `metrics/compute.py` | Pure functions: area, coverage, floor area ratio, height, floors, unit conversion. No Rhino import. Metrics are computed **per building**; there is no site-level aggregate, so a site-wide FAR is the sum over buildings and must not be read off any single row. |
| `metrics/rhino3dm_reader.py` | Reads a `.3dm` with `rhino3dm` and calls `compute.py`. |
| `metrics/rhino8_script.py` | Same functions through RhinoCommon, for the Rhino 8 Script Editor. |
| `check/evaluator.py` | Compares rules and metrics. Returns PASS, FAIL, MISSING_METRIC or CANNOT_CHECK per building and rule. |
| `report/html.py` | HTML report and `compliance_graph.json`. |
| `index/build.py` | Optional ChromaDB index, built at runtime. |
| `pipeline.py`, `cli.py` | The `demo` pipeline and the `archai` command. |

`plugin/` is a Rhino 8 plug-in (C#) with a dockable panel. It scans layers, writes `metrics.json` and shells out to `python -m archai`.

## Verdicts

| Status | Meaning |
|---|---|
| PASS | The measured value satisfies the rule. |
| FAIL | It does not. |
| MISSING_METRIC | The rule is checkable but the model has no value for it. |
| CANNOT_CHECK | The clause is qualitative, so there is no number to compare. |

## Layer convention

| Layer | Object |
|---|---|
| `SITE::BOUNDARY` | closed planar curve, user text `zone=R2` |
| `BLDG_<id>::FOOTPRINT` | closed planar curve |
| `BLDG_<id>::FLOORS` | any object with user text `floors=N` |
| `BLDG_<id>::MASS` | extrusion, brep or mesh; its z-extent is the height |

## Tests

`tests/` covers the extractor, checker, metrics from the generated `.3dm` files, the report and CLI, and the LLM path with a mocked client (including invalid JSON and retry). Run `python -m pytest -q`.
