"""Generate the synthetic sample inputs (all invented).

Writes ``corpus/dreamtown/regulation.pdf`` (rendered from the Markdown with fpdf2),
``examples/metrics.sample.json`` and ``examples/expected-report.html``.
Also writes ``examples/sample-site.3dm`` and ``sample-site-missing.3dm`` (rhino3dm).

Run:  python examples/make_sample.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from archai.metrics.compute import building_metrics, polygon_area

# Invented geometry, metres, near the origin.
SITE = [(0, 0), (96, 0), (96, 100), (0, 100)]  # 9,600 m2
BUILDINGS = {
    "A": {"footprint": [(10, 10), (55, 10), (55, 50), (10, 50)], "floors": 7, "height": 24.5},
    "B": {"footprint": [(60, 20), (90, 20), (90, 60), (60, 60)], "floors": 4, "height": 14.0},
}


def make_pdf(md: Path, pdf: Path) -> None:
    from fpdf import FPDF

    doc = FPDF()
    doc.set_title("DreamTown Urban Regulation (fictional)")
    doc.set_author("archai-compliance")
    doc.add_page()
    for raw in md.read_text(encoding="utf-8").splitlines():
        line = raw.lstrip("> ").strip()
        if line.startswith("# "):
            doc.set_font("Helvetica", "B", 16)
            line = line[2:]
        elif line.startswith("## "):
            doc.set_font("Helvetica", "B", 12)
            line = line[3:]
        else:
            doc.set_font("Helvetica", "", 10)
        if not line:
            doc.ln(3)
            continue
        doc.multi_cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    pdf.parent.mkdir(parents=True, exist_ok=True)
    doc.output(str(pdf))


def _layer(model, name: str, parent=None):
    import rhino3dm

    layer = rhino3dm.Layer()
    layer.Name = name
    if parent is not None:
        layer.ParentLayerId = parent.Id
    model.Layers.Add(layer)
    return model.Layers.FindIndex(len(model.Layers) - 1)


def scrub_3dm(path: Path) -> None:
    """Remove the OS user name and absolute path openNURBS writes into every .3dm.

    Replacements keep the byte length, then the CRC32 of each record chunk whose checksum
    was valid is recomputed, so the file stays valid. The file is re-read afterwards.
    """
    import getpass
    import re
    import struct
    import zlib

    import rhino3dm

    data = bytearray(path.read_bytes())
    user = getpass.getuser()

    def crc_chunks(buf: bytearray) -> list[tuple[int, int]]:
        """(data_start, crc_pos) of record chunks directly under table chunks."""
        found: list[tuple[int, int]] = []
        pos = 32
        while pos + 12 <= len(buf):
            code, length = struct.unpack_from("<Iq", buf, pos)
            if code & 0x80000000:
                pos += 12
                continue
            body, stop = pos + 12, pos + 12 + length
            if code & 0x10000000 and not code & 0x8000:
                sub = body
                while sub + 12 <= stop:
                    scode, slen = struct.unpack_from("<Iq", buf, sub)
                    if scode & 0x80000000:
                        sub += 12
                        continue
                    if scode & 0x8000:
                        found.append((sub + 12, sub + 12 + slen - 4))
                    sub += 12 + slen
            pos = stop
        return found

    def crc_ok(buf: bytearray, start: int, crc_pos: int) -> bool:
        (stored,) = struct.unpack_from("<I", buf, crc_pos)
        return zlib.crc32(bytes(buf[start:crc_pos])) == stored

    verified = [c for c in crc_chunks(data) if crc_ok(data, *c)]

    def utf16(text: str) -> bytes:
        return text.encode("utf-16le")

    # absolute path strings: C:\... up to the NUL terminator -> bare file name + NUL padding
    for m in list(re.finditer(rb"(?:[ -~]\x00)+", bytes(data))):
        text = m.group().decode("utf-16le")
        if re.match(r"[A-Za-z]:\\", text) or r"\Users" in text:
            repl = utf16(path.name)[: len(m.group())].ljust(len(m.group()), b"\x00")
            data[m.start() : m.end()] = repl
    fake = (("archai_user" * 4)[: len(user)]).encode("utf-16le")
    data = bytearray(bytes(data).replace(utf16(user), fake))

    for start, crc_pos in verified:  # CRCs that were valid must stay valid
        struct.pack_into("<I", data, crc_pos, zlib.crc32(bytes(data[start:crc_pos])))
    path.write_bytes(bytes(data))
    if rhino3dm.File3dm.Read(str(path)) is None:
        raise RuntimeError(f"{path} unreadable after scrub")
    raw = path.read_bytes()
    if utf16(user) in raw or user.encode() in raw:
        raise RuntimeError(f"{path} still contains the OS user name")


def make_3dm(path: Path, with_missing_mass: bool = False) -> None:
    """Write a synthetic site model following the layer convention (metres)."""
    import rhino3dm

    model = rhino3dm.File3dm()
    model.Settings.ModelUnitSystem = rhino3dm.UnitSystem.Meters

    def ring_curve(pts):
        poly = rhino3dm.Polyline(0)
        for x, y in pts + [pts[0]]:
            poly.Add(x, y, 0.0)
        return poly.ToPolylineCurve()

    def attrs(layer, **user_text):
        a = rhino3dm.ObjectAttributes()
        a.LayerIndex = layer.Index
        for k, v in user_text.items():
            a.SetUserString(k, str(v))
        return a

    site = _layer(model, "SITE")
    boundary = _layer(model, "BOUNDARY", site)
    model.Objects.AddCurve(ring_curve(SITE), attrs(boundary, zone="R2"))
    for bid, b in BUILDINGS.items():
        parent = _layer(model, f"BLDG_{bid}")
        fp = _layer(model, "FOOTPRINT", parent)
        fl = _layer(model, "FLOORS", parent)
        mass = _layer(model, "MASS", parent)
        curve = ring_curve(b["footprint"])
        model.Objects.AddCurve(curve, attrs(fp))
        cx = sum(x for x, _ in b["footprint"]) / 4
        cy = sum(y for _, y in b["footprint"]) / 4
        model.Objects.AddPoint(
            rhino3dm.Point3d(cx, cy, 0.0), attrs(fl, floors=f"floors={b['floors']}")
        )
        if with_missing_mass and bid == "B":
            continue  # layer exists, geometry deliberately absent -> MISSING_METRIC
        ext = rhino3dm.Extrusion.Create(ring_curve(b["footprint"]), b["height"], True)
        model.Objects.AddExtrusion(ext, attrs(mass))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not model.Write(str(path), 7):
        raise RuntimeError(f"could not write {path}")
    scrub_3dm(path)


def make_metrics() -> dict:
    site_area = round(polygon_area(SITE), 2)
    return {
        "model": "ARCHAI synthetic sample",
        "units": "m",
        "site": {"zone": "R2", "plot_area_m2": site_area},
        "buildings": [
            building_metrics(
                f"BLDG_{bid}",
                b["footprint"],
                b["floors"],
                [(x, y, 0.0) for x, y in b["footprint"]]
                + [(x, y, b["height"]) for x, y in b["footprint"]],
                site_area,
            )
            for bid, b in BUILDINGS.items()
        ],
    }


def main() -> None:
    from archai.pipeline import run_demo

    make_pdf(ROOT / "corpus/dreamtown/regulation.md", ROOT / "corpus/dreamtown/regulation.pdf")
    make_3dm(ROOT / "examples/sample-site.3dm")
    make_3dm(ROOT / "examples/sample-site-missing.3dm", with_missing_mass=True)
    metrics = make_metrics()
    (ROOT / "examples/metrics.sample.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    tmp = ROOT / "out" / "sample"
    run_demo(tmp)
    (ROOT / "examples/expected-report.html").write_text(
        (tmp / "report.html").read_text(encoding="utf-8"), encoding="utf-8"
    )
    print("sample inputs written")


if __name__ == "__main__":
    main()
