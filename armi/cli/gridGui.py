"""
CLI entry point to spin up the GridEditor GUI.
"""
import wx

from armi.cli import entryPoint
from armi.utils import gridEditor


class GridGuiEntryPoint(entryPoint.EntryPoint):
    """
    Load the grid editor GUI
    """

    name = "grids"

    def addOptions(self):
        self.parser.add_argument("blueprints", nargs="?", type=str, default=None,
        help="Optional path to a blueprint file to open")

    def invoke(self):
        app = wx.App()

        frame = wx.Frame(
            None, wx.ID_ANY, title="Grid Editor", size=(1000, 1000)
        )

        gui = gridEditor.GridBlueprintControl(frame)
        frame.Show()
        if self.args.blueprints is not None:
            gui.loadFile(self.args.blueprints)
        app.MainLoop()
