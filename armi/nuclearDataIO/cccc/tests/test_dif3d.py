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

"""Test reading/writing of DIF3D binary input."""

import os
import unittest

from armi.nuclearDataIO.cccc import dif3d
from armi.utils.directoryChangers import TemporaryDirectoryChanger

THIS_DIR = os.path.dirname(__file__)

SIMPLE_HEXZ_INP = os.path.join(THIS_DIR, "../../tests", "simple_hexz.inp")
SIMPLE_HEXZ_DIF3D = os.path.join(THIS_DIR, "fixtures", "simple_hexz.dif3d")


class TestDif3d(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load DIF3D data from binary file."""
        cls.df = dif3d.Dif3dStream.readBinary(SIMPLE_HEXZ_DIF3D)

    def test__rwFileID(self):
        """Verify the file identification info."""
        self.assertEqual(self.df.metadata["HNAME"], "DIF3D")
        self.assertEqual(self.df.metadata["HUSE1"], "")
        self.assertEqual(self.df.metadata["HUSE2"], "")
        self.assertEqual(self.df.metadata["VERSION"], 1)

    def test__rwFile1DRecord(self):
        """Verify the rest of the metadata"""
        title = "3D Hex-Z to generate NHFLUX file"

        EXPECTED_TITLE = ["3D Hex", "-Z to", "genera", "te NHF", "LUX fi", "le"] + [
            "" for i in range(5)
        ]
        for i in range(10):
            self.assertEqual(self.df.metadata[f"TITLE{i}"], EXPECTED_TITLE[i])
        self.assertEqual(self.df.metadata["MAXSIZ"], 10000)
        self.assertEqual(self.df.metadata["MAXBLK"], 1800000)
        self.assertEqual(self.df.metadata["IPRINT"], 0)

    def test__rw2DRecord(self):
        """Verify the Control Parameters"""
        EXPECTED_2D = [
            0,
            0,
            0,
            10000,
            30,
            0,
            1000000000,
            5,
            0,
            0,
            50,
            0,
            1,
            1,
            0,
            0,
            0,
            110,
            10,
            100,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            10,
            40,
            32,
            0,
            0,
            2,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ]
        for i, param in enumerate(dif3d.FILE_SPEC_2D_PARAMS):
            self.assertEqual(self.df.twoD[param], EXPECTED_2D[i])

    def test__rw3DRecord(self):
        """Verify the Convergence Criteria"""
        EXPECTED_3D = [
            1e-7,
            1e-5,
            1e-5,
            3.823807613470224e-01,
            1e-3,
            4e-2,
            1e0,
            0e0,
            0e0,
            9.999999747378752e-05,
        ] + [0.0 for i in range(1, 21)]
        for i, param in enumerate(dif3d.FILE_SPEC_3D_PARAMS):
            self.assertEqual(self.df.threeD[param], EXPECTED_3D[i])

    def test__rw4DRecord(self):
        """Verify the optimum overrelaxation factors"""
        self.assertEqual(self.df.fourD, None)

    def test__rw5DRecord(self):
        """Verify the axial coarse-mesh rebalance boundaries"""
        self.assertEqual(self.df.fiveD, None)

    def test_writeBinary(self):
        """Verify binary equivalence of written dif3d file."""
        with TemporaryDirectoryChanger():
            dif3d.Dif3dStream.writeBinary(self.df, "DIF3D2")
            with open(SIMPLE_HEXZ_DIF3D, "rb") as f1, open("DIF3D2", "rb") as f2:
                expectedData = f1.read()
                actualData = f2.read()
            for expected, actual in zip(expectedData, actualData):
                self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
