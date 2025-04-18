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

r"""
Interface to help diagnose memory issues during debugging/development.

There are many approaches to memory profiling.

1. You can ask psutil for the memory used by the process from an OS perspective.
This is great for top-down analysis. This module provides printouts
that show info from every process running. This is very fast.

2. You can use ``gc.get_objects()`` to list all objects that the garbage collector is tracking. If you want, you
can filter it down and get the counts and sizes of objects of interest (e.g. all armi objects).

This module has tools to do all of this. It should help you out.

NOTE: Psutil and sys.getsizeof will certainly report slightly different results.

NOTE: In Windows, it seems that even if your garbage is collected, Windows does not de-allocate all the memory.
So if you are a worker and you just got a 2GB reactor but then deleted it, Windows will keep you at 2GB for a while.

See Also
--------
https://pythonhosted.org/psutil/
https://docs.python.org/3/library/gc.html#gc.garbage
"""
import gc
import sys
from os import cpu_count
from typing import Optional

from armi import context, interfaces, mpiActions, runLog
from armi.reactor.composites import ArmiObject
from armi.utils import tabulate
from armi.utils.customExceptions import NonexistentSetting

try:
    # psutil is an optional requirement, since it doesn't support MacOS very well
    import psutil

    _havePsutil = True
except ImportError:
    runLog.warning(
        "Failed to import psutil; MemoryProfiler will not provide meaningful data."
    )
    _havePsutil = False


ORDER = interfaces.STACK_ORDER.POSTPROCESSING
REPORT_COUNT = 100000


def describeInterfaces(cs):
    """Function for exposing interface(s) to other code."""
    return (MemoryProfiler, {})


def getTotalJobMemory(nTasks, cpusPerTask):
    """Function to calculate the total memory of a job. This is a constant during a simulation."""
    cpuPerNode = cpu_count()
    ramPerCpuGB = psutil.virtual_memory().total / (1024**3) / cpuPerNode
    jobMem = nTasks * cpusPerTask * ramPerCpuGB
    return jobMem


def getCurrentMemoryUsage():
    """This scavenges the memory profiler in ARMI to get the current memory usage."""
    memUsageAction = PrintSystemMemoryUsageAction()
    memUsageAction.broadcast()
    smpu = SystemAndProcessMemoryUsage()
    memUsages = memUsageAction.gather(smpu)
    # Grab virtual memory instead of physical. There is a large discrepancy, we will be conservative
    memoryUsageInMB = sum([mu.processVirtualMemoryInMB for mu in memUsages])
    return memoryUsageInMB


