# Copyright 2024 TerraPower, LLC
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

"""Test the reading and writing of the DIF3D FIXSRC file format."""
# ruff: noqa: E501
import numpy as np
import os
import unittest

from armi.nuclearDataIO.cccc import fixsrc
from armi.utils.directoryChangers import TemporaryDirectoryChanger

THIS_DIR = os.path.dirname(__file__)

FIXSRC_ASCII = """0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.400773529E+10 0.420960166E+10 0.482217466E+10 0.515352953E+10 0.492640631E+10 0.462049678E+10
0.424579058E+10 0.375705157E+10 0.331109843E+10 0.347941464E+10 0.357026393E+10 0.324041693E+10 0.294185827E+10 0.290284208E+10 0.292508320E+10 0.276336392E+10 0.241353762E+10 0.203581568E+10
0.165570000E+10 0.147688523E+10 0.145537921E+10 0.143562608E+10 0.129712804E+10 0.115290008E+10 0.100961455E+10 0.884121899E+09 0.792349039E+09 0.726549275E+09 0.657507586E+09 0.588993652E+09
0.502686828E+09 0.414645952E+09 0.347394860E+09 0.301480158E+09 0.240354797E+09 0.235586152E+09 0.163417513E+09 0.152059467E+09 0.125767834E+09 0.903158783E+08 0.615758380E+08 0.398285540E+08
0.313411195E+08 0.302950333E+08 0.298257082E+08 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00
0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00 0.000000000E+00"""
FIXSRC_ARRAY = np.array(FIXSRC_ASCII.split(), dtype=np.float32).reshape((3, 3, 2, 4))


class TestFixsrc(unittest.TestCase):
    def test_writeReadBinaryLoop(self):
        with TemporaryDirectoryChanger() as newDir:
            fileName = "fixsrc_writeBinary.bin"
            binaryFilePath = os.path.join(newDir.destination, fileName)
            fixsrc.writeBinary(binaryFilePath, FIXSRC_ARRAY)

            self.assertIn(fileName, os.listdir(newDir.destination))
            self.assertGreater(os.path.getsize(binaryFilePath), 0)
