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
"""Tests for the JaggedArray class."""
import shutil
import subprocess
import unittest

import h5py
import numpy

from armi.bookkeeping.db.jaggedArray import JaggedArray
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class TestJaggedArray(unittest.TestCase):
    """Tests for the JaggedArray class"""

    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    def test_roundTrip(self):
        """Basic test that we handle Nones correctly in database read/writes."""
        dataSet = [1, 2.0, None, [], [3, 4], (5, 6, 7), numpy.array([8, 9, 10, 11])]
        self._compareRoundTrip(dataSet, "test-numbers")

    def test_roundTripBool(self):
        """Basic test that we handle Nones correctly in database read/writes."""
        dataSet = [True, True, [False, True, False]]
        self._compareRoundTrip(dataSet, "test-bool")

    def test_flatten(self):
        """Test the recursive flattening static method"""
        testdata = [(1, 2), [3, 4, 5], [], None, 6, numpy.array([7, 8, 9])]
        flatArray = JaggedArray.flatten(testdata)
        self.assertEqual(flatArray, [1, 2, 3, 4, 5, None, 6, 7, 8, 9])

    def _compareRoundTrip(self, data, paramName):
        """Make sure that data is unchanged by packing/unpacking."""
        jaggedArray = JaggedArray(data, paramName)

        # write to HDF5
        h5file = "test_jaggedArray.h5"
        with h5py.File(h5file, "w") as hf:
            dset = hf.create_dataset(
                data=jaggedArray.flattenedArray,
                name=jaggedArray.paramName,
            )
            dset.attrs["jagged"] = True
            dset.attrs["offsets"] = jaggedArray.offsets
            dset.attrs["shapes"] = jaggedArray.shapes
            dset.attrs["noneLocations"] = jaggedArray.nones

        with h5py.File(h5file, "r") as hf:
            dataset = hf[paramName]
            values = dataset[()]
            offsets = dataset.attrs["offsets"]
            shapes = dataset.attrs["shapes"]
            nones = dataset.attrs["noneLocations"]

        roundTrip = JaggedArray.fromH5(
            values,
            offsets,
            shapes,
            nones,
            dtype=jaggedArray.flattenedArray.dtype,
            paramName=paramName,
        )
        self._compareArrays(data, roundTrip)

    def _compareArrays(self, ref, src):
        """
        Compare two numpy arrays.

        Comparing numpy arrays that may have unsavory data (NaNs, Nones, jagged
        data, etc.) is really difficult. For now, convert to a list and compare
        element-by-element.

        Several types of data do not survive a round trip. The if-elif branch
        here converts the initial data into the format expected to be produced
        by the round trip. The conversions are:

        - For scalar values (int, float, etc.), the data becomes a numpy
          array with a dimension of 1 after the round trip.
        - Tuples and lists become numpy arrays
        - Empty lists become `None`

        """
        # self.assertEqual(type(src), JaggedArray)
        if isinstance(ref, numpy.ndarray):
            ref = ref.tolist()
            src = src.tolist()

        for v1, v2 in zip(ref, src):
            # Entries may be None
            if isinstance(v1, numpy.ndarray):
                v1 = v1.tolist()
            elif isinstance(v1, tuple):
                v1 = list(v1)
            elif isinstance(v1, int):
                v1 = numpy.array([v1])
            elif isinstance(v1, float):
                v1 = numpy.array([v1], dtype=numpy.float64)
            elif v1 is None:
                pass
            elif len(v1) == 0:
                v1 = None

            if isinstance(v2, numpy.ndarray):
                v2 = v2.tolist()

            self.assertEqual(v1, v2)