class MemoryProfiler(interfaces.Interface):

    name = "memoryProfiler"

    def __init__(self, r, cs):
        interfaces.Interface.__init__(self, r, cs)
        self.sizes = {}

    def interactBOL(self):
        interfaces.Interface.interactBOL(self)
        self.printCurrentMemoryState()
        mpiAction = PrintSystemMemoryUsageAction()
        mpiAction.broadcast().invoke(self.o, self.r, self.cs)
        mpiAction.printUsage("BOL SYS_MEM")

        # so we can debug mem profiler quickly
        if self.cs["debugMem"]:
            mpiAction = ProfileMemoryUsageAction("EveryNode")
            mpiAction.broadcast().invoke(self.o, self.r, self.cs)

    def interactEveryNode(self, cycle, node):
        self.printCurrentMemoryState()

        mp = PrintSystemMemoryUsageAction()
        mp.broadcast()
        mp.invoke(self.o, self.r, self.cs)
        mp.printUsage("c{} n{} SYS_MEM".format(cycle, node))

        self.r.core.p.minProcessMemoryInMB = round(mp.minProcessMemoryInMB * 10) / 10.0
        self.r.core.p.maxProcessMemoryInMB = round(mp.maxProcessMemoryInMB * 10) / 10.0

        if self.cs["debugMem"]:
            mpiAction = ProfileMemoryUsageAction("EveryNode")
            mpiAction.broadcast().invoke(self.o, self.r, self.cs)

    def interactEOL(self):
        """End of life hook. Good place to wrap up or print out summary outputs."""
        if self.cs["debugMem"]:
            mpiAction = ProfileMemoryUsageAction("EOL")
            mpiAction.broadcast().invoke(self.o, self.r, self.cs)

    def printCurrentMemoryState(self):
        """Print the current memory footprint and available memory."""
        try:
            cpusPerTask = self.cs["cpusPerTask"]
        except NonexistentSetting:
            runLog.extra(
                "To view memory consumed, remaining available, and total allocated for a case, "
                "add the setting 'cpusPerTask' to your application."
            )
            return
        nTasks = self.cs["nTasks"]
        totalMemoryInGB = getTotalJobMemory(nTasks, cpusPerTask)
        currentMemoryUsageInGB = getCurrentMemoryUsage() / 1024
        availableMemoryInGB = totalMemoryInGB - currentMemoryUsageInGB
        runLog.info(
            f"Currently using {currentMemoryUsageInGB} GB of memory. "
            f"There is {availableMemoryInGB} GB of memory left. "
            f"There is a total allocation of {totalMemoryInGB} GB."
        )

    def displayMemoryUsage(self, timeDescription):
        r"""
        Print out some information to stdout about the memory usage of ARMI.

        Useful when the debugMem setting is set to True.

        Turn these on as appropriate to find all your problems.
        """
        runLog.important(
            "----- Memory Usage Report at {} -----".format(timeDescription)
        )
        self._printFullMemoryBreakdown(reportSize=self.cs["debugMemSize"])
        self._reactorAssemblyTrackingBreakdown()
        runLog.important(
            "----- End Memory Usage Report at {} -----".format(timeDescription)
        )

    def _reactorAssemblyTrackingBreakdown(self):
        runLog.important("Reactor attribute ArmiObject tracking count")
        for attrName, attrObj in self.r.core.__dict__.items():
            if not attrObj:
                continue

            if isinstance(attrObj, list) and isinstance(attrObj[0], ArmiObject):
                runLog.important(
                    "List {:30s} has {:4d} ArmiObjects".format(attrName, len(attrObj))
                )

            if isinstance(attrObj, dict) and isinstance(
                list(attrObj.values())[0], ArmiObject
            ):
                runLog.important(
                    "Dict {:30s} has {:4d} ArmiObjects".format(attrName, len(attrObj))
                )

        if self.r.excore.get("sfp") is not None:
            runLog.important(
                "SFP has {:4d} ArmiObjects".format(len(self.r.excore["sfp"]))
            )

    def checkForDuplicateObjectsOnArmiModel(self, attrName, refObject):
        """Scans through ARMI model for duplicate objects."""
        if self.r is None:
            return
        uniqueIds = set()
        uniqueObjTypes = set()

        def checkAttr(subObj):
            if getattr(subObj, attrName, refObject) != refObject:
                uniqueIds.add(id(getattr(subObj, attrName)))
                uniqueObjTypes.add(subObj.__class__.__name__)

        for a in self.r.core.getAssemblies(includeAll=True):
            checkAttr(a)
            for b in a:
                checkAttr(b)
                for c in b:
                    checkAttr(c)
                    checkAttr(c.material)

        for i in self.o.getInterfaces():
            checkAttr(i)
            if i.name == "xsGroups":
                for _, block in i.representativeBlocks.items():
                    checkAttr(block)

        if len(uniqueIds) == 0:
            runLog.important("There are no duplicate `.{}` attributes".format(attrName))
        else:
            runLog.error(
                "There are {} unique objects stored as `.{}` attributes!\n"
                "Expected id {}, but got {}.\nExpected object:{}\n"
                "These types of objects had unique attributes: {}".format(
                    len(uniqueIds) + 1,
                    attrName,
                    id(refObject),
                    uniqueIds,
                    refObject,
                    ", ".join(uniqueObjTypes),
                )
            )
            raise RuntimeError

    def _printFullMemoryBreakdown(self, reportSize=True, printReferrers=False):
        """
        looks for any class from any module in the garbage collector and prints their count and size.

        Parameters
        ----------
        reportSize : bool, optional
            calculate size as well as counting individual objects.

        Notes
        -----
        Just because you use startsWith=armi doesn't mean you'll capture all ARMI objects. Some are in lists
        and dictionaries.
        """
        cs = self.cs
        operator = self.o
        reactor = self.r

        if reportSize:
            self.o.detach()

        gc.collect()
        allObjects = gc.get_objects()
        runLog.info("GC returned {} objects".format(len(allObjects)))

        instanceCounters = KlassCounter(reportSize)
        instanceCounters.countObjects(allObjects)

        for counter in sorted(instanceCounters.counters.values()):
            runLog.info(
                "UNIQUE_INSTANCE_COUNT: {:60s} {:10d}     {:10.1f} MB".format(
                    counter.classType.__name__,
                    counter.count,
                    counter.memSize / (1024**2.0),
                )
            )
            if printReferrers and counter.memSize / (1024**2.0) > 100:
                referrers = gc.get_referrers(counter.first)
                runLog.info("          Referrers of first one: ")
                for referrer in referrers:
                    runLog.info("             {}".format(repr(referrer)[:150]))

        runLog.info("gc garbage: {}".format(gc.garbage))
        if printReferrers:
            # if you want more info on the garbage referrers, run this. WARNING, it's generally like 1000000 lines.
            runLog.info("referrers")
            for o in gc.garbage:
                for r in gc.get_referrers(o):
                    runLog.info("ref for {}: {}".format(o, r))

        if reportSize:
            operator.reattach(reactor, cs)

    @staticmethod
    def getReferrers(obj):
        """Print referrers in a useful way (as opposed to gigabytes of text."""
        runLog.info("Printing first 100 character of first 100 referrers")
        for ref in gc.get_referrers(obj)[:100]:
            runLog.important("ref for {}: {}".format(obj, repr(ref)[:100]))


