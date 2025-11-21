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

import os
import unittest
from logging import WARNING

from armi import runLog
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.testing import TESTING_ROOT
from armi.tests import mockRunLogs
from armi.utils import directoryChangers

TEST_INPUT_TITLE = "c5g7-settings.yaml"


class C5G7ReactorTests(unittest.TestCase):
    def setUp(self):
        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

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

            # load the reactor
            _o, r = test_reactors.loadTestReactor(
                os.path.join(TESTING_ROOT, "c5g7"),
                inputFileName=TEST_INPUT_TITLE,
            )

            # test warnings are being logged for malformed isotopics info in the settings file
            streamVal = mock.getStdout()
            self.assertIn("Case Information", streamVal, msg=streamVal)
            self.assertIn("Input File", streamVal, msg=streamVal)

            # test that there are 100 of each high, medium, and low MOX pins
            b = r.core.getFirstBlock(Flags.MOX)
            fuelPinsHigh = b.getComponent(Flags.HIGH | Flags.MOX)
            self.assertEqual(fuelPinsHigh.getDimension("mult"), 100)

            # test the Guide Tube dimensions
            gt = b.getComponent(Flags.GUIDE_TUBE)
            self.assertEqual(gt.getDimension("mult"), 24)
