# Copyright 2026 TerraPower, LLC
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

"""Test rough matProps performance timing."""

import copy
import os
import pickle
import timeit
import unittest

import armi.matProps

# NOTE: This is a sketchy magic number for testing that are heavily machine dependent.
_LIMIT_SECONDS = 15


class TestPerformance(unittest.TestCase):
    """
    The tests in this class are an early warning of matProps performance changes. It tests common operations that are
    done with matProps to ensure their execution time remains in the correct ballpark.
    """

    def test_load(self):
        """Tests the speed of loading a set of material files."""
        armi.matProps.clear()

        testFiles = os.path.join(os.path.dirname(__file__), "testMaterialsData")

        t = timeit.timeit(lambda: (armi.matProps.loadAll(testFiles), armi.matProps.clear()), number=10)

        self.assertLess(t, _LIMIT_SECONDS, msg="matProps material loading takes too long to execute.")

    def test_pickle(self):
        """Tests the speed of pickling a set of material files. Pickling is important for multiprocessing."""
        armi.matProps.clear()

        # This directory's material has many properties so it is more representative for pickle size.
        testFiles = os.path.join(os.path.dirname(__file__), "testDir4")
        armi.matProps.loadAll(testFiles)
        mat = armi.matProps.getMaterial("sampleProperty")

        t = timeit.timeit(lambda: pickle.loads(pickle.dumps(mat)), number=100)

        self.assertLess(t, _LIMIT_SECONDS, msg="matProps material pickling takes too long to execute.")

    def test_calc(self):
        """Tests the speed of calculating a property value."""
        armi.matProps.clear()

        testFiles = os.path.join(os.path.dirname(__file__), "testMaterialsData")
        armi.matProps.loadAll(testFiles)
        # This material's density is a linear function.
        mat = armi.matProps.getMaterial("materialA")
        prop = mat.rho

        t = timeit.timeit(lambda: prop.calc({"T": 300}), number=10000)

        self.assertLess(t, _LIMIT_SECONDS, msg="matProps material calculation takes too long to execute.")

    def test_deepcopy(self):
        """
        Tests the speed of deepcopying a material. Copying is important for copying other objects that may be
        referencing a matProps material.
        """
        armi.matProps.clear()

        # This directory's material has many properties so it is more representative for copy size.
        testFiles = os.path.join(os.path.dirname(__file__), "testDir4")
        armi.matProps.loadAll(testFiles)
        mat = armi.matProps.getMaterial("sampleProperty")

        t = timeit.timeit(lambda: copy.deepcopy(mat), number=100)

        self.assertLess(t, _LIMIT_SECONDS, msg="matProps material copying takes too long to execute.")
