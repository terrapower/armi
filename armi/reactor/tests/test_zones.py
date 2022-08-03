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

"""Test for Zones"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import copy
import logging
import os
import unittest

from armi import runLog
from armi.reactor import assemblies
from armi.reactor import blueprints
from armi.reactor import geometry
from armi.reactor import grids
from armi.reactor import reactors
from armi.reactor import zones
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.settings.fwSettings import globalSettings
from armi.tests import mockRunLogs

THIS_DIR = os.path.dirname(__file__)


class Zone_TestCase(unittest.TestCase):
    def setUp(self):
        bp = blueprints.Blueprints()
        r = reactors.Reactor("zonetest", bp)
        r.add(reactors.Core("Core"))
        r.core.spatialGrid = grids.HexGrid.fromPitch(1.0)
        r.core.spatialGrid.symmetry = geometry.SymmetryType(
            geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC
        )
        r.core.spatialGrid.geomType = geometry.HEX
        aList = []
        for ring in range(10):
            a = assemblies.HexAssembly("fuel")
            a.spatialLocator = r.core.spatialGrid[ring, 1, 0]
            a.parent = r.core
            aList.append(a)
        self.aList = aList

    def test_addAssemblyLocations(self):
        zone = zones.Zone("TestZone")
        zone.addAssemblyLocations(self.aList)
        for a in self.aList:
            self.assertIn(a.getLocation(), zone)

        self.assertRaises(RuntimeError, zone.addAssemblyLocations, self.aList)

    def test_iteration(self):
        locs = [a.getLocation() for a in self.aList]
        zone = zones.Zone("TestZone")
        zone.addAssemblyLocations(self.aList)
        for aLoc in zone:
            self.assertIn(aLoc, locs)

        # loop twice to make sure it iterates nicely.
        for aLoc in zone:
            self.assertIn(aLoc, locs)

    def test_extend(self):
        zone = zones.Zone("TestZone")
        zone.extend([a.getLocation() for a in self.aList])
        for a in self.aList:
            self.assertIn(a.getLocation(), zone)

    def test_index(self):
        zone = zones.Zone("TestZone")
        zone.addAssemblyLocations(self.aList)
        for i, loc in enumerate(zone.locList):
            self.assertEqual(i, zone.index(loc))

    def test_addRing(self):
        zone = zones.Zone("TestZone")
        zone.addRing(5)
        self.assertIn("005-003", zone)
        self.assertNotIn("006-002", zone)

        zone.addRing(6, 3, 9)
        self.assertIn("006-003", zone)
        self.assertIn("006-009", zone)
        self.assertNotIn("006-002", zone)
        self.assertNotIn("006-010", zone)

    def test_add(self):
        zone = zones.Zone("TestZone")
        zone.addRing(5)
        otherZone = zones.Zone("OtherZone")
        otherZone.addRing(6, 3, 9)
        combinedZoneList = zone + otherZone
        self.assertIn("005-003", combinedZoneList)
        self.assertIn("006-003", combinedZoneList)
        self.assertIn("006-009", combinedZoneList)


class Zones_InReactor(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor()

    def test_buildRingZones(self):
        o, r = self.o, self.r
        cs = o.cs

        newSettings = {globalSettings.CONF_ZONING_STRATEGY: "byRingZone"}
        newSettings["ringZones"] = []
        cs = cs.modified(newSettings=newSettings)
        zonez = zones.buildZones(r.core, cs)
        self.assertEqual(len(list(zonez)), 1)
        self.assertEqual(9, r.core.numRings)

        newSettings = {"ringZones": [5, 8]}
        cs = cs.modified(newSettings=newSettings)
        zonez = zones.buildZones(r.core, cs)
        self.assertEqual(len(list(zonez)), 2)
        zone = zonez["ring-1"]
        self.assertEqual(len(zone), (5 * (5 - 1) + 1))
        zone = zonez["ring-2"]
        # Note that the actual number of rings in the reactor model is 9. Even though we
        # asked for the last zone to to to 8, the zone engine should bump it out. Not
        # sure if this is behavior that we want to preserve, but at least it's being
        # tested properly now.
        self.assertEqual(len(zone), (9 * (9 - 1) + 1) - (5 * (5 - 1) + 1))

        newSettings = {"ringZones": [5, 7, 8]}
        cs = cs.modified(newSettings=newSettings)
        zonez = zones.buildZones(r.core, cs)
        self.assertEqual(len(list(zonez)), 3)
        zone = zonez["ring-3"]
        self.assertEqual(len(zone), 30)  # rings 8 and 9. See above comment

    def test_buildManualZones(self):
        o, r = self.o, self.r
        cs = o.cs

        # customize settings for this test
        newSettings = {globalSettings.CONF_ZONING_STRATEGY: "manual"}
        newSettings["zoneDefinitions"] = [
            "ring-1: 001-001",
            "ring-2: 002-001, 002-002",
            "ring-3: 003-001, 003-002, 003-003",
        ]
        cs = cs.modified(newSettings=newSettings)
        zonez = zones.buildZones(r.core, cs)

        self.assertEqual(len(list(zonez)), 3)
        self.assertIn("003-002", zonez["ring-3"])

    def test_buildAssemTypeZones(self):
        o, r = self.o, self.r
        cs = o.cs

        # customize settings for this test
        newSettings = {globalSettings.CONF_ZONING_STRATEGY: "byFuelType"}
        cs = cs.modified(newSettings=newSettings)
        zonez = zones.buildZones(r.core, cs)

        self.assertEqual(len(list(zonez)), 4)
        self.assertIn("008-040", zonez["feed fuel"])
        self.assertIn("005-023", zonez["igniter fuel"])
        self.assertIn("003-002", zonez["lta fuel"])
        self.assertIn("004-003", zonez["lta fuel b"])

    def test_buildZonesForEachFA(self):
        o, r = self.o, self.r
        cs = o.cs

        # customize settings for this test
        newSettings = {globalSettings.CONF_ZONING_STRATEGY: "everyFA"}
        cs = cs.modified(newSettings=newSettings)
        zonez = zones.buildZones(r.core, cs)

        self.assertEqual(len(list(zonez)), 53)
        self.assertIn("008-040", zonez["channel 1"])
        self.assertIn("005-023", zonez["channel 2"])
        self.assertIn("006-029", zonez["channel 3"])

    def test_removeZone(self):
        o, r = self.o, self.r
        cs = o.cs

        # customize settings for this test
        newSettings = {globalSettings.CONF_ZONING_STRATEGY: "byRingZone"}
        newSettings["ringZones"] = [5, 8]
        cs = cs.modified(newSettings=newSettings)

        # produce 2 zones, with the names ringzone0 and ringzone1
        daZones = zones.buildZones(r.core, cs)
        daZones.removeZone("ring-1")

        # The names list should only house the only other remaining zone now
        self.assertEqual(["ring-2"], daZones.names)

        # if indexed like a dict, the zones object should give a key error from the removed zone
        with self.assertRaises(KeyError):
            daZones["ring-1"]  # pylint: disable=pointless-statement

        # Ensure we can still iterate through our zones object
        for name in daZones.names:
            _ = daZones[name]

    def test_findZoneAssemblyIsIn(self):
        cs = self.o.cs

        newSettings = {"ringZones": [5, 7, 8]}
        cs = cs.modified(newSettings=newSettings)

        daZones = zones.buildZones(self.r.core, cs)
        for zone in daZones:
            a = self.r.core.getAssemblyWithStringLocation(zone.locList[0])
            aZone = daZones.findZoneAssemblyIsIn(a)
            self.assertEqual(aZone, zone)

        # lets test if we get a none and a warning if the assembly does not exist in a zone
        a = self.r.core.getAssemblyWithStringLocation(
            daZones[daZones.names[0]].locList[0]
        )  # get assem from first zone
        daZones.removeZone(
            daZones.names[0]
        )  # remove a zone to ensure that our assem does not have a zone anymore

        self.assertEqual(daZones.findZoneAssemblyIsIn(a), None)


class Zones_InRZReactor(unittest.TestCase):
    def test_zoneSummary(self):
        o, r = test_reactors.loadTestReactor()

        r.core.buildZones(o.cs)
        daZones = r.core.zones

        # make sure we have a couple of zones to test on
        for name0 in ["ring-1"]:
            self.assertIn(name0, daZones.names)

        with mockRunLogs.BufferLog() as mock:
            runLog.LOG.startLog("test_zoneSummary")
            runLog.LOG.setVerbosity(logging.INFO)

            self.assertEqual("", mock._outputStream)

            daZones.summary()

            self.assertIn("Zone Summary", mock._outputStream)
            self.assertIn("Zone Power", mock._outputStream)
            self.assertIn("Zone Average Flow", mock._outputStream)


if __name__ == "__main__":
    unittest.main()
