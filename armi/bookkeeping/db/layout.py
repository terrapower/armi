# Copyright 2022 TerraPower, LLC
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
Groundwork for ARMI Database, version 3.4.

When interacting with the database file, the :py:class:`Layout` class is used to help
map the hierarchical Composite Reactor Model to the flat representation in
:py:class:`Database <armi.bookkeeping.db.database.Database>`.

This module also stores packing/packing tools to support
:py:class:`Database <armi.bookkeeping.db.database.Database>`, as well as database
versioning information.
"""

import collections
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
)

import numpy as np

from armi import runLog
from armi.reactor import grids
from armi.reactor.components import Component
from armi.reactor.composites import ArmiObject
from armi.reactor.excoreStructure import ExcoreStructure
from armi.reactor.reactors import Core, Reactor

# Here we store the Database version information.
DB_MAJOR = 3
DB_MINOR = 4
DB_VERSION = f"{DB_MAJOR}.{DB_MINOR}"

# CONSTANTS USED TO PACK AND UNPACK DATA
LOC_NONE = "N"
LOC_COORD = "C"
LOC_INDEX = "I"
LOC_MULTI = "M:"

LOCATION_TYPE_LABELS = {
    type(None): LOC_NONE,
    grids.CoordinateLocation: LOC_COORD,
    grids.IndexLocation: LOC_INDEX,
    grids.MultiIndexLocation: LOC_MULTI,
}

# NOTE: Here we assume no one assigns min(int)+2 as a meaningful value
NONE_MAP = {float: float("nan"), str: "<!None!>"}
NONE_MAP.update(
    {
        intType: np.iinfo(intType).min + 2
        for intType in (
            int,
            np.int8,
            np.int16,
            np.int32,
            np.int64,
        )
    }
)
NONE_MAP.update(
    {
        intType: np.iinfo(intType).max - 2
        for intType in (
            np.uint,
            np.uint8,
            np.uint16,
            np.uint32,
            np.uint64,
        )
    }
)
NONE_MAP.update({floatType: floatType("nan") for floatType in (float, np.float64)})


class Layout:
    """
    The Layout class describes the hierarchical layout of the Composite Reactor model
    in a flat representation for
    :py:class:`Database <armi.bookkeeping.db.database.Database>`.

    A Layout is built by starting at the root of a composite tree and recursively
    appending each node in the tree to a list of data. So the data will be ordered by
    depth-first search: [r, c, a1, a1b1, a1b1c1, a1b1c2, a1b2, a1b2c1, ..., a2, ...].

    The layout is also responsible for storing Component attributes, like location,
    material, and temperatures, which aren't stored as Parameters. Temperatures,
    specifically, are rather complicated in ARMI.

    Notes
    -----
     * Elements in Layout are stored in depth-first order. This permits use of
       algorithms such as Pre-Order Tree Traversal for efficient traversal of regions
       of the model.

     * ``indexInData`` increases monotonically within each object ``type``. For
       example, the data for all ``HexBlock`` children of a given parent are stored
       contiguously within the ``HexBlock`` group, and will not be interleaved with
       data from the ``HexBlock`` children of any of the parent's siblings.

     * Aside from the hierarchy, there is no guarantee what order objects are stored
       in the layout.  The ``Core`` is not necessarily the first child of the
       ``Reactor``, and is not guaranteed to use the zeroth grid.
    """

    def __init__(self, version: Tuple[int, int], h5group=None, comp=None):
        self.type: List[str] = []
        self.name: List[str] = []
        self.serialNum: List[int] = []
        # The index into the parameter datasets corresponding to each object's class.
        # E.g., the 5th HexBlock object in the tree would get 5; to look up its
        # "someParameter" value, you would extract cXXnYY/HexBlock/someParameter[5].
        self.indexInData: List[int] = []
        # The number of direct children this object has.
        self.numChildren: List[int] = []
        # The type of location that specifies the object's physical location; see the
        # associated pack/unpackLocation functions for more information about how
        # locations are handled.
        self.locationType: List[str] = []
        # There is a minor asymmetry here in that before writing to the DB, this is
        # truly a flat list of tuples. However when reading, this may contain lists of
        # tuples, which represent MI locations. This comes from the fact that we map the
        # tuples to Location objects in Database._compose, but map from Locations to
        # tuples in Layout._createLayout. Ideally we would handle both directions in the
        # same place so this can be less surprising. Resolving this would require
        # changing the interface of the various pack/unpack functions, which have
        # multiple versions, so the update would need to be done with care.
        self.location: List[Tuple[int, int, int]] = []
        # Which grid, as stored in the database, this object uses to arrange its
        # children
        self.gridIndex: List[int] = []
        self.temperatures: List[float] = []
        self.material: List[str] = []
        # Used to cache all of the spatial locators so that we can pack them all at
        # once. The benefit here is that the version checking can happen up front and
        # less branching down below
        self._spatialLocators: List[grids.LocationBase] = []
        # set of grid parameters that have been seen in _createLayout. For efficient
        # checks for uniqueness
        self._seenGridParams: Dict[Any, Any] = dict()
        # actual list of grid parameters, with stable order for safe indexing
        self.gridParams: List[Any] = []
        self.version = version

        self.groupedComps: Dict[Type[ArmiObject], List[ArmiObject]] = collections.defaultdict(list)

        # it should be noted, one of the two inputs must be non-None: comp/h5group
        if comp is not None:
            self._createLayout(comp)
            self.locationType, self.location = _packLocations(self._spatialLocators)
        else:
            self._readLayout(h5group)

        self._snToLayoutIndex = {sn: i for i, sn in enumerate(self.serialNum)}

        # find all subclasses of Grid
        self.gridClasses = {c.__name__: c for c in Layout.allSubclasses(grids.Grid)}
        self.gridClasses["Grid"] = grids.Grid

    def __getitem__(self, sn):
        layoutIndex = self._snToLayoutIndex[sn]
        return (
            self.type[layoutIndex],
            self.name[layoutIndex],
            self.serialNum[layoutIndex],
            self.indexInData[layoutIndex],
            self.numChildren[layoutIndex],
            self.locationType[layoutIndex],
            self.location[layoutIndex],
            self.temperatures[layoutIndex],
            self.material[layoutIndex],
        )

    def _createLayout(self, comp):
        """
        Populate a hierarchical representation and group the reactor model items by type.

        This is used when writing a reactor model to the database.

        Notes
        -----
        This is recursive.

        See Also
        --------
        _readLayout : does the opposite
        """
        compList = self.groupedComps[type(comp)]
        compList.append(comp)

        self.type.append(comp.__class__.__name__)
        self.name.append(comp.name)
        self.serialNum.append(comp.p.serialNum)
        self.indexInData.append(len(compList) - 1)
        self.numChildren.append(len(comp))

        # determine how many components have been read in, to set the grid index
        if comp.spatialGrid is not None:
            gridType = type(comp.spatialGrid).__name__
            gridParams = (gridType, comp.spatialGrid.reduce())
            if gridParams not in self._seenGridParams:
                self._seenGridParams[gridParams] = len(self.gridParams)
                self.gridParams.append(gridParams)
            self.gridIndex.append(self._seenGridParams[gridParams])
        else:
            self.gridIndex.append(None)

        self._spatialLocators.append(comp.spatialLocator)

        # set the materials and temperatures
        try:
            self.temperatures.append((comp.inputTemperatureInC, comp.temperatureInC))
            self.material.append(comp.material.__class__.__name__)
        except Exception:
            self.temperatures.append((-900, -900))  # an impossible temperature
            self.material.append("")

        try:
            comps = sorted(list(comp))
        except ValueError:
            runLog.error(
                "Failed to sort some collection of ArmiObjects for database output: {} value {}".format(
                    type(comp), list(comp)
                )
            )
            raise

        # depth-first search recursion of all components
        for c in comps:
            self._createLayout(c)

    def _readLayout(self, h5group):
        """
        Populate a hierarchical representation and group the reactor model items by type.

        This is used when reading a reactor model from a database.

        See Also
        --------
        _createLayout : does the opposite
        """
        try:
            # location is either an index, or a point
            # iter over list is faster
            locations = h5group["layout/location"][:].tolist()
            self.locationType = np.char.decode(h5group["layout/locationType"][:]).tolist()
            self.location = _unpackLocations(self.locationType, locations, self.version[1])
            self.type = np.char.decode(h5group["layout/type"][:])
            self.name = np.char.decode(h5group["layout/name"][:])
            self.serialNum = h5group["layout/serialNum"][:]
            self.indexInData = h5group["layout/indexInData"][:]
            self.numChildren = h5group["layout/numChildren"][:]
            self.material = np.char.decode(h5group["layout/material"][:])
            self.temperatures = h5group["layout/temperatures"][:]
            self.gridIndex = replaceNonsenseWithNones(h5group["layout/gridIndex"][:], "layout/gridIndex")

            gridGroup = h5group["layout/grids"]
            gridTypes = [t.decode() for t in gridGroup["type"][:]]

            self.gridParams = []
            for iGrid, gridType in enumerate(gridTypes):
                thisGroup = gridGroup[str(iGrid)]

                unitSteps = thisGroup["unitSteps"][:]
                bounds = []
                for ibound in range(3):
                    boundName = "bounds_{}".format(ibound)
                    if boundName in thisGroup:
                        bounds.append(thisGroup[boundName][:])
                    else:
                        bounds.append(None)
                unitStepLimits = thisGroup["unitStepLimits"][:]
                offset = thisGroup["offset"][:] if thisGroup.attrs["offset"] else None
                geomType = thisGroup["geomType"].asstr()[()] if "geomType" in thisGroup else None
                symmetry = thisGroup["symmetry"].asstr()[()] if "symmetry" in thisGroup else None

                self.gridParams.append(
                    (
                        gridType,
                        grids.GridParameters(
                            unitSteps,
                            bounds,
                            unitStepLimits,
                            offset,
                            geomType,
                            symmetry,
                        ),
                    )
                )

        except KeyError as e:
            runLog.error("Failed to get layout information from group: {}".format(h5group.name))
            raise e

    def _initComps(self, caseTitle, bp):
        comps = []
        groupedComps = collections.defaultdict(list)

        for (
            compType,
            name,
            serialNum,
            numChildren,
            location,
            material,
            temperatures,
            gridIndex,
        ) in zip(
            self.type,
            self.name,
            self.serialNum,
            self.numChildren,
            self.location,
            self.material,
            self.temperatures,
            self.gridIndex,
        ):
            Klass = ArmiObject.TYPES[compType]

            if issubclass(Klass, Reactor):
                comp = Klass(caseTitle, bp)
            elif issubclass(Klass, Core):
                comp = Klass(name)
            elif issubclass(Klass, ExcoreStructure):
                comp = Klass(name)
            elif issubclass(Klass, Component):
                # init all dimensions to 0, they will be loaded and assigned after load
                kwargs = dict.fromkeys(Klass.DIMENSION_NAMES, 0)
                kwargs["material"] = material
                kwargs["name"] = name
                kwargs["Tinput"] = temperatures[0]
                kwargs["Thot"] = temperatures[1]
                comp = Klass(**kwargs)
            else:
                comp = Klass(name)

            if gridIndex is not None:
                gridParams = self.gridParams[gridIndex]
                comp.spatialGrid = self.gridClasses[gridParams[0]](*gridParams[1], armiObject=comp)

            comps.append((comp, serialNum, numChildren, location))
            groupedComps[compType].append(comp)

        return comps, groupedComps

    def writeToDB(self, h5group):
        """Write a chunk of data to the database.

        .. impl:: Write data to the DB for a given time step.
            :id: I_ARMI_DB_TIME0
            :implements: R_ARMI_DB_TIME

            This method writes a snapshot of the current state of the reactor to the
            database. It takes a pointer to an existing HDF5 file as input, and it
            writes the reactor data model to the file in depth-first search order.
            Other than this search order, there are no guarantees as to what order the
            objects are written to the file. Though, this turns out to still be very
            powerful. For instance, the data for all ``HexBlock`` children of a given
            parent are stored contiguously within the ``HexBlock`` group, and will not
            be interleaved with data from the ``HexBlock`` children of any of the parent's siblings.
        """
        if "layout/type" in h5group:
            # It looks like we have already written the layout to DB, skip for now
            return
        try:
            h5group.create_dataset(
                "layout/type",
                data=np.array(self.type).astype("S"),
                compression="gzip",
            )
            h5group.create_dataset(
                "layout/name",
                data=np.array(self.name).astype("S"),
                compression="gzip",
            )
            h5group.create_dataset("layout/serialNum", data=self.serialNum, compression="gzip")
            h5group.create_dataset("layout/indexInData", data=self.indexInData, compression="gzip")
            h5group.create_dataset(
                "layout/numChildren",
                data=self.numChildren,
                compression="gzip",
                track_order=True,
            )
            h5group.create_dataset(
                "layout/location",
                data=self.location,
                compression="gzip",
                track_order=True,
            )
            h5group.create_dataset(
                "layout/locationType",
                data=np.array(self.locationType).astype("S"),
                compression="gzip",
                track_order=True,
            )
            h5group.create_dataset(
                "layout/material",
                data=np.array(self.material).astype("S"),
                compression="gzip",
                track_order=True,
            )
            h5group.create_dataset(
                "layout/temperatures",
                data=self.temperatures,
                compression="gzip",
                track_order=True,
            )

            h5group.create_dataset(
                "layout/gridIndex",
                data=replaceNonesWithNonsense(np.array(self.gridIndex), "layout/gridIndex"),
                compression="gzip",
            )

            gridsGroup = h5group.create_group("layout/grids", track_order=True)
            gridsGroup.attrs["nGrids"] = len(self.gridParams)
            gridsGroup.create_dataset(
                "type",
                data=np.array([gp[0] for gp in self.gridParams]).astype("S"),
                track_order=True,
            )

            for igrid, gridParams in enumerate(gp[1] for gp in self.gridParams):
                thisGroup = gridsGroup.create_group(str(igrid), track_order=True)
                thisGroup.create_dataset("unitSteps", data=gridParams.unitSteps, track_order=True)

                for ibound, bound in enumerate(gridParams.bounds):
                    if bound is not None:
                        bound = np.array(bound)
                        thisGroup.create_dataset("bounds_{}".format(ibound), data=bound, track_order=True)

                thisGroup.create_dataset("unitStepLimits", data=gridParams.unitStepLimits, track_order=True)

                offset = gridParams.offset
                thisGroup.attrs["offset"] = offset is not None
                if offset is not None:
                    thisGroup.create_dataset("offset", data=offset, track_order=True)
                thisGroup.create_dataset("geomType", data=gridParams.geomType, track_order=True)
                thisGroup.create_dataset("symmetry", data=gridParams.symmetry, track_order=True)
        except RuntimeError:
            runLog.error("Failed to create datasets in: {}".format(h5group))
            raise

    @staticmethod
    def computeAncestors(serialNum, numChildren, depth=1) -> List[Optional[int]]:
        """
        Return a list containing the serial number of the parent corresponding to each
        object at the given depth.

        Depth in this case means how many layers to reach up to find the desired
        ancestor. A depth of 1 will yield the direct parent of each element, depth of 2
        would yield the elemen's parent's parent, and so on.

        The zero-th element will always be None, as the first object is the root element
        and so has no parent. Subsequent depths will result in more Nones.

        This function is useful for forming a lightweight sense of how the database
        contents stitch together, without having to go to the trouble of fully unpacking
        the Reactor model.

        Parameters
        ----------
        serialNum : List of int
            List of serial numbers for each object/element, as laid out in Layout
        numChildren : List of int
            List of numbers of children for each object/element, as laid out in Layout

        Note
        ----
        This is not using a recursive approach for a couple of reasons. First, the
        iterative form isn't so bad; we just need two stacks. Second, the interface of
        the recursive function would be pretty unwieldy. We are progressively
        consuming two lists, of which we would need to keep passing down with an
        index/cursor, or progressively slice them as we go, which would be pretty
        inefficient.
        """
        ancestors: List[Optional[int]] = [None]

        snStack = [serialNum[0]]
        ncStack = [numChildren[0]]

        for sn, nc in zip(serialNum[1:], numChildren[1:]):
            ncStack[-1] -= 1
            if nc > 0:
                ancestors.append(snStack[-1])
                snStack.append(sn)
                ncStack.append(nc)
            else:
                ancestors.append(snStack[-1])

            while ncStack and ncStack[-1] == 0:
                snStack.pop()
                ncStack.pop()

        if depth > 1:
            # handle deeper scenarios. This is a bit tricky. Store the original
            # ancestors for the first generation, since that ultimately contains all of
            # the information that we need. Then in a loop, keep hopping one more layer
            # of indirection, and indexing into the corresponding location in the
            # original ancestor array
            indexMap = {sn: i for i, sn in enumerate(serialNum)}
            origAncestors = ancestors
            for _ in range(depth - 1):
                ancestors = [origAncestors[indexMap[ia]] if ia is not None else None for ia in ancestors]

        return ancestors

    @staticmethod
    def allSubclasses(cls) -> set:
        """Find all subclasses of the given class, in any namespace."""
        return set(cls.__subclasses__()).union([s for c in cls.__subclasses__() for s in Layout.allSubclasses(c)])


def _packLocations(
    locations: List[grids.LocationBase], minorVersion: int = DB_MINOR
) -> Tuple[List[str], List[Tuple[int, int, int]]]:
    """
    Extract information from a location needed to write it to this DB.

    Each locator has one locationType and up to N location-defining datums,
    where N is the number of entries in a possible multiindex, or just 1
    for everything else.

    Shrink grid locator names for storage efficiency.

    Notes
    -----
    Contains some conditionals to still load databases made before
    db version 3.3 which can be removed once no users care about
    those DBs anymore.
    """
    if minorVersion <= 2:
        locationTypes, locationData = _packLocationsV1(locations)
    elif minorVersion == 3:
        locationTypes, locationData = _packLocationsV2(locations)
    elif minorVersion > 3:
        locationTypes, locationData = _packLocationsV3(locations)
    else:
        raise ValueError("Unsupported minor version: {}".format(minorVersion))
    return locationTypes, locationData


def _packLocationsV1(
    locations: List[grids.LocationBase],
) -> Tuple[List[str], List[Tuple[int, int, int]]]:
    """Delete when reading v <=3.2 DB's no longer wanted."""
    locTypes = []
    locData: List[Tuple[int, int, int]] = []
    for loc in locations:
        locationType = loc.__class__.__name__
        if loc is None:
            locationType = "None"
            locDatum = [(0.0, 0.0, 0.0)]
        elif isinstance(loc, grids.IndexLocation):
            locDatum = [loc.indices]
        else:
            raise ValueError(f"Invalid location type: {loc}")

        locTypes.append(locationType)
        locData.extend(locDatum)

    return locTypes, locData