class KlassCounter:
    """
    Helper class, to allow us to count instances of various classes in the
    Python standard library garbage collector (gc).

    Counting can be done simply, or by memory footprint.
    """

    def __init__(self, reportSize):
        self.counters = dict()
        self.reportSize = reportSize
        self.count = 0

    def __getitem__(self, classType):
        if classType not in self.counters:
            self.counters[classType] = InstanceCounter(classType, self.reportSize)
        return self.counters[classType]

    def countObjects(self, ao):
        """
        Recursively find objects inside arbitrarily-deeply-nested containers.

        This is designed to work with the garbage collector, so it focuses on
        objects potentially being held in dict, tuple, list, or sets.
        """
        counter = self[type(ao)]
        if counter.add(ao):
            self.count += 1
            if self.count % REPORT_COUNT == 0:
                runLog.info("Counted {} items".format(self.count))

            if isinstance(ao, dict):
                for k, v in ao.items():
                    self.countObjects(k)
                    self.countObjects(v)
            elif isinstance(ao, (list, tuple, set)):
                for v in iter(ao):
                    self.countObjects(v)


class InstanceCounter:
    def __init__(self, classType, reportSize):
        self.classType = classType
        self.count = 0
        self.reportSize = reportSize
        if reportSize:
            self.memSize = 0
        else:
            self.memSize = float("nan")
        self.items = set()
        self.ids = set()
        self.first = None

    def add(self, item):
        itemId = id(item)
        if itemId in self.ids:
            return False

        self.ids.add(itemId)
        if self.reportSize:
            self.memSize += sys.getsizeof(item)
        self.count += 1
        return True

    def __cmp__(self, that):
        return (self.count > that.count) - (self.count < that.count)

    def __ls__(self, that):
        return self.count < that.count

    def __gt__(self, that):
        return self.count > that.count


