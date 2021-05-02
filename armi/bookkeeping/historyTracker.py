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
The History Tracker is a bookkeeping interface that accesses and reports time-dependent state
information from the database.

At the end of a run, these write text files to
show the histories for various follow-on mechanical analysis,
fuel performance analysis, etc.

Other interfaces may find this useful as well, to get an assembly history
for fuel performance analysis, etc. This is particularly useful in equilibrium runs,
where the ``EqHistoryTrackerInterface`` will unravel the full history from a single
equilibrium cycle.

Getting history information
---------------------------
Loop over blocks, keys, and timesteps of interest and use commands like this::

    history.getBlockHistoryVal(armiBlock.getName(), key, ts)

Using the database-based history trackers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
You can pre-load information before gathering it to get much better performance::

    history.preloadBlockHistoryVals(blockNames, historyKeys, timeSteps)

This is essential for performance when history information is going to be accessed
in loops over assemblies or blocks. Reading each param directly from the database
individually in loops is paralyzingly slow.

Specifying parameters to add to the EOL history report
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
To add state parameters to the list of things that get their history reported, you need to define an interface
method called `getHistoryParams`. It should return a list of block parameters that will become available. For example::

    def getHistoryParams(self):
        return ['flux', 'percentBu']

When you'd like to access history information, you need to grab the history interface. The history interfaces is
present by default in your interface stack. To get it, just call::

    history = self.getInterface('history')

Now you can do a few things, such as::

    # get some info about what's stored in the history
    assemsWithHistory = history.getDetailAssemblies()
    timeStepsAvailable = history.getTimeIndices()

    # now go out and get some time-dependent block params:
    fluxAtTimeStep3 = history.getBlockHistoryVal('B1003A', 'flux', 3)

Specifying blocks and assemblies to track
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
See :ref:`detail-assems`.

