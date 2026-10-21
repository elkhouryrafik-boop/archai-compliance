"""Rhino 8 (RhinoCommon, Python 3) metrics extraction using the shared compute functions.

Only importable inside Rhino: it needs ``Rhino`` and ``scriptcontext``. Everything it
imports besides those is the standard library and ``archai.metrics.compute``.
Model units are converted to metres.
"""

import json
import os

import scriptcontext as sc

import Rhino
from archai.metrics.compute import assemble_metrics, parse_layer


def _scale(doc):
    return Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Meters)


def _ring(curve, k):
    ok, poly = curve.TryGetPolyline()
    if ok:
        return [(p.X * k, p.Y * k) for p in poly]
    return None


def collect(doc):
    k = _scale(doc)
    parts, zone = {}, None
    for obj in doc.Objects:
        if obj.IsDeleted:
            continue
        layer = doc.Layers[obj.Attributes.LayerIndex]
        parsed = parse_layer(layer.FullPath)
        if parsed is None:
            continue
        bid, part = parsed
        slot = parts.setdefault(bid, {})
        geom = obj.Geometry
        if part == "BOUNDARY":
            if isinstance(geom, Rhino.Geometry.Curve):
                slot["boundary"] = _ring(geom, k)
            zone = obj.Attributes.GetUserString("zone") or zone
        elif part == "FOOTPRINT" and isinstance(geom, Rhino.Geometry.Curve):
            slot["footprint"] = _ring(geom, k)
        elif part == "FLOORS":
            value = obj.Attributes.GetUserString("floors")
            if value:
                slot["floors"] = value
        elif part == "MASS":
            bb = geom.GetBoundingBox(True)
            if bb.IsValid:
                slot["mass"] = [
                    (bb.Min.X * k, bb.Min.Y * k, bb.Min.Z * k),
                    (bb.Max.X * k, bb.Max.Y * k, bb.Max.Z * k),
                ]
    return parts, zone


def run(doc=None):
    doc = doc or sc.doc
    parts, zone = collect(doc)
    metrics = assemble_metrics(doc.Name or "untitled", parts, zone=zone)
    out = os.environ.get("ARCHAI_METRICS_OUT")
    if not out:
        folder = os.path.dirname(doc.Path) if doc.Path else os.getcwd()
        out = os.path.join(folder, "metrics.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"wrote {out} ({len(metrics['buildings'])} buildings)")
    return metrics
