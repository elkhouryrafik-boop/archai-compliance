using System;
using System.Diagnostics;
using System.IO;
using System.Text;

namespace ArchaiCompliance.Core
{
    /// <summary>
    /// Runs the Python CLI of this repository (python -m archai ...).
    /// Configuration is by environment variable only; nothing is hard-coded:
    ///   ARCHAI_HOME       root of the archai-compliance checkout (required)
    ///   ARCHAI_PYTHON     python executable (default: "python" on PATH)
    ///   ARCHAI_WORKDIR    where metrics/results/report are written
    ///                     (default: %LocalAppData%\ARCHAI\work)
    ///   ARCHAI_REGULATION regulation .md/.pdf (default: corpus/dreamtown/regulation.md)
    /// </summary>
    public static class ArchaiRunner
    {
        public static string Home
        {
            get
            {
                var v = Environment.GetEnvironmentVariable("ARCHAI_HOME");
                if (string.IsNullOrWhiteSpace(v))
                    throw new Exception("ARCHAI_HOME is not set. Point it at your archai-compliance checkout and restart Rhino.");
                return v.Trim();
            }
        }

        public static string Python
        {
            get
            {
                var v = Environment.GetEnvironmentVariable("ARCHAI_PYTHON");
                return string.IsNullOrWhiteSpace(v) ? "python" : v.Trim();
            }
        }

        public static string WorkDir
        {
            get
            {
                var v = Environment.GetEnvironmentVariable("ARCHAI_WORKDIR");
                if (!string.IsNullOrWhiteSpace(v)) return v.Trim();
                return Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "ARCHAI", "work");
            }
        }

        public static string Regulation
        {
            get
            {
                var v = Environment.GetEnvironmentVariable("ARCHAI_REGULATION");
                return !string.IsNullOrWhiteSpace(v)
                    ? v.Trim()
                    : Path.Combine(Home, "corpus", "dreamtown", "regulation.md");
            }
        }

        public static string MetricsPath => Path.Combine(WorkDir, "metrics.json");
        public static string RulesPath => Path.Combine(WorkDir, "rule_graph.json");
        public static string ResultsPath => Path.Combine(WorkDir, "results.json");
        public static string ReportPath => Path.Combine(WorkDir, "report.html");

        private static string Q(string s) => "\"" + s.Replace("\"", "\\\"") + "\"";

        /// <summary>Runs "python -m archai ARGS"; throws with the captured stderr on a non-zero exit.</summary>
        public static string RunArchai(string args)
        {
            Directory.CreateDirectory(WorkDir);
            var psi = new ProcessStartInfo
            {
                FileName = Python,
                Arguments = "-m archai " + args,
                WorkingDirectory = Home,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            var stdout = new StringBuilder();
            var stderr = new StringBuilder();
            using (var p = new Process { StartInfo = psi })
            {
                p.OutputDataReceived += (_, e) => { if (e.Data != null) stdout.AppendLine(e.Data); };
                p.ErrorDataReceived += (_, e) => { if (e.Data != null) stderr.AppendLine(e.Data); };
                try { p.Start(); }
                catch (Exception ex)
                {
                    throw new Exception("Could not start " + Python + ": " + ex.Message + " (set ARCHAI_PYTHON)");
                }
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                p.WaitForExit();
                if (p.ExitCode != 0)
                    throw new Exception("archai " + args + " failed (exit " + p.ExitCode + "):\n" + stderr);
            }
            return stdout.ToString().Trim();
        }

        /// <summary>extract, then check, then report, using the metrics.json the panel exported.</summary>
        public static string RunCheck()
        {
            if (!File.Exists(MetricsPath))
                throw new Exception("No metrics.json yet. Run step 2 (Export metrics) first.");

            var log = new StringBuilder();
            log.AppendLine(RunArchai("extract " + Q(Regulation) + " --out " + Q(RulesPath)));
            log.AppendLine(RunArchai("check --rules " + Q(RulesPath) + " --metrics " + Q(MetricsPath) + " --out " + Q(ResultsPath)));
            log.AppendLine(RunArchai("report --results " + Q(ResultsPath) + " --out " + Q(ReportPath)));
            return log.ToString().Trim();
        }
    }
}
