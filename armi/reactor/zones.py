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

"""
Zones are collections of locations in the Core, used to divide it up for analysis.
"""
from armi import runLog
from armi.reactor import grids
from armi.reactor.flags import Flags
from armi.settings.fwSettings import globalSettings


class Zone:
    """
    A group of locations in the Core, used to divide it up for analysis.
    Each location represents an Assembly or a Block.
    """

    def __init__(self, name, locations=None, symmetry=3):
        self.symmetry = symmetry
        self.name = name
        if locations is None:
            locations = []
        self.locList = locations
        self.hostZone = name

    def __repr__(self):
        return "<Zone {0} with {1} locations>".format(self.name, len(self))

    def __getitem__(self, index):
        return self.locList[index]

    def __setitem__(self, index, locStr):
        self.locList[index] = locStr

    def extend(self, locList):
        self.locList.extend(locList)

    def index(self, loc):
        return self.locList.index(loc)

    def __len__(self):
        return len(self.locList)

    def __add__(self, other):
        """Returns all the blocks in both assemblies."""
        return self.locList + other.locList

    def append(self, obj):
        if obj in self.locList:
            # locations must be unique
            raise RuntimeError("{0} is already in this zone: {1}".format(obj, self))
        self.locList.append(obj)

    def addAssemblyLocations(self, aList):
        """
        Adds the locations of a list of assemblies to a zone

        Parameters
        ----------
        aList : list
            List of assembly objects
        """
        for a in aList:
            self.append(a.getLocation())

    # TODO: p0, p1 are only used in testing
    def addRing(self, ring, p0=None, p1=None):
        """
        Adds a section of a ring (or a whole ring) to the zone

        Parameters
        ----------
        ring : int
            The ring to add

        p0 : int, optional
            beginning position within ring. Default: None (full ring)

        p1 : int, optional
            Ending position within ring.
        """
        grid = grids.HexGrid.fromPitch(1.0)
        if p0 is None or p1 is None:
            if self.symmetry == 3:
                posList = grid.allPositionsInThird(ring)
            elif self.symmetry == 1:
                posList = range(1, grid.getPositionsInRing(ring) + 1)
            else:
                raise RuntimeError(
                    "Zones are not written to handle {0}-fold symmetry yet"
                    "".format(self.symmetry)
                )
        else:
            posList = range(p0, p1 + 1)

        for pos in posList:
            newLoc = grid.getLabel(
                grid.getLocatorFromRingAndPos(ring, pos).getCompleteIndices()[:2]
            )
            if newLoc not in self.locList:
                self.append(newLoc)


