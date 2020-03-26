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

r"""Tests locations.py"""
from __future__ import print_function

import unittest
import numpy as np

from armi.reactor.locations import *


class Location_TestCase(unittest.TestCase):
    def setUp(self):
        self.i1 = 0o5
        self.i2 = 0o3
        self.Location = Location(i1=self.i1, i2=self.i2)
        self.Location.setLabel("testLabel")

    def tearDown(self):
        self.Location = None

    def test_duplicate(self):
        self.Location2 = self.Location.duplicate()

        cur = self.Location2.label
        ref = self.Location.label
        self.assertEqual(cur, ref)

        cur = self.Location2.i1
        ref = self.Location.i1
        self.assertAlmostEqual(cur, ref)

        cur = self.Location2.i2
        ref = self.Location.i2
        self.assertAlmostEqual(cur, ref)

    def test_isInCore(self):

        loc = Location()
        self.assertEqual(
            loc.isInCore(), False, msg="Newly instantiated location is in the core"
        )

        loc = Location(2, 4)
        self.assertEqual(
            loc.isInCore(), True, msg="In-core location is not flagged as in-core"
        )

    def test_makeLabel(self):
        loc = Location(5, 3)
        self.assertEqual(str(loc), "A5003")
        loc = Location(11, 5, "B")
        self.assertEqual(str(loc), "B1005B")
        loc = Location(label="TestLabel")
        self.assertEqual(str(loc), "TestLabel")

    def test_axialRange(self):
        for i, char in enumerate(AXIAL_CHARS):
            self.Location.setAxial(char)
            self.assertEqual(self.Location.axial, i)
        with self.assertRaises(ValueError):
            self.Location.setAxial(i + 1)  # pylint: disable=undefined-loop-variable

    def test_isInSameStackAs(self):
        Location2 = Location(i1=self.i1, i2=self.i2)
        Location3 = Location(i1=7, i2=9)

        self.assertTrue(self.Location.isInSameStackAs(Location2))

        self.assertFalse(self.Location.isInSameStackAs(Location3))

    def test_uniqueInt(self):
        cur = self.Location.uniqueInt()
        ref = 100000 * self.i1 + self.i2 * 100 + 0
        self.assertEqual(cur, ref)

    def test_fromUniqueInt(self):
        self.Location.fromUniqueInt(500325)
        cur = self.Location.label
        ref = "A5003Z"
        self.assertEqual(cur, ref)
        for badArgument in [-3, 10 ** 8, 10.0, "10"]:
            self.assertRaises(ValueError, self.Location.fromUniqueInt, badArgument)

    def test_getFirstChar(self):
        self.Location.getFirstChar()
        cur = self.Location.firstChar
        ref = "A5"
        self.assertEqual(cur, ref)

    def test_generateSortedHexLocationList(self):
        grid = grids.HexGrid.fromPitch(1.0)
        locators = grid.generateSortedHexLocationList(7)
        asSet = set(locators)
        self.assertIn((+0, +0, 0), asSet)  # 1
        self.assertIn((-1, +0, 0), asSet)  # 2
        self.assertIn((-1, +1, 0), asSet)  # 3
        self.assertIn((+0, -1, 0), asSet)  # 4
        self.assertIn((+0, +1, 0), asSet)  # 5
        self.assertIn((+1, -1, 0), asSet)  # 6
        self.assertIn((+1, +0, 0), asSet)  # 7
        curList = set(
            grid.getLabel(l.indices[:2]) for l in locators if grid.isInFirstThird(l)
        )
        refList = set(("A1001", "A2001", "A2002"))
        self.assertEqual(refList, curList)

    def test_lessThan(self):
        loc1 = Location(1, 1, "A")
        loc2 = Location(1, 1, "B")
        self.assertTrue(loc1 < loc2)
        self.assertTrue(loc2 > loc1)

        loc1 = Location(2, 5, "C")
        loc2 = Location(7, 1, "A")
        self.assertTrue(loc2 > loc1)

        loc1 = Location(4, 2, "C")
        loc2 = Location(5, 1, "A")
        self.assertTrue(loc2 > loc1)

        loc1 = Location(4, 2, "C")
        loc2 = Location(4, 2, "C")
        self.assertFalse(loc2 > loc1)
        self.assertFalse(loc2 > loc1)


