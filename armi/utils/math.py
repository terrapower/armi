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

"""various, helpful math utilities"""
import numpy as np


def resampleStepwise(xin, yin, xout, method="avg"):
    """TODO"""
    # TODO: assuming xin and xout start and end at the same place
    assert xin[0] == xout[0] and xin[-1] == xout[-1]

    # TODO: yin must be 1 shorter than xin
    assert (len(xin) - 1) == len(yin)

    bins = np.digitize(xout, bins=xin)
    print("bins", bins)

    yout = []
    for i in range(1, len(bins)):
        chunk = yin[bins[i - 1] - 1 : bins[i]]
        length = xin[bins[i - 1] - 1 : bins[i] + 1]
        length = [length[j] - length[j - 1] for j in range(1, len(length))]

        print("\n==== Chunk ", chunk)
        print("    LENGTH", length)

        if not len(chunk):
            yout.append(0)
            continue

        if xout[i] < xin[min(bins[i], len(xin) - 1)]:
            print("--------- trimming right")
            fraction = (xout[i] - xin[bins[i] - 1]) / (xin[bins[i]] - xin[bins[i] - 1])
            if not fraction:
                chunk = chunk[:-1]
                length = length[:-1]
            else:
                chunk[-1]  # *= fraction
                length[-1] *= fraction
            print("trim right side: ", chunk, length)

        if xout[i - 1] > xin[bins[i - 1] - 1]:
            print("--------- trimming left")
            fraction = (xin[bins[i - 1]] - xout[i - 1]) / (
                xin[bins[i - 1]] - xin[bins[i - 1] - 1]
            )
            if not fraction:
                chunk = chunk[1:]
                length = length[1:]
            else:
                chunk[0]  # *= fraction
                length[0] *= fraction
            print("trim left side: ", chunk, length)

        print("final chunk", chunk)
        print("final length", length)
        assert len(length) == len(chunk)

        weighted_sum = sum([c * l for c, l in zip(chunk, length)])
        print(weighted_sum, sum(length))
        yout.append(weighted_sum / sum(length))

    return yout
