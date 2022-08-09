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
from armi.reactor.assemblies import Assembly
from armi.reactor.blocks import Block
from armi.reactor.flags import Flags
from armi.settings.fwSettings import globalSettings


class Zone:
    """
    A group of locations in the Core, used to divide it up for analysis.
    Each location represents an Assembly or a Block.
    """

    VALID_TYPES = (Assembly, Block)

    def __init__(self, name, locations=None, zoneType=Assembly):
        self.name = name

        # A single Zone must contain items of the same type
        if zoneType not in Zone.VALID_TYPES:
            raise TypeError(
                "Invalid Type {0}; A Zone can only be of type {1}".format(
                    zoneType, Zone.VALID_TYPES
                )
            )
        self.zoneType = zoneType

        # a Zone is mostly just a collection of locations in the Reactor
        if locations is None:
            self.locs = set()
        else:
            # TODO: We either need to do a type check here, or put a note in that users have to be careful.
            self.locs = set(locations)

    def __contains__(self, loc):
        return loc in self.locs

    def __iter__(self):
        """Loop through the locations, in order."""
        for loc in sorted(self.locs):
            yield loc

    def __len__(self):
        return len(self.locs)

    def __repr__(self):
        zType = "Assemblies"
        if self.zoneType == Block:
            zType = "Blocks"

        return "<Zone {0} with {1} {2}>".format(self.name, len(self), zType)

    def addLoc(self, loc):
        # TODO: We either need to do a type check here, or put a note in that users have to be careful.
        assert isinstance(loc, str), "TODO?"
        self.locs.add(loc)

    def addLocs(self, locs):
        for loc in locs:
            self.addLoc(loc)

    def addItem(self, item):
        """TODO"""
        assert issubclass(type(item), self.zoneType), "TODO?"
        self.locs.add(item.getLocation())

    def addItems(self, items):
        """
        Adds the locations of a list of assemblies to a zone

        Parameters
        ----------
        items : list
            List of Assembly/Block objects
        """
        for item in items:
            self.addItem(item)


class Zones:
    """Collection of Zone objects."""

    def __init__(self):
        """Build a Zones object."""
        self._zones = {}

    @property
    def names(self):
        """Ordered names of contained zones."""
        return sorted(self._zones.keys())

    def __contains__(self, nomen):
        return nomen in self._zones

    def __delitem__(self, name):
        del self._zones[name]

    def __getitem__(self, name):
        """Access a zone by name."""
        return self._zones[name]

    def __iter__(self):
        """Loop through the zones in order."""
        for nm in sorted(self._zones.keys()):
            yield self._zones[nm]

    def addZone(self, zone):
        """Add a zone to the collection."""
        if zone.name in self._zones:
            raise ValueError(
                "Cannot add {} because a zone of that name already exists.".format(
                    zone.name
                )
            )
        self._zones[zone.name] = zone

    def addZones(self, zones):
        """Add multiple zones to the collection"""
        for zone in zones:
            self.addZone(zone)

        self.checkDuplicates()

    def removeZone(self, name):
        """delete a zone by name."""
        del self[name]

    def checkDuplicates(self):
        """TODO"""
        allLocs = []
        for zone in self:
            allLocs.extend(list(zone.locs))

        # use set lotic to test for duplicates
        if len(allLocs) == len(set(allLocs)):
            # no duplicates
            return

        # find duplicates by removing unique locs from the full list
        for uniqueLoc in set(allLocs):
            allLocs.remove(uniqueLoc)

        # there are duplicates, so raise an error
        locs = sorted(set(allLocs))
        raise RuntimeError("Duplicate items found in Zones: {0}".format(locs))

    def getZoneLocations(self, zoneNames):
        """
        Get the location labels of a particular (or a few) zone(s).

        Parameters
        ----------
        zoneNames : str, or list
            the zone name or list of names

        Returns
        -------
        zoneLocs : set
            List of location labels of this/these zone(s)
        """
        if not isinstance(zoneNames, list):
            zoneNames = [zoneNames]

        zoneLocs = set()
        for zn in zoneNames:
            try:
                thisZoneLocs = set(self[zn])
            except KeyError:
                runLog.error(
                    "The zone {0} does not exist. Please define it.".format(zn)
                )
                raise
            zoneLocs.update(thisZoneLocs)

        return zoneLocs

    def getAllLocations(self):
        """TODO"""
        locs = set()
        for zoneName in self:
            locs.update(self[zoneName])

        return locs

    def findZoneItIsIn(self, a):
        """
        Return the zone object that this Assembly/Block is in.

        Parameters
        ----------
        a : Assembly or Block
           The item to locate

        Returns
        -------
        zone : Zone object that the input item resides in.
        """
        aLoc = a.getLocation()
        zoneFound = False
        for zone in self:
            if aLoc in zone.locs:
                zoneFound = True
                return zone

        if not zoneFound:
            runLog.warning("Was not able to find which zone {} is in".format(a))

        return None


