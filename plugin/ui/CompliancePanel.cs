using System;
using System.Threading.Tasks;
using System.Runtime.InteropServices;
using Eto.Forms;
using Eto.Drawing;
using Rhino;
using ArchaiCompliance.Core;

namespace ArchaiCompliance.UI
{
    [Guid("FDAB2951-EA26-40D7-B00C-76009556C61A")]
    public class CompliancePanel : Panel
    {
        private readonly TextArea _log;

        public CompliancePanel()
        {
            Padding = 10;

            var btnScan = new Button { Text = "1) Scan layers" };
            var btnExport = new Button { Text = "2) Export metrics.json" };
            var btnRun = new Button { Text = "3) Run compliance check" };
            var btnOpen = new Button { Text = "4) Open report" };

            _log = new TextArea { ReadOnly = true, Height = 220 };

            btnScan.Click += (_, __) =>
            {
                try
                {
                    var scan = MetricsExporter.Scan(RhinoDoc.ActiveDoc);
                    Log("Site boundary found: " + scan.HasSiteBoundary);
                    Log("Buildings found: " + scan.BuildingIds.Count);
                    foreach (var id in scan.BuildingIds) Log("- BLDG_" + id);
                    if (scan.Warnings.Count == 0) Log("No warnings.");
                    foreach (var w in scan.Warnings) Log("WARNING: " + w);
                }
                catch (Exception ex) { Log("ERROR: " + ex.Message); }
            };

            btnExport.Click += (_, __) =>
            {
                try
                {
                    var path = MetricsExporter.Export(RhinoDoc.ActiveDoc, ArchaiRunner.MetricsPath);
                    Log("Exported: " + path);
                }
                catch (Exception ex) { Log("ERROR: " + ex.Message); }
            };

            btnRun.Click += async (_, __) =>
            {
                SetEnabled(false, btnScan, btnExport, btnRun, btnOpen);
                try
                {
                    Log("Running: python -m archai extract / check / report ...");
                    var output = await Task.Run(() => ArchaiRunner.RunCheck());
                    Log(output);
                    Log("DONE. Report: " + ArchaiRunner.ReportPath);
                }
                catch (Exception ex) { Log("ERROR: " + ex.Message); }
                finally { SetEnabled(true, btnScan, btnExport, btnRun, btnOpen); }
            };

            btnOpen.Click += (_, __) =>
            {
                try
                {
                    var report = ArchaiRunner.ReportPath;
                    if (!System.IO.File.Exists(report))
                    {
                        Log("Report not found: " + report);
                        return;
                    }
                    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
                    {
                        FileName = report,
                        UseShellExecute = true
                    });
                    Log("Opened report.");
                }
                catch (Exception ex) { Log("ERROR: " + ex.Message); }
            };

            Content = new StackLayout
            {
                Spacing = 10,
                Items =
                {
                    new Label { Text = "ARCHAI Compliance (Rhino 8)", Font = new Font(SystemFont.Bold, 14) },
                    new GroupBox
                    {
                        Text = "Workflow",
                        Content = new StackLayout
                        {
                            Spacing = 8,
                            Items =
                            {
                                new StackLayout { Orientation = Orientation.Horizontal, Spacing = 8, Items = { btnScan, btnExport } },
                                new StackLayout { Orientation = Orientation.Horizontal, Spacing = 8, Items = { btnRun, btnOpen } }
                            }
                        }
                    },
                    new Label { Text = "Log" },
                    _log
                }
            };

            Log("Panel ready. Set ARCHAI_HOME to your archai-compliance checkout (see plugin/README.md).");
        }

        private static void SetEnabled(bool on, params Button[] buttons)
        {
            foreach (var b in buttons) b.Enabled = on;
        }

        private void Log(string msg)
        {
            _log.Append(DateTime.Now.ToString("HH:mm:ss") + "  " + msg + "\n");
            RhinoApp.WriteLine(msg);
        }
    }
}
