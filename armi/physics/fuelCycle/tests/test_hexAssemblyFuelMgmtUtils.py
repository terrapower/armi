# Copyright 2022 TerraPower, LLC
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
"""Tests some fuel handling tools, specific to hex-assembly reactors."""
import unittest

from armi.physics.fuelCycle import hexAssemblyFuelMgmtUtils as hexUtils
from armi.reactor.tests import test_reactors
from armi.tests import ArmiTestHelper, TEST_ROOT
from armi.utils import directoryChangers


class TestHexAssemMgmtTools(ArmiTestHelper):
    def setUp(self):
        # prepare the input files. This is important so the unit tests run from wherever
        # they need to run from.
        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    def test_buildEqRingScheduleHelper(self):
        numRings = 9
        ringList1 = [1, 5]
        buildRing1 = hexUtils._buildEqRingScheduleHelper(ringList1, numRings)
        self.assertEqual(buildRing1, [1, 2, 3, 4, 5])

        ringList2 = [1, 5, 9, 6]
        buildRing2 = hexUtils._buildEqRingScheduleHelper(ringList2, numRings)
        self.assertEqual(buildRing2, [1, 2, 3, 4, 5, 9, 8, 7, 6])

        ringList3 = [9, 5, 3, 4, 1, 2]
        buildRing3 = hexUtils._buildEqRingScheduleHelper(ringList3, numRings)
        self.assertEqual(buildRing3, [9, 8, 7, 6, 5, 3, 4, 1, 2])

        ringList4 = [2, 5, 1, 1]
        buildRing1 = hexUtils._buildEqRingScheduleHelper(ringList4, numRings)
        self.assertEqual(buildRing1, [2, 3, 4, 5, 1])

    def test_buildEqRingSchedule(self):
        _o, r = test_reactors.loadTestReactor(TEST_ROOT)
        core = r.core

        circularRingOrder = "angle"
        locSchedule = hexUtils.buildEqRingSchedule(core, [2, 1], circularRingOrder)
        self.assertEqual(locSchedule, ["002-001", "002-002", "001-001"])

        circularRingOrder = "distanceSmart"
        locSchedule = hexUtils.buildEqRingSchedule(core, [2, 1], circularRingOrder)
        self.assertEqual(locSchedule, ["002-001", "002-002", "001-001"])

        circularRingOrder = "somethingCrazy"
        locSchedule = hexUtils.buildEqRingSchedule(core, [2, 1], circularRingOrder)
        self.assertEqual(locSchedule, ["002-001", "002-002", "001-001"])

    def test_buildConvergentRingSchedule(self):
        schedule, widths = hexUtils.buildConvergentRingSchedule(1, 17, 0)
        self.assertEqual(schedule, [1, 17])
        self.assertEqual(widths, [16, 1])

        schedule, widths = hexUtils.buildConvergentRingSchedule(3, 17, 1)
        self.assertEqual(schedule, [3, 17])
        self.assertEqual(widths, [14, 1])

        schedule, widths = hexUtils.buildConvergentRingSchedule(12, 16, 0.5)
        self.assertEqual(schedule, [12, 16])
        self.assertEqual(widths, [4, 1])

    def test_buildRingSchedule(self):
        # simple divergent
        schedule, widths = hexUtils.buildRingSchedule(9, 1, 9)
        self.assertEqual(schedule, [9, 8, 7, 6, 5, 4, 3, 2, 1])
        zeroWidths = [0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.assertEqual(widths, zeroWidths)

        # simple with no jumps
        schedule, widths = hexUtils.buildRingSchedule(9, 9, 1, jumpRingTo=1)
        self.assertEqual(schedule, [1, 2, 3, 4, 5, 6, 7, 8, 9])
        self.assertEqual(widths, zeroWidths)

        # simple with 1 jump
        schedule, widths = hexUtils.buildRingSchedule(9, 9, 1, jumpRingFrom=6)
        self.assertEqual(schedule, [5, 4, 3, 2, 1, 6, 7, 8, 9])
        self.assertEqual(widths, zeroWidths)

        # 1 jump plus auto-correction to core size
        schedule, widths = hexUtils.buildRingSchedule(9, 1, 17, jumpRingFrom=5)
        self.assertEqual(schedule, [6, 7, 8, 9, 5, 4, 3, 2, 1])
        self.assertEqual(widths, zeroWidths)

        # crash on invalid jumpring
        with self.assertRaises(ValueError):
            schedule, widths = hexUtils.buildRingSchedule(9, 1, 17, jumpRingFrom=0)

        # test 4: Mid way jumping
        schedule, widths = hexUtils.buildRingSchedule(
            9, 1, 9, jumpRingTo=6, jumpRingFrom=3
        )
        self.assertEqual(schedule, [9, 8, 7, 4, 5, 6, 3, 2, 1])
        self.assertEqual(widths, zeroWidths)


if __name__ == "__main__":
    unittest.main()
