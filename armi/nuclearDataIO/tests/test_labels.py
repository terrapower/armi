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
Test the reading and writing of the DIF3D/VARIANT LABELS interface file
"""
import unittest
import os

from armi.nuclearDataIO import labels
from armi.utils import pathTools

THIS_DIR = pathTools.armiAbsDirFromName(__name__)


class TestLabels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._originalDir = os.getcwd()
        os.chdir(THIS_DIR)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._originalDir)

    def test_readLabelsBinary(self):
        expectedName = "LABELS"
        expectedTrianglesPerHex = 6
        expectedNumZones = 5800
        expectedNumRegions = 2900
        expectedNumHexagonalRings = 13
        labelsData = labels.readBinary(os.path.join("labels.binary"))
        self.assertEqual(
            labelsData._metadata["hname"], expectedName
        )  # pylint: disable=protected-access
        self.assertEqual(
            labelsData._metadata["numTrianglesPerHex"], expectedTrianglesPerHex
        )  # pylint: disable=protected-access
        self.assertEqual(
            labelsData._metadata["numZones"], expectedNumZones
        )  # pylint: disable=protected-access
        self.assertEqual(
            labelsData._metadata["numRegions"], expectedNumRegions
        )  # pylint: disable=protected-access
        self.assertEqual(
            labelsData._metadata["numHexagonalRings"], expectedNumHexagonalRings
        )  # pylint: disable=protected-access

    def test_writeLabelsAscii(self):
        labelsData = labels.readBinary("labels.binary")
        labels.writeAscii(labelsData, self._testMethodName + "labels.ascii")
        with open(self._testMethodName + "labels.ascii", "r") as f:
            actualData = f.read().splitlines()
        with open("labels.ascii", "r") as f:
            expectedData = f.read().splitlines()
        for i in range(len(actualData)):
            self.assertEqual(expectedData[i], actualData[i])
        os.remove(self._testMethodName + "labels.ascii")


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'TestLabels.test_writeLabelsAscii']
    unittest.main()
