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
