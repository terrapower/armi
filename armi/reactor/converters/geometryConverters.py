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
Change a reactor from one geometry to another.

Examples may include going from Hex to R-Z or from Third-core to full core.
This module contains **converters** (which create new reactor objects with different geometry),
and **changers** (which modify a given reactor in place) in this module.
"""
import collections
import copy
import math

import matplotlib
import matplotlib.pyplot as plt
import numpy

from armi import materials
from armi import runLog
from armi.reactor import assemblies
from armi.reactor import blocks
from armi.reactor import components
from armi.reactor import locations
from armi.reactor import reactors
from armi.reactor import parameters
from armi.reactor.parameters import Category
from armi.reactor.parameters import ParamLocation
from armi.reactor.parameters import NEVER
from armi.reactor.parameters import SINCE_LAST_GEOMETRY_TRANSFORMATION
from armi.reactor import geometry
from armi.reactor.converters import meshConverters
from armi.utils import plotting
from armi.utils import units
from armi.reactor import grids
from armi.reactor.flags import Flags
from armi.utils import hexagon
from armi.reactor.converters import blockConverters

BLOCK_AXIAL_MESH_SPACING = (
    20  # Block axial mesh spacing set for nodal diffusion calculation (cm)
)
STR_SPACE = " "


class GeometryChanger(object):
    """Geometry changer class that updates the geometry (number of assems or blocks per assem) of a given reactor."""

    def __init__(self, cs=None, quiet=False):
        self._newAssembliesAdded = []
        self._sourceReactor = None
        self._cs = cs
        self._assemblyModuleCounter = assemblies.getAssemNum()
        if not quiet:
            self._writeAssemblyModuleCounter()

    def __repr__(self):
        return "<{}>".format(self.__class__.__name__)

    def getNewAssembliesAdded(self):
        return self._newAssembliesAdded

    def getAssemblyModuleCounter(self):
        return self._assemblyModuleCounter

    def _writeAssemblyModuleCounter(self):
        runLog.debug(
            "Assembly Module Counter is {}".format(self._assemblyModuleCounter)
        )

    def convert(self, r=None):
        """
        Run the conversion.

        Parameters
        ----------
        cs : CaseSettings object
            CaseSettings associated with a specific reactor
        sourceReactor : Reactor object
            The reactor to convert.

        Returns
        -------
        convReactor : Reactor object
            the converted reactor (converters only, not changers)

        """
        raise NotImplementedError


class GeometryConverter(GeometryChanger):
    """
    Base class for GeometryConverter which makes a new converted reactor.

    Examples
    --------
    To convert a hex case to a R-Z case, do this:

    >>> geomConv = armi.reactorConverters.HexToRZConverter(useMostCommonXsId=False, expandReactor=False)
    >>> geomConv.convert(r)
    >>> newR = geomConv.convReactor
    >>> dif3d = dif3dInterface.Dif3dInterface('dif3dRZ', newR)
    >>> dif3d.o = self.o
    >>> dif3d.writeInput('rzGeom_actual.inp')
    """

    def __init__(self, cs=None, quiet=False):
        GeometryChanger.__init__(self, cs=cs, quiet=quiet)
        self.convReactor = None


class BlockNumberModifier(GeometryChanger):
    """
    Change the fueled region to have a certain number of blocks with uniform height.

    Notes
    -----
    Makes some assumptions about how control and fuel blocks are laid out.
    """

    def __init__(self, cs):
        GeometryChanger.__init__(self, cs)
        self.numToAdd = None

    def convert(self, r=None):
        """
        Changes the fueled region to have a certain number of blocks with uniform height

        Makes some assumptions about how control and fuel blocks
        are laid out.
        """
        refAssem = r.core.refAssem
        fuelI = refAssem.getBlocks().index(refAssem.getFirstBlock(Flags.FUEL))
        origRefBlocks = len(
            refAssem
        )  # store this b/c the ref assem length will change.

        for a in r.core.getAssemblies(includeBolAssems=True):
            if len(a) == origRefBlocks:
                # modify the number of blocks. Otherwise, it might be a shield
                # and snapping should accomplish its goal
                if a.hasFlags(Flags.FUEL):
                    self.setNumberOfBlocks(a)
                else:
                    # non-fuel. Control?
                    self.setNumberOfBlocks(a, blockType=a[fuelI].getType())
            else:
                # radial shields, etc. go here.
                pass

        # update inert assemblies to snap to the proper block sizes.
        axMesh = refAssem.getAxialMesh()
        for a in r.core.getAssemblies(includeBolAssems=True):
            a.makeAxialSnapList(refAssem)
            a.setBlockMesh(axMesh)
        r.core.updateAxialMesh()
        # update bookkeeping.
        r.core.regenAssemblyLists()

    def setNumberOfBlocks(self, assem, blockType=Flags.FUEL):
        r"""
        Change the region to have a certain number of blocks with uniform height

        Useful for parameter studies varying the block resolution.

        Parameters
        ----------
        assem : Assembly
            The assembly to modify

        blockType : str, optional
            Type of block to change. Default: Fuel. Allows control
            assemblies, etc. to modified just like fuel assemblies.

        Notes
        -----
        This also snaps the non-fuel blocks to the fuel mesh after calling this function
        on all assemblies. You will need to manually do this to all inert assems
        in the reactor.

        This renames blocks according to their axial position. Rerun history tracker
        if you're tracking history.

        """
        fuelHeight = assem.getTotalHeight(blockType)
        blockHeight = fuelHeight / self.numToAdd
        fuelBlocks = set(assem.getBlocks(blockType))
        newBlockStack = []
        numFuelBlocksAdded = 0
        # make a tracker flag that tells us if we're below or above fuel.
        # This model requires that there are no inert blocks interspersed in the fuel.
        fuelEncountered = False
        # add lower blocks, and as much fuel as possible.
        for bi, b in enumerate(assem.getBlocks()):
            if b not in fuelBlocks:
                if fuelEncountered:
                    # we're above fuel and assem[bi] is the first above-fuel block.
                    break
                else:
                    # add lower inert blocks as they are
                    newBlockStack.append(b)
            else:
                # fuel block.
                fuelEncountered = True
                if numFuelBlocksAdded < self.numToAdd:
                    numFuelBlocksAdded += 1
                    newBlockStack.append(b)
                    b.setHeight(blockHeight)
                    b.completeInitialLoading()

        # potentially add extra fuel blocks to fill up the assembly.
        # this will happen if we increased the number of fuel blocks
        # by a lot.
        for _extraBlock in range(self.numToAdd - numFuelBlocksAdded):
            newB = newBlockStack[-1].duplicate()  # copy the last fuel block.
            newBlockStack.append(newB)

        # add in the upper inert blocks, starting with the bi-th
        for b in assem.getBlocks()[bi:]:
            newBlockStack.append(b)

        # apply the new blocks to this assembly.
        assem.removeAll()
        for b in newBlockStack:
            assem.add(b)
        assem.reestablishBlockOrder()


class FuelAssemNumModifier(GeometryChanger):
    """
    Modify the number of fuel assemblies in the reactor.

    Notes
    -----
    - The number of fuel assemblies should ALWAYS be set for the third-core regardless of the reactor geometry model.
    - The modification is only valid for third-core and full-core geometry models.
    """

    def __init__(self, cs):
        GeometryChanger.__init__(self, cs)
        self.numFuelAssems = None  # in full core.
        self.fuelType = "feed fuel"
        self.overwriteList = [Flags.REFLECTOR, Flags.SHIELD]
        self.ringsToAdd = []
        self.modifyReactorPower = False

    def convert(self, r=None):
        """
        Set the number of fuel assemblies in the reactor.

        Notes
        -----
        - While adding fuel, does not modify existing fuel/control positions, but does overwrite assemblies in the
          overwriteList (e.g. reflectors, shields)
        - Once specified amount of fuel is in place, removes all assemblies past the outer fuel boundary
        - To re-add reflector/shield assemblies around the new core, use the ringsToAdd attribute
        """
        self._sourceReactor = r

        if r.core.powerMultiplier != 1 and r.core.powerMultiplier != 3:
            raise ValueError(
                "Invalid reactor geometry {} in {}. Reactor must be full or third core to modify the "
                "number of assemblies.".format(r.core.powerMultiplier, self)
            )

        # Set the number of fueled and non-fueled positions within the core (Full core or third-core)
        coreGeom = "full-core" if r.core.powerMultiplier == 1 else "third-core"
        runLog.info(
            "Modifying {} geometry to have {} fuel assemblies.".format(
                coreGeom, self.numFuelAssems
            )
        )
        nonFuelAssems = (
            sum(not assem.hasFlags(Flags.FUEL) for assem in r.core)
            * r.core.powerMultiplier
        )
        self.numFuelAssems *= r.core.powerMultiplier
        totalCoreAssems = nonFuelAssems + self.numFuelAssems

        # Adjust the total power of the reactor by keeping power per assembly constant
        if self.modifyReactorPower:
            r.core.p.power *= float(self.numFuelAssems) / (
                len(r.core.getAssemblies(Flags.FUEL)) * r.core.powerMultiplier
            )

        # Get the sorted assembly locations in the core (Full core or third core)
        assemOrderList = r.core.spatialGrid.generateSortedHexLocationList(
            totalCoreAssems
        )
        if r.core.powerMultiplier == 3:
            assemOrderList = [
                loc for loc in assemOrderList if r.core.spatialGrid.isInFirstThird(loc)
            ]

        # Add fuel assemblies to the core
        addingFuelIsComplete = False
        numFuelAssemsAdded = 0
        for loc in assemOrderList:
            assem = r.core.childrenByLocator.get(loc)
            if numFuelAssemsAdded < self.numFuelAssems:
                if assem is None:
                    raise KeyError("Cannot find expected fuel assem in {}".format(loc))
                # Add new fuel assembly to the core
                if assem.hasFlags(self.overwriteList):
                    fuelAssem = r.core.createAssemblyOfType(assemType=self.fuelType)
                    # Remove existing assembly in the core location before adding new assembly
                    if assem.hasFlags(self.overwriteList):
                        r.core.removeAssembly(assem, discharge=False)
                    r.core.add(fuelAssem, loc)
                    numFuelAssemsAdded += r.core.powerMultiplier
                else:
                    # Keep the existing assembly in the core
                    if assem.hasFlags(Flags.FUEL):
                        # Count the assembly in the location if it is fuel
                        numFuelAssemsAdded += r.core.powerMultiplier
                    else:
                        pass
            # Flag the completion of adding fuel assemblies (see note 1)
            elif numFuelAssemsAdded == self.numFuelAssems:
                addingFuelIsComplete = True

            # Remove the remaining assemblies in the the assembly list once all the fuel has been added
            if addingFuelIsComplete and assem is not None:
                r.core.removeAssembly(assem, discharge=False)

        # Remove all other assemblies from the core
        for assem in r.core.getAssemblies():
            if (
                assem.spatialLocator not in assemOrderList
            ):  # check if assembly is on the list
                r.core.removeAssembly(
                    assem, discharge=False
                )  # get rid of the old assembly

        # Add the remaining rings of assemblies to the core
        for assemType in self.ringsToAdd:
            self.addRing(assemType=assemType)

        # Complete the reactor loading
        r.core.processLoading(self._cs)  # pylint: disable=protected-access
        r.core.numRings = r.core.getNumRings()
        r.core.regenAssemblyLists()
        r.core.circularRingList = None  # need to reset this (possibly other stuff too)

    def addRing(self, assemType="big shield"):
        r"""
        Add a ring of fuel assemblies around the outside of an existing core

        Works by first finding the assembly furthest from the center, then filling in
        all assemblies that are within one pitch further with the specified assembly type

        Parameters
        ----------
        assemType : str
            Assembly type that will be added to the outside of the core
        """
        r = self._sourceReactor
        # first look through the core and finds the one farthest from the center
        maxDist = 0.0
        for assem in r.core.getAssemblies():
            dist = numpy.linalg.norm(
                assem.spatialLocator.getGlobalCoordinates()
            )  # get distance from origin
            dist = round(
                dist, 6
            )  # round dist to 6 places to avoid differences due to floating point math
            maxDist = max(maxDist, dist)

        # add one hex pitch to the maximum distance to get the bounding distance for the new ring
        hexPitch = r.core.spatialGrid.pitch
        newRingDist = maxDist + hexPitch

        maxArea = (
            math.pi * (newRingDist + hexPitch) ** 2.0
        )  # area that is guaranteed to bound the new core
        maxAssemsFull = maxArea / hexagon.area(
            hexPitch
        )  # divide by hex area to get number of hexes in a full core

        # generate ordered list of assembly locations
        assemOrderList = r.core.spatialGrid.generateSortedHexLocationList(maxAssemsFull)
        if r.core.powerMultiplier == 3:
            assemOrderList = [
                loc
                for loc in assemOrderList
                if self._sourceReactor.core.spatialGrid.isInFirstThird(loc)
            ]
        elif r.core.powerMultiplier != 1:
            raise RuntimeError("{} only works on full or 1/3 symmetry.".format(self))
        # add new assemblies to core within one ring
        for locator in assemOrderList:
            assem = r.core.childrenByLocator.get(
                locator
            )  # check on assemblies, moving radially outward
            dist = numpy.linalg.norm(locator.getGlobalCoordinates())
            dist = round(dist, 6)
            if dist <= newRingDist:  # check distance
                if assem is None:  # no assembly in that position, add assembly
                    newAssem = r.core.createAssemblyOfType(
                        assemType=assemType
                    )  # create a fuel assembly
                    r.core.add(newAssem, locator)  # put new assembly in reactor!
                else:  # all other types of assemblies (fuel, control, etc) leave as is
                    pass
            else:
                pass


class HexToRZThetaConverter(GeometryConverter):
    """
    Convert hex-based cases to an equivalent R-Z-Theta full core geometry.

    Parameters
    ----------
    converterSettings: dictionary like object
        Settings that specify how the mesh of the RZTheta reactor should be generated. Controls the number of theta
        regions, how to group regions, etc.
    expandReactor : bool
        If True, the HEX-Z reactor will be expanded to full core geometry prior to converting to the RZT reactor.
        Either way the converted RZTheta core will be full core.
    strictHomogenization : bool
        If True, the converter will restrict HEX-Z blocks with dissimilar XS types from being homogenized into an
        RZT block.
    """

    _GEOMETRY_TYPE = geometry.RZT
    _BLOCK_MIXTURE_TYPE_MAP = {
        "mixture control": ["control"],
        "mixture fuel": ["fuel"],
        "mixture radial shield": ["radial shield"],
        "mixture axial shield": ["shield"],
        "mixture structure": [
            "grid plate",
            "reflector",
            "inlet nozzle",
            "handling socket",
        ],
        "mixture duct": ["duct"],
        "mixture plenum": ["plenum"],
    }

    _BLOCK_MIXTURE_TYPE_EXCLUSIONS = ["control", "fuel", "radial shield"]
    _MESH_BY_RING_COMP = "Ring Compositions"
    _MESH_BY_AXIAL_COORDS = "Axial Coordinates"
    _MESH_BY_AXIAL_BINS = "Axial Bins"

    def __init__(
        self, cs, converterSettings, expandReactor=False, strictHomogenization=False
    ):
        GeometryConverter.__init__(self, cs)
        self.converterSettings = converterSettings
        self._o = None
        self.meshConverter = None
        self._expandSourceReactor = expandReactor
        self._strictHomogenization = strictHomogenization
        self._radialMeshConversionType = None
        self._axialMeshConversionType = None
        self._previousRadialZoneAssemTypes = None
        self._currentRadialZoneType = None
        self._assemsInRadialZone = collections.defaultdict(list)
        self._newBlockNum = 0
        self.blockMap = collections.defaultdict(list)
        self.blockVolFracs = collections.defaultdict(dict)

    def _generateConvertedReactorMesh(self):
        """
        Convert the source reactor using the converterSettings
        """
        runLog.info("Generating mesh coordinates for the reactor conversion")
        self._radialMeshConversionType = self.converterSettings["radialConversionType"]
        self._axialMeshConversionType = self.converterSettings["axialConversionType"]
        converter = None
        if self._radialMeshConversionType == self._MESH_BY_RING_COMP:
            if self._axialMeshConversionType == self._MESH_BY_AXIAL_COORDS:
                converter = meshConverters.RZThetaReactorMeshConverterByRingCompositionAxialCoordinates(
                    self.converterSettings
                )
            elif self._axialMeshConversionType == self._MESH_BY_AXIAL_BINS:
                converter = meshConverters.RZThetaReactorMeshConverterByRingCompositionAxialBins(
                    self.converterSettings
                )
        if converter is None:
            raise ValueError(
                "No mesh converter exists for `radialConversionType` and `axialConversionType` settings "
                "of {} and {}".format(
                    self._radialMeshConversionType, self._axialMeshConversionType
                )
            )
        self.meshConverter = converter
        return self.meshConverter.generateMesh(self._sourceReactor)

    def convert(self, r):
        """
        Run the conversion to 3 dimensional R-Z-Theta.

        Attributes
        ----------
        r : Reactor object
            The reactor to convert.

        Notes
        -----
        As a part of the RZT mesh converters it is possible to obtain a radial mesh that has repeated ring numbers.
        For instance, if there are fuel assemblies and control assemblies within the same radial hex ring then it's
        possible that a radial mesh output from the byRingComposition mesh converter method will look something like:

        self.meshConverter.radialMesh = [2, 3, 4, 4, 5, 5, 6, 6, 6, 7, 8, 8, 9, 10]

        In this instance the hex ring will remain the same for multiple iterations over radial direction when
        homogenizing the hex core into the RZT geometry. In this case, the converter needs to keep track of the
        compositions within this ring so that it can separate this repeated ring into multiple RZT rings. Each of the
        RZT rings should have a single composition (fuel1, fuel2, control, etc.)

        See Also
        --------
        armi.reactor.converters.meshConverters
        """
        if r.core.geomType != geometry.HEX:
            raise ValueError(
                "Cannot use {} to convert {} reactor".format(
                    self, r.core.geomType.upper()
                )
            )

        self._sourceReactor = r
        self._setupSourceReactorForConversion()
        reactorConversionMethod = (
            "hexagonal"
            if self.converterSettings["hexRingGeometryConversion"]
            else "circular"
        )
        runLog.extra(
            "Converting reactor using {} rings".format(reactorConversionMethod)
        )
        rztSpatialGrid = self._generateConvertedReactorMesh()
        runLog.info(rztSpatialGrid)
        self._setupConvertedReactor(rztSpatialGrid)

        innerDiameter = 0.0
        lowerRing = 1
        radialMeshCm = [0.0]
        for radialIndex, upperRing in enumerate(self.meshConverter.radialMesh):
            lowerTheta = 0.0
            # see notes
            self._previousRadialZoneAssemTypes = (
                self._previousRadialZoneAssemTypes if lowerRing == upperRing else []
            )
            if lowerRing == upperRing:
                lowerRing = upperRing - 1

            self._setNextAssemblyTypeInRadialZone(lowerRing, upperRing)
            self._setAssemsInRadialZone(radialIndex, lowerRing, upperRing)
            for thetaIndex, upperTheta in enumerate(self.meshConverter.thetaMesh):
                zoneAssems = self._getAssemsInRadialThetaZone(
                    lowerRing, upperRing, lowerTheta, upperTheta
                )
                self._writeRadialThetaZoneHeader(
                    radialIndex,
                    lowerRing,
                    upperRing,
                    thetaIndex,
                    lowerTheta,
                    upperTheta,
                )
                outerDiameter = self._createRadialThetaZone(
                    innerDiameter,
                    thetaIndex,
                    radialIndex,
                    lowerTheta,
                    upperTheta,
                    zoneAssems,
                )
                lowerTheta = upperTheta
            innerDiameter = outerDiameter
            lowerRing = upperRing
            radialMeshCm.append(outerDiameter / 2.0)

        # replace temporary index-based ring indices with actual radial distances
        self.convReactor.core.spatialGrid._bounds = (
            self.convReactor.core.spatialGrid._bounds[0],
            numpy.array(radialMeshCm),
            self.convReactor.core.spatialGrid._bounds[2],
        )

        self.convReactor.core.updateAxialMesh()
        self.convReactor.core.summarizeReactorStats()

    def _setNextAssemblyTypeInRadialZone(self, lowerRing, upperRing):
        """
        Change the currently-active assembly type to the next active one based on a specific order.

        If this is called with the same (lowerRing, upperRing) twice, the next assembly type
        will be applied. This is useful, for instance, in putting control zones amidst fuel.
        """
        sortedAssemTypes = self._getSortedAssemblyTypesInRadialZone(
            lowerRing, upperRing
        )
        for aType in sortedAssemTypes:
            if aType not in self._previousRadialZoneAssemTypes:
                self._previousRadialZoneAssemTypes.append(aType)
                self._currentRadialZoneType = aType
                break

    def _getSortedAssemblyTypesInRadialZone(self, lowerRing, upperRing):
        """
        Retrieve assembly types in a radial zone between (lowerRing, upperRing), sort from highest occurrence to lowest.

        Notes
        -----
        - Assembly types are based on the assembly names and not the direct composition within each assembly. For
          instance, if two assemblies are named `fuel 1` and `fuel 2` but they have the same composition at some reactor
          state then they will still be separated as two different assembly types.
        """
        aCountByTypes = collections.Counter()
        for a in self._getAssembliesInCurrentRadialZone(lowerRing, upperRing):
            aCountByTypes[a.getType().lower()] += 1

        # sort on tuple (int, str) to force consistent ordering of result when counts are tied
        sortedAssemTypes = sorted(
            aCountByTypes, key=lambda aType: (aCountByTypes[aType], aType), reverse=True
        )
        return sortedAssemTypes

    def _getAssembliesInCurrentRadialZone(self, lowerRing, upperRing):
        ringAssems = []
        for ring in range(lowerRing, upperRing):
            if self.converterSettings["hexRingGeometryConversion"]:
                ringAssems.extend(
                    self._sourceReactor.core.getAssembliesInSquareOrHexRing(ring)
                )
            else:
                ringAssems.extend(self._sourceReactor.core.getAssembliesInRing(ring))
        return ringAssems

    def _setupSourceReactorForConversion(self):
        self._sourceReactor.core.summarizeReactorStats()
        if self._expandSourceReactor:
            self._expandSourceReactorGeometry()
        self._o = self._sourceReactor.o

    def _setupConvertedReactor(self, grid):
        self.convReactor = reactors.Reactor(
            "ConvertedReactor", self._sourceReactor.blueprints
        )
        core = reactors.Core("Core")
        if self._cs is not None:
            core.setOptionsFromCs(self._cs)
        self.convReactor.add(core)
        self.convReactor.core.spatialGrid = grid
        grid.symmetry = geometry.FULL_CORE
        grid.geomType = self._GEOMETRY_TYPE
        grid.armiObject = self.convReactor.core
        self.convReactor.core.p.power = self._sourceReactor.core.p.power
        self.convReactor.core.name += " - {0}".format(self._GEOMETRY_TYPE)

    def _setAssemsInRadialZone(self, radialIndex, lowerRing, upperRing):
        """
        Retrieve a list of assemblies in the reactor between (lowerRing, upperRing)

        Notes
        -----
        self._assemsInRadialZone keeps track of the unique assemblies that are in each radial ring. This
        ensures that no assemblies are duplicated when using self._getAssemsInRadialThetaZone()
        """

        lowerTheta = 0.0
        for _thetaIndex, upperTheta in enumerate(self.meshConverter.thetaMesh):
            assemsInRadialThetaZone = self._getAssemsInRadialThetaZone(
                lowerRing, upperRing, lowerTheta, upperTheta
            )
            newAssemsInRadialZone = set(assemsInRadialThetaZone)
            oldAssemsInRadialZone = set(self._assemsInRadialZone[radialIndex])
            self._assemsInRadialZone[radialIndex].extend(
                sorted(list(newAssemsInRadialZone.union(oldAssemsInRadialZone)))
            )
            lowerTheta = upperTheta

        if not self._assemsInRadialZone[radialIndex]:
            raise ValueError(
                "No assemblies in radial zone {} between rings {} and {}".format(
                    self._assemsInRadialZone[radialIndex], lowerRing, upperRing
                )
            )

    def _getAssemsInRadialThetaZone(self, lowerRing, upperRing, lowerTheta, upperTheta):
        """Retrieve list of assemblies in the reactor between (lowerRing, upperRing) and (lowerTheta, upperTheta)."""
        thetaAssems = self._sourceReactor.core.getAssembliesInSector(
            math.degrees(lowerTheta), math.degrees(upperTheta)
        )
        ringAssems = self._getAssembliesInCurrentRadialZone(lowerRing, upperRing)
        if self._radialMeshConversionType == self._MESH_BY_RING_COMP:
            ringAssems = self._selectAssemsBasedOnType(ringAssems)

        ringAssems = set(ringAssems)
        thetaAssems = set(thetaAssems)
        assemsInRadialThetaZone = sorted(ringAssems.intersection(thetaAssems))

        if not assemsInRadialThetaZone:
            raise ValueError(
                "No assemblies in radial-theta zone between rings {} and {} "
                "and theta bounds of {} and {}".format(
                    lowerRing, upperRing, lowerTheta, upperTheta
                )
            )

        return assemsInRadialThetaZone

    def _selectAssemsBasedOnType(self, assems):
        """Retrieve a list of assemblies of a given type within a subset of an assembly list.

        Parameters
        ----------
        assems: list
            Subset of assemblies in the reactor.
        """
        selectedAssems = []
        for a in assems:
            if a.getType().lower() == self._currentRadialZoneType:
                selectedAssems.append(a)

        return selectedAssems

    def _createRadialThetaZone(
        self, innerDiameter, thetaIndex, radialIndex, lowerTheta, upperTheta, zoneAssems
    ):
        """
        Add a new stack of circles to the TRZ reactor by homogenizing assems

        Inputs
        ------
        innerDiameter:
            The current innerDiameter of the radial-theta zone

        thetaIndex:
            The theta index of the radial-theta zone

        radialIndex:
            The radial index of the radial-theta zone

        lowerTheta:
            The lower theta bound for the radial-theta zone

        upperTheta:
            The upper theta bound for the radial-theta zone

        Returns
        -------
        outerDiameter : float
            The outer diameter (in cm) of the radial zone just added
        """

        newAssembly = assemblies.ThRZAssembly("mixtureAssem")
        newAssembly.spatialLocator = self.convReactor.core.spatialGrid[
            thetaIndex, radialIndex, 0
        ]
        newAssembly.p.AziMesh = 2
        newAssembly.spatialGrid = grids.axialUnitGrid(
            len(self.meshConverter.axialMesh), armiObject=newAssembly
        )

        lowerAxialZ = 0.0
        for axialIndex, upperAxialZ in enumerate(self.meshConverter.axialMesh):

            # Setup the new block data
            newBlockName = "B{:04d}{}".format(
                int(newAssembly.getNum()), chr(axialIndex + 65)
            )
            newBlock = blocks.ThRZBlock(newBlockName)

            # Compute the homogenized block data
            (
                newBlockAtoms,
                newBlockType,
                newBlockTemp,
                newBlockVol,
            ) = self.createHomogenizedRZTBlock(
                newBlock, lowerAxialZ, upperAxialZ, zoneAssems
            )
            # Compute radial zone outer diameter
            axialSegmentHeight = upperAxialZ - lowerAxialZ
            radialZoneVolume = self._calcRadialRingVolume(
                lowerAxialZ, upperAxialZ, radialIndex
            )
            radialRingArea = (
                radialZoneVolume
                / axialSegmentHeight
                * self._sourceReactor.core.powerMultiplier
            )
            outerDiameter = blockConverters.getOuterDiamFromIDAndArea(
                innerDiameter, radialRingArea
            )

            # Set new homogenized block parameters
            material = materials.material.Material()
            material.name = "mixture"
            material.p.refDens = 1.0  # generic density. Will cancel out.
            dims = {
                "inner_radius": innerDiameter / 2.0,
                "radius_differential": (outerDiameter - innerDiameter) / 2.0,
                "inner_axial": lowerAxialZ,
                "height": axialSegmentHeight,
                "inner_theta": lowerTheta,
                "azimuthal_differential": (upperTheta - lowerTheta),
                "mult": 1.0,
                "Tinput": newBlockTemp,
                "Thot": newBlockTemp,
            }
            for nuc in self._sourceReactor.blueprints.allNuclidesInProblem:
                material.setMassFrac(nuc, 0.0)
            newComponent = components.DifferentialRadialSegment(
                "mixture", material, **dims
            )
            newBlock.p.axMesh = int(axialSegmentHeight / BLOCK_AXIAL_MESH_SPACING) + 1
            newBlock.p.zbottom = lowerAxialZ
            newBlock.p.ztop = upperAxialZ

            # Assign the new block cross section type and burn up group
            newBlock.setType(newBlockType)
            newXsType, newBuGroup = self._createBlendedXSID(newBlock)
            newBlock.p.xsType = newXsType
            newBlock.p.buGroup = newBuGroup

            # Update the block dimensions and set the block densities
            newComponent.updateDims()  # ugh.
            newBlock.p.height = axialSegmentHeight
            newBlock.clearCache()
            newBlock.add(newComponent)
            for nuc, atoms in newBlockAtoms.items():
                newBlock.setNumberDensity(nuc, atoms / newBlockVol)

            self._writeRadialThetaZoneInfo(axialIndex + 1, axialSegmentHeight, newBlock)
            self._checkVolumeConservation(newBlock)

            newAssembly.add(newBlock)
            lowerAxialZ = upperAxialZ
        newAssembly.calculateZCoords()  # builds mesh
        self.convReactor.core.add(newAssembly)

        return outerDiameter

    def _calcRadialRingVolume(self, lowerZ, upperZ, radialIndex):
        """Compute the total volume of a list of assemblies within a ring between two axial heights."""
        ringVolume = 0.0
        for assem in self._assemsInRadialZone[radialIndex]:
            for b, heightHere in assem.getBlocksBetweenElevations(lowerZ, upperZ):
                ringVolume += b.getVolume() * heightHere / b.getHeight()

        if not ringVolume:
            raise ValueError("Ring volume of ring {} is 0.0".format(radialIndex + 1))

        return ringVolume

    def _checkVolumeConservation(self, newBlock):
        """Write the volume fractions of each hex block within the homogenized RZT block."""
        newBlockVolumeFraction = 0.0
        for hexBlock in self.blockMap[newBlock]:
            newBlockVolumeFraction += self.blockVolFracs[newBlock][hexBlock]

        if abs(newBlockVolumeFraction - 1.0) > 0.00001:
            raise ValueError(
                "The volume fraction of block {} is {} and not 1.0. An error occurred when converting the reactor"
                " geometry.".format(newBlock, newBlockVolumeFraction)
            )

    def createHomogenizedRZTBlock(
        self, homBlock, lowerAxialZ, upperAxialZ, radialThetaZoneAssems
    ):
        """
        Create the homogenized RZT block by computing the average atoms in the zone.

        Additional calculations are performed to determine the homogenized block type, the block average temperature,
        and the volume fraction of each hex block that is in the new homogenized block.
        """
        homBlockXsTypes = set()
        numHexBlockByType = collections.Counter()
        homBlockAtoms = collections.defaultdict(int)
        homBlockVolume = 0.0
        homBlockTemperature = 0.0
        for assem in radialThetaZoneAssems:
            blocksHere = assem.getBlocksBetweenElevations(lowerAxialZ, upperAxialZ)
            for b, heightHere in blocksHere:
                homBlockXsTypes.add(b.p.xsType)
                numHexBlockByType[b.getType().lower()] += 1
                blockVolumeHere = b.getVolume() * heightHere / b.getHeight()
                if blockVolumeHere == 0.0:
                    raise ValueError(
                        "Geometry conversion failed. Block {} has zero volume".format(b)
                    )
                homBlockVolume += blockVolumeHere
                homBlockTemperature += b.getAverageTempInC() * blockVolumeHere
                for nucName in b.getNuclides():
                    homBlockAtoms[nucName] += (
                        b.getNumberDensity(nucName) * blockVolumeHere
                    )
                self.blockMap[homBlock].append(b)
                self.blockVolFracs[homBlock][b] = blockVolumeHere
        # Notify if blocks with different xs types are being homogenized. May be undesired behavior.
        if len(homBlockXsTypes) > 1:
            msg = (
                "Blocks {} with dissimilar XS IDs are being homogenized in {} between axial heights {} "
                "cm and {} cm. ".format(
                    self.blockMap[homBlock],
                    self.convReactor.core,
                    lowerAxialZ,
                    upperAxialZ,
                )
            )
            if self._strictHomogenization:
                raise ValueError(
                    msg + "Modify mesh converter settings before proceeding."
                )
            else:
                runLog.important(msg)

        homBlockType = self._getHomogenizedBlockType(numHexBlockByType)
        homBlockTemperature = homBlockTemperature / homBlockVolume
        for b in self.blockMap[homBlock]:
            self.blockVolFracs[homBlock][b] = (
                self.blockVolFracs[homBlock][b] / homBlockVolume
            )

        return homBlockAtoms, homBlockType, homBlockTemperature, homBlockVolume

    def _getHomogenizedBlockType(self, numHexBlockByType):
        """
        Generate the homogenized block mixture type based on the frequency of hex block types that were merged
        together.

        Notes
        -----
        self._BLOCK_MIXTURE_TYPE_EXCLUSIONS:
            The normal function of this method is to assign the mixture name based on the number of occurrences of the
            block type. This list stops that and assigns the mixture based on the first occurrence.
            (i.e. if the mixture has a set of blocks but it comes across one with the name of 'control' the process will
            stop and the new mixture type will be set to 'mixture control'

        self._BLOCK_MIXTURE_TYPE_MAP:
            A dictionary that provides the name of blocks that are condensed together
        """
        assignedMixtureBlockType = None

        # Find the most common block type out of the types in the block mixture type exclusions list
        excludedBlockTypesInBlock = set(
            [
                x
                for x in self._BLOCK_MIXTURE_TYPE_EXCLUSIONS
                for y in numHexBlockByType
                if x in y
            ]
        )
        if excludedBlockTypesInBlock:
            for blockType in self._BLOCK_MIXTURE_TYPE_EXCLUSIONS:
                if blockType in excludedBlockTypesInBlock:
                    assignedMixtureBlockType = "mixture " + blockType
                    return assignedMixtureBlockType

        # Assign block type by most common hex block type
        mostCommonHexBlockType = sorted(numHexBlockByType.most_common(1))[0][
            0
        ]  # sort needed for tie break

        for mixtureType in sorted(self._BLOCK_MIXTURE_TYPE_MAP):
            validBlockTypesInMixture = self._BLOCK_MIXTURE_TYPE_MAP[mixtureType]
            for validBlockType in validBlockTypesInMixture:
                if validBlockType in mostCommonHexBlockType:
                    assignedMixtureBlockType = mixtureType
                    return assignedMixtureBlockType

        assignedMixtureBlockType = "mixture structure"
        runLog.extra(
            "The mixture type for this homogenized block was not determined and is defaulting to {}".format(
                assignedMixtureBlockType
            )
        )

        return assignedMixtureBlockType

    def _createBlendedXSID(self, newBlock):
        """
        Generate the blended XS id using the most common XS id in the hexIdList
        """
        ids = [hexBlock.getMicroSuffix() for hexBlock in self.blockMap[newBlock]]
        xsTypeList, buGroupList = zip(*ids)

        xsType, _count = collections.Counter(xsTypeList).most_common(1)[0]
        buGroup, _count = collections.Counter(buGroupList).most_common(1)[0]

        return xsType, buGroup

    def _writeRadialThetaZoneHeader(
        self, radIdx, lowerRing, upperRing, thIdx, lowerTheta, upperTheta
    ):
        radialAssemType = (
            "({})".format(self._currentRadialZoneType)
            if self._currentRadialZoneType is not None
            else ""
        )
        runLog.info(
            "Creating: Radial Zone {}, Theta Zone {} {}".format(
                radIdx + 1, thIdx + 1, radialAssemType
            )
        )
        runLog.extra(
            "{} Hex Rings: [{}, {}), Theta Revolutions: [{:.2f}, {:.2f})".format(
                9 * STR_SPACE,
                lowerRing,
                upperRing,
                lowerTheta * units.RAD_TO_REV,
                upperTheta * units.RAD_TO_REV,
            )
        )
        runLog.debug(
            "{} Axial Zone - Axial Height (cm) Block Number Block Type             XS ID : Original Hex Block XS ID(s)".format(
                9 * STR_SPACE
            )
        )
        runLog.debug(
            "{} ---------- - ----------------- ------------ ---------------------- ----- : ---------------------------".format(
                9 * STR_SPACE
            )
        )

    def _writeRadialThetaZoneInfo(self, axIdx, axialSegmentHeight, blockObj):
        """
        Create a summary of the mapping between the converted reactor block ids to the hex reactor block ids
        """
        self._newBlockNum += 1
        hexBlockXsIds = []
        for hexBlock in self.blockMap[blockObj]:
            hexBlockXsIds.append(hexBlock.getMicroSuffix())
        runLog.debug(
            "{} {:<10} - {:<17.3f} {:<12} {:<22} {:<5} : {}".format(
                9 * STR_SPACE,
                axIdx,
                axialSegmentHeight,
                self._newBlockNum,
                blockObj.getType(),
                blockObj.getMicroSuffix(),
                hexBlockXsIds,
            )
        )

    def _expandSourceReactorGeometry(self):
        """
        Expansion of the reactor geometry to build the R-Z-Theta core model
        """
        runLog.info("Expanding source reactor core to a full core model")
        reactorExpander = ThirdCoreHexToFullCoreChanger(self._cs)
        reactorExpander.convert(self._sourceReactor)
        self._sourceReactor.core.summarizeReactorStats()

    def plotConvertedReactor(self):
        """
        Generate plots for the converted RZT reactor.

        Notes
        -----
        XTView can be used to view the RZT reactor but this is useful to examine the conversion of the hex-z reactor
        to the rzt reactor.
        """
        runLog.info(
            "Generating plot(s) of the converted {} reactor".format(
                self.convReactor.core.geomType.upper()
            )
        )
        colConv = matplotlib.colors.ColorConverter()
        colGen = plotting.colorGenerator(5)
        blockColors = {}
        thetaMesh, radialMesh, axialMesh = self._getReactorMeshCoordinates()
        innerTheta = 0.0
        for i, outerTheta in enumerate(thetaMesh):
            plt.figure(figsize=(12, 12), dpi=300)
            ax = plt.gca()
            innerRadius = 0.0
            for outerRadius in radialMesh:
                innerAxial = 0.0
                for outerAxial in axialMesh:
                    b = self._getBlockAtMeshPoint(
                        innerTheta,
                        outerTheta,
                        innerRadius,
                        outerRadius,
                        innerAxial,
                        outerAxial,
                    )
                    blockType = b.getType()
                    blockColor = self._getBlockColor(
                        colConv, colGen, blockColors, blockType
                    )
                    if blockColor is not None:
                        blockColors[blockType] = blockColor
                    blockPatch = matplotlib.patches.Rectangle(
                        (innerRadius, innerAxial),
                        (outerRadius - innerRadius),
                        (outerAxial - innerAxial),
                        facecolor=blockColors[blockType],
                        linewidth=0,
                        alpha=0.7,
                    )
                    ax.add_patch(blockPatch)
                    innerAxial = outerAxial
                innerRadius = outerRadius
            plt.title(
                "{} Core Map of from {} to {} revolutions".format(
                    self.convReactor.core.geomType.upper(),
                    innerTheta * units.RAD_TO_REV,
                    outerTheta * units.RAD_TO_REV,
                ),
                y=1.03,
            )
            ax.set_xticks([0.0] + radialMesh)
            ax.set_yticks([0.0] + axialMesh)
            ax.tick_params(axis="both", which="major", labelsize=11, length=0, width=0)
            ax.grid()
            labels = ax.get_xticklabels()
            for label in labels:
                label.set_rotation(270)
            handles = []
            labels = []
            for blockType, blockColor in blockColors.items():
                line = matplotlib.lines.Line2D(
                    [], [], color=blockColor, markersize=15, label=blockType
                )
                handles.append(line)
                labels.append(line.get_label())
            plt.xlabel("Radial Mesh (cm)".upper(), labelpad=20)
            plt.ylabel("Axial Mesh (cm)".upper(), labelpad=20)
            plt.plot()
            figName = (
                "coreMap"
                + "-{}".format(self.convReactor.core.geomType)
                + "_{}".format(i)
                + ".png"
            )
            plt.savefig(figName)
            plt.close()
            innerTheta = outerTheta

    def _getReactorMeshCoordinates(self):
        thetaMesh, radialMesh, axialMesh = self.convReactor.core.findAllMeshPoints(
            applySubMesh=False
        )
        thetaMesh.remove(0.0)
        radialMesh.remove(0.0)
        axialMesh.remove(0.0)
        return thetaMesh, radialMesh, axialMesh

    def _getBlockAtMeshPoint(
        self, innerTheta, outerTheta, innerRadius, outerRadius, innerAxial, outerAxial
    ):
        for b in self.convReactor.core.getBlocks():
            blockMidTh, blockMidR, blockMidZ = b.spatialLocator.getGlobalCoordinates(
                nativeCoords=True
            )
            if (blockMidTh >= innerTheta) and (blockMidTh <= outerTheta):
                if (blockMidR >= innerRadius) and (blockMidR <= outerRadius):
                    if (blockMidZ >= innerAxial) and (blockMidZ <= outerAxial):
                        return b
        raise ValueError(
            "No block found between ({}, {}), ({}, {}), ({}, {})\n"
            "Last block had TRZ= {} {} {}".format(
                innerTheta,
                outerTheta,
                innerRadius,
                outerRadius,
                innerAxial,
                outerAxial,
                blockMidTh,
                blockMidR,
                blockMidZ,
            )
        )

    def _getBlockColor(self, colConverter, colGenerator, blockColors, blockType):
        nextColor = None
        if blockType not in blockColors:
            if "fuel" in blockType:
                nextColor = "tomato"
            elif "structure" in blockType:
                nextColor = "lightgrey"
            elif "radial shield" in blockType:
                nextColor = "lightgrey"
            elif "duct" in blockType:
                nextColor = "grey"
            else:
                while True:
                    try:
                        nextColor = next(colGenerator)
                        colConverter.to_rgba(nextColor)
                        break
                    except ValueError:
                        continue
        return nextColor


class HexToRZConverter(HexToRZThetaConverter):
    r"""
    Create a new reactor with R-Z coordinates from the Hexagonal-Z reactor

    This is a subclass of the HexToRZThetaConverter. See the HexToRZThetaConverter for explanation and setup of
    the converterSettings.
    """

    _GEOMETRY_TYPE = geometry.RZ


class ThirdCoreHexToFullCoreChanger(GeometryChanger):
    """
    Change third-core models to full core in place

    Does not generate a new reactor object.

    Examples
    --------
    >>> converter = ThirdCoreHexToFullCoreChanger()
    >>> converter.convert(myReactor)

    """

    EXPECTED_INPUT_SYMMETRY = "third periodic"

    def convert(self, r=None):
        """
        Run the conversion.

        Parameters
        ----------
        sourceReactor : Reactor object
            The reactor to convert.

        """
        if r.core.isFullCore:
            # already full core from geometry file. No need to copy symmetry over.
            runLog.important(
                "Detected that full core reactor already exists. Cannot expand."
            )
            return r
        elif not (
            r.core.symmetry == self.EXPECTED_INPUT_SYMMETRY
            and r.core.geomType == geometry.HEX
        ):
            raise ValueError(
                "ThirdCoreHexToFullCoreChanger requires the input to have be third core hex geometry."
                "Geometry received was {} {}".format(r.core.symmetry, r.core.geomType)
            )
        edgeChanger = EdgeAssemblyChanger()
        edgeChanger.removeEdgeAssemblies(r.core)
        runLog.info("Expanding to full core geometry")
        r.core.symmetry = geometry.FULL_CORE

        for a in r.core.getAssemblies():
            # make extras and add them too. since the input is assumed to be 1/3 core.
            otherLocs = r.core.spatialGrid.getSymmetricIdenticalsThird(
                a.spatialLocator.indices
            )
            for i, j in otherLocs:
                newAssem = copy.deepcopy(a)
                newAssem.makeUnique()
                r.core.add(newAssem, r.core.spatialGrid[i, j, 0])
                self._newAssembliesAdded.append(newAssem)

    def restorePreviousGeometry(self, cs, reactor):
        """
        Undo the changes made by convert by going back to 1/3 core.
        """
        # remove the assemblies that were added when the conversion happened.
        if bool(self.getNewAssembliesAdded()):

            for a in self.getNewAssembliesAdded():
                reactor.core.removeAssembly(a, discharge=False)

            # restore the settings of the core
            cs.unsetTemporarySettings()

            reactor.core.symmetry = self.EXPECTED_INPUT_SYMMETRY


class EdgeAssemblyChanger(GeometryChanger):
    """
    Add/remove "edge assemblies" for Finite difference or MCNP cases

    Examples
    --------
    edgeChanger = EdgeAssemblyChanger()
    edgeChanger.removeEdgeAssemblies(reactor.core)
    """

    def addEdgeAssemblies(self, core):
        """
        Add the assemblies on the 120 degree symmetric line to 1/3 symmetric cases

        Needs to be called before a finite difference (DIF3D, DIFNT) or MCNP calculation

        Parameters
        ----------
        reactor : Reactor
            Reactor to modify

        See Also
        --------
        removeEdgeAssemblies : removes the edge assemblies

        """
        if core.isFullCore:
            return

        if self.getNewAssembliesAdded():
            runLog.important(
                "Skipping addition of edge assemblies because they are already there"
            )
            return False

        assembliesOnLowerBoundary = core.getAssembliesOnSymmetryLine(
            locations.BOUNDARY_0_DEGREES
        )
        assembliesOnUpperBoundary = []
        for a in assembliesOnLowerBoundary:
            a.clearCache()  # symmetry factors of these assemblies will change since they are now half assems.
            a2 = copy.deepcopy(a)
            a2.makeUnique()
            assembliesOnUpperBoundary.append(a2)

        if not assembliesOnUpperBoundary:
            runLog.extra("No edge assemblies to add")

        # Move the assemblies into their reflective position on symmetry line 3
        for a in assembliesOnUpperBoundary:
            # loc will now be either an empty set [], or two different locations
            # in our case, we only want the first of the two locations
            locs = core.spatialGrid.getSymmetricIdenticalsThird(a.spatialLocator)
            if locs:
                i, j = locs[0]
                spatialLocator = core.spatialGrid[i, j, 0]
                if core.childrenByLocator.get(spatialLocator):
                    runLog.warning(
                        "Edge assembly already exists in {0}. Not adding.".format(
                            locs[0]
                        )
                    )
                    continue
                # add the copied assembly to the reactor list
                runLog.debug(
                    "Adding edge assembly {0} to {1} to the reactor".format(
                        a, spatialLocator
                    )
                )
                core.add(a, spatialLocator)
                self._newAssembliesAdded.append(a)

        parameters.ALL_DEFINITIONS.resetAssignmentFlag(
            SINCE_LAST_GEOMETRY_TRANSFORMATION
        )

    def removeEdgeAssemblies(self, core):
        r"""
        remove the edge assemblies in preparation for the nodal diffusion approximation

        This makes use of the assemblies knowledge of if it is in a region that it
        needs to be removed.

        See Also
        --------
        addEdgeAssemblies : adds the edge assemblies

        """
        if core.isFullCore:
            return

        assembliesOnLowerBoundary = core.getAssembliesOnSymmetryLine(
            locations.BOUNDARY_0_DEGREES
        )
        # don't use newAssembliesAdded b/c this may be BOL cleaning of a fresh
        # case that has edge assems
        edgeAssemblies = core.getAssembliesOnSymmetryLine(
            locations.BOUNDARY_120_DEGREES
        )
        for a in edgeAssemblies:
            runLog.debug(
                "Removing edge assembly {} from {} from the reactor without discharging".format(
                    a, a.spatialLocator.getRingPos()
                )
            )
            core.removeAssembly(a, discharge=False)

        if edgeAssemblies:
            # clear list so next call knows they're gone.
            self._newAssembliesAdded = []
            for a in assembliesOnLowerBoundary:
                a.clearCache()  # clear cached area since symmetry factor will change
            # Reset the SINCE_LAST_GEOMETRY_TRANSFORMATION flag, so that subsequent geometry
            # conversions don't erroneously think they've been changed inside this geometry
            # conversion
            pDefs = parameters.ALL_DEFINITIONS.unchanged_since(NEVER)
            pDefs.setAssignmentFlag(SINCE_LAST_GEOMETRY_TRANSFORMATION)
        else:
            runLog.extra("No edge assemblies to remove")

    def scaleParamsRelatedToSymmetry(self, reactor, paramsToScaleSubset=None):
        """
        Scale volume-dependent params like power to account for cut-off edges

        These params are at half their full hex value. Scale them right before deleting their
        symmetric identicals. The two operations (scaling them and then removing others) is
        identical to combining two half-assemblies into a full one.

        See Also
        --------
        armi.reactor.converters.geometryConverter.EdgeAssemblyChanger.removeEdgeAssemblies
        armi.reactor.blocks.HexBlock.getSymmetryFactor
        """
        runLog.extra(
            "Scaling edge-assembly parameters to account for full hexes instead of two halves"
        )
        completeListOfParamsToScale = _generateListOfParamsToScale(
            reactor, paramsToScaleSubset
        )
        symmetricAssems = (
            reactor.core.getAssembliesOnSymmetryLine(locations.BOUNDARY_0_DEGREES),
            reactor.core.getAssembliesOnSymmetryLine(locations.BOUNDARY_120_DEGREES),
        )
        if not all(symmetricAssems):
            runLog.extra("No edge-assemblies found to scale parameters for.")

        for a, aSymmetric in zip(*symmetricAssems):
            for b, bSymmetric in zip(a, aSymmetric):
                _scaleParamsInBlock(b, bSymmetric, completeListOfParamsToScale)


def _generateListOfParamsToScale(r, paramsToScaleSubset):
    fluxParamsToScale = (
        r.core.getFirstBlock()
        .p.paramDefs.inCategory(Category.fluxQuantities)
        .inCategory(Category.multiGroupQuantities)
        .names
    )
    listOfVolumeIntegratedParamsToScale = (
        r.core.getFirstBlock()
        .p.paramDefs.atLocation(ParamLocation.VOLUME_INTEGRATED)
        .since(SINCE_LAST_GEOMETRY_TRANSFORMATION)
    )
    listOfVolumeIntegratedParamsToScale = listOfVolumeIntegratedParamsToScale.names
    if paramsToScaleSubset:
        listOfVolumeIntegratedParamsToScale = [
            pn
            for pn in paramsToScaleSubset
            if pn in listOfVolumeIntegratedParamsToScale
        ]
    return (listOfVolumeIntegratedParamsToScale, fluxParamsToScale)


def _scaleParamsInBlock(b, bSymmetric, completeListOfParamsToScale):
    """Scale volume-integrated params to include their identical symmetric assemblies."""
    listOfVolumeIntegratedParamsToScale, fluxParamsToScale = completeListOfParamsToScale
    for paramName in [
        pn for pn in listOfVolumeIntegratedParamsToScale if numpy.any(b.p[pn])
    ]:
        runLog.debug(
            "Scaling {} in symmetric identical assemblies".format(paramName),
            single=True,
        )
        if paramName in fluxParamsToScale:
            _scaleFluxValues(b, bSymmetric, paramName)  # updated volume weighted fluxes
        else:
            b.p[paramName] = b.p[paramName] + bSymmetric.p[paramName]


def _scaleFluxValues(b, bSymmetric, paramName):
    totalVol = b.getVolume() + bSymmetric.getVolume()

    b.p[paramName] = [
        f + fSymmetric for f, fSymmetric in zip(b.p[paramName], bSymmetric.p[paramName])
    ]

    newTotalFlux = sum(b.p[paramName]) / totalVol

    if paramName == "mgFlux":
        b.p.flux = newTotalFlux
    elif paramName == "adjMgFlux":
        b.p.fluxAdj = newTotalFlux
    elif paramName == "mgFluxGamma":
        b.p.fluxGamma = newTotalFlux