def _packLocationsV2(
    locations: List[grids.LocationBase],
) -> Tuple[List[str], List[Tuple[int, int, int]]]:
    """Location packing implementation for minor version 3. See module docstring above."""
    locTypes = []
    locData: List[Tuple[int, int, int]] = []
    for loc in locations:
        locationType = LOCATION_TYPE_LABELS[type(loc)]
        if loc is None:
            locDatum = [(0.0, 0.0, 0.0)]
        elif loc.__class__ is grids.CoordinateLocation:
            locDatum = [loc.indices]
        elif loc.__class__ is grids.IndexLocation:
            locDatum = [loc.indices]
        elif loc.__class__ is grids.MultiIndexLocation:
            # encode number of sub-locations to allow in-line unpacking.
            locationType += f"{len(loc)}"
            locDatum = [subloc.indices for subloc in loc]
        else:
            raise ValueError(f"Invalid location type: {loc}")

        locTypes.append(locationType)
        locData.extend(locDatum)

    return locTypes, locData


def _packLocationsV3(
    locations: List[grids.LocationBase],
) -> Tuple[List[str], List[Tuple[int, int, int]]]:
    """Location packing implementation for minor version 4. See module docstring above."""
    locTypes = []
    locData: List[Tuple[int, int, int]] = []

    for loc in locations:
        locationType = LOCATION_TYPE_LABELS[type(loc)]
        if loc is None:
            locDatum = [(0.0, 0.0, 0.0)]
        elif type(loc) is grids.IndexLocation:
            locDatum = [loc.getCompleteIndices()]
        elif type(loc) is grids.CoordinateLocation:
            # CoordinateLocations do not implement getCompleteIndices properly, and we
            # do not really have a motivation to store them as we do with index
            # locations.
            locDatum = [loc.indices]
        elif type(loc) is grids.MultiIndexLocation:
            locationType += f"{len(loc)}"
            locDatum = [subloc.indices for subloc in loc]
        else:
            raise ValueError(f"Invalid location type: {loc}")

        locTypes.append(locationType)
        locData.extend(locDatum)

    return locTypes, locData


