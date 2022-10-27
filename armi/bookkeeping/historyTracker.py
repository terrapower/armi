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
from typing import Tuple

import tabulate

from armi import interfaces
from armi import runLog
from armi import operators
from armi.reactor.flags import Flags
from armi.reactor import grids

ORDER = 2 * interfaces.STACK_ORDER.BEFORE + interfaces.STACK_ORDER.BOOKKEEPING


def describeInterfaces(cs):
    """Function for exposing interface(s) to other code"""
    if cs["runType"] not in (operators.RunTypes.EQUILIBRIUM):
        klass = HistoryTrackerInterface
        return (klass, {})

    return None


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
        """Get a representative fuel block from an assembly."""
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
