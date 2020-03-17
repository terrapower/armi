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
from __future__ import print_function

import os
import sys
import time
import pickle
import re
import pkgutil
import importlib
import traceback
import getpass
import math
import datetime
import tempfile
import shutil
import threading
import subprocess
import collections

import hashlib

import numpy
import scipy.optimize as sciopt
from scipy import arange, array

import armi
from armi import runLog
from armi.utils import iterables
from armi.localization import strings
from armi.localization import warnings
from armi.localization import exceptions

_HASH_BUFFER_SIZE = (
    1024 * 1024
)  # Read in file 1 MB at a time to reduce memory burden of reading entire file at once


def coverageReportHelper(config, dataPaths):
    """
    Small utility function to generate coverage reports.

    This was created to side-step the difficulties in submitting multi-line python
    commands on-the-fly.

    This combines data paths and then makes html and xml reports for the
    fully-combined result.
    """
    from coverage import Coverage
    import coverage

    try:
        cov = Coverage(config_file=config)
        if dataPaths:
            # fun fact: if you combine when there's only one file, it gets deleted.
            cov.combine(data_paths=dataPaths)
            cov.save()
        else:
            cov.load()
        cov.html_report()
        cov.xml_report()
    except PermissionError:
        # Albert has some issues with filename that start with a '.', such as the
        # .coverage files. If a permissions error is raised, it likely has something to
        # do with that. We changed the COVERAGE_RESULTS_FILE in cases.py for this reason.
        #
        # We print here, since this is used to run a one-off command, so runLog isn't
        # really appropriate.
        print(
            "There was an issue in generating coverage reports. Probably related to "
            "Albert hidden file issues."
        )
        # disabled until we figure out the problem.
        # raise
    except coverage.misc.CoverageException as e:
        # This is happening when forming the unit test coverage report. This may be
        # caused by the TestFixture coverage report gobbling up all of the coverage
        # files before the UnitTests.cov_report task gets a chance to see them. It may
        # simply be that we dont want a coverage report generated for the TestFixture.
        # Something to think about. Either way, we do not want to fail the job just
        # because of this
        print(
            "There was an issue generating coverage reports "
            "({}):\n{}".format(type(e), e.args)
        )


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


def efmt(a):
    r"""Converts string exponential number to another string with just 2 digits in the exponent."""
    # this assumes that none of our numbers will be more than 1e100 or less than 1e-100...
    if len(a.split("E")) != 2:
        two = a.split("e")
    else:
        two = a.split("E")
    # print two
    exp = two[1]  # this is '+002' or '+02' or something

    if len(exp) == 4:  # it has 3 digits of exponent
        exp = exp[0] + exp[2:]  # gets rid of the hundred's place digit

    return two[0] + "E" + exp


def fixThreeDigitExp(strToFloat):
    """
    Convert FORTRAN numbers that cannot be converted into floats.

    Notes
    -----
    Converts a number line  "9.03231714805651-101" (no e or E) to "9.03231714805651e-101".
    Some external depletion kernels currently need this fix. From contact with developer:
    The notation like 1.0-101 is a FORTRAN thing, with history going back to the 60's.
    They will only put E before an exponent 99 and below.  Fortran will also read these guys
    just fine, and they are valid floating point numbers.  It would not be a useful effort,
    in terms of time, trying to get FORTRAN to behave differently.
    The approach has been to write a routine in the reading code which will interpret these.
    """
    scipat = r"([+-]?\d*\.\d+)[eEdD]?([+-]\d+)"
    match = re.match(scipat, strToFloat)
    return float("{}E{}".format(*match.groups()))


def findClosest(listToSearch, val, indx=False):
    r"""
    find closest item in a list.

    Parameters
    ----------
    listToSearch : list
        The list to search through

    val : float
        The target value that is being searched for in the list

    indx : bool, optional
        If true, returns minVal and minIndex, otherwise, just the value

    Returns
    -------
    minVal : float
        The item in the listToSearch that is closest to val
    minI : int
        The index of the item in listToSearch that is closest to val. Returned if indx=True.

    """
    d = float("inf")
    minVal = None
    minI = None
    for i, item in enumerate(listToSearch):
        if abs(item - val) < d:
            d = abs(item - val)
            minVal = item
            minI = i
    if indx:
        return minVal, minI
    else:
        # backwards compatibility
        return minVal


