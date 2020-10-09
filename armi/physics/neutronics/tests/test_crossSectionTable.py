"""Tests for cross section table for depletion"""
import unittest

from armi.physics.neutronics.isotopicDepletion import crossSectionTable as cst
from armi.reactor.flags import Flags
from armi.nuclearDataIO.cccc import isotxs
from armi.reactor.tests.test_blocks import loadTestBlock
from armi.tests import ISOAA_PATH


class TestCrossSectionTable(unittest.TestCase):
    def testMakeTable(self):
        obj = loadTestBlock()
        obj.p.mgFlux = range(33)
        core = obj.getAncestorWithFlags(Flags.CORE)
        core.lib = isotxs.readBinary(ISOAA_PATH)
        table = cst.makeReactionRateTable(obj)
        self.assertEqual(len(table), len(obj.getNuclides()))


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
