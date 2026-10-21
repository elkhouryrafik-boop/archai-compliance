using Rhino;
using Rhino.Commands;
using ArchaiCompliance.UI;

namespace ArchaiCompliance
{
    /// <summary>Rhino command ArchaiCompliance: opens the panel.</summary>
    public class ArchaiCommand : Command
    {
        public override string EnglishName => "ArchaiCompliance";

        protected override Result RunCommand(RhinoDoc doc, RunMode mode)
        {
            RhinoApp.WriteLine("Opening ARCHAI Compliance panel...");
            CompliancePanelHost.Show();
            return Result.Success;
        }
    }
}
