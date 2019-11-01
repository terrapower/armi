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


import itertools


def colorGenerator(skippedColors=10):
    """
    Selects a color from the built-in wx color database.

    Parameters
    ----------
    skippedColors: int
        Number of colors to skip in the built-in wx color database when generating the next color. Without skipping
        colors the next color may be similar to the previous color.

    Notes
    -----
    Will cycle indefinitely to accommodate large cores. Colors will repeat.
    """
    from wx.lib.colourdb import getColourList

    excludedColors = ["WHITE", "CREAM", "BLACK", "MINTCREAM"]
    colors = getColourList()
    for start in itertools.cycle(range(20, 20 + skippedColors)):
        for i in range(start, len(colors), skippedColors):
            if colors[i] not in excludedColors:
                yield colors[i]
