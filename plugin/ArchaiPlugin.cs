using Rhino.PlugIns;

namespace ArchaiCompliance
{
    /// <summary>The single PlugIn-derived class of the .rhp. Rhino instantiates it.</summary>
    public class ArchaiPlugin : PlugIn
    {
        public ArchaiPlugin()
        {
            Instance = this;
        }

        public static ArchaiPlugin Instance { get; private set; }

        protected override LoadReturnCode OnLoad(ref string errorMessage)
        {
            UI.CompliancePanelHost.Register();
            return LoadReturnCode.Success;
        }
    }
}
