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

"""Program that runs tests for the TestHashValues class."""

import os
import platform
import re
import shutil
import sys
import unittest
from contextlib import contextmanager
from io import StringIO

import armi.matProps


@contextmanager
def stdout_redirected(new_stdout):
    """Wraps the stdout output so that it can be compared against expected results."""
    save_stdout = sys.stdout
    sys.stdout = new_stdout
    try:
        yield None
    finally:
        sys.stdout = save_stdout


def parseSha1Contents(lineList):
    """
    Constructs a dictionary from default lines or lines from Material.print_loaded_SHA1s() that maps material names to
    SHA1 values.

    Parameters
    ----------
    lineList
        List of strings parsed from stdout. Each element represents a line printed from stdout.

    Returns
    -------
    dict
        Dictionary mapping material name to SHA1 value.
    """
    sha1sumRegex = re.compile(r"SHA1 value for material (\S+) is (\S+)\.")

    materialValue, hashValue = None, None
    fileHashDict = {}

    for line in lineList:
        sha1SumResult = sha1sumRegex.search(line)
        if sha1SumResult is None:
            raise RuntimeError(f"Could not parse sha1sum results from line\n{line}\n")

        materialValue = sha1SumResult.group(1)
        hashValue = sha1SumResult.group(2)
        fileHashDict[materialValue] = hashValue

    return fileHashDict


def parseLoadedFiles(lineList):
    """
    Constructs a list of files whose material information was loaded into armi.matProps.materials from lines printed out
    by Material.print_sha1().

    Parameters
    ----------
    lineList
        List of strings parsed from stdout. Each element represents a line printed from stdout.

    Returns
    -------
    list
        List of files whose Material instances were loaded into armi.matProps.materials.
    """
    searchLine = "Material is saved into armi.matProps"
    materialRegex = re.compile(r"SHA1 value for material (\S+)")
    materialList = []
    for line in lineList:
        if searchLine in line:
            materialResult = materialRegex.search(line)
            if materialResult is None:
                raise RuntimeError(f"Could not parse material name from line\n{line}\n")

            material = materialResult.group(1)
            materialList.append(material)

    return materialList


