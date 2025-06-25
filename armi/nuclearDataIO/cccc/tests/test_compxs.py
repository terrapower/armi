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

"""Test the COMPXS reader/writer with a simple problem."""

import os
import unittest

import numpy as np
from scipy.sparse import csc_matrix

from armi import nuclearDataIO
from armi.nuclearDataIO.cccc import compxs
from armi.nuclearDataIO.xsLibraries import CompxsLibrary
from armi.tests import COMPXS_PATH
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class TestCompxs(unittest.TestCase):
    """Test the compxs reader/writer."""

    @property
    def binaryWritePath(self):
        return os.path.join(self._testMethodName + "compxs-b")

    @property
    def asciiWritePath(self):
        return os.path.join(self._testMethodName + "compxs-a.txt")

    @classmethod
    def setUpClass(cls):
        try:
            cls.lib = compxs.readAscii(COMPXS_PATH)
        except Exception as ee:
            raise Exception("Failed to load COMPXS ascii.\n{}".format(ee))
        cls.fissileRegion = cls.lib.regions[1]
        cls.numGroups = cls.lib.compxsMetadata["numGroups"]

    def test_libraryData(self):
        """Test library data including energy group information and number of compositions."""
        self.assertEqual(11, self.numGroups)
        self.assertEqual(14190675.0, max(self.lib.neutronEnergyUpperBounds))
        self.assertAlmostEqual(0.41745778918, min(self.lib.neutronEnergyUpperBounds))

    def test_regionPrimaryXS(self):
        """Test the primary cross sections for the second region - fissile."""
        expectedMacros = {
            "absorption": [
                0.00810444,
                0.0049346,
                0.00329084,
                0.00500318,
                0.00919719,
                0.01548523,
                0.02816499,
                0.04592259,
                0.09402685,
                0.12743879,
                0.20865865,
            ],
            "fission": [
                0.00720288,
                0.00398085,
                0.00181345,
                0.00236554,
                0.00341723,
                0.00564286,
                0.0110835,
                0.0211668,
                0.04609869,
                0.09673319,
                0.16192732,
            ],
            "total": [
                0.18858715,
                0.18624092,
                0.22960965,
                0.27634201,
                0.33255093,
                0.61437815,
                0.42582573,
                0.48091191,
                0.4931102,
                0.49976887,
                0.58214497,
            ],
            "removal": [
                0.07268185,
                0.03577923,
                0.01127517,
                0.01003666,
                0.01254067,
                0.02686466,
                0.02881869,
                0.04606618,
                0.09605395,
                0.13462841,
                0.20865865,
            ],
            "transport": [
                0.10812569,
                0.13096095,
                0.18227532,
                0.24610402,
                0.29647433,
                0.55842311,
                0.40818328,
                0.45512788,
                0.45669781,
                0.49153138,
                0.55067248,
            ],
            "nuSigF": [
                0.02247946,
                0.01047702,
                0.00449566,
                0.00576889,
                0.00829842,
                0.01373361,
                0.02697533,
                0.05151573,
                0.11224934,
                0.23570964,
                0.39456832,
            ],
            "chi": [
                [1.38001099e-01],
                [6.28044390e-01],
                [2.04412257e-01],
                [2.63437497e-02],
                [2.85959793e-03],
                [3.03098935e-04],
                [3.19825784e-05],
                [3.42715844e-06],
                [3.00034836e-07],
                [3.87667231e-08],
                [2.66151779e-13],
            ],
        }
        for xsName, expectedXS in expectedMacros.items():
            actualXS = self.fissileRegion.macros[xsName]
            self.assertTrue(np.allclose(actualXS, expectedXS))

    def test_totalScatterMatrix(self):
        """
        Test the total scattering matrix by comparing the sparse components.

        Sparse matrices can be constructed from three vectors: data, indices, and indptr.
        For column matrix, the row indices for column ``j`` are stored in
        ``indices[indptr[j]:indptr[j + 1]]`` and the corresponding data is stored in
        ``data[indptr[j]:indptr[j + 1]]``.

        See Also
        --------
        scipy.sparse.csc_matrix
        """
        expectedSparseData = np.array(
            [
                1.15905297e-01,
                1.50461698e-01,
                4.19181830e-02,
                2.18334481e-01,
                2.66726391e-02,
                2.06841438e-02,
                2.66305350e-01,
                7.93398724e-03,
                3.74972053e-03,
                2.82068371e-03,
                3.20010257e-01,
                4.98916288e-03,
                4.64327778e-05,
                3.62943322e-04,
                2.33116653e-04,
                5.87513494e-01,
                3.33728477e-03,
                4.05355062e-05,
                3.40557886e-06,
                5.05978110e-05,
                2.44368007e-05,
                3.97007043e-01,
                1.13794357e-02,
                5.81324838e-06,
                3.57958695e-06,
                4.21100811e-07,
                6.02755319e-06,
                3.70765519e-06,
                4.34845744e-01,
                6.53692627e-04,
                3.65838392e-07,
                1.91840932e-07,
                6.47891881e-08,
                4.70903065e-07,
                7.53010883e-07,
                3.97056267e-01,
                1.43584939e-04,
                1.69959524e-08,
                7.63482393e-09,
                1.07996799e-08,
                7.79766262e-08,
                1.42976480e-07,
                3.65140459e-01,
                2.02709238e-03,
                1.62021799e-09,
                1.25812112e-09,
                3.39504415e-09,
                2.13443401e-06,
                7.75326455e-06,
                3.73486301e-01,
                7.18962870e-03,
                4.72605255e-15,
                5.11975260e-13,
                1.25417930e-08,
                4.57563838e-08,
            ]
        )

        expectedSparseIndices = [
            0,
            1,
            0,
            2,
            1,
            0,
            3,
            2,
            1,
            0,
            4,
            3,
            2,
            1,
            0,
            5,
            4,
            3,
            2,
            1,
            0,
            6,
            5,
            4,
            3,
            2,
            1,
            0,
            7,
            6,
            4,
            3,
            2,
            1,
            0,
            8,
            7,
            4,
            3,
            2,
            1,
            0,
            9,
            8,
            4,
            3,
            2,
            1,
            0,
            10,
            9,
            4,
            2,
            1,
            0,
        ]

        expectedSparseIndptr = [0, 1, 3, 6, 10, 15, 21, 28, 35, 42, 49, 55]

        actualTotalScatter = self.fissileRegion.macros.totalScatter.toarray()
        expectedTotalScatter = csc_matrix(
            (expectedSparseData, expectedSparseIndices, expectedSparseIndptr),
            actualTotalScatter.shape,
        ).toarray()

        self.assertTrue(np.allclose(actualTotalScatter, expectedTotalScatter))

    def test_binaryRW(self):
        """Test to make sure the binary read/writer reads/writes the exact same library."""
        with TemporaryDirectoryChanger():
            compxs.writeBinary(self.lib, self.binaryWritePath)
            self.assertTrue(compxs.compare(self.lib, compxs.readBinary(self.binaryWritePath)))

    def test_asciiRW(self):
        """Test to make sure the ascii reader/writer reads/writes the exact same library."""
        with TemporaryDirectoryChanger():
            compxs.writeAscii(self.lib, self.asciiWritePath)
            self.assertTrue(compxs.compare(self.lib, compxs.readAscii(self.asciiWritePath)))

    def test_mergeCompxsLibraries(self):
        """Test to verify the compxs merging returns a library with new regions."""
        someLib = CompxsLibrary()
        someLib.merge(self.lib)
        self.assertEqual(len(self.lib.regions), len(someLib.regions))
        self.assertTrue(self.lib.compxsMetadata.compare(someLib.compxsMetadata, self.lib, someLib))

    def test_getCOMPXSFileName(self):
        self.assertEqual(nuclearDataIO.getExpectedCOMPXSFileName(cycle=0), "COMPXS-c0")
        self.assertEqual(nuclearDataIO.getExpectedCOMPXSFileName(cycle=1), "COMPXS-c1")
        self.assertEqual(nuclearDataIO.getExpectedCOMPXSFileName(cycle=23), "COMPXS-c23")
        self.assertEqual(nuclearDataIO.getExpectedCOMPXSFileName(), "COMPXS")
