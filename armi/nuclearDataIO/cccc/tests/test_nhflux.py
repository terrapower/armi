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

"""Test reading/writing of NHFLUX dataset."""

import os
import unittest

import numpy as np

from armi.nuclearDataIO.cccc import nhflux
from armi.utils.directoryChangers import TemporaryDirectoryChanger

THIS_DIR = os.path.dirname(__file__)

SIMPLE_HEXZ_INP = os.path.join(THIS_DIR, "../../tests", "simple_hexz.inp")
SIMPLE_HEXZ_NHFLUX = os.path.join(THIS_DIR, "fixtures", "simple_hexz.nhflux")
SIMPLE_HEXZ_NHFLUX_VARIANT = os.path.join(THIS_DIR, "fixtures", "simple_hexz.nhflux.variant")


class TestNhflux(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load NHFLUX data from binary file."""
        cls.nhf = nhflux.NhfluxStream.readBinary(SIMPLE_HEXZ_NHFLUX)

    def test_fc(self):
        """Verify the file control info."""
        self.assertEqual(self.nhf.metadata["ndim"], 3)
        self.assertEqual(self.nhf.metadata["ngroup"], 4)
        self.assertEqual(self.nhf.metadata["ninti"], 5)
        self.assertEqual(self.nhf.metadata["nintj"], 5)
        self.assertEqual(self.nhf.metadata["nintk"], 6)
        self.assertEqual(self.nhf.metadata["nSurf"], 6)
        self.assertEqual(self.nhf.metadata["nMom"], 5)
        self.assertEqual(self.nhf.metadata["nintxy"], 19)
        self.assertEqual(self.nhf.metadata["npcxy"], 144)
        self.assertEqual(self.nhf.metadata["iaprx"], 4)
        self.assertEqual(self.nhf.metadata["iaprxz"], 3)

        variantControlInfo = nhflux.FILE_SPEC_1D_KEYS_VARIANT11
        for info in variantControlInfo:
            self.assertTrue(info not in self.nhf.metadata)

    def test_fluxMoments(self):
        """
        Verify that the flux moments are properly read.

        The 5 flux moments values are manually verified for two nodes. The indices
        are converted to zero based from the original by subtracting one.
        """
        # node 1 (ring=1, position=1), axial=3, group=2
        i = 0  # first one in node map (ring=1, position=1)
        # 13 = 2*5 + 2 + 1 => (i=2, j=2)
        self.assertEqual(self.nhf.geodstCoordMap[i], 13)
        iz, ig = 2, 1  # zero based
        self.assertTrue(
            np.allclose(
                self.nhf.fluxMoments[i, iz, :, ig],
                [1.424926e08, -2.018375e-01, 2.018375e-01, -2.018374e-01, 1.758205e06],
            )
        )

        # node 8 (ring=3, position=2), axial=6, group=1
        i = 7  # ring=3, position=2
        self.assertEqual(self.nhf.geodstCoordMap[i], 20)  # 20 = 3*5 + 4 + 1 => (i=4, j=3)
        iz, ig = 5, 0  # zero based
        self.assertTrue(
            np.allclose(
                self.nhf.fluxMoments[i, iz, :, ig],
                [7.277324e06, -1.453915e06, -1.453915e06, 2.362100e-02, -8.626439e05],
            )
        )

    def test_xyPartialCurrents(self):
        """
        Verify that the XY-directed partial currents can be read.

        The surface partial currents can be used to reconstruct the surface
        flux and corner flux values. This test shows that the outgoing current
        in one hex is identical to the incoming current in the adjacent hex.
        """
        # node 2 (ring=3, position=1), axial=4, group=2, surface=4, outgoing
        iNode, iSurf, iz, ig = 1, 3, 3, 1  # zero based
        self.assertEqual(self.nhf.geodstCoordMap[iNode], 15)
        self.assertAlmostEqual(self.nhf.partialCurrentsHex[iNode, iz, iSurf, ig] / 1.5570424e07, 1.0)

        # node 14 (ring=2, position=1), axial=4, group=2, surface=1, incoming
        iNode, iSurf = 13, 0
        ipcpnt = self.nhf.incomingPointersToAllAssemblies[iSurf, iNode]
        iNode1, iSurf1 = divmod(ipcpnt - 1, self.nhf.metadata["nSurf"])
        self.assertEqual(iNode1, 1)  # node 2
        self.assertEqual(iSurf1, 3)  # surface 4

    def test_zPartialCurrents(self):
        """
        Verify that the Z-directed partial currents can be read.

        The Z-directed partial currents are manually checked for one node
        surface.
        """
        # node 15 (ring=2, position=3), axial=3, group=3, j=1 (z-plus)
        iNode, iz, ig, j = 14, 2, 2, 0
        self.assertAlmostEqual(self.nhf.partialCurrentsZ[iNode, iz, j, ig] / 1.6928521e06, 1.0)

    def test_write(self):
        """Verify binary equivalence of written binary file."""
        with TemporaryDirectoryChanger():
            nhflux.NhfluxStream.writeBinary(self.nhf, "NHFLUX2")
            with open(SIMPLE_HEXZ_NHFLUX, "rb") as f1, open("NHFLUX2", "rb") as f2:
                expectedData = f1.read()
                actualData = f2.read()
            for expected, actual in zip(expectedData, actualData):
                self.assertEqual(expected, actual)


class TestNhfluxVariant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load NHFLUX data from binary file. This file was produced using VARIANT v11.0."""
        cls.nhf = nhflux.NhfluxStreamVariant.readBinary(SIMPLE_HEXZ_NHFLUX_VARIANT)

    def test_fc(self):
        """Verify the file control info."""
        # These entries exist for both Nodal and VARIANT, but have different values
        # for the same model
        print(self.nhf.metadata.items())
        self.assertEqual(self.nhf.metadata["nMom"], 35)
        self.assertEqual(self.nhf.metadata["nscoef"], 3)

        # These entries are only for VARIANT
        self.assertEqual(self.nhf.metadata["npcbdy"], 30)
        self.assertEqual(self.nhf.metadata["npcsym"], 0)
        self.assertEqual(self.nhf.metadata["npcsec"], 0)
        self.assertEqual(self.nhf.metadata["iwnhfl"], 0)
        self.assertEqual(self.nhf.metadata["nMoms"], 0)

    def test_fluxMoments(self):
        # node 1 (ring=1, position=1), axial=3, group=2
        i = 0
        self.assertEqual(self.nhf.geodstCoordMap[i], 13)
        iz, ig = 2, 1
        fluxMoments = self.nhf.fluxMoments[i, iz, :, ig]
        numZeroFluxMoments = fluxMoments[fluxMoments == 0.0].shape[0]
        self.assertTrue(numZeroFluxMoments == 23)
        actualNonzeroFluxMoments = fluxMoments[fluxMoments != 0.0]
        expectedNonzeroFluxMoments = [
            1.42816534e08,
            -5.97642574e06,
            -1.54354423e06,
            -2.15736929e06,
            -1.53415481e06,
            5.54278533e04,
            7.74699855e04,
            2.38133712e04,
            6.69907176e03,
            5.49027950e03,
            9.01170812e03,
            1.05852790e04,
        ]
        self.assertTrue(np.allclose(actualNonzeroFluxMoments, expectedNonzeroFluxMoments))

    def test_write(self):
        """Verify binary equivalence of written binary file."""
        with TemporaryDirectoryChanger():
            nhflux.NhfluxStreamVariant.writeBinary(self.nhf, "NHFLUX2")
            with open(SIMPLE_HEXZ_NHFLUX_VARIANT, "rb") as f1, open("NHFLUX2", "rb") as f2:
                expectedData = f1.read()
                actualData = f2.read()
            for expected, actual in zip(expectedData, actualData):
                self.assertEqual(expected, actual)