class HexLocation_TestCase(unittest.TestCase):
    def setUp(self):
        self.i1 = 5
        self.i2 = 3
        self.HexLocation = HexLocation(i1=self.i1, i2=self.i2)
        self.HexLocation.setLabel("testLabel")

        # Additional hex locations for use
        self.HexLocation2 = HexLocation(i1=5, i2=23)
        self.HexLocation3 = HexLocation(i1=3, i2=4)

    def tearDown(self):
        self.HexLocation = None
        self.HexLocation2 = None
        self.HexLocation3 = None

    def test_niceLabel(self):
        cur = self.HexLocation.niceLabel()
        ref = "Ring,Pos= {0:3d} {1:3d}".format(
            self.HexLocation.ring, self.HexLocation.pos
        )
        self.assertEqual(cur, ref)

    def test_fromLabel(self):
        self.HexLocation.makeLabel()
        self.HexLocation2.fromLabel(self.HexLocation.label)

        cur = self.HexLocation.i1
        ref = self.HexLocation2.i1
        self.assertEqual(cur, ref)

        cur = self.HexLocation.i2
        ref = self.HexLocation2.i2
        self.assertEqual(cur, ref)

        cur = self.HexLocation.ring
        ref = self.HexLocation2.ring
        self.assertEqual(cur, ref)

        loc = HexLocation(label="C6123Z")
        self.assertEqual(loc.ring, 26, msg="fromLabel did not convert ring properly")
        self.assertEqual(loc.i1, 26, msg="fromLabel did not convert i1 properly")
        self.assertEqual(loc.i2, 123, msg="fromLabel did not convert i2 properly")
        self.assertEqual(loc.pos, 123, msg="fromLabel did not convert pos properly")
        self.assertEqual(loc.axial, 25)

    def test_coords(self):
        cur = self.HexLocation.coords(p=8.15)
        ref = (14.116214081686351, 24.450000000000003)
        places = 6
        np.testing.assert_almost_equal(cur, ref, decimal=places)

        cur = self.HexLocation2.coords(p=2.5)
        ref = (8.660254037844387, 0.0)
        places = 6
        np.testing.assert_almost_equal(cur, ref, decimal=places)

        cur = self.HexLocation3.coords(p=3.14)
        ref = (-2.7193197678831376, 4.71)
        places = 6
        np.testing.assert_almost_equal(cur, ref, decimal=places)

    def test_getAngle(self):
        self.assertAlmostEqual(HexLocation(4, 1).getAngle(degrees=True), 30.0)
        self.assertAlmostEqual(HexLocation(3, 3).getAngle(degrees=True), 90.0)
        self.assertAlmostEqual(HexLocation(3, 12).getAngle(degrees=True), 0.0)
        self.assertAlmostEqual(HexLocation(3, 4).getAngle(degrees=True), 120.0)
        self.assertAlmostEqual(HexLocation(2, 6).getAngle(degrees=True), 330.0)
        self.assertAlmostEqual(HexLocation(1, 1).getAngle(degrees=True), 0.0)

    def test_indices(self):
        cur = self.HexLocation.indices()
        ref = (2, 2)
        self.assertEqual(cur, ref)

        cur = self.HexLocation2.indices()
        ref = (4, -2)
        self.assertEqual(cur, ref)

        cur = self.HexLocation3.indices()
        ref = (-1, 2)
        self.assertEqual(cur, ref)

    def test_getSymmetricIdenticalsThird(self):
        curList = self.HexLocation.getSymmetricIdenticalsThird()
        refList = ["A5011", "A5019"]
        for cur, ref in zip(curList, refList):
            cur = str(cur)
            self.assertEqual(cur, ref)

        curList = self.HexLocation2.getSymmetricIdenticalsThird()
        refList = ["A5007", "A5015"]
        for cur, ref in zip(curList, refList):
            cur = str(cur)
            self.assertEqual(cur, ref)

        curList = self.HexLocation3.getSymmetricIdenticalsThird()
        refList = ["A3008", "A3012"]
        for cur, ref in zip(curList, refList):
            cur = str(cur)
            self.assertEqual(cur, ref)

    def test_getSymmetricIdenticalsSixth(self):
        curList = self.HexLocation.getSymmetricIdenticalsSixth()
        refList = ["A5007", "A5011", "A5015", "A5019", "A5023"]
        for cur, ref in zip(curList, refList):
            cur = str(cur)
            self.assertEqual(cur, ref)

        curList = self.HexLocation2.getSymmetricIdenticalsSixth()
        refList = ["A5003", "A5007", "A5011", "A5015", "A5019"]
        for cur, ref in zip(curList, refList):
            cur = str(cur)
            self.assertEqual(cur, ref)

        curList = self.HexLocation3.getSymmetricIdenticalsSixth()
        refList = ["A3006", "A3008", "A3010", "A3012", "A3002"]
        for cur, ref in zip(curList, refList):
            cur = str(cur)
            self.assertEqual(cur, ref)

    def test_allPositionsInThird(self):
        grid = grids.HexGrid.fromPitch(1.0)
        curList = grid.allPositionsInThird(5)
        refList = [1, 2, 3, 4, 5, 6, 23, 24]
        self.assertEqual(refList, curList)

        curList = grid.allPositionsInThird(5)
        refList = [1, 2, 3, 4, 5, 6, 23, 24]
        self.assertEqual(refList, curList)

        curList = grid.allPositionsInThird(3)
        refList = [1, 2, 3, 12]
        self.assertEqual(refList, curList)

        curList = grid.allPositionsInThird(3, includeEdgeAssems=True)
        refList = [1, 2, 3, 4, 12]
        self.assertEqual(refList, curList)

    def test_getNumPositions(self):
        cur = self.HexLocation.getNumPositions()
        ref = 61
        self.assertEqual(cur, ref)

        cur = self.HexLocation2.getNumPositions()
        ref = 61
        self.assertEqual(cur, ref)

        cur = self.HexLocation3.getNumPositions()
        ref = 19
        self.assertEqual(cur, ref)

    def test_getNumPosInRing(self):
        cur = self.HexLocation.getNumPositions()
        ref = 61
        self.assertEqual(cur, ref)

        cur = self.HexLocation2.getNumPositions()
        ref = 61
        self.assertEqual(cur, ref)

        cur = self.HexLocation3.getNumPositions()
        ref = 19
        self.assertEqual(cur, ref)

        # cur = self.HexLocation.getNumPosInRing(ring=None)
        # ref =
        # places =
        # self.assertAlmostEqual(cur, ref, places=places)

    def test_getNumRings(self):
        cur = self.HexLocation.getNumRings(721)
        ref = 16
        self.assertEqual(cur, ref)

        cur = self.HexLocation.getNumRings(127)
        ref = 7
        self.assertEqual(cur, ref)

        cur = self.HexLocation.getNumRings(26791)
        ref = 95
        self.assertEqual(cur, ref)

        self.assertEqual(self.HexLocation.getNumRings(1), 1)
        self.assertEqual(self.HexLocation.getNumRings(0), 0)

    def test_getNumPinsInLine(self):
        cur = self.HexLocation.getNumPinsInLine()
        ref = 9
        self.assertEqual(cur, ref)

        cur = self.HexLocation2.getNumPinsInLine()
        ref = 9
        self.assertEqual(cur, ref)

        cur = self.HexLocation3.getNumPinsInLine()
        ref = 5
        self.assertEqual(cur, ref)

    def test_containsWhichFDMeshPointsThird(self):
        cur = self.HexLocation.containsWhichFDMeshPoints(resolution=1)
        ref = [(12, 7), (13, 7), (14, 7), (11, 6), (12, 6), (13, 6)]
        self.assertEqual(cur, ref)

        cur = self.HexLocation2.containsWhichFDMeshPoints(resolution=2)
        ref = [
            (24, 2),
            (25, 2),
            (26, 2),
            (27, 2),
            (28, 2),
            (22, 1),
            (23, 1),
            (24, 1),
            (25, 1),
            (26, 1),
            (27, 1),
            (28, 1),
        ]
        self.assertEqual(cur, ref)

        cur = self.HexLocation3.containsWhichFDMeshPoints(resolution=2)
        ref = [
            (1, 8),
            (2, 8),
            (3, 8),
            (4, 8),
            (1, 7),
            (2, 7),
            (3, 7),
            (4, 7),
            (1, 6),
            (2, 6),
            (3, 6),
            (1, 5),
        ]
        self.assertEqual(cur, ref)

        cur = HexLocation(4, 5).containsWhichFDMeshPoints(resolution=1)
        self.assertEqual(cur, [(2, 6), (3, 6), (4, 6), (1, 5), (2, 5), (3, 5)])

        cur = HexLocation(3, 12).containsWhichFDMeshPoints(resolution=1)
        self.assertEqual(cur, [(6, 1), (7, 1), (8, 1)])

        cur = HexLocation(3, 4).containsWhichFDMeshPoints(resolution=1)
        self.assertEqual(cur, [(1, 4), (2, 4), (1, 3)])

        loc = HexLocation(1, 1)
        cur = loc.containsWhichFDMeshPoints()
        self.assertEqual(len(cur), 2)

    def test_containsWhichFDMeshPointsFull(self):
        loc = HexLocation(1, 1)
        cur = loc.containsWhichFDMeshPoints(fullCore=True)
        self.assertEqual(cur, [(0, 1), (1, 1), (2, 1), (-1, 0), (0, 0), (1, 0)])

        # make sure there are no overlaps over a set of assemblies.
        allPoints = []
        for (ring, pos) in [(2, 3), (2, 4), (2, 5), (2, 6), (1, 1), (2, 1)]:
            loc = HexLocation(ring, pos)
            points = loc.containsWhichFDMeshPoints(fullCore=True)
            for point in points:
                self.assertNotIn(point, allPoints)
            allPoints.extend(points)

    def test_containsWhichFDMeshPointsRectangular(self):
        loc = HexLocation(1, 1)
        vals = loc.containsWhichFDMeshPoints(rectangular=True, fullCore=True)
        ref = [(1, 1), (2, 1), (3, 1), (1, 0), (2, 0), (3, 0)]
        self.assertEqual(vals, ref)

        # try double resolution
        vals = loc.containsWhichFDMeshPoints(
            resolution=2, rectangular=True, fullCore=True
        )
        ref = [
            (0, 2),
            (1, 2),
            (2, 2),
            (3, 2),
            (4, 2),
            (-1, 1),
            (0, 1),
            (1, 1),
            (2, 1),
            (3, 1),
            (4, 1),
            (5, 1),
            (-1, 0),
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 0),
            (4, 0),
            (5, 0),
            (0, -1),
            (1, -1),
            (2, -1),
            (3, -1),
            (4, -1),
        ]
        self.assertEqual(vals, ref)

    def test_getTopCenterIndices(self):

        # parallelogram domain
        locs = [(1, 1), (2, 1), (2, 2), (2, 6)]
        centerIndices = [(1, 1), (5, 2), (3, 3), (3, 0)]
        for locI, centerI in zip(locs, centerIndices):
            loc = HexLocation(*locI)
            i, j = loc._getTopCenterIndices(1, False)
            self.assertEqual(i, centerI[0])
            self.assertEqual(j, centerI[1])

        # rectangular domain
        locs = [(1, 1), (2, 1), (2, 2), (2, 6)]
        centerIndices = [(2, 1), (5, 2), (2, 3), (5, 0)]
        for locI, centerI in zip(locs, centerIndices):
            loc = HexLocation(*locI)
            i, j = loc._getTopCenterIndices(1, True)
            self.assertEqual(i, centerI[0])
            self.assertEqual(j, centerI[1])

        # assembly with double-resolution.
        locs = [(1, 1), (2, 1), (2, 2), (2, 6)]
        centerIndices = [(1, 1), (9, 3), (5, 5), (5, -1)]
        for locI, centerI in zip(locs, centerIndices):
            loc = HexLocation(*locI)
            i, j = loc._getTopCenterIndices(2, False)
            self.assertEqual(i, centerI[0])
            self.assertEqual(j, centerI[1])

        # double-resolution with rectangular domain
        locs = [(1, 1), (2, 1), (2, 2), (2, 6)]
        centerIndices = [(2, 1), (8, 3), (2, 5), (8, -1)]
        for locI, centerI in zip(locs, centerIndices):
            loc = HexLocation(*locI)
            i, j = loc._getTopCenterIndices(2, True)
            self.assertEqual(i, centerI[0])
            self.assertEqual(j, centerI[1])


