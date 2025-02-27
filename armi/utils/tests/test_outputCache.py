# Copyright 2022 TerraPower, LLC
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
"""Tests of the output cache tools."""

import os
import time
import unittest

from armi.utils import directoryChangers, outputCache


class TestOutputCache(unittest.TestCase):
    def _buildOutputCache(self, arbitraryString):
        """
        Helper method, to set up a semi-stupid output cache directory
        It will have one file and a manifest.
        It is expected this will be run from within a self-cleaning temp dir.
        """
        # create some temp file
        outFile = "something_{0}.txt".format(arbitraryString)
        with open(outFile, "w") as f:
            f.write("test")

        # create an output location
        os.mkdir(arbitraryString)

        # do the worK: call the function that creates the manifest
        outputCache._makeOutputManifest([outFile], arbitraryString)

    def test_hashFiles(self):
        with directoryChangers.TemporaryDirectoryChanger() as _:
            files = ["test_hashFiles1.txt", "test_hashFiles2.txt"]
            for fileName in files:
                with open(fileName, "w") as f:
                    f.write("hi")

            hashed = outputCache._hashFiles(files)

            self.assertEqual(hashed, "e9f5713dec55d727bb35392cec6190ce")

    def test_deleteCache(self):
        with directoryChangers.TemporaryDirectoryChanger() as _:
            outDir = "snapshotOutput_Cache"
            self.assertFalse(os.path.exists(outDir))

            os.mkdir(outDir)
            with open(os.path.join(outDir, "test_deleteCache2.txt"), "w") as f:
                f.write("hi there")

            self.assertTrue(os.path.exists(outDir))
            time.sleep(2)
            outputCache.deleteCache(outDir)
            self.assertFalse(os.path.exists(outDir))

    def test_getCachedFolder(self):
        with directoryChangers.TemporaryDirectoryChanger() as _:
            exePath = "/path/to/what.exe"
            inputPaths = ["/path/to/something.txt", "/path/what/some.ini"]
            cacheDir = "/tmp/thing/what/"
            with self.assertRaises(FileNotFoundError):
                _ = outputCache._getCachedFolder(exePath, inputPaths, cacheDir)

            fakeExe = "what_getCachedFolder.exe"
            with open(fakeExe, "w") as f:
                f.write("hi")

            with self.assertRaises(FileNotFoundError):
                _ = outputCache._getCachedFolder(fakeExe, inputPaths, cacheDir)

            fakeIni = "fake_getCachedFolder.ini"
            with open(fakeIni, "w") as f:
                f.write("hey")

            folder = outputCache._getCachedFolder(fakeExe, [fakeIni], cacheDir)
            self.assertTrue(folder.startswith("/tmp/thing/what/what_getCachedFolder"))

    def test_makeOutputManifest(self):
        with directoryChangers.TemporaryDirectoryChanger() as _:
            # validate manifest doesn't exist yet
            manifest = "test_makeOutputManifest/CRC-manifest.json"
            self.assertFalse(os.path.exists(manifest))

            # create outputCache dir and manifest
            self._buildOutputCache("test_makeOutputManifest")

            # validate manifest was created
            manifest = "test_makeOutputManifest/CRC-manifest.json"
            self.assertTrue(os.path.exists(manifest))

    def test_retrieveOutput(self):
        with directoryChangers.TemporaryDirectoryChanger() as _:
            # create outputCache dir and manifest
            cacheDir = "test_retrieveOutput_Output_Cache"
            self._buildOutputCache(cacheDir)

            # validate manifest was created
            manifest = "{0}/CRC-manifest.json".format(cacheDir)
            self.assertTrue(os.path.exists(manifest))

            # create a dummy file (not executable), to stand in for the executable
            fakeExe = "what_{0}.exe".format(cacheDir)
            with open(fakeExe, "w") as f:
                f.write("hi")

            # create folder to retrieve to
            inputPaths = ["something_{0}.txt".format(cacheDir)]
            newFolder = outputCache._getCachedFolder(fakeExe, inputPaths, cacheDir)
            os.makedirs(newFolder)

            # throw a new manifest into the new out cache
            with open(os.path.join(newFolder, "CRC-manifest.json"), "w") as f:
                f.write(open(manifest, "r").read())

            # attempt to retrieve some output from dummy caches
            result = outputCache.retrieveOutput(fakeExe, inputPaths, cacheDir, newFolder)
            self.assertFalse(result)
