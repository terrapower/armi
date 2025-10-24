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

"""Tests for lumpedFissionProduce module."""

import io
import math
import os
import unittest

from armi.context import RES
from armi.nucDirectory.nuclideBases import NuclideBases
from armi.physics.neutronics.fissionProductModel import (
    REFERENCE_LUMPED_FISSION_PRODUCT_FILE,
    lumpedFissionProduct,
)
from armi.physics.neutronics.fissionProductModel.fissionProductModelSettings import (
    CONF_FP_MODEL,
    CONF_LFP_COMPOSITION_FILE_PATH,
)
from armi.reactor.flags import Flags
from armi.reactor.tests.test_reactors import buildOperatorOfEmptyHexBlocks
from armi.settings import Settings

LFP_TEXT = """LFP35 GE73   5.9000E-06
LFP35 GE74    1.4000E-05
LFP35 GE76    1.6000E-04
LFP35 AS75    8.9000E-05
LFP35 KR85    8.9000E-05
LFP35 MO99    8.9000E-05
LFP35 SM150   8.9000E-05
LFP35 XE135   8.9000E-05
LFP39 XE135   8.9000E-05
LFP38 XE135   8.9000E-05
"""


def getDummyLFPFile():
    return lumpedFissionProduct.FissionProductDefinitionFile(io.StringIO(LFP_TEXT))


class TestFissionProductDefinitionFile(unittest.TestCase):
    """Test of the fission product model."""

    def setUp(self):
        self.fpd = getDummyLFPFile()
        self.nuclideBases = NuclideBases()

    def test_createLFPs(self):
        """Test of the fission product model creation."""
        lfps = self.fpd.createLFPsFromFile()
        xe135 = self.nuclideBases.fromName("XE135")
        self.assertEqual(len(lfps), 3)
        self.assertIn("LFP35", lfps)
        for lfp in lfps.values():
            self.assertIn(xe135, lfp)

    def test_createReferenceLFPs(self):
        """Test of the reference fission product model creation."""
        with open(REFERENCE_LUMPED_FISSION_PRODUCT_FILE, "r") as LFP_FILE:
            LFP_TEXT = LFP_FILE.read()
        fpd = lumpedFissionProduct.FissionProductDefinitionFile(io.StringIO(LFP_TEXT))
        fpd.fName = REFERENCE_LUMPED_FISSION_PRODUCT_FILE
        lfps = fpd.createLFPsFromFile()
        self.assertEqual(len(lfps), 5)

        LFP_IDS = [
            "LFP35",
            "LFP38",
            "LFP39",
            "LFP40",
            "LFP41",
        ]

        for lfp_id in LFP_IDS:
            self.assertIn(lfp_id, lfps)

        mo99 = self.nuclideBases.fromName("MO99")
        ref_mo99_yields = [0.00091, 0.00112, 0.00099, 0.00108, 0.00101]

        for ref_fp_yield, lfp_id in zip(ref_mo99_yields, LFP_IDS):
            lfp = lfps[lfp_id]
            self.assertIn(mo99, lfp)

            error = math.fabs(ref_fp_yield - lfp[mo99]) / ref_fp_yield
            self.assertLess(error, 1e-6)


class TestLumpedFissionProduct(unittest.TestCase):
    """Test of the lumped fission product yields."""

    def setUp(self):
        self.fpd = lumpedFissionProduct.FissionProductDefinitionFile(io.StringIO(LFP_TEXT))
        self.nuclideBases = NuclideBases()

    def test_getYield(self):
        """Test of the yield of a fission product."""
        xe135 = self.nuclideBases.fromName("XE135")
        lfp = self.fpd.createSingleLFPFromFile("LFP39")
        lfp[xe135] = 1.2
        val3 = lfp[xe135]
        self.assertEqual(val3, 1.2)
        self.assertEqual(lfp[5], 0.0)

    def test_gaseousYieldFraction(self):
        lfp = self.fpd.createSingleLFPFromFile("LFP39")
        # This is equal to the Xe yield set in the dummy ``LFP_TEXT``
        # data for these tests.
        self.assertEqual(lfp.getGaseousYieldFraction(), 8.9000e-05)

    def test_isGas(self):
        """Tests that a nuclide is a gas or not at STP based on its chemical phase."""
        nb = self.nuclideBases.byName["H1"]
        self.assertTrue(lumpedFissionProduct.isGas(nb))
        nb = self.nuclideBases.byName["H2"]
        self.assertTrue(lumpedFissionProduct.isGas(nb))
        nb = self.nuclideBases.byName["H3"]
        self.assertTrue(lumpedFissionProduct.isGas(nb))

        nb = self.nuclideBases.byName["U235"]
        self.assertFalse(lumpedFissionProduct.isGas(nb))

        nb = self.nuclideBases.byName["O16"]
        self.assertTrue(lumpedFissionProduct.isGas(nb))

        nb = self.nuclideBases.byName["XE135"]
        self.assertTrue(lumpedFissionProduct.isGas(nb))


