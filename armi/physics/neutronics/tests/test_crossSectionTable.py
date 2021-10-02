"""Tests for cross section table for depletion"""
import unittest

from armi.physics.neutronics.isotopicDepletion import crossSectionTable as cst
from armi.reactor.flags import Flags
from armi.nuclearDataIO.cccc import isotxs
from armi.reactor.tests.test_blocks import loadTestBlock
from armi.tests import ISOAA_PATH


class TestCrossSectionTable(unittest.TestCase):
    def test_makeTable(self):
        obj = loadTestBlock()
        obj.p.mgFlux = range(33)
        core = obj.getAncestorWithFlags(Flags.CORE)
        core.lib = isotxs.readBinary(ISOAA_PATH)
        table = cst.makeReactionRateTable(obj)

        self.assertEqual(len(obj.getNuclides()), len(table))
        self.assertEqual(obj.getName(), "B0001-000")

        self.assertEqual(table.getName(), "B0001-000")
        self.assertTrue(table.hasValues())

        xSecTable = table.getXsecTable()
        self.assertEqual(len(xSecTable), 11)
        self.assertIn("xsecs", xSecTable[0])
        self.assertIn("mcnpId", xSecTable[-1])


if __name__ == "__main__":
    unittest.main()
