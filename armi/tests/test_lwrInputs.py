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
from logging import WARNING
import os
import unittest

import numpy as np

from armi import Mode
from armi import runLog
from armi import init as armi_init
from armi.bookkeeping import db
from armi.reactor.flags import Flags
from armi.tests import mockRunLogs
from armi.tests import TEST_ROOT
from armi.utils import directoryChangers

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
        (Also, check that we are getting warnings when reading the YAML).
        """
        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock.getStdout())
            runLog.LOG.startLog("test_loadC5G7")
            runLog.LOG.setVerbosity(WARNING)

            # ingest the settings file
            Mode.setMode(Mode.BATCH)
            o = armi_init(fName=TEST_INPUT_TITLE + ".yaml")
            b = o.r.core.getFirstBlock(Flags.MOX)

            # test warnings are being logged for malformed isotopics info in the settings file
            streamVal = mock.getStdout()
            self.assertIn("UraniumOxide", streamVal, msg=streamVal)
            self.assertIn("SaturatedWater", streamVal, msg=streamVal)

            # test that there are 100 of each high, medium, and low MOX pins
            fuelPinsHigh = b.getComponent(Flags.HIGH | Flags.MOX)
            self.assertEqual(fuelPinsHigh.getDimension("mult"), 100)

            # test the Guide Tube dimensions
            gt = b.getComponent(Flags.GUIDE_TUBE)
            self.assertEqual(gt.getDimension("mult"), 24)
