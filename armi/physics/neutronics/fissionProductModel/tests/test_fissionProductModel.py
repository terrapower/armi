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
"""
Test the fission product module to ensure all FP are available.
"""
import unittest
from ordered_set import OrderedSet

from armi import nuclideBases
from armi.physics.neutronics.fissionProductModel import lumpedFissionProduct
from armi.physics.neutronics.fissionProductModel import fissionProductModel
from armi.reactor.tests.test_reactors import buildOperatorOfEmptyHexBlocks

from armi.physics.neutronics.fissionProductModel.tests import test_lumpedFissionProduct


def _getLumpedFissionProductNumberDensities(b):
    """Returns the number densities for each lumped fission product in a block."""
    nDens = {}
    for lfpName, lfp in b.getLumpedFissionProductCollection().items():
        nDens[lfp] = b.getNumberDensity(lfpName)
    return nDens


class TestFissionProductModelLumpedFissionProducts(unittest.TestCase):
    """
    Tests the fission product model interface behavior when lumped fission products are enabled.

    Notes
    -----
    This loads the global fission products from a file stream.
    """

    def setUp(self):
        o = buildOperatorOfEmptyHexBlocks()
        o.removeAllInterfaces()
        self.fpModel = fissionProductModel.FissionProductModel(o.r, o.cs)
        o.addInterface(self.fpModel)

        # Load the fission products from a file stream.
        dummyLFPs = test_lumpedFissionProduct.getDummyLFPFile()
        self.fpModel.setGlobalLumpedFissionProducts(dummyLFPs.createLFPsFromFile())

        # Set up the global LFPs and check that they are setup.
        self.fpModel.setAllBlockLFPs()
        self.assertTrue(self.fpModel._useGlobalLFPs)

    def test_loadGlobalLFPsFromFile(self):
        """Tests that loading lumped fission products from a file."""
        self.assertEqual(len(self.fpModel._globalLFPs), 3)
        lfps = self.fpModel.getGlobalLumpedFissionProducts()
        self.assertIn("LFP39", lfps)

    def test_getAllFissionProductNames(self):
        """Tests retrieval of the fission product names within all the lumped fission products of the core."""
        fissionProductNames = self.fpModel.getAllFissionProductNames()
        self.assertGreater(len(fissionProductNames), 5)
        self.assertIn("XE135", fissionProductNames)


class TestFissionProductModelNoGasRemoval(unittest.TestCase):
    """Tests that no gaseous fission products are removed when the `fgRemoval` settings is disabled."""

    def setUp(self):
        o = buildOperatorOfEmptyHexBlocks()
        o.removeAllInterfaces()
        o.cs["fgRemoval"] = False

        self.core = o.r.core
        self.fpModel = fissionProductModel.FissionProductModel(o.r, o.cs)
        o.addInterface(self.fpModel)

        # Set up the global LFPs and check that they are setup.
        self.fpModel.setAllBlockLFPs()
        self.assertTrue(self.fpModel._useGlobalLFPs)

        # Setup the blocks to have the same lumped fission product densities.
        for b in self.core.getBlocks():
            if b.getLumpedFissionProductCollection() is None:
                continue
            for lfp in b.getLumpedFissionProductCollection():
                updatedNumberDensities = b.getNumberDensities()
                updatedNumberDensities[lfp] = 1e5
                b.setNumberDensities(updatedNumberDensities)

    def test_removeAllGaseousFissionProductsLFP(self):
        """
        Same as ``TestFissionProductModelGasRemovalLumpedFissionProducts.test_removeAllGaseousFissionProductsLFP``
        but the `fgRemoval` setting is disabled so there is expected to be no change.
        """
        gasRemovalFractions = {}
        previousBlockFissionProductNumberDensities = {}
        updatedBlockFissionProductNumberDensities = {}

        # Get the initial fission product number densities and setup the gas removal fractions.
        for b in self.core.getBlocks():
            lfpCollection = b.getLumpedFissionProductCollection()
            if lfpCollection is None:
                continue

            previousBlockFissionProductNumberDensities[
                b
            ] = _getLumpedFissionProductNumberDensities(b)
            gasRemovalFractions = {b: 1.0}

        # Remove the fission gases
        self.fpModel.removeFissionGasesFromBlocks(gasRemovalFractions)

        # Check that the fission gases were removed correctly.
        for b in self.core.getBlocks():
            lfpCollection = b.getLumpedFissionProductCollection()
            if lfpCollection is None:
                continue

            updatedBlockFissionProductNumberDensities[
                b
            ] = _getLumpedFissionProductNumberDensities(b)
            for lfp in lfpCollection.values():
                old = previousBlockFissionProductNumberDensities[b][lfp]
                new = updatedBlockFissionProductNumberDensities[b][lfp]
                self.assertAlmostEqual(new, old)


