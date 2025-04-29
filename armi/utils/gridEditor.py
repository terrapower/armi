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
GUI elements for manipulating grid layout and contents.

This provides a handful of classes which provide wxPython Controls for manipulating grids and grid
Blueprints.

The grid editor may be invoked with the :py:mod:`armi.cli.gridGui` entry point::

    $ python -m armi grids

If you have an existing set of input files, pass in the blueprints input file as the first argument
and the system will load up the associated grid, e.g.::

    $ python -m armi grids FFTF-blueprints.yaml


.. figure:: /.static/gridEditor.png
    :align: center

    An example of the Grid Editor being used on a FFTF input file

**Known Issues**

* There is no action stack or undo functionality. Save frequently if you want to recover previous
  states

* Cartesian grids are supported, but not rendered as nicely as their Hex counterparts. The "through
  center assembly" case is not rendered properly with the half-assemblies that lie along the edges.

* The controls are optimized for manipulating a Core layout, displaying an "Assembly palette" that
  contains the Assembly designs found in the top-level blueprints. A little extra work and this
  could also be made to manipulate block grids or other things.

* Assembly colors are derived from the set of flags applied to them, but the mapping of colors to
  flags is not particularly rich, and there isn't anything to disambiguate between assemblies of
  different design, but the same flags.

