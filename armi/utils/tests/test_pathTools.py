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
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access,no-member,disallowed-name,invalid-name
import unittest
import os
import tempfile
import types

from armi.utils import pathTools

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

    def test_cleanPathOnValidPaths(self):
        """Test cleanPaths by cleaning a path for a file, an empty folder, and a file containing a folder.
        Test in an initialized armi context to include MPI."""
        import armi

        testParentFolderPath = tempfile.mkdtemp(
            dir=str(os.path.join(THIS_DIR)), prefix="testCleanPath"
        )

        testFolderPath = tempfile.mkdtemp(
            dir=testParentFolderPath, prefix="testCleanPath", suffix="testFolder"
        )
        fileFd, testFilePath = tempfile.mkstemp(
            dir=testParentFolderPath, prefix="testCleanPath", suffix="testFile"
        )
        folderWithFileInside = tempfile.mkdtemp(
            dir=testParentFolderPath,
            prefix="testCleanPath",
            suffix="testFolderWithFile",
        )
        _, tempFileInTestFolder = tempfile.mkstemp(
            dir=folderWithFileInside, prefix="testCleanPath", suffix="testFileInFolder"
        )

        self.assertTrue(os.path.exists(testFilePath))
        self.assertTrue(os.path.exists(tempFileInTestFolder))
        self.assertTrue(os.path.exists(folderWithFileInside))
        self.assertTrue(os.path.exists(testFolderPath))

        testResults = [
            pathTools.cleanPath(test)
            for test in [folderWithFileInside, testFilePath, testFolderPath]
        ]

        self.assertEqual([True, True, True], testResults)
        self.assertFalse(os.path.exists(testFilePath))
        self.assertFalse(os.path.exists(tempFileInTestFolder))
        self.assertFalse(os.path.exists(folderWithFileInside))
        self.assertFalse(os.path.exists(testFolderPath))

        os.close(fileFd)
        os.rmdir(testParentFolderPath)

    def test_cleanPathOnInvalidPath(self):
        """Test cleanPath when passed an 'invalid' path not present in the list of valid paths inside cleanPath.
        Test in an initialized armi context to include MPI."""
        import armi

        with tempfile.TemporaryDirectory() as invalidFolderPath:
            self.assertRaises(Exception, pathTools.cleanPath, invalidFolderPath)


if __name__ == "__main__":
    unittest.main()
