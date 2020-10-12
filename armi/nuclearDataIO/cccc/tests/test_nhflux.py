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
import shutil
import subprocess
import tempfile
import unittest

import numpy

from armi import settings
from armi.nuclearDataIO.cccc import nhflux


THIS_DIR = os.path.dirname(__file__)

SIMPLE_HEXZ_INP = os.path.join(THIS_DIR, "simple_hexz.inp")
SIMPLE_HEXZ_NHFLUX = os.path.join(THIS_DIR, "fixtures", "simple_hexz.nhflux")


def createSIMPLE_HEXZ_NHFLUX():
    """
    Create NHFLUX file.

    In order to test the reading of NHFLUX file, there is a need to provide one such
    file for testing. This function runs the provided DIF3D input, and generates an
    NHFLUX file. The DIF3D input is a modified version of test case 01 from the DIF3D
    code package. It uses the 4-group cross sections located in the last part of the
    input. The modification includes:

    1) reduce the geometry to 3 rows of assemblies in full core geometry;
    2) reduce the fuel assembly to contain 6 nodes only;
    3) change the dimension to be whole numbers.

    In this way, the produced NHFLUX file is fairly small in size that makes it suitable
    for testing purposes. Another benefit of the simplified input is the trivial
    computer running time. It should take < 10 seconds to generate the NHFLUX file.
    Nevertheless, since the diffusion approximation is likely to be invalid for such a
    small-size core, results are not meant for physics benchmarking or other realistic
    applications.

    .. important::
        This requires both DIF3D and the TerraPower's DIF3D ARMI plugin in order to run.
        The latest output is shipped with the test, but regenerating or updating it will
        require these extra dependencies. Also, if you don't have them you can ask
        someone that does and maybe they can hook you up.
    """
    DIF3D_EXE = settings.getMasterCs().settings["dif3d"].value

    runDir = tempfile.mkdtemp()
    shutil.copy(SIMPLE_HEXZ_INP, os.path.join(runDir, "input"))
    process = subprocess.Popen(
        "{} < input > output".format(DIF3D_EXE), cwd=runDir, shell=True
    )
    process.communicate()
    shutil.copy(os.path.join(runDir, "NHFLUX"), SIMPLE_HEXZ_NHFLUX)
    shutil.rmtree(runDir)


class TestNHFLUX(unittest.TestCase):
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

    def test_fluxMoments(self):
        """
        Verify that the flux moments are properly read.

        The 5 flux moments values are manually verified for two nodes. The indices
        are converted to zero based from the original by subtracting one.

        :req:`REQ77f06870-5923-429c-b3c7-d42f5a24f404`
        """
        # node 1 (ring=1, position=1), axial=3, group=2
        i = 0  # first one in node map (ring=1, position=1)
        # 13 = 2*5 + 2 + 1 => (i=2, j=2)
        self.assertEqual(self.nhf.geodstCoordMap[i], 13)
        iz, ig = 2, 1  # zero based
        self.assertTrue(
            numpy.allclose(
                self.nhf.fluxMoments[i, iz, :, ig],
                [1.424926e08, -2.018375e-01, 2.018375e-01, -2.018374e-01, 1.758205e06],
            )
        )

        # node 8 (ring=3, position=2), axial=6, group=1
        i = 7  # ring=3, position=2
        self.assertEqual(
            self.nhf.geodstCoordMap[i], 20
        )  # 20 = 3*5 + 4 + 1 => (i=4, j=3)
        iz, ig = 5, 0  # zero based
        self.assertTrue(
            numpy.allclose(
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

        :req:`REQ77f06870-5923-429c-b3c7-d42f5a24f404`
        """
        # node 2 (ring=3, position=1), axial=4, group=2, surface=4, outgoing
        iNode, iSurf, iz, ig = 1, 3, 3, 1  # zero based
        self.assertEqual(self.nhf.geodstCoordMap[iNode], 15)
        self.assertAlmostEqual(
            self.nhf.partialCurrentsHex[iNode, iz, iSurf, ig] / 1.5570424e07, 1.0
        )

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

        :req:`REQ77f06870-5923-429c-b3c7-d42f5a24f404`
        """
        # node 15 (ring=2, position=3), axial=3, group=3, j=1 (z-plus)
        iNode, iz, ig, j = 14, 2, 2, 0
        self.assertAlmostEqual(
            self.nhf.partialCurrentsZ[iNode, iz, j, ig] / 1.6928521e06, 1.0
        )

    def test_write(self):
        """Verify binary equivalence of written binary file."""
        nhflux.NhfluxStream.writeBinary(self.nhf, "NHFLUX2")
        with open(SIMPLE_HEXZ_NHFLUX, "rb") as f1, open("NHFLUX2", "rb") as f2:
            expectedData = f1.read()
            actualData = f2.read()
        for expected, actual in zip(expectedData, actualData):
            self.assertEqual(expected, actual)
        os.remove("NHFLUX2")


if __name__ == "__main__":
    unittest.main()
