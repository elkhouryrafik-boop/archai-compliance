"""Pure metric functions (no Rhino import) shared by the rhino3dm reader and the Rhino 8 script.

Geometry is passed as plain ``[(x, y), ...]`` / ``[(x, y, z), ...]`` lists, units metres.
Layer convention: ``SITE::BOUNDARY`` and ``BLDG_<id>::FOOTPRINT|FLOORS|MASS``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

SITE_LAYER = "SITE::BOUNDARY"
BLDG_PREFIX = "BLDG_"
PARTS = ("FOOTPRINT", "FLOORS", "MASS")


def polygon_area(points: Sequence[Sequence[float]]) -> float:
    """Planar area (shoelace) of a closed or open ring; absolute value."""
    pts = [(p[0], p[1]) for p in points]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    s = 0.0
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def z_extent(points: Iterable[Sequence[float]]) -> float:
    zs = [p[2] for p in points]
    return (max(zs) - min(zs)) if zs else 0.0


def parse_layer(full_name: str) -> tuple[str, str] | None:
    """``BLDG_A::MASS`` -> (``A``, ``MASS``); site boundary -> (``SITE``, ``BOUNDARY``)."""
    if full_name == SITE_LAYER:
        return "SITE", "BOUNDARY"
    if "::" not in full_name:
        return None
    head, part = full_name.rsplit("::", 1)
    if head.startswith(BLDG_PREFIX) and part in PARTS:
        return head[len(BLDG_PREFIX) :], part
    return None


def building_metrics(
    bid: str,
    footprint: Sequence | None,
    floors: int | None,
    mass_points: Sequence | None,
    site_area: float | None,
) -> dict[str, Any]:
    """Derive per-building metrics; absent inputs leave their metrics out (-> MISSING_METRIC)."""
    m: dict[str, Any] = {"id": bid}
    fp = polygon_area(footprint) if footprint else None
    if fp is not None:
        m["footprint_area_m2"] = round(fp, 2)
    if floors is not None:
        m["floors"] = int(floors)
    if mass_points:
        m["height_m"] = round(z_extent(mass_points), 2)
    if fp is not None and floors is not None:
        m["gross_floor_area_m2"] = round(fp * floors, 2)
        if site_area:
            m["far"] = round(fp * floors / site_area, 3)
    if fp is not None and site_area:
        m["site_coverage_pct"] = round(100.0 * fp / site_area, 2)
    return m


def parse_floors(value: Any) -> int | None:
    """Accept ``7``, ``"7"`` or ``"floors=7"`` (user-text form); anything else -> None."""
    if value is None:
        return None
    text = str(value).strip()
    if "=" in text:
        key, _, text = text.partition("=")
        if key.strip().lower() != "floors":
            return None
    try:
        n = int(float(text.strip()))
    except ValueError:
        return None
    return n if n >= 0 else None


def assemble_metrics(
    model: str,
    parts: dict[str, dict[str, Any]],
    zone: str | None = None,
) -> dict[str, Any]:
    """Build the ``metrics.json`` document from per-layer geometry.

    ``parts`` maps a layer id (``"SITE"`` or ``"A"``) to a dict with optional keys
    ``boundary`` / ``footprint`` (xy ring), ``floors`` (int or user-text) and ``mass``
    (xyz points). Both the rhino3dm reader and the Rhino 8 script call this function,
    so they cannot drift apart. Missing parts simply leave their metrics out.
    """
    site = parts.get("SITE", {})
    boundary = site.get("boundary")
    site_area = round(polygon_area(boundary), 2) if boundary else None
    site_doc: dict[str, Any] = {}
    if zone:
        site_doc["zone"] = zone
    if site_area is not None:
        site_doc["plot_area_m2"] = site_area
    buildings = [
        building_metrics(
            f"{BLDG_PREFIX}{bid}",
            p.get("footprint"),
            parse_floors(p.get("floors")),
            p.get("mass"),
            site_area,
        )
        for bid, p in sorted(parts.items())
        if bid != "SITE"
    ]
    return {"model": model, "units": "m", "site": site_doc, "buildings": buildings}
