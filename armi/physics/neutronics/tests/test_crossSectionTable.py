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
"""Tests for cross section table for depletion."""
import unittest

from armi.nuclearDataIO.cccc import isotxs
from armi.physics.neutronics.isotopicDepletion import (
    crossSectionTable,
)
from armi.physics.neutronics.isotopicDepletion import (
    isotopicDepletionInterface as idi,
)
from armi.physics.neutronics.latticePhysics import ORDER
from armi.reactor.tests.test_blocks import loadTestBlock
from armi.settings import Settings
from armi.testing import loadTestReactor
from armi.tests import ISOAA_PATH


class TestCrossSectionTable(unittest.TestCase):
    def test_makeTable(self):
        """Test making a cross section table.

        .. test:: Generate cross section table.
            :id: T_ARMI_DEPL_TABLES
            :tests: R_ARMI_DEPL_TABLES
        """
        obj = loadTestBlock()
        obj.p.mgFlux = range(33)
        core = obj.parent.parent
        core.lib = isotxs.readBinary(ISOAA_PATH)
        table = crossSectionTable.makeReactionRateTable(obj)

        self.assertEqual(len(obj.getNuclides()), len(table))
        self.assertEqual(obj.getName(), "B0001-000")

        self.assertEqual(table.getName(), "B0001-000")
        self.assertTrue(table.hasValues())

        xSecTable = table.getXsecTable()
        self.assertEqual(len(xSecTable), 11)
        self.assertIn("xsecs", xSecTable[0])
        self.assertIn("mcnpId", xSecTable[-1])

    def test_isotopicDepletionInterface(self):
        """
        Test isotopic depletion interface.

        .. test:: ARMI provides a base class to deplete isotopes.
            :id: T_ARMI_DEPL_ABC
            :tests: R_ARMI_DEPL_ABC
        """
        _o, r = loadTestReactor(
            inputFileName="smallestTestReactor/armiRunSmallest.yaml"
        )
        cs = Settings()

        aid = idi.AbstractIsotopicDepleter(r, cs)
        self.assertIsNone(aid.efpdToBurn)
        self.assertEqual(len(aid._depleteByName), 0)

        self.assertEqual(len(aid.getToDeplete()), 0)
        self.assertEqual(ORDER, 5.0)
