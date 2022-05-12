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
from pathlib import Path
import shutil

from armi.utils import directoryChangers
from armi.utils import directoryChangersMpi


class ExpectedException(Exception):
    pass


class TestDirectoryChangers(unittest.TestCase):
    """Tests for directory changers."""

    def setUp(self):
        self.temp_directory = (
            self._testMethodName + "ThisIsATemporaryDirectory-AAZZ0099"
        )
        if os.path.exists(self.temp_directory):
            shutil.rmtree(self.temp_directory)

    def tearDown(self):
        if os.path.exists(self.temp_directory):
            shutil.rmtree(self.temp_directory)

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

    def test_exception(self):
        """Make sure directory changers bring back full folder when an exception is raised."""
        try:
            with directoryChangers.ForcedCreationDirectoryChanger(self.temp_directory):
                Path("file1.txt").touch()
                Path("file2.txt").touch()
                os.mkdir("subdir")
                raise ExpectedException("Ooops")
        except ExpectedException:
            pass

        retrievedFolder = f"dump-{self.temp_directory}"
        self.assertTrue(os.path.exists(os.path.join(retrievedFolder, "file1.txt")))
        self.assertTrue(os.path.exists(os.path.join(retrievedFolder, "file2.txt")))
        shutil.rmtree(retrievedFolder)

    def test_exception_disabled(self):
        """Make sure directory changers do not bring back full folder when handling is disabled."""
        try:
            with directoryChangers.ForcedCreationDirectoryChanger(
                self.temp_directory, dumpOnException=False
            ):
                Path("file1.txt").touch()
                Path("file2.txt").touch()
                raise ExpectedException("Ooops")
        except ExpectedException:
            pass

        self.assertFalse(
            os.path.exists(os.path.join(f"dump-{self.temp_directory}", "file1.txt"))
        )

    def test_change_to_nonexisting_fails(self):
        """Fail if destination doesn't exist."""
        with self.assertRaises(OSError):
            with directoryChangers.DirectoryChanger(self.temp_directory):
                pass

    def test_change_to_nonexisting_works_forced(self):
        """Succeed with forced creation even when destination doesn't exist."""
        with directoryChangers.ForcedCreationDirectoryChanger(self.temp_directory):
            pass

    def test_temporary_cleans(self):
        """Make sure Temporary cleaner cleans up temporary files."""
        with directoryChangers.TemporaryDirectoryChanger() as dc:
            Path("file1.txt").touch()
            Path("file2.txt").touch()
            tempName = dc.destination

        self.assertFalse(os.path.exists(tempName))

    def test_file_retrieval(self):
        """
        Make sure requested files and/or globs get copied back.

        * Checks basic copy feature
        * Checks rename feature
        * Checks glob expansion
        """

        def f(name):
            """Utility to avoid test clashes during cleanups"""
            return self._testMethodName + name

        with directoryChangers.TemporaryDirectoryChanger(
            filesToRetrieve=[(f("file1.txt"), f("newfile1.txt"))]
        ):
            Path(f("file1.txt")).touch()
            Path(f("file2.txt")).touch()

        self.assertTrue(os.path.exists(f("newfile1.txt")))
        os.remove(f("newfile1.txt"))

        with directoryChangers.TemporaryDirectoryChanger(
            filesToRetrieve=[f("file*.txt")]
        ) as dc:
            Path(f("file1.txt")).touch()
            Path(f("file2.txt")).touch()

        self.assertTrue(os.path.exists(f("file1.txt")))
        self.assertTrue(os.path.exists(f("file2.txt")))
        os.remove(f("file1.txt"))
        os.remove(f("file2.txt"))

    def test_file_retrieval_missing_file(self):
        """Tests that the directory changer still returns a subset of files even if all do not exist."""

        def f(name):
            """Utility to avoid test clashes during cleanups"""
            return self._testMethodName + name

        with directoryChangers.TemporaryDirectoryChanger(
            filesToRetrieve=[f("file1.txt"), f("file2.txt")]
        ):
            Path(f("file1.txt")).touch()

        self.assertTrue(os.path.exists(f("file1.txt")))
        self.assertFalse(os.path.exists(f("file2.txt")))
        os.remove(f("file1.txt"))