class CartesianLocation_TestCase(unittest.TestCase):
    def setUp(self):
        self.CartesianLocation = CartesianLocation(i1=5, i2=3)
        self.CartesianLocation2 = CartesianLocation(i1=5, i2=23)
        self.CartesianLocation3 = CartesianLocation(i1=3, i2=4)

    def tearDown(self):
        self.CartesianLocation = None
        self.CartesianLocation2 = None
        self.CartesianLocation3 = None

    def test_coords(self):
        cur = self.CartesianLocation.coords((1, 1))
        ref = (5.5, 3.5)
        self.assertEqual(cur, ref)

    def test_getNumPosInRing(self):
        cur = self.CartesianLocation.getNumPosInRing(ring=None)
        ref = 32
        self.assertEqual(cur, ref)

        cur = self.CartesianLocation2.getNumPosInRing(ring=None)
        ref = 32
        self.assertEqual(cur, ref)

        cur = self.CartesianLocation3.getNumPosInRing(ring=None)
        ref = 16
        self.assertEqual(cur, ref)

    def test_makeLabel(self):
        loc = CartesianLocation(i1=0, i2=1)
        self.assertEqual(loc.label, "A0001")

    def test_uniqueInt(self):
        # Cartesian cases need to function when the origin is at 0 in the i1 dimension
        loc = CartesianLocation(i1=0, i2=1)
        uniqInt = loc.uniqueInt()
        ref = 100  # 100000*(loc.i1)+loc.i2*100+0 (axial)
        self.assertEqual(uniqInt, ref)

        loc = CartesianLocation()
        loc.fromUniqueInt(uniqInt)
        self.assertEqual(loc.i1, 0)
        self.assertEqual(loc.i2, 1)

    def test_fromUniqueInt(self):
        loc = CartesianLocation()
        loc.fromUniqueInt(0)
        cur = loc.label
        ref = "A0000A"
        self.assertEqual(cur, ref)

    def test_getNumPositions(self):
        numRingsToExpectedNumPositions = {0: 0, 1: 1, 2: 9, 3: 25, 4: 49}
        for numRings, expectedNumPositions in numRingsToExpectedNumPositions.items():
            self.assertEqual(
                expectedNumPositions, self.CartesianLocation.getNumPositions(numRings)
            )

    def test_getNumRings(self):
        numPositionsToExpectedNumRings = {
            0: 0,
            1: 1,
            2: 2,
            9: 2,
            11: 3,
            25: 3,
            28: 4,
            49: 4,
        }
        for numPositions, expectedNumRings in numPositionsToExpectedNumRings.items():
            self.assertEqual(
                expectedNumRings, self.CartesianLocation.getNumRings(numPositions)
            )


