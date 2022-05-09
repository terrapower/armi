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
import os
import types
import unittest

from armi import context
from armi.utils import pathTools
from armi.utils.directoryChangers import TemporaryDirectoryChanger

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

    @unittest.skipUnless(context.MPI_RANK == 0, "test only on root node")
    def test_cleanPathNoMpi(self):
        """Simple tests of cleanPath(), in the no-MPI scenario"""
        # Test 0: File is not safe to delete, due to name pathing
        with TemporaryDirectoryChanger():
            filePath0 = "test0_cleanPathNoMpi"
            open(filePath0, "w").write("something")

            self.assertTrue(os.path.exists(filePath0))
            with self.assertRaises(Exception):
                pathTools.cleanPath(filePath0, mpiRank=0)

        # Test 1: Delete a single file
        with TemporaryDirectoryChanger():
            filePath1 = "test1_cleanPathNoMpi_mongoose"
            open(filePath1, "w").write("something")

            self.assertTrue(os.path.exists(filePath1))
            pathTools.cleanPath(filePath1, mpiRank=0)
            self.assertFalse(os.path.exists(filePath1))

        # Test 2: Delete an empty directory
        with TemporaryDirectoryChanger():
            dir2 = "mongoose"
            os.mkdir(dir2)

            self.assertTrue(os.path.exists(dir2))
            pathTools.cleanPath(dir2, mpiRank=0)
            self.assertFalse(os.path.exists(dir2))

        # Test 3: Delete a directory with two files inside
        with TemporaryDirectoryChanger():
            # create directory
            dir3 = "mongoose"
            os.mkdir(dir3)

            # throw in a couple of simple text files
            open(os.path.join(dir3, "file1.txt"), "w").write("something1")
            open(os.path.join(dir3, "file2.txt"), "w").write("something2")

            # delete the directory and test
            self.assertTrue(os.path.exists(dir3))
            self.assertTrue(os.path.exists(os.path.join(dir3, "file1.txt")))
            self.assertTrue(os.path.exists(os.path.join(dir3, "file2.txt")))
            pathTools.cleanPath(dir3, mpiRank=0)
            self.assertFalse(os.path.exists(dir3))


if __name__ == "__main__":
    unittest.main()
