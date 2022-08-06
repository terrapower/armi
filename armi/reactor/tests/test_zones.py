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
        for i, loc in enumerate(zone.locs):
            self.assertEqual(i, zone.index(loc))


class Zones_InReactor(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor()

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

    def test_removeZone(self):
        o, r = self.o, self.r
        cs = o.cs

        # customize settings for this test
        newSettings = {globalSettings.CONF_ZONING_STRATEGY: "manual"}
        newSettings["zoneDefinitions"] = [
            "ring-1: 001-001",
            "ring-2: 002-001, 002-002",
        ]
        cs = cs.modified(newSettings=newSettings)

        # build 2 zones
        daZones = zones.buildZones(r.core, cs)

        # remove a Zone
        daZones.removeZone("ring-1")

        # verify we only have the one zone left
        self.assertEqual(["ring-2"], daZones.names)

        # if indexed like a dict, the zones object should give a key error from the removed zone
        with self.assertRaises(KeyError):
            daZones["ring-1"]  # pylint: disable=pointless-statement

        # Ensure we can still iterate through our zones object
        for name in daZones.names:
            _ = daZones[name]

    def test_findZoneAssemblyIsIn(self):
        cs = self.o.cs

        # customize settings for this test
        newSettings = {globalSettings.CONF_ZONING_STRATEGY: "manual"}
        newSettings["zoneDefinitions"] = [
            "ring-1: 001-001",
            "ring-2: 002-001, 002-002",
        ]
        cs = cs.modified(newSettings=newSettings)

        daZones = zones.buildZones(self.r.core, cs)
        for zone in daZones:
            a = self.r.core.getAssemblyWithStringLocation(zone.locs[0])
            aZone = daZones.findZoneAssemblyIsIn(a)
            self.assertEqual(aZone, zone)

        # get assem from first zone
        a = self.r.core.getAssemblyWithStringLocation(daZones[daZones.names[0]].locs[0])
        # remove the zone
        daZones.removeZone(daZones.names[0])

        # ensure that we can no longer find the assembly in the zone
        self.assertEqual(daZones.findZoneAssemblyIsIn(a), None)


class Zones_InRZReactor(unittest.TestCase):
    def test_zoneSummary(self):
        o, r = test_reactors.loadTestReactor()

        # customize settings for this test
        newSettings = {globalSettings.CONF_ZONING_STRATEGY: "manual"}
        newSettings["zoneDefinitions"] = [
            "ring-1: 001-001",
            "ring-2: 002-001, 002-002",
        ]
        o.cs = o.cs.modified(newSettings=newSettings)

        r.core.buildZones(o.cs)
        daZones = r.core.zones

        # make sure we have a couple of zones to test on
        for name0 in ["ring-1"]:
            self.assertIn(name0, daZones.names)

        # test the summary (in the log)
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