class ProfileMemoryUsageAction(mpiActions.MpiAction):
    def __init__(self, timeDescription):
        mpiActions.MpiAction.__init__(self)
        self.timeDescription = timeDescription

    def invokeHook(self):
        mem = self.o.getInterface("memoryProfiler")
        mem.displayMemoryUsage(self.timeDescription)


class SystemAndProcessMemoryUsage:
    def __init__(self):
        self.nodeName = context.MPI_NODENAME
        # no psutil, no memory diagnostics.
        # TODO: Ideally, we could cut MemoryProfiler entirely, but it is referred to
        # directly by the standard operator and reports, so easier said than done.
        self.percentNodeRamUsed: Optional[float] = None
        self.processMemoryInMB: Optional[float] = None
        self.processVirtualMemoryInMB: Optional[float] = None
        if _havePsutil:
            self.percentNodeRamUsed = psutil.virtual_memory().percent
            self.processMemoryInMB = psutil.Process().memory_info().rss / (1024.0**2)
            self.processVirtualMemoryInMB = psutil.Process().memory_info().vms / (
                1024.0**2
            )

    def __isub__(self, other):
        if self.percentNodeRamUsed is not None and other.percentNodeRamUsed is not None:
            self.percentNodeRamUsed -= other.percentNodeRamUsed
            self.processMemoryInMB -= other.processMemoryInMB
            self.processVirtualMemoryInMB -= other.processVirtualMemoryInMB
        return self


class PrintSystemMemoryUsageAction(mpiActions.MpiAction):
    def __init__(self):
        mpiActions.MpiAction.__init__(self)
        self.usages = []
        self.percentNodeRamUsed: Optional[float] = None

    def __iter__(self):
        return iter(self.usages)

    def __isub__(self, other):
        if self.percentNodeRamUsed is not None and other.percentNodeRamUsed is not None:
            self.percentNodeRamUsed -= other.percentNodeRamUsed
        for mine, theirs in zip(self, other):
            mine -= theirs
        return self

    @property
    def minProcessMemoryInMB(self):
        if len(self.usages) == 0:
            return 0.0
        return min(mu.processMemoryInMB or 0.0 for mu in self)

    @property
    def maxProcessMemoryInMB(self):
        if len(self.usages) == 0:
            return 0.0
        return max(mu.processMemoryInMB or 0.0 for mu in self)

    def invokeHook(self):
        spmu = SystemAndProcessMemoryUsage()
        self.percentNodeRamUsed = spmu.percentNodeRamUsed
        self.usages = self.gather(spmu)

    def printUsage(self, description=None):
        """This method prints the usage of all MPI nodes.

        The printout looks something like:

            SYS_MEM HOSTNAME     14.4% RAM. Proc mem (MB):   491   472   471   471   471   470
            SYS_MEM HOSTNAME     13.9% RAM. Proc mem (MB):   474   473   472   471   460   461
            SYS_MEM HOSTNAME     ...
            SYS_MEM HOSTNAME     ...
        """
        printedNodes = set()
        prefix = description or "SYS_MEM"

        memoryData = []
        for memoryUsage in self:
            if memoryUsage.nodeName in printedNodes:
                continue
            printedNodes.add(memoryUsage.nodeName)
            nodeUsages = [mu for mu in self if mu.nodeName == memoryUsage.nodeName]
            sysMemAvg = sum(mu.percentNodeRamUsed or 0.0 for mu in nodeUsages) / len(
                nodeUsages
            )

            memoryData.append(
                (
                    "{:<24}".format(memoryUsage.nodeName),
                    "{:5.1f}%".format(sysMemAvg),
                    "{}".format(
                        " ".join(
                            "{:5.0f}".format(mu.processMemoryInMB or 0.0)
                            for mu in nodeUsages
                        )
                    ),
                )
            )

        runLog.info(
            "Summary of the system memory usage at `{}`:\n".format(prefix)
            + tabulate.tabulate(
                memoryData,
                headers=[
                    "Machine",
                    "Average System RAM Usage",
                    "Processor Memory Usage (MB)",
                ],
                tableFmt="armi",
            )
        )