def _unpackLocations(locationTypes, locData, minorVersion: int = DB_MINOR):
    """
    Convert location data as read from DB back into data structure for building reactor model.

    location and locationType will only have different lengths when multiindex locations
    are used.
    """
    if minorVersion < 3:
        return _unpackLocationsV1(locationTypes, locData)
    else:
        return _unpackLocationsV2(locationTypes, locData)


def _unpackLocationsV1(locationTypes, locData):
    """Delete when reading v <=3.2 DB's no longer wanted."""
    locsIter = iter(locData)
    unpackedLocs = []
    for lt in locationTypes:
        if lt == "None":
            loc = next(locsIter)
            unpackedLocs.append(None)
        elif lt == "IndexLocation":
            loc = next(locsIter)
            # the data is stored as float, so cast back to int
            unpackedLocs.append(tuple(int(i) for i in loc))
        else:
            loc = next(locsIter)
            unpackedLocs.append(tuple(loc))
    return unpackedLocs


def _unpackLocationsV2(locationTypes, locData):
    """Location unpacking implementation for minor version 3+. See module docstring above."""
    locsIter = iter(locData)
    unpackedLocs = []
    for lt in locationTypes:
        if lt == LOC_NONE:
            loc = next(locsIter)
            unpackedLocs.append(None)
        elif lt == LOC_INDEX:
            loc = next(locsIter)
            # the data is stored as float, so cast back to int
            unpackedLocs.append(tuple(int(i) for i in loc))
        elif lt == LOC_COORD:
            loc = next(locsIter)
            unpackedLocs.append(tuple(loc))
        elif lt.startswith(LOC_MULTI):
            # extract number of sublocations from e.g. "M:345" string.
            numSubLocs = int(lt.split(":")[1])
            multiLocs = []
            for _ in range(numSubLocs):
                subLoc = next(locsIter)
                # All multiindexes sublocs are index locs
                multiLocs.append(tuple(int(i) for i in subLoc))
            unpackedLocs.append(multiLocs)
        else:
            raise ValueError(f"Read unknown location type {lt}. Invalid DB.")

    return unpackedLocs


