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
The MPI-aware variant of the standard ARMI operator.

See :py:class:`~armi.operators.operator.Operator` for the parent class.

This sets up the main Operator on the master MPI node and initializes worker
processes on all other MPI nodes. At certain points in the run, particular interfaces
might call into action all the workers. For example, a depletion or
subchannel T/H module may ask the MPI pool to perform a few hundred
independent physics calculations in parallel. In many cases, this can
speed up the overall execution of an analysis manyfold, if a big enough
computer or computer cluster is available. 

Notes
-----
This is not *yet* smart enough to use shared memory when the MPI
tasks are on the same machine. Everything goes through MPI. This can 
be optimized as needed.
"""
import time
import re
import os
import gc

import armi
from armi.operators.operator import Operator
from armi import mpiActions
from armi import runLog
from armi.bookkeeping import memoryProfiler
from armi.reactor import reactors
from armi.reactor import assemblies
from armi import settings


class OperatorMPI(Operator):
    """MPI-aware Operator."""

    def __init__(self, cs):
        runLog.LOG.startLog(cs.caseTitle)
        try:
            Operator.__init__(self, cs)
        except:
            # kill the workers too so everything dies.
            runLog.important("Master node failed on init. Quitting.")
            if armi.MPI_COMM:  # else it's a single cpu case.
                armi.MPI_COMM.bcast("quit", root=0)
            raise

    def operate(self):
        """
        Operate method for all nodes.

        Calls _mainOperate or workerOperate depending on which MPI rank we are, and
        handles errors.
        """
        runLog.debug("OperatorMPI.operate")
        if armi.MPI_RANK == 0:
            # this is the master
            try:
                # run the regular old operate function
                Operator.operate(self)
                runLog.important(time.ctime())
            except Exception as ee:
                runLog.error(
                    "Error in Master Node. Check STDERR for a traceback.\n{}".format(ee)
                )
                raise
            finally:
                if armi.MPI_SIZE > 0:
                    runLog.important(
                        "Stopping all MPI worker nodes and cleaning temps."
                    )
                    armi.MPI_COMM.bcast(
                        "quit", root=0
                    )  # send the quit command to the workers.
                    runLog.debug("Waiting for all nodes to close down")
                    armi.MPI_COMM.bcast(
                        "finished", root=0
                    )  # wait until they're done cleaning up.
                    runLog.important("All worker nodes stopped.")
                time.sleep(
                    1
                )  # even though we waited, still need more time to close stdout.
                runLog.debug("Main operate finished")
                runLog.LOG.close()  # concatenate all logs.
        else:
            try:
                self.workerOperate()
            except:
                # grab the final command
                runLog.warning(
                    "An error has occurred in one of the worker nodes. See STDERR for traceback."
                )
                # bcasting quit won't work if the main is sitting around waiting for a
                # different bcast or gather.
                runLog.debug("Worker failed")
                runLog.LOG.close()
                raise

    def workerOperate(self):
        """
        The main loop on any worker MPI nodes.

        Notes
        -----
        This method is what worker nodes are in while they wait for instructions from
        the master node in a parallel run. The nodes will sit, waiting for a "worker
        command". When this comes (from a bcast from the master), a set of if statements
        are evaluated, with specific behaviors defined for each command. If the operator
        doesn't understand the command, it loops through the interface stack to see if
        any of the interfaces understand it.

        Originally, "magic strings" were broadcast, which were handled either here or in
        one of the interfaces' ``workerOperate`` methods. Since then, the
        :py:mod:`~armi.mpiActions` system has been devised which just broadcasts
        ``MpiAction`` objects. Both methods are still supported.

        See Also
        --------
        armi.mpiActions : MpiAction information
        armi.interfaces.workerOperate : interface-level handling of worker commands.

        """
        while True:
            # sit around waiting for a command from the master
            runLog.extra("Node {0} ready and waiting".format(armi.MPI_RANK))
            cmd = armi.MPI_COMM.bcast(None, root=0)
            runLog.extra("worker received command {0}".format(cmd))
            # got a command. go use it.
            if isinstance(cmd, mpiActions.MpiAction):
                cmd.invoke(self, self.r, self.cs)
            elif cmd == "quit":
                self.workerQuit()
                break  # If this break is removed, the program will remain in the while loop forever.
            elif cmd == "finished":
                runLog.warning(
                    "Received unexpected FINISHED command. Usually a QUIT command precedes this. "
                    "Skipping cleanup of temporary files."
                )
                break
            elif cmd == "sync":
                # wait around for a sync
                runLog.debug("Worker syncing")
                note = armi.MPI_COMM.bcast("wait", root=0)
                if note != "wait":
                    raise RuntimeError('did not get "wait". Got {0}'.format(note))
            else:
                # we don't understand the command on our own. check the interfaces
                # this allows all interfaces to have their own custom operation code.
                handled = False
                for i in self.interfaces:
                    handled = i.workerOperate(cmd)
                    if handled:
                        break
                if not handled:
                    if armi.MPI_RANK == 0:
                        print("Interfaces" + str(self.interfaces))
                    runLog.error(
                        "No interface understood worker command {0}\n check stdout for err\n"
                        "available interfaces:\n  {1}".format(
                            cmd,
                            "\n  ".join(
                                "name:{} typeName:{} {}".format(i.name, i.function, i)
                                for i in self.interfaces
                            ),
                        )
                    )
                    raise RuntimeError(
                        "Failed to delegate worker command {} to an interface.".format(
                            cmd
                        )
                    )

            if self._workersShouldResetAfter(cmd):
                # clear out the reactor on the workers to start anew.
                # Note: This should build empty non-core systems too.
                xsGroups = self.getInterface("xsGroups")
                if xsGroups:
                    xsGroups.clearRepresentativeBlocks()
                cs = settings.getMasterCs()
                bp = self.r.blueprints
                spatialGrid = self.r.core.spatialGrid
                self.detach()
                self.r = reactors.Reactor(cs.caseTitle, bp)
                core = reactors.Core("Core")
                self.r.add(core)
                core.spatialGrid = spatialGrid
                self.reattach(self.r, cs)

            # might be an mpi action which has a reactor and everything, preventing
            # garbage collection
            del cmd
            gc.collect()

    @staticmethod
    def _workersShouldResetAfter(cmd):
        """
        Figure out when to reset the reactor on workers after an mpi action.

        This only resets the reactor... not the interfaces.

        * crWorth runs multiple passes often so we need to maintain the state.
        * Memory profiling is small enough that we don't want to reset
        * distributing state would be undone by this so we don't want that.
        * Depletion matrices are supposed to stick around for predictor-corrector
          (especially in equilibrium)

        """
        shouldReset = True  # default
        if isinstance(cmd, str):
            for whiteListed in ["crWorth-"]:
                if whiteListed in cmd:
                    shouldReset = False
                    break
        else:
            from terrapower.physics.neutronics.reactivityCoefficients import (
                rxCoeffAnalyzers,
            )
            from terrapower.physics.neutronics.mc2 import mc2ExecutionAgents

            whiteListed = (
                mpiActions.DistributeStateAction,
                memoryProfiler.PrintSystemMemoryUsageAction,
                memoryProfiler.ProfileMemoryUsageAction,
                mpiActions.DistributionAction,
                rxCoeffAnalyzers.RxCoeffAnalyzer,
                mc2ExecutionAgents._Mc2ExecutionAgent,  # pylint: disable=protected-access
            )
            shouldReset = not isinstance(cmd, whiteListed)
        return shouldReset

    @staticmethod
    def workerQuit():
        runLog.debug("Worker ending")
        runLog.LOG.close()  # no more messages.
        armi.MPI_COMM.bcast(
            "finished", root=0
        )  # wait until all workers are closed so we can delete them.

    def collapseAllStderrs(self):
        """Takes all the individual stderr files from each processor and arranges them nicely into one file"""
        stderrFiles = []
        for fName in os.listdir("."):
            match = re.search(r"_(\d\d\d\d)\.stderr", fName)
            if match:
                stderrFiles.append((match.group(1), fName))
        stderrFiles.sort()

        stderr = open("{0}w.stderr".format(self.cs.caseTitle), "w")
        for cpu, fName in stderrFiles:
            f = open(fName)
            stderr.write("Processor {0}\n".format(cpu))
            stderr.write(f.read())
            stderr.write("\n")
            f.close()
        stderr.close()
