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

"""Generic ARMI utilities"""
import collections
import datetime
import getpass
import hashlib
import importlib
import math
import os
import pickle
import pkgutil
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback

from armi import __name__ as armi_name
from armi import __path__ as armi_path
from armi import runLog
from armi.utils import iterables
from armi.utils.flags import Flag
from armi.utils.mathematics import *  # for backwards compatibility

# Read in file 1 MB at a time to reduce memory burden of reading entire file at once
_HASH_BUFFER_SIZE = 1024 * 1024


def getFileSHA1Hash(filePath, digits=40):
    """
    Generate a SHA-1 hash of the input file.

    Parameters
    ----------
    filePath : str
        Path to file to obtain the SHA-1 hash
    digits : int, optional
        Number of digits to include in the hash (40 digit maximum for SHA-1)
    """
    sha1 = hashlib.sha1()
    with open(filePath, "rb") as f:
        while True:
            data = f.read(_HASH_BUFFER_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()[:digits]


def copyWithoutBlocking(src, dest):
    """
    Copy a file in a separate thread to avoid blocking while IO completes.

    Useful for copying large files while ARMI moves along.
    """
    files = "{} to {}".format(src, dest)
    runLog.extra("Copying (without blocking) {}".format(files))
    t = threading.Thread(target=shutil.copy, args=(src, dest))
    t.start()
    return t


def getPowerFractions(cs):
    """
    Return the power fractions for each cycle.

    Parameters
    ----------
    cs : case settings object

    Returns
    -------
    powerFractions : 2-list
        A list with nCycles elements, where each element is itself a list of the
        power fractions at each step of the cycle.

    Notes
    -----
    This is stored outside of the Operator class so that it can be easily called
    to resolve case settings objects in other contexts (i.e. in the preparation
    of restart runs).
    """
    if cs["cycles"] != []:
        return [
            expandRepeatedFloats(
                (cycle["power fractions"])
                if "power fractions" in cycle.keys()
                else [1] * getBurnSteps(cs)[cycleIdx]
            )
            for (cycleIdx, cycle) in enumerate(cs["cycles"])
        ]
    else:
        valuePerCycle = (
            expandRepeatedFloats(cs["powerFractions"])
            if cs["powerFractions"] not in [None, []]
            else [1.0] * cs["nCycles"]
        )

        return [
            [value] * (cs["burnSteps"] if cs["burnSteps"] != None else 0)
            for value in valuePerCycle
        ]


def getCycleNames(cs):
    """
    Return the names of each cycle. If a name is omitted, it is `None`.

    Parameters
    ----------
    cs : case settings object

    Returns
    -------
    cycleNames : list
        A list of the availability factors.

    Notes
    -----
    This is stored outside of the Operator class so that it can be easily called
    to resolve case settings objects in other contexts (i.e. in the preparation
    of restart runs).
    """
    if cs["cycles"] != []:
        return [
            (cycle["name"] if "name" in cycle.keys() else None)
            for cycle in cs["cycles"]
        ]
    else:
        return [None] * cs["nCycles"]


def getAvailabilityFactors(cs):
    """
    Return the availability factors for each cycle.

    Parameters
    ----------
    cs : case settings object

    Returns
    -------
    availabilityFactors : list
        A list of the availability factors.

    Notes
    -----
    This is stored outside of the Operator class so that it can be easily called
    to resolve case settings objects in other contexts (i.e. in the preparation
    of restart runs).
    """
    if cs["cycles"] != []:
        availabilityFactors = []
        for cycle in cs["cycles"]:
            if "availability factor" in cycle.keys():
                availabilityFactors.append(cycle["availability factor"])
            else:
                availabilityFactors.append(1)
        return availabilityFactors
    else:
        return (
            expandRepeatedFloats(cs["availabilityFactors"])
            if cs["availabilityFactors"] not in [None, []]
            else (
                [cs["availabilityFactor"]] * cs["nCycles"]
                if cs["availabilityFactor"] != None
                else [1]
            )
        )


def _getStepAndCycleLengths(cs):
    """
    These need to be gotten together because it is a chicken/egg depending on which
    style of cycles input the user employs.

    Note that using this method directly is more effecient than calling `getStepLengths`
    and `getCycleLengths` separately, but it is probably more clear to the user
    to call each of them separately.
    """
    stepLengths = []
    availabilityFactors = getAvailabilityFactors(cs)
    if cs["cycles"] != []:
        for cycleIdx, cycle in enumerate(cs["cycles"]):
            cycleKeys = cycle.keys()

            if "step days" in cycleKeys:
                stepLengths.append(expandRepeatedFloats(cycle["step days"]))
            elif "cumulative days" in cycleKeys:
                cumulativeDays = cycle["cumulative days"]
                stepLengths.append(getStepsFromValues(cumulativeDays))
            elif "burn steps" in cycleKeys and "cycle length" in cycleKeys:
                stepLengths.append(
                    [
                        cycle["cycle length"]
                        * availabilityFactors[cycleIdx]
                        / cycle["burn steps"]
                    ]
                    * cycle["burn steps"]
                )
            else:
                raise ValueError(
                    f"No cycle time history is given in the detailed cycles history for cycle {cycleIdx}"
                )

        cycleLengths = [sum(cycleStepLengths) for cycleStepLengths in stepLengths]
        cycleLengths = [
            cycleLength / aFactor
            for (cycleLength, aFactor) in zip(cycleLengths, availabilityFactors)
        ]

    else:
        cycleLengths = (
            expandRepeatedFloats(cs["cycleLengths"])
            if cs["cycleLengths"] not in [None, []]
            else (
                [cs["cycleLength"]] * cs["nCycles"]
                if cs["cycleLength"] != None
                else [0]
            )
        )
        cycleLengthsModifiedByAvailability = [
            length * availability
            for (length, availability) in zip(cycleLengths, availabilityFactors)
        ]
        stepLengths = (
            [
                [length / cs["burnSteps"]] * cs["burnSteps"]
                for length in cycleLengthsModifiedByAvailability
            ]
            if cs["burnSteps"] not in [0, None]
            else [[]]
        )

    return stepLengths, cycleLengths


def getStepLengths(cs):
    """
    Return the length of each step in each cycle.

    Parameters
    ----------
    cs : case settings object

    Returns
    -------
    stepLengths : 2-list
        A list with elements for each cycle, where each element itself is a list
        containing the step lengths in days.

    Notes
    -----
    This is stored outside of the Operator class so that it can be easily called
    to resolve case settings objects in other contexts (i.e. in the preparation
    of restart runs).
    """
    return _getStepAndCycleLengths(cs)[0]


def getCycleLengths(cs):
    """
    Return the lengths of each cycle in days.

    Parameters
    ----------
    cs : case settings object

    Returns
    -------
    cycleLengths : list
        A list of the cycle lengths in days.

    Notes
    -----
    This is stored outside of the Operator class so that it can be easily called
    to resolve case settings objects in other contexts (i.e. in the preparation
    of restart runs).
    """
    return _getStepAndCycleLengths(cs)[1]


def getBurnSteps(cs):
    """
    Return the number of burn steps for each cycle.

    Parameters
    ----------
    cs : case settings object

    Returns
    -------
    burnSteps : list
        A list of the number of burn steps.

    Notes
    -----
    This is stored outside of the Operator class so that it can be easily called
    to resolve case settings objects in other contexts (i.e. in the preparation
    of restart runs).
    """
    stepLengths = getStepLengths(cs)
    return [len(steps) for steps in stepLengths]


def hasBurnup(cs):
    """Is depletion being modeled?

    Parameters
    ----------
    cs : case settings object

    Returns
    -------
    bool
        Are there any burnup steps?
    """
    return sum(getBurnSteps(cs)) > 0


def getMaxBurnSteps(cs):
    burnSteps = getBurnSteps(cs)
    return max(burnSteps)


def getCumulativeNodeNum(cycle, node, cs):
    """
    Return the cumulative node number associated with a cycle and time node.

    Note that a cycle with n time steps has n+1 nodes, and for cycle m with n steps, nodes
    (m, n+1) and (m+1, 0) are counted separately.

    Parameters
    ----------
    cycle : int
        The cycle number
    node : int
        The intra-cycle time node (0 for BOC, etc.)
    cs : Settings object
    """
    nodesPerCycle = getNodesPerCycle(cs)
    return sum(nodesPerCycle[:cycle]) + node


def getCycleNodeFromCumulativeStep(timeStepNum, cs):
    """
    Return the (cycle, node) corresponding to a cumulative time step number.

    "Node" refers to the node at the start of the time step.

    Parameters
    ----------
    timeStepNum : int
        The cumulative number of time steps since the beginning
    cs : case settings object
        A case settings object to get the steps-per-cycle from

    Notes
    -----
    Time steps are the spaces between time nodes, and are 1-indexed.

    To get the (cycle, node) from a cumulative time node, see instead
    getCycleNodeFromCumulativeNode.
    """
    stepsPerCycle = getBurnSteps(cs)

    if timeStepNum < 1:
        raise ValueError(f"Cumulative time step cannot be less than 1.")

    cSteps = 0  # cumulative steps
    for i in range(len(stepsPerCycle)):
        cSteps += stepsPerCycle[i]
        if timeStepNum <= cSteps:
            return (i, timeStepNum - (cSteps - stepsPerCycle[i]) - 1)

    i = len(stepsPerCycle) - 1
    return (i, timeStepNum - (cSteps - stepsPerCycle[i]) - 1)


def getCycleNodeFromCumulativeNode(timeNodeNum, cs):
    """
    Return the (cycle, node) corresponding to a cumulative time node number.

    Parameters
    ----------
    timeNodeNum : int
        The cumulative number of time nodes since the beginning
    cs : case settings object
        A case settings object to get the nodes-per-cycle from

    Notes
    -----
    Time nodes are the start/end of time steps, and are 0-indexed. For a cycle
    with n steps, there will be n+1 nodes (one at the start of the cycle and another
    at the end, plus those separating the steps). For cycle m with n steps, nodes
    (m, n+1) and (m+1, 0) are counted separately.

    To get the (cycle, node) from a cumulative time step, see instead
    getCycleNodeFromCumulativeStep.
    """
    nodesPerCycle = getNodesPerCycle(cs)

    if timeNodeNum < 0:
        raise ValueError(f"Cumulative time node cannot be less than 0.")

    cNodes = 0  # cumulative nodes
    for i in range(len(nodesPerCycle)):
        cNodes += nodesPerCycle[i]
        if timeNodeNum < cNodes:
            return (i, timeNodeNum - (cNodes - nodesPerCycle[i]))

    i = len(nodesPerCycle) - 1
    return (i, timeNodeNum - (cNodes - nodesPerCycle[i]))


def getNodesPerCycle(cs):
    """Return the number of nodes per cycle for the case settings object."""
    return [s + 1 for s in getBurnSteps(cs)]


def getPreviousTimeNode(cycle, node, cs):
    """Return the (cycle, node) before the specified (cycle, node)"""
    if (cycle, node) == (0, 0):
        raise ValueError("There is no time step before (0, 0)")
    if node != 0:
        return (cycle, node - 1)
    else:
        nodesPerCycle = getNodesPerCycle(cs)
        nodesInLastCycle = nodesPerCycle[cycle - 1]
        indexOfLastNode = nodesInLastCycle - 1  # zero based indexing for nodes
        return (cycle - 1, indexOfLastNode)


def tryPickleOnAllContents(obj, ignore=None, verbose=False):
    r"""
    Attempts to pickle all members of this object and identifies those who cannot be pickled.

    Useful for debugging MPI-bcast errors

    Not recursive yet. Would be nice to have it loop through nested objects (blocks in assems in reactors)

    Parameters
    ----------
    obj : object
        Any object to be tested.
    ignore : iterable
        list of string variable names to ignore.
    verbose : bool, optional
        Print all objects whether they fail or not
    """
    if ignore is None:
        ignore = []

    # pickle gives better error messages than cPickle
    for name, ob in obj.__dict__.items():
        if name not in ignore:
            if verbose:
                print("Checking {0}...".format(name))
            try:
                pickle.dumps(ob)  # dump as a string
            except:
                print(
                    "{0} in {1} cannot be pickled. It is: {2}. ".format(name, obj, ob)
                )


def doTestPickleOnAllContents2(obj, ignore=None):
    r"""
    Attempts to find one unpickleable object in a nested object

    Returns
    -------
    pickleChain : list
        list of names in a chain that are unpickleable. Just one example per object
        e.g. ['r','assemblies','A101','lib] means the lib is unpicklable.
    """
    if ignore is None:
        ignore = []
    unpickleable = []
    if not hasattr(obj, "__dict__"):
        print("done")
        return unpickleable
    for name, ob in obj.__dict__.items():
        print(("checking ", name))
        if name not in ignore:
            try:
                pickle.dumps(ob)  # dump as a string
            except:
                unpickleable.append(name)
                print("Cant pickle {0}".format(name))
                # recursive call.
                unpickleable.extend(
                    doTestPickleOnAllContents2(ob, ignore=unpickleable + ignore)
                )

    return unpickleable


class MyPickler(pickle.Pickler):
    r"""
    This will find your pickle errors if all else fails.

    Use with tryPickleOnAllContents3.
    """

    def save(self, obj):
        try:
            pickle.Pickler.save(self, obj)
        except Exception:
            _excType, excValue, _excTraceback = sys.exc_info()
            print("Object that failed: {}. Err: {}".format(obj, excValue))
            raise


def tryPickleOnAllContents3(obj):
    """
    Definitely find pickle errors

    Notes
    -----
    In this form, this just finds one pickle error and then crashes. If you want
    to make it work like the other testPickle functions and handle errors, you could.
    But usually you just have to find one unpickleable SOB.
    """
    with tempfile.TemporaryFile() as output:
        try:
            MyPickler(output).dump(obj)
        except (pickle.PicklingError, TypeError):
            pass


def classesInHierarchy(obj, classCounts, visited=None):
    """Count the number of instances of each class contained in an objects heirarchy."""
    if not isinstance(classCounts, collections.defaultdict):
        raise TypeError(
            "Need to pass in a default dict for classCounts (it's an out param)"
        )

    if visited is None:
        classCounts[type(obj)] += 1
        visited = set()
        visited.add(id(obj))

    try:
        for c in obj.__dict__.values():
            if id(c) not in visited:
                classCounts[type(c)] += 1
                visited.add(id(c))
                classesInHierarchy(c, classCounts, visited=visited)
    except AttributeError:
        pass


def slantSplit(val, ratio, nodes, order="low first"):
    r"""
    Returns a list of values whose sum is equal to the value specified.
    The ratio between the highest and lowest value is equal to the specified ratio,
    and the middle values trend linearly between them.
    """
    val = float(val)
    ratio = float(ratio)
    nodes = int(nodes)
    v0 = 2.0 * val / (nodes * (1.0 + ratio))
    X = []
    for i in range(nodes):
        X.append(v0 + i * (v0 * ratio - v0) / (nodes - 1))

    if order == "high first":
        X.reverse()

    return X


def prependToList(originalList, listToPrepend):
    """
    Add a new list to the beginnning of an original list.

    Parameters
    ----------
    originalList : list
        The list to prepend to.

    listToPrepend : list
        The list to add to the beginning of (prepend) the originalList.

    Returns
    -------
    originalList : list
        The original list with the listToPrepend at it's beginning.

    """
    listToPrepend.reverse()
    originalList.reverse()
    originalList.extend(listToPrepend)
    originalList.reverse()
    listToPrepend.reverse()
    return originalList


def capStrLen(s: str, length: int) -> str:
    """
    Truncates a string to a certain length.

    Adds '...' if it's too long.

    Parameters
    ----------
    s : str
        The string to cap at length l.
    length : int
        The maximum length of the string s.
    """
    if length <= 2:
        raise Exception("l must be at least 3 in utils.capStrLen")

    if len(s) <= length:
        return s

    return s[0 : length - 3] + "..."


def list2str(strings, width=None, preStrings=None, fmt=None):
    """
    Turn a list of strings into one string, applying the specified format to each.

    Parameters
    ----------
    strings : list
        The items to create centered strings in the line for.
        Can be str, float, int, etc.

    width : int, optional
        The maximum width that the strings are allowed to take up.
        Only strings are affected by this parameter, because it does
        not make sense to truncate ints or floats.

    preStrings : list of str, optional
        Any strings that come before the centered strings.

    fmt : str, optional
        The format to apply to each string, such as
        ' >4d', '^12.4E'.

    """
    if preStrings is None:
        preStrings = []

    if fmt is None:
        fmt = ""

    newStrings = []
    for string in strings:
        if isinstance(string, str) and width is not None:
            string = capStrLen(str(string), width)
        string = "{0:{fmt}}".format(string, fmt=fmt)
        newStrings.append(string)

    preStrings.extend(newStrings)
    return "".join(preStrings)


def createFormattedStrWithDelimiter(
    dataList, maxNumberOfValuesBeforeDelimiter=9, delimiter="\n"
):
    r"""
    Return a formatted string with delimiters from a list of data.

    Parameters
    ----------
    dataList : list
        List of data that will be formatted into a string
    maxNumberOfValuesBeforeDelimiter : int
        maximum number of values to have before the delimiter is added
    delimiter : str
        A delimiter on the formatted string (default: "\n")

    Notes
    -----
    As an example::

        >>> createFormattedStrWithDelimiter(['hello', 'world', '1', '2', '3', '4'],
        ...     maxNumberOfValuesBeforeDelimiter=3, delimiter = '\n')
        "hello, world, 1, \n2, 3, \n4, 5\n"

    """
    formattedString = ""
    if not dataList:
        return formattedString

    if not maxNumberOfValuesBeforeDelimiter:
        numRows = 1
    else:
        numRows = (
            int(
                math.ceil(
                    float(len(dataList)) / float(maxNumberOfValuesBeforeDelimiter)
                )
            )
            or 1
        )

    # Create a list of string delimiters to use when joining the strings
    commaList = ["," for d in dataList]
    commaList[-1] = ""
    dataList = [str(d) + commaList[i] for i, d in enumerate(dataList)]
    for splitList in iterables.split(dataList, n=numRows, padWith=""):
        formattedString += " ".join(splitList) + delimiter
    return formattedString


def plotMatrix(
    matrix,
    fName,
    minV=None,
    maxV=None,
    show=False,
    title=None,
    xlabel=None,
    ylabel=None,
    xticks=None,
    yticks=None,
    cmap=None,
    figsize=None,
):
    """Plots a matrix"""
    import matplotlib
    import matplotlib.pyplot as plt

    if figsize:
        plt.figure(figsize=figsize)  # dpi=300)
    else:
        plt.figure()

    if cmap is None:
        cmap = plt.cm.jet  # @UndefinedVariable  #pylint: disable=no-member

    cmap.set_bad("w")
    try:
        matrix = matrix.todense()
    except:
        pass

    if minV:
        norm = matplotlib.colors.Normalize(minV, maxV)
    else:
        norm = None

    if title is None:
        title = fName

    # or bicubic or nearest#,vmin=0, vmax=300)
    plt.imshow(matrix, cmap=cmap, norm=norm, interpolation="nearest")
    plt.colorbar()
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if xticks:
        plt.xticks(*xticks, rotation=90)
    if yticks:
        plt.yticks(*yticks)
    plt.grid()
    plt.savefig(fName)
    if show:
        plt.show()
    plt.close()


def userName() -> str:
    """
    Return a database-friendly username.

    This will return the current user's username, removing any prefix like ``pre-``, if
    present.

    Notes
    -----
    ARMI uses the user name in a number of places, namely in the database names, which
    cannot contain hyphens.
    """
    return re.sub("^[a-zA-Z]-", "", getpass.getuser())


class MergeableDict(dict):
    """
    Overrides python dictionary and implements a merge method.

    Notes
    -----
    Allows multiple dictionaries to be combined in a single line
    """

    def merge(self, *otherDictionaries) -> None:
        for dictionary in otherDictionaries:
            self.update(dictionary)


def safeCopy(src: str, dst: str) -> None:
    """This copy overwrites ``shutil.copy`` and checks that copy operation is truly completed before continuing."""
    waitTime = 0.01  # 10 ms
    if os.path.isdir(dst):
        dst = os.path.join(dst, os.path.basename(src))
    srcSize = os.path.getsize(src)
    shutil.copyfile(src, dst)
    shutil.copymode(src, dst)
    while True:
        dstSize = os.path.getsize(dst)
        if srcSize == dstSize:
            break
        time.sleep(waitTime)
    runLog.extra("Copied {} -> {}".format(src, dst))


# Allow us to check the copy operation is complete before continuing
shutil_copy = shutil.copy
shutil.copy = safeCopy