def replaceNonesWithNonsense(data: np.ndarray, paramName: str, nones: np.ndarray = None) -> np.ndarray:
    """
    Replace instances of ``None`` with nonsense values that can be detected/recovered
    when reading.

    Parameters
    ----------
    data
        The numpy array containing ``None`` values that need to be replaced.

    paramName
        The name of the parameter who's data we are treating. Only used for diagnostics.

    nones
        An array containing the index locations on the ``None`` elements. It is a little
        strange to pass these, in but we find these indices to determine whether we need
        to call this function in the first place, so might as well pass it in, so that
        we don't need to perform the operation again.

    Notes
    -----
    This only supports situations where the data is a straight-up ``None``, or a valid,
    database-storable numpy array (or easily convertible to one (e.g. tuples/lists with
    numerical values)). This does not support, for instance, a numpy ndarray with some
    Nones in it.

    For example, the following is supported::

        [[1, 2, 3], None, [7, 8, 9]]

    However, the following is not::

        [[1, 2, 3], [4, None, 6], [7, 8, 9]]

    See Also
    --------
    replaceNonsenseWithNones
        Reverses this operation.
    """
    if nones is None:
        nones = np.where([d is None for d in data])[0]

    try:
        # loop to find what the default value should be. This is the first non-None
        # value that we can find.
        defaultValue = None
        realType = None
        val = None

        for val in data:
            if isinstance(val, np.ndarray):
                # if multi-dimensional, val[0] could still be an array, val.flat is
                # a flattened iterator, so next(val.flat) gives the first value in
                # an n-dimensional array
                realType = type(next(val.flat))

                if realType is type(None):
                    continue

                defaultValue = np.reshape(np.repeat(NONE_MAP[realType], val.size), val.shape)
                break
            else:
                realType = type(val)

                if realType is type(None):
                    continue

                defaultValue = NONE_MAP[realType]
                break
        else:
            # Couldn't find any non-None entries, so it really doesn't matter what type we
            # use. Using float, because NaN is nice.
            realType = float
            defaultValue = NONE_MAP[realType]

        if isinstance(val, np.ndarray):
            data = np.array([d if d is not None else defaultValue for d in data])
        else:
            data[nones] = defaultValue

    except Exception as ee:
        runLog.error(
            "Error while attempting to determine default for {}.\nvalue: {}\nError: {}".format(paramName, val, ee)
        )
        raise TypeError(
            "Could not determine None replacement for {} with type {}, val {}, default {}".format(
                paramName, realType, val, defaultValue
            )
        )

    try:
        data = data.astype(realType)
    except Exception:
        raise ValueError("Could not coerce data for {} to {}, data:\n{}".format(paramName, realType, data))

    if data.dtype.kind == "O":
        raise TypeError("Failed to convert data to valid HDF5 type {}, data:{}".format(paramName, data))

    return data


