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
This module performs some file manipulations, cleanups, state loads, etc.

It's a bit of a catch-all interface, and it's name is admittedly not very descriptive.
"""

import glob
import os
import re
import itertools

from armi import context
from armi import interfaces
from armi import runLog
from armi import utils
from armi.utils import pathTools
from armi import operators
from armi.utils.customExceptions import InputError
from armi.bookkeeping.db.database3 import Database3


ORDER = interfaces.STACK_ORDER.PREPROCESSING


def describeInterfaces(_cs):
    """Function for exposing interface(s) to other code"""
    return (MainInterface, {"reverseAtEOL": True})


class MainInterface(interfaces.Interface):
    """
    Do some basic manipulations, calls, Instantiates the databse.

    Notes
    -----
    Interacts early so that the database is accessible as soon as possible in the run.
    The database interfaces interacts near the end of the interface stack, but the main
    interface interacts first.
    """

    name = "main"

    def interactBOL(self):
        interfaces.Interface.interactBOL(self)
        self._activateDB()
        self._moveFiles()

    def _activateDB(self):
        """
        Instantiate the database state.

        Notes
        -----
        This happens here rather than on the database interface, as the database
        interacts near the end of the stack. Some interactBOL methods may be
        dependent on having data in the database, such as calls to history tracker
        during a restart run.
        """
        dbi = self.o.getInterface("database")
        if not dbi.enabled():
            return
        dbi.initDB()
        if (
            self.cs["loadStyle"] != "fromInput"
            and self.cs["runType"] != operators.RunTypes.SNAPSHOTS
        ):
            # load case before going forward with normal cycle
            runLog.important("MainInterface loading from DB")

            # Load the database from the point just before start cycle and start node
            # as the run will continue at the begining of start cycle and start node,
            # and the database contains the values from the run at the end of the
            # interface stack, which are what the start start cycle and start node
            # should begin with.

            # NOTE: this should be the responsibility of the database, but cannot
            # because the Database is last in the stack and the MainInterface is
            # first
            dbi.prepRestartRun()
            self.r.p.cycle = self.cs["startCycle"]
            self.r.p.timeNode = self.cs["startNode"]

    def _moveFiles(self):
        # check for orificed flow bounds files. These will often be named based on the
        # case that this one is dependent upon, but not always. For example, testSassys
        # is dependent on the safety case but requires physics bounds files.  now copy
        # the files over
        copyFilesFrom = [
            filePath
            for possiblePat in self.cs["copyFilesFrom"]
            for filePath in glob.glob(possiblePat)
        ]
        copyFilesTo = self.cs["copyFilesTo"]

        if len(copyFilesTo) in (len(copyFilesFrom), 0, 1):
            # if any files to copy, then use the first as the default, i.e. len() == 1,
            # otherwise assume '.'
            default = copyFilesTo[0] if any(copyFilesTo) else "."
            for filename, dest in itertools.zip_longest(
                copyFilesFrom, copyFilesTo, fillvalue=default
            ):
                pathTools.copyOrWarn("copyFilesFrom", filename, dest)
        else:
            runLog.error(
                "cs['copyFilesTo'] must either be length 1, 0, or have the same number of entries as "
                "cs['copyFilesFrom']. Actual values:\n"
                "    copyFilesTo   : {}\n"
                "    copyFilesFrom : {}".format(copyFilesTo, copyFilesFrom)
            )
            raise InputError("Failed to process copyFilesTo/copyFilesFrom")

    def interactBOC(self, cycle=None):
        r"""typically the first interface to interact beginning of cycle."""

        runLog.important("Beginning of Cycle {0}".format(cycle))
        runLog.LOG.clearSingleWarnings()

        if self.cs["reallySmallRun"]:
            self.cleanLastCycleFiles()

    def interactEveryNode(self, cycle, node):
        """Loads from db if necessary."""
        if self.cs["loadStyle"] == "fromDB" and self.cs["loadFromDBEveryNode"]:
            if cycle == 0 and node == 0:
                # skip at BOL because interactBOL handled it.
                pass
            else:
                with Database3(self.cs["reloadDBName"], "r") as db:
                    r = db.load(cycle, node, self.cs, self.r.blueprints, self.r.geom)

                self.o.reattach(r, self.cs)

    def interactEOL(self):
        if self.cs["smallRun"]:
            # successful run with smallRun activated. Clean things up.
            self.cleanARMIFiles()
        runLog.warningReport()

    def cleanARMIFiles(self):
        r"""delete ARMI run files like MC**2 and REBUS inputs/outputs. Useful
        if running a clean job that doesn't require restarts."""
        runLog.important("Cleaning ARMI files due to smallRun option")
        for fileName in os.listdir(os.getcwd()):
            # clean MC**2 and REBUS inputs and outputs
            for candidate in [".BCD", ".inp", ".out", "ISOTXS-"]:
                if candidate in fileName:
                    if ".htos.out" in fileName:
                        continue
                    if "sassys.inp" in fileName:
                        continue

                    os.remove(fileName)

            if re.search("ISO..F?$", fileName):
                # clean intermediate XS
                os.remove(fileName)

        for snapText in self.cs["dumpSnapshot"]:
            # snapText is a CCCNNN with C=cycle and N=node
            cycle = int(snapText[0:3])
            node = int(snapText[3:])
            newFolder = "snapShot{0}_{1}".format(cycle, node)
            utils.pathTools.cleanPath(newFolder, context.MPI_RANK)

        # delete database if it's SQLlite
        # no need to delete because the database won't have copied it back if using fastpath.

        # clean temp directories.
        if os.path.exists("shuffleBranches"):
            utils.pathTools.cleanPath("shuffleBranches", context.MPI_RANK)
        if os.path.exists("failedRuns"):
            utils.pathTools.cleanPath("failedRuns", context.MPI_RANK)

    # pylint: disable=no-self-use
    def cleanLastCycleFiles(self):
        r"""Delete ARMI files from previous cycle that aren't necessary for the next cycle.
        Unless you're doing reloads, of course."""
        runLog.important("Cleaning ARMI files due to reallySmallRun option")
        for fileName in os.listdir(os.getcwd()):
            # clean MC**2 and REBUS inputs and outputs
            for candidate in [".BCD", ".inp", ".out", "ISOTXS-"]:
                if candidate in fileName:
                    # Do not remove .htos.out files.
                    if ".htos.out" in fileName:
                        continue
                    if re.search(r"mcc[A-Z0-9]+\.inp", fileName):
                        continue
                    # don't remove mccIA1.inp stuff in case we go out of a burnup bound.
                    try:
                        os.remove(fileName)
                    except OSError:
                        runLog.warning(
                            "Error removing file {0} during cleanup. It is still in use,"
                            " probably".format(fileName)
                        )