class ThRZLocation_TestCase(unittest.TestCase):
    def setUp(self):

        self.m = Mesh()
        for radius in [112.6208, 175.6608, 202.68]:
            self.m.appendUpper(label="R", p=radius)
        self.m.addRegDirectionFromMax(L=(2.0 * math.pi), N=3, label="Th")
        self.m.appendUpper(label="Z", p=12.0)

        self.location = ThetaRZLocation(i1=1, i2=2, ThRZmesh=self.m)

    def tearDown(self):
        self.location = None

    def test_coords(self):
        pass

    def test_getAreaVolume(self):
        self.assertAlmostEqual(
            self.location.getVolume(axial=1),
            math.pi * (175.6608 ** 2 - 112.6208 ** 2) / 3.0 * 12.0,
            places=7,
        )
        runLog.info(
            'Warning message for height of "None" expected. Ignore these warning messages'
        )
        self.assertEqual(self.location.getVolume(), None)
        self.assertAlmostEqual(
            self.location.getZArea(),
            math.pi * (175.6608 ** 2 - 112.6208 ** 2) / 3.0,
            places=7,
        )
        self.assertAlmostEqual(
            self.location.getInnerRArea(refHeight=12.0),
            (2.0 * math.pi * (112.6208) / 3.0 * 12.0),
            places=7,
        )
        self.assertAlmostEqual(
            self.location.getOuterRArea(refHeight=12.0),
            (2.0 * math.pi * (175.6608) / 3.0 * 12.0),
            places=7,
        )

        self.m.i["Z"][1] = 10
        self.m.setDiInternal()
        self.assertAlmostEqual(
            self.location.getVolume(axial=1),
            math.pi * (175.6608 ** 2 - 112.6208 ** 2) / 3.0 * 10.0,
            places=7,
        )

        del self.location.ThRZmesh.di["Z"]
        del self.location.ThRZmesh.i["Z"]
        self.assertEqual(self.location.getVolume(axial=1), None)

    def test_ThRZcoords(self):

        m = Mesh()
        i = {
            "Z": [
                0,
                40.0,
                80.0,
                90.38000000000001,
                126.38000000000002,
                162.38000000000002,
                190.38,
                198.38000000000002,
                234.38,
                270.38,
                290.38,
                294.38,
                318.38,
                342.38,
                366.38,
                390.38,
                400.76,
                440.76,
                480.76,
            ],
            "R": [
                0,
                30.0,
                60.0,
                90.0,
                120.0,
                150.0,
                176.66666666666666,
                203.33333333333331,
                229.99999999999997,
                245.824,
                261.648,
                277.47200000000004,
                293.29600000000005,
                309.99999999999994,
                311.62,
            ],
            "Th": [0, 6.283185307179586],
        }

        for label, positions in i.items():
            for p in positions:
                m.appendUpper(label, p)

        loc = ThetaRZLocation(i1=1, i2=1, axial="D", ThRZmesh=m)
        th, r, z = loc.ThRZcoords()

        self.assertAlmostEqual(z, (80.0 + 90.38000000000001) / 2.0, 14)


