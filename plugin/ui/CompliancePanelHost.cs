using System;
using Rhino.UI;

namespace ArchaiCompliance.UI
{
    public static class CompliancePanelHost
    {
        // Must match the [Guid(...)] on CompliancePanel.
        public static readonly Guid PanelId = new Guid("FDAB2951-EA26-40D7-B00C-76009556C61A");

        public static void Register()
        {
            Panels.RegisterPanel(
                ArchaiPlugin.Instance,
                typeof(CompliancePanel),
                "ARCHAI Compliance",
                System.Drawing.SystemIcons.Information
            );
        }

        public static void Show()
        {
            Panels.OpenPanel(PanelId);
        }
    }
}
