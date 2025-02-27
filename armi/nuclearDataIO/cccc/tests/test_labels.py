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

"""Test the reading and writing of the DIF3D/VARIANT LABELS interface file."""

import os
import unittest

from armi.nuclearDataIO.cccc import labels
from armi.utils.directoryChangers import TemporaryDirectoryChanger

THIS_DIR = os.path.dirname(__file__)

LABELS_FILE_BIN = os.path.join(THIS_DIR, "fixtures", "labels.binary")
LABELS_FILE_ASCII = os.path.join(THIS_DIR, "fixtures", "labels.ascii")


class TestLabels(unittest.TestCase):
    """Tests for labels."""

    def test_readLabelsBinary(self):
        expectedName = "LABELS"
        expectedTrianglesPerHex = 6
        expectedNumZones = 5800
        expectedNumRegions = 2900
        expectedNumHexagonalRings = 13
        labelsData = labels.readBinary(LABELS_FILE_BIN)
        self.assertEqual(labelsData.metadata["hname"], expectedName)
        self.assertEqual(labelsData.metadata["numTrianglesPerHex"], expectedTrianglesPerHex)
        self.assertEqual(labelsData.metadata["numZones"], expectedNumZones)
        self.assertEqual(labelsData.metadata["numRegions"], expectedNumRegions)
        self.assertEqual(labelsData.metadata["numHexagonalRings"], expectedNumHexagonalRings)
        self.assertEqual(len(labelsData.regionLabels), expectedNumRegions)

    def test_writeLabelsAscii(self):
        with TemporaryDirectoryChanger():
            labelsData = labels.readBinary(LABELS_FILE_BIN)
            labels.writeAscii(labelsData, self._testMethodName + "labels.ascii")
            with open(self._testMethodName + "labels.ascii", "r") as f:
                actualData = f.read().splitlines()
            with open(LABELS_FILE_ASCII) as f:
                expectedData = f.read().splitlines()
            for expected, actual in zip(expectedData, actualData):
                self.assertEqual(expected, actual)
