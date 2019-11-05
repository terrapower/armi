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
Zones are collections of locations.
"""

import math

import tabulate

from armi import runLog
from armi import utils
from armi.reactor import grids
from armi.reactor import locations
from armi.reactor.flags import Flags
from armi.utils import hexagon
from armi.settings.fwSettings import globalSettings


class Zone(object):
    """
    A group of locations labels useful for choosing where to shuffle from or where to compute
    reactivity coefficients.
    locations if specified should be provided as a list of assembly locations.
    """

    def __init__(self, name, locations=None, symmetry=3):
        self.symmetry = symmetry
        self.name = name
        if locations is None:
            locations = []
        self.locList = locations
        self.hotZone = False
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
        if p0 is None or p1 is None:
            if self.symmetry == 3:
                grid = grids.hexGridFromPitch(1.0)
                posList = grid.allPositionsInThird(ring)
            elif self.symmetry == 1:
                posList = range(1, hexagon.numPositionsInRing(ring) + 1)
            else:
                raise RuntimeError(
                    "Zones are not written to handle {0}-fold symmetry yet"
                    "".format(self.symmetry)
                )
        else:
            posList = range(p0, p1 + 1)

        for pos in posList:
            newLoc = str(locations.HexLocation(ring, pos))
            if newLoc not in self.locList:
                self.append(newLoc)


class Zones(object):
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
            maxPowerAssem = None
            fuelAssemsInZone = self.core.getAssemblies(Flags.FUEL, zones=zoneName)
            for a in fuelAssemsInZone:
                flow = a.p.THmassFlowRate * a.getSymmetryFactor()
                aPow = a.calcTotalParam("power", calcBasedOnFullObj=True)
                if aPow > maxPower:
                    maxPower = aPow
                    maxPowerAssem = a
                if not flow:
                    runLog.important(
                        "No TH data. Run with thermal hydraulics activated. "
                        "Zone report will have flow rate of zero",
                        single=True,
                        label="Cannot summarize ring zone T/H",
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
            if self.cs["doOrificedTH"] and maxPowerAssem[0].p.THmaxLifeTimePower:
                # print on the maximum power to flow in each ring zone.  This only has any meaning in
                # an orficedTH case, no reason to use it otherwise.
                runLog.info(
                    "  The maximum power to flow is {} from assembly {} in this zone"
                    "".format(
                        maxPower / maxPowerAssem[0].p.THmaxLifeTimePower, maxPowerAssem
                    )
                )
            # runLog.info('Flow rate  (m/s): {0:.3f}'.format())
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

    def getRingZoneRings(self):
        """
        Get rings in each ring zone as a list of lists.

        Returns
        -------
        ringZones : list
            List of lists. Each entry is the ring numbers in a ring zone.
            If there are no ring zones defined, returns a list of all rings.
        """
        core = self.core
        if not self.cs["ringZones"]:
            # no ring zones defined. Return all rings.
            return [range(1, core.getNumRings() + 1)]

        # ringZones are upper limits, defining ring zones from the center. so if they're
        #  [3, 5, 8, 90] then the ring zones are from 1 to 3, 4 to 5, 6 to 8, etc.
        # AKA, the upper bound is included in that particular zone.

        # check validity of ringZones. Increasing order and integers.
        ring0 = 0
        for i, ring in enumerate(self.cs["ringZones"]):
            if ring <= ring0 or not isinstance(ring, int):
                runLog.warning(
                    "ring zones {0} are invalid. Must be integers, increasing in order. "
                    "Can not return ring zone rings.".format(self.cs["ringZones"])
                )
                return
            ring0 = ring
            if i == len(self.cs["ringZones"]) - 1:
                # this is the final ring zone
                if ring < (core.getNumRings() + 1):
                    finalRing = core.getNumRings()
                else:
                    finalRing = None

        # modify the ringZones to definitely include all assemblies
        if finalRing:
            runLog.debug(
                "Modifying final ring zone definition to include all assemblies. New max: {0}".format(
                    finalRing
                ),
                single=True,
                label="Modified ring zone definition",
            )
            self.cs["ringZones"][-1] = finalRing

        # build the ringZone list
        ring0 = 0
        ringZones = []
        for upperRing in self.cs["ringZones"]:
            ringsInThisZone = range(
                ring0 + 1, upperRing + 1
            )  # the rings in this ring zone as defined above.

            ringZones.append(ringsInThisZone)
            ring0 = upperRing

        return ringZones

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


def buildZones(core, cs):
    """
    Build/update the zones.

    Zones are groups of assembly locations used for various purposes such as defining SASSYS channels and
    reactivity coefficients.

    The zoning option is determined by the ``zoningStrategy`` setting.
    """
    zones = Zones(core, cs)
    zoneOption = cs[globalSettings.CONF_ZONING_STRATEGY]
    if "byRingZone" in zoneOption:
        zones.update(_buildRingZoneZones(core, cs))
    elif "manual" in zoneOption:
        zones.update(_buildManualZones(core, cs))
    elif "byFuelType" in zoneOption:
        zones.update(_buildAssemTypeZones(core, cs, Flags.FUEL))
    elif "byOrifice" in zoneOption:
        zones.update(_buildZonesByOrifice(core, cs))
    elif "everyFA" in zoneOption:
        zones.update(_buildZonesforEachFA(core, cs))
    else:
        raise ValueError(
            "Invalid `zoningStrategy` grouping option {}".format(zoneOption)
        )

    if cs["createAssemblyTypeZones"]:
        zones.update(_buildAssemTypeZones(core, cs, Flags.FUEL))

    # Summarize the zone information
    headers = [
        "Zone\nNumber",
        "\nName",
        "\nAssemblies",
        "\nLocations",
        "Symmetry\nFactor",
        "Hot\nZone",
    ]
    zoneSummaryData = []
    for zi, zone in enumerate(zones, 1):
        assemLocations = utils.createFormattedStrWithDelimiter(
            zone, maxNumberOfValuesBeforeDelimiter=6
        )
        zoneSummaryData.append(
            (zi, zone.name, len(zone), assemLocations, zone.symmetry, zone.hotZone)
        )
    runLog.info(
        "Assembly zone definitions:\n"
        + tabulate.tabulate(
            tabular_data=zoneSummaryData, headers=headers, tablefmt="armi"
        ),
        single=True,
    )
    return zones


def _buildZonesByOrifice(core, cs):
    """
    Group fuel assemblies by orifice zones.

    Each zone will contain all FAs with in same orifice coefficients.

    Return
    ------
    faZonesForSafety : dict
        dictionary of zone name and list of FAs name in that zone

    Notes
    -----
    It separate oxide and LTA assembly into their own zones
    """
    runLog.extra("Building Zones by Orifice zone")
    orificeZones = Zones(core, cs)

    # first get all different orifice setting zones
    for a in core.getAssembliesOfType(Flags.FUEL):
        orificeSetting = "zone" + str(a.p.THorificeZone)
        b = a.getFirstBlock(Flags.FUEL)
        cFuel = b.getComponent(Flags.FUEL)
        fuelMaterial = cFuel.getProperties()
        if "lta" in a.getType():
            orificeSetting = "lta" + str((orificeSetting))
        elif "Oxide" in fuelMaterial.getName():
            orificeSetting = "Oxide" + str((orificeSetting))
        if orificeSetting not in orificeZones.names:
            orificeZones.add(Zone(orificeSetting))

    # now put FAs of the same orifice zone in to one channel
    for a in core.getAssembliesOfType(Flags.FUEL):
        orificeSetting = "zone" + str(a.p.THorificeZone)
        b = a.getFirstBlock(Flags.FUEL)
        cFuel = b.getComponent(Flags.FUEL)
        fuelMaterial = cFuel.getProperties()
        # get channel for lta
        if "lta" in a.getType():
            orificeZones["lta" + str(orificeSetting)].append(a.getLocation())
        # account for oxide fuel
        elif "Oxide" in fuelMaterial.getName():
            orificeZones["Oxide" + str(orificeSetting)].append(a.getLocation())
        # account for LTA
        else:
            orificeZones[orificeSetting].append(a.getLocation())

    return orificeZones


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


def _buildZonesforEachFA(core, cs):
    """
    Split every fuel assembly in to a zones for safety analysis.

    Returns
    ------
        reactorChannelZones : dict
            dictionary of each channel as a zone
    """
    runLog.extra("Creating zones for `everyFA`")
    reactorChannelZones = Zones(core, cs)
    for i, a in enumerate(core.getAssembliesOfType(Flags.FUEL)):
        reactorChannelZones.add(Zone("channel " + str(int(i) + 1), [a.getLocation()]))
    return reactorChannelZones


def _buildRingZoneZones(core, cs):
    """
    Build zones based on annular rings.

    Notes
    -----
    Originally, there were ringZones. These were defined by a user-input list of
    upper bound rings and the zones were just annular regions between rings.
    They were used to compute reactivity coefficients and whatnot. Then
    one day, it became clear that more general zones were required. To support
    old code that used ringZones, this code produces modern zones out
    of the ringZone input.

    It creates zones called ring-0, ring-1, etc. for each zone.

    If no zones are defined, one big ringzone comprising the whole core will be built.

    See Also
    --------
    getRingZoneAssemblies : gets assemblies in a ringzone
    getRingZoneRings : computes rings in a ringzone
    getAssembly : accesses assemblies in a zone the new way.

    """
    zones = Zones(core, cs)
    zoneRings = zones.getRingZoneRings()
    for ringZone, rings in enumerate(zoneRings, 1):
        zoneName = "ring-{0}".format(ringZone)
        zone = Zone(zoneName)
        for ring in rings:
            zone.addRing(ring)
        zones.add(zone)
    return zones


def _buildAssemTypeZones(core, cs, typeSpec=None):
    """
    Builds zones based on assembly type labels.

    Notes
    -----
    Creates a zone for each assembly type. All locations occupied by
    a certain type of assembly become a new zone based on that type.

    For example, after this call, all 'feed fuel a' assemblies will reside
    in the 'feed fuel a' zone.

    Useful for building static zones based on some BOL core layout.

    Parameters
    ----------
    core : Core
        The core
        
    typeSpec : Flags or list of Flags, optional
        Assembly types to consider (e.g. Flags.FUEL)

    Return
    ------
    zones : Zones
    """
    zones = Zones(core, cs)
    for a in core.getAssemblies(typeSpec):
        zoneName = a.getType()
        try:
            zone = zones[zoneName]
        except KeyError:
            zone = Zone(a.name)
            zones.add(zone)
        zone.append(a.getLocation())
    return zones


def splitZones(core, cs, zones):
    """
    Split the existing zone style into smaller zones via number of blocks and assembly type.

    Parameters
    ----------
    core:  Core
        The Core object to which the Zones belong
    cs: Case settings
        The case settings for the run
    zones: Zones
        The Zones to split

    Returns
    -------
    zones: Zones

    Notes
    -----
    Zones are collections of locations grouped by some user input.
    Calling this method transforms a collection of zones into another collection of zones
    further broken down by assembly type and number of blocks.
    Each new zone only contains assemblies of the same type and block count.
    any other arbitrary grouping method. A subZone is a further breakdown of a zone.

    Examples
    --------
    If the original zone was ringZone3 and ringZone3 contained three assemblies, one of them being a burner with
    nine blocks, one being a burner with 8 blocks and one control assembly with 3 blocks three splitZones
    would be produced and ringZone3 would be deleted. The the zones would be named ringZone3_Burner_8,
    ringZone3_Burner_9, ringZone3_Control_3.
    """

    if not cs["splitZones"]:
        return zones

    # We should make this unchangeable
    originalZoneNames = tuple([zone.name for zone in zones])
    splitZoneToOriginalZonesMap = {}
    subZoneNameSeparator = "-"
    for name in originalZoneNames:

        assems = core.getAssemblies(zones=name)
        for a in assems:
            # figure out what type of assembly we have
            flavor = a.getType().replace(" ", subZoneNameSeparator)  # replace spaces
            subZoneName = (
                name
                + subZoneNameSeparator
                + flavor
                + subZoneNameSeparator
                + str(len(a))
            )
            splitZoneToOriginalZonesMap[subZoneName] = name
            try:
                zone = zones[subZoneName]
            except KeyError:
                zone = Zone(subZoneName)
                zones.add(zone)
            zone.append(a.getLocation())
        # now remove the original non separated zone
        zones.removeZone(name)
    # Summarize the zone information
    headers = [
        "Zone\nNumber",
        "\nName",
        "Original\nName",
        "\nAssemblies",
        "\nLocations",
        "Symmetry\nFactor",
        "Hot\nZone",
    ]
    zoneSummaryData = []
    for zi, zone in enumerate(zones, 1):
        assemLocations = utils.createFormattedStrWithDelimiter(
            zone, maxNumberOfValuesBeforeDelimiter=6
        )
        zoneSummaryData.append(
            (
                zi,
                zone.name,
                splitZoneToOriginalZonesMap[zone.name],
                len(zone),
                assemLocations,
                zone.symmetry,
                zone.hotZone,
            )
        )
    runLog.info(
        "The setting `splitZones` is enabled. Building subzones from core zones:\n"
        + tabulate.tabulate(
            tabular_data=zoneSummaryData, headers=headers, tablefmt="armi"
        ),
        single=True,
    )
    return zones


def createHotZones(core, zones):
    """
    Make new zones from assemblies with the max power to flow ratio in a zone.

    Parameters
    ----------
    core : Core
        The core object
    zones: Zones
        Zones

    Returns
    -------
    zones: zones object

    Notes
    -----
    This method determines which assembly has the highest power to flow ratio in each zone.
    This method then removes that assembly from its original zone and places it in a new zone.
    """
    originalZoneNames = tuple([zone.name for zone in zones])
    for name in originalZoneNames:
        assems = core.getAssemblies(zones=name)
        # don't create hot zones from zones with only one assembly
        if len(assems) > 1:
            maxPOverF = 0.0
            hotLocation = ""
            for a in assems:
                # Check to make sure power and TH calcs were performed for this zon
                try:
                    pOverF = a.calcTotalParam("power") / a[-1].p.THmassFlowRate
                    loc = a.getLocation()
                    if pOverF >= maxPOverF:
                        maxPOverF = pOverF
                        hotLocation = loc
                except ZeroDivisionError:
                    runLog.warning(
                        "{} has no flow. Skipping {} in hot channel generation.".format(
                            a, name
                        )
                    )
                    break
            # If we were able to identify the hot location, create a hot zone.
            if hotLocation:
                zones[name].locList.remove(hotLocation)
                hotZoneName = "hot_" + name
                hotZone = Zone(hotZoneName)
                zones.add(hotZone)
                zones[hotZoneName].append(hotLocation)
                zones[hotZoneName].hotZone = True
                zones[hotZoneName].hostZone = name
            # Now remove the original zone if its does not store any locations anymore.
            if len(zones[name]) == 0:
                zones.removeZone(name)
    return zones