class TestFissionProductModelGasRemovalLumpedFissionProducts(unittest.TestCase):
    """
    Tests the fission product model interface behavior when lumped fission products are enabled.

    Notes
    -----
    This loads the global fission products from the default file.
    """

    def setUp(self):
        o = buildOperatorOfEmptyHexBlocks()
        o.removeAllInterfaces()
        o.cs["fgRemoval"] = True

        self.core = o.r.core
        self.fpModel = fissionProductModel.FissionProductModel(o.r, o.cs)
        o.addInterface(self.fpModel)

        # Set up the global LFPs and check that they are setup.
        self.fpModel.setAllBlockLFPs()
        self.assertTrue(self.fpModel._useGlobalLFPs)

        # Setup the blocks to have the same lumped fission product densities.
        for b in self.core.getBlocks():
            if b.getLumpedFissionProductCollection() is None:
                continue
            for lfp in b.getLumpedFissionProductCollection():
                updatedNumberDensities = b.getNumberDensities()
                updatedNumberDensities[lfp] = 1e5
                b.setNumberDensities(updatedNumberDensities)

    def test_removeZeroGaseousFissionProductsLFP(self):
        """Tests removal of gaseous fission products globally in the core with a removal fraction of zero."""
        gasRemovalFractions = {}
        previousBlockFissionProductNumberDensities = {}
        updatedBlockFissionProductNumberDensities = {}

        # Get the initial fission product number densities and setup the gas removal fractions.
        for b in self.core.getBlocks():
            lfpCollection = b.getLumpedFissionProductCollection()
            if lfpCollection is None:
                continue

            previousBlockFissionProductNumberDensities[
                b
            ] = _getLumpedFissionProductNumberDensities(b)
            gasRemovalFractions = {b: 0.0}

        # Remove the fission gases
        self.fpModel.removeFissionGasesFromBlocks(gasRemovalFractions)

        # Check that the fission gases were removed correctly.
        for b in self.core.getBlocks():
            lfpCollection = b.getLumpedFissionProductCollection()
            if lfpCollection is None:
                continue

            updatedBlockFissionProductNumberDensities[
                b
            ] = _getLumpedFissionProductNumberDensities(b)
            for lfp in lfpCollection.values():
                old = previousBlockFissionProductNumberDensities[b][lfp]
                new = updatedBlockFissionProductNumberDensities[b][lfp]

                # The expected result should be the previous number densities for the lumped fission
                # product within the block that is subtracted by the gas removal fraction multiplied
                # by the fraction of gas atoms produced from fission.
                result = old - (
                    old * gasRemovalFractions[b] * lfp.getGaseousYieldFraction()
                )
                self.assertAlmostEqual(new, result)
                self.assertEqual(new, old)

    def test_removeHalfGaseousFissionProductsLFP(self):
        """Tests removal of gaseous fission products globally in the core with a removal fraction of 0.5."""
        gasRemovalFractions = {}
        previousBlockFissionProductNumberDensities = {}
        updatedBlockFissionProductNumberDensities = {}

        # Get the initial fission product number densities and setup the gas removal fractions.
        for b in self.core.getBlocks():
            lfpCollection = b.getLumpedFissionProductCollection()
            if lfpCollection is None:
                continue

            previousBlockFissionProductNumberDensities[
                b
            ] = _getLumpedFissionProductNumberDensities(b)
            gasRemovalFractions = {b: 0.5}

        # Remove the fission gases
        self.fpModel.removeFissionGasesFromBlocks(gasRemovalFractions)

        # Check that the fission gases were removed correctly.
        for b in self.core.getBlocks():
            lfpCollection = b.getLumpedFissionProductCollection()
            if lfpCollection is None:
                continue

            updatedBlockFissionProductNumberDensities[
                b
            ] = _getLumpedFissionProductNumberDensities(b)
            for lfp in lfpCollection.values():
                old = previousBlockFissionProductNumberDensities[b][lfp]
                new = updatedBlockFissionProductNumberDensities[b][lfp]

                # The expected result should be the previous number densities for the lumped fission
                # product within the block that is subtracted by the gas removal fraction multiplied
                # by the fraction of gas atoms produced from fission.
                result = old - (
                    old * gasRemovalFractions[b] * lfp.getGaseousYieldFraction()
                )
                self.assertAlmostEqual(new, result)

    def test_removeAllGaseousFissionProductsLFP(self):
        """Tests removal of gaseous fission products globally in the core with a removal fraction of 1.0."""
        gasRemovalFractions = {}
        previousBlockFissionProductNumberDensities = {}
        updatedBlockFissionProductNumberDensities = {}

        # Get the initial fission product number densities and setup the gas removal fractions.
        for b in self.core.getBlocks():
            lfpCollection = b.getLumpedFissionProductCollection()
            if lfpCollection is None:
                continue

            previousBlockFissionProductNumberDensities[
                b
            ] = _getLumpedFissionProductNumberDensities(b)
            gasRemovalFractions = {b: 1.0}

        # Remove the fission gases
        self.fpModel.removeFissionGasesFromBlocks(gasRemovalFractions)

        # Check that the fission gases were removed correctly.
        for b in self.core.getBlocks():
            lfpCollection = b.getLumpedFissionProductCollection()
            if lfpCollection is None:
                continue

            updatedBlockFissionProductNumberDensities[
                b
            ] = _getLumpedFissionProductNumberDensities(b)
            for lfp in lfpCollection.values():
                old = previousBlockFissionProductNumberDensities[b][lfp]
                new = updatedBlockFissionProductNumberDensities[b][lfp]

                # The expected result should be the previous number densities for the lumped fission
                # product within the block that is subtracted by the gas removal fraction multiplied
                # by the fraction of gas atoms produced from fission.
                result = old - (
                    old * gasRemovalFractions[b] * lfp.getGaseousYieldFraction()
                )
                self.assertAlmostEqual(new, result)


