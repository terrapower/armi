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

"""various math utilities"""
import numpy as np


def resampleStepwise(xin, yin, xout, method="avg"):
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

    method : str, optional
        By default, this method resamples to average values,
        but using "sum" here will resample to a conservation
        of the total value.
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
            if not fraction:
                chunk = chunk[:-1]
                length = length[:-1]
            elif method == "sum":
                chunk[-1] *= fraction
            else:
                length[-1] *= fraction

        # trim any partial left-side bins
        if xout[i - 1] > xin[start - 1]:
            fraction = (xin[start] - xout[i - 1]) / (xin[start] - xin[start - 1])
            if not fraction:
                chunk = chunk[1:]
                length = length[1:]
            elif method == "sum":
                chunk[0] *= fraction
            else:
                length[0] *= fraction

        # return the sum or the average
        if method == "sum":
            yout.append(sum(chunk))
        else:
            weighted_sum = sum([c * l for c, l in zip(chunk, length)])
            yout.append(weighted_sum / sum(length))

    return yout
