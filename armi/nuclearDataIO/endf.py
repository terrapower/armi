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

"""
Translates things like MT and MF numbers to meaningful information.

Source: http://www.nndc.bnl.gov/exfor/help7.jsp
"""

import re


def loadMTNums(fName):
    """
    Loads MT number descriptions from a data file

    Builds a dictionary with MT num keys (int) and (symbol,description) tuples of string vals
    """
    f = open(fName)
    mtNums = {}
    for line in f:
        if not re.search(r"^\d", line):
            # skip the headers
            continue
        items = line.split()

        nums = getNums(items[0])
        symbol = getMTSymbol(items[1])
        if symbol:
            desc = " ".join(items[2:])
        else:
            desc = " ".join(items[1:])

        for n in nums:
            mtNums[n] = (symbol, desc)

    return mtNums


def loadMFNums(fName):
    """
    Builds MF number descriptions from data file.

    """

    f = open(fName)
    mfNums = {}
    for line in f:
        if not re.search("^\d", line):
            # skip the headers
            continue
        items = line.split()

        nums = getNums(items[0])
        symbol = getMFSymbol(items[1])
        desc = " ".join(items[2:])

        for n in nums:
            mfNums[n] = (symbol, desc)

    return mfNums


def getNums(numStr):
    """
    Extract number or range of numbers from data file

    Examples
    --------
    >>> getNums('4')
    [4]
    >>> getNums('4-7')
    [4,5,6,7]


    """
    if "-" in numStr:
        # range of numbers
        nums = [int(n) for n in numStr.split("-")]
        nums = range(nums[0], nums[1] + 1)
    else:
        nums = [int(numStr)]  # just one number. Keep in list to be general.

    return nums


def getMTSymbol(symStr):
    """
    Extract number or range of numbers from data file

    Examples
    --------
    >>> getSymbol('n,tc')
    'n,tc'
    >>> getSymbol('Third')
    None

    """

    if "," not in symStr and not re.search("^[A-Z]\d*$", symStr):
        symbol = None
    else:
        symbol = symStr
    return symbol


def getMFSymbol(symStr):
    return symStr