class TestLumpedFissionProductCollection(unittest.TestCase):
    """Test of the fission product collection."""

    def setUp(self):
        fpd = lumpedFissionProduct.FissionProductDefinitionFile(io.StringIO(LFP_TEXT))
        self.lfps = fpd.createLFPsFromFile()
        self.nuclideBases = NuclideBases()

    def test_getAllFissionProductNames(self):
        """Test to ensure the fission product names are present."""
        names = self.lfps.getAllFissionProductNames()
        self.assertIn("XE135", names)
        self.assertIn("KR85", names)

    def test_getAllFissionProductNuclideBases(self):
        """Test to ensure the fission product nuclide bases are present."""
        clideBases = self.lfps.getAllFissionProductNuclideBases()
        xe135 = self.nuclideBases.fromName("XE135")
        kr85 = self.nuclideBases.fromName("KR85")
        self.assertIn(xe135, clideBases)
        self.assertIn(kr85, clideBases)

    def test_duplicate(self):
        """Test to ensure that when we duplicate, we don't adjust the original file."""
        newLfps = self.lfps.duplicate()
        ba = self.nuclideBases.fromName("XE135")
        lfp1 = self.lfps["LFP39"]
        lfp2 = newLfps["LFP39"]
        v1 = lfp1[ba]
        lfp1[ba] += 1.3  # make sure copy doesn't change w/ first.
        v2 = lfp2[ba]
        self.assertEqual(v1, v2)

    def test_getNumberDensities(self):
        o = buildOperatorOfEmptyHexBlocks()
        b = next(o.r.core.iterBlocks(Flags.FUEL))
        fpDensities = self.lfps.getNumberDensities(objectWithParentDensities=b)
        for fp in ["GE73", "GE74", "GE76", "AS75", "KR85", "MO99", "SM150", "XE135"]:
            self.assertEqual(fpDensities[fp], 0.0)
            # basic test reactor has no fission products in it

    def test_getMassFrac(self):
        with self.assertRaises(ValueError):
            self.lfps.getMassFrac(oldMassFrac=None)
        oldMassFrac = {
            "LFP35": 0.5,
            "LFP38": 0.2,
            "LFP39": 0.3,
        }
        newMassFracs = self.lfps.getMassFrac(oldMassFrac)
        refMassFrac = {
            "GE73": 0.0034703064077030933,
            "GE74": 0.00834728937688672,
            "GE76": 0.09797894499881823,
            "AS75": 0.053783069618403435,
            "KR85": 0.0609551394006646,
            "MO99": 0.07100169460812283,
            "SM150": 0.1076193196365748,
            "XE135": 0.5968442359528263,
        }
        for fp, newMassFrac in newMassFracs.items():
            self.assertAlmostEqual(newMassFrac, refMassFrac[fp.name])


class TestLumpedFissionProductsFromReferenceFile(unittest.TestCase):
    """Tests loading from the `referenceFissionProducts.dat` file."""

    def test_fissionProductYields(self):
        """Test that the fission product yields for the lumped fission products sums to 2.0."""
        cs = Settings()
        cs[CONF_FP_MODEL] = "infinitelyDilute"
        cs[CONF_LFP_COMPOSITION_FILE_PATH] = os.path.join(RES, "referenceFissionProducts.dat")
        self.lfps = lumpedFissionProduct.lumpedFissionProductFactory(cs)
        for lfp in self.lfps.values():
            self.assertAlmostEqual(lfp.getTotalYield(), 2.0, places=3)


class TestLumpedFissionProductsExplicit(unittest.TestCase):
    """Tests loading fission products with explicit modeling."""

    def test_explicitFissionProducts(self):
        """Tests that there are no lumped fission products added when the `explicitFissionProducts` model is enabled."""
        cs = Settings()
        cs[CONF_FP_MODEL] = "explicitFissionProducts"
        self.lfps = lumpedFissionProduct.lumpedFissionProductFactory(cs)
        self.assertIsNone(self.lfps)


class TestMo99LFP(unittest.TestCase):
    """Test of the fission product model from Mo99."""

    def setUp(self):
        self.lfps = lumpedFissionProduct._buildMo99LumpedFissionProduct()

    def test_getAllFissionProductNames(self):
        """Test to ensure that Mo99 is present, but other FP are not."""
        names = self.lfps.getAllFissionProductNames()
        self.assertIn("MO99", names)
        self.assertNotIn("KR85", names)
        self.assertAlmostEqual(self.lfps["LFP35"].getTotalYield(), 2.0)
