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
import os
import unittest

import numpy as np

from armi.nuclearDataIO.cccc import fixsrc
from armi.utils.directoryChangers import TemporaryDirectoryChanger

# ruff: noqa: E501
FIXSRC_ASCII = """0 0 0 0 0 0 0.4008E+10 0.4210E+10 0.4822E+10 0.5154E+10 0.4926E+10 0.4621E+10
0.4246E+10 0.3757E+10 0.3311E+10 0.3479E+10 0.357E+10 0.324E+10 0.2942E+10 0.2903E+10 0.2925E+10 0.2763E+10 0.2414E+10 0.2036E+10
0.1656E+10 0.1477E+10 0.1455E+10 0.1434E+10 0.1297E+10 0.1153E+10 0.101E+10 0.8841E+9 0.7923E+9 0.7266E+9 0.6575E+9 0.589E+9
0.5027E+9 0.4146E+9 0.3474E+9 0.3015E+9 0.2403E+9 0.2356E+9 0.1634E+9 0.1521E+9 0.1258E+9 0.9032E+8 0.6156E+8 0.3983E+8
0.3134E+8 0.303E+8 0.2983E+8 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0"""
FIXSRC_ARRAY = np.array(FIXSRC_ASCII.split(), dtype=np.float32).reshape((3, 3, 2, 4))


class TestFixsrc(unittest.TestCase):
    def test_writeReadBinaryLoop(self):
        with TemporaryDirectoryChanger() as newDir:
            fileName = "fixsrc_writeBinary.bin"
            binaryFilePath = os.path.join(newDir.destination, fileName)
            fixsrc.writeBinary(binaryFilePath, FIXSRC_ARRAY)

            self.assertIn(fileName, os.listdir(newDir.destination))
            self.assertGreater(os.path.getsize(binaryFilePath), 0)
