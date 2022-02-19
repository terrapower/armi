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
import numpy as np


# TODO: 0. JOHN! Find any unused and remove them.
# TODO: 1. JOHN! Look for unit tests, and move them into test_math.py.
# TODO: 2. JOHN! Find imports within ARMI and fix them.


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


def findNearestValue(searchList, searchValue):
    """Search a given list for the value that is closest to the given search value."""
    return findNearestValueAndIndex(searchList, searchValue)[0]


def findNearestValueAndIndex(searchList, searchValue):
    """Search a given list for the value that is closest to the given search value. Return a tuple
    containing the value and its index in the list."""
    searchArray = numpy.array(searchList)
    closestValueIndex = (numpy.abs(searchArray - searchValue)).argmin()
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


def relErr(v1: float, v2: float) -> float:
    """TODO JOHN"""
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
        if None in chunk:
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
    rotationMatrix = numpy.array([[cosT, -sinT], [sinT, cosT]])
    xr, yr = rotationMatrix.dot(numpy.vstack((x, y)))
    if len(xr) > 1:
        # Convert to lists because everyone prefers lists for some reason
        return xr.tolist(), yr.tolist()
    else:
        # Convert to scalar for consistency with old implementation
        return xr[0], yr[0]