* No proper zoom support, and object sizes are fixed and don't accommodate long specifiers.
"""
import colorsys
import enum
import io
import os
import pathlib
import sys
from typing import Dict, Optional, Sequence, Tuple, Union

import numpy as np
import numpy.linalg
import wx
import wx.adv

from armi.reactor import geometry, grids
from armi.reactor.blueprints import Blueprints, gridBlueprint, migrate
from armi.reactor.blueprints.assemblyBlueprint import AssemblyBlueprint
from armi.reactor.blueprints.gridBlueprint import GridBlueprint, saveToStream
from armi.reactor.flags import Flags
from armi.settings.caseSettings import Settings
from armi.utils import hexagon, textProcessors

UNIT_SIZE = 50  # pixels per assembly
UNIT_MARGIN = 40  # offset applied to the draw area margins

# The color to use for each object is based on the flags that that object has. All applicable colors
# will be blended together to produce the final color for the object. There are also plans to apply
# brush styles like cross-hatching or the like, which is what the Nones are for below. Future work
# to employ these. Colors are RGB fractions.
FLAG_STYLES = {
    # Red
    Flags.FUEL: (np.array([1.0, 0.0, 0.0]), None),
    # Green
    Flags.CONTROL: (np.array([0.0, 1.0, 0.0]), None),
    # Gray
    Flags.SHIELD: (np.array([0.4, 0.4, 0.4]), None),
    # Yellow
    Flags.REFLECTOR: (np.array([0.5, 0.5, 0.0]), None),
    # Paisley?
    Flags.INNER: (np.array([0.5, 0.5, 1.0]), None),
    # We shouldn't see many SECONDARY, OUTER, MIDDLE, etc. on their own, so these
    # will just darken or brighten whatever color we would otherwise get)
    Flags.SECONDARY: (np.array([0.0, 0.0, 0.0]), None),
    Flags.OUTER: (np.array([0.0, 0.0, 0.0]), None),
    # WHITE (same as above, this will just lighten anything that it accompanies)
    Flags.MIDDLE: (np.array([1.0, 1.0, 1.0]), None),
    Flags.ANNULAR: (np.array([1.0, 1.0, 1.0]), None),
    Flags.IGNITER: (np.array([0.2, 0.2, 0.2]), None),
    Flags.STARTER: (np.array([0.4, 0.4, 0.4]), None),
    Flags.FEED: (np.array([0.6, 0.6, 0.6]), None),
    Flags.DRIVER: (np.array([0.8, 0.8, 0.8]), None),
}

# RGB weights for calculating luminance. We use this to decide whether we should put white or black
# text on top of the color. These come from CCIR 601
LUMINANCE_WEIGHTS = np.array([0.3, 0.59, 0.11])


def _translationMatrix(x, y):
    """Return an affine transformation matrix representing an x- and y-translation."""
    return np.array([[1.0, 0.0, x], [0.0, 1.0, y], [0.0, 0.0, 1.0]])


def _boundingBox(points: Sequence[np.ndarray]) -> wx.Rect:
    """Return the smallest wx.Rect that contains all of the passed points."""
    xmin = np.amin([p[0] for p in points])
    xmax = np.amax([p[0] for p in points])

    ymin = np.amin([p[1] for p in points])
    ymax = np.amax([p[1] for p in points])

    return wx.Rect(wx.Point(int(xmin), int(ymin)), wx.Point(int(xmax), int(ymax)))


def _desaturate(c: Sequence[float]):
    r, g, b = tuple(c)
    hue, lig, sat = colorsys.rgb_to_hls(r, g, b)
    lig = lig + (1.0 - lig) * 0.5
    return np.array(colorsys.hls_to_rgb(hue, lig, sat))


def _getColorAndBrushFromFlags(f, bold=True):
    """Given a set of Flags, return a wx.Pen and wx.Brush with which to draw a shape."""
    c = np.array([0.0, 0.0, 0.0])
    nColors = 0

    for styleFlag, style in FLAG_STYLES.items():
        if not styleFlag & f:
            continue

        color, brush = style
        if color is not None:
            c += color
            nColors += 1
    if nColors:
        c /= nColors

    if not bold:
        # round-trip the rgb color through hsv so that we can desaturate
        c = _desaturate(c)

    luminance = c.dot(LUMINANCE_WEIGHTS)
    dark = luminance < 0.5

    c = tuple(int(255 * ci) for ci in c)

    brush = wx.Brush(wx.Colour(*c, 255))
    pen = wx.WHITE if dark else wx.BLACK

    return pen, brush


def _drawShape(
    dc: wx.DC,
    geom: geometry.GeomType,
    view: np.ndarray,
    model: Optional[np.ndarray] = None,
    label: str = "",
    description: Optional[str] = None,
    bold: bool = True,
):
    """
    Draw a shape to the passed DC, given its GeomType and other relevant information. Return the
    bounding box.

    Parameters
    ----------
    dc: wx.DC
        The device context to draw to
    geom: geometry.GeomType
        The geometry type, which defines the shape to be drawn
    view: np.ndarray
        A 3x3 matrix defining the world transform
    model: np.ndarray, optional
        A 3x3 matrix defining the model transform. No transform is made to the "unit"
        shape if no model transform is provided.
    label: str, optional
        A string label to draw on the shape
    description: str, optional
        A string containing metadata for determining how to style to shape
    bold: bool, optional
        Whether the object should be drawn with full saturation. Default ``True``
    """
    if description is None:
        dc.SetBrush(wx.Brush(wx.Colour(200, 200, 200, 255)))
        color = wx.BLACK
    else:
        aFlags = Flags.fromStringIgnoreErrors(description)
        color, brush = _getColorAndBrushFromFlags(aFlags, bold=bold)
        dc.SetBrush(brush)

    if geom == geometry.GeomType.HEX:
        primitive = hexagon.corners(rotation=0)
    elif geom == geometry.GeomType.CARTESIAN:
        primitive = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
    else:
        raise ValueError("Geom type `{}` unsupported".format(geom))

    # Appending 1 to each coordinate since the transformation matrix is 3x3
    poly = np.array([np.append(vertex, 1) for vertex in primitive]).transpose()
    model = model if model is not None else np.eye(3)
    poly = view.dot(model).dot(poly).transpose()
    poly = [wx.Point(int(vertex[0]), int(vertex[1])) for vertex in poly]

    boundingBox = _boundingBox(poly)

    dc.SetTextForeground(color)
    dc.DrawPolygon(poly)
    dc.DrawLabel(label, boundingBox, wx.ALIGN_CENTRE)

    return boundingBox


class _GridControls(wx.Panel):
    """Collection of controls for the main Grid editor. Save/Open, num rings, etc."""

    def __init__(self, parent):
        wx.Panel.__init__(
            self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=wx.DefaultSize
        )

        self.parent = parent

        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.ringControl = wx.SpinCtrl(self, id=wx.ID_ANY, initial=5, min=1, max=20)
        self.ringControl.SetToolTip("Select how many rings of the grid to display")
        self.ringApply = wx.Button(self, id=wx.ID_ANY, label="Apply")
        self.ringApply.SetToolTip(
            "Apply the number of rings to the current grid. "
            "Assemblies outside of the displayed region will not be removed."
        )

        self.expandButton = wx.Button(self, id=wx.ID_ANY, label="Expand to full core")
        self.labelMode = wx.Choice(
            self,
            id=wx.ID_ANY,
            choices=[
                mode.label for mode in GridGui.Mode if mode is not GridGui.Mode.PATH
            ],
        )
        self.labelMode.SetSelection(int(GridGui.Mode.SPECIFIER))
        self.labelMode.SetToolTip("Select what to display in each grid region.")

        self.saveButton = wx.Button(self, id=wx.ID_ANY, label="Save grid blueprints...")
        self.saveButton.SetToolTip("Save just the grids section to its own file. ")
        self.openButton = wx.Button(self, id=wx.ID_ANY, label="Open blueprints...")
        self.openButton.SetToolTip(
            "Open a new top-level blueprints file. Top-level is "
            "needed to populate the assembly palette on the right."
        )
        self.newButton = wx.Button(self, id=wx.ID_ANY, label="New grid blueprints...")
        self.newButton.SetToolTip("Create a new Grid blueptint.")
        self.helpButton = wx.Button(self, id=wx.ID_ANY, label="Help")
        self.saveImgButton = wx.Button(self, id=wx.ID_ANY, label="Save image...")
        self.saveImgButton.SetToolTip("Save the grid layout to an image file.")

        self.Bind(wx.EVT_BUTTON, self.onChangeRings, self.ringApply)
        self.Bind(wx.EVT_BUTTON, self.onExpand, self.expandButton)
        self.Bind(wx.EVT_BUTTON, self.onSave, self.saveButton)
        self.Bind(wx.EVT_BUTTON, self.onOpen, self.openButton)
        self.Bind(wx.EVT_BUTTON, self.onNew, self.newButton)
        self.Bind(wx.EVT_BUTTON, self.onHelp, self.helpButton)
        self.Bind(wx.EVT_BUTTON, self.onSaveImage, self.saveImgButton)
        self.Bind(wx.EVT_CHOICE, self.onLabelMode, self.labelMode)

        self.help = HelpDialog(self)

        ringBox = wx.BoxSizer(wx.VERTICAL)
        ringLabel = wx.StaticText(
            self, wx.ID_ANY, "Num. Rings", style=wx.ALIGN_CENTRE_HORIZONTAL
        )
        ringBox.Add(ringLabel, 1, wx.EXPAND)
        ringBox.Add(self.ringControl, 1, wx.EXPAND)
        ringBox.Add(self.ringApply, 1, wx.EXPAND)
        sizer.Add(ringBox, 0, wx.ALL, 0)

        auxButtons = wx.BoxSizer(wx.VERTICAL)
        auxButtons.Add(self.expandButton, 1, wx.EXPAND)
        auxButtons.Add(self.labelMode, 1, wx.EXPAND)
        sizer.Add(auxButtons)

        fileBox = wx.BoxSizer(wx.VERTICAL)
        fileBox.Add(self.saveButton, 1, wx.EXPAND)
        fileBox.Add(self.openButton, 1, wx.EXPAND)
        fileBox.Add(self.newButton, 1, wx.EXPAND)

        sizer.Add(fileBox)
        sizer.Add(self.helpButton)
        sizer.Add(self.saveImgButton)

        self.SetSizerAndFit(sizer)

    def setNumRings(self, numRings):
        self.ringControl.SetValue(numRings)

    def onChangeRings(self, _event):
        self.parent.setNumRings(self.ringControl.GetValue())

    def onHelp(self, _event):
        self.help.Show()

    def onLabelMode(self, _event):
        newMode = GridGui.Mode(self.labelMode.GetSelection())
        self.parent.setMode(newMode)

    def onExpand(self, event):
        self.parent.expandToFullCore(event)

    def onSave(self, event):
        self.parent.save()

    def onSaveImage(self, event):
        self.parent.saveImage()

    def onOpen(self, event):
        self.parent.open(event)

    def onNew(self, event):
        self.parent.new(event)


class _PathControl(wx.Panel):
    """Collection of controls for manipulating fuel shuffling paths."""

    def __init__(self, parent, viewer=None):
        wx.Panel.__init__(self, parent, id=wx.ID_ANY)

        # Direct link to the main viz control. This avoids having to reach up and back down for an
        # instance, with all of the structural assumptions that that requires.
        self._viewer = viewer

        self._needsIncrement = False

        self.activateButton = wx.ToggleButton(self, label="Fuel Path")
        self.clearButton = wx.ToggleButton(self, label="Remove From Path")
        sizer = wx.BoxSizer(wx.VERTICAL)

        pathSizer = wx.BoxSizer(wx.HORIZONTAL)
        indexSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.pathSpinner = wx.SpinCtrl(self, id=wx.ID_ANY, initial=0, min=0)
        self.indexSpinner = wx.SpinCtrl(self, id=wx.ID_ANY, initial=0, min=0)
        self.autoIncrement = wx.CheckBox(self, id=wx.ID_ANY, label="Increment")

        pathSizer.Add(wx.StaticText(self, wx.ID_ANY, "Path: "))
        pathSizer.Add(self.pathSpinner, 1)

        indexSizer.Add(wx.StaticText(self, wx.ID_ANY, "Index: "))
        indexSizer.Add(self.indexSpinner, 1)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonSizer.Add(self.activateButton)
        buttonSizer.Add(self.clearButton)
        buttonSizer.AddSpacer(20)

        sizer.Add(buttonSizer, 1, wx.EXPAND)
        sizer.Add(pathSizer, 1)
        sizer.Add(indexSizer, 1)

        sizer.Add(self.autoIncrement)

        self.Bind(wx.EVT_TOGGLEBUTTON, parent.onToggle, self.activateButton)
        self.Bind(wx.EVT_TOGGLEBUTTON, parent.onToggle, self.clearButton)
        self.Bind(wx.EVT_CHECKBOX, self.onAutoIncrement, self.autoIncrement)
        self.Bind(wx.EVT_SPINCTRL, self.onPathChange, self.pathSpinner)

        self.SetSizerAndFit(sizer)

    def onPathChange(self, event):
        self.indexSpinner.SetValue(0)
        if self._viewer is not None:
            self._viewer.drawGrid()
            self._viewer.drawArrows()
            self._viewer.Refresh()

    def onAutoIncrement(self, event):
        self.indexSpinner.Enable(not self.autoIncrement.GetValue())

    def getActivateButtons(self):
        return {
            self.activateButton.GetId(): self.activateButton,
            self.clearButton.GetId(): self.clearButton,
        }

    def getIndices(self, clear=False) -> Tuple[Optional[int], Optional[int]]:
        if self.clearButton.GetValue() and clear:
            return None, None
        path, index = self.pathSpinner.GetValue(), self.indexSpinner.GetValue()
        if self._needsIncrement:
            self._needsIncrement = False
            self.indexSpinner.SetValue(index + 1)
        return path, index

    def maybeIncrement(self):
        self._needsIncrement = (
            self.autoIncrement.GetValue() and self.activateButton.GetValue()
        )


class _AssemblyPalette(wx.ScrolledWindow):
    """
    Collection of toggle controls for each defined AssemblyBlueprint, as well as some extra controls
    for configuring fuel shuffling paths.
    """

    def __init__(
        self,
        parent,
        geomType: Optional[geometry.GeomType],
        assemDesigns=None,
        viewer=None,
    ):
        wx.ScrolledWindow.__init__(
            self, parent, wx.ID_ANY, (0, 0), size=(250, 150), style=wx.SUNKEN_BORDER
        )

        self.parent = parent
        self.geomType = geomType
        self.assemDesigns = assemDesigns or dict()

        self.SetScrollRate(0, 20)

        # None -> None is useful for propagating a None to other components without
        # special branching
        self.assemDesignsById: Dict[Optional[int], Optional[AssemblyBlueprint]] = {
            None: None
        }

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(
            wx.StaticText(self, wx.ID_ANY, "Assemblies:"),
            0,
            wx.ALIGN_CENTRE | wx.ALL,
            5,
        )

        # keyed on ID
        self.assemButtons = dict()
        self.buttonIdBySpecifier = {None: None}
        self.activeAssemID: Optional[int] = None

        for key, design in self.assemDesigns.items():
            # flip y-coordinates, enlarge, offset
            flip_y = np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]])
            scale = np.array(
                [
                    [UNIT_SIZE * 0.8, 0.0, 0.0],
                    [0.0, UNIT_SIZE * 0.8, 0.0],
                    [0.0, 0.0, 1.0],
                ]
            )
            translate = np.array(
                [
                    [1.0, 0.0, UNIT_SIZE * 0.5],
                    [0.0, 1.0, UNIT_SIZE * 0.5],
                    [0.0, 0.0, 0.0],
                ]
            )
            transform = translate.dot(flip_y).dot(scale)

            bmap = wx.Bitmap(UNIT_SIZE, UNIT_SIZE)
            dc = wx.MemoryDC()
            dc.SelectObject(bmap)
            brush = wx.Brush(self.GetBackgroundColour())
            dc.SetBackground(brush)
            dc.Clear()

            _drawShape(
                dc,
                self.geomType,
                transform,
                label=design.specifier,
                description=design.flags or key,
            )

            dc.SelectObject(wx.NullBitmap)

            img = wx.StaticBitmap(self, bitmap=bmap)
            button = wx.ToggleButton(self, wx.ID_ANY, key)
            self.assemButtons[button.GetId()] = button
            self.buttonIdBySpecifier[design.specifier] = button.GetId()

            self.Bind(wx.EVT_TOGGLEBUTTON, self.onToggle, button)

            buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
            buttonSizer.Add(img)
            buttonSizer.Add(button, 1, wx.EXPAND)
            buttonSizer.AddSpacer(20)

            sizer.Add(buttonSizer, 1, wx.EXPAND)

            self.assemDesignsById[button.GetId()] = design

        sizer.Add(
            wx.StaticText(self, wx.ID_ANY, "Equilibrium Fuel Path:"), 0, wx.ALIGN_CENTRE
        )

        self.pathControl = _PathControl(self, viewer)
        sizer.Add(self.pathControl)
        self.assemButtons.update(self.pathControl.getActivateButtons())

        self.SetSizerAndFit(sizer)

    def _setActiveAssemID(self, id: Optional[int]):
        """Make sure the appropriate button is on, but none others."""
        if self.activeAssemID is not None and self.activeAssemID != id:
            # there is currently an active assem, and it isn't the requested one. Turn
            # its button off.
            self.assemButtons[self.activeAssemID].SetValue(False)

        if id is not None:
            # we are activating an assem ID. Turn its button on
            self.assemButtons[id].SetValue(True)

        self.activeAssemID = id

    def onToggle(self, event):
        """
        Respond to toggle events.

        This makes sure that the right selector button is activated, and switches the
        GUI mode into the proper one based on whether an assembly design is selected, or
        the fuel path controls.
        """
        if self.assemButtons[event.GetId()].GetValue():
            # The button that generated the event is "on" (the ToggleButton assumes its new value
            # before the event is propagated). We need to select whichever button it was.
            setTo = event.GetId()
        else:
            # The button that generated the event is off, implying that the user clicked on the
            # previously-selected button. Clear the active selection
            setTo = None

        self._setActiveAssemID(setTo)

        mode = (
            GridGui.Mode.PATH
            if event.GetId() in self.pathControl.getActivateButtons()
            and setTo is not None
            else GridGui.Mode.SPECIFIER
        )

        self.parent.setMode(mode)

    def editorClicked(self):
        self.pathControl.maybeIncrement()

    def getSelectedAssem(self) -> Optional[Union[AssemblyBlueprint, Tuple[int, int]]]:
        """Return the currently-selected assembly design or fuel path indices."""
        if self.activeAssemID in self.assemDesignsById:
            # We have an assembly design activated. return it
            return self.assemDesignsById[self.activeAssemID]
        elif self.activeAssemID in self.pathControl.getActivateButtons():
            # we are in path selection mode, return stuff from the pathControl
            return self.pathControl.getIndices(clear=False)
        else:
            return None

    def getAssemToSet(self) -> Optional[Union[AssemblyBlueprint, Tuple[int, int]]]:
        """
        Return the assembly design of fuel path tuple that a client should set.

        This differs from ``getSelectedAssem`` in that it can incorporate more logic to enforce
        certain rules, such as performing increments, masking things off based on other state etc.,
        whereas ``getSelectedAssem`` should be more dumb and just return the state of the controls
        themselves.
        """
        if self.activeAssemID in self.assemDesignsById:
            # We have an assembly design activated. return it
            return self.assemDesignsById[self.activeAssemID]
        elif self.activeAssemID in self.pathControl.getActivateButtons():
            # we are in path selection mode, return stuff from the pathControl
            return self.pathControl.getIndices(clear=True)
        else:
            return None

    def setActiveAssem(self, assemDesign: Optional[Union[AssemblyBlueprint, tuple]]):
        """Override the selected assembly design from above."""
        specifier = None
        if isinstance(assemDesign, AssemblyBlueprint):
            specifier = assemDesign.specifier
            self._setActiveAssemID(self.buttonIdBySpecifier[specifier])
        elif isinstance(assemDesign, tuple):
            self._setActiveAssemID(self.pathControl.activateButton.GetId())
        elif assemDesign is None:
            self._setActiveAssemID(None)


class GridGui(wx.ScrolledWindow):
    """
    Visual editor for grid blueprints.

    This is the actual viewer that displays the grid and grid blueprints contents, and responds to
    mouse events. Under the hood, it uses a wx.PseudoDC to handle the drawing, which provides the
    following benefits over a regular DC:

     * Drawn objects can be associated with an ID, allowing parts of the drawing to be modified or
       cleared without having to re-draw everything.
     * The IDs associated with the objects can be used to distinguish what was clicked on in a mouse
       event (though the support for this isn't super great, so we do have to do some of our own
       object disambiguation).

    The ``drawGrid()`` method is used to re-draw the entire geometry, whereas the ``applyAssem()``
    method may be used to update a single assembly.
    """

    class Mode(enum.IntEnum):
        """
        Enumeration for what type of objects are currently being manipulated.

        This can either be SPECIFIER, for laying out the initial core layout, or PATH for
        manipulating fuel shuffling paths.
        """

        # We use these values to map between selections in GUI elements, so do not go changing them
        # willy-nilly.
        SPECIFIER = 0
        POSITION_IJ = 1
        POSITION_RINGPOS = 2
        PATH = 3

        @property
        def label(self):
            if self == self.SPECIFIER:
                return "Specifier"
            elif self == self.PATH:
                return "Shuffle Path"
            elif self == self.POSITION_IJ:
                return "(i, j)"
            else:
                return "(Ring, Position)"

        @property
        def isPosition(self):
            return self in (self.POSITION_IJ, self.POSITION_RINGPOS)

    def __init__(self, parent, bp=None, defaultGeom=geometry.CARTESIAN):
        """
        Create a new GridGui.

        Parameters
        ----------
        parent : wx.Window
            The parent control

        bp : set of grid blueprints, optional
            This should be the ``gridDesigns`` section of a root Blueprints object. If
            not provided, a dictionary will be created with an empty "core" grid blueprint.
        """
        wx.ScrolledWindow.__init__(
            self, parent, wx.ID_ANY, (0, 0), size=(250, 150), style=wx.BORDER_DEFAULT
        )

        self.parent = parent

        if bp is None:
            bp = {
                "core": GridBlueprint(
                    name="core", gridContents=dict(), geom=defaultGeom
                )
            }

        self.bp = bp
        self.coreBp = bp["core"]
        self.eqFuelPathBp = bp.get("coreEqPath", None)

        self.numRings = 7

        self._grid = None
        self._geomType = None

        # What are we displaying/modifying
        self._mode = GridGui.Mode.SPECIFIER

        grid = self.coreBp.construct()
        if self.coreBp.gridContents:
            maxRings = max(
                grid.getRingPos(idx)[0] for idx in self.coreBp.gridContents.keys()
            )
            self.numRings = max(7, maxRings)

        # Need to assign this after setting numRings, since we need a grid to
        # determine numRings, but need numRings to properly set the self.grid
        # property.
        self.grid = grid

        # If we are in the middle of handling some click events, what are the indices of
        # the clicked-on region
        self.clickIndices = None

        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.Bind(wx.EVT_MOUSE_EVENTS, self.onMouse)

        self.contextMenuIDs = {
            item[0]: (wx.NewIdRef(), item[1])
            for item in [
                ("Select assembly type", self.onSelectAssembly),
                ("Make ring like this", self.onFillRing),
                ("Clear ring", self.onClearRing),
            ]
        }
        self.contextMenu = wx.Menu()
        for text, info in self.contextMenuIDs.items():
            self.contextMenu.Append(info[0], text)
            self.Bind(wx.EVT_MENU, info[1], info[0])

        self.pdc = wx.adv.PseudoDC()

        # Might be a good idea to implement this with bidict, but maybe not worth the
        # dependency
        self.pdcIdToIndices: Dict[int, Tuple[int, int, int]] = dict()
        self.indicesToPdcId: Dict[Tuple[int, int, int], int] = dict()
        # map from a PeudoDC ID (e.g. a hex) to the pixel location of the shapes
        # center. This is used to distinguish between a multi-object hit on click
        # events. While the FindObjects docs purport to distinguish objects
        # pixel-by-pixel, it seems like this is a lie, and that they simply use the
        # bounding boxes provided by the drawer. Laaaaame.
        self.pdcIdToCenter: Dict[int, wx.Point] = dict()
        # The ID to use for all arrow drawing. lets us clear and re-draw easily
        self._arrowPdcId = wx.NewIdRef()

        self.drawGrid()

    @property
    def grid(self):
        return self._grid

    @grid.setter
    def grid(self, newGrid):
        self._grid = newGrid
        self._geomType = self._grid.geomType
        self._idxByRing = [list() for _ in range(self.numRings)]
        for idx, loc in self._grid.items():
            ring, _pos = self._grid.getRingPos(idx)
            if (
                not self._grid.locatorInDomain(loc, symmetryOverlap=False)
                or ring > self.numRings
            ):
                continue
            self._idxByRing[ring - 1].append(idx)

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, newMode):
        if self.mode == newMode:
            return

        self._mode = newMode
        self.drawGrid()

        if self._mode == GridGui.Mode.PATH:
            self.drawArrows()

        self.Refresh()

    @property
    def activeBlueprints(self):
        if self.mode == GridGui.Mode.SPECIFIER:
            return self.coreBp
        elif self.mode == GridGui.Mode.PATH:
            return self.eqFuelPathBp
        elif self.mode.isPosition:
            return self.coreBp
        else:
            raise ValueError("Unsupported mode `{}`".format(self.mode))

    def growToFullCore(self):
        if geometry.FULL_CORE not in self.coreBp.symmetry:
            self.coreBp.expandToFull()
            if self.eqFuelPathBp is not None:
                self.eqFuelPathBp.expandToFull()
            self.grid = self.coreBp.construct()
            self.drawGrid()
            self.Refresh()

    def _getWindowCoordinates(self, event):
        xv, yv = self.GetViewStart()
        dx, dy = self.GetScrollPixelsPerUnit()
        xOffset = dx * xv
        yOffset = dy * yv
        x = event.GetX()
        y = event.GetY()
        xScrolled = x + xOffset
        yScrolled = y + yOffset

        return xScrolled, yScrolled

    def _getIndicesFromEvent(self, event) -> Optional[Tuple[int, int, int]]:
        obj = self._getObjectFromEvent(event)

        if obj is None:
            return None

        return self.pdcIdToIndices[obj]

    def _getObjectFromEvent(self, event) -> Optional[int]:
        def _distanceish(p1, p2):
            return (p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2

        x, y = self._getWindowCoordinates(event)
        objs = self.pdc.FindObjects(x, y, radius=1)

        if not objs:
            return None

        if len(objs) == 1:
            return objs[0]

        # list of tuples with (distance, ID)
        sortableObjectIds = [
            (_distanceish(wx.RealPoint(x, y), self.pdcIdToCenter[obj]), obj)
            for obj in objs
        ]

        return min(sortableObjectIds)[1]

    def drawGrid(self):
        """Wipe out anything in the drawing and re-draw everything."""
        self.pdc.Clear()
        self.pdc.RemoveAll()

        self.pdcIdToIndices = dict()
        self.indicesToPdcId = dict()
        self.pdcIdToCenter = dict()
        self.pdc.SetPen(wx.Pen("BLACK", 1))

        gridScale = self._gridScale(self.grid)

        # flip y-coordinates, enlarge
        flip_y = np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]])
        scale = np.array(
            [
                [UNIT_SIZE / gridScale[0], 0.0, 0.0],
                [0.0, UNIT_SIZE / gridScale[1], 0.0],
                [0.0, 0.0, 1.0],
            ]
        )

        # uniform grid, so all shapes have the same scale
        model = np.array(
            [[gridScale[0], 0.0, 0.0], [0.0, gridScale[1], 0.0], [0.0, 0.0, 1.0]]
        )
        self.transform = flip_y.dot(scale)
        rect = self._calcGridBounds()
        self.SetVirtualSize((rect.Width, rect.Height))
        self.SetScrollRate(20, 20)
        # Global translation used to center the view
        translate = _translationMatrix(-1 * rect.Left, -1 * rect.Top)
        self.transform = translate.dot(self.transform)

        brush = wx.Brush(wx.Colour(128, 128, 128, 0))
        self.pdc.SetBrush(brush)

        for idx, loc in self.grid.items():
            ring, _ = self.grid.getRingPos(idx)
            if not self.grid.locatorInDomain(loc) or ring > self.numRings:
                continue

            id = wx.NewIdRef()
            self.pdcIdToIndices[id] = idx
            self.indicesToPdcId[idx] = id
            self.pdc.SetId(id)

            label, description, bold = self._getLabel(idx)

            coords = np.array(self.grid.getCoordinates(idx))[:2]
            offset = _translationMatrix(*coords)

            boundingBox = _drawShape(
                self.pdc,
                self._geomType,
                self.transform,
                model=offset.dot(model),
                label=label,
                description=description,
                bold=bold,
            )
            center = (boundingBox.TopLeft + boundingBox.BottomRight) / 2
            self.pdcIdToCenter[id] = center
            self.pdc.SetIdBounds(id, boundingBox)

    def drawArrows(self):
        """Draw fuel path arrows."""
        if self.mode != GridGui.Mode.PATH:
            return

        self.pdc.ClearId(self._arrowPdcId)
        self.pdc.SetId(self._arrowPdcId)

        goodPen = wx.Pen(wx.Colour(0, 0, 0), width=1, style=wx.PENSTYLE_DOT)
        badPen = wx.Pen(wx.Colour(255, 0, 0))

        thisPath = self.parent.getSelectedPath()

        stuffInPath = sorted(
            [
                (index, idx)
                for idx, (path, index) in self.eqFuelPathBp.gridContents.items()
                if path == thisPath
            ]
        )
        touchedIndices = {entry[0] for entry in stuffInPath}
        indexGraph = {index: list() for index in touchedIndices}
        for index, location in stuffInPath:
            indexGraph[index].append(location)

        # python 3.6+ should maintain key order from the sorted stuffInPath
        keys = list(indexGraph.keys())
        for i1, i2 in zip(keys[:-1], keys[1:]):
            pen = goodPen
            if i2 - i1 != 1:
                pen = badPen
            if len(indexGraph[i1]) > 1 or len(indexGraph[i2]) > 1:
                pen = badPen

            self.pdc.SetPen(pen)

            for fromIdx in indexGraph[i1]:
                for toIdx in indexGraph[i2]:
                    p1 = self.grid.getCoordinates(fromIdx + (0,))
                    p2 = self.grid.getCoordinates(toIdx + (0,))

                    p1[2] = 1.0
                    p2[2] = 1.0

                    p1 = self.transform.dot(p1)[0:2]
                    p2 = self.transform.dot(p2)[0:2]
                    p1 = [int(v) for v in p1]
                    p2 = [int(v) for v in p2]
                    self.pdc.DrawLines([wx.Point(*p1), wx.Point(*p2)])

    def _getLabel(self, idx) -> Tuple[str, Optional[str], bool]:
        """
        Given (i, j, k) indices, return information about the object at that location.

        This will return a tuple containing:
         - The label to actually display in the GUI
         - Optionally, a description that can be turned into Flags and used to determine
           what the object should look like
         - Whether the object should be drawn in its full/bold representation
        """
        ring, pos = self.grid.getRingPos(idx)
        specifier = self.coreBp.gridContents.get(tuple(idx[0:2]), None)
        aDesign = None
        description = None
        bold = True
        if specifier is not None:
            aDesign = self.parent.getAssemDesignBySpecifier(specifier)
            description = aDesign.flags or aDesign.name

        if self.mode == GridGui.Mode.SPECIFIER:
            if aDesign is not None:
                label = specifier
            else:
                label = "{}, {}".format(ring, pos)
        elif self.mode == GridGui.Mode.PATH:
            selectedPath = self.parent.getSelectedPath()
            if self.eqFuelPathBp is None:
                # We need to add a grid blueprint for the equilibrium fuel path
                self.bp["coreEqPath"] = GridBlueprint("coreEqPath", self.coreBp.geom)
                self.eqFuelPathBp = self.bp["coreEqPath"]
            if self.eqFuelPathBp.gridContents is None:
                _grid = self.eqFuelPathBp.construct()

            path, index = self.eqFuelPathBp.gridContents.get(idx[0:2], (None, None))
            if path != selectedPath:
                bold = False
            if path is not None and index is not None:
                label = "({}, {})".format(path, index)
            else:
                label = "-"
        elif self.mode == GridGui.Mode.POSITION_RINGPOS:
            label = "{}, {}".format(ring, pos)
        elif self.mode == GridGui.Mode.POSITION_IJ:
            label = "{}, {}".format(*idx[0:2])

        else:
            raise ValueError("Unsupported mode `{}`".format(self.mode))

        return label, description, bold

    def setNumRings(self, n: int):
        """Change the number of rings that should be drawn."""
        self.numRings = n
        if self.grid.geomType == geometry.GeomType.HEX:
            grid = grids.HexGrid.fromPitch(1, numRings=self.numRings)
        elif self.grid.geomType == geometry.GeomType.CARTESIAN:
            rectangle = [1.0, 1.0]
            if self.coreBp.latticeDimensions is not None:
                rectangle = [
                    self.coreBp.latticeDimensions.x,
                    self.coreBp.latticeDimensions.y,
                ]
            grid = grids.CartesianGrid.fromRectangle(*rectangle, numRings=self.numRings)
        else:
            raise ValueError(
                "Only support Hex and Cartesian grids, not {}".format(
                    self.grid.geomType
                )
            )

        grid.symmetry = self.grid.symmetry
        grid.geomType = self.grid.geomType
        self.grid = grid

        self.drawGrid()
        self.Refresh()

    def onPaint(self, event, dc=None):
        selfPaint = dc is None
        dc = dc or wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(wx.Colour(255, 255, 255, 255)))
        dc.Clear()

        self.DoPrepareDC(dc)

        if selfPaint:
            xv, yv = self.GetViewStart()
            dx, dy = self.GetScrollPixelsPerUnit()
            region = self.GetUpdateRegion()
            region.Offset(dx * xv, dy * yv)

            _ = region.GetBox()

        self.pdc.DrawToDC(dc)

    def onMouse(self, event):
        if event.RightUp():
            self.onContextMenu(event)
            return event.Skip()

        if event.LeftDown():
            _ = event.GetX()
            _ = event.GetY()

            objId = self._getObjectFromEvent(event)

            if objId is None:
                return event.Skip()

            idx = tuple(self.pdcIdToIndices[objId])[0:2]
            self.parent.objectClicked(idx)
            assem = self.parent.getAssemToSet()
            self.applyAssem(objId, assem)

        if event.LeftUp():
            pass

        return event.Skip()

    def onContextMenu(self, event):
        self.clickIndices = self._getIndicesFromEvent(event)
        self.PopupMenu(self.contextMenu)
        self.clickIndices = None

    def onSelectAssembly(self, event):
        specifier = self.coreBp.gridContents.get(self.clickIndices[0:2], None)
        aDesign = (
            self.parent.getAssemDesignBySpecifier(specifier)
            if specifier is not None
            else None
        )
        self.parent.setActiveAssem(aDesign)

    def onFillRing(self, event):
        ring, _ = self.grid.getRingPos(self.clickIndices)
        specifier = self.coreBp.gridContents.get(self.clickIndices[0:2], None)
        aDesign = (
            self.parent.getAssemDesignBySpecifier(specifier)
            if specifier is not None
            else None
        )
        for idx in self._idxByRing[ring - 1]:
            self.applyAssem(self.indicesToPdcId[idx], aDesign)

    def onClearRing(self, event):
        ring, _ = self.grid.getRingPos(self.clickIndices)
        for idx in self._idxByRing[ring - 1]:
            self.applyAssem(self.indicesToPdcId[idx], None)

    def applyAssem(
        self, pdcId, value: Optional[Union[AssemblyBlueprint, Tuple[int, int]]]
    ):
        """
        Apply the passed assembly design or equilibrium path indices for the desired
        object and redraw it.
        """
        if self.activeBlueprints is None:
            return

        # uniform grid, so all shapes have the same scale
        gridScale = self._gridScale(self.grid)
        model = np.array(
            [[gridScale[0], 0.0, 0.0], [0.0, gridScale[1], 0.0], [0.0, 0.0, 1.0]]
        )

        idx = tuple(self.pdcIdToIndices[pdcId])
        idx2 = idx[0:2]
        if value is not None:
            if isinstance(value, AssemblyBlueprint):
                assert self.mode in {
                    GridGui.Mode.SPECIFIER,
                    GridGui.Mode.POSITION_IJ,
                    GridGui.Mode.POSITION_RINGPOS,
                }
                self.activeBlueprints.gridContents[idx2] = value.specifier
            elif isinstance(value, tuple):
                assert self.mode == GridGui.Mode.PATH
                self.activeBlueprints.gridContents[idx2] = value
        else:
            # Clear whatever we clicked on
            if idx2 in self.activeBlueprints.gridContents:
                del self.activeBlueprints.gridContents[idx2]

        self.pdc.ClearId(pdcId)
        self.pdc.SetId(pdcId)

        coords = np.array(self.grid.getCoordinates(idx))
        model = _translationMatrix(*coords[0:2]).dot(model)

        label, description, bold = self._getLabel(idx)

        boundingBox = _drawShape(
            self.pdc,
            self._geomType,
            self.transform,
            model=model,
            label=label,
            description=description,
            bold=bold,
        )
        self.pdc.SetIdBounds(pdcId, boundingBox)

        self.drawArrows()
        self.Refresh()

    @staticmethod
    def _gridScale(grid):
        if isinstance(grid, grids.HexGrid):
            # Unit steps aren't aligned with the x,y coordinate system for Hex, so just
            # use the y dimension, assuming that's the proper flat-to-flat dimension
            coordScale = np.array([grid._unitSteps[1][1]] * 2)
        elif isinstance(grid, grids.CartesianGrid):
            # Cartesian grids align with the GUI coordinates, so just use unit steps
            # directly
            coordScale = np.array([grid._unitSteps[0][0], grid._unitSteps[1][1]])
        return coordScale

    def _calcGridBounds(self) -> wx.Rect:
        """
        Return the width and height (in pixels) that are needed to display the passed grid.

        This allows us to dynamically size the scrolled area, and to offset the geometry
        properly into the center of the screen.
        """
        inDomain = {
            idx: loc
            for idx, loc in self.grid.items()
            if self.grid.locatorInDomain(loc)
            and self.grid.getRingPos(loc)[0] <= self.numRings
        }

        _ = self._gridScale(self.grid)

        allCenters = np.array([self.grid.getCoordinates(idx)[:2] for idx in inDomain])
        minXY = np.amin(allCenters, axis=0)
        maxXY = np.amax(allCenters, axis=0)

        topRight = np.append([maxXY[1], maxXY[1]], 1.0)
        bottomLeft = np.append([minXY[0], minXY[1]], 1.0)
        nudge = np.array([UNIT_MARGIN, -UNIT_MARGIN, 0.0])

        bottomRight = (self.transform.dot(topRight) + nudge).tolist()
        topLeft = (self.transform.dot(bottomLeft) - nudge).tolist()

        bottomRight = [int(v) for v in bottomRight]
        topLeft = [int(v) for v in topLeft]

        return wx.Rect(wx.Point(*topLeft[:2]), wx.Point(*bottomRight[:2]))


class GridBlueprintControl(wx.Panel):
    """
    A GUI for manipulating core layouts.

    The original intent of this is to serve as a stand-in replacement for the current
    "HexDragger". With further work, this could be made to function as a more general
    tool for manipulating grids of any sort.
    """

    _wildcard = "YAML blueprints (*.yaml)|*.yaml|All files (*.*)|*.*"

    _defaultGeom = geometry.CARTESIAN

    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY, size=(200, 30))

        bp = Blueprints()
        bp.gridDesigns = gridBlueprint.Grids()

        # cs only needed for migrations. Realistically, this would be set from a
        # higher-level GUI container. If it is not set and migrations are needed
        # anyways, the user will be prompted.
        self._cs = None
        self._fName = None

        self._bp = bp

        self.clicker = GridGui(self, defaultGeom=self._defaultGeom)
        self.assemblyPalette = _AssemblyPalette(self, None, dict(), self.clicker)

        self.controls = _GridControls(self)
        self.controls.setNumRings(self.clicker.numRings)

        sizer = wx.BoxSizer(wx.VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(self.clicker, 1, wx.EXPAND)
        hsizer.Add(self.assemblyPalette, 0)

        sizer.Add(hsizer, 1, wx.EXPAND)
        sizer.Add(self.controls, 0)

        self.sizer = sizer
        self.SetSizerAndFit(self.sizer)

    @property
    def bp(self):
        return self._bp

    @bp.setter
    def bp(self, bp):
        self._bp = bp

        geomType = geometry.GeomType.fromStr(bp.gridDesigns["core"].geom)

        # Make new assembly palette and editor
        newClicker = GridGui(self, bp=self.bp.gridDesigns)
        newPalette = _AssemblyPalette(self, geomType, bp.assemDesigns, newClicker)

        self.sizer.Replace(self.assemblyPalette, newPalette, recursive=True)
        self.sizer.Replace(self.clicker, newClicker, recursive=True)

        self.assemblyPalette.Destroy()
        self.clicker.Destroy()

        self.assemblyPalette = newPalette
        self.clicker = newClicker

        self.controls.setNumRings(self.clicker.numRings)

        self.sizer.Layout()
        self.SendSizeEventToParent()

    @property
    def grid(self):
        return self.clicker.grid

    def setNumRings(self, n: int):
        self.clicker.setNumRings(n)

    def setActiveAssem(self, aDesign):
        self.assemblyPalette.setActiveAssem(aDesign)
        self.clicker.mode = (
            GridGui.Mode.SPECIFIER
            if isinstance(aDesign, (AssemblyBlueprint, type(None)))
            else GridGui.Mode.PATH
        )

    def setMode(self, mode: GridGui.Mode):
        self.clicker.mode = mode

        # make sure that gui elements that have to do with mode setting are consistent
        if mode == GridGui.Mode.isPosition:
            self.assemblyPalette.setActiveAssem(None)
        self.controls.labelMode.SetSelection(mode)

    def expandToFullCore(self, event):
        self.clicker.growToFullCore()

    def objectClicked(self, _idx):
        """
        Notify relevant controls that the object at the passed indices has been
        activated.

        This is needed to make the auto-increment stuff work in the fuel path editor.
        Without some sort of event that provides a positive assertion that the user is
        trying to interact with the layout, we can't know when to increment.
        """
        self.assemblyPalette.editorClicked()

    def saveImage(self):
        """
        Save the core layout to an image.

        Currently this only supports PNG images for simplicity. wxpython does not
        attempt to infer the file type based on extension, so we would need to make a
        file extension-to-format mapping.
        """
        dlg = wx.FileDialog(
            self,
            message="Save image to...",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            wildcard="PNG images (.png)|*.png",
        )

        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
        else:
            return

        size = self.clicker.GetVirtualSize()
        image = wx.Bitmap(size)

        dc = wx.MemoryDC()
        dc.SelectObject(image)

        self.clicker.onPaint(None, dc=dc)
        dc.SelectObject(wx.NullBitmap)
        image.SaveFile(path, wx.BITMAP_TYPE_PNG)

    def save(self, stream=None, full=False):
        """
        Save the blueprints to the passed stream, if provided. Otherwise prompt for a
        file to save to.

        This can save either the entire blueprints, or just the `grids:` section of the
        blueprints, based on the passed ``full`` argument. Saving just the grid
        blueprints can be useful when cobbling blueprints together with !include flags.
        """
        if stream is None:
            self._saveNoStream(full)
        else:
            saveToStream(stream, self.bp, full, tryMap=True)

    def _saveNoStream(self, full=False):
        """Prompt for a file to save to.

        This can save either the entire blueprints, or just the `grids:` section of the
        blueprints, based on the passed ``full`` argument. Saving just the grid
        blueprints can be useful when cobbling blueprints together with !include flags.
        """
        # Prompt the user for a file name, open it, and call ourself again with that
        # as the stream argument
        if self._fName is None:
            wd = os.getcwd()
        else:
            wd = os.path.split(self._fName)[0]

        # Don't use the blueprints filename as the default if we are only saving the
        # grids section; doing so may encourage users to overwrite their main
        # blueprints file.
        if full:
            fName = self._fName or ""
        else:
            fName = ""

        title = "Save blueprints to..." if full else "Save grid designs to..."

        dlg = wx.FileDialog(
            self,
            message=title,
            defaultDir=wd,
            defaultFile=fName,
            wildcard=self._wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )

        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
        else:
            return

        # Disallow overwriting the main blueprints with the grids section
        if (
            not full
            and pathlib.Path(path).exists()
            and pathlib.Path(path).samefile(self._fName)
        ):
            message = (
                "The chosen path, `{}` is the same as the main blueprints "
                'file. This tool only saves the "grids" section of the '
                "blueprints file, so saving over the original top-level blueprints "
                "will lead to data loss. Try again with a different name.".format(path)
            )

            with wx.MessageDialog(
                self,
                message,
                "Overwriting top-level blueprints!",
                style=wx.ICON_WARNING,
            ) as dlg:
                dlg.ShowModal()
                return

        # Try writing to an internal buffer before opening the file for write. This
        # way to don't destroy anything unless we know we have something with which
        # to replace it.
        bpStream = io.StringIO()
        saveToStream(bpStream, self.bp, full, tryMap=True)
        with open(path, "w") as stream:
            stream.write(bpStream.getvalue())

    def open(self, _event):
        if self._fName is None:
            wd = os.getcwd()
        else:
            wd = os.path.split(self._fName)[0]

        dlg = wx.FileDialog(
            self,
            message="Open blueprints file...",
            defaultDir=wd,
            defaultFile="",
            wildcard=self._wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )

        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()

            self.loadFile(path)

    def new(self, _event):
        """
        Create a Dialog with options to make a new grid blueprint, then make it and
        rejigger everything to use it.
        """
        with NewGridBlueprintDialog(self) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                # Make new bp
                gridBp = dlg.getGridBlueprint()
                if self.bp is not None:
                    self.bp.gridDesigns[gridBp.name] = gridBp
                self.bp = self.bp

    def loadFile(self, fName, cs=None):
        """Load a new blueprints file, refreshing pretty much everything."""
        self._fName = fName
        self._cs = cs
        with open(fName, "r") as bpYaml:
            bpYaml = textProcessors.resolveMarkupInclusions(
                bpYaml, root=pathlib.Path(fName).parent
            )
            bp = Blueprints.load(bpYaml)
            if bp.gridDesigns is None or "core" not in bp.gridDesigns:
                cs = self._cs or self._promptForCs()
                if cs is None:
                    # We didn't get a CS from the user, so cannot migrate old
                    # blueprints. Give up.
                    return

                migrate(bp, cs)

        self.bp = bp

    def getAssemDesignBySpecifier(self, specifier):
        for _key, design in self.bp.assemDesigns.items():
            if design.specifier == specifier:
                return design

        raise KeyError(
            "Could not find an Assembly design with specifier `{}`".format(specifier)
        )

    def getAssemToSet(self):
        return self.assemblyPalette.getAssemToSet()

    def getSelectedPath(self):
        """
        Return the fuel path index that is currently selected.

        This is used to route the state of the _AssemblyPalette controls to things that
        need to know about such things (arrow drawing, whether objects should be bold,
        etc.)
        """
        assem = self.assemblyPalette.getSelectedAssem()
        assert isinstance(assem, tuple)
        return assem[0]

    def _promptForCs(self) -> Optional[Settings]:
        """
        Ask the user for a case settings file to locate the appropriate geom file to
        perform blueprint migrations.
        """
        if self._fName is None:
            wd = os.getcwd()
        else:
            wd = os.path.split(self._fName)[0]

        dlg = wx.FileDialog(
            self,
            message="Migrations needed. Please provide a settings file...",
            defaultDir=wd,
            defaultFile="",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )

        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            return Settings(path)
        return None


class HelpDialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, id=wx.ID_ANY, title="About the grid editor...")

        helpTxt = """