"""
import re
import os
from collections import OrderedDict
from typing import Tuple

import numpy
from matplotlib import pyplot
import tabulate

from armi import interfaces
import armi.runLog as runLog
from armi import utils
from armi import operators
from armi.utils import textProcessors
from armi.reactor.flags import Flags
from armi.reactor import grids

ORDER = 2 * interfaces.STACK_ORDER.BEFORE + interfaces.STACK_ORDER.BOOKKEEPING


def describeInterfaces(cs):
    """Function for exposing interface(s) to other code"""
    if cs["runType"] not in (operators.RunTypes.EQUILIBRIUM):
        klass = HistoryTrackerInterface
        return (klass, {})


class HistoryTrackerInterface(interfaces.Interface):
    """
    Makes reports of the state that individual assemblies encounter.

    Attributes
    ----------
    detailAssemblyNames : list
        List of detail assembly names in the reactor

    time : list
        list of reactor time in years

    """

    name = "history"

    def __init__(self, r, cs):
        """
        HistoryTracker that uses the database to look up parameter history rather than storing them in memory.

        Warning
        -------
        If the current timestep history is requested and the database has not yet
        been written this timestep, the current value of the requested parameter is
        provided. It is possible that this is not the value that will be written to
        the database during this time step since many interfaces that change
        parameters  may interact between this call and the database write.
        """
        interfaces.Interface.__init__(self, r, cs)
        self.detailAssemblyNames = []
        self.time = []  # time in years
        self.fullCoreLocations = {}
        self.xsHistory = {}
        self._preloadedBlockHistory = None

    def interactBOL(self):
        self.addDetailAssembliesBOL()

    def interactBOC(self, cycle=None):
        """Look for any new assemblies that are asked for and add them to tracking."""
        self.addDetailAssemsByAssemNums()
        if self.cs["detailAllAssems"]:
            self.addAllFuelAssems()

    def interactEOL(self):
        """Generate the history reports."""
        self._writeDetailAssemblyHistories()
        self.printFullCoreLocations()

    def addDetailAssembliesBOL(self):
        """
        Find and activate assemblies that the user requested detailed treatment of.
        """
        if self.cs["detailAssemLocationsBOL"]:
            for locLabel in self.cs["detailAssemLocationsBOL"]:
                ring, pos, _axial = grids.locatorLabelToIndices(locLabel)
                i, j = self.r.core.spatialGrid.getIndicesFromRingAndPos(ring, pos)
                aLoc = self.r.core.spatialGrid[i, j, 0]
                try:
                    a = self.r.core.childrenByLocator[aLoc]
                except KeyError:
                    runLog.error(
                        "Detail assembly in location {} (requested via "
                        "`detailAssemLocationsBOL`) is not in core. "
                        "Update settings.".format(locLabel)
                    )
                    raise
                self.addDetailAssembly(a)

        if self.cs["detailAllAssems"]:
            self.addAllFuelAssems()

        # This also gets called at BOC but we still
        # do it here for operators that do not call BOC.
        self.addDetailAssemsByAssemNums()

    def addAllFuelAssems(self):
        """Add all fuel assems as detail assems."""
        for a in self.r.core:
            if a.hasFlags(Flags.FUEL):
                self.addDetailAssembly(a)

    def addDetailAssemsByAssemNums(self):
        """
        Activate detail assemblies from input based on assembly number.

        This is used to activate detail assembly tracking on assemblies
        that are not present in the core at BOL.

        See Also
        --------
        addDetailAssembliesBOL : Similar but for BOL
        """
        detailAssemNums = self.cs["detailAssemNums"]
        if not detailAssemNums:
            return
        for a in self.r.core:
            thisNum = a.getNum()
            # check for new detail assemblies
            if thisNum in detailAssemNums:
                self.addDetailAssembly(a)

    def _writeDetailAssemblyHistories(self):
        """
        Write data file with assembly histories
        """
        for a in self.getDetailAssemblies():
            self.writeAssemHistory(a)

    def _getAssemHistoryFileName(self, assem):
        return self._getHistoryFileName(assem.getName(), "a")

    def _getBlockHistoryFileName(self, block):
        """Get name for block."""
        return self._getHistoryFileName(
            block.getName() + "{}".format(block.spatialLocator.k), "b"
        )

    def _getLocationHistoryFileName(self, location):
        return self._getHistoryFileName(
            str(location) + "{}".format(location.axial), "l"
        )

    def _getHistoryFileName(self, label, letter):
        return "{0}-{1}-{2}Hist.txt".format(self.cs.caseTitle, label, letter)

    def getTrackedParams(self):
        """
        Give the list of block parameters that are being tracked.
        """
        trackedParams = {"residence", "ztop", "zbottom"}

        # loop through interfaces to allow them to add custom params.
        for i in self.o.getInterfaces():
            for newParam in i.getHistoryParams():
                if newParam not in trackedParams:
                    trackedParams.add(newParam)
        return sorted(trackedParams)

    def addDetailAssembly(self, a):
        """Track the name of assemblies that are flagged for detailed treatment."""
        aName = a.getName()
        if aName not in self.detailAssemblyNames:
            self.detailAssemblyNames.append(aName)

    def getDetailAssemblies(self):
        r"""returns the assemblies that have been signaled as detail assemblies."""
        assems = []
        if not self.detailAssemblyNames:
            runLog.info("No detail assemblies HistoryTrackerInterface")
        for name in self.detailAssemblyNames:
            try:
                assems.append(self.r.core.getAssemblyByName(name))
            except KeyError:
                if name in {a.name for a in self.r.core}:
                    raise Exception("Found it")
                runLog.warning(
                    "Cannot find detail assembly {} in assemblies-by-name lookup table, which has {} entries"
                    "".format(name, len(self.r.core.assembliesByName))
                )
        return assems

    def getDetailBlocks(self):
        """Get all blocks in all detail assemblies."""
        return [block for a in self.getDetailAssemblies() for block in a]

    def filterTimeIndices(self, timeIndices, boc=False, moc=False, eoc=False):
        """Takes a list of time indices and filters them down to boc moc or eoc."""
        filtered = []

        steps = self.cs["burnSteps"] + 1

        for i in timeIndices:
            if boc and i % steps == 0:
                filtered.append(i)
            if moc and i % steps == steps // 2:
                filtered.append(i)
            if eoc and i % steps == steps - 1:
                filtered.append(i)
            if not boc and not moc and not eoc:
                filtered.append(i)

        return filtered

    def getTimeIndices(self, a=None, boc=False, moc=False, eoc=False):
        r"""
        Generate a list of timestep indices where valid history data exist for the given criteria.

        Parameters
        ----------
        a : Assembly, optional
            If given, only generate time indices where the assembly `a` is in the core. Default: All assemblies.

        boc, moc, eoc : bool, optional
            Will return boc/moc/eoc timenodes in every cycle. If any of these are true, allNodes becomes False

        Returns
        -------
        timeIndices : list
            A list of integers where history data exists.

        Examples
        --------
        If there are 5 nodes per cycle (burnSteps = 4),
        0 1 2 3 4 | 5 6 7 8 9 | 10 11 12 13 14 | ...:

        >>> getTimeIndices(moc=True):
        [2, 7, 12, ...]

        Warning
        -------
        This is no longer functional, as much of the old history tracking was based on
        implementation details of the Database, version 2. We now directly support
        history tracking through the Database, version 3. At some point this code should
        be removed.

        See Also
        --------
        getTimeSteps : gets time in years where the assembly is in the core

        """
        timeIndices = []
        coreGrid = self.r.core.spatialGrid
        for globalNode in range(
            utils.getTimeStepNum(self.r.p.cycle, self.r.p.timeNode, self.cs) + 1
        ):
            if a is None:
                timeIndices.append(globalNode)
            else:
                fBlock = a.getFirstBlock(Flags.FUEL)
                if fBlock is None:
                    blockLocationLabel = None
                else:
                    blockLocationLabel = self._blockLocationAtTimenode(
                        fBlock, globalNode
                    )
                    runLog.info(
                        "Location label of {} at timestep {} is {}".format(
                            fBlock, globalNode, blockLocationLabel
                        )
                    )
                # only add this timestep if it's around for this assembly.
                if blockLocationLabel is not None:
                    # this label doesn't actually properly correspond to the block
                    # location label determined by _blockLocationAtTimenode.
                    # blockLocationLabel is supposed to be coming from a previous time
                    # state in the database.
                    if a.spatialLocator.grid is coreGrid:
                        timeIndices.append(globalNode)

        return self.filterTimeIndices(timeIndices, boc, moc, eoc)

    def getBOCEOCTimeIndices(self, assem=None):
        r"""returns a list of time step indices that only include BOC and EOC, no intermediate ones."""
        tIndices = self.getTimeIndices(assem)  # list of times in years
        counter = 0
        filtered = []
        for tIndex in tIndices:
            if counter == 0:
                # boc. add it.
                filtered.append(tIndex)
                counter += 1
            elif counter == self.cs["burnSteps"]:
                # eoc. add it.
                filtered.append(tIndex)
                counter = 0
            else:
                # not boc or eoc. Just increment counter. tick, tick, tick
                counter += 1

        return filtered

    def getAssemParamHistory(self, a, neededParams):
        """Gets the history typically used for the Alchemy Writer

        Returns
        -------
        assemHistory : dict, nested with 3 levels,
            e.g. assemHistory[block][time_step][parameter] = value of parameter at time step on block


        Raises
        ------
        RuntimeError
            When the assembly has no history.
        """
        timeSteps = self.getTimeIndices(a)
        if not timeSteps:
            raise RuntimeError(
                "Time steps empty. Cannot get assembly history for {}".format(a)
            )

        # assemHistory[block][time_step][parameter] = value of parameter at time step on block
        assemHistory = OrderedDict([(block, None) for block in a.getBlocks(Flags.FUEL)])
        for block in assemHistory:
            assemHistory[block] = OrderedDict([(ts, None) for ts in timeSteps])

            for ts in assemHistory[block]:
                assemHistory[block][ts] = OrderedDict(
                    [(param, None) for param in neededParams]
                )

                for param in assemHistory[block][ts]:
                    val = self.getBlockHistoryVal(block.getName(), param, ts)
                    assemHistory[block][ts][param] = val
                assemHistory[block][ts]["location"] = self.getBlockHistoryVal(
                    block.getName(), "loc", ts
                )

        return assemHistory

    def writeAssemHistory(self, a, fName=""):
        """Write the assembly history report to a text file."""
        fName = fName or self._getAssemHistoryFileName(a)
        dbi = self.getInterface("database")
        times = dbi.getHistory(self.r, ["time"])["time"]

        with open(fName, "w") as out:
            # ts is a tuple, remove the spaces from the string representation so it is easy to load
            # into a spreadsheet or whatever
            headers = [str(ts).replace(" ", "") for ts in times.keys()]
            out.write(
                tabulate.tabulate(
                    headers=headers,
                    tabular_data=(times.values(),),
                    tablefmt="plain",
                    floatfmt="11.5E",
                )
            )
            out.write("\n")

            params = self.getTrackedParams()
            blocks = [
                b for bi, b in enumerate(a) if bi not in self.cs["stationaryBlocks"]
            ]
            blockHistories = dbi.getHistories(blocks, params)

            for param in params:
                out.write("\n\nkey: {0}\n".format(param))

                data = [blockHistories[b][param].values() for b in blocks]
                out.write(tabulate.tabulate(data, tablefmt="plain", floatfmt="11.5E"))
                out.write("\n")

            # loc is a tuple, remove the spaces from the string representation so it is easy to load
            # into a spreadsheet or whatever
            location = [
                str(loc).replace(" ", "")
                for loc in dbi.getHistory(a, ["location"])["location"].values()
            ]
            out.write("\n\nkey: location\n")
            out.write(tabulate.tabulate((location,), tablefmt="plain"))
            out.write("\n\n\n")

            headers = "EOL bottom top center".split()
            data = [("", b.p.zbottom, b.p.ztop, b.p.z) for b in blocks]
            out.write(
                tabulate.tabulate(
                    data, headers=headers, tablefmt="plain", floatfmt="10.3f"
                )
            )

            out.write("\n\n\nAssembly info\n")
            out.write("{0} {1}\n".format(a.getName(), a.getType()))
            for b in blocks:
                out.write('"{}" {} {}\n'.format(b.getType(), b.p.xsType, b.p.buGroup))

    def printFullCoreLocations(self):
        """
        Print a report showing the locations of each assembly as functions of time.

        This is useful for third-party follow-on analysis of fuel management.
        """
        aNameList = []  # NWT: Have to read this from the DB.

        ofile = open(self.cs.caseTitle + ".locationHistory.txt", "w")  # MORE data files
        ofile.write(
            " ".join(
                ["Assem"]
                + ["{:5d}".format(c) for c in range(self.cs["nCycles"])]
                + ["\n"]
            )
        )

        for aName in aNameList:
            # print the assembly number and then all the locations it was ever in.
            line = [aName[1:] + " "]
            for cycle in range(self.cs["nCycles"]):
                row, loc = self.fullCoreLocations.get((aName, cycle), (None, None))
                if row:
                    val1 = "{0:02d}{1:03d}".format(row, loc)
                else:
                    # none returned
                    val1 = "     "
                line.append(val1)
            line.append("\n")
            ofile.write(" ".join(line))
        ofile.close()

    def preloadBlockHistoryVals(self, names, keys, timesteps):
        """
        Pre-load block data so it can be more quickly accessed in the future.

        Notes
        -----
        Pre-loading has value because the database is organized in a fashion that is
        easy/inexpensive to look up data for many of time steps simultaneously. These
        can then be stored and provided when the specific timestep is requested. The
        method ``getBlockHistoryVal`` still looks at the database if the preloaded
        values don't have the needed data, so the same results should be given if this
        method is not called.
        """
        try:
            dbi = self.getInterface("database")
            blocks = [self.r.core.getBlockByName(name) for name in names]
            # weird special stuff for loc, just leave it be.
            keys = [key for key in keys if key != "loc"]
            data = dbi.getHistories(blocks, keys, timesteps)
            self._preloadedBlockHistory = data
        except:  # pylint: disable=bare-except
            # fails during the beginning of standard runs, but that's ok
            runLog.info(
                f"Unable to pre-load block history values due to error:"
                "\n{traceback.format_exc()}"
            )
            self.unloadBlockHistoryVals()

    def unloadBlockHistoryVals(self):
        """Remove all cached db reads."""
        self._preloadedBlockHistory = None

    def getBlockHistoryVal(self, name: str, paramName: str, ts: Tuple[int, int]):
        """
        Use the database interface to return the parameter values for the supplied block
        names, and timesteps.

        Notes
        -----
        If the current timestep history is requested and the database has not yet
        been written this timestep, the current value of the requested parameter is
        returned.

        Parameters
        ----------
        name
            name of block
        paramName
            parameter keys of interest
        ts
            cycle and node from which to load data

        Raises
        ------
        KeyError
            When param not found in database.
        """
        block = self.r.core.getBlockByName(name)

        if paramName == "loc":
            # special behavior for location param.
            return self._blockLocationAtTimenode(block, ts)

        if self._isCurrentTimeStep(ts) and not self._databaseHasDataForTimeStep(ts):
            # current timenode may not have been written to the DB. Use the current
            # value in the param system.  works for fuel performance, for some params,
            # e.g. burnup, dpa.
            return block.p[paramName]

        try:
            val = self._preloadedBlockHistory[block][paramName][ts]
        # not in preloaded or preloaded failed
        except (TypeError, ValueError, KeyError, IndexError):
            dbi = self.getInterface("database")
            try:
                data = dbi.database.getHistory(block, [paramName], [ts])
                val = data[paramName][ts]
            except KeyError:
                runLog.error(
                    "No value in DB. param name: {} requested index: {}"
                    "".format(paramName, ts)
                )
                raise
        return val

    def _isCurrentTimeStep(self, ts: Tuple[int, int]):
        """Return True if the timestep requested is the current time step."""
        return ts == (self.r.p.cycle, self.r.p.timeNode)

    def _databaseHasDataForTimeStep(self, ts):
        """Return True if the database has data for the requested time step."""
        dbi = self.getInterface("database")
        return ts in dbi.database.genTimeSteps()

    def getTimeSteps(self, a=None):
        r"""
        return list of time steps values (in years) that are available.

        Parameters
        ----------
        a : Assembly object, optional
            An assembly object designated a detail assem. If passed, only timesteps
            where this assembly is in the core will be tracked.

        Returns
        -------
        timeSteps : list
            times in years that are available in the history

        See Also
        --------
        getTimeIndices : gets indices where an assembly is in the core
        """
        dbi = self.getInterface("database")
        timeInYears = dbi.getHistory(self.r, ["time"])["time"]

        # remove the time step info. Clients don't want it
        timeInYears = [t[1] for t in timeInYears]
        if a:
            b = self._getBlockInAssembly(a)
            ids = dbi.getHistory(["id"])["id"]
            timeInYears = [time for time, ids in zip(timeInYears, ids) if b.p.id in ids]
        return timeInYears

    @staticmethod
    def _getBlockInAssembly(a):
        """Get a representative block from an assembly."""
        b = a.getFirstBlock(Flags.FUEL)
        if not b:
            # there is a problem, it doesn't look like we have a fueled assembly
            # but that is all we track... what is it? Throw an error
            runLog.warning("Assembly {} does not contain fuel".format(a))
            for b in a:
                runLog.warning("Block {}".format(b))
            raise RuntimeError(
                "A tracked assembly does not contain fuel and has caused this error, see the details in stdout."
            )
        return b

    def _blockLocationAtTimenode(self, block, timeNode):
        """
        Find block location label at a specific timenode.

        Warning
        -------
        This fuction no longer functions, as it relies on implmentation details of
        Database version 2, which is no longer used. Retaining for historical purposes,
        but this should be removed soon.
        """
        dbi = self.getInterface("database")
        ids = dbi.database.readBlockParam("id", timeNode)
        locs = dbi.database.lookupGeometry()
        if ids is None:
            return None
        ids = ids.tolist()
        try:
            blockIndex = ids.index(block.p.id)
            return locs[blockIndex]
        except ValueError:
            return None


class HistoryFile:
    r"""
    A general history file that contains the parameter history of an object.

    The object may be a block or assembly. This tracks them through time

    Originally, these files were just created by the history interface,
    but it became necessary to read them and post-process them for statistical needs
    (stats for individual assembly types) so it became an object

    They were typically named A234-ahist.txt or so.
    """


class AssemblyHistory(HistoryFile):
    """History report of a single assembly."""

    def __repr__(self):
        return "<AssemHistory {0}>".format(self.assemName)

    def read(self, fName):
        r"""
        Reads an assembly history file into memory.

        Parameters
        ----------
        fName : str
            The filename to read

        Creates a blockStack list where each entry is a dictionary of [param,ts]=val maps

        """

        f = textProcessors.TextProcessor(fName)
        timeSteps = map(int, f.f.next().split())  # first line is timestep integers
        _timeYears = map(float, f.f.next().split())  # second line is times in years

        # now there is a loop over all params
        blockStack = (
            []
        )  # will assign to block names once they are read in (at end of file)
        while True:
            # expect a line like: "key: burnup"
            line = f.fsearch("key:")
            paramName = line.split()[1]  # pylint: disable=no-member
            if paramName == "location":
                operation = str
            else:
                operation = float
            # expect values for each timestep on the next few lines
            for line in f.f:
                line = line.strip()
                # read arbitrary number of blocks
                if (
                    not line or "EOL bottom" in line
                ):  # detect axial info to(b/c we used to not have blank lines)
                    # end on blank line
                    break
                vals = map(operation, line.split())
                blockVals = {}
                for ts, val in zip(timeSteps, vals):
                    blockVals[paramName, ts] = val
                blockStack.append(blockVals)

            if paramName == "location":
                # flags the end of the params.
                break

        # skip the EOL axial information (for now)
        f.fsearch("Assembly info")

        assemblyInfoLine = next(f.f)
        assemblyInfo = assemblyInfoLine.split()
        self.assemName = assemblyInfo[0]
        if len(assemblyInfo) > 1:
            self.assemType = " ".join(assemblyInfo[1:]).lower()
        else:
            self.assemType = None

        blockTypes = []
        for line in f.f:
            match = re.search(r'"(.+)"\s(\S)\s(\S)', line)
            if match:
                blockTypes.append(match.group(1))
        f.f.close()

        self.blockStack = blockStack

    def readFromArmi(self, blockName, historyInterface):
        r"""
        Loads up a working AssemblyHistory object from the history interface
        """
        pass

    def computeBounds(self):
        r"""
        Finds the min and max values of all params in this assembly history

        Returns
        -------
        mins : dict
            Keys are param names, vals are minimum values for that param
        maxes : dict
            Keys are param names, vals are maximum values for that param

        """

        mins = {}
        maxes = {}
        for blockVals in self.blockStack:
            for (paramName, _ts), val in blockVals.items():
                if val < mins.get(paramName, float("inf")):
                    mins[paramName] = val
                if val > maxes.get(paramName, -float("inf")):
                    maxes[paramName] = val

        return mins, maxes


class HistoryProcessor:
    r"""
    Processes stats on a bunch of assembly history files

    Original use: computing ranges of operation for testing program
    """

    @staticmethod
    def findHistoryFiles(path=None, title=None):
        r"""
        Finds a list of all history files in a directory

        Parameters
        ----------
        path : str, optional
            The path to look for. Default cwd.

        title : str, optional
            The case title to limit too. Default: all

        Returns
        -------
        fileList : list
            List of file names of assembly history files.

        """
        if path is None:
            path = os.getcwd()

        fileList = []
        for fName in os.listdir(path):
            if title and title not in fName:
                continue
            if "aHist" in fName:
                fileList.append(fName)

        return fileList

    def readAllAssemHistories(self, path=None, title=None):
        r"""
        Parameters
        ----------
        path : str, optional
            The path to look for. Default cwd.

        title : str, optional
            The case title to limit too. Default: all

        Returns
        -------
        assemHistoryList : list
            List of assembly history objects
        """
        assemHistoryList = []
        fileList = self.findHistoryFiles(path, title)
        for fName in fileList:
            print("reading {0}".format(fName))
            aHist = AssemblyHistory()
            aHist.read(fName)
            assemHistoryList.append(aHist)

        return assemHistoryList

    def printAssemblyStats(
        self, assemTypes=None, path=None, title=None, assemHistoryList=None
    ):
        r"""
        Prints statistical report for assemblies of type assemType

        Parameters
        ----------
        assemType : str or list
            Assembly type e.g. ['LTA fuel','feed fuel']
        path : str, optional
            The path to look for. Default cwd.
        title : str, optional
            The case title to limit too. Default: all
        assemHistoryList : list of processed assembly histories
            Useful for multiple calls
        """

        validHistories = self.getValidHistories(
            assemTypes, path, title, assemHistoryList
        )

        # combine valid histories and print stats for the collection.
        # This will make a historyVals[paramName,aType] dictionary of values
        # organize vals by their block type
        # this loses order and timestep ordering. Just good for min, max, avg, stddev.
        self.historyData = {}
        for aHist in validHistories:
            aType = aHist.assemType
            for blockVals in aHist.blockStack:
                for (paramName, _ts), val in blockVals.items():
                    currentVals = self.historyData.get((paramName, aType), [])
                    currentVals.append(val)
                    if len(currentVals) == 1:
                        # initialize this value
                        self.historyData[(paramName, aType)] = currentVals

        self.locateBoundingHistories()

    def findHistoriesWithHotPICT(
        self,
        assemTypes=None,
        path=None,
        title=None,
        assemHistoryList=None,
        pctBounds=[590, 600, 610, 620],
    ):
        r"""
        Finds assemblies that have a peak 2-sigma PICT>various temperatures

        Parameters
        ----------
        assemType : str or list
            Assembly type e.g. ['LTA fuel','feed fuel']
        path : str, optional
            The path to look for. Default cwd.
        title : str, optional
            The case title to limit too. Default: all
        assemHistoryList : list of processed assembly histories
            Useful for multiple calls
        pctBounds : list, optional
            The temperatures in C to make histograms for.

        Asked for by Bruce for materials testing development in BOR-60. Produces very useful figures
        during post-processing.
        """

        validHistories = self.getValidHistories(
            assemTypes, path, title, assemHistoryList
        )
        if assemTypes is None:
            assemTypes = "All"
        dataSets = []
        for pct in pctBounds:
            aboveThreshold = []
            for aHist in validHistories:
                maxTs = 0
                # find max TS that this assembly encounters
                for blockVals in aHist.blockStack:
                    thisMax = max([ts for _paramName, ts in blockVals.keys()])
                    if thisMax > maxTs:
                        maxTs = thisMax

                numTimesAboveInARow = 0
                numTimeStepsAbove = 0
                maxTimesInARow = 0
                lifeMax = 0
                for ts in range(maxTs + 1):
                    maxPict = 0.0
                    # find maximum pict in assembly
                    for blockVals in aHist.blockStack:
                        pict = blockVals.get(("SC2SigmaCladIDT", ts), None)
                        if pict > maxPict:
                            maxPict = pict

                    if maxPict > pct:
                        numTimesAboveInARow += 1
                        numTimeStepsAbove += 1
                    else:
                        # reset in-a-row counter
                        numTimesAboveInARow = 0

                    # track max number in a row too
                    if numTimesAboveInARow > maxTimesInARow:
                        maxTimesInARow = numTimesAboveInARow

                    if maxPict > lifeMax:
                        lifeMax = maxPict

                # track how many times this assembly was above the threshold
                if numTimeStepsAbove:  # filter out zero entries to allow log plotting.
                    aboveThreshold.append(numTimeStepsAbove)

                print(
                    "{0} was above {3}C {1} times. Max T was {2}C".format(
                        aHist, maxTimesInARow, lifeMax, pct
                    )
                )
            dataSets.append(3 * aboveThreshold)  # multiply by 3 for 1/3 symmetry.

        # eliminate empty datasets.
        filteredSets = []
        filteredBounds = []
        for dataSet, pctBound in zip(dataSets, pctBounds):
            if dataSet:
                filteredSets.append(dataSet)
                filteredBounds.append(pctBound)

        if not any(filteredSets):
            print("No data")
        else:
            savedData = (filteredSets, filteredBounds, assemTypes)
            import pickle

            file = open("saveData.dat", "w")
            pickle.dump(savedData, file)
            file.close()
            self.plotBounds(filteredSets, filteredBounds, assemTypes)

        return validHistories, dataSets

    @staticmethod
    def plotBounds(filteredSets, filteredBounds, assemTypes):
        """
        Plots an incredibly useful figure showing which assemblies have which PICT through the lifetime

        This is done after a run in post-processing for documentation of the case.
        """
        fig, ax = pyplot.subplots()
        ax.hist(
            filteredSets,
            10,
            histtype="barstacked",
            normed=False,
            label=["Above {0}C".format(i) for i in filteredBounds],
            log=True,
        )
        ax.legend()
        ax.set_ylabel("Number of assemblies")
        ax.set_xlabel("Number of timesteps above theshhold")
        ax.set_title(
            "{0} assembly history stats for 2-sigma PICT for TWR-P".format(assemTypes)
        )
        figName = "{0}-assemStats.pdf".format(assemTypes)
        fig.savefig(figName)
        pyplot.close(fig)

    def getValidHistories(self, assemTypes, path, title=None, assemHistoryList=None):
        r"""
        Loads or filters a set of assembly histories to certain assemtypes

        Parameters
        ----------
        assemType : str or list
            Assembly type e.g. ['LTA fuel','feed fuel']
        path : str, optional
            The path to look or. Default cwd.
        title : str, optional
            The case title to limit too. Default: all
        assemHistoryList : list of processed assembly histories
            Useful for multiple calls

        Returns
        -------
        validAssems : list
            The assem histories that match the criteria.
        """
        # process arguments
        if assemTypes and not isinstance(assemTypes, list):
            assemTypes = [assemTypes]
        if not assemHistoryList:
            assemHistoryList = self.readAllAssemHistories(path, title)

        # filter down to have just the assemblies of interest
        validHistories = []
        for aHist in assemHistoryList:
            if not assemTypes:
                validHistories.append(aHist)
            else:
                for validType in assemTypes:
                    if validType in aHist.assemType:
                        validHistories.append(aHist)

        return validHistories

    def locateBoundingHistories(self):
        r"""
        Determines which detail assemblies reach the bounds of each tracked parameter.

        Returns
        -------
        minMax : dict
            Keys are tracked keys, vals are (minV, maxV, avg, std) where
            minV and maxV(value, assembly, timestep) tuples for min and max
            avg is the arithmetic mean and std is the standard deviation for key

        Notes
        -----
        This basically provides bounding values for each tracked parameter
        """
        minMax = {}
        aTypes = []
        params = []
        for (paramName, aType), vals in self.historyData.items():
            # track min and max (value, assembly, timestep) for each key
            # remove zeros and Nones.
            # value is 0. It's debatable whether we want zeros in the average or not.
            # Without excluding the non-fuel assemblies, it weights the average very low.
            # But if you just ignore zeros, you miss the truly zero values (fresh fuel burnup, etc.)
            # Very many min's are zero if we don't ignore so it's not that useful (due to grid plate often)
            allValues = [v for v in vals if v]
            if paramName == "location":
                # skip this. No way to average.
                continue
            if allValues:
                try:
                    minV = min(allValues)
                    maxV = max(allValues)
                    mean = numpy.mean(allValues)
                    std = numpy.std(allValues)
                except:
                    print(allValues)
                    raise
            else:
                # no data. Just zero it out.
                minV = -float("inf")
                maxV = float("inf")
                mean = 0.0
                std = 0.0

            minMax[paramName, aType] = (minV, maxV, mean, std)
            if aType not in aTypes:
                aTypes.append(aType)
            if paramName not in params:
                params.append(paramName)

        params.sort()
        # loop through all aTypes and print tables.
        for aType in aTypes:
            print(aType)
            self.printBoundingHistories(aType, params, minMax)

    @staticmethod
    def printBoundingHistories(aType, params, minMax):
        r"""
        Prints a summary of bounding parameter values for all detail assemblies.

        Parameters
        ----------
        minMax : dict
            Keys are tracked keys, vals are (value, assembly, timestep) tuples for min and max.
        """
        print("Detail History Statistical Summary")
        print(
            "{key:40s} {minV:11s} {maxV:11s}"
            " {mean:11s} {std:11s}"
            "".format(
                key="Key", minV="MinVal", maxV="MaxVal", mean="Mean", std="Std. Dev."
            )
        )

        for key in params:
            minV, maxV, mean, std = minMax[key, aType]
            print(
                "{key:40s} {minV:11.5E}  {maxV:11.5E} "
                "{mean:11.5E} {std:11.5E}"
                "".format(key=key, minV=minV, maxV=maxV, mean=mean, std=std)
            )

    def processAll(self, path, title):
        self.readAllAssemHistories(path, title)
