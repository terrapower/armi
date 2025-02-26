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
"""Test GEODST reading and writing."""

import os
import unittest

from numpy.testing import assert_equal

from armi.nuclearDataIO.cccc import geodst
from armi.utils.directoryChangers import TemporaryDirectoryChanger

THIS_DIR = os.path.dirname(__file__)
SIMPLE_GEODST = os.path.join(THIS_DIR, "fixtures", "simple_hexz.geodst")


class TestGeodst(unittest.TestCase):
    """
    Tests the GEODST class.

    This reads from a GEODST file that was created using DIF3D 11 on a small
    test hex reactor in 1/3 geometry.
    """

    def test_readGeodst(self):
        """Ensure we can read a GEODST file.

        .. test:: Test reading GEODST files.
            :id: T_ARMI_NUCDATA_GEODST0
            :tests: R_ARMI_NUCDATA_GEODST
        """
        geo = geodst.readBinary(SIMPLE_GEODST)
        self.assertEqual(geo.metadata["IGOM"], 18)
        self.assertAlmostEqual(geo.xmesh[1], 16.79, places=5)  # hex pitch
        self.assertAlmostEqual(geo.zmesh[-1], 448.0, places=5)  # top of reactor in cm
        self.assertEqual(geo.coarseMeshRegions.shape, (10, 10, len(geo.zmesh) - 1))
        self.assertEqual(geo.coarseMeshRegions.min(), 0)
        self.assertEqual(geo.coarseMeshRegions.max(), geo.metadata["NREG"])

    def test_writeGeodst(self):
        """Ensure that we can write a modified GEODST.

        .. test:: Test writing GEODST files.
            :id: T_ARMI_NUCDATA_GEODST1
            :tests: R_ARMI_NUCDATA_GEODST
        """
        with TemporaryDirectoryChanger():
            geo = geodst.readBinary(SIMPLE_GEODST)
            geo.zmesh[-1] *= 2
            geodst.writeBinary(geo, "GEODST2")
            geo2 = geodst.readBinary("GEODST2")
            self.assertAlmostEqual(geo2.zmesh[-1], 448.0 * 2, places=5)
            assert_equal(geo.kintervals, geo2.kintervals)