The Grid Editor is a rudimentary tool for manipulating the contents and basic structure
of Grid Blueprints. Rather than being a full-featured reactor editor GUI, it intends to
help in the specific task of laying objects out in a grid, which can be frustrating or
tedious to do by hand in a text editor.

Since this is not a general-purpose blueprint editor, this will only save the "grids"
section of a blueprints file, which will then need to be incorporated into a top-level
blueprints input, typically by !include-ing from the host blueprints.

When opening a blueprints file, the root blueprints should be provided, since the Editor
uses the assembly designs to populate the assembly palette on the right.

Controls
--------
Left-click in map: Apply the selected assembly design to the clicked location. If no
assembly is selected, clear the assembly design in the licked location.

Right-click in map: Summon context menu with useful tools.

"Num. Rings" spinner: Modify the number of rings that the displayed grid should span.
Reducing the number of rings below the region with defined assemblies *will not* clear
those regions.

"Expand to full core": Expand a 1/N-th reactor map into full symmetry. This will honor
the periodic/reflective boundary conditions as specified.

Label display drop-down: Select what should be displayed at each grid location.

Save grid blueprints: Save just the grid blueprints to a file. This will need to be
incorporated into a top-level blueprints file. To prevent loss of data, it will try to
prevent overwriting the original blueprints file that was opened.

