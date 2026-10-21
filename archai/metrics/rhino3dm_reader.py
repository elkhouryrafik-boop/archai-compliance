"""Read the layer convention from a ``.3dm`` file with ``rhino3dm`` (plain CPython, no Rhino).

Layers: ``SITE::BOUNDARY`` (closed curve, user text ``zone=R2``) and
``BLDG_<id>::FOOTPRINT`` (closed curve), ``::FLOORS`` (any object with user text
``floors=N``), ``::MASS`` (extrusion / brep / mesh whose z-extent is the height).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rhino3dm

from archai.metrics.compute import assemble_metrics, parse_layer

MODEL_NAME = "ARCHAI synthetic sample"


def _layer_paths(model: rhino3dm.File3dm) -> dict[int, str]:
    layers = {str(layer.Id): layer for layer in model.Layers}
    paths: dict[int, str] = {}
    for idx, layer in enumerate(model.Layers):
        names, cur, guard = [layer.Name], layer, 0
        while str(cur.ParentLayerId) in layers and guard < 16:
            cur = layers[str(cur.ParentLayerId)]
            names.append(cur.Name)
            guard += 1
        paths[idx] = "::".join(reversed(names))
    return paths


def _curve_ring(geom: Any) -> list[tuple[float, float]] | None:
    if isinstance(geom, rhino3dm.PolylineCurve):
        return [(geom.Point(i).X, geom.Point(i).Y) for i in range(geom.PointCount)]
    if isinstance(geom, rhino3dm.Curve):
        ok, poly = geom.TryGetPolyline()
        if ok:
            return [(poly[i].X, poly[i].Y) for i in range(poly.Count)]
    return None


def _mass_points(geom: Any) -> list[tuple[float, float, float]] | None:
    bb = geom.GetBoundingBox()
    if not bb.IsValid:
        return None
    return [(bb.Min.X, bb.Min.Y, bb.Min.Z), (bb.Max.X, bb.Max.Y, bb.Max.Z)]


def read_model(path: Path | str) -> dict[str, Any]:
    """Return the ``metrics.json`` document for a ``.3dm`` following the layer convention."""
    model = rhino3dm.File3dm.Read(str(path))
    if model is None:
        raise ValueError(f"cannot read {path} as a .3dm file")
    paths = _layer_paths(model)
    parts: dict[str, dict[str, Any]] = {}
    zone: str | None = None
    for obj in model.Objects:
        parsed = parse_layer(paths.get(obj.Attributes.LayerIndex, ""))
        if parsed is None:
            continue
        bid, part = parsed
        slot = parts.setdefault(bid, {})
        geom = obj.Geometry
        if part == "BOUNDARY":
            ring = _curve_ring(geom)
            if ring:
                slot["boundary"] = ring
            zone = obj.Attributes.GetUserString("zone") or zone
        elif part == "FOOTPRINT":
            ring = _curve_ring(geom)
            if ring:
                slot["footprint"] = ring
        elif part == "FLOORS":
            value = obj.Attributes.GetUserString("floors")
            if value:
                slot["floors"] = value
        elif part == "MASS":
            pts = _mass_points(geom)
            if pts:
                slot["mass"] = pts
    return assemble_metrics(MODEL_NAME, parts, zone=zone)
