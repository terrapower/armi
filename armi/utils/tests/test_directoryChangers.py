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

"""Module for testing directoryChangers."""
import os
import unittest

from armi.utils import directoryChangers
from armi.utils import directoryChangersMpi


class TestDirectoryChangers(unittest.TestCase):
    """Tests for directory changers."""

    def setUp(self):
        self.temp_directory = (
            self._testMethodName + "ThisIsATemporaryDirectory-AAZZ0099"
        )
        if os.path.exists(self.temp_directory):
            os.rmdir(self.temp_directory)

    def test_mpiAction(self):
        try:
            os.mkdir(self.temp_directory)
            cdma = directoryChangersMpi._ChangeDirectoryMpiAction(
                self.temp_directory
            )  # pylint: disable=protected-access
            self.assertTrue(cdma.invoke(None, None, None))
        finally:
            os.chdir("..")
            os.rmdir(self.temp_directory)

    def test_mpiActionFailsOnNonexistentPath(self):
        with self.assertRaises(IOError):
            cdma = directoryChangersMpi._ChangeDirectoryMpiAction(
                self.temp_directory
            )  # pylint: disable=protected-access
            cdma.invoke(None, None, None)
