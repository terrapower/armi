# Copyright 2026 TerraPower, LLC
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

"""Program that runs all of the tests contained in VersionTests class."""

import os
import sys
import unittest


def cleanFolder(folder):
    """
    Clean up a folder. If a file is locked by the OS, it will not be deleted and the folder structure leading to it will
    be retained.
    """
    folderItems = os.listdir(folder)
    for item in folderItems:
        itemPath = os.path.join(folder, item)
        if os.path.isdir(itemPath):
            cleanFolder(itemPath)
            if len(os.listdir(itemPath)) == 0:
                os.rmdir(itemPath)
        else:
            try:
                os.remove(itemPath)
            except OSError as e:
                print(f"Warning: Could not delete file: {item}")
                print("Failed with:", e.strerror)


class VersionTests(unittest.TestCase):
    """Class which contains tests for the matProps Version class."""

    @classmethod
    def setUpClass(cls):
        """Create the /temporary subfolder and add all generated .txt test files there."""
        cls.startingWorkingDir = os.getcwd()
        testFolder = os.path.dirname(os.path.realpath(__file__))
        cls.outputFolder = os.path.join(testFolder, "versionTemporary")
        if os.path.exists(cls.outputFolder) is False:
            os.makedirs(cls.outputFolder)
        cleanFolder(cls.outputFolder)
        os.chdir(cls.outputFolder)

    def test_pythonVersion(self):
        """This is just a helper test to dump the python version."""
        pyVersion = sys.version

        with open(os.path.join(self.outputFolder, "pythonVersion.txt"), "w", encoding="utf-8") as versionFile:
            versionFile.write(pyVersion)
