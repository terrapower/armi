# Copyright 2019 TerraPower, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Grid editor GUI entry point.

CLI entry point to spin up the GridEditor GUI.
"""
from armi.cli import entryPoint


class GridGuiEntryPoint(entryPoint.EntryPoint):
    """Load the grid editor GUI."""

    name = "grids"

    def addOptions(self):
        self.parser.add_argument(
            "blueprints",
            nargs="?",
            type=str,
            default=None,
            help="Optional path to a blueprint file to open",
        )

    def invoke(self):
        # Import late since wxpython is kind of big and only needed when actually
        # invoking the entry point
        try:
            import wx

            from armi.utils import gridEditor
        except ImportError:
            raise RuntimeError(
                "wxPython is not installed in this "
                "environment, but is required for the Grid GUI. wxPython is not "
                "installed during the default ARMI installation process. Refer to "
                "installation instructions to install extras like wxPython."
            )

        app = wx.App()

        frame = wx.Frame(None, wx.ID_ANY, title="Grid Editor", size=(1000, 1000))

        gui = gridEditor.GridBlueprintControl(frame)
        frame.Show()
        if self.args.blueprints is not None:
            gui.loadFile(self.args.blueprints)
        app.MainLoop()
