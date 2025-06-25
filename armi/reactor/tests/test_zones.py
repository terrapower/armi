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

"""Test for Zones."""

import logging
import os
import unittest

from armi import runLog
from armi.reactor import (
    assemblies,
    blocks,
    blueprints,
    geometry,
    grids,
    reactors,
    zones,
)
from armi.reactor.tests import test_reactors
from armi.tests import mockRunLogs

THIS_DIR = os.path.dirname(__file__)


class TestZone(unittest.TestCase):
    def setUp(self):
        # set up a Reactor, for the spatialLocator
        bp = blueprints.Blueprints()
        r = reactors.Reactor("zonetest", bp)
        r.add(reactors.Core("Core"))
        r.core.spatialGrid = grids.HexGrid.fromPitch(1.0)
        r.core.spatialGrid._bounds = (
            [0, 1, 2, 3, 4],
            [0, 10, 20, 30, 40],
            [0, 20, 40, 60, 80],
        )
        r.core.spatialGrid.symmetry = geometry.SymmetryType(
            geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC
        )
        r.core.spatialGrid.geomType = geometry.HEX

        # some testing constants
        self.numAssems = 5
        self.numBlocks = 5

        # build a list of Assemblies
        self.aList = []
        for ring in range(self.numAssems):
            a = assemblies.HexAssembly("fuel")
            a.spatialGrid = r.core.spatialGrid
            a.spatialLocator = r.core.spatialGrid[ring, 1, 0]
            a.parent = r.core
            self.aList.append(a)

        # build a list of Blocks
        self.bList = []
        for _ in range(self.numBlocks):
            b = blocks.HexBlock("TestHexBlock")
            b.setType("defaultType")
            b.p.nPins = 3
            b.setHeight(3.0)
            self.aList[0].add(b)
            self.bList.append(b)

    def test_addItem(self):
        """
        Test adding an item.

        .. test:: Add item to a zone.
            :id: T_ARMI_ZONE0
            :tests: R_ARMI_ZONE
        """
        zone = zones.Zone("test_addItem")
        zone.addItem(self.aList[0])
        self.assertIn(self.aList[0].getLocation(), zone)

        self.assertRaises(AssertionError, zone.addItem, "nope")

    def test_removeItem(self):
        zone = zones.Zone("test_removeItem", [a.getLocation() for a in self.aList])
        zone.removeItem(self.aList[0])
        self.assertNotIn(self.aList[0].getLocation(), zone)

        self.assertRaises(AssertionError, zone.removeItem, "also nope")

    def test_addItems(self):
        """
        Test adding items.

        .. test:: Add multiple items to a zone.
            :id: T_ARMI_ZONE1
            :tests: R_ARMI_ZONE
        """
        zone = zones.Zone("test_addItems")
        zone.addItems(self.aList)
        for a in self.aList:
            self.assertIn(a.getLocation(), zone)

    def test_removeItems(self):
        zone = zones.Zone("test_removeItems", [a.getLocation() for a in self.aList])
        zone.removeItems(self.aList)
        for a in self.aList:
            self.assertNotIn(a.getLocation(), zone)

    def test_addLoc(self):
        """
        Test adding a location.

        .. test:: Add location to a zone.
            :id: T_ARMI_ZONE2
            :tests: R_ARMI_ZONE
        """
        zone = zones.Zone("test_addLoc")
        zone.addLoc(self.aList[0].getLocation())
        self.assertIn(self.aList[0].getLocation(), zone)

        self.assertRaises(AssertionError, zone.addLoc, 1234)

    def test_removeLoc(self):
        zone = zones.Zone("test_removeLoc", [a.getLocation() for a in self.aList])
        zone.removeLoc(self.aList[0].getLocation())
        self.assertNotIn(self.aList[0].getLocation(), zone)

        self.assertRaises(AssertionError, zone.removeLoc, 1234)

    def test_addLocs(self):
        """
        Test adding locations.

        .. test:: Add multiple locations to a zone.
            :id: T_ARMI_ZONE3
            :tests: R_ARMI_ZONE
        """
        zone = zones.Zone("test_addLocs")
        zone.addLocs([a.getLocation() for a in self.aList])
        for a in self.aList:
            self.assertIn(a.getLocation(), zone)

    def test_removeLocs(self):
        zone = zones.Zone("test_removeLocs", [a.getLocation() for a in self.aList])
        zone.removeLocs([a.getLocation() for a in self.aList])
        for a in self.aList:
            self.assertNotIn(a.getLocation(), zone)

    def test_iteration(self):
        locs = [a.getLocation() for a in self.aList]
        zone = zones.Zone("test_iteration")

        # BONUS TEST: Zone.__len__()
        self.assertEqual(len(zone), 0)
        zone.addLocs(locs)
        self.assertEqual(len(zone), self.numAssems)

        # loop once to prove looping works
        for aLoc in zone:
            self.assertIn(aLoc, locs)
            self.assertTrue(aLoc in zone)  # Tests Zone.__contains__()

        # loop twice to make sure it iterates nicely.
        for aLoc in zone:
            self.assertIn(aLoc, locs)
            self.assertTrue(aLoc in zone)  # Tests Zone.__contains__()

    def test_repr(self):
        zone = zones.Zone("test_repr")
        zone.addItems(self.aList)
        zStr = "Zone test_repr with 5 Assemblies"
        self.assertIn(zStr, str(zone))

    def test_blocks(self):
        zone = zones.Zone("test_blocks", zoneType=blocks.Block)

        # test the blocks were correctly added
        self.assertEqual(len(zone), 0)
        zone.addItems(self.bList)
        self.assertEqual(len(zone), self.numBlocks)

        # loop once to prove looping works
        for aLoc in zone:
            self.assertIn(aLoc, zone.locs)
            self.assertTrue(aLoc in zone)  # test Zone.__contains__()