class TestFissionProductModelGasRemovalExplicitFissionProducts(unittest.TestCase):
    """Tests the fission product model interface behavior when `explicitFissionProducts` are enabled."""

    def setUp(self):
        o = buildOperatorOfEmptyHexBlocks()
        o.removeAllInterfaces()
        o.cs["fgRemoval"] = True
        o.cs["fpModel"] = "explicitFissionProducts"
        o.cs["fpModelLibrary"] = "MC2-3"

        nuclidesToAdd = []
        for nb in lumpedFissionProduct.getAllNuclideBasesByLibrary(o.cs):
            nuclidesToAdd.append(nb.name)
        o.r.blueprints.allNuclidesInProblem = OrderedSet(sorted(nuclidesToAdd))

        self.core = o.r.core
        self.fpModel = fissionProductModel.FissionProductModel(o.r, o.cs)
        o.addInterface(self.fpModel)

        # Set up the global LFPs and check that they are setup.
        self.fpModel.setAllBlockLFPs()
        self.assertFalse(self.fpModel._useGlobalLFPs)

        # Setup the blocks to have the same lumped fission product densities.
        for b in self.core.getBlocks():
            updatedNumberDensities = b.getNumberDensities()
            for nuc in b.getNuclides():
                nb = nuclideBases.byName[nuc]
                if not lumpedFissionProduct.isGas(nb):
                    continue
                updatedNumberDensities[nuc] = 1e5
            b.setNumberDensities(updatedNumberDensities)

    def test_removeZeroGaseousFissionProducts(self):
        """Tests removal of gaseous fission products in the core with a removal fraction of zero."""
        gasRemovalFractions = {}
        previousBlockFissionProductNumberDensities = {}
        updatedBlockFissionProductNumberDensities = {}

        # Get the initial fission product number densities and setup the gas removal fractions.
        for b in self.core.getBlocks():
            previousBlockFissionProductNumberDensities[b] = b.getNumberDensities()
            gasRemovalFractions = {b: 0.0}

        # Remove the fission gases
        self.fpModel.removeFissionGasesFromBlocks(gasRemovalFractions)

        # Check that the fission gases were removed correctly.
        for b in self.core.getBlocks():
            updatedBlockFissionProductNumberDensities[b] = b.getNumberDensities()
            for nuc in b.getNuclides():
                nb = nuclideBases.byName[nuc]
                if not lumpedFissionProduct.isGas(nb):
                    continue

                old = previousBlockFissionProductNumberDensities[b][nuc]
                new = updatedBlockFissionProductNumberDensities[b][nuc]
                result = old - (old * gasRemovalFractions[b])
                self.assertAlmostEqual(new, result)
                self.assertAlmostEqual(new, old)

    def test_removeHalfGaseousFissionProducts(self):
        """Tests removal of gaseous fission products in the core with a removal fraction of 0.5."""
        gasRemovalFractions = {}
        previousBlockFissionProductNumberDensities = {}
        updatedBlockFissionProductNumberDensities = {}

        # Get the initial fission product number densities and setup the gas removal fractions.
        for b in self.core.getBlocks():
            previousBlockFissionProductNumberDensities[b] = b.getNumberDensities()
            gasRemovalFractions = {b: 0.5}

        # Remove the fission gases
        self.fpModel.removeFissionGasesFromBlocks(gasRemovalFractions)

        # Check that the fission gases were removed correctly.
        for b in self.core.getBlocks():
            updatedBlockFissionProductNumberDensities[b] = b.getNumberDensities()
            for nuc in b.getNuclides():
                nb = nuclideBases.byName[nuc]
                if not lumpedFissionProduct.isGas(nb):
                    continue

                old = previousBlockFissionProductNumberDensities[b][nuc]
                new = updatedBlockFissionProductNumberDensities[b][nuc]
                result = old - (old * gasRemovalFractions[b])
                self.assertAlmostEqual(new, result)

    def test_removeAllGaseousFissionProducts(self):
        """Tests removal of gaseous fission products in the core with a removal fraction of 1.0."""
        gasRemovalFractions = {}
        previousBlockFissionProductNumberDensities = {}
        updatedBlockFissionProductNumberDensities = {}

        # Get the initial fission product number densities and setup the gas removal fractions.
        for b in self.core.getBlocks():
            previousBlockFissionProductNumberDensities[b] = b.getNumberDensities()
            gasRemovalFractions = {b: 1.0}

        # Remove the fission gases
        self.fpModel.removeFissionGasesFromBlocks(gasRemovalFractions)

        # Check that the fission gases were removed correctly.
        for b in self.core.getBlocks():
            updatedBlockFissionProductNumberDensities[b] = b.getNumberDensities()
            for nuc in b.getNuclides():
                nb = nuclideBases.byName[nuc]
                if not lumpedFissionProduct.isGas(nb):
                    continue

                old = previousBlockFissionProductNumberDensities[b][nuc]
                new = updatedBlockFissionProductNumberDensities[b][nuc]
                result = old - (old * gasRemovalFractions[b])
                self.assertAlmostEqual(new, result)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
