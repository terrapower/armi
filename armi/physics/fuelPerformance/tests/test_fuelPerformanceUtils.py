"""
Tests for fuel performance utilities.
"""

import unittest

from armi.physics.fuelPerformance import utils
from armi.reactor.flags import Flags
from armi.reactor.tests import test_blocks


class TestFuelPerformanceUtils(unittest.TestCase):
    def test_enforceBondRemovalFraction(self):
        """
        Tests that the bond sodium is removed from the `bond` component in a block
        and the mass is then evenly distributed across all other sodium containing components 
        (e.g., coolant, intercoolant).
        """
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

    def test_applyFuelDisplacement(self):
        displacement = 0.01
        block = test_blocks.loadTestBlock()
        fuel = block.getComponent(Flags.FUEL)
        originalHotODInCm = fuel.getDimension("od")
        utils.applyFuelDisplacement(block, displacement)
        finalHotODInCm = fuel.getDimension("od")

        self.assertAlmostEqual(finalHotODInCm, originalHotODInCm + 2 * displacement)
