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

r"""

"""
import unittest
import math

from armi.utils import units
import armi.utils as utils


class Utils_TestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_parabola(self):
        # test the parabola function
        a, b, c = utils.parabolaFromPoints((0, 1), (1, 2), (-1, 2))
        self.assertEqual(a, 1.0)
        self.assertEqual(b, 0.0)
        self.assertEqual(c, 1.0)

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
        #Test with strings
        str1 = utils.capStrLen('sodium', 5)
        self.assertEqual('so...', str1)
        str1 = utils.capStrLen("potassium", 6)
        self.assertEqual('pot...', str1)
        str1 = utils.capStrLen('rubidium', 7)
        self.assertEqual('rubi...', str1)

class TestUnits(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_invalidGroupStructureType(self):
        """Test that the reverse lookup fails on non-existent energy group bounds."""
        modifier = 1e-5
        for groupStructureType in units.GROUP_STRUCTURE.keys():
            energyBounds = units.getGroupStructure(groupStructureType)
            energyBounds[0] = energyBounds[0] * modifier
            with self.assertRaises(ValueError):
                units.getGroupStructureType(energyBounds)

    def test_consistenciesBetweenGroupStructureAndGroupStructureType(self):
        """
        Test that the reverse lookup of the energy group structures work.

        Notes
        -----
        Several group structures point to the same energy group structure so the reverse lookup will fail to
        get the correct group structure type.
        """
        for groupStructureType in units.GROUP_STRUCTURE.keys():
            self.assertEqual(
                groupStructureType,
                units.getGroupStructureType(
                    units.getGroupStructure(groupStructureType)
                ),
            )


if __name__ == "__main__":
    unittest.main()
