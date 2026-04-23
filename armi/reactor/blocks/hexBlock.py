# Copyright 2026 TerraPower, LLC
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

"""The HexBlock is a vertical slice of a hexagon-shaped assembly. This is a common geometry in reactor design."""

import copy
import functools
import math
import operator
from typing import Callable, ClassVar, Optional, Tuple, Type

import numpy as np

from armi import runLog
from armi.physics.neutronics import GAMMA, NEUTRON
from armi.reactor import components, geometry, grids
from armi.reactor.blocks.block import Block
from armi.reactor.components.basicShapes import Circle, Hexagon
from armi.reactor.components.complexShapes import Helix
from armi.reactor.flags import Flags
from armi.reactor.parameters import ParamLocation
from armi.utils import hexagon, iterables, units

_PitchDefiningComponent = Optional[Tuple[Type[components.Component], ...]]


class HexBlock(Block):
    """
    Defines a Block shaped like a hexagon.

    .. impl:: ARMI has the ability to create hex shaped blocks.
        :id: I_ARMI_BLOCK_HEX
        :implements: R_ARMI_BLOCK_HEX

        This class defines hexagonal-shaped Blocks. It inherits functionality from the parent class,
        Block, and defines hexagonal-specific methods including, but not limited to, querying pin
        pitch, pin linear power densities, hydraulic diameter, and retrieving inner and outer pitch.
    """

    PITCH_COMPONENT_TYPE: ClassVar[_PitchDefiningComponent] = (components.Hexagon,)

    def __init__(self, name, height=1.0):
        Block.__init__(self, name, height)

    def coords(self):
        """
        Returns the coordinates of the block.

        .. impl:: Coordinates of a block are queryable.
            :id: I_ARMI_BLOCK_POSI2
            :implements: R_ARMI_BLOCK_POSI

            Calls to the :py:meth:`~armi.reactor.grids.locations.IndexLocation.getGlobalCoordinates`
            method of the block's ``spatialLocator`` attribute, which recursively calls itself on
            all parents of the block to get the coordinates of the block's centroid in 3D cartesian
            space.

            Will additionally adjust the x and y coordinates based on the block parameters
            ``displacementX`` and ``displacementY``.
        """
        x, y, _z = self.spatialLocator.getGlobalCoordinates()
        x += self.p.displacementX * 100.0
        y += self.p.displacementY * 100.0
        return (
            round(x, units.FLOAT_DIMENSION_DECIMALS),
            round(y, units.FLOAT_DIMENSION_DECIMALS),
        )

    def createHomogenizedCopy(self, pinSpatialLocators=False):
        """
        Create a new homogenized copy of a block that is less expensive than a full deepcopy.

        .. impl:: Block compositions can be homogenized.
            :id: I_ARMI_BLOCK_HOMOG
            :implements: R_ARMI_BLOCK_HOMOG

            This method creates and returns a homogenized representation of itself in the form of a
            new Block. The homogenization occurs in the following manner. A single Hexagon Component
            is created and added to the new Block. This Hexagon Component is given the
            :py:class:`armi.materials.mixture._Mixture` material and a volume averaged temperature
            (``getAverageTempInC``). The number densities of the original Block are also stored on
            this new Component (:need:`I_ARMI_CMP_GET_NDENS`). Several parameters from the original
            block are copied onto the homogenized block (e.g., macros, lumped fission products,
            burnup group, number of pins, and spatial grid).

        Notes
        -----
        This can be used to improve performance when a new copy of a reactor needs to be built, but
        the full detail of the block (including component geometry, material, number density, etc.)
        is not required for the targeted physics solver being applied to the new reactor model.

        The main use case is for the uniform mesh converter (UMC). Frequently, a deterministic
        neutronics solver will require a uniform mesh reactor, which is produced by the UMC. Many
        deterministic solvers for fast spectrum reactors will also treat the individual blocks as
        homogenized mixtures. Since the neutronics solver does not need to know about the geometric
        and material details of the individual child components within a block, we can save
        significant effort while building the uniform mesh reactor with the UMC by omitting this
        detailed data and only providing the necessary level of detail for the uniform mesh reactor:
        number densities on each block.

        Individual components within a block can have different temperatures, and this can affect
        cross sections. This temperature variation is captured by the lattice physics module. As
        long as temperature distribution is correctly captured during cross section generation, it
        does not need to be transferred to the neutronics solver directly through this copy
        operation.

        If you make a new block, you must add it to an assembly and a reactor.

        Returns
        -------
        b : A homogenized block containing a single Hexagon Component that contains an average
            temperature and the number densities from the original block.

        See Also
        --------
        armi.reactor.converters.uniformMesh.UniformMeshGeometryConverter.makeAssemWithUniformMesh
        """
        b = self.__class__(self.getName(), height=self.getHeight())
        b.setType(self.getType(), self.p.flags)

        # assign macros and LFP
        b.macros = self.macros
        b._lumpedFissionProducts = self._lumpedFissionProducts
        b.p.envGroup = self.p.envGroup

        hexComponent = Hexagon(
            "homogenizedHex",
            "_Mixture",
            self.getAverageTempInC(),
            self.getAverageTempInC(),
            self._pitchDefiningComponent[1],
        )
        hexComponent.setNumberDensities(self.getNumberDensities())
        b.add(hexComponent)

        b.p.nPins = self.p.nPins
        if pinSpatialLocators:
            # create a null component with cladding flags and spatialLocator from source block's
            # clad components in case pin locations need to be known for physics solver
            if self.hasComponents(Flags.CLAD):
                cladComponents = self.getComponents(Flags.CLAD)
                for i, clad in enumerate(cladComponents):
                    pinComponent = Circle(
                        f"voidPin{i}",
                        "Void",
                        self.getAverageTempInC(),
                        self.getAverageTempInC(),
                        0.0,
                    )
                    pinComponent.setType("pin", Flags.CLAD)
                    pinComponent.spatialLocator = copy.deepcopy(clad.spatialLocator)
                    if isinstance(pinComponent.spatialLocator, grids.MultiIndexLocation):
                        for i1, i2 in zip(list(pinComponent.spatialLocator), list(clad.spatialLocator)):
                            i1.associate(i2.grid)
                    pinComponent.setDimension("mult", clad.getDimension("mult"))
                    b.add(pinComponent)

        if self.spatialGrid is not None:
            b.spatialGrid = self.spatialGrid

        return b

    def getMaxArea(self):
        """Compute the max area of this block if it was totally full."""
        pitch = self.getPitch()
        if not pitch:
            return 0.0
        return hexagon.area(pitch)

    def getDuctIP(self):
        """Returns the duct IP dimension."""
        duct = self.getComponent(Flags.DUCT, exact=True)
        return duct.getDimension("ip")

    def getDuctOP(self):
        """Returns the duct OP dimension."""
        duct = self.getComponent(Flags.DUCT, exact=True)
        return duct.getDimension("op")

    def setPinPowers(self, powers, powerKeySuffix=""):
        """
        Updates the pin linear power densities of this block.

        The linear densities are represented by the ``linPowByPin`` parameter.

        It is expected that the ordering of ``powers`` is consistent with :meth:`getPinLocations`. That helps ensure
        alignment with component-level look ups like :meth:`~armi.reactor.components.Circle.getPinIndices`.

        The ``linPowByPin`` parameter can be directly assigned to instead of using this method if the multiplicity of
        the pins in the block is equal to the number of pins in the block.

        Parameters
        ----------
        powers : list of floats, required
            The block-level pin linear power densities. ``powers[i]`` represents the average linear power density of pin
            ``i`` location at ``self.getPinLocations()[i]``. The units of linear power density is watts/cm (i.e., watts
            produced per cm of pin length).
        powerKeySuffix: str, optional
            Must be either an empty string, :py:const:`NEUTRON <armi.physics.neutronics.const.NEUTRON>`, or
            :py:const:`GAMMA <armi.physics.neutronics.const.GAMMA>`. Defaults to empty string.
        """
        numPins = self.getNumPins()
        if not numPins or numPins != len(powers):
            raise ValueError(
                f"Invalid power data for {self} with {numPins} pins. Got {len(powers)} entries in powers: {powers}"
            )

        powerKey = f"linPowByPin{powerKeySuffix}"
        self.p[powerKey] = powers

        # If using the *powerKeySuffix* parameter, we also need to set total power, which is sum of neutron and gamma
        # powers. We assume that a solo gamma calculation to set total power does not make sense.
        if powerKeySuffix:
            if powerKeySuffix == GAMMA:
                if self.p[f"linPowByPin{NEUTRON}"] is None:
                    msg = f"Neutron power has not been set yet. Cannot set total power for {self}."
                    raise UnboundLocalError(msg)
                self.p.linPowByPin = self.p[f"linPowByPin{NEUTRON}"] + self.p[powerKey]
            else:
                self.p.linPowByPin = self.p[powerKey]

    def rotate(self, rad: float):
        """
        Rotates a block's spatially varying parameters by a specified angle in the counter-clockwise direction.

        The parameters must have a ParamLocation of either CORNERS or EDGES and must be a Python list of length 6 in
        order to be eligible for rotation; all parameters that do not meet these two criteria are not rotated.

        .. impl:: Rotating a hex block updates parameters on the boundary, the orientation
            parameter, and the spatial coordinates on contained objects.
            :id: I_ARMI_ROTATE_HEX_BLOCK
            :implements: R_ARMI_ROTATE_HEX

            This method rotates a block on a hexagonal grid, conserving the 60-degree symmetry of the grid. It first
            determines how many rotations the block will undergo based on the 60-degree hex grid. Then it uses that
            "rotation number" to do a few things: reset the orientation parameter, rotate the children, and rotate the
            boundary parameters. It also sets the "displacement in X" and "displacement in Y" parameters.

        Parameters
        ----------
        rad: float, required
            Angle of counter-clockwise rotation in units of radians. Rotations must be in 60-degree increments
            (i.e., PI/3, 2 * PI/3, PI, 4 * PI/3, 5 * PI/3, and 2 * PI).
        """
        rotNum = round((rad % (2 * math.pi)) / math.radians(60))
        self._rotateChildLocations(rad, rotNum)
        if self.p.orientation is None:
            self.p.orientation = np.array([0.0, 0.0, 0.0])
        self.p.orientation[2] += rotNum * 60.0
        self._rotateBoundaryParameters(rotNum)
        self._rotateDisplacement(rad)

    def _rotateChildLocations(self, radians: float, rotNum: int):
        """Update spatial locators for children."""
        if self.spatialGrid is None:
            return

        locationRotator = functools.partial(self.spatialGrid.rotateIndex, rotations=rotNum)
        rotationMatrix = np.array([[math.cos(radians), -math.sin(radians)], [math.sin(radians), math.cos(radians)]])
        for c in self:
            if isinstance(c.spatialLocator, grids.MultiIndexLocation):
                newLocations = list(map(locationRotator, c.spatialLocator))
                c.spatialLocator = grids.MultiIndexLocation(self.spatialGrid)
                c.spatialLocator.extend(newLocations)
            elif isinstance(c.spatialLocator, grids.CoordinateLocation):
                oldCoords = c.spatialLocator.getLocalCoordinates()
                newXY = rotationMatrix.dot(oldCoords[:2])
                newLocation = grids.CoordinateLocation(newXY[0], newXY[1], oldCoords[2], self.spatialGrid)
                c.spatialLocator = newLocation
            elif isinstance(c.spatialLocator, grids.IndexLocation):
                c.spatialLocator = locationRotator(c.spatialLocator)
            elif c.spatialLocator is not None:
                msg = f"{c} on {self} has an invalid spatial locator for rotation: {c.spatialLocator}"
                runLog.error(msg)
                raise TypeError(msg)

    def _rotateBoundaryParameters(self, rotNum: int):
        """Rotate any parameters defined on the corners or edge of bounding hexagon.

        Parameters
        ----------
        rotNum : int
            Rotation number between zero and five, inclusive, specifying how many rotations have taken place.
        """
        names = self.p.paramDefs.atLocation(ParamLocation.CORNERS).names
        names += self.p.paramDefs.atLocation(ParamLocation.EDGES).names
        for name in names:
            original = self.p[name]
            if isinstance(original, (list, np.ndarray)):
                if len(original) == 6:
                    # Rotate by making the -rotNum item be first
                    self.p[name] = iterables.pivot(original, -rotNum)
                elif len(original) == 0:
                    # Hasn't been defined yet, no warning needed.
                    pass
                else:
                    msg = (
                        "No rotation method defined for spatial parameters that aren't defined "
                        f"once per hex edge/corner. No rotation performed on {name}"
                    )
                    runLog.warning(msg)
            elif isinstance(original, (int, float)):
                # this is a scalar and there shouldn't be any rotation.
                pass
            elif original is None:
                # param is not set yet. no rotations as well.
                pass
            else:
                raise TypeError(
                    f"b.rotate() method received unexpected data type for {name} on block {self}\n"
                    + f"expected list, np.ndarray, int, or float. received {original}"
                )

    def _rotateDisplacement(self, rad: float):
        # This specifically uses the .get() functionality to avoid an error if this parameter does not exist.
        dispx = self.p.get("displacementX")
        dispy = self.p.get("displacementY")
        if (dispx is not None) and (dispy is not None):
            self.p.displacementX = dispx * math.cos(rad) - dispy * math.sin(rad)
            self.p.displacementY = dispx * math.sin(rad) + dispy * math.cos(rad)

    def verifyBlockDims(self):
        """Perform some checks on this type of block before it is assembled."""
        try:
            wireComp = self.getComponent(Flags.WIRE, quiet=True)  # Quiet because None case is checked for below
            ductComps = self.getComponents(Flags.DUCT)
            cladComp = self.getComponent(Flags.CLAD, quiet=True)  # Quiet because None case is checked for below
        except ValueError:
            # there are probably more that one clad/wire, so we really dont know what this block looks like
            runLog.info(f"Block design {self} is too complicated to verify dimensions. Make sure they are correct!")
            return

        # check wire wrap in contact with clad
        if cladComp is not None and wireComp is not None:
            wwCladGap = self.getWireWrapCladGap(cold=True)
            if round(wwCladGap, 6) != 0.0:
                runLog.warning(
                    "The gap between wire wrap and clad in block {} was {} cm. Expected 0.0.".format(self, wwCladGap),
                    single=True,
                )

        # check clad duct overlap
        pinToDuctGap = self.getPinToDuctGap(cold=True)
        # Allow for some tolerance; user input precision may lead to slight negative gaps
        if pinToDuctGap is not None and pinToDuctGap < -0.005:
            raise ValueError(
                "Gap between pins and duct is {0:.4f} cm in {1}. Make more room.".format(pinToDuctGap, self)
            )
        elif pinToDuctGap is None:
            # only produce a warning if pin or clad are found, but not all of pin, clad and duct. We may need to tune
            # this logic a bit
            ductComp = next(iter(ductComps), None)
            if (cladComp is not None or wireComp is not None) and any(
                [c is None for c in (wireComp, cladComp, ductComp)]
            ):
                runLog.warning("Some component was missing in {} so pin-to-duct gap not calculated".format(self))

    def getPinToDuctGap(self, cold=False):
        """
        Returns the distance in cm between the outer most pin and the duct in a block.

        Parameters
        ----------
        cold : boolean
            Determines whether the results should be cold or hot dimensions.

        Returns
        -------
        pinToDuctGap : float
            Returns the diameteral gap between the outer most pins in a hex pack to the duct inner face to face in cm.
        """
        wire = self.getComponent(Flags.WIRE, quiet=True)  # Quiet because None case is checked for below
        ducts = sorted(self.getChildrenWithFlags(Flags.DUCT))
        duct = None
        if any(ducts):
            duct = ducts[0]
            if not isinstance(duct, components.Hexagon):
                # getPinCenterFlatToFlat only works for hexes
                # inner most duct might be circle or some other shape
                duct = None
            elif isinstance(duct, components.HoledHexagon):
                # has no ip and is circular on inside so following
                # code will not work
                duct = None
        clad = self.getComponent(Flags.CLAD, quiet=True)  # Quiet because None case is checked for below
        if any(c is None for c in (duct, wire, clad)):
            return None

        # NOTE: If nRings was a None, this could be for a non-hex packed fuel assembly see thermal hydraulic design
        # basis for description of equation
        pinCenterFlatToFlat = self.getPinCenterFlatToFlat(cold=cold)
        pinOuterFlatToFlat = (
            pinCenterFlatToFlat + clad.getDimension("od", cold=cold) + 2.0 * wire.getDimension("od", cold=cold)
        )
        ductMarginToContact = duct.getDimension("ip", cold=cold) - pinOuterFlatToFlat
        pinToDuctGap = ductMarginToContact / 2.0

        return pinToDuctGap

    def getRotationNum(self) -> int:
        """Get index 0 through 5 indicating number of rotations counterclockwise around the z-axis."""
        # assume rotation only in Z
        return np.rint(self.p.orientation[2] / 360.0 * 6) % 6

    def setRotationNum(self, rotNum: int):
        """
        Set orientation based on a number 0 through 5 indicating number of rotations
        counterclockwise around the z-axis.
        """
        self.p.orientation[2] = 60.0 * rotNum

    def getSymmetryFactor(self):
        """
        Return a factor between 1 and N where 1/N is how much cut-off by symmetry lines this mesh cell is.

        Reactor-level meshes have symmetry information so we have a reactor for this to work. That is why it is not
        implemented on the grid/locator level.

        When edge-assemblies are included on both edges (i.e. MCNP or DIF3D-FD 1/3-symmetric cases), the edge assemblies
        have symmetry factors of 2.0. Otherwise (DIF3D-nodal) there's a full assembly on the bottom edge (overhanging)
        and no assembly at the top edge so the ones at the bottom are considered full (symmetryFactor=1).

        If this block is not in any grid at all, then there can be no symmetry so return 1.
        """
        try:
            symmetry = self.parent.spatialLocator.grid.symmetry
        except Exception:
            return 1.0
        if symmetry.domain == geometry.DomainType.THIRD_CORE and symmetry.boundary == geometry.BoundaryType.PERIODIC:
            indices = self.spatialLocator.getCompleteIndices()
            if indices[0] == 0 and indices[1] == 0:
                # central location
                return 3.0
            else:
                symmetryLine = self.core.spatialGrid.overlapsWhichSymmetryLine(indices)
                # Detect if upper edge assemblies are included. Doing this is the only way to know definitively whether
                # or not the edge assemblies are half-assems or full. Seeing the first one is the easiest way to detect
                # them. Check it last in the and statement so we don't waste time doing it.
                upperEdgeLoc = self.core.spatialGrid[-1, 2, 0]
                if symmetryLine in [
                    grids.BOUNDARY_0_DEGREES,
                    grids.BOUNDARY_120_DEGREES,
                ] and bool(self.core.childrenByLocator.get(upperEdgeLoc)):
                    return 2.0
        return 1.0

    def autoCreateSpatialGrids(self, systemSpatialGrid=None):
        """
        Given a block without a spatialGrid, create a spatialGrid and give its children the corresponding
        spatialLocators (if it is a simple block).

        In this case, a simple block would be one that has either multiplicity of components equal to 1 or N but no
        other multiplicities. Also, this should only happen when N fits exactly into a given number of hex rings.
        Otherwise, do not create a grid for this block.

        Parameters
        ----------
        systemSpatialGrid : Grid, optional
            Spatial Grid of the system-level parent of this Assembly that contains this Block.

        Notes
        -----
        When a hex grid has another hex grid nested inside it, the nested grid has the opposite orientation (corners vs
        flats up). This method takes care of that.

        If components inside this block are multiplicity 1, they get a single locator at the center of the grid cell. If
        the multiplicity is greater than 1, all the components are added to a multiIndexLocation on the hex grid.

        Raises
        ------
        ValueError
            If the multiplicities of the block are not only 1 or N or if generated ringNumber leads to more positions
            than necessary.
        """
        # not necessary
        if self.spatialGrid is not None:
            return

        # Check multiplicities
        mults = {c.getDimension("mult") for c in self.iterComponents()}

        # Do some validation: Should we try to create a spatial grid?
        multz = {float(m) for m in mults}
        if len(multz) == 1 and 1.0 in multz:
            runLog.extra(
                f"Block {self.p.type} does not need a spatial grid: multiplicities are all 1.",
                single=True,
            )
            return
        elif len(multz) != 2 or 1.0 not in multz:
            runLog.extra(
                f"Could not create a spatialGrid for block {self.p.type}, multiplicities are not {{1, N}} "
                f"they are {mults}",
                single=True,
            )
            return

        # build the grid, from pitch and orientation
        if isinstance(systemSpatialGrid, grids.HexGrid):
            cornersUp = not systemSpatialGrid.cornersUp
        else:
            cornersUp = False

        grid = grids.HexGrid.fromPitch(
            self.getPinPitch(cold=True),
            numRings=0,
            armiObject=self,
            cornersUp=cornersUp,
        )

        ringNumber = hexagon.numRingsToHoldNumCells(self.getNumPins())
        numLocations = 0
        for ring in range(ringNumber):
            numLocations = numLocations + hexagon.numPositionsInRing(ring + 1)

        if numLocations != self.getNumPins():
            raise ValueError(
                "Cannot create spatialGrid, number of locations in rings {} not equal to pin number {}".format(
                    numLocations, self.getNumPins()
                )
            )

        # set the spatial position of the sub-block components
        spatialLocators = grids.MultiIndexLocation(grid=grid)
        for ring in range(ringNumber):
            for pos in range(grid.getPositionsInRing(ring + 1)):
                i, j = grid.getIndicesFromRingAndPos(ring + 1, pos + 1)
                spatialLocators.append(grid[i, j, 0])

        # finally, fill the spatial grid, and put the sub-block components on it
        if self.spatialGrid is None:
            self.spatialGrid = grid
            for c in self:
                if c.getDimension("mult") > 1:
                    c.spatialLocator = spatialLocators
                elif c.getDimension("mult") == 1:
                    c.spatialLocator = grids.CoordinateLocation(0.0, 0.0, 0.0, grid)

    def assignPinIndices(self):
        """Assign pin indices for pin components on the block."""
        if self.spatialGrid is None:
            return
        locations = self.getPinLocations()
        if not locations:
            return
        # Clear out any previous values. If your block is built with one ordering
        # and then sorted, things that used to have pin indices may now have invalid
        # pin indices. Wipe them out just to be safe
        for c in self:
            c.p.pinIndices = None
        ijGetter = operator.attrgetter("i", "j")
        allIJ: tuple[tuple[int, int]] = tuple(map(ijGetter, locations))
        # Flags for components that we want to set this parameter
        # Usually things are linked to one of these "important" flags, like
        # a cladding component having linked dimensions to a fuel component
        primaryFlags = (Flags.FUEL, Flags.CONTROL, Flags.SHIELD)
        withPinIndices: list[components.Component] = []
        for c in self.iterChildrenWithFlags(primaryFlags):
            if self._setPinIndices(c, ijGetter, allIJ):
                withPinIndices.append(c)
        # Iterate over every other thing on the grid and make sure
        # 1) it share a lattice site with something that has pin indices, or
        # 2) it itself declares the pin indices
        for c in self:
            if c.p.pinIndices is not None:
                continue
            # Does anything with pin indices share this lattice site?
            if any(other.spatialLocator == c.spatialLocator for other in withPinIndices):
                continue
            if self._setPinIndices(c, ijGetter, allIJ):
                withPinIndices.append(c)

    @staticmethod
    def _setPinIndices(
        c: components.Component, ijGetter: Callable[[grids.IndexLocation], tuple[int, int]], allIJ: tuple[int, int]
    ):
        localLocations = c.spatialLocator
        if isinstance(localLocations, grids.MultiIndexLocation):
            localIJ = list(map(ijGetter, localLocations))
        # CoordinateLocations do not live on the grid, by definition
        elif isinstance(localLocations, grids.CoordinateLocation):
            return False
        elif isinstance(localLocations, grids.IndexLocation):
            localIJ = [ijGetter(localLocations)]
        else:
            return False
        localIndices = list(map(allIJ.index, localIJ))
        c.p.pinIndices = localIndices
        return True

    def getPinCenterFlatToFlat(self, cold=False):
        """Return the flat-to-flat distance between the centers of opposing pins in the outermost ring."""
        clad = self.getComponent(Flags.CLAD)
        nRings = hexagon.numRingsToHoldNumCells(clad.getDimension("mult"))
        pinPitch = self.getPinPitch(cold=cold)
        pinCenterCornerToCorner = 2 * (nRings - 1) * pinPitch
        pinCenterFlatToFlat = math.sqrt(3.0) / 2.0 * pinCenterCornerToCorner
        return pinCenterFlatToFlat

    def hasPinPitch(self):
        """Return True if the block has enough information to calculate pin pitch."""
        try:
            return (self.getComponent(Flags.CLAD, quiet=True) is not None) and (
                self.getComponent(Flags.WIRE, quiet=True) is not None
            )
        except ValueError:
            # not well defined pitch due to multiple pin and/or wire components
            return False

    def getPinPitch(self, cold=False):
        """
        Get the pin pitch in cm.

        Assumes that the pin pitch is defined entirely by contacting cladding tubes and wire wraps.
        Grid spacers not yet supported.

        Parameters
        ----------
        cold : boolean
            Determines whether the dimensions should be cold or hot

        Returns
        -------
        pinPitch : float
            pin pitch in cm
        """
        try:
            clad = self.getComponent(Flags.CLAD, quiet=True)  # Quiet because None case is checked for below
            wire = self.getComponent(Flags.WIRE, quiet=True)  # Quiet because None case is checked for below
        except ValueError:
            raise ValueError(f"Block {self} has multiple clad and wire components, so pin pitch is not well-defined.")

        if wire and clad:
            return clad.getDimension("od", cold=cold) + wire.getDimension("od", cold=cold)
        else:
            raise ValueError(f"Cannot get pin pitch in {self} because it does not have a wire and a clad")

    def getWettedPerimeter(self):
        """
        Return the total wetted perimeter of the block in cm.

        Notes
        -----
        Please be aware that this method is specific to Fast Reactors, and probably even Sodium Fast Reactors. This is
        obviously an awkward design choice, and we hope to improve upon it soon.
        """
        # flags pertaining to hexagon components where the interior of the hexagon is wetted
        wettedHollowHexagonComponentFlags = (
            Flags.DUCT,
            Flags.GRID_PLATE,
            Flags.INLET_NOZZLE,
            Flags.HANDLING_SOCKET,
            Flags.DUCT | Flags.DEPLETABLE,
            Flags.GRID_PLATE | Flags.DEPLETABLE,
            Flags.INLET_NOZZLE | Flags.DEPLETABLE,
            Flags.HANDLING_SOCKET | Flags.DEPLETABLE,
        )

        # flags pertaining to circular pin components where the exterior of the circle is wetted
        wettedPinComponentFlags = (
            Flags.CLAD,
            Flags.WIRE,
        )

        # flags pertaining to components where both the interior and exterior are wetted
        wettedHollowComponentFlags = (
            Flags.DUCT | Flags.INNER,
            Flags.DUCT | Flags.INNER | Flags.DEPLETABLE,
        )

        # obtain all wetted components based on type
        wettedHollowHexagonComponents = []
        for flag in wettedHollowHexagonComponentFlags:
            c = self.getComponent(flag, exact=True)
            wettedHollowHexagonComponents.append(c) if c else None

        wettedPinComponents = []
        for flag in wettedPinComponentFlags:
            comps = self.getComponents(flag)
            wettedPinComponents.extend(comps)

        wettedHollowCircleComponents = []
        wettedHollowHexComponents = []
        for flag in wettedHollowComponentFlags:
            c = self.getComponent(flag, exact=True)
            if isinstance(c, Hexagon):
                wettedHollowHexComponents.append(c) if c else None
            else:
                wettedHollowCircleComponents.append(c) if c else None

        # calculate wetted perimeters according to their geometries
        # hollow hexagon = 6 * ip / sqrt(3)
        wettedHollowHexagonPerimeter = 0.0
        for c in wettedHollowHexagonComponents:
            wettedHollowHexagonPerimeter += 6 * c.getDimension("ip") / math.sqrt(3) if c else 0.0

        # solid circle = NumPins * pi * (Comp Diam + Wire Diam)
        wettedPinPerimeter = 0.0
        for c in wettedPinComponents:
            correctionFactor = 1.0
            if isinstance(c, Helix):
                # account for the helical wire wrap
                correctionFactor = np.hypot(
                    1.0,
                    math.pi * c.getDimension("helixDiameter") / c.getDimension("axialPitch"),
                )
            compWettedPerim = c.getDimension("od") * correctionFactor * c.getDimension("mult") * math.pi
            wettedPinPerimeter += compWettedPerim

        # hollow circle = (id + od) * pi
        wettedHollowCirclePerimeter = 0.0
        for c in wettedHollowCircleComponents:
            wettedHollowCirclePerimeter += c.getDimension("id") + c.getDimension("od") if c else 0.0
        wettedHollowCirclePerimeter *= math.pi

        # hollow hexagon = 6 * (ip + op) / sqrt(3)
        wettedHollowHexPerimeter = 0.0
        for c in wettedHollowHexComponents:
            wettedHollowHexPerimeter += c.getDimension("ip") + c.getDimension("op") if c else 0.0
        wettedHollowHexPerimeter *= 6 / math.sqrt(3)

        return (
            wettedHollowHexagonPerimeter + wettedPinPerimeter + wettedHollowCirclePerimeter + wettedHollowHexPerimeter
        )

    def getFlowArea(self):
        """Return the total flowing coolant area of the block in cm^2."""
        area = self.getComponent(Flags.COOLANT, exact=True).getArea()
        for c in self.getComponents(Flags.INTERDUCTCOOLANT, exact=True):
            area += c.getArea()

        return area

    def getHydraulicDiameter(self):
        """
        Return the hydraulic diameter in this block in cm.

        Hydraulic diameter is 4A/P where A is the flow area and P is the wetted perimeter. In a hex assembly, the wetted
        perimeter includes the cladding, the wire wrap, and the inside of the duct. The flow area is the inner area of
        the duct minus the area of the pins and the wire.
        """
        return 4.0 * self.getFlowArea() / self.getWettedPerimeter()