class Mesh_TestCase(unittest.TestCase):
    def setUp(self):
        self.ReactorMesh = Mesh()
        for radius in [112.6208, 175.6608, 202.68]:
            self.ReactorMesh.appendUpper(label="R", p=radius)
        self.ReactorMesh.addRegDirectionFromMax(L=(2.0 * math.pi), N=3, label="Th")

    def tearDown(self):
        self.ReactorMesh = None

    def test_MeshInitilization(self):
        r"""This test verifies the mesh object is created successfully"""
        self.assertEqual(
            self.ReactorMesh.getPositions("R"), [0, 112.6208, 175.6608, 202.68]
        )
        self.assertEqual(
            self.ReactorMesh.getPositions("Th"),
            [0, 2.0 / 3.0 * math.pi, 4.0 / 3.0 * math.pi, 2.0 * math.pi],
        )

    def test_appendFromBounds(self):
        subMesh = Mesh()
        subMesh.appendFromBounds(label="R", p1=175.6608, p2=202.68, n=1)

        self.assertEqual(len(subMesh.getPositions("R")), 3)
        subMesh.appendFromBounds(label="r", p1=0, p2=110.0, n=3)
        self.assertEqual(len(subMesh.getPositions("r")), 4)

    def test_GetClosest(self):
        subMesh = Mesh()
        subMesh.addFromPositions(
            positions=[
                0.0,
                22.9633333333,
                42.1166666667,
                62.54,
                85.379582193,
                100.379582193,
                120.379582193,
                140.379582193,
                160.379582193,
                180.379582193,
                200.379582193,
                220.379582193,
                240.379582193,
                260.379582193,
                275.379582193,
                298.2191643861,
                308.2191643861,
                328.6424977194,
                347.7958310527,
                370.7591643861,
            ],
            labels="Z",
        )
        self.assertEqual(
            subMesh.getClosestUpperFromPosition(p=308.219164386, label="Z"), 16
        )
        self.assertEqual(
            subMesh.getClosestUpperFromPosition(p=370.7591643861, label="Z"), 19
        )

    def test_appendFromUpper(self):
        subMesh = Mesh()
        # subMesh.i = {'Z':[0, 355.68]}
        subMesh.addFromPositions(positions=[0, 355.68], labels="Z")
        subMesh.appendUpper(label="Z", p=177.84)
        self.assertEqual(subMesh.i["Z"][0], 0)
        self.assertEqual(subMesh.i["Z"][1], 177.84)
        self.assertEqual(subMesh.i["Z"][2], 355.68)


if __name__ == "__main__":
    #     import sys;sys.argv=['','CartesianLocation_TestCase']
    unittest.main()
