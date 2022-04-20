# Copyright 2022 TerraPower, LLC
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

"""Various math utilities"""
import math
import re

import numpy as np
import scipy.optimize as sciopt

# special pattern to deal with FORTRAN-produced scipats without E, like 3.2234-234
SCIPAT_SPECIAL = re.compile(r"([+-]?\d*\.\d+)[eEdD]?([+-]\d+)")


def average1DWithinTolerance(vals, tolerance=0.2):
    """
    Compute the average of a series of arrays with a tolerance.

    Tuned for averaging assembly meshes or block heights.

    Parameters
    ----------
    vals : 2D np.array
        could be assembly x axial mesh tops or heights
    """
    vals = np.array(vals)

    filterOut = np.array([False])  # this gets discarded
    while not filterOut.all():  # 20% difference is the default tolerance
        avg = vals.mean(axis=0)  # average over all columns
        diff = abs(vals - avg) / avg  # no nans, because all vals are non-zero
        # True = 1, sum across axis means any height in assem is off
        filterOut = (diff > tolerance).sum(axis=1) == 0
        vals = vals[filterOut]  # filter anything that is skewing

    if vals.size == 0:
        raise ValueError("Nothing was near the mean, there are no acceptable values!")

    if (avg <= 0.0).any():
        raise ValueError(
            "A non-physical value (<=0) was computed, but this is not possible.\n"
            "Values: {}\navg: {}".format(vals, avg)
        )

    return avg


def convertToSlice(x, increment=False):
    """
    Convert a int, float, list of ints or floats, None, or slice
    to a slice. Also optionally increments that slice to make it easy to line
    up lists that don't start with 0.

    Use this with np.array (np.ndarray) types to easily get selections of it's elements.

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
    a = np.array([10, 11, 12, 13])

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
        x = np.s_[:]

    if isinstance(x, list):
        x = np.array(x)

    if isinstance(x, (int, np.integer)) or isinstance(x, (float, np.floating)):
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

        return np.s_[jstart:jstop:jstep]

    elif isinstance(x, np.ndarray):
        return np.array([i + increment for i in x])

    else:
        raise Exception(
            (
                "It is not known how to handle x type: " "{0} in utils.convertToSlice"
            ).format(type(x))
        )


def efmt(a: str) -> str:
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


def findNearestValue(searchList, searchValue):
    """Search a given list for the value that is closest to the given search value."""
    return findNearestValueAndIndex(searchList, searchValue)[0]


def findNearestValueAndIndex(searchList, searchValue):
    """Search a given list for the value that is closest to the given search value. Return a tuple
    containing the value and its index in the list."""
    searchArray = np.array(searchList)
    closestValueIndex = (np.abs(searchArray - searchValue)).argmin()
    return searchArray[closestValueIndex], closestValueIndex


def fixThreeDigitExp(strToFloat: str) -> float:
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

    This helps when the scientific number exponent does not fit.
    """
    match = SCIPAT_SPECIAL.match(strToFloat)
    return float("{}E{}".format(*match.groups()))


def getFloat(val):
    r"""returns float version of val, or None if it's impossible. Useful for converting
    user-input into floats when '' might be possible."""
    try:
        newVal = float(val)
        return newVal
    except:
        return None


def getStepsFromValues(values, prevValue=0.0):
    """Convert list of floats to list of steps between each float."""
    steps = []
    for val in values:
        currentVal = float(val)
        steps.append(currentVal - prevValue)
        prevValue = currentVal
    return steps


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
    A = np.array(
        [[p1[0] ** 2, p1[0], 1], [p2[0] ** 2, p2[0], 1], [p3[0] ** 2, p3[0], 1]]
    )

    b = np.array([[p1[1]], [p2[1]], [p3[1]]])

    try:
        x = np.linalg.solve(A, b)
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
    roots = np.roots([ap, bp, cp - targetY])
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


def relErr(v1: float, v2: float) -> float:
    """find the relative error between to numbers"""
    if v1:
        return (v2 - v1) / v1
    else:
        return -1e99


def resampleStepwise(xin, yin, xout, avg=True):
    """
    Resample a piecewise-defined step function from one set of mesh points
    to another. This is useful for reallocating values along a given axial
    mesh (or assembly of blocks).

    Parameters
    ----------
    xin : list
        interval points / mesh points

    yin : list
        interval values / inter-mesh values

    xout : list
        new interval points / new mesh points

    avg : bool
        By default, this is set to True, forcing the resampling to be done
        by averaging. But if this is False, the resmampling will be done by
        summation, to try and preserve the totals after resampling.
    """
    # validation: there must be one more mesh point than inter-mesh values
    assert (len(xin) - 1) == len(yin)

    # find out in which xin bin each xout value lies
    bins = np.digitize(xout, bins=xin)

    # loop through xout / the xout bins
    yout = []
    for i in range(1, len(bins)):
        start = bins[i - 1]
        end = bins[i]
        chunk = yin[start - 1 : end]
        length = xin[start - 1 : end + 1]
        length = [length[j] - length[j - 1] for j in range(1, len(length))]

        # if the xout lies outside the xin range
        if not len(chunk):
            yout.append(0)
            continue

        # trim any partial right-side bins
        if xout[i] < xin[min(end, len(xin) - 1)]:
            fraction = (xout[i] - xin[end - 1]) / (xin[end] - xin[end - 1])
            if fraction == 0:
                chunk = chunk[:-1]
                length = length[:-1]
            elif avg:
                length[-1] *= fraction
            else:
                chunk[-1] *= fraction

        # trim any partial left-side bins
        if xout[i - 1] > xin[start - 1]:
            fraction = (xin[start] - xout[i - 1]) / (xin[start] - xin[start - 1])
            if fraction == 0:
                chunk = chunk[1:]
                length = length[1:]
            elif avg:
                length[0] *= fraction
            else:
                chunk[0] *= fraction

        # return the sum or the average
        if [1 for c in chunk if (not hasattr(c, "__len__") and c is None)]:
            yout.append(None)
        elif avg:
            weighted_sum = sum([c * l for c, l in zip(chunk, length)])
            yout.append(weighted_sum / sum(length))
        else:
            yout.append(sum(chunk))

    return yout


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
    rotationMatrix = np.array([[cosT, -sinT], [sinT, cosT]])
    xr, yr = rotationMatrix.dot(np.vstack((x, y)))
    if len(xr) > 1:
        # Convert to lists because everyone prefers lists for some reason
        return xr.tolist(), yr.tolist()
    else:
        # Convert to scalar for consistency with old implementation
        return xr[0], yr[0]