class Zones:
    """Collection of Zone objects."""

    def __init__(self, core, cs):
        """Build a Zones object."""
        self.core = core
        self.cs = cs
        self._zones = {}
        self._names = []

    @property
    def names(self):
        """Ordered names of contained zones."""
        return self._names

    def __getitem__(self, name):
        """Access a zone by name."""
        return self._zones[name]

    def __delitem__(self, name):
        del self._zones[name]
        # Now delete the corresponding zone name from the names list
        try:
            self._names.remove(name)
        except ValueError as ee:
            raise ValueError(ee)

    def __iter__(self):
        """Loop through the zones in order."""
        for nm in self._names:
            yield self._zones[nm]

    def update(self, zones):
        """Merge with another Zones."""
        for zone in zones:
            self.add(zone)

    def add(self, zone):
        """Add a zone to the collection."""
        if zone.name in self._zones:
            raise ValueError(
                "Cannot add {} because a zone of that name already exists.".format(
                    zone.name
                )
            )
        self._zones[zone.name] = zone
        self._names.append(zone.name)

    def removeZone(self, name):
        """delete a zone by name."""
        del self[name]

    def summary(self, zoneNames=None):
        """Print out power distribution of fuel assemblies this/these zone."""
        if zoneNames is None:
            zoneNames = self.names
        msg = "Zone Summary"
        if self.core.r is not None:
            msg += " at Cycle {0}, timenode {1}".format(
                self.core.r.p.cycle, self.core.r.p.timeNode
            )
        runLog.info(msg)
        totalPower = 0.0

        for zoneName in sorted(zoneNames):
            runLog.info("zone {0}".format(zoneName))
            massFlow = 0.0

            # find the maximum power to flow in each zone
            maxPower = -1.0
            fuelAssemsInZone = self.core.getAssemblies(Flags.FUEL, zones=zoneName)
            a = []
            for a in fuelAssemsInZone:
                flow = a.p.THmassFlowRate * a.getSymmetryFactor()
                aPow = a.calcTotalParam("power", calcBasedOnFullObj=True)
                if aPow > maxPower:
                    maxPower = aPow
                if not flow:
                    runLog.important(
                        "No TH data. Run with thermal hydraulics activated. "
                        "Zone report will have flow rate of zero",
                        single=True,
                        label="Cannot summarize zone T/H",
                    )
                    # no TH for some reason
                    flow = 0.0
                massFlow += flow

            # Get power from the extracted power method.
            slabPowList = self.getZoneAxialPowerDistribution(zoneName)
            if not slabPowList or not fuelAssemsInZone:
                runLog.important(
                    "No fuel assemblies exist in zone {0}".format(zoneName)
                )
                return

            # loop over the last assembly to produce the final output.
            z = 0.0
            totalZonePower = 0.0
            for zi, b in enumerate(a):
                slabHeight = b.getHeight()
                thisSlabPow = slabPowList[zi]
                runLog.info(
                    "  Power of {0:8.3f} cm slab at z={1:8.3f} (W): {2:12.5E}"
                    "".format(slabHeight, z, thisSlabPow)
                )
                z += slabHeight
                totalZonePower += thisSlabPow

            runLog.info("  Total Zone Power (Watts): {0:.3E}".format(totalZonePower))
            runLog.info(
                "  Zone Average Flow rate (kg/s): {0:.3f}"
                "".format(massFlow / len(fuelAssemsInZone))
            )
            runLog.info(
                "  There are {0} assemblies in this zone"
                "".format(len(fuelAssemsInZone) * self.core.powerMultiplier)
            )

            totalPower += totalZonePower
        runLog.info(
            "Total power of fuel in all zones is {0:.6E} Watts".format(totalPower)
        )

    def getZoneAxialPowerDistribution(self, zone):
        """Return a list of powers in watts of the axial levels of zone."""
        slabPower = {}
        zi = 0
        for a in self.core.getAssemblies(Flags.FUEL, zones=zone):
            # Add up slab power and flow rates
            for zi, b in enumerate(a):
                slabPower[zi] = (
                    slabPower.get(zi, 0.0)
                    + b.p.power * b.getSymmetryFactor() * self.core.powerMultiplier
                )

        # reorder the dictionary into a list, knowing that zi is stopped at the highest block
        slabPowList = []
        for i in range(zi + 1):
            try:
                slabPowList.append(slabPower[i])
            except:
                runLog.warning("slabPower {} zone {}".format(slabPower, zone))
        return slabPowList

    def getZoneLocations(self, zoneNames):
        """
        Get the location labels of a particular (or a few) zone(s).

        Parameters
        ----------
        zoneNames : str or list
            the zone name or list of names

        Returns
        -------
        zoneLocs : list
            List of location labels of this/these zone(s)
        """
        if not isinstance(zoneNames, list):
            zoneNames = [zoneNames]

        zoneLocs = []
        for zn in zoneNames:
            try:
                thisZoneLocs = self[zn]
            except KeyError:
                runLog.error(
                    "The zone {0} does not exist. Please define it.".format(zn)
                )
                raise
            zoneLocs.extend(thisZoneLocs)

        return zoneLocs

    def findZoneAssemblyIsIn(self, a):
        """
        Return the zone object that this assembly is in.

        Parameters
        ----------
        a : assembly
           The assembly to locate

        Returns
        -------
        zone : Zone object that the input assembly resides in.
        """
        aLoc = a.getLocation()
        zoneFound = False
        for zone in self:
            if aLoc in zone.locList:
                zoneFound = True
                return zone

        if not zoneFound:
            runLog.warning("Was not able to find which zone {} is in".format(a))

        return None


# TODO: How do we support zoningStrategies in external codebases?
def buildZones(core, cs):
    """
    Build/update the Zones.

    The zoning option is determined by the ``zoningStrategy`` setting.
    """
    zones = Zones(core, cs)
    zoneOption = cs[globalSettings.CONF_ZONING_STRATEGY]
    if "manual" in zoneOption:
        zones.update(_buildManualZones(core, cs))
    else:
        raise ValueError(
            "Invalid `zoningStrategy` grouping option {}".format(zoneOption)
        )

    return zones


def _buildManualZones(core, cs):
    runLog.extra(
        "Building Zones by manual zone definitions in `zoneDefinitions` setting"
    )
    stripper = lambda s: s.strip()
    zones = Zones(core, cs)
    # read input zones, which are special strings like this: "zoneName: loc1,loc2,loc3,loc4,..."
    for zoneString in cs["zoneDefinitions"]:
        zoneName, zoneLocs = zoneString.split(":")
        zoneLocs = zoneLocs.split(",")
        zone = Zone(zoneName.strip())
        zone.extend(map(stripper, zoneLocs))
        zones.add(zone)
    return zones
