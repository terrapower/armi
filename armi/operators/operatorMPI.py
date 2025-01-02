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

.. impl:: There is an MPI-aware variant of the ARMI Operator.
    :id: I_ARMI_OPERATOR_MPI
    :implements: R_ARMI_OPERATOR_MPI

    This sets up the main Operator on the primary MPI node and initializes
    worker processes on all other MPI nodes. At certain points in the run,
    particular interfaces might call into action all the workers. For
    example, a depletion or subchannel T/H module may ask the MPI pool to
    perform a few hundred independent physics calculations in parallel. In
    many cases, this can speed up the overall execution of an analysis,
    if a big enough computer or computing cluster is available.

    See :py:class:`~armi.operators.operator.Operator` for the parent class.

Notes
-----
This is not *yet* smart enough to use shared memory when the MPI
tasks are on the same machine. Everything goes through MPI. This can
be optimized as needed.
"""
import gc
import os
import re
import time
import traceback

from armi import context, getPluginManager, mpiActions, runLog
from armi.operators.operator import Operator
from armi.reactor import reactors


class OperatorMPI(Operator):
    """MPI-aware Operator."""

    def __init__(self, cs):
        try:
            Operator.__init__(self, cs)
        except:
            # kill the workers too so everything dies.
            runLog.important("Primary node failed on init. Quitting.")
            if context.MPI_COMM:  # else it's a single cpu case.
                context.MPI_COMM.bcast("quit", root=0)
            raise

    def operate(self):
        """
        Operate method for all nodes.

        Calls _mainOperate or workerOperate depending on which MPI rank we are, and
        handles errors.
        """
        runLog.debug("OperatorMPI.operate")
        if context.MPI_RANK == 0:
            # this is the primary
            try:
                # run the regular old operate function
                Operator.operate(self)
                runLog.important(time.ctime())
            except Exception as ee:
                runLog.error(
                    "Error in Primary Node. Check STDERR for a traceback.\n{}".format(
                        ee
                    )
                )
                raise
            finally:
                if context.MPI_SIZE > 0:
                    runLog.important(
                        "Stopping all MPI worker nodes and cleaning temps."
                    )
                    context.MPI_COMM.bcast(
                        "quit", root=0
                    )  # send the quit command to the workers.
                    runLog.debug("Waiting for all nodes to close down")
                    context.MPI_COMM.bcast(
                        "finished", root=0
                    )  # wait until they're done cleaning up.
                    runLog.important("All worker nodes stopped.")
                time.sleep(
                    1
                )  # even though we waited, still need more time to close stdout.
                runLog.debug("Main operate finished")
                runLog.close()  # concatenate all logs.
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
                traceback.print_exc()
                runLog.debug("Worker failed")
                runLog.close()
                raise

    def workerOperate(self):
        """
        The main loop on any worker MPI nodes.

        Notes
        -----
        This method is what worker nodes are in while they wait for instructions from
        the primary node in a parallel run. The nodes will sit, waiting for a "worker
        command". When this comes (from a bcast from the primary), a set of if statements
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
            # sit around waiting for a command from the primary
            runLog.extra("Node {0} ready and waiting".format(context.MPI_RANK))
            cmd = context.MPI_COMM.bcast(None, root=0)
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
                note = context.MPI_COMM.bcast("wait", root=0)
                if note != "wait":
                    raise RuntimeError('did not get "wait". Got {0}'.format(note))
            elif cmd == "reset":
                runLog.extra("Workers are being reset.")
            else:
                # we don't understand the command on our own. check the interfaces
                # this allows all interfaces to have their own custom operation code.
                handled = False
                for i in self.interfaces:
                    handled = i.workerOperate(cmd)
                    if handled:
                        break
                if not handled:
                    if context.MPI_RANK == 0:
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

            pm = getPluginManager()
            resetFlags = pm.hook.mpiActionRequiresReset(cmd=cmd)
            # only reset if all the plugins agree to reset
            if all(resetFlags) or cmd == "reset":
                self._resetWorker()

            # might be an mpi action which has a reactor and everything, preventing
            # garbage collection
            del cmd
            gc.collect()

    def _finalizeInteract(self):
        """Inherited member called after each interface has completed its interact.

        This will force all the workers to clear their reactor data so that it
        isn't carried around to the next interact.

        Notes
        -----
        This is only called on the root processor. Worker processors will know
        what to do with the "reset" broadcast.
        """
        if context.MPI_SIZE > 1:
            context.MPI_COMM.bcast("reset", root=0)
            runLog.extra("Workers have been reset.")

    def _resetWorker(self):
        """
        Clear out the reactor on the workers to start anew.

        Notes
        -----
        This was made to help minimize the amount of RAM that is used during some
        gigantic long-running cases. Resetting after building copies of reactors
        or transforming their geometry is one approach. We hope to implement
        more efficient solutions in the future.

        .. warning:: This should build empty non-core systems too.
        """
        # Nothing to do if we never had anything
        if self.r is None:
            return

        cs = self.cs
        bp = self.r.blueprints
        spatialGrid = self.r.core.spatialGrid
        spatialGrid.armiObject = None
        xsGroups = self.getInterface("xsGroups")
        if xsGroups:
            xsGroups.clearRepresentativeBlocks()
        self.detach()
        self.r = reactors.Reactor(cs.caseTitle, bp)
        core = reactors.Core("Core")
        self.r.add(core)
        core.spatialGrid = spatialGrid
        core.spatialGrid.armiObject = core
        self.reattach(self.r, cs)

    @staticmethod
    def workerQuit():
        runLog.debug("Worker ending")
        runLog.close()  # no more messages.
        # wait until all workers are closed so we can delete them.
        context.MPI_COMM.bcast("finished", root=0)

    def collapseAllStderrs(self):
        """Takes all the individual stderr files from each processor and arranges them nicely into one file."""
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