# TODO: move into pathTools
def cleanPath(path):
    r"""
    Recursively delete a path.

    !!! careful with this !!! It can delete the entire cluster.

    We add copious os.path.exists checks in case an MPI set of things is trying to delete everything at the same time.
    Always check filenames for some special flag when calling this, especially
    with full permissions on the cluster. You could accidentally delete everyone's work
    with one misplaced line! This doesn't ask questions.

    Safety nets include a whitelist of paths.

    This makes use of shutil.rmtree and os.remove

    Returns
    -------
    success : bool
        True if file was deleted. False if it was not.

    """
    valid = False
    if os.path.exists(path):
        runLog.extra("Clearing all files in {}".format(path))
    else:
        runLog.extra("Nothing to clean in {}. Doing nothing. ".format(path))
        return True
    for validPath in [
        "users",
        "shufflebranches",
        "snapshot",
        "failedruns",
        "armiruns",
        "mc2run",
        "tests",
        "mongoose",
    ]:
        if validPath in path.lower():
            valid = True

    if not valid:
        raise Exception(
            "Thou shalt not try to delete folders other than things in Users. Thou tried to delete {0}"
            "".format(path)
        )

    for i in range(3):
        try:
            if os.path.exists(path) and os.path.isdir(path):
                shutil.rmtree(path)
            elif not os.path.isdir(path):
                # it's just a file. Delete it.
                os.remove(path)
        except:
            if i == 2:
                pass
            # in case the OS is behind or something
            time.sleep(0.1)
        time.sleep(0.3)
        if not os.path.exists(path):
            break
        time.sleep(0.3)

    if os.path.exists(path):
        return False
    else:
        return True


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


def linearInterpolation(x0, y0, x1, y1, targetX=None, targetY=None):
    r"""
    does a linear interpolation (or extrapolation) for y=f(x)

    Parameters
    ----------
    x0,y0,x1,y1 : float
        Coordinates of two points to interpolate between

    targetX : float, optional
        X value to evaluate the line at

    targetY : float, optional
        Y value we want to find the x value for (inverse interpolation)

    Returns
    -------
    interpY : float
        The value of y(targetX), if targetX is not None

    interpX : float
        The value of x where y(x) = targetY (if targetY is not None)

    y = m(x-x0) + b

    x = (y-b)/m

    """

    if x1 == x0:
        raise ZeroDivisionError("The x-values are identical. Cannot interpolate.")

    m = (y1 - y0) / (x1 - x0)
    b = -m * x0 + y0

    if targetX is not None:
        return m * targetX + b
    else:
        return (targetY - b) / m


def parabolaFromPoints(p1, p2, p3):
    r"""
    find the parabola that passes through three points

    We solve a simultaneous equation with three points.

    A = x1**2 x1 1
        x2**2 x2 1
        x3**2 x3 1

    b = y1
        y2
        y3

    find coefficients Ax=b

    Parameters
    ----------
    p1 : tuple
        first point (x,y) coordinates
    p2,p3: tuple, second and third points.

    Returns
    -------
    a,b,c coefficients of y=ax^2+bx+c

    """

    A = numpy.array(
        [[p1[0] ** 2, p1[0], 1], [p2[0] ** 2, p2[0], 1], [p3[0] ** 2, p3[0], 1]]
    )

    b = numpy.array([[p1[1]], [p2[1]], [p3[1]]])
    try:
        x = numpy.linalg.solve(A, b)
    except:
        print("Error in parabola {} {}".format(A, b))
        raise

    return float(x[0]), float(x[1]), float(x[2])


