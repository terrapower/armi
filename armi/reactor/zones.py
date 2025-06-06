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
A Zone object is a collection of locations in the Core.
A Zones object is a collection of Zone objects.
Together, they are used to conceptually divide the Core for analysis.
"""

from typing import Iterator, List, Optional, Set, Union

from armi import runLog
from armi.reactor.assemblies import Assembly
from armi.reactor.blocks import Block


class Zone:
    """
    A group of locations in the Core, used to divide it up for analysis.
    Each location represents an Assembly or a Block.

    .. impl:: A user can define a collection of armi locations.
        :id: I_ARMI_ZONE0
        :implements: R_ARMI_ZONE

        The Zone class facilitates the creation of a Zone object representing a collection of
        locations in the Core. A Zone contains a group of locations in the Core, used to subdivide
        it for analysis. Each location represents an Assembly or a Block, where a single Zone must
        contain items of the same type (i.e., Assembly or Block). Methods are provided to add or
        remove one or more locations to/from the Zone, and similarly, add or remove one or more
        items with a Core location (i.e., Assemblies or Blocks) to/from the Zone. In addition,
        several methods are provided to facilitate the retrieval of locations from a Zone by
        performing functions to check if a location exists in the Zone, looping through the
        locations in the Zone in alphabetical order, and returning the number of locations in the
        Zone, etc.
    """

    VALID_TYPES = (Assembly, Block)

    def __init__(self, name: str, locations: Optional[List] = None, zoneType: type = Assembly):
        self.name = name

        # A single Zone must contain items of the same type
        if zoneType not in Zone.VALID_TYPES:
            raise TypeError("Invalid Type {0}; A Zone can only be of type {1}".format(zoneType, Zone.VALID_TYPES))
        self.zoneType = zoneType

        # a Zone is mostly just a collection of locations in the Reactor
        if locations is None:
            self.locs = set()
        else:
            # NOTE: We are not validating the locations.
            self.locs = set(locations)

    def __contains__(self, loc: str) -> bool:
        return loc in self.locs

    def __iter__(self) -> Iterator[str]:
        """Loop through the locations, in alphabetical order."""
        for loc in sorted(self.locs):
            yield loc

    def __len__(self) -> int:
        """Return the number of locations."""
        return len(self.locs)

    def __repr__(self) -> str:
        zType = "Assemblies"
        if self.zoneType == Block:
            zType = "Blocks"

        return "<Zone {0} with {1} {2}>".format(self.name, len(self), zType)

    def addLoc(self, loc: str) -> None:
        """
        Adds the location to this Zone.

        Parameters
        ----------
        loc : str
            Location within the Core.

        Notes
        -----
        This method does not validate that the location given is somehow "valid". We are not doing
        any reverse lookups in the Reactor to prove that the type or location is valid. Because this
        would require heavier computation, and would add some chicken-and-the-egg problems into
        instantiating a new Reactor.
        """
        assert isinstance(loc, str), "The location must be a str: {0}".format(loc)
        self.locs.add(loc)

    def removeLoc(self, loc: str) -> None:
        """
        Removes the location from this Zone.

        Parameters
        ----------
        loc : str
            Location within the Core.

        Notes
        -----
        This method does not validate that the location given is somehow "valid".
        We are not doing any reverse lookups in the Reactor to prove that the type
        or location is valid. Because this would require heavier computation, and
        would add some chicken-and-the-egg problems into instantiating a new Reactor.

        Returns
        -------
        None
        """
        assert isinstance(loc, str), "The location must be a str: {0}".format(loc)
        self.locs.remove(loc)

    def addLocs(self, locs: List) -> None:
        """
        Adds the locations to this Zone.

        Parameters
        ----------
        items : list
            List of str objects
        """
        for loc in locs:
            self.addLoc(loc)

    def removeLocs(self, locs: List) -> None:
        """
        Removes the locations from this Zone.

        Parameters
        ----------
        items : list
            List of str objects
        """
        for loc in locs:
            self.removeLoc(loc)

    def addItem(self, item: Union[Assembly, Block]) -> None:
        """
        Adds the location of an Assembly or Block to a zone.

        Parameters
        ----------
        item : Assembly or Block
            A single item with Core location (Assembly or Block)
        """
        assert issubclass(type(item), self.zoneType), "The item ({0}) but be have a type in: {1}".format(
            item, Zone.VALID_TYPES
        )
        self.addLoc(item.getLocation())

    def removeItem(self, item: Union[Assembly, Block]) -> None:
        """
        Removes the location of an Assembly or Block from a zone.

        Parameters
        ----------
        item : Assembly or Block
            A single item with Core location (Assembly or Block)
        """
        assert issubclass(type(item), self.zoneType), "The item ({0}) but be have a type in: {1}".format(
            item, Zone.VALID_TYPES
        )
        self.removeLoc(item.getLocation())

    def addItems(self, items: List) -> None:
        """
        Adds the locations of a list of Assemblies or Blocks to a zone.

        Parameters
        ----------
        items : list
            List of Assembly/Block objects
        """
        for item in items:
            self.addItem(item)

    def removeItems(self, items: List) -> None:
        """
        Removes the locations of a list of Assemblies or Blocks from a zone.

        Parameters
        ----------
        items : list
            List of Assembly/Block objects
        """
        for item in items:
            self.removeItem(item)


class Zones:
    """Collection of Zone objects.

    .. impl:: A user can define a collection of armi zones.
        :id: I_ARMI_ZONE1
        :implements: R_ARMI_ZONE

        The Zones class facilitates the creation of a Zones object representing a collection of Zone
        objects. Methods are provided to add or remove one or more Zone to/from the Zones object.
        Likewise, methods are provided to validate that the zones are mutually exclusive, obtain the
        location labels of zones, return the Zone object where a particular Assembly or Block
        resides, sort the Zone objects alphabetically, and summarize the zone definitions. In
        addition, methods are provided to facilitate the retrieval of Zone objects by name, loop
        through the Zones in order, and return the number of Zone objects.
    """

    def __init__(self):
        """Build a Zones object."""
        self._zones = {}

    @property
    def names(self) -> List:
        """Ordered names of contained zones.

        Returns
        -------
        list
            Alphabetical collection of Zone names
        """
        return sorted(self._zones.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._zones

    def __delitem__(self, name: str) -> None:
        del self._zones[name]

    def __getitem__(self, name: str) -> Zone:
        """Access a zone by name."""
        return self._zones[name]

    def __iter__(self) -> Iterator[Zone]:
        """Loop through the zones in order."""
        for nm in sorted(self._zones.keys()):
            yield self._zones[nm]

    def __len__(self) -> int:
        """Return the number of Zone objects."""
        return len(self._zones)

    def addZone(self, zone: Zone) -> None:
        """Add a zone to the collection.

        Parameters
        ----------
        zone: Zone
            A new Zone to add to this collection.
        """
        if zone.name in self._zones:
            raise ValueError("Cannot add {} because a zone of that name already exists.".format(zone.name))
        self._zones[zone.name] = zone

    def addZones(self, zones: List) -> None:
        """
        Add multiple zones to the collection, and validate the Zones collection still make sense.

        Parameters
        ----------
        zones: List (or Zones)
            A multiple new Zone objects to add to this collection.
        """
        for zone in zones:
            self.addZone(zone)

        self.checkDuplicates()

    def removeZone(self, name: str) -> None:
        """Delete a zone by name.

        Parameters
        ----------
        name: str
            Name of zone to remove
        """
        del self[name]

    def removeZones(self, names: List) -> None:
        """
        Delete multiple zones by name.

        Parameters
        ----------
        names: List (or names)
            Multiple Zone names to remove from this collection.
        """
        for name in names:
            self.removeZone(name)

    def checkDuplicates(self) -> None:
        """
        Validate that the zones are mutually exclusive.

        That is, make sure that no item appears in more than one Zone.
        """
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

    def getZoneLocations(self, zoneNames: List) -> Set:
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
                runLog.error("The zone {0} does not exist. Please define it.".format(zn))
                raise
            zoneLocs.update(thisZoneLocs)

        return zoneLocs

    def getAllLocations(self) -> Set:
        """Return all locations across every Zone in this Zones object.

        Returns
        -------
        set
            A combination set of all locations, from every Zone
        """
        locs = set()
        for zone in self:
            locs.update(self[zone.name])

        return locs

    def findZoneItIsIn(self, a: Union[Assembly, Block]) -> Optional[Zone]:
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
            runLog.debug(f"Was not able to find which zone {a} is in", single=True)

        return None

    def sortZones(self, reverse=False) -> None:
        """Sorts the Zone objects alphabetically.

        Parameters
        ----------
        reverse : bool, optional
            Whether to sort in reverse order, by default False
        """
        self._zones = dict(sorted(self._zones.items(), reverse=reverse))

    def summary(self) -> None:
        """
        Summarize the zone definitions clearly, and in a way that can be copy/pasted
        back into a settings file under "zoneDefinitions", if the user wants to
        manually reuse these zones later.

        Examples
        --------
            zoneDefinitions:
            - ring-1: 001-001
            - ring-2: 002-001, 002-002
            - ring-3: 003-001, 003-002, 003-003
        """
        # log a quick header
        runLog.info("zoneDefinitions:")

        # log the zone definitions in a way that can be copy/pasted back into a settings file
        for name in sorted(self._zones.keys()):
            locs = sorted(self._zones[name].locs)
            line = "- {0}: ".format(name) + ", ".join(locs)
            runLog.info(line)
