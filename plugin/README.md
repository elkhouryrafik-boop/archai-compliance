# ARCHAI Compliance — Rhino 8 plug-in (`.rhp`)

A dockable Rhino 8 panel (Windows) that reads the ARCHAI layer convention from the open
document, exports `metrics.json`, and runs this repository's CLI
(`python -m archai extract | check | report`). The checking logic stays in Python; the plug-in
only collects geometry and shells out.

Credit: co-authored with a classmate (original plug-in skeleton, panel and layer scan). See the repository README credits.

## Layer convention

| Layer | Object |
|---|---|
| `SITE::BOUNDARY` | closed planar curve; user text `zone=R2` |
| `BLDG_<id>::FOOTPRINT` | closed planar curve |
| `BLDG_<id>::FLOORS` | any object with user text `floors=N` |
| `BLDG_<id>::MASS` | extrusion / brep / mesh; its z-extent is the height |

Model units are converted to metres. A missing part leaves its metrics out and the checker
reports `MISSING_METRIC`. The output has the same schema as `examples/metrics.sample.json`.

## Build

Needs the .NET SDK (7 or newer) on Windows. NuGet restores `RhinoCommon` 8.0.x and `Newtonsoft.Json`.

```
cd plugin
dotnet build -c Release
```

Output: `bin/Release/net7.0-windows/ArchaiCompliance.rhp` (Rhino 8 default runtime) and
`bin/Release/net48/ArchaiCompliance.rhp` (.NET Framework runtime). `bin/` and `obj/` are git-ignored.

## Configuration (environment variables only)

| Variable | Meaning | Default |
|---|---|---|
| `ARCHAI_HOME` | path of this repository checkout (required) | — |
| `ARCHAI_PYTHON` | Python with `pip install -e .` done, e.g. the repo `.venv` interpreter | `python` on PATH |
| `ARCHAI_WORKDIR` | where `metrics.json`, `results.json`, `report.html` are written | `%LocalAppData%\ARCHAI\work` |
| `ARCHAI_REGULATION` | regulation `.md` / `.pdf` | `corpus/dreamtown/regulation.md` |

No API key is used by the plug-in.

## Manual load test (not automated — needs Rhino 8)

1. Build as above; set `ARCHAI_HOME` (and `ARCHAI_PYTHON`) and restart Rhino.
2. In Rhino 8 run `_PlugInManager`, click *Install...*, pick `ArchaiCompliance.rhp` from `bin/Release/net7.0-windows/`.
3. Open `examples/sample-site.3dm`; run the command `ArchaiCompliance` (the panel "ARCHAI Compliance" opens).
4. Press 1 *Scan layers* (expect: site boundary found, `BLDG_A`, `BLDG_B`, no warnings), 2 *Export metrics.json*
   (compare with `examples/metrics.sample.json`; only `model` differs), 3 *Run compliance check*, 4 *Open report*
   (BLDG_A fails height and floors, BLDG_B passes).
5. Repeat with `examples/sample-site-missing.3dm`: the scan warns about `BLDG_B::MASS`, the report shows `MISSING_METRIC`.
