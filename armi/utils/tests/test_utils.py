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

"""Testing some utility functions."""
import os
import unittest
from collections import defaultdict

import numpy as np

from armi import utils
from armi.settings.caseSettings import Settings
from armi.testing import loadTestReactor
from armi.tests import mockRunLogs
from armi.utils import (
    codeTiming,
    directoryChangers,
    getAvailabilityFactors,
    getBurnSteps,
    getCumulativeNodeNum,
    getCycleLengths,
    getCycleNames,
    getCycleNodeFromCumulativeNode,
    getCycleNodeFromCumulativeStep,
    getFileSHA1Hash,
    getMaxBurnSteps,
    getNodesPerCycle,
    getPowerFractions,
    getPreviousTimeNode,
    getStepLengths,
    hasBurnup,
    safeCopy,
    safeMove,
)


class TestGeneralUtils(unittest.TestCase):
    def test_getFileSHA1Hash(self):
        with directoryChangers.TemporaryDirectoryChanger():
            path = "test.txt"
            with open(path, "w") as f1:
                f1.write("test")
            sha = getFileSHA1Hash(path)
            self.assertIn("a94a8", sha)

    def test_getFileSHA1HashDir(self):
        with directoryChangers.TemporaryDirectoryChanger():
            pathDir = "testDir"
            path1 = os.path.join(pathDir, "test1.txt")
            path2 = os.path.join(pathDir, "test2.txt")
            os.mkdir(pathDir)
            for i, path in enumerate([path1, path2]):
                with open(path, "w") as f1:
                    f1.write(f"test{i}")
            sha = getFileSHA1Hash(pathDir)
            self.assertIn("ccd13", sha)

    def test_mergeableDictionary(self):
        mergeableDict = utils.MergeableDict()
        normalDict = {"luna": "thehusky", "isbegging": "fortreats", "right": "now"}
        mergeableDict.merge(
            {"luna": "thehusky"}, {"isbegging": "fortreats"}, {"right": "now"}
        )
        self.assertEqual(mergeableDict, normalDict)

    def test_createFormattedStrWithDelimiter(self):
        # Test with a random list of strings
        dataList = ["hello", "world", "1", "2", "3", "4", "5"]
        maxNumberOfValuesBeforeDelimiter = 3
        delimiter = "\n"
        outputStr = utils.createFormattedStrWithDelimiter(
            dataList=dataList,
            maxNumberOfValuesBeforeDelimiter=maxNumberOfValuesBeforeDelimiter,
            delimiter=delimiter,
        )
        self.assertEqual(outputStr, "hello, world, 1,\n2, 3,\n4, 5\n")

        outputStr = utils.createFormattedStrWithDelimiter(
            dataList=dataList,
            maxNumberOfValuesBeforeDelimiter=0,
            delimiter=delimiter,
        )
        self.assertEqual(outputStr, "hello, world, 1, 2, 3, 4, 5\n")

        # test with an empty list
        dataList = []
        outputStr = utils.createFormattedStrWithDelimiter(
            dataList=dataList,
            maxNumberOfValuesBeforeDelimiter=maxNumberOfValuesBeforeDelimiter,
            delimiter=delimiter,
        )
        self.assertEqual(outputStr, "")

    def test_capStrLen(self):
        # Test with strings
        str1 = utils.capStrLen("sodium", 5)
        self.assertEqual("so...", str1)
        str1 = utils.capStrLen("potassium", 6)
        self.assertEqual("pot...", str1)
        str1 = utils.capStrLen("rubidium", 7)
        self.assertEqual("rubi...", str1)
        with self.assertRaises(Exception):
            str1 = utils.capStrLen("sodium", 2)

    def test_list2str(self):
        # Test with list of strings
        list1 = ["One", "Two"]
        list2 = ["Three", "Four"]
        str1 = "OneTwo"
        str2 = utils.list2str(list1, 4, None, None)
        self.assertEqual(str1, str2)
        str1 = "One  Two  "
        str2 = utils.list2str(list1, None, None, 5)
        self.assertEqual(str1, str2)
        str1 = "OneTwoThreeFour"
        str2 = utils.list2str(list2, None, list1, None)
        self.assertEqual(str1, str2)
        str1 = "OneTwoThreeFourT...Four"
        str2 = utils.list2str(list2, 4, list1, None)
        self.assertEqual(str1, str2)
        str1 = "OneTwoThreeFourT...FourThreeFour "
        str2 = utils.list2str(list2, None, list1, 5)
        self.assertEqual(str1, str2)
        str1 = "OneTwoThreeFourT...FourThreeFour T... Four "
        str2 = utils.list2str(list2, 4, list1, 5)
        self.assertEqual(str1, str2)

    def test_slantSplit(self):
        x1 = utils.slantSplit(10.0, 4.0, 4)
        x2 = utils.slantSplit(10.0, 4.0, 4, order="high first")
        self.assertListEqual(x1, [1.0, 2.0, 3.0, 4.0])
        self.assertListEqual(x2, [4.0, 3.0, 2.0, 1.0])

    def test_prependToList(self):
        a = ["hello", "world"]
        b = [1, 2, 3]
        utils.prependToList(a, b)
        self.assertListEqual(a, [1, 2, 3, "hello", "world"])

    def test_plotMatrix(self):
        matrix = np.zeros([2, 2], dtype=float)
        matrix[0, 0] = 1
        matrix[0, 1] = 2
        matrix[1, 0] = 3
        matrix[1, 1] = 4
        xtick = ([0, 1], ["1", "2"])
        ytick = ([0, 1], ["1", "2"])
        fname = "test_plotMatrix_testfile"
        with directoryChangers.TemporaryDirectoryChanger():
            utils.plotMatrix(matrix, fname, show=False, title="plot")
            utils.plotMatrix(matrix, fname, show=False, minV=0, maxV=5, figsize=[3, 4])
            utils.plotMatrix(matrix, fname, show=False, xticks=xtick, yticks=ytick)

    def test_classesInHierarchy(self):
        """Tests the classesInHierarchy utility."""
        # load the test reactor
        _o, r = loadTestReactor(
            inputFileName="smallestTestReactor/armiRunSmallest.yaml"
        )

        # call the `classesInHierarchy` function
        classCounts = defaultdict(lambda: 0)
        utils.classesInHierarchy(r, classCounts, None)

        # validate the `classesInHierarchy` function
        self.assertGreater(len(classCounts), 30)
        self.assertEqual(classCounts[type(r)], 1)
        self.assertEqual(classCounts[type(r.core)], 1)

        # further validate the Reactor hierarchy is in place
        self.assertEqual(len(r.core.getAssemblies()), 1)
        self.assertEqual(len(r.core.getBlocks()), 1)

    def test_codeTiming(self):
        """Test that codeTiming preserves function attributes when it wraps a function."""

        @codeTiming.timed
        def testFunc():
            """Test function docstring."""
            pass

        self.assertEqual(getattr(testFunc, "__doc__"), "Test function docstring.")
        self.assertEqual(getattr(testFunc, "__name__"), "testFunc")

    def test_safeCopy(self):
        with directoryChangers.TemporaryDirectoryChanger():
            os.mkdir("dir1")
            os.mkdir("dir2")
            file1 = "dir1/file1.txt"
            with open(file1, "w") as f:
                f.write("Hello")
            file2 = "dir1\\file2.txt"
            with open(file2, "w") as f:
                f.write("Hello2")

            with mockRunLogs.BufferLog() as mock:
                # Test Linuxy file path
                self.assertEqual("", mock.getStdout())
                safeCopy(file1, "dir2")
                self.assertIn("Copied", mock.getStdout())
                self.assertIn("file1", mock.getStdout())
                self.assertIn("->", mock.getStdout())
                # Clean up for next safeCopy
                mock.emptyStdout()
                # Test Windowsy file path
                self.assertEqual("", mock.getStdout())
                safeCopy(file2, "dir2")
                self.assertIn("Copied", mock.getStdout())
                self.assertIn("file2", mock.getStdout())
                self.assertIn("->", mock.getStdout())
            self.assertTrue(os.path.exists(os.path.join("dir2", "file1.txt")))

    def test_safeMove(self):
        with directoryChangers.TemporaryDirectoryChanger():
            os.mkdir("dir1")
            os.mkdir("dir2")
            file1 = "dir1/file1.txt"
            with open(file1, "w") as f:
                f.write("Hello")
            file2 = "dir1\\file2.txt"
            with open(file2, "w") as f:
                f.write("Hello2")

            with mockRunLogs.BufferLog() as mock:
                # Test Linuxy file path
                self.assertEqual("", mock.getStdout())
                safeMove(file1, "dir2")
                self.assertIn("Moved", mock.getStdout())
                self.assertIn("file1", mock.getStdout())
                self.assertIn("->", mock.getStdout())
                # Clean up for next safeCopy
                mock.emptyStdout()
                # Test Windowsy file path
                self.assertEqual("", mock.getStdout())
                safeMove(file2, "dir2")
                self.assertIn("Moved", mock.getStdout())
                self.assertIn("file2", mock.getStdout())
                self.assertIn("->", mock.getStdout())
            self.assertTrue(os.path.exists(os.path.join("dir2", "file1.txt")))

    def test_safeMoveDir(self):
        with directoryChangers.TemporaryDirectoryChanger():
            os.mkdir("dir1")
            file1 = "dir1/file1.txt"
            with open(file1, "w") as f:
                f.write("Hello")
            file2 = "dir1\\file2.txt"
            with open(file2, "w") as f:
                f.write("Hello2")

            with mockRunLogs.BufferLog() as mock:
                self.assertEqual("", mock.getStdout())
                safeMove("dir1", "dir2")
                self.assertIn("Moved", mock.getStdout())
                self.assertIn("dir1", mock.getStdout())
                self.assertIn("dir2", mock.getStdout())
            self.assertTrue(os.path.exists(os.path.join("dir2", "file1.txt")))


