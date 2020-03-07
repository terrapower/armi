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
import copy
import unittest

import armi
from armi import settings
from armi.reactor import assemblies
from armi.reactor import blueprints
from armi.reactor import geometry
from armi.reactor import grids
from armi.reactor import reactors
from armi.reactor import zones
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.utils import pathTools
from armi.settings.fwSettings import globalSettings

THIS_DIR = pathTools.armiAbsDirFromName(__name__)


class Zone_TestCase(unittest.TestCase):
    def setUp(self):
        bp = blueprints.Blueprints()
        r = reactors.Reactor("zonetest", bp)
        r.add(reactors.Core("Core"))
        r.core.spatialGrid = grids.hexGridFromPitch(1.0)
        r.core.spatialGrid.symmetry = geometry.THIRD_CORE + geometry.PERIODIC
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

    def test_addRing(self):
        zone = zones.Zone("TestZone")
        zone.addRing(5)
        self.assertIn("A5003", zone)
        self.assertNotIn("A6002", zone)

        zone.addRing(6, 3, 9)
        self.assertIn("A6003", zone)
        self.assertIn("A6009", zone)
        self.assertNotIn("A6002", zone)
        self.assertNotIn("A6010", zone)


class Zones_InReactor(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor()

    def test_buildRingZones(self):
        o, r = self.o, self.r
        cs = o.cs
        cs[globalSettings.CONF_ZONING_STRATEGY] = "byRingZone"
        cs["ringZones"] = []
        zonez = zones.buildZones(r.core, cs)
        self.assertEqual(len(list(zonez)), 1)
        self.assertEqual(9, r.core.numRings)

        cs["ringZones"] = [5, 8]
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

        cs["ringZones"] = [5, 7, 8]
        zonez = zones.buildZones(r.core, cs)
        self.assertEqual(len(list(zonez)), 3)
        zone = zonez["ring-3"]
        self.assertEqual(len(zone), 30)  # rings 8 and 9. See above comment

    def test_removeZone(self):
        o, r = self.o, self.r
        cs = o.cs
        cs[globalSettings.CONF_ZONING_STRATEGY] = "byRingZone"
        cs["ringZones"] = [5, 8]
        # produce 2 zones, with the names ringzone0 and ringzone1
        daZones = zones.buildZones(r.core, cs)
        daZones.removeZone("ring-1")
        # The names list should only house the only other remaining zone now
        self.assertEqual(["ring-2"], daZones.names)

        # if indexed like a dict, the zones object should give a key error from the removed zone
        with self.assertRaises(KeyError):
            daZones["ring-1"]

        # Ensure we can still iterate through our zones object
        for name in daZones.names:
            aZone = daZones[name]

    def test_findZoneAssemblyIsIn(self):
        cs = self.o.cs
        cs["ringZones"] = [5, 7, 8]
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
    def test_splitZones(self):
        # Test to make sure that we can split a zone containing control and fuel assemblies.
        # Also test that we can separate out assemblies with differing numbers of blocks.

        o, r = test_reactors.loadTestReactor(inputFileName="partisnTestReactor.yaml")
        cs = o.cs
        cs["splitZones"] = False
        cs[globalSettings.CONF_ZONING_STRATEGY] = "byRingZone"
        cs["ringZones"] = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        diverseZone = "ring-4"
        r.core.buildZones(cs)
        daZones = r.core.zones
        # lets make one of the assemblies have an extra block
        zoneLocations = daZones.getZoneLocations(diverseZone)
        originalAssemblies = r.core.getLocationContents(
            zoneLocations, assemblyLevel=True
        )
        fuel = [a for a in originalAssemblies if a.hasFlags(Flags.FUEL)][0]
        newBlock = copy.deepcopy(fuel[-1])
        fuel.add(newBlock)

        # should contain a zone for every ring zone
        # we only want one ring zone for this test, containing assemblies of different types.
        zoneTup = tuple(daZones.names)
        for zoneName in zoneTup:
            if zoneName != diverseZone:
                daZones.removeZone(zoneName)
        # this should split diverseZone into multiple zones by nodalization type.
        cs["splitZones"] = True
        zones.splitZones(r.core, cs, daZones)
        # test to make sure that we split the ring zone correctly
        self.assertEqual(len(daZones["ring-4-primary-control-5"]), 2)
        self.assertEqual(len(daZones["ring-4-middle-fuel-5"]), 3)
        self.assertEqual(len(daZones["ring-4-middle-fuel-6"]), 1)

    def test_createHotZones(self):
        # Test to make sure createHotZones identifies the highest p/f location in a zone
        # Test to make sure createHotZones can remove the peak assembly from that zone and place it in a new zone
        # Test that the power in the old zone and the new zone is conserved.
        # Test that if a hot zone can not be created from a single assembly zone.
        o, r = test_reactors.loadTestReactor(inputFileName="partisnTestReactor.yaml")
        cs = o.cs
        cs["splitZones"] = False
        cs[globalSettings.CONF_ZONING_STRATEGY] = "byRingZone"
        cs["ringZones"] = [9]  # build one giant zone
        r.core.buildZones(cs)
        daZones = r.core.zones

        originalassemblies = []
        originalPower = 0.0
        peakZonePFRatios = []

        # Create a single assembly zone to verify that it will not create a hot zone
        single = zones.Zone("single")
        daZones.add(single)
        aLoc = r.core.getFirstAssembly(Flags.FUEL).getLocation()
        single.append(aLoc)

        # Set power and flow.
        # Also gather channel peak P/F ratios, assemblies and power.
        for zone in daZones:
            powerToFlow = []
            zoneLocations = daZones.getZoneLocations(zone.name)
            assems = r.core.getLocationContents(zoneLocations, assemblyLevel=True)
            power = 300.0
            flow = 300.0
            for a in assems:
                a.getFirstBlock().p.power = power
                assemblyPower = a.calcTotalParam("power")
                a[-1].p.THmassFlowRate = flow
                powerToFlow.append(assemblyPower / a[-1].p.THmassFlowRate)
                originalPower += assemblyPower
                originalassemblies.append(a)
                power += 1
                flow -= 1
            peakZonePFRatios.append(max(powerToFlow))

        daZones = zones.createHotZones(r.core, daZones)
        # Test that the hot zones have the peak P/F from the host channels
        i = 0
        for zone in daZones:
            if zone.hotZone:
                hotAssemLocation = daZones.getZoneLocations(zone.name)
                hotAssem = r.core.getLocationContents(
                    hotAssemLocation, assemblyLevel=True
                )[0]
                self.assertEqual(
                    peakZonePFRatios[i],
                    hotAssem.calcTotalParam("power") / hotAssem[-1].p.THmassFlowRate,
                )
                i += 1

        powerAfterHotZoning = 0.0
        assembliesAfterHotZoning = []

        # Check that power is conserved and that we did not lose any assemblies
        for zone in daZones:
            locs = daZones.getZoneLocations(zone.name)
            assems = r.core.getLocationContents(locs, assemblyLevel=True)
            for a in assems:
                assembliesAfterHotZoning.append(a)
                powerAfterHotZoning += a.calcTotalParam("power")
        self.assertEqual(powerAfterHotZoning, originalPower)
        self.assertEqual(len(assembliesAfterHotZoning), len(originalassemblies))

        # check that the original zone with 1 channel has False for hotzone
        self.assertEqual(single.hotZone, False)
        # check that we have the correct number of hot and normal zones.
        hotCount = 0
        normalCount = 0
        for zone in daZones:
            if zone.hotZone:
                hotCount += 1
            else:
                normalCount += 1
        self.assertEqual(hotCount, 1)
        self.assertEqual(normalCount, 2)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Zones_InReactor.test_buildRingZones']
    unittest.main()
