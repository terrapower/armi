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
"""Test PWDINT reading and writing."""

import os
import unittest

from armi.nuclearDataIO.cccc import pwdint
from armi.utils.directoryChangers import TemporaryDirectoryChanger

THIS_DIR = os.path.dirname(__file__)
SIMPLE_PWDINT = os.path.join(THIS_DIR, "fixtures", "simple_cartesian.pwdint")


class TestGeodst(unittest.TestCase):
    r"""
    Tests the PWDINT class.

    This reads from a PWDINT file that was created using DIF3D 11 on a small
    test hex reactor in 1/3 geometry.
    """

    def test_readGeodst(self):
        """Ensure we can read a PWDINT file."""
        pwr = pwdint.readBinary(SIMPLE_PWDINT)
        self.assertGreater(pwr.powerDensity.min(), 0.0)

    def test_writeGeodst(self):
        """Ensure that we can write a modified PWDINT."""
        with TemporaryDirectoryChanger():
            pwr = pwdint.readBinary(SIMPLE_PWDINT)
            pwdint.writeBinary(pwr, "PWDINT2")
            pwr2 = pwdint.readBinary("PWDINT2")
            self.assertTrue((pwr2.powerDensity == pwr.powerDensity).all())