def parabolicInterpolation(ap, bp, cp, targetY):
    r"""
    Given parabola coefficients, this interpolates the time
    that would give k=targetK.

    keff = at^2+bt+c
    We want to solve a*t^2+bt+c-targetK = 0.0 for time.
    if there are real roots, we should probably take the smallest one
    because the larger one might be at very high burnup.
    If there are no real roots, just take the point where the deriv ==0, or
    2at+b=0, so t = -b/2a
    The slope of the curve is the solution to 2at+b at whatever t has been determined

    Parameters
    ----------
    ap, bp,cp : floats
        coefficients of a parabola y = ap*x^2 + bp*x + cp

    targetK : float
        The keff to find the cycle length of

    Returns
    -------
    realRoots : list of tuples
        (root, slope)
        The best guess of the cycle length that will give k=targetK
        If no positive root was found, this is the maximum of the curve. In that case,
        it will be a negative number. If there are two positive roots, there will be two entries.

        slope : float
            The slope of the keff vs. time curve at t=newTime

    """
    roots = numpy.roots([ap, bp, cp - targetY])
    realRoots = []
    for r in roots:
        if r.imag == 0 and r.real > 0:
            realRoots.append((r.real, 2.0 * ap * r.real + bp))

    if not realRoots:
        # no positive real roots. Take maximum and give up for this cyclic.
        newTime = -bp / (2 * ap)
        if newTime < 0:
            raise RuntimeError("No positive roots or maxima.")
        slope = 2.0 * ap * newTime + bp
        newTime = (
            -newTime
        )  # return a negative newTime to signal that it is not expected to be critical.
        realRoots = [(newTime, slope)]

    return realRoots


def getFloat(val):
    r"""returns float version of val, or None if it's impossible. Useful for converting
    user-input into floats when '' might be possible. """
    try:
        newVal = float(val)
        return newVal
    except:
        return None


def relErr(v1, v2):
    if v1:
        return (v2 - v1) / v1
    else:
        return -1e99


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
                # traceback.print_exc(limit=0,file=sys.stdout)


def tryPickleOnAllContents2(*args, **kwargs):
    # helper
    print(doTestPickleOnAllContents2(*args, **kwargs))


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
    The big guns. This will find your pickle errors if all else fails.

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
    """
    Count the number of instances of each class contained in an objects heirarchy.
    """
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
    Returns a list of values who's sum is equal to the value specified.
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


def newtonsMethod(
    func, goal, guess, maxIterations=None, cs=None, positiveGuesses=False
):
    r"""
    Solves a Newton's method with the given function, goal value, and first guess.

    Parameters
    ----------
    func : function
        The function that guess will be changed to try to make it return the goal value.

    goal : float
        The function will be changed until it's return equals this value.

    guess : float
        The first guess value to do Newton's method on the func.

    maxIterations : int
        The maximum number of iterations that the Newton's method will be allowed to perform.


    Returns
    -------
    ans : float
        The guess that when input to the func returns the goal.

    """

    def goalFunc(guess, func, positiveGuesses):
        if positiveGuesses is True:
            guess = abs(guess)
        funcVal = func(guess)
        val = abs(goal - funcVal)
        return val

    if (maxIterations is None) and (cs is not None):
        maxIterations = cs["maxNewtonsIterations"]

    # try:
    ans = float(
        sciopt.newton(
            goalFunc,
            guess,
            args=(func, positiveGuesses),
            tol=1.0e-3,
            maxiter=maxIterations,
        )
    )

    if positiveGuesses is True:
        ans = abs(ans)

    return ans


def minimizeScalarFunc(
    func,
    goal,
    guess,
    maxIterations=None,
    cs=None,
    positiveGuesses=False,
    method=None,
    tol=1.0e-3,
):
    r"""
    Use scipy minimize with the given function, goal value, and first guess.

    Parameters
    ----------
    func : function
        The function that guess will be changed to try to make it return the goal value.

    goal : float
        The function will be changed until it's return equals this value.

    guess : float
        The first guess value to do Newton's method on the func.

    maxIterations : int
        The maximum number of iterations that the Newton's method will be allowed to perform.


    Returns
    -------
    ans : float
        The guess that when input to the func returns the goal.

    """

    def goalFunc(guess, func, positiveGuesses):
        if positiveGuesses is True:
            guess = abs(guess)
        funcVal = func(guess)
        val = abs(goal - funcVal)
        return val

    if (maxIterations is None) and (cs is not None):
        maxIterations = cs["maxNewtonsIterations"]

    X = sciopt.minimize(
        goalFunc,
        guess,
        args=(func, positiveGuesses),
        method=method,
        tol=tol,
        options={"maxiter": maxIterations},
    )
    ans = float(X["x"])
    if positiveGuesses is True:
        ans = abs(ans)

    return ans


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
        path=armi.__path__, prefix=armi.__name__ + "."
    ):
        try:
            mod = importlib.import_module(name)
            if funcName in dir(mod):  # there is a module.funcName. so call it.
                func = getattr(mod, funcName)
                func(*args, **kwargs)
        except:
            # just print traceback but don't throw an error.
            traceback.print_exc()


