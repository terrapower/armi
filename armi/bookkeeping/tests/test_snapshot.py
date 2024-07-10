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

"""Test Snapshots."""
import unittest
from unittest.mock import patch

from armi import settings
from armi.bookkeeping import snapshotInterface
from armi.operators.operator import Operator


class MockReactorParams:
    def __init__(self):
        self.cycle = 0
        self.timeNode = 1


class MockReactor:
    def __init__(self, cs):
        self.p = MockReactorParams()
        self.o = Operator(cs)


class TestSnapshotInterface(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.cs = settings.Settings()

    def setUp(self):
        self.cs.revertToDefaults()
        self.si = snapshotInterface.SnapshotInterface(MockReactor(self.cs), self.cs)

    @patch("armi.operators.operator.Operator.snapshotRequest")
    def test_interactEveryNode(self, mockSnapshotRequest):
        newSettings = {}
        newSettings["dumpSnapshot"] = ["000001"]
        self.si.cs = self.si.cs.modified(newSettings=newSettings)
        self.si.interactEveryNode(0, 1)
        self.assertTrue(mockSnapshotRequest.called)

    @patch("armi.operators.operator.Operator.snapshotRequest")
    def test_interactCoupled(self, mockSnapshotRequest):
        newSettings = {}
        newSettings["dumpSnapshot"] = ["000001"]
        self.si.cs = self.si.cs.modified(newSettings=newSettings)
        self.si.interactCoupled(2)
        self.assertTrue(mockSnapshotRequest.called)

    def test_activeateDefaultSnapshots_30cycles2BurnSteps(self):
        """
        Test snapshots for 30 cycles and 2 burnsteps, checking the dumpSnapshot setting.

        .. test:: Allow extra data to be saved from a run, at specified time nodes.
            :id: T_ARMI_SNAPSHOT0
            :tests: R_ARMI_SNAPSHOT
        """
        self.assertEqual([], self.cs["dumpSnapshot"])

        newSettings = {}
        newSettings["nCycles"] = 30
        newSettings["burnSteps"] = 2
        newSettings["cycleLength"] = 365
        self.si.cs = self.si.cs.modified(newSettings=newSettings)
        self.cs = self.si.cs

        self.si.activateDefaultSnapshots()
        self.assertEqual(["000000", "014000", "029002"], self.si.cs["dumpSnapshot"])

    def test_activeateDefaultSnapshots_17cycles5BurnSteps(self):
        """
        Test snapshots for 17 cycles and 5 burnsteps, checking the dumpSnapshot setting.

        .. test:: Allow extra data to be saved from a run, at specified time nodes.
            :id: T_ARMI_SNAPSHOT1
            :tests: R_ARMI_SNAPSHOT
        """
        self.assertEqual([], self.cs["dumpSnapshot"])

        newSettings = {}
        newSettings["nCycles"] = 17
        newSettings["burnSteps"] = 5
        newSettings["cycleLength"] = 365
        self.si.cs = self.si.cs.modified(newSettings=newSettings)
        self.cs = self.si.cs

        self.si.activateDefaultSnapshots()
        self.assertEqual(["000000", "008000", "016005"], self.si.cs["dumpSnapshot"])
