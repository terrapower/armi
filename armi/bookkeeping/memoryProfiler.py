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

1. You can ask psutil for the memory used by the process
from an OS perspective. This is great for top-down analysis. This module provides printouts
that show info from every process running. This is very fast.

2. You can use ``asizeof`` (part of pympler) to measure the size of various individual objects. This will help
you pin-point your issue. But it's slow.

3. You can use ``gc.get_objects()`` to list all objects that the garbage collector is tracking. If you want, you
can filter it down and get the counts and sizes of objects of interest (e.g. all armi objects).

This module has tools to do all of this. It should help you out.

Note that if psutil is reporting way more memory usage than the asizeof reports, then you probably are dealing
with a garbage collection queue. If you free a large number of objects, call `gc.collect()` to force a
garbage collection and the psutil process memory should fall by a lot.
Also, it seems that even if your garbage is collected, Windows does not de-allocate all the memory. So if
you are a worker and you just got a  1.6GB reactor but then deleted it, Windows will keep you at 1.6GB for a while.


See Also:

http://packages.python.org/Pympler/index.html
https://pythonhosted.org/psutil/
https://docs.python.org/2/library/gc.html#gc.garbage
"""
import gc
import logging
import tabulate
from typing import Optional

from armi import context
from armi import interfaces
from armi import mpiActions
from armi import runLog
from armi.reactor.composites import ArmiObject

try:
    import psutil

    # psutil is an optional requirement, since it doesnt support MacOS very well
    _havePsutil = True
except ImportError:
    runLog.warning(
        "Failed to import psutil; MemoryProfiler will not provide meaningful data."
    )
    _havePsutil = False


# disable the import warnings (Issue #88)
logging.disable(logging.CRITICAL)
from pympler.asizeof import asizeof

# This is necessary to reset pympler's changes to the logging configuration
logging.disable(logging.NOTSET)


ORDER = interfaces.STACK_ORDER.POSTPROCESSING


def describeInterfaces(cs):
    """Function for exposing interface(s) to other code"""
    return (MemoryProfiler, {})


class MemoryProfiler(interfaces.Interface):

    name = "memoryProfiler"

    def __init__(self, r, cs):
        interfaces.Interface.__init__(self, r, cs)
        self.sizes = {}

    def interactBOL(self):
        interfaces.Interface.interactBOL(self)
        mpiAction = PrintSystemMemoryUsageAction()
        mpiAction.broadcast().invoke(self.o, self.r, self.cs)
        mpiAction.printUsage("BOL SYS_MEM")

        # so we can debug mem profiler quickly
        if self.cs["debugMem"]:
            mpiAction = ProfileMemoryUsageAction("EveryNode")
            mpiAction.broadcast().invoke(self.o, self.r, self.cs)

    def interactEveryNode(self, cycle, node):
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
        r"""End of life hook. Good place to wrap up or print out summary outputs"""
        if self.cs["debugMem"]:
            mpiAction = ProfileMemoryUsageAction("EOL")
            mpiAction.broadcast().invoke(self.o, self.r, self.cs)

    def displayMemoryUsage(self, timeDescription):
        r"""
        Print out some information to stdout about the memory usage of ARMI.

        Makes use of the asizeof utility.

        Useful when the debugMem setting is set to True.

        Turn these on as appropriate to find all your problems.
        """
        runLog.important(
            "----- Memory Usage Report at {} -----".format(timeDescription)
        )
        self._printFullMemoryBreakdown(
            startsWith="", reportSize=self.cs["debugMemSize"]
        )
        self._reactorAssemblyTrackingBreakdown()
        runLog.important(
            "----- End Memory Usage Report at {} -----".format(timeDescription)
        )

    def _reactorAssemblyTrackingBreakdown(self):
        runLog.important("Reactor attribute ArmiObject tracking count")
        for attrName, attrObj in self.r.core.__dict__.items():
            if (
                isinstance(attrObj, list)
                and attrObj
                and isinstance(attrObj[0], ArmiObject)
            ):
                runLog.important(
                    "List {:30s} has {:4d} assemblies".format(attrName, len(attrObj))
                )
            if (
                isinstance(attrObj, dict)
                and attrObj
                and isinstance(list(attrObj.values())[0], ArmiObject)
            ):
                runLog.important(
                    "Dict {:30s} has {:4d} assemblies".format(attrName, len(attrObj))
                )
        runLog.important("SFP has {:4d} assemblies".format(len(self.r.core.sfp)))

    def checkForDuplicateObjectsOnArmiModel(self, attrName, refObject):
        """Scans thorugh ARMI model for duplicate objects"""
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

    def _printFullMemoryBreakdown(
        self, startsWith="armi", reportSize=True, printReferrers=False
    ):
        """
        looks for any class from any module in the garbage collector and prints their count and size

        Very powerful. Also very slow if you reportSize

        Parameters
        ----------
        startsWith : str, optional
            limit to objects with classes that start with a certain string
        reportSize : bool, optional
            calculate size as well as counting individual objects. SLLOOOWW.

        Notes
        -----
        Just because you use startsWith=armi doesn't mean you'll capture all ARMI objects. Some are in lists
        and dictionaries.
        """
        cs = self.cs
        operator = self.o
        reactor = self.r

        if reportSize:
            self.r.detach()
            self.o.detach()

        gc.collect()
        allObjects = gc.get_objects()
        instanceCounters = KlassCounter(reportSize)

        runLog.info("GC returned {} objects".format(len(allObjects)))

        instanceCounters.countObjects(allObjects)
        for counter in sorted(instanceCounters.counters.values()):
            runLog.info(
                "UNIQUE_INSTANCE_COUNT: {:60s} {:10d}     {:10.1f} MB".format(
                    counter.classType.__name__,
                    counter.count,
                    counter.memSize / (1024 ** 2.0),
                )
            )
            if printReferrers and counter.memSize / (1024 ** 2.0) > 100:
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
    def getSpecificReferrers(klass, ancestorKlass):
        """Try to determine some useful information about the structure of ArmiObjects and potential
        orphans.

        This takes a class and an expected/nominal parent class, which should both be instances of
        ArmiObject. It will then locate all instances of klass that are tracked by the GC, igoring
        those that have an ancestor of ancestorKlass type. A report will be generated containing
        the counts of the instances of klass that are _not_ part of the ancestor_class along with
        their referrer class.

        This is useful for diagnosing memory leaks, as it points to unexpected referrers to
        ArmiObjects.
        """
        if not issubclass(klass, ArmiObject) or not issubclass(
            ancestorKlass, ArmiObject
        ):
            raise TypeError(
                "klass and ancestorKlass should be subclasses of ArmiObject"
            )

        # info will be a list containing a tuple for every instance of klass that does not have an
        # ancestorKlass somewhere in its chain of parents. Each tuple contains its parent object
        # and the set of classes of objects that refer to it
        info = []
        nominalCount = 0
        exampleObj = None
        maxObjects = 100
        objectsSoFar = 0
        for obj in (o for o in gc.get_objects() if isinstance(o, klass)):
            if objectsSoFar > maxObjects:
                break

            isNominal = False
            o2 = obj
            while o2.parent is not None:
                if isinstance(o2.parent, ancestorKlass):
                    isNominal = True
                    break
                o2 = o2.parent
            runLog.important("isNominal: {} parent: {}".format(isNominal, obj.parent))
            if isNominal:
                nominalCount += 1
            else:
                exampleObj = obj
                objectsSoFar += 1
                referrers = gc.get_referrers(obj)
                referrerClasses = {type(o) for o in referrers}
                info.append((obj.parent, referrerClasses))

        if exampleObj is not None:
            runLog.important("Walking referrers for {}".format(exampleObj))
            _walkReferrers(exampleObj, maxLevel=8)
            raise RuntimeError("All done")

        runLog.important(
            "List of {} orphaned ArmiObjects (obj.parent, {{referring object "
            "classes}})".format(len(info))
        )
        for item in info:
            runLog.important("{}".format(item))

    @staticmethod
    def getReferrers(obj):
        """Print referrers in a useful way (as opposed to gigabytes of text"""
        runLog.info("Printing first 100 character of first 100 referrers")
        for ref in gc.get_referrers(obj)[:100]:
            print("ref for {}: {}".format(obj, repr(ref)[:100]))

    @staticmethod
    def discussSkipped(skipped, errors):
        runLog.warning("Skipped {} objects".format(skipped))
        runLog.warning(
            "errored out on {0} objects:\n {1}".format(
                len(errors), "\n".join([repr(ei)[:30] for ei in errors])
            )
        )


class KlassCounter:
    def __init__(self, reportSize):
        self.counters = dict()
        self.reportSize = reportSize
        self.count = 0

    def __getitem__(self, classType):
        if classType not in self.counters:
            self.counters[classType] = InstanceCounter(classType, self.reportSize)
        return self.counters[classType]

    def __iadd__(self, item):
        klass = type(item)
        if klass in self.counters:
            counter = self.counters[klass]
        else:
            counter = InstanceCounter(klass, self.reportSize)
            counter.first = item  # done here for speed
            self.counters[klass] = counter
        counter += item

    def countObjects(self, ao):
        """
        Recursively find non-list,dict, tuple objects in containers.

        Essential for traversing the garbage collector
        """
        itemType = type(ao)
        counter = self[itemType]
        if counter.add(ao):
            self.count += 1
            if self.count % 100000 == 0:
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
            try:
                self.memSize += asizeof(item)
            except:
                self.memSize = float("nan")
        self.count += 1
        return True

    def __cmp__(self, that):
        return (self.count > that.count) - (self.count < that.count)

    def __ls__(self, that):
        return self.count < that.count

    def __gt__(self, that):
        return self.count > that.count


def _getClsName(obj):
    try:
        return obj.__class__.__name__
    except:
        try:
            return obj.__name__
        except:
            return repr(obj)[:20]


def _getModName(obj):
    try:
        return obj.__class__.__module__
    except:
        return None


class ObjectSizeBreakdown:
    def __init__(
        self,
        name,
        minMBToShowAttrBreakdown=30.0,
        excludedAttributes=None,
        initialZeroes=0,
    ):
        # don't hold onto obj, otherwise we'll bloat like crazy!!
        self.name = name
        self.sizes = [0.0] * initialZeroes
        self.minMBToShowAttrBreakdown = minMBToShowAttrBreakdown
        self.excludedAttributes = excludedAttributes or []
        self.attrSizes = {}

    @property
    def size(self):
        return self.sizes[-1]

    def calcSize(self, obj):
        tempAttrs = {}
        try:
            for attrName in self.excludedAttributes:
                if hasattr(obj, attrName):
                    tempAttrs[attrName] = getattr(obj, attrName, None)
                    setattr(obj, attrName, None)
            self.sizes.append(asizeof(obj) / (1024.0 ** 2))
            self._breakdownAttributeSizes(obj)
        finally:
            for attrName, attrObj in tempAttrs.items():
                setattr(obj, attrName, attrObj)

    def _breakdownAttributeSizes(self, obj):
        if self.size > self.minMBToShowAttrBreakdown:
            # make a getter where getter(obj, key) gives obj.key or obj[key]
            if isinstance(obj, dict):
                keys = obj.keys()
                getter = lambda obj, key: obj.get(key)
            elif isinstance(obj, list):
                keys = range(len(obj))
                getter = lambda obj, key: obj[key]
            else:
                keys = obj.__dict__.keys()
                getter = getattr

            for attrName in set(keys) - set(self.excludedAttributes):
                name = "  .{}".format(attrName)
                if name not in self.attrSizes:
                    # arbitrarily, we don't care unless the attribute is a GB
                    self.attrSizes[name] = ObjectSizeBreakdown(
                        name, 1000.0, initialZeroes=len(self.sizes) - 1
                    )
                attrSize = self.attrSizes[name]
                attrSize.calcSize(getter(obj, attrName))

    def __repr__(self):
        message = []
        name = self.name
        if self.excludedAttributes:
            name += " except(.{})".format(", .".join(self.excludedAttributes))
        message.append("{0:53s} {1:8.4f}MB".format(name, self.size))
        for attr in self.attrSizes.values():
            message.append(repr(attr))
        return "\n".join(message)


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
        if _havePsutil:
            self.percentNodeRamUsed = psutil.virtual_memory().percent
            self.processMemoryInMB = psutil.Process().memory_info().rss / (1012.0 ** 2)

    def __isub__(self, other):
        if self.percentNodeRamUsed is not None and other.percentNodeRamUsed is not None:
            self.percentNodeRamUsed -= other.percentNodeRamUsed
            self.processMemoryInMB -= other.processMemoryInMB
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
                tablefmt="armi",
            )
        )


def _getFunctionObject():
    """Return the function object of the calling function. Useful for debugging"""
    from inspect import currentframe, getframeinfo

    caller = currentframe().f_back
    func_name = getframeinfo(caller)[2]
    caller = caller.f_back

    func = caller.f_locals.get(func_name, caller.f_globals.get(func_name))

    return func


def _walkReferrers(o, maxLevel=0, level=0, memo=None, whitelist=None):
    """Walk the tree of objects that refer to the passed object, printing diagnostics."""
    if maxLevel and level > maxLevel:
        return
    if level == 0:
        gc.collect()
        whitelist = {id(obj) for obj in gc.get_objects()}
        whitelist.remove(id(_getFunctionObject()))
        whitelist.remove(id(_getFunctionObject))

    if memo is None:
        memo = set()
    gc.collect()
    referrers = [
        (referrer, id(referrer), id(referrer) in memo)
        for referrer in gc.get_referrers(o)
        if referrer.__class__.__name__ != "frame" and id(referrer) in whitelist
    ]
    memo.update({oid for (_obj, oid, _seen) in referrers})
    for (obj, _, seen) in referrers:
        runLog.important(
            "{}{}    {} at {:x} seen: {}".format(
                "-" * level, type(obj), "{}".format(obj)[:100], id(obj), seen
            )
        )
        if seen:
            return
        _walkReferrers(
            obj, maxLevel=maxLevel, level=level + 1, memo=memo, whitelist=whitelist
        )