# TODO: move to pathTools
def mkdir(dirname):
    r"""
    Keeps trying to make a directory, outputting whatever errors it encounters,
    until it is successful.

    Parameters
    ----------
    dirname : str
        Path to the directory to create.
        What you would normally pass to os.mkdir.

    """
    numTimesTried = 0
    while numTimesTried < 1000:
        try:
            os.mkdir(dirname)
            break

        except Exception as err:
            numTimesTried += 1
            # Only ouput err every 10 times.
            if numTimesTried % 10 == 0:
                print(err)
            # Wait 0.5 seconds, try again.
            time.sleep(0.5)


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


def capStrLen(string, length):
    """
    Truncates a string to a certain length.

    Adds '...' if it's too long.

    Parameters
    ----------
    string : str
        The string to cap at length l.
    length : int
        The maximum length of the string s.
    """
    if length <= 2:
        raise Exception("l must be at least 3 in utils.capStrLen")

    if len(string) <= length:
        return string

    return string[0 : length - 3] + "..."


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


def rotateXY(x, y, degreesCounterclockwise=None, radiansCounterclockwise=None):
    """
    Rotates x, y coordinates

    Parameters
    ----------
    x, y : array_like
        coordinates

    degreesCounterclockwise : float
        Degrees to rotate in the CCW direction

    radiansCounterclockwise : float
        Radians to rotate in the CCW direction

    Returns
    -------
    xr, yr : array_like
        the rotated coordinates.
    """

    if radiansCounterclockwise is None:
        radiansCounterclockwise = degreesCounterclockwise * math.pi / 180.0

    sinT = math.sin(radiansCounterclockwise)
    cosT = math.cos(radiansCounterclockwise)
    rotationMatrix = numpy.array([[cosT, -sinT], [sinT, cosT]])
    xr, yr = rotationMatrix.dot(numpy.vstack((x, y)))
    if len(xr) > 1:
        ## Convert to lists because everyone prefers lists for some reason
        return xr.tolist(), yr.tolist()
    else:
        ## Convert to scalar for consistency with old implementation
        return xr[0], yr[0]


def convertToSlice(x, increment=False):
    """
    Convert a int, float, list of ints or floats, None, or slice
    to a slice. Also optionally increments that slice to make it easy to line
    up lists that don't start with 0.

    Use this with numpy.array (numpy.ndarray) types to easily get selections of it's elements.

    Parameters
    ----------
    x : multiple types allowed.
        int: select one index.
        list of int: select these index numbers.
        None: select all indices.
        slice: select this slice

    Returns
    -------
    slice : slice
        Returns a slice object that can be used in an array
        like a[x] to select from its members.
        Also, the slice has its index numbers decremented by 1.
        It can also return a numpy array, which can be used
        to slice other numpy arrays in the same way as a slice.

    Examples
    --------
    a = numpy.array([10, 11, 12, 13])

    >>> convertToSlice(2)
    slice(2, 3, None)
    >>> a[convertToSlice(2)]
    array([12])

    >>> convertToSlice(2, increment=-1)
    slice(1, 2, None)
    >>> a[convertToSlice(2, increment=-1)]
    array([11])

    >>> a[convertToSlice(None)]
    array([10, 11, 12, 13])


    >>> a[utils.convertToSlice([1, 3])]
    array([11, 13])


    >>> a[utils.convertToSlice([1, 3], increment=-1)]
    array([10, 12])

    >>> a[utils.convertToSlice(slice(2, 3, None), increment=-1)]
    array([11])

    """
    if increment is False:
        increment = 0

    if not isinstance(increment, int):
        raise Exception("increment must be False or an integer in utils.convertToSlice")

    if x is None:
        x = numpy.s_[:]

    if isinstance(x, list):
        x = numpy.array(x)

    if isinstance(x, (int, numpy.integer)) or isinstance(x, (float, numpy.floating)):
        x = slice(int(x), int(x) + 1, None)

    # Correct the slice indices to be group instead of index based.
    # The energy groups are 1..x and the indices are 0..x-1.
    if isinstance(x, slice):
        if x.start is not None:
            jstart = x.start + increment
        else:
            jstart = None

        if x.stop is not None:
            if isinstance(x.stop, list):
                jstop = [x + increment for x in x.stop]
            else:
                jstop = x.stop + increment
        else:
            jstop = None

        jstep = x.step

        return numpy.s_[jstart:jstop:jstep]

    elif isinstance(x, numpy.ndarray):
        return numpy.array([i + increment for i in x])

    else:
        raise Exception(
            (
                "It is not known how to handle x type: " "{0} in utils.convertToSlice"
            ).format(type(x))
        )


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
    """
    Plots a matrix
    """
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
    plt.imshow(
        matrix, cmap=cmap, norm=norm, interpolation="nearest"
    )  # or bicubic or nearest#,vmin=0, vmax=300)
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


