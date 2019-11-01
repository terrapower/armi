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

"""
Unit tests for pathTools.
"""
import unittest
from os import path


from armi.utils import pathTools
from armi.utils import directoryChangers
from armi import ROOT

THIS_DIR = pathTools.armiAbsDirFromName(__name__)


class PathToolsTests(unittest.TestCase):
    def test_getFullFileNames(self):
        with directoryChangers.DirectoryChanger(THIS_DIR):
            baseCall = pathTools.getFullFileNames()
            # all variations should return the same values.
            self.assertEqual(
                pathTools.getFullFileNames(), pathTools.getFullFileNames(THIS_DIR)
            )
            self.assertEqual(
                pathTools.getFullFileNames(recursive=True),
                pathTools.getFullFileNames(THIS_DIR, recursive=True),
            )

    def test_armiAbsDir(self):
        result = pathTools.armiAbsDirFromName("armi.utils.tests.test1")
        self.assertEqual(result, path.join(ROOT, "utils", "tests"))

    def test_armiAbsDir_name(self):
        result = pathTools.armiAbsDirFromName(__name__)
        self.assertEqual(result, path.join(ROOT, "utils", "tests"))


if __name__ == "__main__":
    unittest.main()
