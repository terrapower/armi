"""
Tests for fuel performance utilities.
"""

import unittest

from armi.physics.fuelPerformance import utils
from armi.reactor.flags import Flags
from armi.reactor.tests import test_blocks


class TestFuelPerformanceUtils(unittest.TestCase):
    def test_enforceBondRemovalFraction(self):
        b = test_blocks.loadTestBlock()
        bond = b.getComponent(Flags.BOND)
        bondRemovalFrac = 0.705
        ndensBefore = b.getNumberDensity("NA")
        bondNdensBefore = bond.getNumberDensity("NA")
        b.p.bondBOL = bondNdensBefore
        utils.enforceBondRemovalFraction(b, bondRemovalFrac)
        bondNdensAfter = bond.getNumberDensity("NA")
        ndensAfter = b.getNumberDensity("NA")

        self.assertAlmostEqual(
            bondNdensAfter / bondNdensBefore, (1.0 - bondRemovalFrac)
        )
        self.assertAlmostEqual(ndensBefore, ndensAfter)

        # make sure it doesn't change if you run it twice
        utils.enforceBondRemovalFraction(b, bondRemovalFrac)
        bondNdensAfter = bond.getNumberDensity("NA")
        ndensAfter = b.getNumberDensity("NA")
        self.assertAlmostEqual(
            bondNdensAfter / bondNdensBefore, (1.0 - bondRemovalFrac)
        )
        self.assertAlmostEqual(ndensBefore, ndensAfter)
