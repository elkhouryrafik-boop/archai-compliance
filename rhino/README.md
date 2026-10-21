# Rhino 8 metrics script

`archai_extract_metrics.py` runs inside Rhino 8 (Script Editor, Python 3) and writes the
same `metrics.json` that `python -m archai metrics <file.3dm>` produces with `rhino3dm`.
Both call `archai.metrics.compute.assemble_metrics`.

Layer convention (units: model units are converted to metres):

| Layer | Object |
|---|---|
| `SITE::BOUNDARY` | closed planar curve; user text `zone=R2` |
| `BLDG_<id>::FOOTPRINT` | closed planar curve |
| `BLDG_<id>::FLOORS` | any object with user text `floors=N` |
| `BLDG_<id>::MASS` | extrusion / brep / mesh; its z-extent is the height |

## Manual check (5 steps, run once)

1. `python examples/make_sample.py` (or use the committed `examples/sample-site.3dm`).
2. Open `examples/sample-site.3dm` in Rhino 8.
3. `Tools > Script Editor`, open `rhino/archai_extract_metrics.py`, press Run.
   Console: `wrote ...metrics.json (2 buildings)`.
4. Compare the written `metrics.json` with `examples/metrics.sample.json`
   (identical apart from the `model` name, which comes from the Rhino document name).
5. Repeat with `examples/sample-site-missing.3dm`: `BLDG_B` has no `height_m`, so the report
   shows `MISSING_METRIC` for its height rule.

Not covered by automated tests (they use the `rhino3dm` path on fixture files).