Open blueprints: Open a new top-level blueprints file.

New grid blueprints: Create a new grid blueprint, allowing configuration of the geometry
type, domain, and boundary conditions.

"""

        self.Sizer = wx.BoxSizer(wx.VERTICAL)
        txt = wx.StaticText(self, label=helpTxt)
        ok = wx.Button(self, id=wx.ID_OK)

        self.Sizer.Add(txt)
        self.Sizer.Add(ok)

        self.Fit()


class NewGridBlueprintDialog(wx.Dialog):
    """Dialog box for configuring a new grid blueprint."""

    # these provide stable mappings from the wx.Choice control indices to the respective geom types
    _geomFromIdx = {
        i: geomType
        for i, geomType in enumerate(
            {geometry.GeomType.CARTESIAN, geometry.GeomType.HEX}
        )
    }
    _idxFromGeom = {geomType: i for i, geomType in _geomFromIdx.items()}

    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, id=wx.ID_ANY, title="New Grid Blueprint...")

        nameLabel = wx.StaticText(self, label="Grid name:")
        self.gridName = wx.TextCtrl(self, value="core")
        nameSizer = wx.BoxSizer(wx.HORIZONTAL)
        nameSizer.Add(nameLabel, 0)
        nameSizer.Add(self.gridName, 1, wx.EXPAND)

        self.geomType = wx.Choice(
            self,
            id=wx.ID_ANY,
            choices=[gt.label for gt in self._geomFromIdx.values()],
        )

        self.Bind(wx.EVT_CHOICE, self.onSelectGeomType, self.geomType)

        # Domain controls
        self.throughCenter = wx.CheckBox(
            self, id=wx.ID_ANY, label="Through Center Assembly"
        )
        self.domainFull = wx.RadioButton(
            self, id=wx.ID_ANY, label="Full Core", style=wx.RB_GROUP
        )
        self.domain3 = wx.RadioButton(self, id=wx.ID_ANY, label="1/3 Core")
        self.domain4 = wx.RadioButton(self, id=wx.ID_ANY, label="1/4 Core")

        domainBox = wx.StaticBoxSizer(wx.VERTICAL, self, label="Domain")
        domainBox.Add(self.domainFull, 0)
        domainBox.Add(self.domain3, 0)
        domainBox.Add(self.domain4, 0)
        domainBox.Add(self.throughCenter, 0)

        self.Bind(wx.EVT_RADIOBUTTON, self.onDomainChange)

        # Symmetry controls
        self.symmetryFull = wx.RadioButton(
            self, id=wx.ID_ANY, style=wx.RB_GROUP, label="Full"
        )
        self.periodic = wx.RadioButton(self, id=wx.ID_ANY, label="Periodic")
        self.reflective = wx.RadioButton(self, id=wx.ID_ANY, label="Reflective")

        symmetryBox = wx.StaticBoxSizer(wx.VERTICAL, self, label="Symmetry")
        symmetryBox.Add(self.symmetryFull, 0)
        symmetryBox.Add(self.periodic, 0)
        symmetryBox.Add(self.reflective, 0)

        # arrange the two boxes horizontally
        gridControls = wx.BoxSizer(wx.HORIZONTAL)
        gridControls.Add(domainBox, 0)
        gridControls.Add(symmetryBox, 0)

        ok = wx.Button(self, wx.ID_OK)
        cancel = wx.Button(self, wx.ID_CANCEL)

        self.Sizer = wx.BoxSizer(wx.VERTICAL)
        self.Sizer.Add(nameSizer, 1, wx.ALL, 0)
        self.Sizer.Add(self.geomType, 0, wx.ALL, 0)
        self.Sizer.Add(gridControls, 0, wx.ALL, 0)
        self.Sizer.Add(wx.StaticLine(self), 0, wx.EXPAND)

        okCancelSizer = wx.BoxSizer(wx.HORIZONTAL)
        okCancelSizer.Add(ok)
        okCancelSizer.Add(cancel)

        self.Sizer.Add(okCancelSizer, 0, wx.EXPAND | wx.ALL, 10)

        self.selectGeomType(geometry.GeomType.HEX)
        self.Fit()

    def selectGeomType(self, geom):
        """Enable/disable relevant controls for the selected geom type."""
        # make sure the geom type Choice is in sync. This function doesn't have to be
        # called from the event handler.
        self.geomType.SetSelection(self._idxFromGeom[geom])
        # switch to full-core, since it's always available
        self.domainFull.SetValue(True)
        self.symmetryFull.SetValue(True)
        self._toggleControls()

    def onSelectGeomType(self, _event):
        self.selectGeomType(self._geomFromIdx[self.geomType.GetSelection()])

    def _toggleControls(self):
        """Make sure that the appropriate controls are enabled/disabled."""
        geom = self._geomFromIdx[self.geomType.GetSelection()]
        full = self.domainFull.GetValue()
        self.throughCenter.Enable(enable=geom == geometry.GeomType.CARTESIAN)
        self.symmetryFull.Enable(enable=full)
        self.domain3.Enable(enable=geom == geometry.GeomType.HEX)
        self.domain4.Enable(enable=geom == geometry.GeomType.CARTESIAN)
        self.periodic.Enable(enable=not full)
        self.reflective.Enable(enable=not full and geom == geometry.GeomType.CARTESIAN)
        if full:
            self.symmetryFull.SetValue(True)

    def onDomainChange(self, event):
        if event.EventObject in {self.domainFull, self.domain3, self.domain4}:
            if self.domainFull.GetValue():
                self.symmetryFull.SetValue(True)
            else:
                self.periodic.SetValue(True)
        self._toggleControls()

    def getGridBlueprint(self):
        """Using the state of the dialog controls, return a corresponding GridBlueprint."""
        name = self.gridName.GetValue()
        geom = self._geomFromIdx[self.geomType.GetSelection()]

        if self.domainFull.GetValue():
            domain = geometry.DomainType.FULL_CORE
        elif self.domain3.GetValue():
            domain = geometry.DomainType.THIRD_CORE
        elif self.domain4.GetValue():
            domain = geometry.DomainType.QUARTER_CORE
        else:
            raise ValueError("Couldn't map selection to supported fractional domain")

        if self.periodic.GetValue():
            bc = geometry.BoundaryType.PERIODIC
        elif self.reflective.GetValue():
            bc = geometry.BoundaryType.REFLECTIVE
        else:
            bc = geometry.BoundaryType.NO_SYMMETRY

        symmetry = geometry.SymmetryType(domain, bc, self.throughCenter.GetValue())

        assert symmetry.checkValidSymmetry()

        bp = GridBlueprint(name=name, geom=str(geom), symmetry=str(symmetry))

        return bp


if __name__ == "__main__":
    app = wx.App()
    frame = wx.Frame(None, wx.ID_ANY, title="Grid Blueprints GUI", size=(1000, 1000))

    gui = GridBlueprintControl(frame)
    frame.Show()
    if len(sys.argv) > 1:
        gui.loadFile(sys.argv[1])
    app.MainLoop()
