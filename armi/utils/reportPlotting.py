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
Plotting Utils specific to reports.

This module makes heavy use of matplotlib. Beware that plots generated with matplotlib
may not free their memory, even after the plot is closed, and excessive use of
plotting functions may gobble up all of your machine's memory.

Therefore, you should use these plotting tools judiciously. It is not advisable to,
for instance, plot some sequence of objects in a loop at every time node. If you start
to see your memory usage grow inexplicably, you should question any plots that you are
generating.
"""
import itertools
import math
import os

import matplotlib.path
import matplotlib.projections.polar
import matplotlib.pyplot as plt
import matplotlib.spines
import numpy as np
from matplotlib import colormaps
from matplotlib import colors as mpltcolors

from armi import runLog, settings
from armi.bookkeeping import report
from armi.physics.neutronics import crossSectionGroupManager
from armi.reactor.flags import Flags


def plotReactorPerformance(reactor, dbi, buGroups, extension=None, history=None):
    """
    Generates a set of plots useful in reactor analysis given a populated reactor.

    Parameters
    ----------
    reactor : armi.reactor.reactors.Reactor
        The reactor to plot

    dbi : armi.bookkeeping.db.DatabaseInterface
        The DatabaseInterface object from which to pull historical data

    buGroups : list of float
        The burnup groups in the problem

    extension : str, optional
        The file extension for saving plots

    history: armi.bookkeeping.historyTracker.HistoryTrackerInterface object
        The history tracker interface
    """
    try:
        data = dbi.getHistory(reactor, params=["cycle", "time"])
        data.update(
            dbi.getHistory(
                reactor.core,
                params=[
                    "keff",
                    "keffUnc",
                    "maxPD",
                    "maxBuI",
                    "maxBuF",
                    "maxDPA",
                    "numMoves",
                ],
            )
        )
    except Exception as ee:
        runLog.warning(
            "Cannot plot rxPerformance without the data model present in the database.\nError: {}".format(
                ee
            )
        )
        return

    # data is a dict of OrderedDict: { <paramName> : { (<cycle>, <node>) : value } }
    scalars = {key: list(timeStepDict.values()) for key, timeStepDict in data.items()}
    runLog.info("scalars for plotting {}".format(scalars))

    valueVsTime(
        reactor.name,
        scalars["time"],
        scalars["maxPD"],
        "maxPD",
        "Max Areal PD (MW/m^2)",
        "Max Areal PD vs. time",
        0.0,
        extension=extension,
    )
    keffVsTime(
        reactor.name,
        scalars["time"],
        scalars["keff"],
        scalars["keffUnc"],
        ymin=1.0,
        extension=extension,
    )
    xsHistoryVsTime(reactor.name, history, buGroups, extension=extension)
    movesVsCycle(reactor.name, scalars, extension=extension)


def valueVsTime(name, x, y, key, yaxis, title, ymin=None, extension=None):
    """
    Plots a value vs. time with a standard graph format.

    Parameters
    ----------
    name : str
        Reactor.name
    x : iterable
        The x-axis values (the abscissa)
    y : iterable
        The y-axis values (the ordinate)
    key : str
        A key word to add the item to the report interface
    yaxis : str
        The y axis label
    title : str
        the plot title
    ymin : str, optional
        The minimum y-axis value. If any ordinates are less than this value,
        it will be ignored.
    extension : str, optional
        The file extension for saving the figure
    """
    extension = extension or settings.Settings()["outputFileExtension"]

    plt.figure()
    plt.plot(x, y, ".-")
    plt.xlabel("Time (yr)")
    plt.ylabel(yaxis)
    plt.grid(color="0.70")
    plt.title(title + " for {0}".format(name))

    if ymin is not None and all([yi > ymin for yi in y]):
        # set ymin all values are greater than it and it exists.
        ax = plt.gca()
        ax.set_ylim(bottom=ymin)

    figName = name + "." + key + "." + extension
    plt.savefig(figName)
    plt.close(1)

    report.setData("PlotTime", os.path.abspath(figName), report.TIME_PLOT)


def keffVsTime(name, time, keff, keffUnc=None, ymin=None, extension=None):
    """
    Plots core keff vs. time.

    Parameters
    ----------
    name : str
        reactor.name
    time : list
        Time in years
    keff : list
        Keff in years
    keffUnc : list, optional
        Uncontrolled keff or None (will be plotted as secondary series)
    ymin : float, optional
        Minimum y-axis value to target.
    extension : str, optional
        The file extension for saving the figure
    """
    extension = extension or settings.Settings()["outputFileExtension"]

    plt.figure()
    if any(keffUnc):
        label1 = "Controlled k-eff"
        label2 = "Uncontrolled k-eff"
    else:
        label1 = None

    plt.plot(time, keff, ".-", label=label1)
    if any(keffUnc):
        plt.plot(time, keffUnc, ".-", label=label2)
        plt.legend()
    plt.xlabel("Time (yr)")
    plt.ylabel("k-eff")
    plt.grid(color="0.70")
    plt.title("k-eff vs. time" + " for {0}".format(name))

    if ymin is not None and all([yi > ymin for yi in keff]):
        # set ymin all values are greater than it and it exists.
        ax = plt.gca()
        ax.set_ylim(bottom=ymin)

    figName = name + ".keff." + extension
    plt.savefig(figName)
    plt.close(1)

    report.setData("K-Eff", os.path.abspath(figName), report.KEFF_PLOT)


def xsHistoryVsTime(name, history, buGroups, extension=None):
    r"""
    Plot cross section history vs. time.

    Parameters
    ----------
    name : str
        reactor.name
    history : armi.bookkeeping.historyTracker.HistoryTrackerInterface object
        The history interface.
    buGroups : list of float
        The burnup groups in the problem
    extension : str, optional
        The file extension for saving the figure
    """
    extension = extension or settings.Settings()["outputFileExtension"]

    if history is None or not history.xsHistory:
        return

    colors = itertools.cycle(["b", "g", "r", "c", "m", "y", "k"])
    plt.figure()
    maxbu = 0.0
    for typeNum, dataList in history.xsHistory.items():
        times = [d[0] for d in dataList]
        burnups = [d[1] for d in dataList]
        maxb = max(burnups)
        if maxb > maxbu:
            maxbu = maxb
        xsType = crossSectionGroupManager.getXSTypeLabelFromNumber(typeNum)
        color = next(colors)
        plt.plot(times, burnups, color + ".", label="Type {0} XS".format(xsType))

    for upperBu in [0.0] + buGroups:
        # draw a hline at the limits of each burnup group
        plt.axhline(y=upperBu)

    plt.legend()
    plt.title("Block burnups used to generate XS for {0}".format(name))
    plt.xlabel("Time (years)")
    plt.ylabel(r"Burnup (% FIMA)")

    plt.ylim(0, maxbu * 1.05)
    figName = name + ".bugroups." + extension
    plt.savefig(figName)
    plt.close(1)
    report.setData("Xs Plot", os.path.abspath(figName), report.XS_PLOT)


def movesVsCycle(name, scalars, extension=None):
    """
    Make a bar chart showing the number of moves per cycle in the full core.

    A move is defined as an assembly being picked up, moved, and put down. So if
    two assemblies are swapped, that is 2 moves. Note that it does not count
    temporary storage for such swaps. This is an approximation because in a chain of moves,
    only one out of the chain would have to be temporarily stored. So as the chains get longer,
    this approximation gets more accurate.

    Parameters
    ----------
    name : str
        reactor.name
    extension : str, optional
        The file extension for saving the figure

    See Also
    --------
    FuelHandler.outage : sets the number of moves in each cycle
    """
    extension = extension or settings.Settings()["outputFileExtension"]

    cycles = []
    yvals = []
    for moves, cycle in zip(scalars["numMoves"], scalars["cycle"]):
        if moves is None:
            moves = 0.0
        if cycle not in cycles:  # only one move per cycle
            # use the cycles scalar val in case burnSteps is dynamic
            cycles.append(cycle)
            yvals.append(moves)

    plt.figure(figsize=(12, 6))  # make it wide and short
    plt.bar(cycles, yvals, align="center")
    if len(cycles) > 1:
        plt.xticks(cycles)
    plt.grid(color="0.70")
    plt.xlabel("Cycle")
    plt.ylabel("Number of Moves")
    plt.title("Fuel management rate for " + name)
    figName = name + ".moves." + extension
    plt.savefig(figName)
    plt.close(1)

    report.setData("Moves Plot", os.path.abspath(figName), report.MOVES_PLOT)


def plotCoreOverviewRadar(reactors, reactorNames=None):
    """
    Plot key features of a set of reactors on radar/spider plots.

    Useful for comparing reactors to one another.
    """
    runLog.info("Plotting reactor comparison.")
    fig = plt.figure(figsize=(17, 9))
    fig.subplots_adjust(wspace=0.25, hspace=0.20, top=0.85, bottom=0.05)
    colors = itertools.cycle(["b", "r", "g"])
    axes = {}
    thetas = {}
    scrapers = [
        _getNeutronicVals,
        _getMechanicalVals,
        _getFuelVals,
        _getTHVals,
        _getPhysicalVals,
    ]
    firstReactorVals = {}  # for normalization
    numRows, numCols = 2, (len(scrapers) + 1) // 2
    for r, color in zip(reactors, colors):
        for si, scraper in enumerate(scrapers):
            physicsName, physicsLabels, physicsVals = scraper(r)
            runLog.info("{}".format(physicsName))
            runLog.info(
                "\n".join(
                    [
                        "{:10s} {}".format(label, val)
                        for label, val in zip(physicsLabels, physicsVals)
                    ]
                )
            )
            physicsVals = np.array(physicsVals)
            theta = thetas.get(physicsName)
            if theta is None:
                # first time through. Build the radar, store the axis
                theta = _radarFactory(len(physicsLabels), frame="polygon")
                thetas[physicsName] = theta
                firstReactorVals[physicsName] = physicsVals
                ax = fig.add_subplot(numRows, numCols, si + 1, projection="radar")
                axes[physicsName] = ax
                ax.set_title(
                    physicsName,
                    weight="bold",
                    size="medium",
                    position=(0.5, 1.1),
                    horizontalalignment="center",
                    verticalalignment="center",
                )
                ax.set_var_labels(physicsLabels)
                plt.rgrids([0.2, 0.4, 0.6, 0.8])  # radial grid lines
            else:
                ax = axes[physicsName]
            with np.errstate(divide="ignore", invalid="ignore"):
                vals = (
                    physicsVals / firstReactorVals[physicsName]
                )  # normalize to first reactor b/c values differ by a lot.
                vals[np.isnan(vals)] = 0.2
            ax.plot(theta, vals, color=color)
            ax.fill(theta, vals, facecolor=color, alpha=0.25)

    if reactorNames:
        plt.subplot(numRows, numCols, 1)  # legend on top-left plot
        legend = plt.legend(reactorNames, loc=(0.9, 0.95), labelspacing=0.1)
    plt.setp(legend.get_texts(), fontsize="small")
    plt.figtext(
        0.5,
        0.965,
        "Comparison",
        ha="center",
        color="black",
        weight="bold",
        size="large",
    )
    plt.savefig("reactor_comparison.png")
    plt.close()


def _getNeutronicVals(r):
    labels, vals = list(
        zip(
            *[
                ("Rx. Swing", r.core.p.rxSwing),
                ("Fast Flux Fr.", r.core.p.fastFluxFrAvg),
                ("Leakage", r.core.p.leakageFracTotal),
                ("Beta", r.core.p.beta),
                ("Peak flux", r.core.p.maxFlux),
            ]
        )
    )
    return "Neutronics", labels, vals


def _getMechanicalVals(r):
    labels, vals = list(
        zip(
            *[
                ("Hold down", 1.0),
                ("Distortion", 3.0),
            ]
        )
    )

    return "Mechanical", labels, vals


def _getPhysicalVals(r):
    avgHeight = 0.0
    fuelA = r.core.getAssemblies(Flags.FUEL)

    # get average height
    avgHeight = 0
    for a in fuelA:
        for b in a.iterBlocks(Flags.FUEL):
            try:
                avgHeight += b.getInputHeight()
            except AttributeError:
                avgHeight += b.getHeight()
    avgHeight /= len(fuelA)

    radius = r.core.getCoreRadius()
    labels, vals = list(
        zip(
            *[
                ("Cold fuel height", avgHeight),
                ("Fuel assems", len(fuelA)),
                ("Assem weight", r.core.getFirstAssembly(Flags.FUEL).getMass()),
                ("Core radius", radius),
                ("Core aspect ratio", (2 * radius) / avgHeight),  # width/height
                ("Fissile mass", r.core.getFissileMass()),
            ]
        )
    )

    return "Dimensions", labels, vals


def _getFuelVals(r):
    tOverD = 0.0
    numClad = 0.0
    for b in r.core.iterBlocks(Flags.FUEL):
        clad = b.getComponent(Flags.CLAD)
        if clad:
            cladOD = clad.getDimension("od")
            cladID = clad.getDimension("id")
            tOverD += (cladOD - cladID) / cladOD
            numClad += 1
    tOverD /= numClad
    data = [
        (
            "Smear dens.",
            r.core.calcAvgParam("smearDensity", generationNum=2, typeSpec=Flags.FUEL),
        ),
        ("Clad T/D", tOverD),
        ("dpa", r.core.p.maxdetailedDpaPeak),
    ]
    labels, vals = list(zip(*data))
    return "Fuel Perf.", labels, vals


def _getTHVals(r):
    labels, vals = zip(
        *[
            ("Max PD", r.core.p.maxPD),
            ("Mass flow", r.core.getMaxParam("THmassFlowRate")),
            ("Th. striping", r.core.getMaxParam("THlocalDToutFuel")),
            ("Fuel temp", r.core.getMaxBlockParam("THhotChannelFuelCenterlineT")),
        ]
    )
    return "T/H", labels, vals


def _radarFactory(numVars, frame="circle"):
    """Create a radar chart with `numVars` axes.

    This function creates a RadarAxes projection and registers it.

    Raises
    ------
    ValueError
        If value of the frame is unknown.

    Parameters
    ----------
    numVars : int
        Number of variables for radar chart.
    frame : {'circle' | 'polygon'}
        Shape of frame surrounding axes.
    """
    # calculate evenly-spaced axis angles
    # rotate theta such that the first axis is at the top
    # keep within 0 to 2pi range though.
    theta = (np.linspace(0, 2 * np.pi, numVars, endpoint=False) + np.pi / 2) % (
        2.0 * np.pi
    )

    def drawPolyPatch():
        verts = _unitPolyVerts(theta)
        return plt.Polygon(verts, closed=True, edgecolor="k")

    def drawCirclePatch():
        # unit circle centered on (0.5, 0.5)
        return plt.Circle((0.5, 0.5), 0.5)

    def close_line(line):
        """Closes the input line."""
        x, y = line.get_data()
        if x[0] != x[-1]:
            x = np.concatenate((x, [x[0]]))
            y = np.concatenate((y, [y[0]]))
            line.set_data(x, y)

    patchDict = {"polygon": drawPolyPatch, "circle": drawCirclePatch}
    if frame not in patchDict:
        raise ValueError("unknown value for `frame`: %s" % frame)

    class _RadarAxes(matplotlib.projections.polar.PolarAxes):
        """
        Radar projection.

        Note different PEP8 naming convention to comply with parent class.
        """

        name = "radar"
        # use 1 line segment to connect specified points
        RESOLUTION = 1
        # define draw_frame method
        draw_patch = staticmethod(patchDict[frame])

        def fill(self, *args, **kwargs):
            """Override fill so that line is closed by default."""
            closed = kwargs.pop("closed", True)
            return super(_RadarAxes, self).fill(closed=closed, *args, **kwargs)

        def plot(self, *args, **kwargs):
            """Override plot so that line is closed by default."""
            lines = super(_RadarAxes, self).plot(*args, **kwargs)
            for line in lines:
                close_line(line)

        def set_var_labels(self, labels):
            self.set_thetagrids(np.degrees(theta), labels)

        def _gen_axes_patch(self):
            return self.draw_patch()

        def _gen_axes_spines(self):
            if frame == "circle":
                return matplotlib.projections.polar.PolarAxes._gen_axes_spines(self)
            # The following is a hack to get the spines (i.e. the axes frame)
            # to draw correctly for a polygon frame.

            # spine_type must be 'left', 'right', 'top', 'bottom', or `circle`.
            spine_type = "circle"
            verts = _unitPolyVerts(theta)
            # close off polygon by repeating first vertex
            verts.append(verts[0])
            path = matplotlib.path.Path(verts)

            spine = matplotlib.spines.Spine(self, spine_type, path)
            spine.set_transform(self.transAxes)
            return {"polar": spine}

    matplotlib.projections.register_projection(_RadarAxes)
    return theta


def _unitPolyVerts(theta):
    """Return vertices of polygon for subplot axes.

    This polygon is circumscribed by a unit circle centered at (0.5, 0.5)
    """
    x0 = y0 = r = 0.5
    verts = list(zip(r * np.cos(theta) + x0, r * np.sin(theta) + y0))
    return verts


def createPlotMetaData(
    title, xLabel, yLabel, xMajorTicks=None, yMajorTicks=None, legendLabels=None
):
    """
    Create plot metadata (title, labels, ticks).

    Parameters
    ----------
    title : str
        Plot title

    xLabel : str
        x-axis label

    yLabel : str
        y-axis label

    xMajorTicks : list of float
        List of axial position at which to insert major ticks

    yMajorTicks : list of float
        List of axial position at which to insert major ticks

    legendsLabels : list of str
        Labels to used in the plot legend

    Returns
    -------
    metadata : dict
        Dictionary with all plot metadata information
    """
    metadata = {}

    metadata["title"] = title
    metadata["xlabel"] = xLabel
    metadata["ylabel"] = yLabel
    metadata["xMajorTicks"] = xMajorTicks
    metadata["yMajorTicks"] = yMajorTicks
    metadata["legendLabels"] = legendLabels

    return metadata


def plotAxialProfile(zVals, dataVals, fName, metadata, nPlot=1, yLog=False):
    """
    Plot the axial profile of quantity zVals.

    Parameters
    ----------
    zVals: list of float
        Axial position of the quantity to be plotted

    dataVals: list of float
        Axial quantity to be plotted

    fName: str
        The file name for the plot image file.

    metadata : bool
        Metadata (title, labels, legends, ticks)

    nPlot: int
        Number of plots to be generated

    yLog: bool
        Boolean flag indicating that y-axis is to be plotted on a log scale.
    """
    plt.figure(figsize=(15, 10))

    plt.xlabel(metadata["xlabel"])
    plt.ylabel(metadata["ylabel"])
    plt.title(metadata["title"])
    if metadata["legendLabels"]:
        plt.legend(metadata["legendLabels"], loc=1, fontsize="small")

    ax = plt.gca()

    if yLog:  # plot the axial profiles on a log scale
        dataVals = np.log10(abs(dataVals))

    if nPlot > 1:
        colormap = colormaps["jet"]
        norm = mpltcolors.Normalize(0, nPlot - 1)

        # alternate between line styles to help distinguish neighboring groups (close on the color map)
        lineTypes = ["", ":", "--", "-."]
        nLineTypes = len(lineTypes)
        for n in range(nPlot):
            # reverse order for color map, so high E is red and low E is blue
            n_ = nPlot - n - 1
            color = colormap(norm(n_))
            lineTypeIndex = int(math.fmod(n, nLineTypes))
            plt.plot(zVals, dataVals[:, n], lineTypes[lineTypeIndex], color=color)
    else:
        plt.plot(zVals, dataVals)

    ax.autoscale_view()

    if metadata["xMajorTicks"]:
        ax.set_xticks(metadata["xMajorTicks"])
        ax.set_xticklabels([str(int(x)) for x in metadata["xMajorTicks"]], fontsize=12)

    if metadata["yMajorTicks"]:
        ax.set_xticks(metadata["yMajorTicks"])
        ax.set_xticklabels([str(int(x)) for x in metadata["yMajorTicks"]], fontsize=12)

    ax.xaxis.grid()
    ax.yaxis.grid()

    plt.savefig(fName)
    plt.close()
