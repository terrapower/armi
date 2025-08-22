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
Assemblies are collections of Blocks.

Generally, Blocks are stacked from bottom to top.
"""

import copy
import math
import pickle
from collections.abc import Iterable
from random import randint
from typing import ClassVar, Optional, Type

import numpy as np
from scipy import interpolate

from armi import runLog
from armi.materials.material import Fluid
from armi.reactor import assemblyParameters, blocks, composites, grids
from armi.reactor.flags import Flags, TypeSpec
from armi.reactor.parameters import ParamLocation
from armi.reactor.spentFuelPool import SpentFuelPool


class Assembly(composites.Composite):
    """
    A single assembly in a reactor made up of blocks built from the bottom up.
    Append blocks to add them up. Index blocks with 0 being the bottom.
    """

    _BLOCK_TYPE: ClassVar[Optional[Type[blocks.Block]]] = None
    pDefs = assemblyParameters.getAssemblyParameterDefinitions()

    # For assemblies coming in from the database, waiting to be loaded to their old
    # position. This is a necessary distinction, since we need to make sure that a bunch
    # of fuel management stuff doesn't treat its re-placement into the core as a new move
    DATABASE = "database"
    LOAD_QUEUE = "LoadQueue"
    SPENT_FUEL_POOL = "SFP"
    NOT_IN_CORE = [LOAD_QUEUE, SPENT_FUEL_POOL]

    def __init__(self, typ, assemNum=None):
        """
        Parameters
        ----------
        typ : str
            Name of assembly design (e.g. the name from the blueprints input file).
        assemNum : int, optional
            The unique ID number of this assembly. If None is provided, we generate a
            random int. This makes it clear that it is a placeholder. When an assembly with
            a negative ID is placed into a Reactor, it will be given a new, positive ID.
        """
        # If no assembly number is provided, generate a random number as a placeholder.
        if assemNum is None:
            assemNum = randint(-9000000000000, -1)
        name = self.makeNameFromAssemNum(assemNum)
        composites.Composite.__init__(self, name)
        self.p.assemNum = assemNum
        self.setType(typ)
        self._current = 0  # for iterating
        self.p.buLimit = self.getMaxParam("buLimit")
        self.lastLocationLabel = self.LOAD_QUEUE

    def __repr__(self):
        msg = "<{typeName} Assembly {name} at {loc}>".format(
            name=self.getName(), loc=self.getLocation(), typeName=self.getType()
        )
        return msg

    def __lt__(self, other):
        """
        Compare two assemblies by location.

        Notes
        -----
        As with other ArmiObjects, Assemblies are sorted based on location. Assemblies are more
        permissive in the grid consistency checks to accommodate situations where assemblies might be
        children of the same Core, but not in the same grid as each other (like in the spent fuel
        pool). In these situations, the operator returns ``False``.  This behavior may lead to some
        strange sorting behavior when two or more Assemblies are being compared that do not live in
        the same grid.

        See Also
        --------
        armi.reactor.composites.ArmiObject.__lt__
        """
        try:
            return composites.ArmiObject.__lt__(self, other)
        except ValueError:
            return False

    def renameBlocksAccordingToAssemblyNum(self):
        """
        Updates the names of all blocks to comply with the assembly number.

        Useful after an assembly number/name has been loaded from a snapshot and you
        want to update all block names to be consistent.

        It may be better to store block numbers on each block as params. A database that
        can hold strings would be even better.

        Notes
        -----
        You must run armi.reactor.reactors.Reactor.regenAssemblyLists after calling this.
        """
        assemNum = self.getNum()
        for bi, b in enumerate(self):
            b.setName(b.makeName(assemNum, bi))

    @staticmethod
    def makeNameFromAssemNum(assemNum):
        """
        Set the name of this assembly (and the containing blocks) based on an assemNum.

        AssemNums are like serial numbers for assemblies.
        """
        return "A{0:04d}".format(int(assemNum))

    def renumber(self, newNum):
        """
        Change the assembly number of this assembly.

        And handle the downstream impacts of changing the name of this Assembly and all
        of the Blocks within this Assembly.

        Parameters
        ----------
        newNum : int
            The new Assembly number.
        """
        self.p.assemNum = int(newNum)
        self.name = self.makeNameFromAssemNum(self.p.assemNum)
        self.renameBlocksAccordingToAssemblyNum()

    def makeUnique(self):
        """
        Function to make an assembly unique by getting a new assembly number.

        This also adjusts the assembly's blocks IDs. This is necessary when using
        ``deepcopy`` to get a unique ``assemNum`` since a deepcopy implies it would
        otherwise have been the same object.
        """
        # Default to a random negative assembly number (unique enough)
        self.p.assemNum = randint(-9000000000000, -1)
        self.renumber(self.p.assemNum)

    def _checkPotentialChild(self, obj: blocks.Block, action: str = "add"):
        """An internal helper method to ensure the Block type is valid for this Assembly."""
        if self._BLOCK_TYPE is None or isinstance(obj, self._BLOCK_TYPE):
            # this is the right Block, pass on
            return

        # if we got here, this Block is not the right type for this Assembly
        msg = f"Cannot {action} {obj} to this Assembly, it is not a {self._BLOCK_TYPE}."
        runLog.error(msg)
        raise TypeError(msg)

    def add(self, obj: blocks.Block):
        """
        Add an object to this assembly.

        The simple act of adding a block to an assembly fully defines the location of
        the block in 3-D.

        .. impl:: Assemblies are made up of type Block.
            :id: I_ARMI_ASSEM_BLOCKS
            :implements: R_ARMI_ASSEM_BLOCKS

            Adds a unique Block to the top of the Assembly. If the Block already
            exists in the Assembly, an error is raised in
            :py:meth:`armi.reactor.composites.Composite.add`.
            The spatialLocator of the Assembly is updated to account for
            the new Block. In ``reestablishBlockOrder``, the Assembly spatialGrid
            is reinitialized and Block-wise spatialLocator and name objects
            are updated. The axial mesh and other Block geometry parameters are
            updated in ``calculateZCoords``.
        """
        self._checkPotentialChild(obj, "add")
        composites.Composite.add(self, obj)
        obj.spatialLocator = self.spatialGrid[0, 0, len(self) - 1]

        # more work is needed, make a new mesh
        self.reestablishBlockOrder()
        self.calculateZCoords()

    def insert(self, index, obj):
        """Insert an object at a given index position with the assembly."""
        self._checkPotentialChild(obj, "insert")
        composites.Composite.insert(self, index, obj)
        obj.spatialLocator = self.spatialGrid[0, 0, index]

    def moveTo(self, locator):
        """Move an assembly somewhere else."""
        oldSymmetryFactor = self.getSymmetryFactor()
        composites.Composite.moveTo(self, locator)
        if self.lastLocationLabel != self.DATABASE:
            self.p.numMoves += 1
            self.p.daysSinceLastMove = 0.0
        self.parent.childrenByLocator[locator] = self
        # symmetry may have changed (either moving on or off of symmetry line)
        self.clearCache()
        self.scaleParamsToNewSymmetryFactor(oldSymmetryFactor)

    def scaleParamsToNewSymmetryFactor(self, oldSymmetryFactor):
        scalingFactor = oldSymmetryFactor / self.getSymmetryFactor()
        if scalingFactor == 1:
            return

        volIntegratedParamsToScale = self[0].p.paramDefs.atLocation(ParamLocation.VOLUME_INTEGRATED)
        for b in self:
            for param in volIntegratedParamsToScale:
                name = param.name
                if b.p[name] is None or isinstance(b.p[name], str):
                    continue
                elif isinstance(b.p[name], Iterable):
                    b.p[name] = [value * scalingFactor for value in b.p[name]]
                else:
                    # numpy array or other
                    b.p[name] = b.p[name] * scalingFactor

    def getNum(self):
        """Return unique integer for this assembly."""
        return int(self.p.assemNum)

    def getLocation(self):
        """
        Get string label representing this object's location.

        .. impl:: Assembly location is retrievable.
            :id: I_ARMI_ASSEM_POSI0
            :implements: R_ARMI_ASSEM_POSI

            This method returns a string label indicating the location
            of an Assembly. There are three options: 1) the Assembly
            is not within a Core object and is interpreted as in the
            "load queue"; 2) the Assembly is within the spent fuel pool;
            3) the Assembly is within a Core object, so it has a physical
            location within the Core.
        """
        # just use ring and position, not axial (which is 0)
        if not self.parent:
            return self.LOAD_QUEUE
        elif isinstance(self.parent, SpentFuelPool):
            return self.SPENT_FUEL_POOL
        return self.parent.spatialGrid.getLabel(self.spatialLocator.getCompleteIndices()[:2])

    def coords(self):
        """Return the location of the assembly in the plane using cartesian global coordinates.

        .. impl:: Assembly coordinates are retrievable.
            :id: I_ARMI_ASSEM_POSI1
            :implements: R_ARMI_ASSEM_POSI

            In this method, the spatialLocator of an Assembly is leveraged to return its physical
            (x,y) coordinates in cm.
        """
        x, y, _z = self.spatialLocator.getGlobalCoordinates()
        return (x, y)

    def getArea(self):
        """
        Return the area of the assembly by looking at its first block.

        The assumption is that all blocks in an assembly have the same area. Calculate the total
        assembly volume in cm^3.
        """
        try:
            return self[0].getArea()
        except IndexError:
            runLog.warning(f"{self} has no blocks and therefore no area.")
            return None

    def getVolume(self):
        """Calculate the total assembly volume in cm^3."""
        return self.getArea() * self.getTotalHeight()

    def getPinPlenumVolumeInCubicMeters(self) -> float:
        """
        Return the total volume of the plenum for an assembly in m^3.

        Notes
        -----
        If there is no plenum blocks in the assembly, a plenum volume of 0.0 is returned.

        Warning
        -------
        This is a bit design-specific for pinned assemblies.

        Returns
        -------
        float: Total plenum volume for an assembly.
        """
        plenumVolume = 0.0
        for b in self.iterChildrenWithFlags(Flags.PLENUM):
            length = b.getHeight()
            for c in b.iterChildrenWithFlags(Flags.CLAD):
                cladId = c.getDimension("id")
                plenumVolume += math.pi * (cladId / 2.0) ** 2.0 * length
        # convert vol from cm^3 to m^3
        plenumVolume *= 1e-6
        return plenumVolume

    def getAveragePlenumTemperature(self):
        """Return the average of the plenum block outlet temperatures."""
        plenumBlocks = self.iterChildrenWithFlags(Flags.PLENUM)
        plenumTemps = [b.p.THcoolantOutletT for b in plenumBlocks]

        # no plenum blocks, use the top block of the assembly for plenum temperature
        if not plenumTemps:
            runLog.warning("No plenum blocks exist. Using outlet coolant temperature.")
            plenumTemps = [self[-1].p.THcoolantOutletT]

        return sum(plenumTemps) / len(plenumTemps)

    def adjustResolution(self, refA):
        """Split the blocks in this assembly to have the same mesh structure as refA."""
        newBlockStack = []

        newBlocks = 0  # number of new blocks we've added so far.
        for i, b in enumerate(self):
            refB = refA[i + newBlocks]  # pick the block that is "supposed to" line up with refB.

            if refB.getHeight() == b.getHeight():
                # these blocks line up
                newBlockStack.append(b)
                continue
            elif refB.getHeight() > b.getHeight():
                raise RuntimeError(
                    "can't split {0} ({1}cm) into larger blocks to match ref block {2} ({3}cm)".format(
                        b, b.getHeight(), refB, refB.getHeight()
                    )
                )
            else:
                # b is larger than refB. Split b up by splitting it into several smaller blocks of
                # refBs
                heightToChop = b.getHeight()
                heightChopped = 0.0
                while abs(heightChopped - heightToChop) > 1e-5:  # stop when they are equal. floating point.
                    # update which ref block we're on (does nothing on the first pass)
                    refB = refA[i + newBlocks]
                    newB = copy.deepcopy(b)
                    newB.setHeight(refB.getHeight())  # make block match ref mesh
                    newBlockStack.append(newB)
                    heightChopped += refB.getHeight()
                    newBlocks += 1
                    runLog.important(f"Added a new block {newB} of height {newB.getHeight()}")
                    runLog.important(f"Chopped {heightChopped} of {heightToChop}")

                # subtract one because we eliminated the original b completely.
                newBlocks -= 1

        self.removeAll()
        self.spatialGrid = grids.AxialGrid.fromNCells(len(newBlockStack))
        for b in newBlockStack:
            self.add(b)
        self.reestablishBlockOrder()

    def getAxialMesh(self, centers=False, zeroAtFuel=False):
        """
        Make a list of the block z-mesh tops from bottom to top in cm.

        Parameters
        ----------
        centers : bool, optional
            Return centers instead of tops. If centers and zeroesAtFuel the zero point will be
            center of first fuel.

        zeroAtFuel : bool, optional
            If true will make the (bottom or center depending on centers) of the first fuel block be
            the zero point instead of the bottom of the first block.

        See Also
        --------
        armi.reactor.assemblies.Assembly.makeAxialSnapList : makes index-based lookup of axial mesh

        armi.reactor.reactors.Reactor.findAllAxialMeshPoints : gets a global list of all of these,
        plus finer res.
        """
        bottom = 0.0
        meshVals = []
        fuelIndex = None
        for bi, b in enumerate(self):
            top = bottom + b.getHeight()
            if centers:
                center = bottom + (top - bottom) / 2.0
                meshVals.append(center)
            else:
                meshVals.append(top)
            bottom = top
            if fuelIndex is None and b.isFuel():
                fuelIndex = bi

        if zeroAtFuel:
            # adjust the mesh to put zero at the first fuel block.
            zeroVal = meshVals[fuelIndex]
            meshVals = [mv - zeroVal for mv in meshVals]

        return meshVals

    def calculateZCoords(self):
        """
        Set the center z-coords of each block and the params for axial expansion.

        See Also
        --------
        reestablishBlockOrder
        """
        bottom = 0.0
        mesh = [bottom]
        for bi, b in enumerate(self):
            b.p.z = bottom + (b.getHeight() / 2.0)
            b.p.zbottom = bottom
            top = bottom + b.getHeight()
            b.p.ztop = top
            mesh.append(top)
            bottom = top
            b.spatialLocator = self.spatialGrid[0, 0, bi]

        # also update the 1-D axial assembly level grid (this is intended to replace z,
        # ztop, zbottom, etc.)

        # length of this is numBlocks + 1
        bounds = list(self.spatialGrid._bounds)
        bounds[2] = np.array(mesh)
        self.spatialGrid._bounds = tuple(bounds)

    def getTotalHeight(self, typeSpec=None):
        """
        Determine the height of this assembly in cm.

        Parameters
        ----------
        typeSpec : See :py:meth:`armi.composites.Composite.hasFlags`

        Returns
        -------
        height : float
            the height in cm
        """
        h = 0.0
        for b in self:
            if b.hasFlags(typeSpec):
                h += b.getHeight()
        return h

    def getHeight(self, typeSpec=None):
        return self.getTotalHeight(typeSpec)

    def getReactiveHeight(self, enrichThresh=0.02):
        """
        Returns the zBottom and total height in cm that has fissile enrichment over
        enrichThresh.
        """
        reactiveH = 0.0
        zBot = None
        z = 0.0
        for b in self:
            h = b.getHeight()
            if b.getFissileMass() > 0.01 and b.getFissileMassEnrich() > enrichThresh:
                if zBot is None:
                    zBot = z
                reactiveH += h
            z += h

        return zBot, reactiveH

    def getElevationBoundariesByBlockType(self, blockType=None):
        """
        Gets of list of elevations, ordered from bottom to top of all boundaries of the block of specified type.

        Useful for determining location of the top of the upper grid plate or active
        fuel, etc by using [0] to get the lowest boundary and [-1] to get highest

        Notes
        -----
        The list will have duplicates when blocks of the same type share a boundary.
        this is intentional. It makes it easy to grab pairs off the list and know that
        the first item in a pair is the bottom boundary and the second is the top.

        Parameters
        ----------
        blockType : str
            Block type to find. empty accepts all

        Returns
        -------
        elevation : list of floats
            Every float in the list is an elevation of a block boundary for the block
            type specified (has duplicates)
        """
        elevation, elevationsWithBlockBoundaries = 0.0, []

        # loop from bottom to top, stopping at the first instance of blockType
        for b in self:
            if b.hasFlags(blockType):
                elevationsWithBlockBoundaries.append(elevation)  # bottom Boundary
                elevationsWithBlockBoundaries.append(elevation + b.getHeight())  # top Boundary
            elevation += b.getHeight()

        return elevationsWithBlockBoundaries

    def getElevationsMatchingParamValue(self, param, value):
        """
        Return the elevations (z-coordinates) where the specified param takes the
        specified value.

        Uses linear interpolation, assuming params correspond to block centers

        Parameters
        ----------
        param : str
            Name of param to try and match

        value: float

        Returns
        -------
        heights : list
            z-coordinates where the specified param takes the specified value
        """
        heights = []
        # loop from bottom to top
        for i in range(0, len(self) - 1):
            diff1 = self[i].p[param] - value
            diff2 = self[i + 1].p[param] - value
            z1 = (self[i].p.zbottom + self[i].p.ztop) / 2
            z2 = (self[i + 1].p.zbottom + self[i + 1].p.ztop) / 2

            if diff1 == diff2:  # params are flat
                if diff1 != 0:  # no match
                    continue
                else:
                    if z1 not in heights:
                        heights.append(z1)
                    if z2 not in heights:
                        heights.append(z2)

            # check if param is bounded by two adjacent blocks
            elif diff1 * diff2 <= 0:
                tie = diff1 / (diff1 - diff2)
                z = z1 + tie * (z2 - z1)
                if z not in heights:  # avoid duplicates
                    heights.append(z)

        return heights

    def getAge(self):
        """Gets a height-averaged residence time of this assembly in days."""
        at = 0.0
        for b in self:
            at += b.p.residence * b.getHeight()
        return at / self.getTotalHeight()

    def makeAxialSnapList(self, refAssem=None, refMesh=None, force=False):
        """
        Creates a list of block indices that should track axially with refAssem's.

        When axially expanding, the control rods, shields etc. need to maintain mesh
        lines with the rest of the core. To do this, we'll just keep track of which
        indices of a reference assembly we should stick with. This method writes the
        indices of the top of a block to settings as topIndex.

        Keep in mind that assemblies can have different number of blocks. This is why
        this function is useful. So this makes a list of reference indices that
        correspond to different axial mesh points on this assembly.

        This is the depletion mesh we're returning, useful for snapping after axial
        extension. Note that the neutronics mesh on rebusOutputs might be different.

        See Also
        --------
        setBlockMesh : applies a snap.

        """
        if not force and self[-1].p.topIndex > 0:
            return

        refMesh = refAssem.getAxialMesh() if refMesh is None else refMesh
        selfMesh = self.getAxialMesh()
        # make a list relating this assemblies axial mesh points to indices of the
        # reference assembly
        z = 0.0
        for b in self:
            top = z + b.getHeight()
            try:
                b.p.topIndex = np.where(np.isclose(refMesh, top))[0].tolist()[0]
            except IndexError:
                runLog.error(
                    "Height {0} in this assembly ({1} in {4}) is not in the reactor mesh "
                    "list from  {2}\nThis has: {3}\nIf you want to run "
                    "a case with non-uniform axial mesh, activate the `detailedAxialExpansion` "
                    "setting".format(top, self, refMesh, selfMesh, self.parent)
                )
                raise
            z = top

    def _shouldMassBeConserved(self, belowFuelColumn, b):
        """
        Determine from a rule set if the mass of a block component should be conserved during axial expansion.

        Parameters
        ----------
        belowFuelColumn : boolean
            Determines whether a block is below the fuel column or not in fuel
            assemblies

        b : armi block
            The block that is being examined for modification

        Returns
        -------
        conserveMass : boolean
            Should the mass be conserved in this block

        conserveComponents : list of components
            What components should have their mass conserved (if any)

        belowFuelColumn : boolean
            Update whether the block is above or below a fuel column

        See Also
        --------
        armi.assemblies.Assembly.setBlockMesh

        """
        if b.hasFlags(Flags.FUEL):
            # fuel block
            conserveMass = True
            conserveComponents = b.getComponents(Flags.FUEL)
        elif self.hasFlags(Flags.FUEL):
            # non-fuel block of a fuel assembly.
            if belowFuelColumn:
                # conserve mass of everything below the fuel so as to not invalidate
                # grid-plate dose calcs.
                conserveMass = True
                # conserve mass of everything except fluids.
                conserveComponents = [comp for comp in b.getComponents() if not isinstance(comp.material, Fluid)]
            else:
                # plenum or above block in fuel assembly. don't conserve mass.
                conserveMass = False
                conserveComponents = []
        else:
            # non fuel block in non-fuel assem. Don't conserve mass.
            conserveMass = False
            conserveComponents = []

        return conserveMass, conserveComponents

    def setBlockMesh(self, blockMesh, conserveMassFlag=False):
        """
        Snaps the axial mesh points of this assembly to correspond with the reference mesh.

        Notes
        -----
        This function only conserves mass on certain conditions:
            1) Fuel Assembly
                a) Structural material below the assembly conserves mass to accurate
                   depict grid plate shielding Sodium is not conserved.
                b) Fuel blocks only conserve mass of the fuel, not the structure since
                   the fuel slides up through the cladding (thus fuel/cladding should be
                   reduced).
                c) Structure above the assemblies (expected to be plenum) do not
                   conserve mass since plenum regions have their height reduced to
                   conserve the total structure mass when the fuel grows in the
                   cladding.  See b)
            2) Reflectors, shields, and control rods
                a) These assemblies do not conserve mass since they should remain
                   uniform to keep radial shielding accurate. This approach should be
                   conservative.
                b) Control rods do not have their mass conserved and the control rod
                   interface is required to be run after this function is called to
                   correctly place mass of poison axially.

        Parameters
        ----------
        blockMesh : iterable
            A list of floats describing the upper mesh points of each block in cm.

        conserveMassFlag : bool or str
            Option for how to treat mass conservation when the block mesh changes.
            Conservation of mass for fuel components is enabled by
            conserveMassFlag="auto". If not auto, a boolean value should be
            passed. The default is False, which does not conserve any masses.
            True conserves mass for all components.

        See Also
        --------
        makeAxialSnapList : Builds the lookup table used by this method
        getAxialMesh : builds a mesh compatible with this
        """
        # Just adjust the heights and everything else will fall into place
        zBottom = 0.0
        belowFuelColumn = True

        if self[-1].p.topIndex == 0:
            runLog.warning(
                "Reference uniform mesh not being applied to {}. It was likely "
                "excluded through the setting `nonUniformAssemFlags`.".format(self.p.type)
            )
            return

        for b in self:
            if b.isFuel():
                belowFuelColumn = False

            topIndex = b.p.topIndex

            if not 0 <= topIndex < len(blockMesh):
                runLog.warning(
                    "index {0} does not exist in topvals (len:{1}). 0D case? Skipping snap".format(
                        topIndex, len(blockMesh)
                    )
                )
                return

            newTop = blockMesh[topIndex]

            if newTop is None:
                runLog.warning("Skipping axial snapping on {0}".format(self), 1)
                return

            if conserveMassFlag == "auto":
                conserveMass, conserveComponents = self._shouldMassBeConserved(belowFuelColumn, b)
            else:
                conserveMass = conserveMassFlag
                conserveComponents = b.getComponents()

            oldBlockHeight = b.getHeight()
            b.setHeight(newTop - zBottom)
            if conserveMass:
                heightRatio = oldBlockHeight / b.getHeight()
                for c in conserveComponents:
                    c.changeNDensByFactor(heightRatio)
            zBottom = newTop

        self.calculateZCoords()

    def setBlockHeights(self, blockHeights):
        """Set the block heights of all blocks in the assembly."""
        mesh = np.cumsum(blockHeights)
        self.setBlockMesh(mesh)

    def dump(self, fName=None):
        """Pickle the assembly and write it to a file."""
        if not fName:
            fName = self.getName() + ".dump.pkl"

        with open(fName, "w") as pkl:
            pickle.dump(self, pkl)

    def iterBlocks(self, typeSpec=None, exact=False):
        """Produce an iterator over all blocks in this assembly from bottom to top.

        Parameters
        ----------
        typeSpec : Flags or list of Flags, optional
            Restrict returned blocks to have these flags.
        exact : bool, optional
            If true, only produce blocks that have those exact flags.

        Returns
        -------
        iterable of Block

        See Also
        --------
        * :meth:`__iter__` - if no type spec provided, assemblies can be
          naturally iterated upon.
        * :meth:`iterChildrenWithFlags` - alternative if you know you have
           a type spec that isn't ``None``.
        """
        if typeSpec is None:
            return iter(self)
        return self.iterChildrenWithFlags(typeSpec, exact)

    def getBlocks(self, typeSpec=None, exact=False):
        """
        Get blocks in an assembly from bottom to top.

        Parameters
        ----------
        typeSpec : Flags or list of Flags, optional
            Restrict returned blocks to those of this type.
        exact : bool, optional
            If true, will only return if there's an exact match in typeSpec

        Returns
        -------
        blocks : list
            List of blocks.
        """
        return list(self.iterBlocks(typeSpec, exact))

    def getBlocksAndZ(self, typeSpec=None, returnBottomZ=False, returnTopZ=False):
        """
        Get blocks and their z-coordinates from bottom to top.

        This method is useful when you need to know the z-coord of a block.

        Parameters
        ----------
        typeSpec : Flags or list of Flags, optional
            Block type specification to restrict to

        returnBottomZ : bool, optional
            If true, will return bottom coordinates instead of centers.

        Returns
        -------
        blocksAndCoords, list
            (block, zCoord) tuples

        Examples
        --------
            for block, bottomZ in a.getBlocksAndZ(returnBottomZ=True):
                print({0}'s bottom mesh point is {1}'.format(block, bottomZ))
        """
        if returnBottomZ and returnTopZ:
            raise ValueError("Both returnTopZ and returnBottomZ are set to `True`")

        blocks, zCoords = [], []
        bottom = 0.0
        for b in self:
            top = bottom + b.getHeight()
            mid = (bottom + top) / 2.0
            if b.hasFlags(typeSpec):
                blocks.append(b)
                if returnBottomZ:
                    val = bottom
                elif returnTopZ:
                    val = top
                else:
                    val = mid
                zCoords.append(val)
            bottom = top

        return zip(blocks, zCoords)

    def hasContinuousCoolantChannel(self):
        return all(b.containsAtLeastOneChildWithFlags(Flags.COOLANT) for b in self)

    def getFirstBlock(self, typeSpec: TypeSpec = None, exact: bool = False) -> Optional[blocks.Block]:
        """Find the first block that matches the spec.

        Parameters
        ----------
        typeSpec
            Specification to require on the returned block.
        exact
            Require block to exactly match ``typeSpec``

        Returns
        -------
        Block or None
            First block that matches if such a block could be found.
        """
        if typeSpec is None:
            items = iter(self)
        else:
            items = self.iterChildrenWithFlags(typeSpec, exact)
        try:
            # Create an iterator and attempt to advance it to the first value.
            return next(items)
        except StopIteration:
            # No items found in the iteration -> no blocks match the request
            return None

    def getFirstBlockByType(self, typeName: str) -> Optional[blocks.Block]:
        blocks = filter(lambda b: b.getType() == typeName, self)
        try:
            return next(blocks)
        except StopIteration:
            return None

    def getBlockAtElevation(self, elevation: float) -> Optional[blocks.Block]:
        """
        Returns the block at a specified axial dimension elevation (given in cm).

        If height matches the exact top of the block, the block is considered at that
        height.

        Parameters
        ----------
        elevation : float
            The elevation of interest to grab a block (cm)

        Returns
        -------
        targetBlock : block or None
            The block that exists at the specified height in the reactor. ``None``
            if a block was not found.
        """
        bottomOfBlock = 0.0
        for b in self:
            topOfBlock = bottomOfBlock + b.getHeight()
            if (
                topOfBlock > elevation or abs(topOfBlock - elevation) / elevation < 1e-10
            ) and bottomOfBlock < elevation:
                return b
            bottomOfBlock = topOfBlock
        return None

    def getBIndexFromZIndex(self, zIndex):
        """
        Returns the ARMI block axial index corresponding to a DIF3D node axial index.

        Parameters
        ----------
        zIndex : float
            The axial index (beginning with 0) of a DIF3D node.

        Returns
        -------
        bIndex : int
            The axial index (beginning with 0) of the ARMI block containing the
            DIF3D node corresponding to zIndex.
        """
        zIndexTot = -1
        for bIndex, b in enumerate(self):
            zIndexTot += b.p.axMesh
            if zIndexTot >= zIndex:
                return bIndex
        return -1  # no block index found

    def getBlocksBetweenElevations(self, zLower, zUpper, eps=1e-10):
        """
        Return block(s) between two axial elevations and their corresponding heights.

        Parameters
        ----------
        zLower, zUpper : float
            Elevations in cm where blocks should be found.
        eps : float, optional
            Lower bound for relative block height fraction that we care about.
            Below this bound, small slivers of overlapping block are ignored.


        Returns
        -------
        blockInfo : list
            list of (blockObj, overlapHeightInCm) tuples

        Examples
        --------
        If the block structure looks like:
        50.0 to 100.0 Block3
        25.0 to 50.0  Block2
        0.0 to 25.0   Block1

        Then,

        >>> a.getBlocksBetweenElevations(0,50)
        [(Block1, 25.0), (Block2, 25.0)]

        >>> a.getBlocksBetweenElevations(0,30)
        [(Block1, 25.0), (Block2, 5.0)]

        """
        blocksHere = []
        allMeshPoints = set()

        for b in self:
            if b.p.ztop >= zLower and b.p.zbottom <= zUpper:
                allMeshPoints.add(b.p.zbottom)
                allMeshPoints.add(b.p.ztop)
                # at least some of this block overlaps the window of interest
                top = min(b.p.ztop, zUpper)
                bottom = max(b.p.zbottom, zLower)
                heightHere = top - bottom

                # Filter out blocks that have an extremely small height fraction
                if heightHere / b.getHeight() > eps:
                    blocksHere.append((b, heightHere))

        totalHeight = 0.0
        allMeshPoints = sorted(allMeshPoints)
        # The expected height snaps to the minimum height that is requested
        expectedHeight = min(allMeshPoints[-1] - allMeshPoints[0], zUpper - zLower)
        for _b, height in blocksHere:
            totalHeight += height

        # Verify that the heights of all the blocks are equal to the expected
        # height for the given zUpper and zLower.
        if abs(totalHeight - expectedHeight) / expectedHeight > 10.0 * eps:
            raise ValueError(
                f"The cumulative height of {blocksHere} is {totalHeight} cm "
                f"and does not equal the expected height of {expectedHeight} cm.\n"
                f"All mesh points: {allMeshPoints}\n"
                f"Upper mesh point: {zUpper} cm\n"
                f"Lower mesh point: {zLower} cm\n"
            )

        return blocksHere

    def getParamValuesAtZ(self, param, elevations, interpType="linear", fillValue=np.nan):
        """
        Interpolates a param axially to find it at any value of elevation z.

        By default, assumes that all parameters are for the center of a block. So for
        parameters such as THoutletTemperature that are defined on the top, this may be
        off. See the paramDefinedAt parameters.

        Defaults to linear interpolations.

        Notes
        -----
        This caches interpolators for each param and must be cleared if new params are
        set or new heights are set.

        Warning
        -------
        Fails when requested to extrapolate. With higher order splines it is possible to interpolate
        non-physical values, for example, a negative flux or dpa. Please use caution when going off
        default in interpType and be certain that interpolated values are physical.

        Parameters
        ----------
        param : str
            the parameter to interpolate
        elevations : array of float
            the elevations from the bottom of the assembly in cm at which you want the point.
        interpType: str or int
            used in interp1d. interp1d documentation: Specifies the kind of interpolation
            as a string ('linear', 'nearest', 'zero', 'slinear', 'quadratic', 'cubic'
            where 'slinear', 'quadratic' and 'cubic' refer to a spline interpolation of
            first, second or third order) or as an integer specifying the order of the
            spline interpolator to use. Default is 'linear'.
        fillValue: str
            Rough pass through to scipy.interpolate.interp1d. If 'extend', then the
            lower and upper bounds are used as the extended value. If 'extrapolate',
            then extrapolation is permitted.

        Returns
        -------
        valAtZ : np.ndarray
            This will be of the shape (z,data-shape)
        """
        interpolator = self.getParamOfZFunction(param, interpType=interpType, fillValue=fillValue)
        return interpolator(elevations)

    def getParamOfZFunction(self, param, interpType="linear", fillValue=np.nan):
        """
        Interpolates a param axially to find it at any value of elevation z.

        By default, assumes that all parameters are for the center of a block. So for
        parameters such as THoutletTemperature that are defined on the top, this may be
        off. See the paramDefinedAt parameters.

        Defaults to linear interpolations.

        Notes
        -----
        This caches interpolators for each param and must be cleared if new params are
        set or new heights are set.

        Warning
        -------
        Fails when requested to extrapololate. With higher order splines it is possible to
        interpolate nonphysical values, for example, a negative flux or dpa. Please use caution when
        going off default in interpType and be certain that interpolated values are physical.

        Parameters
        ----------
        param : str
            the parameter to interpolate
        interpType: str or int
            used in interp1d. interp1d documentation: Specifies the kind of interpolation
            as a string ('linear', 'nearest', 'zero', 'slinear', 'quadratic', 'cubic'
            where 'slinear', 'quadratic' and 'cubic' refer to a spline interpolation of
            first, second or third order) or as an integer specifying the order of the
            spline interpolator to use. Default is 'linear'.
        fillValue: float
            Rough pass through to scipy.interpolate.interp1d. If 'extend', then the
            lower and upper bounds are used as the extended value. If 'extrapolate',
            then extrapolation is permitted.

        Returns
        -------
        valAtZ : np.ndarray
            This will be of the shape (z,data-shape)
        """
        paramDef = self[0].p.paramDefs[param]

        if not isinstance(paramDef.location, ParamLocation):
            raise Exception(
                "Cannot interpolate on `{}`. The ParamDefinition does not define a "
                "valid location `{}`.\nValid locations are {}".format(
                    param,
                    paramDef.location,
                    ", ".join([str(pl) for pl in ParamLocation]),
                )
            )
        atCenter = bool(paramDef.location & (ParamLocation.CENTROID | ParamLocation.VOLUME_INTEGRATED))
        z = self.getAxialMesh(atCenter)

        if paramDef.location & ParamLocation.BOTTOM:
            z.insert(0, 0.0)
            z.pop(-1)

        z = np.asarray(z)

        values = self.getChildParamValues(param).transpose()

        boundsError = None
        if fillValue == "extend":
            boundsError = False
            if values.ndim == 1:
                fillValue = values[0], values[-1]
            elif values.ndim == 2:
                fillValue = values[:, 0], values[:, 1]
            else:
                raise Exception(
                    'Unsupported shape ({}) returned from getChildParamValues("{}").'
                    "Shape must be 1 or 2 dimensions".format(values.shape, param)
                )
        interpolater = interpolate.interp1d(
            z,
            values,
            kind=interpType,
            fill_value=fillValue,
            assume_sorted=True,
            bounds_error=boundsError,
        )
        return interpolater

    def reestablishBlockOrder(self):
        """
        The block ordering has changed, so the spatialGrid and Block-wise spatialLocator and name objects need updating.

        See Also
        --------
        calculateZCoords : updates the ztop/zbottom params on each block after
            reordering.
        """
        # replace grid with one that has the right number of locations
        self.spatialGrid = grids.AxialGrid.fromNCells(len(self))
        self.spatialGrid.armiObject = self
        for zi, b in enumerate(self):
            b.spatialLocator = self.spatialGrid[0, 0, zi]
            # update the name too. NOTE: You must update the history tracker.
            b.setName(b.makeName(self.p.assemNum, zi))

    def countBlocksWithFlags(self, blockTypeSpec=None):
        """
        Returns the number of blocks of a specified type.

        blockTypeSpec : Flags or list
            Restrict to only these types of blocks. typeSpec is None, return all of the
            blocks

        Returns
        -------
        blockCounter : int
            number of blocks of this type
        """
        return sum(1 for _ in self.iterBlocks(blockTypeSpec))

    def getDim(self, typeSpec, dimName):
        """
        With a preference for fuel blocks, find the first component in the Assembly with
        flags that match ``typeSpec`` and return dimension as specified by ``dimName``.

        Example: getDim(Flags.WIRE, 'od') will return a wire's OD in cm.
        """
        # prefer fuel blocks.
        bList = self.getBlocks(Flags.FUEL)
        if not bList:
            # no fuel blocks. take first block.
            bList = self

        for b in bList:
            dim = b.getDim(typeSpec, dimName)
            if dim:
                return dim

        # return none if there is nothing to return
        return None

    def getSymmetryFactor(self):
        """Return the symmetry factor of this assembly."""
        return self[0].getSymmetryFactor()

    def rotate(self, rad):
        """Rotates the spatial variables on an assembly by the specified angle.

        Each Block on the Assembly is rotated in turn.

        Parameters
        ----------
        rad : float
            number (in radians) specifying the angle of counter clockwise rotation
        """
        # handle the orientation parameter
        if self.p.orientation is None:
            self.p.orientation = np.array([0.0, 0.0, 0.0])

        self.p.orientation[2] += math.degrees(rad)

        for b in self:
            b.rotate(rad)

    def isOnWhichSymmetryLine(self):
        grid = self.parent.spatialGrid
        return grid.overlapsWhichSymmetryLine(self.spatialLocator.getCompleteIndices())

    def orientBlocks(self, parentSpatialGrid):
        """Add special grids to the blocks inside this Assembly, respecting their orientation.

        Parameters
        ----------
        parentSpatialGrid : Grid
            Spatial Grid of the parent of this Assembly (probably a system-level grid).
        """
        for b in self:
            if b.spatialGrid is None:
                try:
                    b.autoCreateSpatialGrids(parentSpatialGrid)
                except (ValueError, NotImplementedError) as e:
                    runLog.extra(str(e), single=True)
            # Do more grid initializations from a manual or auto created grid
            if b.spatialGrid is not None:
                b.assignPinIndices()


class HexAssembly(Assembly):
    """An assembly that is hexagonal in cross-section."""

    _BLOCK_TYPE = blocks.HexBlock

    def rotate(self, rad: float):
        """Rotate an assembly and its children.

        .. impl:: A hexagonal assembly shall support rotating around the z-axis in 60 degree increments.
            :id: I_ARMI_ROTATE_HEX_ASSEM
            :implements: R_ARMI_ROTATE_HEX

            This method loops through every ``Block`` in this ``HexAssembly`` and rotates it by a
            given angle (in radians). The rotation angle is positive in the counter-clockwise
            direction. To perform the ``Block`` rotation, the
            :meth:`armi.reactor.blocks.HexBlock.rotate` method is called.

        Parameters
        ----------
        rad : float
            Counter clockwise rotation in radians. **MUST** be in increments of 60 degrees (PI / 3)

        Raises
        ------
        ValueError
            If rotation is not divisible by pi / 3.
        """
        if math.isclose(rad % (math.pi / 3), 0, abs_tol=1e-12):
            return super().rotate(rad)

        msg = f"Rotation must be in 60 degree increments, got {math.degrees(rad)} degrees ({rad} radians)."
        runLog.error(msg)
        raise ValueError(msg)


class CartesianAssembly(Assembly):
    """An assembly that is rectangular in cross-section."""

    _BLOCK_TYPE = blocks.CartesianBlock


class RZAssembly(Assembly):
    """
    RZAssembly are assemblies in RZ geometry; they need to be different objects than HexAssembly
    because they use different locations and need to have Radial Meshes in their setting.

    Notes
    -----
    ThRZAssemblies should be a subclass of Assemblies because they should have a common place to put
    information about subdividing the global mesh for transport. This is similar to how blocks have
    'AxialMesh' in their blocks.
    """

    def __init__(self, name, assemNum=None):
        Assembly.__init__(self, name, assemNum)
        self.p.RadMesh = 1

    def radialOuter(self):
        """Returns the outer radial boundary of this assembly."""
        return self[0].radialOuter()

    def radialInner(self):
        """Returns the inner radial boundary of this assembly."""
        return self[0].radialInner()

    def thetaOuter(self):
        """Returns the outer azimuthal boundary of this assembly."""
        return self[0].thetaOuter()

    def thetaInner(self):
        """Returns the outer azimuthal boundary of this assembly."""
        return self[0].thetaInner()


class ThRZAssembly(RZAssembly):
    """
    ThRZAssembly are assemblies in ThetaRZ geometry, they need to be different objects
    than HexAssembly because they use different locations and need to have Radial Meshes
    in their setting.
    """

    def __init__(self, assemType, assemNum=None):
        RZAssembly.__init__(self, assemType, assemNum)
        self.p.AziMesh = 1