def userName():
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


def expandRepeatedFloats(repeatedList):
    """
    Return an expanded repeat list.

    Notes
    -----
    R char is valid for showing the number of repeats in MCNP. For examples the list:
    [150,  200, '9R']
    indicates a 150 day cycle followed by 10 200 day cycles.
    """
    nonRepeatList = []
    for val in repeatedList:
        isRepeat = False
        if isinstance(val, str):
            val = val.upper()
            if val.count("R") > 1:
                raise ValueError("List had strings that were not repeats")
            elif "R" in val:
                val = val.replace("R", "")
                isRepeat = True
        if isRepeat:
            nonRepeatList += [nonRepeatList[-1]] * int(val)
        else:
            nonRepeatList.append(float(val))
    return nonRepeatList


def getStepsFromValues(values, prevValue=0.0):
    """Convert list of floats to list of steps between each float."""
    steps = []
    for val in values:
        currentVal = float(val)
        steps.append(currentVal - prevValue)
        prevValue = currentVal
    return steps


def average1DWithinTolerance(vals, tolerance=0.2):
    """
    Compute the average of a series of arrays with a tolerance.

    Tuned for averaging assembly meshes or block heights.

    Parameters
    ----------
    vals : 2D numpy.array
        could be assembly x axial mesh tops or heights
    """
    vals = numpy.array(vals)

    filterOut = numpy.array([False])  # this gets discarded
    while not filterOut.all():  # 20% difference is the default tolerance
        avg = vals.mean(axis=0)  # average over all columns
        diff = abs(vals - avg) / avg  # no nans, because all vals are non-zero
        filterOut = (diff > tolerance).sum(
            axis=1
        ) == 0  # True = 1, sum across axis means any height in assem is off
        vals = vals[filterOut]  # filter anything that is skewing

    if vals.size == 0:
        raise ValueError("Nothing was near the mean, there are no acceptable values!")

    if (avg <= 0.0).any():
        raise ValueError(
            "A non-physical value (<=0) was computed, but this is not possible.\n"
            "Values: {}\navg: {}".format(vals, avg)
        )

    return avg


def findNearestValue(searchList, searchValue):
    """Search a given list for the value that is closest to the given search value."""
    return findNearestValueAndIndex(searchList, searchValue)[0]


def findNearestValueAndIndex(searchList, searchValue):
    """Search a given list for the value that is closest to the given search value. Return a tuple
    containing the value and its index in the list."""
    searchArray = numpy.array(searchList)
    closestValueIndex = (numpy.abs(searchArray - searchValue)).argmin()
    return searchArray[closestValueIndex], closestValueIndex


class MergeableDict(dict):
    """
    Overrides python dictionary and implements a merge method.

    Notes
    -----
    Allows multiple dictionaries to be combined in a single line
    """

    def merge(self, *otherDictionaries):
        for dictionary in otherDictionaries:
            self.update(dictionary)


shutil_copy = shutil.copy


def safeCopy(src, dst):
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


shutil.copy = safeCopy
