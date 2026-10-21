using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using Rhino;
using Rhino.DocObjects;
using Rhino.Geometry;

namespace ArchaiCompliance.Core
{
    public class ScanResult
    {
        public bool HasSiteBoundary { get; set; }
        public List<string> BuildingIds { get; } = new List<string>();
        public List<string> Warnings { get; } = new List<string>();
    }

    /// <summary>
    /// Reads the ARCHAI layer convention from the active Rhino document and writes the same
    /// metrics.json as archai/metrics/rhino8_script.py and the rhino3dm reader:
    ///   SITE::BOUNDARY            closed planar curve, user text zone=R2
    ///   BLDG_id::FOOTPRINT        closed planar curve
    ///   BLDG_id::FLOORS           any object with user text floors=N
    ///   BLDG_id::MASS             extrusion / brep / mesh; z-extent is the height
    /// A missing part leaves its metrics out, so the checker reports MISSING_METRIC.
    /// </summary>
    public static class MetricsExporter
    {
        private const string SiteLayer = "SITE::BOUNDARY";
        private const string BldgPrefix = "BLDG_";
        private static readonly string[] Parts = { "FOOTPRINT", "FLOORS", "MASS" };

        public static ScanResult Scan(RhinoDoc doc)
        {
            if (doc == null) throw new Exception("No active Rhino document.");
            var res = new ScanResult();
            res.HasSiteBoundary = doc.Layers.FindByFullPath(SiteLayer, RhinoMath.UnsetIntIndex) >= 0;
            if (!res.HasSiteBoundary)
                res.Warnings.Add("Missing layer: " + SiteLayer + " (needed for FAR and coverage).");

            var ids = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var layer in doc.Layers)
            {
                if (layer == null || layer.IsDeleted) continue;
                var parsed = ParseLayer(layer.FullPath);
                if (parsed != null && parsed.Item1 != "SITE") ids.Add(parsed.Item1);
            }
            res.BuildingIds.AddRange(ids);
            if (res.BuildingIds.Count == 0)
                res.Warnings.Add("No buildings found. Expected layers like BLDG_A::FOOTPRINT.");

            foreach (var id in res.BuildingIds)
                foreach (var part in Parts)
                    if (doc.Layers.FindByFullPath(BldgPrefix + id + "::" + part, RhinoMath.UnsetIntIndex) < 0)
                        res.Warnings.Add(BldgPrefix + id + ": no " + part + " layer (its metrics will be MISSING_METRIC).");
            return res;
        }

        /// <summary>Returns (id, part): "BLDG_A::MASS" gives ("A","MASS"); the site layer gives ("SITE","BOUNDARY").</summary>
        internal static Tuple<string, string> ParseLayer(string fullPath)
        {
            if (fullPath == SiteLayer) return Tuple.Create("SITE", "BOUNDARY");
            if (fullPath == null) return null;
            int cut = fullPath.LastIndexOf("::", StringComparison.Ordinal);
            if (cut < 0) return null;
            string head = fullPath.Substring(0, cut);
            string part = fullPath.Substring(cut + 2);
            if (head.StartsWith(BldgPrefix, StringComparison.Ordinal) && Array.IndexOf(Parts, part) >= 0)
                return Tuple.Create(head.Substring(BldgPrefix.Length), part);
            return null;
        }

