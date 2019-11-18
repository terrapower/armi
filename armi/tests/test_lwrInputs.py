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

from armi.utils import directoryChangers
from armi.tests import TEST_ROOT
from armi.reactor.flags import Flags
import armi


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
        Load the C5G7 case and check basic counts.
        """
        o = armi.init(fName="c5g7-settings.yaml")
        b = o.r.core.getFirstBlock(Flags.MOX)
        # there are 100 of each high, medium, and low MOX pins
        fuelPinsHigh = b.getComponent(Flags.HIGH | Flags.MOX)
        self.assertEqual(fuelPinsHigh.getDimension("mult"), 100)

        gt = b.getComponent(Flags.GUIDE_TUBE)
        self.assertEqual(gt.getDimension("mult"), 24)