class CyclesSettingsTests(unittest.TestCase):
    """
    Check reading of the various cycle history settings for both the detailed
    and simple input options.
    """

    detailedCyclesSettings = """
metadata:
  version: uncontrolled
settings:
  power: 1000000000.0
  nCycles: 3
  cycles:
    - name: dog
      cumulative days: [1, 2, 3]
      power fractions: [0.1, 0.2, 0.3]
      availability factor: 0.1
    - cycle length: 10
      burn steps: 5
      power fractions: [0.2, 0.2, 0.2, 0.2, 0]
      availability factor: 0.5
    - name: ferret
      step days: [3, R4]
      power fractions: [0.3, R4]
  runType: Standard
"""
    simpleCyclesSettings = """
metadata:
  version: uncontrolled
settings:
  power: 1000000000.0
  nCycles: 3
  availabilityFactors: [0.1, R2]
  cycleLengths: [1, 2, 3]
  powerFractions: [0.1, 0.2, R1]
  burnSteps: 3
  runType: Standard
  """

    powerFractionsDetailedSolution = [
        [0.1, 0.2, 0.3],
        [0.2, 0.2, 0.2, 0.2, 0],
        [0.3, 0.3, 0.3, 0.3, 0.3],
    ]
    powerFractionsSimpleSolution = [[0.1, 0.1, 0.1], [0.2, 0.2, 0.2], [0.2, 0.2, 0.2]]
    cycleNamesDetailedSolution = ["dog", None, "ferret"]
    cycleNamesSimpleSolution = [None, None, None]
    availabilityFactorsDetailedSolution = [0.1, 0.5, 1]
    availabilityFactorsSimpleSolution = [0.1, 0.1, 0.1]
    stepLengthsDetailedSolution = [
        [1, 1, 1],
        [10 / 5 * 0.5, 10 / 5 * 0.5, 10 / 5 * 0.5, 10 / 5 * 0.5, 10 / 5 * 0.5],
        [3, 3, 3, 3, 3],
    ]
    stepLengthsSimpleSolution = [
        [1 * 0.1 / 3, 1 * 0.1 / 3, 1 * 0.1 / 3],
        [2 * 0.1 / 3, 2 * 0.1 / 3, 2 * 0.1 / 3],
        [3 * 0.1 / 3, 3 * 0.1 / 3, 3 * 0.1 / 3],
    ]
    cycleLengthsDetailedSolution = [30, 10, 15]
    cycleLengthsSimpleSolution = [1, 2, 3]
    burnStepsDetailedSolution = [3, 5, 5]
    burnStepsSimpleSolution = [3, 3, 3]
    nodesPerCycleDetailedSolution = [4, 6, 6]
    nodesPerCycleSimpleSolution = [4, 4, 4]
    maxBurnStepsDetailedSolution = 5
    maxBurnStepsSimpleSolution = 3

    def setUp(self):
        self.standaloneDetailedCS = Settings()
        self.standaloneDetailedCS.loadFromString(self.detailedCyclesSettings)

        self.standaloneSimpleCS = Settings()
        self.standaloneSimpleCS.loadFromString(self.simpleCyclesSettings)

    def test_getPowerFractions(self):
        self.assertEqual(
            getPowerFractions(self.standaloneDetailedCS),
            self.powerFractionsDetailedSolution,
        )

        self.assertEqual(
            getPowerFractions(self.standaloneSimpleCS),
            self.powerFractionsSimpleSolution,
        )

    def test_getCycleNames(self):
        self.assertEqual(
            getCycleNames(self.standaloneDetailedCS), self.cycleNamesDetailedSolution
        )

        self.assertEqual(
            getCycleNames(self.standaloneSimpleCS), self.cycleNamesSimpleSolution
        )

    def test_getAvailabilityFactors(self):
        self.assertEqual(
            getAvailabilityFactors(self.standaloneDetailedCS),
            self.availabilityFactorsDetailedSolution,
        )

        self.assertEqual(
            getAvailabilityFactors(self.standaloneSimpleCS),
            self.availabilityFactorsSimpleSolution,
        )

    def test_getStepLengths(self):
        self.assertEqual(
            getStepLengths(self.standaloneDetailedCS),
            self.stepLengthsDetailedSolution,
        )

        self.assertEqual(
            getStepLengths(self.standaloneSimpleCS),
            self.stepLengthsSimpleSolution,
        )

    def test_getCycleLengths(self):
        self.assertEqual(
            getCycleLengths(self.standaloneDetailedCS),
            self.cycleLengthsDetailedSolution,
        )

        self.assertEqual(
            getCycleLengths(self.standaloneSimpleCS), self.cycleLengthsSimpleSolution
        )

    def test_getBurnSteps(self):
        self.assertEqual(
            getBurnSteps(self.standaloneDetailedCS), self.burnStepsDetailedSolution
        )

        self.assertEqual(
            getBurnSteps(self.standaloneSimpleCS), self.burnStepsSimpleSolution
        )

    def test_hasBurnup(self):
        self.assertTrue(hasBurnup(self.standaloneDetailedCS))

    def test_getMaxBurnSteps(self):
        self.assertEqual(
            getMaxBurnSteps(self.standaloneDetailedCS),
            self.maxBurnStepsDetailedSolution,
        )

        self.assertEqual(
            getMaxBurnSteps(self.standaloneSimpleCS), self.maxBurnStepsSimpleSolution
        )

    def test_getNodesPerCycle(self):
        self.assertEqual(
            getNodesPerCycle(self.standaloneDetailedCS),
            self.nodesPerCycleDetailedSolution,
        )

        self.assertEqual(
            getNodesPerCycle(self.standaloneSimpleCS), self.nodesPerCycleSimpleSolution
        )

    def test_getCycleNodeFromCumulativeStep(self):
        self.assertEqual(
            getCycleNodeFromCumulativeStep(8, self.standaloneDetailedCS), (1, 4)
        )
        self.assertEqual(
            getCycleNodeFromCumulativeStep(12, self.standaloneDetailedCS), (2, 3)
        )

        self.assertEqual(
            getCycleNodeFromCumulativeStep(4, self.standaloneSimpleCS), (1, 0)
        )
        self.assertEqual(
            getCycleNodeFromCumulativeStep(8, self.standaloneSimpleCS), (2, 1)
        )

    def test_getCycleNodeFromCumulativeNode(self):
        self.assertEqual(
            getCycleNodeFromCumulativeNode(8, self.standaloneDetailedCS), (1, 4)
        )
        self.assertEqual(
            getCycleNodeFromCumulativeNode(12, self.standaloneDetailedCS), (2, 2)
        )

        self.assertEqual(
            getCycleNodeFromCumulativeNode(3, self.standaloneSimpleCS), (0, 3)
        )
        self.assertEqual(
            getCycleNodeFromCumulativeNode(8, self.standaloneSimpleCS), (2, 0)
        )

        with self.assertRaises(ValueError):
            getCycleNodeFromCumulativeNode(-1, self.standaloneSimpleCS)

    def test_getPreviousTimeNode(self):
        with self.assertRaises(ValueError):
            getPreviousTimeNode(0, 0, "foo")
        self.assertEqual(getPreviousTimeNode(1, 1, self.standaloneSimpleCS), (1, 0))
        self.assertEqual(getPreviousTimeNode(1, 0, self.standaloneSimpleCS), (0, 3))
        self.assertEqual(getPreviousTimeNode(1, 0, self.standaloneDetailedCS), (0, 3))
        self.assertEqual(getPreviousTimeNode(2, 4, self.standaloneDetailedCS), (2, 3))

    def test_getCumulativeNodeNum(self):
        self.assertEqual(getCumulativeNodeNum(2, 0, self.standaloneSimpleCS), 8)
        self.assertEqual(getCumulativeNodeNum(1, 2, self.standaloneSimpleCS), 6)

        self.assertEqual(getCumulativeNodeNum(2, 0, self.standaloneDetailedCS), 10)
        self.assertEqual(getCumulativeNodeNum(1, 0, self.standaloneDetailedCS), 4)
