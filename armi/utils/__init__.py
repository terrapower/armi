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


def getTimeStepNum(cycleNumber, subcycleNumber, cs):
    """Return the timestep associated with cycle and tn.

    Parameters
    ----------
    cycleNumber : int, The cycle number
    subcycleNumber : int, The intra-cycle time node (0 for BOC, etc.)
    cs : Settings object

    """
    return cycleNumber * getNodesPerCycle(cs) + subcycleNumber


def getCycleNode(timeStepNum, cs):
    """
    Return the (cycle, node) corresponding to a cumulative time step number.

    Parameters
    ----------
    timeStepNum
        The cumulative number of time steps since the beginning
    cs
        A case Settings object to get the nodes-per-cycle from
    """
    nodesPerCycle = getNodesPerCycle(cs)

    return (timeStepNum // nodesPerCycle, timeStepNum % nodesPerCycle)


def getNodesPerCycle(cs):
    """Return the number of nodes per cycles for this case settings."""
    return cs["burnSteps"] + 1


def getPreviousTimeStep(cycle, node, burnSteps):
    """Return the time step before the specified time step"""
    if (cycle, node) == (0, 0):
        raise ValueError("There is not Time step before (0, 0)")
    if node != 0:
        return (cycle, node - 1)
    else:
        # index starts at zero, so the last node in a cycle is equal to the number of
        # burn steps.
        return (cycle - 1, burnSteps)


def tryPickleOnAllContents(obj, ignore=None, path=None, verbose=False):
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
    path : str
        the path in which to test pickle.
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


def doTestPickleOnAllContents2(obj, ignore=None, path=None, verbose=False):
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


def tryPickleOnAllContents3(obj, ignore=None, path=None, verbose=False):
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


def runFunctionFromAllModules(funcName, *args, **kwargs):
    r"""
    Runs funcName on all modules of ARMI, if it exists.

    Parameters
    ----------
    funcName : str
        The function to run if it is found in a module.

    \*args, \*\*kwargs : arguments to pass to func if it is found

    Notes
    -----
    This imports all modules in ARMI, and if you have a script that isn't inside a
    ``if __name__=='__main__'``, you will be in trouble.

    This could also be useful for finding input consistency checkers for the GUI.

    See Also
    --------
    armi.settings.addAllDefaultSettings : gets all the settings from all modules

    """
    for _modImporter, name, _ispkg in pkgutil.walk_packages(
        path=armi_path, prefix=armi_name + "."
    ):
        try:
            mod = importlib.import_module(name)
            if funcName in dir(mod):  # there is a module.funcName. so call it.
                func = getattr(mod, funcName)
                func(*args, **kwargs)
        except:
            # just print traceback but don't throw an error.
            traceback.print_exc()


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
