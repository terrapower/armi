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
This module makes heavy use of matplotlib. Beware that plots generated with matplotlib
may not free their memory, even after the plot is closed, and excessive use of
plotting functions may gobble up all of your machine's memory.

Therefore, you should use these plotting tools judiciously. It is not advisable to,
for instance, plot some sequence of objects in a loop at every time node. If you start
to see your memory usage grow inexplicably, you should question any plots that you are
generating.
"""

import collections
import itertools
import math
import os
import re

from matplotlib.collections import PatchCollection
from matplotlib.widgets import Slider
from mpl_toolkits import axes_grid1
from ordered_set import OrderedSet
import matplotlib.colors as mcolors
import matplotlib.patches
import matplotlib.pyplot as plt
import matplotlib.text as mpl_text
import numpy

from armi import runLog
from armi.bookkeeping import report
from armi.materials import custom
from armi.nuclearDataIO.cccc.rtflux import RtfluxData
from armi.reactor import grids
from armi.reactor.components import Helix, Circle, DerivedShape
from armi.reactor.components.basicShapes import Hexagon, Rectangle, Square
from armi.reactor.flags import Flags
from armi.utils import hexagon


LUMINANCE_WEIGHTS = numpy.array([0.3, 0.59, 0.11, 0.0])


def colorGenerator(skippedColors=10):
    """
    Selects a color from the matplotlib css color database.

    Parameters
    ----------
    skippedColors: int
        Number of colors to skip in the matplotlib CSS color database when generating the
        next color. Without skipping colors the next color may be similar to the previous
        color.

    Notes
    -----
    Will cycle indefinitely to accommodate large cores. Colors will repeat.
    """
    colors = list(mcolors.CSS4_COLORS)

    for start in itertools.cycle(range(20, 20 + skippedColors)):
        for i in range(start, len(colors), skippedColors):
            yield colors[i]


def plotBlockDepthMap(
    core,
    param="pdens",
    fName=None,
    bare=False,
    cmapName="jet",
    labels=(),
    labelFmt="{0:.3f}",
    legendMap=None,
    fontSize=None,
    minScale=None,
    maxScale=None,
    axisEqual=False,
    makeColorBar=False,
    cBarLabel="",
    title="",
    shuffleArrows=False,
    titleSize=25,
    depthIndex=0,
):
    """
    Plot a param distribution in xy space with the ability to page through depth.

    Notes
    -----
    This is useful for visualizing the spatial distribution of a param through the core.
    Blocks could possibly not be in alignment between assemblies, but the depths
    viewable are based on the first fuel assembly.

    Parameters
    ----------
    The kwarg definitions are the same as those of ``plotFaceMap``.

    depthIndex: int
        The the index of the elevation to show block params.
        The index is determined by the index of the blocks in the first fuel assembly.
    """
    fuelAssem = core.getFirstAssembly(typeSpec=Flags.FUEL)
    if not fuelAssem:
        raise ValueError(
            "Could not find fuel assembly. "
            "This method uses the first fuel blocks mesh for the axial mesh of the plot. "
            "Cannot proceed without fuel block."
        )

    # block mid point elevation
    elevations = [elev for _b, elev in fuelAssem.getBlocksAndZ()]
    data = []
    for elevation in elevations:
        paramValsAtElevation = []
        for a in core:
            paramValsAtElevation.append(a.getBlockAtElevation(elevation).p[param])
        data.append(paramValsAtElevation)

    data = numpy.array(data)

    fig = plt.figure(figsize=(12, 12), dpi=100)
    # Make these now, so they are still referenceable after plotFaceMap.
    patches = _makeAssemPatches(core)
    collection = PatchCollection(patches, cmap=cmapName, alpha=1.0)
    texts = []

    plotFaceMap(
        core,
        param=param,
        vals="peak",
        data=None,  # max values so legend is set correctly
        bare=bare,
        cmapName=cmapName,
        labels=labels,
        labelFmt=labelFmt,
        legendMap=legendMap,
        fontSize=fontSize,
        minScale=minScale,
        maxScale=maxScale,
        axisEqual=axisEqual,
        makeColorBar=makeColorBar,
        cBarLabel=cBarLabel,
        title=title,
        shuffleArrows=shuffleArrows,
        titleSize=titleSize,
        referencesToKeep=[patches, collection, texts],
    )

    # make space for the slider
    fig.subplots_adjust(bottom=0.15)

    ax_slider = fig.add_axes([0.1, 0.05, 0.8, 0.04])

    # This controls what the slider does.
    def update(i):
        # int, since we are indexing an array.
        i = int(i)
        collection.set_array(data[i, :])
        for valToPrint, text in zip(data[i, :], texts):
            text.set_text(labelFmt.format(valToPrint))

    # Slider doesn't seem to work unless assigned to variable
    _slider = DepthSlider(
        ax_slider, "Depth(cm)", elevations, update, "green", valInit=depthIndex
    )

    if fName:
        plt.savefig(fName, dpi=150)
    else:
        plt.show()

    plt.close()
    return fName


def plotFaceMap(
    core,
    param="pdens",
    vals="peak",
    data=None,
    fName=None,
    bare=False,
    cmapName="jet",
    labels=(),
    labelFmt="{0:.3f}",
    legendMap=None,
    fontSize=None,
    minScale=None,
    maxScale=None,
    axisEqual=False,
    makeColorBar=False,
    cBarLabel="",
    title="",
    shuffleArrows=False,
    titleSize=25,
    referencesToKeep=None,
):
    """
    Plot a face map of the core.

    Parameters
    ----------
    core: Core
        The core to plot.

    param : str, optional
        The block-parameter to plot. Default: pdens

    vals : str, optional
        Can be 'peak', 'average', or 'sum'. The type of vals to produce. Will find peak,
        average, or sum of block values in an assembly. Default: peak

    data : list, optional
        rather than using param and vals, use the data supplied as is. It must be in the
        same order as iter(r).

    fName : str, optional
        File name to create. If none, will show on screen.

    bare : bool, optional
        If True, will skip axis labels, etc.

    cmapName : str
        The name of the matplotlib colormap to use. Default: jet
        Other possibilities: http://matplotlib.org/examples/pylab_examples/show_colormaps.html

    labels : list of str, optional
        Data labels corresponding to data values.

    labelFmt : str, optional
        A format string that determines how the data is printed if ``labels`` is not provided.
        E.g. ``"{:.1e}"``

    legendMap : list, optional
        A tuple list of (value, lable, decription), to define the data in the legend.

    fontSize : int, optional
        Font size in points

    minScale : float, optional
        The minimum value for the low color on your colormap (to set scale yourself)
        Default: autoscale

    maxScale : float, optional
        The maximum value for the high color on your colormap (to set scale yourself)
        Default: autoscale

    axisEqual : Boolean, optional
        If True, horizontal and vertical axes are scaled equally such that a circle
        appears as a circle rather than an ellipse.

        If False, this scaling constraint is not imposed.

    makeColorBar : Boolean, optional
        If True, a vertical color bar is added on the right-hand side of the plot.

        If False, no color bar is added.

    cBarLabel : String, optional
        If True, this string is the color bar quantity label.
        If False, the color bar will have no label.
        When makeColorBar=False, cBarLabel affects nothing.

    title : String, optional
        If True, the string is added as the plot title.
        If False, no plot title is added.

    shuffleArrows : list, optional
        Adds arrows indicating fuel shuffling maneuvers

    titleSize : int, optional
        Size of title on plot

    referencesToKeep : list, optional
        References to previous plots you might want to plot on: patches, collection, texts.

    Examples
    --------
    Plotting a BOL assembly type facemap with a legend::

        >>> plotFaceMap(core, param='typeNumAssem', cmapName='RdYlBu')
    """
    if referencesToKeep:
        patches, collection, texts = referencesToKeep
        fig, ax = plt.gcf(), plt.gca()
    else:
        fig, ax = plt.subplots(figsize=(12, 12), dpi=100)
        # set patch (shapes such as hexagon) heat map values
        patches = _makeAssemPatches(core)
        collection = PatchCollection(patches, cmap=cmapName, alpha=1.0)
        texts = []

    ax.set_title(title, size=titleSize)

    # get param vals
    if data is None:
        data = []
        for a in core:
            if vals == "peak":
                data.append(a.getMaxParam(param))
            elif vals == "average":
                data.append(a.calcAvgParam(param))
            elif vals == "sum":
                data.append(a.calcTotalParam(param))
            else:
                raise ValueError(
                    "{0} is an invalid entry for `vals` in plotFaceMap. Use peak, average, or sum.".format(
                        vals
                    )
                )
    if not labels:
        labels = [None] * len(data)
    if len(data) != len(labels):
        raise ValueError(
            "Data had length {}, but lables had length {}. "
            "They should be equal length.".format(len(data), len(labels))
        )

    collection.set_array(numpy.array(data))
    if minScale or maxScale:
        collection.set_clim([minScale, maxScale])
    else:
        collection.norm.autoscale(numpy.array(data))
    ax.add_collection(collection)

    # Makes text in the center of each shape displaying the values.
    # (The text is either black or white depending on the background color it is written on)
    _setPlotValText(ax, texts, core, data, labels, labelFmt, fontSize, collection)

    # allow a color bar option
    if makeColorBar:
        collection2 = PatchCollection(patches, cmap=cmapName, alpha=1.0)
        if minScale and maxScale:
            collection2.set_array(numpy.array([minScale, maxScale]))
        else:
            collection2.set_array(numpy.array(data))

        if "radial" in cBarLabel:
            colbar = fig.colorbar(
                collection2, ticks=[x + 1 for x in range(max(data))], shrink=0.43
            )
        else:
            colbar = fig.colorbar(collection2, ax=ax, shrink=0.43)

        colbar.set_label(cBarLabel, size=20)
        colbar.ax.tick_params(labelsize=16)

    if legendMap is not None:
        legend = _createLegend(legendMap, collection)

    else:
        legend = None

    if axisEqual:  # don't "squish" patches vertically or horizontally
        ax.set_aspect("equal", "datalim")

    ax.autoscale_view(tight=True)

    # make it 2-D, for now...
    shuffleArrows = shuffleArrows or []
    for (sourceCoords, destinationCoords) in shuffleArrows:
        ax.annotate(
            "",
            xy=destinationCoords[:2],
            xytext=sourceCoords[:2],
            arrowprops={"arrowstyle": "->", "color": "white"},
        )

    if bare:
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
    else:
        ax.set_xlabel("x (cm)")
        ax.set_ylabel("y (cm)")

    if fName:
        if legend:
            # expand so the legend fits if necessary
            pltKwargs = {"bbox_extra_artists": (legend,), "bbox_inches": "tight"}
        else:
            pltKwargs = {}
        try:
            plt.savefig(fName, dpi=150, **pltKwargs)
        except IOError:
            runLog.warning(
                "Cannot update facemap at {0}: IOError. Is the file open?"
                "".format(fName)
            )
    elif referencesToKeep:
        # Don't show yet, since it will be updated.
        return fName
    else:
        plt.show()

    # don't close figure here. Have caller call plotting.close or plt.close when
    # they are done with it.

    return fName


def close(fig=None):
    """
    Wrapper for matplotlib close.

    This is useful to avoid needing to import plotting and matplotlib.
    The plot functions cannot always close their figure if it is going
    to be used somewhere else after becoming active (e.g. in reports
    or gallery examples).
    """
    plt.close(fig)


def _makeAssemPatches(core):
    """Return a list of assembly shaped patch for each assembly."""
    patches = []

    if isinstance(core.spatialGrid, grids.HexGrid):
        nSides = 6
    elif isinstance(core.spatialGrid, grids.ThetaRZGrid):
        raise TypeError(
            "This plot function is not currently supported for ThetaRZGrid grids."
        )
    else:
        nSides = 4

    pitch = core.getAssemblyPitch()
    for a in core:
        x, y, _ = a.spatialLocator.getLocalCoordinates()
        if nSides == 6:
            assemPatch = matplotlib.patches.RegularPolygon(
                (x, y), nSides, pitch / math.sqrt(3), orientation=math.pi / 2.0
            )
        elif nSides == 4:
            # for rectangle x, y is defined as sides instead of center
            assemPatch = matplotlib.patches.Rectangle(
                (x - pitch[0] / 2, y - pitch[1] / 2), *pitch
            )
        else:
            raise ValueError(f"Unexpected number of sides: {nSides}.")
        patches.append(assemPatch)
    return patches


def _setPlotValText(ax, texts, core, data, labels, labelFmt, fontSize, collection):
    """Write param values down, and return text so it can be edited later."""
    _ = core.getAssemblyPitch()
    for a, val, label in zip(core, data, labels):
        x, y, _ = a.spatialLocator.getLocalCoordinates()
        cmap = collection.get_cmap()
        patchColor = numpy.asarray(cmap(collection.norm(val)))
        luminance = patchColor.dot(LUMINANCE_WEIGHTS)
        dark = luminance < 0.5
        if dark:
            color = "white"
        else:
            color = "black"
        # Write text on top of patch locations.
        if label is None and labelFmt is not None:
            # Write the value
            labelText = labelFmt.format(val)
            text = ax.text(
                x,
                y,
                labelText,
                zorder=1,
                ha="center",
                va="center",
                fontsize=fontSize,
                color=color,
            )
        elif label is not None:
            text = ax.text(
                x,
                y,
                label,
                zorder=1,
                ha="center",
                va="center",
                fontsize=fontSize,
                color=color,
            )
        else:
            # labelFmt was none, so they don't want any text plotted
            continue
        texts.append(text)


def _createLegend(legendMap, collection, size=9, shape=Hexagon):
    """Make special legend for the assembly face map plot with assembly counts, and Block Diagrams."""

    class AssemblyLegend:
        """
        Custom Legend artist handler.

        Matplotlib allows you to define a class that implements ``legend_artist`` to give you
        full control over how the legend keys and labels are drawn. This is done here to get
        Hexagons with Letters in them on the legend, which is not a built-in legend option.

        See: http://matplotlib.org/users/legend_guide.html#implementing-a-custom-legend-handler
        """

        def legend_artist(self, _legend, orig_handle, _fontsize, handlebox):
            letter, index = orig_handle
            x0, y0 = handlebox.xdescent, handlebox.ydescent
            width, height = handlebox.width, handlebox.height
            x = x0 + width / 2.0
            y = y0 + height / 2.0
            normVal = collection.norm(index)
            cmap = collection.get_cmap()
            colorRgb = cmap(normVal)
            if shape == Hexagon:
                patch = matplotlib.patches.RegularPolygon(
                    (x, y),
                    6,
                    height,
                    orientation=math.pi / 2.0,
                    facecolor=colorRgb,
                    transform=handlebox.get_transform(),
                )
            elif shape == Rectangle:
                patch = matplotlib.patches.Rectangle(
                    (x - height / 2, y - height / 2),
                    height * 2,
                    height,
                    facecolor=colorRgb,
                    transform=handlebox.get_transform(),
                )
            else:
                patch = matplotlib.patches.Circle(
                    (x, y),
                    height,
                    facecolor=colorRgb,
                    transform=handlebox.get_transform(),
                )

            luminance = numpy.array(colorRgb).dot(LUMINANCE_WEIGHTS)
            dark = luminance < 0.5
            if dark:
                color = "white"
            else:
                color = "black"
            handlebox.add_artist(patch)
            txt = mpl_text.Text(
                x=x, y=y, text=letter, ha="center", va="center", size=7, color=color
            )
            handlebox.add_artist(txt)
            return (patch, txt)

    ax = plt.gca()
    keys = []
    labels = []
    for value, label, description in legendMap:
        keys.append((label, value))
        labels.append(description)

    legend = ax.legend(
        keys,
        labels,
        handler_map={tuple: AssemblyLegend()},
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
        prop={"size": size},
    )
    return legend


class DepthSlider(Slider):
    """Page slider used to view params at different depths."""

    def __init__(
        self,
        ax,
        sliderLabel,
        depths,
        updateFunc,
        selectedDepthColor,
        fontsize=8,
        valInit=0,
        **kwargs,
    ):
        # The color of the currently displayed depth page.
        self.selectedDepthColor = selectedDepthColor
        self.nonSelectedDepthColor = "w"

        self.depths = depths

        # Make the selection depth buttons
        self.depthSelections = []
        numDepths = float(len(depths))
        rectangleBot = 0
        textYCoord = 0.5
        # startBoundaries go from zero to just below 1.
        leftBoundary = [i / numDepths for i, _depths in enumerate(depths)]
        for leftBoundary, depth in zip(leftBoundary, depths):
            # First depth (leftBoundary==0) is on, rest are off.
            if leftBoundary == 0:
                color = self.selectedDepthColor
            else:
                color = self.nonSelectedDepthColor
            depthSelectBox = matplotlib.patches.Rectangle(
                (leftBoundary, rectangleBot),
                1.0 / numDepths,
                1,
                transform=ax.transAxes,
                facecolor=color,
            )
            ax.add_artist(depthSelectBox)
            self.depthSelections.append(depthSelectBox)

            # Make text halfway into box
            textXCoord = leftBoundary + 0.5 / numDepths
            ax.text(
                textXCoord,
                textYCoord,
                "{:.1f}".format(depth),
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=fontsize,
            )

        # Make forward and backward button
        backwardArrow, forwardArrow = "$\u25C0$", "$\u25B6$"
        divider = axes_grid1.make_axes_locatable(ax)
        buttonWidthPercent = "5%"
        backwardAxes = divider.append_axes("right", size=buttonWidthPercent, pad=0.03)
        forwardAxes = divider.append_axes("right", size=buttonWidthPercent, pad=0.03)
        self.backButton = matplotlib.widgets.Button(
            backwardAxes,
            label=backwardArrow,
            color=self.nonSelectedDepthColor,
            hovercolor=self.selectedDepthColor,
        )
        self.backButton.label.set_fontsize(fontsize)
        self.backButton.on_clicked(self.previous)
        self.forwardButton = matplotlib.widgets.Button(
            forwardAxes,
            label=forwardArrow,
            color=self.nonSelectedDepthColor,
            hovercolor=self.selectedDepthColor,
        )
        self.forwardButton.label.set_fontsize(fontsize)
        self.forwardButton.on_clicked(self.next)

        # init at end since slider will set val to 0, and it needs to have state
        # setup before doing that
        Slider.__init__(self, ax, sliderLabel, 0, len(depths), valinit=0, **kwargs)
        self.on_changed(updateFunc)
        self.set_val(valInit)  # need to set after updateFunc is added.

        # Turn off value visibility since the buttons text shows the value
        self.valtext.set_visible(False)

    def set_val(self, val):
        """
        Set the value and update the color.

        Notes
        -----
        valmin/valmax are set on the parent to 0 and len(depths).
        """
        val = int(val)
        # valmax is not allowed, since it is out of the array.
        # valmin is allowed since 0 index is in depth array.
        if val < self.valmin or val >= self.valmax:
            # invalid, so ignore
            return
        # activate color is first since we still have access to self.val
        self.updatePageDepthColor(val)
        Slider.set_val(self, val)

    def next(self, _event):
        """Move forward to the next depth (page)."""
        self.set_val(self.val + 1)

    def previous(self, _event):
        """Move backward to the previous depth (page)."""
        self.set_val(self.val - 1)

    def updatePageDepthColor(self, newVal):
        """Update the page colors."""
        self.depthSelections[self.val].set_facecolor(self.nonSelectedDepthColor)
        self.depthSelections[newVal].set_facecolor(self.selectedDepthColor)


def plotAssemblyTypes(
    blueprints=None,
    fileName=None,
    assems=None,
    maxAssems=None,
    showBlockAxMesh=True,
    yAxisLabel=None,
    title=None,
) -> plt.Figure:
    """
    Generate a plot showing the axial block and enrichment distributions of each assembly type in the core.

    Parameters
    ----------
    blueprints: Blueprints
        The blueprints to plot assembly types of. (Either this or ``assems`` must be non-None.)

    fileName : str or None
        Base for filename to write, or None for just returning the fig

    assems: list
        list of assembly objects to be plotted. (Either this or ``blueprints`` must be non-None.)

    maxAssems: integer
        maximum number of assemblies to plot in the assems list.

    showBlockAxMesh: bool
        if true, the axial mesh information will be displayed on the right side of the assembly plot.

    yAxisLabel: str
        Optionally, provide a label for the Y-axis.

    title: str
        Optionally, provide a title for the plot.

    Returns
    -------
    fig : plt.Figure
        The figure object created
    """
    # input validation
    if assems is None and blueprints is None:
        raise ValueError(
            "At least one of these inputs must be non-None: blueprints, assems"
        )

    # handle defaults
    if assems is None:
        assems = list(blueprints.assemblies.values())

    if not isinstance(assems, (list, set, tuple)):
        assems = [assems]

    if maxAssems is not None and not isinstance(maxAssems, int):
        raise TypeError("Maximum assemblies should be an integer")

    numAssems = len(assems)
    if maxAssems is None:
        maxAssems = numAssems

    if yAxisLabel is None:
        yAxisLabel = "THERMALLY EXPANDED AXIAL HEIGHTS (CM)"

    if title is None:
        title = "Assembly Designs"

    # Set assembly/block size constants
    yBlockHeights = []
    yBlockAxMesh = OrderedSet()
    assemWidth = 5.0
    assemSeparation = 0.3
    xAssemLoc = 0.5
    xAssemEndLoc = numAssems * (assemWidth + assemSeparation) + assemSeparation

    # Setup figure
    fig, ax = plt.subplots(figsize=(15, 15), dpi=300)
    for index, assem in enumerate(assems):
        isLastAssem = True if index == (numAssems - 1) else False
        (xBlockLoc, yBlockHeights, yBlockAxMesh) = _plotBlocksInAssembly(
            ax,
            assem,
            isLastAssem,
            yBlockHeights,
            yBlockAxMesh,
            xAssemLoc,
            xAssemEndLoc,
            showBlockAxMesh,
        )
        xAxisLabel = re.sub(" ", "\n", assem.getType().upper())
        ax.text(
            xBlockLoc + assemWidth / 2.0,
            -5,
            xAxisLabel,
            fontsize=13,
            ha="center",
            va="top",
        )
        xAssemLoc += assemWidth + assemSeparation

    # Set up plot layout
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.yaxis.set_ticks_position("left")
    yBlockHeights.insert(0, 0.0)
    yBlockHeights.sort()
    yBlockHeightDiffs = numpy.diff(
        yBlockHeights
    )  # Compute differential heights between each block
    ax.set_yticks([0.0] + list(set(numpy.cumsum(yBlockHeightDiffs))))
    ax.xaxis.set_visible(False)

    ax.set_title(title, y=1.03)
    ax.set_ylabel(yAxisLabel, labelpad=20)
    ax.set_xlim([0.0, 0.5 + maxAssems * (assemWidth + assemSeparation)])

    # Plot and save figure
    ax.plot()
    if fileName:
        fig.savefig(fileName)
        runLog.debug("Writing assem layout {} in {}".format(fileName, os.getcwd()))
        plt.close(fig)

    return fig


def _plotBlocksInAssembly(
    axis,
    assem,
    isLastAssem,
    yBlockHeights,
    yBlockAxMesh,
    xAssemLoc,
    xAssemEndLoc,
    showBlockAxMesh,
):
    # Set dictionary of pre-defined block types and colors for the plot
    lightsage = "xkcd:light sage"
    blockTypeColorMap = collections.OrderedDict(
        {
            "fuel": "tomato",
            "shield": "cadetblue",
            "reflector": "darkcyan",
            "aclp": "lightslategrey",
            "plenum": "white",
            "duct": "plum",
            "control": lightsage,
            "handling socket": "lightgrey",
            "grid plate": "lightgrey",
            "inlet nozzle": "lightgrey",
        }
    )

    # Initialize block positions
    blockWidth = 5.0
    yBlockLoc = 0
    xBlockLoc = xAssemLoc
    xTextLoc = xBlockLoc + blockWidth / 20.0
    for b in assem:
        blockHeight = b.getHeight()
        blockXsId = b.p.xsType
        yBlockCenterLoc = yBlockLoc + blockHeight / 2.5

        # Get the basic text label for the block
        try:
            blockType = [
                bType
                for bType in blockTypeColorMap.keys()
                if b.hasFlags(Flags.fromString(bType))
            ][0]
            color = blockTypeColorMap[blockType]
        except IndexError:
            blockType = b.getType()
            color = "grey"

        # Get the detailed text label for the block
        dLabel = ""
        if b.hasFlags(Flags.FUEL):
            dLabel = " {:0.2f}%".format(b.getFissileMassEnrich() * 100)
        elif b.hasFlags(Flags.CONTROL):
            blockType = "ctrl"
            dLabel = " {:0.2f}%".format(b.getBoronMassEnrich() * 100)
        dLabel += " ({})".format(blockXsId)

        # Set up block rectangle
        blockPatch = matplotlib.patches.Rectangle(
            (xBlockLoc, yBlockLoc),
            blockWidth,
            blockHeight,
            facecolor=color,
            alpha=0.7,
            edgecolor="k",
            lw=1.0,
            ls="solid",
        )
        axis.add_patch(blockPatch)
        axis.text(
            xTextLoc,
            yBlockCenterLoc,
            blockType.upper() + dLabel,
            ha="left",
            fontsize=10,
        )
        yBlockLoc += blockHeight
        yBlockHeights.append(yBlockLoc)

        # Add location, block heights, and axial mesh points to ordered set
        yBlockAxMesh.add((yBlockCenterLoc, blockHeight, b.p.axMesh))

    # Add the block heights, block number of axial mesh points on the far right of the plot.
    if isLastAssem and showBlockAxMesh:
        xEndLoc = 0.5 + xAssemEndLoc
        for bCenter, bHeight, axMeshPoints in yBlockAxMesh:
            axis.text(
                xEndLoc,
                bCenter,
                "{} cm ({})".format(bHeight, axMeshPoints),
                fontsize=10,
                ha="left",
            )

    return xBlockLoc, yBlockHeights, yBlockAxMesh


def plotBlockFlux(core, fName=None, bList=None, peak=False, adjoint=False, bList2=[]):
    """
    Produce energy spectrum plot of real and/or adjoint flux in one or more blocks.

    Parameters
    ----------
    core : Core
        Core object
    fName : str, optional
        the name of the plot file to produce. If none, plot will be shown. A text file with
        the flux values will also be generated if this is non-empty.
    bList : iterable, optional
        is a single block or a list of blocks to average over. If no bList, full core is assumed.
    peak : bool, optional
        a flag that will produce the peak as well as the average on the plot.
    adjoint : bool, optional
        plot the adjoint as well.
    bList2 :
        a separate list of blocks that will also be plotted on a separate axis on the same plot.
        This is useful for comparing flux in some blocks with flux in some other blocks.

    Notes
    -----
    This is not a great method. It should be cleand up and migrated into ``utils.plotting``.
    """

    class BlockListFlux:
        def __init__(
            self, nGroup, blockList=[], adjoint=False, peak=False, primary=False
        ):
            self.nGroup = nGroup
            self.blockList = blockList
            self.adjoint = adjoint
            self.peak = peak
            self.avgHistogram = None
            self.eHistogram = None
            self.peakHistogram = None
            self.E = None

            if not blockList:
                self.avgFlux = numpy.zeros(self.nGroup)
                self.peakFlux = numpy.zeros(self.nGroup)
                self.lineAvg = "-"
                self.linePeak = "-"
            else:
                self.avgFlux = numpy.zeros(self.nGroup)
                self.peakFlux = numpy.zeros(self.nGroup)

                if self.adjoint:
                    self.labelAvg = "Average Adjoint Flux"
                    self.labelPeak = "Peak Adjoint Flux"
                else:
                    self.labelAvg = "Average Flux"
                    self.labelPeak = "Peak Flux"

                if primary:
                    self.lineAvg = "-"
                    self.linePeak = "-"
                else:
                    self.lineAvg = "r--"
                    self.linePeak = "k--"

        def calcAverage(self):
            for b in self.blockList:
                thisFlux = numpy.array(b.getMgFlux(adjoint=self.adjoint))
                self.avgFlux += numpy.array(thisFlux)
                if sum(thisFlux) > sum(self.peakFlux):
                    self.peakFlux = thisFlux

            self.avgFlux = self.avgFlux / len(bList)

        def setEnergyStructure(self, upperEnergyBounds):
            self.E = [eMax / 1e6 for eMax in upperEnergyBounds]

        def makePlotHistograms(self):
            self.eHistogram, self.avgHistogram = makeHistogram(self.E, self.avgFlux)
            if self.peak:
                _, self.peakHistogram = makeHistogram(self.E, self.peakFlux)

        def checkSize(self):
            if not len(self.E) == len(self.avgFlux):
                runLog.error(self.avgFlux)
                raise

        def getTable(self):
            return enumerate(zip(self.E, self.avgFlux, self.peakFlux))

    if bList is None:
        bList = core.getBlocks()
    bList = list(bList)
    if adjoint and bList2:
        runLog.warning("Cannot plot adjoint flux with bList2 argument")
        return
    elif adjoint:
        bList2 = bList

    try:
        G = len(core.lib.neutronEnergyUpperBounds)
    except:  # noqa: bare-except
        runLog.warning("No ISOTXS library attached so no flux plots.")
        return

    BlockListFluxes = set()
    bf1 = BlockListFlux(G, blockList=bList, peak=peak, primary=True)
    BlockListFluxes.add(bf1)
    if bList2:
        bf2 = BlockListFlux(G, blockList=bList2, adjoint=adjoint, peak=peak)
        BlockListFluxes.add(bf2)

    for bf in BlockListFluxes:
        bf.calcAverage()
        bf.setEnergyStructure(core.lib.neutronEnergyUpperBounds)
        bf.checkSize()
        bf.makePlotHistograms()

    if fName:
        # write a little flux text file.
        txtFileName = os.path.splitext(fName)[0] + ".txt"
        with open(txtFileName, "w") as f:
            f.write(
                "{0:16s} {1:16s} {2:16s}\n".format(
                    "Energy_Group", "Average_Flux", "Peak_Flux"
                )
            )
            for _, (eMax, avgFlux, peakFlux) in bf1.getTable():
                f.write("{0:12E} {1:12E} {2:12E}\n".format(eMax, avgFlux, peakFlux))

    if max(bf1.avgFlux) <= 0.0:
        runLog.warning(
            "Cannot plot flux with maxval=={0} in {1}".format(bf1.avgFlux, bList[0])
        )
        return

    plt.figure()
    plt.plot(bf1.eHistogram, bf1.avgHistogram, bf1.lineAvg, label=bf1.labelAvg)

    if peak:
        plt.plot(bf1.eHistogram, bf1.peakHistogram, bf1.linePeak, label=bf1.labelPeak)

    ax = plt.gca()
    ax.set_xscale("log")
    ax.set_yscale("log")
    plt.xlabel("Energy (MeV)")
    plt.ylabel("Flux (n/cm$^2$/s)")

    if peak or bList2:
        plt.legend(loc="lower right")

    plt.grid(color="0.70")
    if bList2:
        if adjoint:
            plt.twinx()
            plt.ylabel("Adjoint Flux (n/cm$^2$/s)", rotation=270)
            ax2 = plt.gca()
            ax2.set_yscale("log")
        plt.plot(bf2.eHistogram, bf2.avgHistogram, bf2.lineAvg, label=bf2.labelAvg)
        if peak and not adjoint:
            plt.plot(
                bf2.eHistogram, bf2.peakHistogram, bf2.linePeak, label=bf2.labelPeak
            )
        plt.legend(loc="lower left")
    plt.title("Group flux")

    if fName:
        plt.savefig(fName)
        plt.close()
        report.setData(
            "Flux Plot {}".format(os.path.split(fName)[1]),
            os.path.abspath(fName),
            report.FLUX_PLOT,
        )
    else:
        plt.show()


def makeHistogram(x, y):
    """
    Take a list of x and y values, and return a histogram-ified version
    Good for plotting multigroup flux spectrum or cross sections.
    """
    if not len(x) == len(y):
        raise ValueError(
            "Cannot make a histogram unless the x and y lists are the same size."
            + "len(x) == {} and len(y) == {}".format(len(x), len(y))
        )
    n = len(x)
    xHistogram = numpy.zeros(2 * n)
    yHistogram = numpy.zeros(2 * n)
    for i in range(n):
        lower = 2 * i
        upper = 2 * i + 1
        xHistogram[lower] = x[i - 1]
        xHistogram[upper] = x[i]
        yHistogram[lower] = y[i]
        yHistogram[upper] = y[i]
    xHistogram[0] = x[0] / 2.0
    return xHistogram, yHistogram


def _makeBlockPinPatches(block, cold):
    """Return lists of block component patches and corresponding data and names (which relates to material
    of the component for later plot-coloring/legend) for a single block.


    Takes in a block that must have a spatialGrid attached as well as a variable
    which signifies whether the dimensions of the components are at hot or cold temps.
    When cold is set to true, you would get the BOL cold temp dimensions.

    Parameters
    ----------
    block : Block

    cold : boolean
        true for cold temps, hot = false

    Return
    ------
    patches : list
        list of patches for block components

    data : list
        list of the materials these components are made of

    name : list
        list of the names of these components
    """
    patches = []
    data = []
    names = []
    if isinstance(block.spatialGrid, grids.HexGrid):
        largestPitch, comp = block.getPitch(returnComp=True)

    elif isinstance(block.spatialGrid, grids.ThetaRZGrid):
        raise TypeError(
            "This plot function is not currently supported for ThetaRZGrid grids."
        )
    else:
        largestPitch, comp = block.getPitch(returnComp=True)
        if block.getPitch()[0] != block.getPitch()[1]:
            raise ValueError("Only works for blocks with equal length and width.")

    sortedComps = sorted(block, reverse=True)

    derivedComponents = block.getComponentsOfShape(DerivedShape)
    if len(derivedComponents) == 1:
        derivedComponent = derivedComponents[0]
        sortedComps.remove(derivedComponent)
        cName = derivedComponent.name

        if isinstance(derivedComponent.material, custom.Custom):
            material = derivedComponent.p.customIsotopicsName
        else:
            material = derivedComponent.material.name

        location = comp.spatialLocator
        if isinstance(location, grids.MultiIndexLocation):
            location = location[0]
        x, y, _ = location.getLocalCoordinates()
        if isinstance(comp, Hexagon):
            derivedPatch = matplotlib.patches.RegularPolygon(
                (x, y), 6, largestPitch / math.sqrt(3)
            )
        elif isinstance(comp, Square):
            derivedPatch = matplotlib.patches.Rectangle(
                (x - largestPitch[0] / 2, y - largestPitch[0] / 2),
                largestPitch[0],
                largestPitch[0],
            )
        else:
            raise TypeError(
                "Shape of the pitch-defining element is not a Square or Hex it is {}, cannot plot for this type of block".format(
                    comp.shape
                )
            )
        patches.append(derivedPatch)
        data.append(material)
        names.append(cName)
    for component in sortedComps:
        locs = component.spatialLocator
        if not isinstance(locs, grids.MultiIndexLocation):
            # make a single location a list to iterate.
            locs = [locs]
        for loc in locs:
            x, y, _ = loc.getLocalCoordinates()

            # goes through each location
            # want to place a patch at that location
            blockPatches = _makeComponentPatch(component, (x, y), cold)
            for element in blockPatches:
                patches.append(element)

                if isinstance(component.material, custom.Custom):
                    material = component.p.customIsotopicsName
                else:
                    material = component.material.name

                data.append(material)
                names.append(component.name)

    return patches, data, names


def _makeComponentPatch(component, position, cold):
    """Makes a component shaped patch to later be used for making block diagrams.

    Parameters
    ----------
        component: a component of a block

        position: tuple
            (x, y) position

        cold: boolean
            True if looking for dimension at cold temps

    Return
    ------
        blockPatch: List
            A list of Patch objects that together represent a component in the diagram.

    Notes
    -----
    Currently accepts components of shape DerivedShape, Helix, Circle, or Square
    """
    x = position[0]
    y = position[1]

    if isinstance(component, Helix):
        blockPatch = matplotlib.patches.Wedge(
            (
                x
                + component.getDimension("helixDiameter", cold=cold)
                / 2
                * math.cos(math.pi / 6),
                y
                + component.getDimension("helixDiameter", cold=cold)
                / 2
                * math.sin(math.pi / 6),
            ),
            component.getDimension("od", cold=cold) / 2,
            0,
            360,
            width=(component.getDimension("od", cold=cold) / 2)
            - (component.getDimension("id", cold=cold) / 2),
        )
    elif isinstance(component, Circle):

        blockPatch = matplotlib.patches.Wedge(
            (x, y),
            component.getDimension("od", cold=cold) / 2,
            0,
            360,
            width=(component.getDimension("od", cold=cold) / 2)
            - (component.getDimension("id", cold=cold) / 2),
        )
    elif isinstance(component, Hexagon):
        if component.getDimension("ip", cold=cold) != 0:
            innerPoints = numpy.array(
                hexagon.corners(30) * component.getDimension("ip", cold=cold)
            )
            outerPoints = numpy.array(
                hexagon.corners(30) * component.getDimension("op", cold=cold)
            )
            blockPatch = []
            for n in range(6):
                corners = [
                    innerPoints[n],
                    innerPoints[(n + 1) % 6],
                    outerPoints[(n + 1) % 6],
                    outerPoints[n],
                ]
                patch = matplotlib.patches.Polygon(corners, fill=True)
                blockPatch.append(patch)
        else:
            # Just make it a hexagon...
            blockPatch = matplotlib.patches.RegularPolygon(
                (x, y), 6, component.getDimension("op", cold=cold) / math.sqrt(3)
            )

    elif isinstance(component, Rectangle):
        if component.getDimension("widthInner", cold=cold) != 0:
            innerPoints = numpy.array(
                [
                    [
                        x + component.getDimension("widthInner", cold=cold) / 2,
                        y + component.getDimension("lengthInner", cold=cold) / 2,
                    ],
                    [
                        x + component.getDimension("widthInner", cold=cold) / 2,
                        y - component.getDimension("lengthInner", cold=cold) / 2,
                    ],
                    [
                        x - component.getDimension("widthInner", cold=cold) / 2,
                        y - component.getDimension("lengthInner", cold=cold) / 2,
                    ],
                    [
                        x - component.getDimension("widthInner", cold=cold) / 2,
                        y + component.getDimension("lengthInner", cold=cold) / 2,
                    ],
                ]
            )

            outerPoints = numpy.array(
                [
                    [
                        x + component.getDimension("widthOuter", cold=cold) / 2,
                        y + component.getDimension("lengthOuter", cold=cold) / 2,
                    ],
                    [
                        x + component.getDimension("widthOuter", cold=cold) / 2,
                        y - component.getDimension("lengthOuter", cold=cold) / 2,
                    ],
                    [
                        x - component.getDimension("widthOuter", cold=cold) / 2,
                        y - component.getDimension("lengthOuter", cold=cold) / 2,
                    ],
                    [
                        x - component.getDimension("widthOuter", cold=cold) / 2,
                        y + component.getDimension("lengthOuter", cold=cold) / 2,
                    ],
                ]
            )
            blockPatch = []
            for n in range(4):
                corners = [
                    innerPoints[n],
                    innerPoints[(n + 1) % 4],
                    outerPoints[(n + 1) % 4],
                    outerPoints[n],
                ]
                patch = matplotlib.patches.Polygon(corners, fill=True)
                blockPatch.append(patch)
        else:
            # Just make it a rectangle...
            blockPatch = matplotlib.patches.Rectangle(
                (
                    x - component.getDimension("widthOuter", cold=cold) / 2,
                    y - component.getDimension("lengthOuter", cold=cold) / 2,
                ),
                component.getDimension("widthOuter", cold=cold),
                component.getDimension("lengthOuter", cold=cold),
            )
    if isinstance(blockPatch, list):
        return blockPatch
    return [blockPatch]


def plotBlockDiagram(block, fName, cold, cmapName="RdYlBu", materialList=None):
    """Given a Block with a spatial Grid, plot the diagram of
    it with all of its components. (wire, duct, coolant, etc...).

    Parameters
    ----------
    block : block object
    fName : String
        name of the file to save to
    cold : boolean
        true is for cold temps, hot is false.
    cmapName : String
        name of a colorMap to use for block colors
    materialList: List
        a list of material names across all blocks to be plotted
        so that same material on all diagrams will have the same color.
    """
    _, ax = plt.subplots(figsize=(20, 20), dpi=200)

    if block.spatialGrid is None:
        return None

    if materialList is None:
        materialList = []
        for component in block:
            if isinstance(component.material, custom.Custom):
                materialName = component.p.customIsotopicsName
            else:
                materialName = component.material.name
            if materialName not in materialList:
                materialList.append(materialName)

    materialMap = {
        material: ai for ai, material in enumerate(numpy.unique(materialList))
    }
    patches, data, _ = _makeBlockPinPatches(block, cold)

    collection = PatchCollection(patches, cmap=cmapName, alpha=1.0)

    allColors = numpy.array(list(materialMap.values()))
    ourColors = numpy.array([materialMap[materialName] for materialName in data])

    collection.set_array(ourColors)
    ax.add_collection(collection)
    collection.norm.autoscale(allColors)

    legendMap = [
        (
            materialMap[materialName],
            "",
            "{}".format(materialName),
        )
        for materialName in numpy.unique(data)
    ]
    legend = _createLegend(legendMap, collection, size=50, shape=Rectangle)
    pltKwargs = {
        "bbox_extra_artists": (legend,),
        "bbox_inches": "tight",
    }

    ax.set_xticks([])
    ax.set_yticks([])

    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.margins(0)
    plt.savefig(fName, format="svg", **pltKwargs)
    plt.close()

    return os.path.abspath(fName)


def plotTriangleFlux(
    rtfluxData: RtfluxData,
    axialZ,
    energyGroup,
    hexPitch=math.sqrt(3.0),
    hexSideSubdivisions=1,
    imgFileExt=".png",
):
    """
    Plot region total flux for one core-wide axial slice on triangular/hexagonal geometry.

    .. warning:: This will run on non-triangular meshes but will look wrong.

    Parameters
    ----------
    rtfluxData : RtfluxData object
        The RTFLUX/ATFLUX data object containing all read file data.
        Alternatively, this could be a FIXSRC file object,
        but only if FIXSRC.fixSrc is first renamed FIXSRC.triangleFluxes.
    axialZ : int
        The DIF3D axial node index of the core-wide slice to plot.
    energyGroup : int
        The energy group index to plot.
    hexPitch: float, optional
        The flat-to-flat hexagonal assembly pitch in this core.
        By default, it is sqrt(3) so that the triangle edge length is 1 if hexSideSubdivisions=1.
    hexSideSubdivisions : int, optional
        By default, it is 1 so that the triangle edge length is 1 if hexPitch=sqrt(3).
    imgFileExt : str, optional
        The image file extension.

    Examples
    --------
    >>> rtflux = rtflux.RtfluxStream.readBinary("RTFLUX")
    >>> plotTriangleFlux(rtflux, axialZ=10, energyGroup=4)
    """
    triHeightInCm = hexPitch / 2.0 / hexSideSubdivisions
    sideLengthInCm = triHeightInCm / (math.sqrt(3.0) / 2.0)
    s2InCm = sideLengthInCm / 2.0

    vals = rtfluxData.groupFluxes[:, :, axialZ, energyGroup]
    patches = []
    colorVals = []
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            # use (i+j)%2 for rectangular meshing
            flipped = i % 2
            xInCm = s2InCm * (i - j)
            yInCm = triHeightInCm * j + sideLengthInCm / 2.0 / math.sqrt(3) * (
                1 + flipped
            )

            flux = vals[i][j]

            if flux:
                triangle = patches.mpatches.RegularPolygon(
                    (xInCm, yInCm),
                    3,
                    sideLengthInCm / math.sqrt(3),
                    orientation=math.pi * flipped,
                    linewidth=0.0,
                )

                patches.append(triangle)
                colorVals.append(flux)

    collection = PatchCollection(patches, alpha=1.0, linewidths=(0,), edgecolors="none")
    # add color map to this collection ONLY (pins, not ducts)
    collection.set_array(numpy.array(colorVals))

    plt.figure()
    ax = plt.gca()
    ax.add_collection(collection)
    colbar = plt.colorbar(collection)
    colbar.set_label("n/s/cm$^3$")
    plt.ylabel("cm")
    plt.xlabel("cm")
    ax.autoscale_view()
    plt.savefig("RTFLUX-z" + str(axialZ + 1) + "-g" + str(energyGroup + 1) + imgFileExt)
    plt.close()


def plotNucXs(
    isotxs, nucNames, xsNames, fName=None, label=None, noShow=False, title=None
):
    """
    generates a XS plot for a nuclide on the ISOTXS library.

    Parameters
    ----------
    isotxs : IsotxsLibrary
        A collection of cross sections (XS) for both neutron and gamma reactions.
    nucNames : str or list
        The nuclides to plot
    xsNames : str or list
        the XS to plot e.g. n,g, n,f, nalph, etc. see xsCollections for actual names.
    fName : str, optional
        if fName is given, the file will be written rather than plotting to screen
    label : str, optional
        is an optional label for image legends, useful in ipython sessions.
    noShow : bool, optional
        Won't finalize plot. Useful for using this to make custom plots.

    Examples
    --------
    >>> l = ISOTXS()
    >>> plotNucXs(l, 'U238NA','fission')

    >>> # Plot n,g for all xenon and krypton isotopes
    >>> f = lambda name: 'XE' in name or 'KR' in name
    >>> plotNucXs(l, sorted(filter(f,l.nuclides.keys())),itertools.repeat('nGamma'))

    See Also
    --------
    armi.nucDirectory.nuclide.plotScatterMatrix
    """
    # convert all input to lists
    if isinstance(nucNames, str):
        nucNames = [nucNames]
    if isinstance(xsNames, str):
        xsNames = [xsNames]

    for nucName, xsName in zip(nucNames, xsNames):
        nuc = isotxs[nucName]
        thisLabel = label or "{0} {1}".format(nucName, xsName)
        x = isotxs.neutronEnergyUpperBounds / 1e6
        y = nuc.micros[xsName]
        plt.plot(x, y, "-", label=thisLabel, drawstyle="steps-post")

    ax = plt.gca()
    ax.set_xscale("log")
    ax.set_yscale("log")
    plt.grid(color="0.70")
    plt.title(title or " microscopic XS from {0}".format(isotxs))
    plt.xlabel("Energy (MeV)")
    plt.ylabel("microscopic XS (barns)")
    plt.legend()

    if fName:
        plt.savefig(fName)
    elif not noShow:
        plt.show()

    plt.close()
