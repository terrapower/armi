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
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import unittest
import math

import numpy as np

from armi.utils import units
from armi.utils import directoryChangers
import armi.utils as utils


class Utils_TestCase(unittest.TestCase):
    def test_parabola(self):
        # test the parabola function
        a, b, c = utils.parabolaFromPoints((0, 1), (1, 2), (-1, 2))
        self.assertEqual(a, 1.0)
        self.assertEqual(b, 0.0)
        self.assertEqual(c, 1.0)

        with self.assertRaises(Exception):
            a, b, c = utils.parabolaFromPoints((0, 1), (0, 1), (-1, 2))

    def test_findClosest(self):
        l1 = range(10)
        self.assertEqual(utils.findClosest(l1, 5.6), 6)
        self.assertEqual(utils.findClosest(l1, 10.1), 9)
        self.assertEqual(utils.findClosest(l1, -200), 0)

        # with index
        self.assertEqual(utils.findClosest(l1, 5.6, indx=True), (6, 6))

    def test_linearInterpolation(self):
        y = utils.linearInterpolation(1.0, 2.0, 3.0, 4.0, targetX=20.0)
        x = utils.linearInterpolation(1.0, 2.0, 3.0, 4.0, targetY=y)

        x2 = utils.linearInterpolation(1.0, 1.0, 2.0, 2.0, targetY=50)

        self.assertEqual(x, 20.0)
        self.assertEqual(x2, 50.0)

        with self.assertRaises(ZeroDivisionError):
            _ = utils.linearInterpolation(1.0, 1.0, 1.0, 2.0)

    def test_parabolicInterpolation(self):
        realRoots = utils.parabolicInterpolation(2.0e-6, -5.0e-4, 1.02, 1.0)
        self.assertAlmostEqual(realRoots[0][0], 200.0)
        self.assertAlmostEqual(realRoots[0][1], 3.0e-4)
        self.assertAlmostEqual(realRoots[1][0], 50.0)
        self.assertAlmostEqual(realRoots[1][1], -3.0e-4)
        noRoots = utils.parabolicInterpolation(2.0e-6, -4.0e-4, 1.03, 1.0)
        self.assertAlmostEqual(noRoots[0][0], -100.0)
        self.assertAlmostEqual(noRoots[0][1], 0.0)
        # 3. run time error
        with self.assertRaises(RuntimeError):
            _ = utils.parabolicInterpolation(2.0e-6, 4.0e-4, 1.02, 1.0)

    def test_rotateXY(self):
        x = [1.0, -1.0]
        y = [1.0, 1.0]

        # test operation on scalar
        xr, yr = utils.rotateXY(x[0], y[0], 45.0)
        self.assertAlmostEqual(xr, 0.0)
        self.assertAlmostEqual(yr, math.sqrt(2))

        xr, yr = utils.rotateXY(x[1], y[1], 45.0)
        self.assertAlmostEqual(xr, -math.sqrt(2))
        self.assertAlmostEqual(yr, 0.0)

        # test operation on list
        xr, yr = utils.rotateXY(x, y, 45.0)
        self.assertAlmostEqual(xr[0], 0.0)
        self.assertAlmostEqual(yr[0], math.sqrt(2))
        self.assertAlmostEqual(xr[1], -math.sqrt(2))
        self.assertAlmostEqual(yr[1], 0.0)

    def test_findNearestValue(self):
        searchList = [0.1, 0.2, 0.25, 0.35, 0.4]
        searchValue = 0.225
        self.assertEqual(utils.findNearestValue(searchList, searchValue), 0.2)
        searchValue = 0.226
        self.assertEqual(utils.findNearestValue(searchList, searchValue), 0.25)
        searchValue = 0.0
        self.assertEqual(utils.findNearestValue(searchList, searchValue), 0.1)
        searchValue = 10
        self.assertEqual(utils.findNearestValue(searchList, searchValue), 0.4)

    def test_expandRepeatedFloats(self):
        repeatedFloats = ["150", "2R", 200.0, 175, "4r", 180.0, "0R"]
        expectedFloats = [150] * 3 + [200] + [175] * 5 + [180]
        self.assertEqual(utils.expandRepeatedFloats(repeatedFloats), expectedFloats)

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

    def test_fixThreeDigitExp(self):
        fixed = utils.fixThreeDigitExp("-9.03231714805651E+101")
        self.assertEqual(-9.03231714805651e101, fixed)
        fixed = utils.fixThreeDigitExp("9.03231714805651-101")
        self.assertEqual(9.03231714805651e-101, fixed)
        fixed = utils.fixThreeDigitExp("-2.4594981981654+101")
        self.assertEqual(-2.4594981981654e101, fixed)
        fixed = utils.fixThreeDigitExp("-2.4594981981654-101")
        self.assertEqual(-2.4594981981654e-101, fixed)

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

    def test_getFloat(self):
        self.assertEqual(utils.getFloat(1.0), 1.0)
        self.assertEqual(utils.getFloat("1.0"), 1.0)
        self.assertIsNone(utils.getFloat("word"))

    def test_relErr(self):
        self.assertAlmostEqual(utils.relErr(1.00, 1.01), 0.01)
        self.assertAlmostEqual(utils.relErr(100.0, 97.0), -0.03)
        self.assertAlmostEqual(utils.relErr(0.00, 1.00), -1e99)

    def test_efmt(self):
        self.assertAlmostEqual(utils.efmt("1.0e+001"), "1.0E+01")
        self.assertAlmostEqual(utils.efmt("1.0E+01"), "1.0E+01")

    def test_slantSplit(self):
        x1 = utils.slantSplit(10.0, 4.0, 4)
        x2 = utils.slantSplit(10.0, 4.0, 4, order="high first")
        self.assertListEqual(x1, [1.0, 2.0, 3.0, 4.0])
        self.assertListEqual(x2, [4.0, 3.0, 2.0, 1.0])

    def test_newtonsMethod(self):
        f = lambda x: (x + 2) * (x - 1)
        root = utils.newtonsMethod(f, 0.0, 5.0, maxIterations=10, positiveGuesses=True)
        self.assertAlmostEqual(root, 1.0, places=3)
        root = utils.newtonsMethod(f, 0.0, -10.0, maxIterations=10)
        self.assertAlmostEqual(root, -2.0, places=3)

    def test_minimizeScalarFunc(self):
        f = lambda x: (x + 1) ** 2
        minimum = utils.minimizeScalarFunc(f, -3.0, 10.0, maxIterations=10)
        self.assertAlmostEqual(minimum, -1.0, places=3)
        minimum = utils.minimizeScalarFunc(
            f, -3.0, 10.0, maxIterations=10, positiveGuesses=True
        )
        self.assertAlmostEqual(minimum, 0.0, places=3)

    def test_prependToList(self):
        a = ["hello", "world"]
        b = [1, 2, 3]
        utils.prependToList(a, b)
        self.assertListEqual(a, [1, 2, 3, "hello", "world"])

    def test_convertToSlice(self):
        slice1 = utils.convertToSlice(2)
        self.assertEqual(slice1, slice(2, 3, None))
        slice1 = utils.convertToSlice(2.0, increment=-1)
        self.assertEqual(slice1, slice(1, 2, None))
        slice1 = utils.convertToSlice(None)
        self.assertEqual(slice1, slice(None, None, None))
        slice1 = utils.convertToSlice([1, 2, 3])
        self.assertTrue(np.allclose(slice1, np.array([1, 2, 3])))
        slice1 = utils.convertToSlice(slice(2, 3, None))
        self.assertEqual(slice1, slice(2, 3, None))
        slice1 = utils.convertToSlice(np.array([1, 2, 3]))
        self.assertTrue(np.allclose(slice1, np.array([1, 2, 3])))
        with self.assertRaises(Exception):
            slice1 = utils.convertToSlice("slice")

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

    def test_getStepsFromValues(self):
        steps = utils.getStepsFromValues([1.0, 3.0, 6.0, 10.0], prevValue=0.0)
        self.assertListEqual(steps, [1.0, 2.0, 3.0, 4.0])


if __name__ == "__main__":
    unittest.main()
