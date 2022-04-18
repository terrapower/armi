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
import math
import unittest

import numpy as np

from armi import utils
from armi.reactor.tests.test_reactors import loadTestReactor
from armi.utils import directoryChangers


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
        o, r = loadTestReactor()

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


if __name__ == "__main__":
    unittest.main()
