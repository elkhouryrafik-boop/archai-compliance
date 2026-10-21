#! python3
"""ARCHAI: write metrics.json for the active Rhino 8 document.

Open the model, then run this file from the Script Editor (Python 3).
Output goes next to the .3dm, or to the path in the ARCHAI_METRICS_OUT variable.
See rhino/README.md for the manual check.

Imports: sys/os (stdlib) and archai.metrics.rhino8_script, which uses RhinoCommon,
the stdlib and archai.metrics.compute only. If ``archai`` is not installed in
Rhino's Python, the repository root (parent of this folder) is added to sys.path.
"""

import os
import sys

try:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:  # the Script Editor may not define __file__
    _root = os.getcwd()
if os.path.isdir(os.path.join(_root, "archai")) and _root not in sys.path:
    sys.path.insert(0, _root)

from archai.metrics.rhino8_script import run

if __name__ == "__main__":
    run()
