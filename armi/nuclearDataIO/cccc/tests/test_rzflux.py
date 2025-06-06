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
"""Test rzflux reading and writing."""

import os
import unittest

from armi.nuclearDataIO.cccc import rzflux
from armi.utils.directoryChangers import TemporaryDirectoryChanger

THIS_DIR = os.path.dirname(__file__)
# This RZFLUX was made by DIF3D 11 in a Cartesian test case.
SIMPLE_RZFLUX = os.path.join(THIS_DIR, "fixtures", "simple_cartesian.rzflux")


class TestRzflux(unittest.TestCase):
    """Tests the rzflux class."""

    def test_readRzflux(self):
        """Ensure we can read a RZFLUX file."""
        flux = rzflux.readBinary(SIMPLE_RZFLUX)
        self.assertEqual(flux.groupFluxes.shape, (flux.metadata["NGROUP"], flux.metadata["NZONE"]))

    def test_writeRzflux(self):
        """Ensure that we can write a modified RZFLUX file."""
        with TemporaryDirectoryChanger():
            flux = rzflux.readBinary(SIMPLE_RZFLUX)
            rzflux.writeBinary(flux, "RZFLUX2")
            self.assertTrue(binaryFilesEqual(SIMPLE_RZFLUX, "RZFLUX2"))
            # perturb off-diag item to check row/col ordering
            flux.groupFluxes[2, 10] *= 1.1
            flux.groupFluxes[12, 1] *= 1.2
            rzflux.writeBinary(flux, "RZFLUX3")
            flux2 = rzflux.readBinary("RZFLUX3")
            self.assertAlmostEqual(flux2.groupFluxes[12, 1], flux.groupFluxes[12, 1])

    def test_rwAscii(self):
        """Ensure that we can read/write in ascii format."""
        with TemporaryDirectoryChanger():
            flux = rzflux.readBinary(SIMPLE_RZFLUX)
            rzflux.writeAscii(flux, "RZFLUX.ascii")
            flux2 = rzflux.readAscii("RZFLUX.ascii")
            self.assertTrue((flux2.groupFluxes == flux.groupFluxes).all())


def binaryFilesEqual(fn1, fn2):
    """True if two files are bytewise identical."""
    with open(fn1, "rb") as f1, open(fn2, "rb") as f2:
        for byte1, byte2 in zip(f1, f2):
            if byte1 != byte2:
                return False
    return True
