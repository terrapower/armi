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
"""Tests for C5G7 input files."""
import unittest
import os

import numpy

from armi.utils import directoryChangers
from armi.tests import TEST_ROOT
from armi.reactor.flags import Flags
from armi import init as armi_init
from armi.bookkeeping import db

TEST_INPUT_TITLE = "c5g7-settings"


class C5G7ReactorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):

        cls.directoryChanger = directoryChangers.DirectoryChanger(
            os.path.join(TEST_ROOT, "tutorials")
        )
        cls.directoryChanger.open()

    @classmethod
    def tearDownClass(cls):
        cls.directoryChanger.close()

    def test_loadC5G7(self):
        """
        Load the C5G7 case from input and check basic counts.
        """
        o = armi_init(fName=TEST_INPUT_TITLE + ".yaml")
        b = o.r.core.getFirstBlock(Flags.MOX)
        # there are 100 of each high, medium, and low MOX pins
        fuelPinsHigh = b.getComponent(Flags.HIGH | Flags.MOX)
        self.assertEqual(fuelPinsHigh.getDimension("mult"), 100)

        gt = b.getComponent(Flags.GUIDE_TUBE)
        self.assertEqual(gt.getDimension("mult"), 24)

    def test_runAndLoadC5G7(self):
        """
        Run C5G7 in basic no-op app and load from the result from DB.

        This ensures that these kinds of cases can be read from DB.
        """

        def _loadLocs(o, locs):
            for b in o.r.core.getBlocks():
                indices = b.spatialLocator.getCompleteIndices()
                locs[indices] = b.spatialLocator.getGlobalCoordinates()

        o = armi_init(fName=TEST_INPUT_TITLE + ".yaml")
        locsInput, locsDB = {}, {}
        _loadLocs(o, locsInput)
        o.operate()
        o2 = db.loadOperator(TEST_INPUT_TITLE + ".h5", 0, 0)
        _loadLocs(o2, locsDB)

        for indices, coordsInput in sorted(locsInput.items()):
            coordsDB = locsDB[indices]
            self.assertTrue(numpy.allclose(coordsInput, coordsDB))