class TestHashValues(unittest.TestCase):
    """Class which covers the unit tests for hashing."""

    @classmethod
    def cloneTestFile(cls, fileName):
        """
        Creates a copy of the repository test yaml files. These test files will have their clrf eol characters removed
        to allow for a common sha1 dictionary to be used regardless of platform.

        Parameters
        ----------
        fileName
            Name of repository test file that will be cloned and have its clrf eol characters removed.
        """
        baseDir = cls.repoTestDir + os.path.sep
        index = len(baseDir)
        componentName = fileName[index:]
        cloneFileName = os.path.join(cls.mirrorDir, componentName)
        if not os.path.exists(os.path.dirname(cloneFileName)):
            os.makedirs(os.path.dirname(cloneFileName))
        shutil.copy(fileName, cloneFileName)
        with open(cloneFileName, encoding="utf-8") as readFile:
            content = readFile.read()

        with open(cloneFileName, "w", encoding="utf-8", newline="\n") as writeFile:
            writeFile.write(content)

    @classmethod
    def setUpClass(cls):
        """Initializes class data members. Creates mirror directory on Windows."""
        cls.repoTestDir = os.path.dirname(os.path.realpath(__file__))
        cls.mirrorDir = os.path.realpath(os.path.join(cls.repoTestDir, "..", "testsMirror"))
        if platform.system() == "Windows":
            if os.path.exists(cls.mirrorDir):
                shutil.rmtree(cls.mirrorDir)

            for root, _, files in os.walk(cls.repoTestDir):
                for name in files:
                    if name.endswith(".yaml"):
                        cls.cloneTestFile(os.path.join(root, name))

    def tearDown(self):  # noqa: PLR6301
        """Clears armi.matProps of material data between tests."""
        armi.matProps.clear()

    @property
    def testDir(self):
        """Provides the root testing directory of the relevant test yaml files."""
        if platform.system() == "Windows":
            return self.mirrorDir
        else:
            return self.repoTestDir

    def test_data_print_sha1_save(self):
        materialA = "a"
        materialB = "materialB"
        testFile1 = os.path.join(self.testDir, "testDir1", f"{materialA}.yaml")
        testFile2 = os.path.join(self.testDir, "testMaterialsData", f"{materialB}.yaml")
        expectedDict = {
            materialA: "6c4051c8784e5845c22b2a0e5b258c0f180a0a79",
            materialB: "2bf5a91a68d80eb861ba6ee1aa20f0ec9973b43a",
        }
        expectedLoadedMaterials = [materialA, materialB]

        matA = armi.matProps.load_material(testFile1, True)
        matB = armi.matProps.load_material(testFile2, True)

        captured_output = StringIO()

        with stdout_redirected(captured_output):
            matA.print_sha1()
            matB.print_sha1()

        output = [line for line in captured_output.getvalue().splitlines() if line.strip()]

        outputDict = parseSha1Contents(output)
        self.assertEqual(outputDict, expectedDict)

        outputLoadedMaterials = parseLoadedFiles(output)
        self.assertEqual(outputLoadedMaterials, expectedLoadedMaterials)

    def test_data_hash_load_material_no_save(self):
        materialA = "a"
        materialB = "materialB"
        testFile1 = os.path.join(self.testDir, "testDir1", f"{materialA}.yaml")
        testFile2 = os.path.join(self.testDir, "testMaterialsData", f"{materialB}.yaml")
        expectedDict = {
            materialA: "6c4051c8784e5845c22b2a0e5b258c0f180a0a79",
            materialB: "2bf5a91a68d80eb861ba6ee1aa20f0ec9973b43a",
        }

        captured_output = StringIO()

        with stdout_redirected(captured_output):
            _ = armi.matProps.load_material(testFile1, False)
            _ = armi.matProps.load_material(testFile2)

        output = [line for line in captured_output.getvalue().splitlines() if line.strip()]

        outputDict = parseSha1Contents(output)
        self.assertEqual(outputDict, expectedDict)

        outputLoadedMaterials = parseLoadedFiles(output)
        self.assertEqual(len(outputLoadedMaterials), 0)

    def test_data_hash_load_all(self):
        materialA, materialB, materialC, materialD = "a", "b", "c", "d"
        testDir1 = os.path.join(self.testDir, "testDir1")
        testDir2 = os.path.join(self.testDir, "testDir2")
        armi.matProps.load_all(testDir1)
        armi.matProps.load_all(testDir2)

        expectedDict = {
            materialA: "6c4051c8784e5845c22b2a0e5b258c0f180a0a79",
            materialB: "868b0dff4ba6dc716ee926ddb4005c320b7e2554",
            materialC: "8042c141cd29c4f1612aeb354f0cb2dc4651c680",
            materialD: "c07f27b199790270cb825430810046fa934de3fa",
        }

        expectedLoadedMaterials = [materialA, materialB, materialC, materialD]

        captured_output = StringIO()

        with stdout_redirected(captured_output):
            armi.matProps.print_hashes()

        output = [line for line in captured_output.getvalue().splitlines() if line.strip()]

        outputDict = parseSha1Contents(output)
        self.assertEqual(outputDict, expectedDict)

        outputLoadedMaterials = parseLoadedFiles(output)
        self.assertEqual(set(outputLoadedMaterials), set(expectedLoadedMaterials))

    def test_data_hash_print_hashes(self):
        testDir1 = os.path.join(self.testDir, "testDir1")
        testDir2 = os.path.join(self.testDir, "testDir2")

        materialA, materialB, materialC, materialD = "a", "b", "c", "d"

        matFileA = os.path.join(testDir1, f"{materialA}.yaml")
        matFileB = os.path.join(testDir1, f"{materialB}.yaml")

        _ = armi.matProps.load_material(matFileA, True)
        _ = armi.matProps.load_material(matFileB, False)
        armi.matProps.load_all(testDir2)

        captured_output = StringIO()

        with stdout_redirected(captured_output):
            armi.matProps.print_hashes()

        output = [line for line in captured_output.getvalue().splitlines() if line.strip()]

        outputDict = parseSha1Contents(output)
        expectedDict = {
            materialA: "6c4051c8784e5845c22b2a0e5b258c0f180a0a79",
            materialC: "8042c141cd29c4f1612aeb354f0cb2dc4651c680",
            materialD: "c07f27b199790270cb825430810046fa934de3fa",
        }
        self.assertEqual(outputDict, expectedDict)

        outputLoadedMaterials = parseLoadedFiles(output)
        expectedLoadedMaterials = [materialA, materialC, materialD]
        self.assertEqual(outputLoadedMaterials, expectedLoadedMaterials)
