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

from armi.utils import outputCache
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class TestOutputCache(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    @staticmethod
    def _buildDirWithFiles(arbitraryString):
        """Helper method, to create a directory with a single file in it."""
        # create an output location
        os.mkdir(arbitraryString)

        # create some temp file
        outFile = os.path.join(arbitraryString, f"something_{arbitraryString}.txt")
        with open(outFile, "w") as f:
            f.write("test")

        return outFile

    @staticmethod
    def _buildOutputCache(arbitraryString):
        """
        Helper method, to set up a semi-stupid output cache directory.

        It will have one file and a manifest. It is expected this will be run from within a self-cleaning temp dir.
        """
        # create some temp file
        outFile = f"something_{arbitraryString}.txt"
        with open(outFile, "w") as f:
            f.write("test")

        # create an output location
        os.mkdir(arbitraryString)

        # do the worK: call the function that creates the manifest
        outputCache._makeOutputManifest([outFile], arbitraryString)

    def test_hashFiles(self):
        files = ["test_hashFiles1.txt", "test_hashFiles2.txt"]
        for fileName in files:
            with open(fileName, "w") as f:
                f.write("hi")

        hashed = outputCache._hashFiles(files)

        self.assertEqual(hashed, "e9f5713dec55d727bb35392cec6190ce")

    def test_deleteCache(self):
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
        # validate manifest does not exist yet
        manifest = "test_makeOutputManifest/CRC-manifest.json"
        self.assertFalse(os.path.exists(manifest))

        # create outputCache dir and manifest
        self._buildOutputCache("test_makeOutputManifest")

        # validate manifest was created
        manifest = "test_makeOutputManifest/CRC-manifest.json"
        self.assertTrue(os.path.exists(manifest))

    def test_retrieveOutput(self):
        # create outputCache dir and manifest
        cacheDir = "test_retrieveOutput_Output_Cache"
        self._buildOutputCache(cacheDir)

        # validate manifest was created
        manifest = f"{cacheDir}/CRC-manifest.json"
        self.assertTrue(os.path.exists(manifest))

        # create a dummy file (not executable), to stand in for the executable
        fakeExe = f"what_{cacheDir}.exe"
        with open(fakeExe, "w") as f:
            f.write("hi")

        # create folder to retrieve to
        inputPaths = [f"something_{cacheDir}.txt"]
        newFolder = outputCache._getCachedFolder(fakeExe, inputPaths, cacheDir)
        os.makedirs(newFolder)

        # throw a new manifest into the new out cache
        with open(os.path.join(newFolder, "CRC-manifest.json"), "w") as f:
            f.write(open(manifest, "r").read())

        # attempt to retrieve some output from dummy caches
        result = outputCache.retrieveOutput(fakeExe, inputPaths, cacheDir, newFolder)
        self.assertFalse(result)

    def test_store(self):
        # create a dummy file (not executable), to stand in for the executable
        cacheDir = "test_store"
        fakeExe = f"what_{cacheDir}.exe"
        with open(fakeExe, "w") as f:
            f.write("hi")

        # create some output files and directories
        inputPath = self._buildDirWithFiles("inFile1")
        outputFile = self._buildDirWithFiles("outFile1")

        # run the code and test that it worked
        folderLoc = outputCache._getCachedFolder(fakeExe, [inputPath], cacheDir)
        self.assertFalse(os.path.exists(folderLoc))

        outputCache.store(fakeExe, [inputPath], [outputFile], cacheDir)

        self.assertTrue(os.path.exists(folderLoc))
        self.assertTrue(os.path.exists(os.path.join(folderLoc, "CRC-manifest.json")))
        self.assertTrue(os.path.exists(os.path.join(folderLoc, "something_outFile1.txt")))

    def test_cacheCall(self):
        """Mock up a simple test for cacheCall() where we call a (non-existant) MC2-3 executable, but bypass it because
        there are existing outputs already.
        """
        # create a dummy cache dir
        cacheDir = "mc2CacheDir"

        # create a dummy executable
        executablePath = "mc2-3.py"
        with open(executablePath, "w") as f:
            f.write("print('This is an empty executable.')")

        # create a dummy input file
        inputPaths = [self._buildDirWithFiles("mc2-input123")]

        # create a output file
        outputFileNames = [self._buildDirWithFiles("mc2-output123")]

        # create a dummy method that does not run the executable
        execute = lambda: None

        # run the code and test that it worked
        folderLoc = outputCache._getCachedFolder(executablePath, inputPaths, cacheDir)
        self.assertFalse(os.path.exists(folderLoc))

        outputCache.cacheCall(cacheDir, executablePath, inputPaths, outputFileNames, execute)

        self.assertTrue(os.path.exists(folderLoc))
        self.assertTrue(os.path.exists(os.path.join(folderLoc, "CRC-manifest.json")))
        self.assertTrue(os.path.exists(os.path.join(folderLoc, "something_mc2-output123.txt")))