        public static string Export(RhinoDoc doc, string outPath)
        {
            if (doc == null) throw new Exception("No active Rhino document.");
            double k = RhinoMath.UnitScale(doc.ModelUnitSystem, UnitSystem.Meters);

            var curves = new Dictionary<string, List<Curve>>();   // key: "SITE|BOUNDARY" or "A|FOOTPRINT"
            var floors = new Dictionary<string, string>();        // building id -> user text value
            var mass = new Dictionary<string, BoundingBox>();     // building id -> union bbox
            string zone = null;

            foreach (RhinoObject obj in doc.Objects)
            {
                if (obj == null || obj.IsDeleted) continue;
                var layer = doc.Layers[obj.Attributes.LayerIndex];
                var parsed = layer == null ? null : ParseLayer(layer.FullPath);
                if (parsed == null) continue;
                string id = parsed.Item1, part = parsed.Item2;
                var geom = obj.Geometry;

                if (part == "BOUNDARY" || part == "FOOTPRINT")
                {
                    if (geom is Curve c)
                    {
                        string key = id + "|" + part;
                        if (!curves.ContainsKey(key)) curves[key] = new List<Curve>();
                        curves[key].Add(c.DuplicateCurve());
                    }
                    if (part == "BOUNDARY")
                    {
                        var z = obj.Attributes.GetUserString("zone");
                        if (!string.IsNullOrWhiteSpace(z)) zone = z.Trim();
                    }
                }
                else if (part == "FLOORS")
                {
                    var v = obj.Attributes.GetUserString("floors");
                    if (!string.IsNullOrWhiteSpace(v)) floors[id] = v;
                }
                else if (part == "MASS")
                {
                    var bb = geom.GetBoundingBox(true);
                    if (bb.IsValid)
                    {
                        if (mass.TryGetValue(id, out var cur)) { cur.Union(bb); mass[id] = cur; }
                        else mass[id] = bb;
                    }
                }
            }

            double? siteArea = AreaOf(curves, "SITE|BOUNDARY", doc.ModelAbsoluteTolerance, k);
            var site = new JObject();
            if (zone != null) site["zone"] = zone;
            if (siteArea.HasValue) site["plot_area_m2"] = Math.Round(siteArea.Value, 2);

            var ids = new SortedSet<string>(StringComparer.Ordinal);
            foreach (var key in curves.Keys) ids.Add(key.Split('|')[0]);
            foreach (var id in floors.Keys) ids.Add(id);
            foreach (var id in mass.Keys) ids.Add(id);
            ids.Remove("SITE");

            var buildings = new JArray();
            foreach (var id in ids)
            {
                var b = new JObject { ["id"] = BldgPrefix + id };
                double? fp = AreaOf(curves, id + "|FOOTPRINT", doc.ModelAbsoluteTolerance, k);
                int? nFloors = ParseFloors(floors.ContainsKey(id) ? floors[id] : null);
                if (fp.HasValue) b["footprint_area_m2"] = Math.Round(fp.Value, 2);
                if (nFloors.HasValue) b["floors"] = nFloors.Value;
                if (mass.ContainsKey(id))
                    b["height_m"] = Math.Round((mass[id].Max.Z - mass[id].Min.Z) * k, 2);
                if (fp.HasValue && nFloors.HasValue)
                {
                    b["gross_floor_area_m2"] = Math.Round(fp.Value * nFloors.Value, 2);
                    if (siteArea.HasValue && siteArea.Value > 0)
                        b["far"] = Math.Round(fp.Value * nFloors.Value / siteArea.Value, 3);
                }
                if (fp.HasValue && siteArea.HasValue && siteArea.Value > 0)
                    b["site_coverage_pct"] = Math.Round(100.0 * fp.Value / siteArea.Value, 2);
                buildings.Add(b);
            }

            var doc3 = new JObject
            {
                ["model"] = string.IsNullOrEmpty(doc.Name) ? "untitled" : doc.Name,
                ["units"] = "m",
                ["site"] = site,
                ["buildings"] = buildings
            };

            Directory.CreateDirectory(Path.GetDirectoryName(outPath));
            File.WriteAllText(outPath, doc3.ToString(Newtonsoft.Json.Formatting.Indented));
            return outPath;
        }

        // ---------- helpers ----------

        private static double? AreaOf(Dictionary<string, List<Curve>> curves, string key, double tol, double k)
        {
            if (!curves.TryGetValue(key, out var list) || list.Count == 0) return null;
            var joined = Curve.JoinCurves(list, tol);
            var best = (joined != null && joined.Length > 0)
                ? joined.OrderByDescending(x => x.GetLength()).First()
                : list[0];
            if (!best.IsClosed) return null;
            var amp = AreaMassProperties.Compute(best);
            return amp == null ? (double?)null : amp.Area * k * k;
        }

        /// <summary>Accepts "7", "7.0" or "floors=7"; anything else gives null.</summary>
        internal static int? ParseFloors(string value)
        {
            if (string.IsNullOrWhiteSpace(value)) return null;
            string text = value.Trim();
            int eq = text.IndexOf('=');
            if (eq >= 0)
            {
                if (!text.Substring(0, eq).Trim().Equals("floors", StringComparison.OrdinalIgnoreCase)) return null;
                text = text.Substring(eq + 1).Trim();
            }
            if (double.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out var d) && d >= 0)
                return (int)d;
            return null;
        }
    }
}