# TODO: This only works for Assemblies!
def zoneSummary(core, zoneNames=None):
    """Print out power distribution of fuel assemblies this/these zone."""
    if zoneNames is None:
        zoneNames = core.zones.names

    msg = "Zone Summary"
    if core.r is not None:
        msg += " at Cycle {0}, timenode {1}".format(core.r.p.cycle, core.r.p.timeNode)

    runLog.info(msg)
    totalPower = 0.0

    for zoneName in sorted(zoneNames):
        runLog.info("zone {0}".format(zoneName))
        massFlow = 0.0

        # find the maximum power to flow in each zone
        maxPower = -1.0
        fuelAssemsInZone = core.getAssemblies(Flags.FUEL, zones=zoneName)
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
        slabPowList = _getZoneAxialPowerDistribution(core, zoneName)
        if not slabPowList or not fuelAssemsInZone:
            runLog.important("No fuel assemblies exist in zone {0}".format(zoneName))
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
            "".format(len(fuelAssemsInZone) * core.powerMultiplier)
        )

        totalPower += totalZonePower

    runLog.info("Total power of fuel in all zones is {0:.6E} Watts".format(totalPower))


def _getZoneAxialPowerDistribution(core, zone):
    """Return a list of powers in watts of the axial levels of zone.
    Helper method for Zones summary.
    """
    slabPower = {}
    zi = 0
    for a in core.getAssemblies(Flags.FUEL, zones=zone):
        # Add up slab power and flow rates
        for zi, b in enumerate(a):
            slabPower[zi] = (
                slabPower.get(zi, 0.0)
                + b.p.power * b.getSymmetryFactor() * core.powerMultiplier
            )

    # reorder the dictionary into a list, knowing that zi is stopped at the highest block
    slabPowList = []
    for i in range(zi + 1):
        try:
            slabPowList.append(slabPower[i])
        except:
            runLog.warning("slabPower {} zone {}".format(slabPower, zone))

    return slabPowList


# TODO: How do we support zoningStrategies in external codebases?
def buildZones(core, cs):
    """
    Build/update the Zones.

    The zoning option is determined by the ``zoningStrategy`` setting.
    """
    zones = Zones()
    zoneOption = cs[globalSettings.CONF_ZONING_STRATEGY]
    if "manual" in zoneOption:
        zones.addZones(_buildManualZones(cs))
    else:
        raise ValueError(
            "Invalid `zoningStrategy` grouping option {}".format(zoneOption)
        )

    return zones


def _buildManualZones(cs):
    runLog.extra(
        "Building Zones by manual zone definitions in `zoneDefinitions` setting"
    )
    stripper = lambda s: s.strip()
    zones = Zones()
    # read input zones, which are special strings like this: "zoneName: loc1,loc2,loc3,loc4,..."
    for zoneString in cs["zoneDefinitions"]:
        zoneName, zoneLocs = zoneString.split(":")
        zoneLocs = zoneLocs.split(",")
        zone = Zone(zoneName.strip())
        zone.addLocs(map(stripper, zoneLocs))
        zones.addZone(zone)

    return zones