class TestZones(unittest.TestCase):
    def setUp(self):
        # spin up the test reactor
        self.o, self.r = test_reactors.loadTestReactor()

        # build some generic test zones to get started with
        newSettings = {}
        newSettings["zoneDefinitions"] = [
            "ring-1: 001-001",
            "ring-2: 002-001, 002-002",
            "ring-3: 003-001, 003-002, 003-003",
        ]
        cs = self.o.cs.modified(newSettings=newSettings)
        self.r.core.buildManualZones(cs)
        self.zonez = self.r.core.zones

    def test_dictionaryInterface(self):
        """
        Test creating and interacting with the Zones object.

        .. test:: Create collection of Zones.
            :id: T_ARMI_ZONE4
            :tests: R_ARMI_ZONE
        """
        zs = zones.Zones()

        # validate the addZone() and __len__() work
        self.assertEqual(len(zs.names), 0)
        zs.addZone(self.zonez["ring-2"])
        self.assertEqual(len(zs.names), 1)

        # validate that __contains__() works
        self.assertFalse("ring-1" in zs)
        self.assertTrue("ring-2" in zs)
        self.assertFalse("ring-3" in zs)

        # validate that __remove__() works
        del zs["ring-2"]
        self.assertEqual(len(zs.names), 0)

        # validate that addZones() works
        zs.addZones(self.zonez)
        self.assertEqual(len(zs.names), 3)
        self.assertTrue("ring-1" in zs)
        self.assertTrue("ring-2" in zs)
        self.assertTrue("ring-3" in zs)

        # validate that get() works
        ring3 = zs["ring-3"]
        self.assertEqual(len(ring3), 3)
        self.assertIn("003-002", ring3)

        # validate that removeZones() works
        zonesToRemove = [z.name for z in self.zonez]
        zs.removeZones(zonesToRemove)
        self.assertEqual(len(zs.names), 0)
        self.assertFalse("ring-1" in zs)
        self.assertFalse("ring-2" in zs)
        self.assertFalse("ring-3" in zs)

    def test_findZoneItIsIn(self):
        # customize settings for this test
        newSettings = {}
        newSettings["zoneDefinitions"] = [
            "ring-1: 001-001",
            "ring-2: 002-001, 002-002",
        ]
        cs = self.o.cs.modified(newSettings=newSettings)

        self.r.core.buildManualZones(cs)
        daZones = self.r.core.zones
        for zone in daZones:
            a = self.r.core.getAssemblyWithStringLocation(sorted(zone.locs)[0])
            aZone = daZones.findZoneItIsIn(a)
            self.assertEqual(aZone, zone)

        # get assem from first zone
        a = self.r.core.getAssemblyWithStringLocation(sorted(daZones[daZones.names[0]].locs)[0])
        # remove the zone
        daZones.removeZone(daZones.names[0])

        # ensure that we can no longer find the assembly in the zone
        self.assertEqual(daZones.findZoneItIsIn(a), None)

    def test_getZoneLocations(self):
        # customize settings for this test
        newSettings = {}
        newSettings["zoneDefinitions"] = [
            "ring-1: 001-001",
            "ring-2: 002-001, 002-002",
        ]
        cs = self.o.cs.modified(newSettings=newSettings)
        self.r.core.buildManualZones(cs)

        # test the retrieval of zone locations
        self.assertEqual(set(["002-001", "002-002"]), self.r.core.zones.getZoneLocations("ring-2"))

    def test_getAllLocations(self):
        # customize settings for this test
        newSettings = {}
        newSettings["zoneDefinitions"] = [
            "ring-1: 001-001",
            "ring-2: 002-001, 002-002",
        ]
        cs = self.o.cs.modified(newSettings=newSettings)
        self.r.core.buildManualZones(cs)

        # test the retrieval of zone locations
        self.assertEqual(set(["001-001", "002-001", "002-002"]), self.r.core.zones.getAllLocations())

    def test_summary(self):
        # make sure we have a couple of zones to test on
        for name0 in ["ring-1", "ring-2", "ring-3"]:
            self.assertIn(name0, self.zonez.names)

        # test the summary (in the log)
        with mockRunLogs.BufferLog() as mock:
            runLog.LOG.startLog("test_summary")
            runLog.LOG.setVerbosity(logging.INFO)
            self.assertEqual("", mock.getStdout())

            self.zonez.summary()

            self.assertIn("zoneDefinitions:", mock.getStdout())
            self.assertIn("- ring-1: ", mock.getStdout())
            self.assertIn("- ring-2: ", mock.getStdout())
            self.assertIn("- ring-3: ", mock.getStdout())
            self.assertIn("003-001, 003-002, 003-003", mock.getStdout())

    def test_sortZones(self):
        # create some zones in non-alphabetical order
        zs = zones.Zones()
        zs.addZone(self.zonez["ring-3"])
        zs.addZone(self.zonez["ring-1"])
        zs.addZone(self.zonez["ring-2"])

        # check the initial order of the zones
        self.assertEqual(list(zs._zones.keys())[0], "ring-3")
        self.assertEqual(list(zs._zones.keys())[1], "ring-1")
        self.assertEqual(list(zs._zones.keys())[2], "ring-2")

        # sort the zones
        zs.sortZones()

        # check the final order of the zones
        self.assertEqual(list(zs._zones.keys())[0], "ring-1")
        self.assertEqual(list(zs._zones.keys())[1], "ring-2")
        self.assertEqual(list(zs._zones.keys())[2], "ring-3")
