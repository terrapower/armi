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

r""" Testing some utility functions
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access,too-many-public-methods,invalid-name
from collections import defaultdict
import unittest

import numpy as np

from armi import utils
from armi.reactor.tests.test_reactors import loadTestReactor
from armi.settings.caseSettings import Settings
from armi.utils import (
    directoryChangers,
    getPowerFractions,
    getCycleNames,
    getAvailabilityFactors,
    getStepLengths,
    getCycleLengths,
    getBurnSteps,
    getMaxBurnSteps,
    getNodesPerCycle,
    getCycleNodeFromCumulativeStep,
    getCycleNodeFromCumulativeNode,
    getPreviousTimeNode,
    getCumulativeNodeNum,
    hasBurnup,
)


class TestGeneralUtils(unittest.TestCase):
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
            utils.plotMatrix(matrix, fname, show=True, title="plot")
            utils.plotMatrix(matrix, fname, minV=0, maxV=5, figsize=[3, 4])
            utils.plotMatrix(matrix, fname, xticks=xtick, yticks=ytick)

    def test_classesInHierarchy(self):
        """Tests the classesInHierarchy utility

        .. test:: Tests that the Reactor is stored heirarchically
           :id: TEST_REACTOR_HIERARCHY_0
           :links: REQ_REACTOR_HIERARCHY

           This test shows that the Blocks and Assemblies are stored
           heirarchically inside the Core, which is inside the Reactor object.
        """
        # load the test reactor
        _o, r = loadTestReactor()

        # call the `classesInHierarchy` function
        classCounts = defaultdict(lambda: 0)
        utils.classesInHierarchy(r, classCounts, None)

        # validate the `classesInHierarchy` function
        self.assertGreater(len(classCounts), 30)
        self.assertEqual(classCounts[type(r)], 1)
        self.assertEqual(classCounts[type(r.core)], 1)

        # further validate the Reactor heirarchy is in place
        self.assertGreater(len(r.core.getAssemblies()), 50)
        self.assertGreater(len(r.core.getBlocks()), 200)


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


if __name__ == "__main__":
    unittest.main()
