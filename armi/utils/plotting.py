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

import collections
import itertools
import math
import re
import os

import numpy
from ordered_set import OrderedSet
import matplotlib.pyplot as plt
import matplotlib.text as mpl_text
import matplotlib.collections
import matplotlib.patches
from mpl_toolkits import axes_grid1

from armi import runLog
from armi.reactor.flags import Flags
from armi.reactor import grids


def colorGenerator(skippedColors=10):
    """
    Selects a color from the built-in wx color database.

    Parameters
    ----------
    skippedColors: int
        Number of colors to skip in the built-in wx color database when generating the next color. Without skipping
        colors the next color may be similar to the previous color.

    Notes
    -----
    Will cycle indefinitely to accommodate large cores. Colors will repeat.
    """
    from wx.lib.colourdb import getColourList

    excludedColors = ["WHITE", "CREAM", "BLACK", "MINTCREAM"]
    colors = getColourList()
    for start in itertools.cycle(range(20, 20 + skippedColors)):
        for i in range(start, len(colors), skippedColors):
            if colors[i] not in excludedColors:
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
    collection = matplotlib.collections.PatchCollection(
        patches, cmap=cmapName, alpha=1.0
    )
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
    slider = PageSlider(ax_slider, "Depth(m)", elevations, activecolor="green")

    # This controls what the slider does.
    def update(val):
        i = int(slider.val)
        collection.set_array(data[i, :])
        for valToPrint, text in zip(data[i, :], texts):
            text.set_text(labelFmt.format(valToPrint))

    slider.on_changed(update)

    # right now plot is set to max values, set to a specific elevation's value.
    slider.set_val(depthIndex)  # sets the vals on the plot
    slider._colorize(depthIndex)  # changes to the right page

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

    vals : ['peak', 'average', 'sum'], optional
        the type of vals to produce. Will find peak, average, or sum of block values
        in an assembly. Default: peak

    data : list(numeric)
        rather than using param and vals, use the data supplied as is. It must be in the same order as iter(r).

    fName : str, optional
        File name to create. If none, will show on screen.

    bare : bool, optional
        If True, will skip axis labels, etc.

    cmapName : str
        The name of the matplotlib colormap to use. Default: jet
        Other possibilities: http://matplotlib.org/examples/pylab_examples/show_colormaps.html

    labels : iterable(str), optional
        Data labels corresponding to data values.

    labelFmt : str, optional
        A format string that determines how the data is printed if ``labels`` is not provided.

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

    plotPartsToUpdate : list, optional
        Send references to the parts of the plot such as patches, collections
        and texts to be changed by another plot utility.

    Examples
    --------
    Plotting a BOL assembly type facemap with a legend:
    >>> plotFaceMap(core, param='typeNumAssem', cmapName='RdYlBu')

    """
    if referencesToKeep:
        patches, collection, texts = referencesToKeep
    else:
        plt.figure(figsize=(12, 12), dpi=100)
        # set patch (shapes such as hexagon) heat map values
        patches = _makeAssemPatches(core)
        collection = matplotlib.collections.PatchCollection(
            patches, cmap=cmapName, alpha=1.0
        )
        texts = []
    ax = plt.gca()

    plt.title(title, size=titleSize)

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
    ax.add_collection(collection)
    collection.norm.autoscale(numpy.array(data))

    # Makes text in the center of each shape displaying the values.
    _setPlotValText(ax, texts, core, data, labels, labelFmt, fontSize)

    if makeColorBar:  # allow a color bar option
        collection2 = matplotlib.collections.PatchCollection(
            patches, cmap=cmapName, alpha=1.0
        )
        collection2.set_array(numpy.array(data))

        if "radial" in cBarLabel:
            colbar = plt.colorbar(collection2, ticks=[x + 1 for x in range(max(data))])
        else:
            colbar = plt.colorbar(collection2)

        colbar.set_label(cBarLabel, size=20)
        colbar.ax.tick_params(labelsize=16)

    if legendMap is not None:
        legend = _createFaceMapLegend(
            legendMap, matplotlib.cm.get_cmap(cmapName), collection.norm
        )
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
        plt.xlabel("x (cm)")
        plt.ylabel("y (cm)")

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

    plt.close()
    return fName


def _makeAssemPatches(core):
    """Return a list of assembly shaped patch for each assembly."""
    patches = []

    if isinstance(core.spatialGrid, grids.HexGrid):
        nSides = 6
    elif isinstance(core.spatialGrid, grids.ThetaRZGrid):
        raise ValueError(
            "This plot function is not currently supported for ThetaRZGrid grids."
        )
    else:
        nSides = 4

    pitch = core.getAssemblyPitch()
    for a in core:
        x, y = a.getLocationObject().coords(pitch)
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


def _setPlotValText(ax, texts, core, data, labels, labelFmt, fontSize):
    """Write param values down, and return text so it can be edited later."""
    pitch = core.getAssemblyPitch()
    for a, val, label in zip(core, data, labels):
        x, y = a.getLocationObject().coords(pitch)

        # Write text on top of patch locations.
        if label is None and labelFmt is not None:
            # Write the value
            labelText = labelFmt.format(val)
            text = ax.text(
                x, y, labelText, zorder=1, ha="center", va="center", fontsize=fontSize
            )
        elif label is not None:
            text = ax.text(
                x, y, label, zorder=1, ha="center", va="center", fontsize=fontSize
            )
        else:
            # labelFmt was none, so they don't want any text plotted
            continue
        texts.append(text)


def _createFaceMapLegend(legendMap, cmap, norm):
    """Make special assembly-legend for the assembly face map plot with assembly counts."""

    class AssemblyLegend(object):
        """
        Custom Legend artist handler.

        Matplotlib allows you to define a class that implements ``legend_artist`` to give you
        full control over how the legend keys and labels are drawn. This is done here to get
        Hexagons with Letters in them on the legend, which is not a built-in legend option.

        See: http://matplotlib.org/users/legend_guide.html#implementing-a-custom-legend-handler

        """

        def legend_artist(self, legend, orig_handle, fontsize, handlebox):
            letter, index = orig_handle
            x0, y0 = handlebox.xdescent, handlebox.ydescent
            width, height = handlebox.width, handlebox.height
            x = x0 + width / 2.0
            y = y0 + height / 2.0
            normVal = norm(index)
            colorRgb = cmap(normVal)
            patch = matplotlib.patches.RegularPolygon(
                (x, y),
                6,
                height,
                orientation=math.pi / 2.0,
                facecolor=colorRgb,
                transform=handlebox.get_transform(),
            )
            handlebox.add_artist(patch)
            txt = mpl_text.Text(x=x, y=y, text=letter, ha="center", va="center", size=7)
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
        prop={"size": 9},
    )
    return legend


class PageSlider(matplotlib.widgets.Slider):
    """
    Page slider used to view params at different depths.

    Notes
    -----
    Largly based off of:
    https://stackoverflow.com/questions/41143782/paging-scrolling-through-set-of-2d-heat-maps-in-matplotlib
    """

    def __init__(self, ax, label, depths, valinit=0, valfmt="%1d", **kwargs):

        self.facecolor = kwargs.get("facecolor", "w")
        self.activecolor = kwargs.pop("activecolor", "b")
        self.fontsize = kwargs.pop("fontsize", 7)
        self.depths = depths

        super(PageSlider, self).__init__(
            ax, label, 0, len(depths), valinit=valinit, valfmt=valfmt, **kwargs
        )

        self.poly.set_visible(False)
        self.vline.set_visible(False)
        self.pageRects = []
        numpages = len(depths)
        for i, depth in enumerate(depths):
            facecolor = self.activecolor if i == valinit else self.facecolor
            rectangle = matplotlib.patches.Rectangle(
                (float(i) / numpages, 0),
                1.0 / numpages,
                1,
                transform=ax.transAxes,
                facecolor=facecolor,
            )
            ax.add_artist(rectangle)
            self.pageRects.append(rectangle)
            ax.text(
                float(i) / numpages + 0.5 / numpages,
                0.5,
                "{:.1f}".format(depth),
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=self.fontsize,
            )
        self.valtext.set_visible(False)

        divider = axes_grid1.make_axes_locatable(ax)
        bax = divider.append_axes("right", size="5%", pad=0.05)
        fax = divider.append_axes("right", size="5%", pad=0.05)
        self.button_back = matplotlib.widgets.Button(
            bax, label="$\u25C0$", color=self.facecolor, hovercolor=self.activecolor
        )
        self.button_forward = matplotlib.widgets.Button(
            fax, label="$\u25B6$", color=self.facecolor, hovercolor=self.activecolor
        )
        self.button_back.label.set_fontsize(self.fontsize)
        self.button_forward.label.set_fontsize(self.fontsize)
        self.button_back.on_clicked(self.backward)
        self.button_forward.on_clicked(self.forward)

    def _update(self, event):
        super(PageSlider, self)._update(event)
        i = int(self.val)
        if i >= self.valmax:
            return
        self._colorize(i)

    def _colorize(self, i):
        for j in range(len(self.depths)):
            self.pageRects[j].set_facecolor(self.facecolor)
        self.pageRects[i].set_facecolor(self.activecolor)

    def forward(self, event):
        """Move forward to the next depth (page)."""
        current_i = int(self.val)
        i = current_i + 1
        if (i < self.valmin) or (i >= self.valmax):
            return
        self.set_val(i)
        self._colorize(i)

    def backward(self, event):
        """Move backward to the previous depth (page)."""
        current_i = int(self.val)
        i = current_i - 1
        if (i < self.valmin) or (i >= self.valmax):
            return
        self.set_val(i)
        self._colorize(i)


def plotAssemblyTypes(
    core, assems=None, plotNumber=1, maxAssems=None, showBlockAxMesh=True
):
    """
    Generate a plot showing the axial block and enrichment distributions of each assembly type in the core.

    Parameters
    ----------
    core: Core
        The core to plot assembly types of.

    assems: list
        list of assembly objects to be plotted.

    plotNumber: integer
        number of uniquely identify the assembly plot from others and to prevent plots from being overwritten.

    maxAssems: integer
        maximum number of assemblies to plot in the assems list.

    showBlockAxMesh: bool
        if true, the axial mesh information will be displayed on the right side of the assembly plot.
    """

    if assems is None:
        assems = list(core.parent.blueprints.assemblies.values())
    if not isinstance(assems, (list, set, tuple)):
        assems = [assems]
    if not isinstance(plotNumber, int):
        raise TypeError("Plot number should be an integer")
    if maxAssems is not None and not isinstance(maxAssems, int):
        raise TypeError("Maximum assemblies should be an integer")

    numAssems = len(assems)
    if maxAssems is None:
        maxAssems = numAssems

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

    ax.set_title("Assembly Designs for {}".format(core.name), y=1.03)
    ax.set_ylabel("Thermally Expanded Axial Heights (cm)".upper(), labelpad=20)
    ax.set_xlim([0.0, 0.5 + maxAssems * (assemWidth + assemSeparation)])

    # Plot and save figure
    ax.plot()
    figName = core.name + "AssemblyTypes{}.png".format(plotNumber)
    runLog.debug("Writing assem layout {} in {}".format(figName, os.getcwd()))
    fig.savefig(figName)
    plt.close(fig)
    return figName


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