def replaceNonsenseWithNones(data: np.ndarray, paramName: str) -> np.ndarray:
    """
    Replace special nonsense values with ``None``.

    This essentially reverses the operations performed by
    :py:func:`replaceNonesWithNonsense`.

    Parameters
    ----------
    data
        The array from the database that contains special ``None`` nonsense values.

    paramName
        The param name who's data we are dealing with. Only used for diagnostics.

    See Also
    --------
    replaceNonesWithNonsense
    """
    # NOTE: This is closely-related to the NONE_MAP.
    if np.issubdtype(data.dtype, np.floating):
        isNone = np.isnan(data)
    elif np.issubdtype(data.dtype, np.integer):
        isNone = data == np.iinfo(data.dtype).min + 2
    elif np.issubdtype(data.dtype, np.str_):
        isNone = data == "<!None!>"
    else:
        raise TypeError("Unable to resolve values that should be None for `{}`".format(paramName))

    if data.ndim > 1:
        result = np.ndarray(data.shape[0], dtype=np.dtype("O"))
        for i in range(data.shape[0]):
            if isNone[i].all():
                result[i] = None
            elif isNone[i].any():
                # This is the meat of the logic to replace "nonsense" with None.
                result[i] = np.array(data[i], dtype=np.dtype("O"))
                result[i][isNone[i]] = None
            else:
                result[i] = data[i]
    else:
        result = np.ndarray(data.shape, dtype=np.dtype("O"))
        result[:] = data
        result[isNone] = None

    return result
