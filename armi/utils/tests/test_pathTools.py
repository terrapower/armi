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
import os
import types

from armi.utils import pathTools
from armi.utils import directoryChangers
from armi import ROOT

THIS_DIR = os.path.dirname(__file__)


class PathToolsTests(unittest.TestCase):
    def test_separateModuleAndAttribute(self):
        self.assertRaises(
            ValueError, pathTools.separateModuleAndAttribute, r"path/with/no/colon"
        )
        self.assertEqual(
            (r"aPath/file.py", "MyClass"),
            pathTools.separateModuleAndAttribute(r"aPath/file.py:MyClass"),
        )
        # testing windows stuff mapped drives since they have more than 1 colon
        self.assertEqual(
            (r"c:/aPath/file.py", "MyClass"),
            pathTools.separateModuleAndAttribute(r"c:/aPath/file.py:MyClass"),
        )
        # not what we want but important to demonstrate what you get when no module
        # attribute is defined.
        self.assertEqual(
            ("c", r"/aPath/file.py"),
            pathTools.separateModuleAndAttribute(r"c:/aPath/file.py"),
        )

    def test_importCustomModule(self):
        """Test that importCustomPyModule is usable just like any other module."""
        module = pathTools.importCustomPyModule(os.path.join(THIS_DIR, __file__))
        self.assertIsInstance(module, types.ModuleType)
        self.assertIn("THIS_DIR", module.__dict__)
        # test that this class is present in the import
        self.assertIn(self.__class__.__name__, module.__dict__)

    def test_moduleAndAttributeExist(self):
        """Test that determination of existence of module attribute works."""

        # test that no `:` doesn't raise an exception
        self.assertFalse(pathTools.moduleAndAttributeExist(r"path/that/not/exist.py"))
        # test that multiple `:` doesn't raise an exception
        self.assertFalse(
            pathTools.moduleAndAttributeExist(r"c:/path/that/not/exist.py:MyClass")
        )
        thisFile = os.path.join(THIS_DIR, __file__)
        # no module attribute specified
        self.assertFalse(pathTools.moduleAndAttributeExist(thisFile))
        self.assertFalse(pathTools.moduleAndAttributeExist(thisFile + ":doesntExist"))
        self.assertTrue(pathTools.moduleAndAttributeExist(thisFile + ":THIS_DIR"))
        self.assertTrue(pathTools.moduleAndAttributeExist(thisFile + ":PathToolsTests"))


if __name__ == "__main__":
    unittest.main()
