# Copyright 2024 TerraPower, LLC
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
Core is a high-level object in the data model in ARMI.

A Core frequently contain assemblies which in turn contain more refinement in representing the
physical reactor.
"""

import collections
import copy
import itertools
import os
import time
from typing import Callable, Iterator, Optional

import numpy as np
import yaml

from armi import getPluginManagerOrFail, nuclearDataIO, runLog
from armi.nuclearDataIO import xsLibraries
from armi.reactor import (
    assemblies,
    blocks,
    composites,
    flags,
    geometry,
    grids,
    parameters,
    reactorParameters,
    zones,
)
from armi.reactor.flags import Flags
from armi.reactor.zones import Zone, Zones
from armi.settings.fwSettings.globalSettings import (
    CONF_AUTOMATIC_VARIABLE_MESH,
    CONF_CIRCULAR_RING_PITCH,
    CONF_DETAILED_AXIAL_EXPANSION,
    CONF_FRESH_FEED_TYPE,
    CONF_MIN_MESH_SIZE_RATIO,
    CONF_NON_UNIFORM_ASSEM_FLAGS,
    CONF_STATIONARY_BLOCK_FLAGS,
    CONF_TRACK_ASSEMS,
    CONF_ZONE_DEFINITIONS,
    CONF_ZONES_FILE,
)
from armi.utils import createFormattedStrWithDelimiter, tabulate, units
from armi.utils.iterables import Sequence
from armi.utils.mathematics import average1DWithinTolerance


class Core(composites.Composite):
    """
    Reactor structure made up of assemblies. Could be a Core, spent fuel pool, reactor head, etc.

    This has the bulk of the data management operations.

    Attributes
    ----------
    params : dict
        Core-level parameters are scalar values that have time dependence. Examples are keff,
        maxPercentBu, etc.
    assemblies : list
        List of assembly objects that are currently in the core
    """

    pDefs = reactorParameters.defineCoreParameters()

    def __init__(self, name):
        """
        Initialize the reactor object.

        Parameters
        ----------
        name : str
            Name of the object. Flags will inherit from this.
        """
        composites.Composite.__init__(self, name)
        self.assembliesByName = {}
        self.circularRingList = {}
        self.blocksByName = {}  # lookup tables
        self.numRings = 0
        self.spatialGrid = None
        self.xsIndex = {}
        self.p.numMoves = 0
        self._lib = None  # placeholder for ISOTXS object
        self.locParams = {}  # location-based parameters
        # overridden in case.py to include pre-reactor time.
        self.timeOfStart = time.time()
        self.zones = zones.Zones()  # initialize with empty Zones object
        # initialize the list that holds all shuffles
        self.moves = {}
        self.scalarVals = {}
        self._nuclideCategories = {}
        self.typeList = []  # list of block types to convert name - to -number.

        # leftover default "settings" that are intended to eventually be elsewhere.
        self._freshFeedType = "feed fuel"
        self._trackAssems = False
        self._circularRingMode = False
        self._circularRingPitch = 1.0
        self._automaticVariableMesh = False
        self._minMeshSizeRatio = 0.15
        self._detailedAxialExpansion = False

    def setOptionsFromCs(self, cs):
        from armi.physics.fuelCycle.settings import (
            CONF_CIRCULAR_RING_MODE,
            CONF_JUMP_RING_NUM,
        )

        # these are really "user modifiable modeling constants"
        self.p.jumpRing = cs[CONF_JUMP_RING_NUM]
        self._freshFeedType = cs[CONF_FRESH_FEED_TYPE]
        self._trackAssems = cs[CONF_TRACK_ASSEMS]
        self._circularRingMode = cs[CONF_CIRCULAR_RING_MODE]
        self._circularRingPitch = cs[CONF_CIRCULAR_RING_PITCH]
        self._automaticVariableMesh = cs[CONF_AUTOMATIC_VARIABLE_MESH]
        self._minMeshSizeRatio = cs[CONF_MIN_MESH_SIZE_RATIO]
        self._detailedAxialExpansion = cs[CONF_DETAILED_AXIAL_EXPANSION]

    def __getstate__(self):
        """Applies a settings and parent to the core and components."""
        state = composites.Composite.__getstate__(self)
        return state

    def __setstate__(self, state):
        composites.Composite.__setstate__(self, state)
        self.regenAssemblyLists()

    def __deepcopy__(self, memo):
        memo[id(self)] = newC = self.__class__.__new__(self.__class__)
        newC.__setstate__(copy.deepcopy(self.__getstate__(), memo))
        newC.name = self.name + "-copy"
        return newC

    def __repr__(self):
        return "<{}: {} id:{}>".format(self.__class__.__name__, self.name, id(self))

    def __iter__(self):
        """Override the base Composite __iter__ to produce stable sort order."""
        return iter(self._children)

    @property
    def r(self):
        from armi.reactor.reactors import Reactor

        if isinstance(self.parent, Reactor):
            return self.parent

        return None

    @property
    def symmetry(self) -> geometry.SymmetryType:
        """Getter for symmetry type.

        .. impl:: Get core symmetry.
            :id: I_ARMI_R_SYMM
            :implements: R_ARMI_R_SYMM

            This property getter returns the symmetry attribute of the spatialGrid instance
            attribute. The spatialGrid is an instance of a child of the abstract base class
            :py:class:`Grid <armi.reactor.grids.grid.Grid>` type. The symmetry attribute is an
            instance of the :py:class:`SymmetryType <armi.reactor.geometry.SymmetryType>` class,
            which is a wrapper around the :py:class:`DomainType <armi.reactor.geometry.DomainType>`
            and :py:class:`BoundaryType <armi.reactor.geometry.BoundaryType>` enumerations used to
            classify the domain (e.g., 1/3 core, quarter core, full core) and symmetry boundary
            conditions (e.g., periodic, reflective, none) of a reactor, respectively.

            Only specific combinations of :py:class:`Grid <armi.reactor.grids.grid.Grid>` type,
            :py:class:`DomainType <armi.reactor.geometry.DomainType>`, and :py:class:`BoundaryType
            <armi.reactor.geometry.BoundaryType>` are valid. The validity of a user-specified
            geometry and symmetry is verified by a settings :py:class:`Inspector
            <armi.operators.settingsValidation.Inspector`.
        """
        if not self.spatialGrid:
            raise ValueError("Cannot access symmetry before a spatialGrid is attached.")
        return self.spatialGrid.symmetry

    @symmetry.setter
    def symmetry(self, val: str):
        """Setter for symmetry type."""
        self.spatialGrid.symmetry = str(val)
        self.clearCache()

    @property
    def geomType(self) -> geometry.GeomType:
        if not self.spatialGrid:
            raise ValueError("Cannot access geomType before a spatialGrid is attached.")
        return self.spatialGrid.geomType

    @property
    def powerMultiplier(self):
        """
        Symmetry factor for this model. 1 for full core, 3 for 1/3 core, etc.

        Notes
        -----
        This should not be a state variable because it just reflects the current geometry.
        It changes automatically if the symmetry changes (e.g. from a geometry conversion).
        """
        return self.symmetry.symmetryFactor()

    @property
    def lib(self) -> Optional[xsLibraries.IsotxsLibrary]:
        """
        Return the microscopic cross section library, if one exists.

        - If there is a library currently associated with the Core, it will be returned
        - Otherwise, an ``ISOTXS`` file will be searched for in the working directory, opened as ``ISOTXS`` object and
          returned. If possible, it will find the correct file for the current cycle and timeNode.
        - Finally, if no ``ISOTXS`` file exists in the working directory, a None value will be returned.
        """
        # determine the current cycle and timeNode
        cycle = None
        node = None
        if self.r is not None:
            cycle = self.r.p.cycle
            node = self.r.p.timeNode

        # if self._lib is None, try to find a local file
        isotxsFileName = nuclearDataIO.getExpectedISOTXSFileName(cycle, node)
        if self._lib is None and os.path.exists(isotxsFileName):
            # try to find the file for this specific cycle/node
            runLog.info(f"Loading microscopic cross section library `{isotxsFileName}` at {cycle}/{node}")
            self._lib = nuclearDataIO.isotxs.readBinary(isotxsFileName)
        elif self._lib is None:
            # try to find any local file, not labeled by cycle/node
            isotxsFileName = nuclearDataIO.getExpectedISOTXSFileName()
            if os.path.exists(isotxsFileName):
                runLog.info(f"Loading microscopic cross section library `{isotxsFileName}`")
                self._lib = nuclearDataIO.isotxs.readBinary(isotxsFileName)

        return self._lib

    @lib.setter
    def lib(self, value):
        """Set the microscopic cross section library."""
        runLog.extra(f"Updating cross section library on {self}.\nInitial: {self._lib}\nUpdated: {value}.")
        self._lib = value

    @property
    def isFullCore(self):
        """Return True if reactor is full core, otherwise False."""
        # Avoid using `not core.isFullCore` to check if third core geometry
        # use `core.symmetry.domain == geometry.DomainType.THIRD_CORE
        return self.symmetry.domain == geometry.DomainType.FULL_CORE

    @property
    def refAssem(self):
        """
        Return the "reference" assembly for this Core.

        The reference assembly is defined as the center-most assembly with a FUEL flag, if any are
        present, or the center-most of any assembly otherwise.

        Warning
        -------
        The convenience of this property should be weighed against it's somewhat arbitrary nature
        for any particular client. The center-most fueled assembly is not particularly
        representative of the state of the core as a whole.
        """
        key = lambda a: a.spatialLocator.getRingPos()
        assems = self.getAssemblies(Flags.FUEL, sortKey=key)
        if not assems:
            assems = self.getAssemblies(sortKey=key)

        return assems[0]

    def sortAssemsByRing(self):
        """Sorts the reactor assemblies by ring and position."""
        sortKey = lambda a: a.spatialLocator.getRingPos()
        self._children = sorted(self._children, key=sortKey)

    def summarizeReactorStats(self):
        """Writes a summary of the reactor to check the mass and volume of all of the blocks."""
        totalMass = 0.0
        fissileMass = 0.0
        heavyMetalMass = 0.0
        totalVolume = 0.0
        numBlocks = 0
        for block in self.iterBlocks():
            totalMass += block.getMass()
            fissileMass += block.getFissileMass()
            heavyMetalMass += block.getHMMass()
            totalVolume += block.getVolume()
            numBlocks += 1
        totalMass = totalMass * self.powerMultiplier / 1000.0
        fissileMass = fissileMass * self.powerMultiplier / 1000.0
        heavyMetalMass = heavyMetalMass * self.powerMultiplier / 1000.0
        totalVolume = totalVolume * self.powerMultiplier
        runLog.extra(
            "Summary of {}\n".format(self)
            + tabulate.tabulate(
                [
                    ("Number of Blocks", numBlocks),
                    ("Total Volume (cc)", totalVolume),
                    ("Total Mass (kg)", totalMass),
                    ("Fissile Mass (kg)", fissileMass),
                    ("Heavy Metal Mass (kg)", heavyMetalMass),
                ],
                tableFmt="armi",
            )
        )

    def setPowerFromDensity(self):
        """Set the power from the powerDensity."""
        self.p.power = self.p.powerDensity * self.getHMMass()

    def setPowerIfNecessary(self):
        """Set the core power, from the power density.

        If the power density is set, but the power isn't, calculate the total heavy metal mass of
        the reactor, and set the total power. Which will then be the real source of truth again.
        """
        if self.p.power == 0 and self.p.powerDensity > 0:
            self.setPowerFromDensity()

    def setBlockMassParams(self):
        """Set the parameters kgHM and kgFis for each block and calculate Pu fraction."""
        for b in self.iterBlocks():
            b.p.kgHM = b.getHMMass() / units.G_PER_KG
            b.p.kgFis = b.getFissileMass() / units.G_PER_KG
            b.p.puFrac = b.getPuMoles() / b.p.molesHmBOL if b.p.molesHmBOL > 0.0 else 0.0

    def getScalarEvolution(self, key):
        return self.scalarVals[key]

    def locateAllAssemblies(self):
        """
        Store the current location of all assemblies.

        This is required for shuffle printouts, repeat shuffling, and MCNP shuffling.
        """
        for a in self.getAssemblies(includeAll=True):
            a.lastLocationLabel = a.getLocation()

    def removeAssembly(self, a1, discharge=True):
        """
        Takes an assembly and puts it out of core.

        Parameters
        ----------
        a1 : assembly
            The assembly to remove
        discharge : bool, optional
            Discharge the assembly, including adding it to the SFP. Default: True

        Notes
        -----
        Please expect this method will delete your assembly (instead of moving it into a Spent Fuel
        Pool) unless you set the ``trackAssems`` to True in your settings file.

        Originally, this held onto all assemblies in the Spend Fuel Pool. However, they use memory.
        And it is possible to have the history interface record only the parameters you need.
        """
        from armi.reactor.reactors import Reactor

        paramDefs = set(parameters.ALL_DEFINITIONS)
        paramDefs.difference_update(set(parameters.forType(Core)))
        paramDefs.difference_update(set(parameters.forType(Reactor)))
        for paramDef in paramDefs:
            if paramDef.assigned & parameters.SINCE_ANYTHING:
                paramDef.assigned = parameters.SINCE_ANYTHING

        if discharge:
            runLog.debug(f"Removing {a1} from {self}")
        else:
            runLog.debug(f"Purging  {a1} from {self}")

        self.childrenByLocator.pop(a1.spatialLocator)
        a1.p.dischargeTime = self.r.p.time
        self.remove(a1)

        if discharge and self._trackAssems:
            if self.parent.excore.get("sfp") is not None:
                self.parent.excore.sfp.add(a1)
            else:
                runLog.info("No Spent Fuel Pool is found, can't track assemblies.")
        else:
            self._removeListFromAuxiliaries(a1)

    def removeAssembliesInRing(self, ringNum, cs, overrideCircularRingMode=False):
        """
        Removes all of the assemblies in a given ring.

        Parameters
        ----------
        ringNum : int
            The ring to remove
        cs: Settings
            A relevant settings object
        overrideCircularRingMode : bool, optional
            False ~ default: use circular/square/hex rings, just as the reactor defines them
            True ~ Turn off circular ring mode, and instead use square or hex.

        See Also
        --------
        getAssembliesInRing : definition of a ring
        """
        for a in self.getAssembliesInRing(ringNum, overrideCircularRingMode=overrideCircularRingMode):
            self.removeAssembly(a)

        self.processLoading(cs)

    def _removeListFromAuxiliaries(self, assembly):
        """
        Remove an assembly from all auxiliary reference tables and lists.

        Otherwise it will get added back into assembliesByName, etc.

        History will fail if it tries to summarize an assembly that has been purged.
        """
        del self.assembliesByName[assembly.getName()]
        for b in assembly:
            try:
                del self.blocksByName[b.getName()]
            except KeyError:
                runLog.warning(
                    "Cannot delete block {0}. It is not in the Core.blocksByName structure".format(b),
                    single=True,
                    label="cannot dereference: lost block",
                )

    def normalizeNames(self, startIndex=0):
        """
        Renumber and rename all the Assemblies and Blocks.

        Parameters
        ----------
        startIndex : int, optional
            The default is to start counting at zero. But if you are renumbering assemblies across
            the entire Reactor, you may want to start at a different number.

        Returns
        -------
        int
            The new max Assembly number.
        """
        ind = startIndex
        for a in self:
            oldName = a.getName()
            newName = a.makeNameFromAssemNum(ind)
            if oldName == newName:
                ind += 1
                continue

            a.p.assemNum = ind
            a.setName(newName)

            for b in a:
                axialIndex = int(b.name.split("-")[-1])
                b.name = b.makeName(ind, axialIndex)

            ind += 1

        self.normalizeInternalBookeeping()

        return ind

    def normalizeInternalBookeeping(self):
        """Update some bookkeeping dictionaries of assembly and block names in this Core."""
        self.assembliesByName = {}
        self.blocksByName = {}
        for assem in self:
            self.assembliesByName[assem.getName()] = assem
            for b in assem:
                self.blocksByName[b.getName()] = b

    def add(self, a, spatialLocator=None):
        """
        Adds an assembly to the reactor.

        An object must be added before it is placed in a particular cell in the reactor's
        spatialGrid. When an object is added to a Reactor it get placed in a generic location at the
        center of the Reactor unless a spatialLocator is passed in as well.

        Parameters
        ----------
        a : ArmiObject
            The object to add to the reactor
        spatialLocator : SpatialLocator object, optional
            The location in the reactor to add the new object to. Must be unoccupied.

        See Also
        --------
        removeAssembly : removes an assembly
        """
        from armi.reactor.reactors import Reactor

        # Negative assembly IDs are placeholders, and we need to renumber the assembly
        if a.p.assemNum < 0:
            a.renumber(self.r.incrementAssemNum())

        # resetting .assigned forces database to be rewritten for shuffled core
        paramDefs = set(parameters.ALL_DEFINITIONS)
        paramDefs.difference_update(set(parameters.forType(Core)))
        paramDefs.difference_update(set(parameters.forType(Reactor)))
        for paramDef in paramDefs:
            if paramDef.assigned & parameters.SINCE_ANYTHING:
                paramDef.assigned = parameters.SINCE_ANYTHING

        # could speed up output by passing format args as an arg and only process if verb good.
        runLog.debug("Adding   {0} to {1}".format(a, self))
        composites.Composite.add(self, a)
        aName = a.getName()

        spatialLocator = spatialLocator or a.spatialLocator

        if spatialLocator is not None and spatialLocator in self.childrenByLocator:
            raise ValueError(
                "Cannot add {} because location {} is already filled by {}.".format(
                    aName, a.spatialLocator, self.childrenByLocator[a.spatialLocator]
                )
            )

        if spatialLocator is not None:
            # transfer spatialLocator to Core one
            spatialLocator = self.spatialGrid[tuple(spatialLocator.indices)]
            if not self.spatialGrid.locatorInDomain(spatialLocator, symmetryOverlap=True):
                raise LookupError(
                    "Location `{}` outside of the represented domain: `{}`".format(
                        spatialLocator, self.spatialGrid.symmetry.domain
                    )
                )
            a.moveTo(spatialLocator)

        self.childrenByLocator[spatialLocator] = a
        # build a lookup table for history tracking.
        if aName in self.assembliesByName and self.assembliesByName[aName] != a:
            # try to keep assem numbering correct
            runLog.error(
                "The assembly {1} in the reactor already has the name {0}.\nCannot add {2}. "
                "Current assemNum is {3}"
                "".format(aName, self.assembliesByName[aName], a, self.r.p.maxAssemNum)
            )
            raise RuntimeError("Core already contains an assembly with the same name.")

        self.assembliesByName[aName] = a
        for b in a:
            self.blocksByName[b.getName()] = b

        a.orientBlocks(parentSpatialGrid=self.spatialGrid)
        if self.geomType == geometry.GeomType.HEX:
            ring, _loc = self.spatialGrid.getRingPos(a.spatialLocator.getCompleteIndices())
            if ring > self.numRings:
                self.numRings = ring

        # track the highest assem Num so when we load from a DB the future assemNums remain constant
        aNum = a.p.assemNum
        if aNum > self.p.maxAssemNum:
            self.p.maxAssemNum = aNum

        if a.lastLocationLabel != a.DATABASE:
            # time the assembly enters the core in days
            a.p.chargeTime = self.r.p.time
            # cycle that the assembly enters the core
            a.p.chargeCycle = self.r.p.cycle
            # convert to kg
            a.p.chargeFis = a.getFissileMass() / 1000.0
            a.p.chargeBu = a.getMaxParam("percentBu")

    def genAssembliesAddedThisCycle(self):
        """
        Yield the assemblies that have been added in the current cycle.

        This uses the reactor's cycle parameter and the assemblies' chargeCycle parameters.
        """
        for a in self:
            if a.p.chargeCycle == self.r.p.cycle:
                yield a

    def getNumRings(self, indexBased=False):
        """
        Returns the number of rings in this reactor. Based on location, so indexing will start at 1.

        Circular ring shuffling changes the interpretation of this result.

        Warning
        -------
        If you loop through range(maxRing) then ring+1 is the one you want!

        Parameters
        ----------
        indexBased : bool, optional
            If true, will force location-index interpretation, even if "circular shuffling" is enabled.
        """
        if self.circularRingList and not indexBased:
            return max(self.circularRingList)
        else:
            return self.getNumHexRings()

    def getNumHexRings(self):
        """Return the number of hex rings in the core. Based on location so indexing starts at 1."""
        maxRing = 0
        for a in self:
            ring, _pos = self.spatialGrid.getRingPos(a.spatialLocator)
            maxRing = max(maxRing, ring)

        return maxRing

    def getNumAssembliesWithAllRingsFilledOut(self, nRings):
        """
        Returns nAssmWithBlanks (see description immediately below).

        Parameters
        ----------
        nRings : int
            The number of hex assembly rings in this core, including non-ful) rings.

        Returns
        -------
        nAssmWithBlanks: int
            The number of assemblies that WOULD exist in this core if all outer assembly hex rings
            were "filled out".
        """
        if self.powerMultiplier == 1:
            return 3 * nRings * (nRings - 1) + 1
        else:
            return nRings * (nRings - 1) + (nRings + 1) // 2

    def getNumEnergyGroups(self):
        """
        Return the number of energy groups used in the problem.

        See Also
        --------
        armi.nuclearDataIO.ISOTXS.read1D : reads the number of energy groups off the ISOTXS library.
        """
        return self.lib.numGroups

    def countBlocksWithFlags(self, blockTypeSpec, assemTypeSpec=None):
        """
        Return the total number of blocks in an assembly in the reactor that
        meets the specified type.

        Parameters
        ----------
        blockTypeSpec : Flags or list of Flags
            The types of blocks to be counted in a single assembly
        assemTypeSpec : Flags or list of Flags
            The types of assemblies that are to be examine for the blockTypes of interest. None is
            every assembly.

        Returns
        -------
        maxBlocks : int
            The maximum number of blocks of the specified types in a single assembly in the core.
        """
        assems = self.getAssemblies(typeSpec=assemTypeSpec)
        try:
            return max(sum(b.hasFlags(blockTypeSpec) for b in a) for a in assems)
        except ValueError:
            # In case assems is empty
            return 0

    def countFuelAxialBlocks(self):
        """
        Return the maximum number of fuel type blocks in any assembly in the core.

        See Also
        --------
        getFirstFuelBlockAxialNode
        """
        fuelblocks = (a.getBlocks(Flags.FUEL) for a in self.getAssemblies(includeBolAssems=True))
        try:
            return max(len(fuel) for fuel in fuelblocks)
        except ValueError:  # thrown when iterator is empty
            return 0

    def getFirstFuelBlockAxialNode(self):
        """
        Determine the offset of the fuel from the grid plate in the assembly with the lowest fuel
        block.

        This assembly will dictate at what block level the SASSYS reactivity coefficients will start
        to be generated
        """
        try:
            return min(
                i
                for a in self.getAssemblies(includeBolAssems=True)
                for (i, b) in enumerate(a)
                if b.hasFlags(Flags.FUEL)
            )
        except ValueError:
            # ValueError is thrown if min is called on an empty sequence.
            return float("inf")

    def getAssembliesInRing(
        self,
        ring,
        typeSpec=None,
        exactType=False,
        exclusions=None,
        overrideCircularRingMode=False,
    ) -> list[assemblies.Assembly]:
        """
        Returns the assemblies in a specified ring. Definitions of rings can change
        with problem parameters.

        This function acts as a switch between two separate functions that define what a
        ring is based on a cs setting 'circularRingMode'

        Parameters
        ----------
        ring : int
            The ring number

        typeSpec : str, list
            a string or list of assembly types of interest

        exactType : bool
            flag to match the assembly type exactly

        exclusions : list of assemblies
            list of assemblies that are not to be considered

        overrideCircularRingMode : bool, optional
            False ~ default: use circular/square/hex rings, just as the reactor defines them
            True ~ If you know you don't want to use the circular ring mode, and instead want square or hex.

        Returns
        -------
        aList : list of assemblies
            A list of assemblies that match the criteria within the ring
        """
        if self._circularRingMode and not overrideCircularRingMode:
            getter = self.getAssembliesInCircularRing
        else:
            getter = self.getAssembliesInSquareOrHexRing

        return getter(ring=ring, typeSpec=typeSpec, exactType=exactType, exclusions=exclusions)

    def getMaxAssembliesInHexRing(self, ring, fullCore=False):
        """
        Returns the maximum number of assemblies possible for a given Hexagonal ring.

        ring - The ring of interest to calculate the maximum number of assemblies.
        numEdgeAssems - The number of edge assemblies in the reactor model (1/3 core).

        Notes
        -----
        Assumes that odd rings do not have an edge assembly in third core geometry.
        """
        numAssemsUpToOuterRing = self.getNumAssembliesWithAllRingsFilledOut(ring)
        numAssemsUpToInnerRing = self.getNumAssembliesWithAllRingsFilledOut(ring - 1)
        maxAssemsInRing = numAssemsUpToOuterRing - numAssemsUpToInnerRing

        # See note*
        if not fullCore:
            ringMod = ring % 2
            if ringMod == 1:
                maxAssemsInRing -= 1

        return maxAssemsInRing

    def getAssembliesInSquareOrHexRing(
        self, ring, typeSpec=None, exactType=False, exclusions=None
    ) -> list[assemblies.Assembly]:
        """
        Returns the assemblies in a specified ring. Definitions of rings can change with problem
        parameters.

        Parameters
        ----------
        ring : int
            The ring number

        typeSpec : Flags or [Flags], optional
            a Flags instance or list of Flags with assembly types of interest

        exactType : bool
            flag to match the assembly type exactly

        exclusions : list of assemblies
            list of assemblies that are not to be considered

        Returns
        -------
        assems : list of assemblies
            A list of assemblies that match the criteria within the ring
        """
        assems = Sequence(self)

        if exclusions:
            exclusions = set(exclusions)
            assems.drop(lambda a: a in exclusions)

        # filter based on geomType
        if self.geomType == geometry.GeomType.CARTESIAN:  # a ring in cartesian is basically a square.
            assems.select(lambda a: any(xy == ring for xy in abs(a.spatialLocator.indices[:2])))
        else:
            assems.select(lambda a: (a.spatialLocator.getRingPos()[0] == ring))

        # filter based on typeSpec
        if typeSpec:
            assems.select(lambda a: a.hasFlags(typeSpec, exact=exactType))

        return list(assems)

    def getAssembliesInCircularRing(
        self, ring, typeSpec=None, exactType=False, exclusions=None
    ) -> list[assemblies.Assembly]:
        """
        Gets an assemblies within a circular range of the center of the core. This function allows
        for more circular styled assembly shuffling instead of the current hex approach.

        Parameters
        ----------
        ring : int
            The ring number

        typeSpec : Flags or list of Flags
            a Flags instance or list of Flags with assembly types of interest

        exactType : bool
            flag to match the assembly type exactly

        exclusions : list of assemblies
            list of assemblies that are not to be considered

        Returns
        -------
        assems : list of assemblies
            A list of assemblies that match the criteria within the ring
        """
        if self.geomType == geometry.GeomType.CARTESIAN:
            # a ring in cartesian is basically a square.
            raise RuntimeError("A circular ring in cartesian coordinates has not been defined yet.")

        # determine if the circularRingList has been generated
        if not self.circularRingList:
            self.circularRingList = self.buildCircularRingDictionary(self._circularRingPitch)

        assems = Sequence(self)

        # Remove exclusions
        if exclusions:
            exclusions = set(exclusions)
            assems.drop(lambda a: a in exclusions)

        # get assemblies at locations
        locSet = self.circularRingList[ring]
        assems.select(lambda a: a.getLocation() in locSet)

        if typeSpec:
            assems.select(lambda a: a.hasFlags(typeSpec, exact=exactType))

        return list(assems)

    def buildCircularRingDictionary(self, ringPitch=1.0):
        """
        Builds a dictionary of all circular rings in the core. This is required information for
        getAssembliesInCircularRing.

        The purpose of this function is to allow for more circular core shuffling in the hex design.

        Parameters
        ----------
        ringPitch : float, optional
            The relative pitch that should be used to define the spacing between each ring.
        """
        runLog.extra("Building a circular ring dictionary with ring pitch {}".format(ringPitch))
        referenceAssembly = self.childrenByLocator[self.spatialGrid[0, 0, 0]]
        refLocation = referenceAssembly.spatialLocator
        pitchFactor = ringPitch / self.spatialGrid.pitch

        circularRingDict = collections.defaultdict(set)

        for a in self:
            dist = a.spatialLocator.distanceTo(refLocation)
            # To reduce numerical sensitivity, round distance to 6 decimal places
            # before truncating.
            index = int(round(dist * pitchFactor, 6)) or 1  # 1 is the smallest ring.
            circularRingDict[index].add(a.getLocation())

        return circularRingDict

    def _getAssembliesByName(self):
        """
        If the assembly name-to-assembly object map is deleted or out of date, then this will
        regenerate it.
        """
        runLog.extra("Generating assemblies-by-name map.")

        # NOTE: eliminated unnecessary repeated lookups in self for self.assembliesByName
        self.assembliesByName = assymap = {}
        # don't includeAll b/c detailed ones are not ready yet
        for assem in self.getAssemblies(includeBolAssems=True, includeSFP=True):
            aName = assem.getName()
            if aName in assymap and assymap[aName] != assem:
                # dangerous situation that can occur in restart runs where the global assemNum isn't
                # updated. !=assem clause added because sometimes an assem is in one of the
                # includeAll lists that is also in the core and that's ok.
                runLog.error(
                    "Two (or more) assemblies in the reactor (and associated lists) have the name "
                    "{0},\nincluding {1} and {2}.".format(aName, assem, assymap[aName])
                )
                raise RuntimeError("Assembly name collision.")

            assymap[aName] = assem

    def getAssemblyByName(self, name: str) -> assemblies.Assembly:
        """
        Find the assembly that has this name.

        .. impl:: Get assembly by name.
            :id: I_ARMI_R_GET_ASSEM0
            :implements: R_ARMI_R_GET_ASSEM

            This method returns the :py:class:`assembly <armi.reactor.core.assemblies.Assembly>`
            with a name matching the value provided as an input parameter to this function. The
            ``name`` of an assembly is based on the ``assemNum`` parameter.

        Parameters
        ----------
        name : str
            the assembly name e.g. 'A0001'

        Returns
        -------
        Assembly

        See Also
        --------
        getAssembly : more general version of this method
        """
        return self.assembliesByName[name]

    def getAssemblies(
        self,
        typeSpec=None,
        sortKey=None,
        includeBolAssems=False,
        includeSFP=False,
        includeAll=False,
        zones=None,
        exact=False,
    ) -> list[assemblies.Assembly]:
        """
        Return a list of all the assemblies in the reactor.

        Assemblies from the Core are sorted based on the location-based Assembly comparison
        operators. This is done so that two reactors with physically identical properties are
        more likely to behave similarly when their assemblies may have been added in different
        orders.

        (In the future this will likely be replaced by sorting the _children list itself internally,
        as there is still opportunity for inconsistencies.)

        Parameters
        ----------
        typeSpec : Flags or iterable of Flags, optional
            List of assembly types that will be returned

        sortKey : callable, optional
            Sort predicate to use when sorting the assemblies.

        includeBolAssems : bool, optional
            Include the BOL assemblies as well as the ones that are in the core.
            Default: False

        includeSFP : bool, optional
            Include assemblies in the SFP

        includeAll : bool, optional
            Will include ALL assemblies.

        zones : iterable, optional
            Only include assemblies that are in this these zones
        """
        if includeAll:
            includeBolAssems = includeSFP = True

        assems = []
        if includeBolAssems and self.parent is not None and self.parent.blueprints is not None:
            assems.extend(self.parent.blueprints.assemblies.values())

        assems.extend(a for a in sorted(self, key=sortKey))

        if includeSFP and self.parent is not None and self.parent.excore.get("sfp") is not None:
            assems.extend(self.parent.excore.sfp.getChildren())

        if typeSpec:
            assems = [a for a in assems if a.hasFlags(typeSpec, exact=exact)]

        if zones:
            zoneLocs = self.zones.getZoneLocations(zones)
            assems = [a for a in assems if a.getLocation() in zoneLocs]

        return assems

    def getNozzleTypes(self):
        r"""
        Get a dictionary of all of the assembly ``nozzleType``\ s in the core.

        Returns
        -------
        nozzles : dict
            A dictionary of ``{nozzleType: nozzleID}`` pairs, where the nozzleIDs are
            numbers corresponding to the alphabetical order of the ``nozzleType`` names.

        Notes
        -----
        Getting the ``nozzleID`` by alphabetical order could cause a problem if a new
        ``nozzleType`` is added during a run. This problem should not occur with the
        ``includeBolAssems=True`` argument provided.
        """
        nozzleList = list(set(a.p.nozzleType for a in self.getAssemblies(includeBolAssems=True)))
        return {nozzleType: i for i, nozzleType in enumerate(sorted(nozzleList))}

    def getBlockByName(self, name: str) -> blocks.Block:
        """
        Finds a block based on its name.

        Parameters
        ----------
        name : str
            Block name e.g. A0001A

        Returns
        -------
        Block : the block with the name

        Notes
        -----
        The blocksByName structure must be up to date for this to work properly.
        """
        try:
            return self.blocksByName[name]
        except AttributeError:
            self._genBlocksByName()
            return self.blocksByName[name]

    def getBlocksByIndices(self, indices) -> list[blocks.Block]:
        """Get blocks in assemblies by block indices."""
        blocks = []
        for i, j, k in indices:
            assem = self.childrenByLocator[self.spatialGrid[i, j, 0]]
            blocks.append(assem[k])
        return blocks

    def _genBlocksByName(self):
        """If self.blocksByName is deleted, then this will regenerate it."""
        self.blocksByName = {block.getName(): block for block in self.getBlocks(includeAll=True)}

    # This will likely fail, but it will help diagnose why property approach wasn't working
    # correctly
    def genBlocksByLocName(self):
        """If self.blocksByLocName is deleted, then this will regenerate it or update it if things change."""
        self.blocksByLocName = {block.getLocation(): block for block in self.getBlocks(includeAll=True)}

    def getBlocks(self, bType=None, **kwargs) -> list[blocks.Block]:
        """
        Returns an iterator over all blocks in the reactor in order.

        Parameters
        ----------
        bType : list or Flags, optional
            Restrict results to a specific block type such as Flags.FUEL, Flags.SHIELD, etc.

        includeBolAssems : bool, optional
            Include the BOL-Assembly blocks as well. These blocks are created at BOL
            and used to create new assemblies, etc. If true, the blocks in these
            assemblies will be returned as well as the ones in the reactor.

        kwargs : dict
            Any keyword argument from :meth:`getAssemblies`

        Returns
        -------
        blocks : iterator
            all blocks in the reactor (or of type requested)

        See Also
        --------
        * :meth:`iterBlocks`: iterator over blocks with limited filtering.
        * :meth:`getAssemblies` : locates the assemblies in the search
        """
        blocks = [b for a in self.getAssemblies(**kwargs) for b in a]
        if bType:
            blocks = [b for b in blocks if b.hasFlags(bType)]
        return blocks

    def getFirstBlock(self, blockType=None, exact=False) -> blocks.Block:
        """
        Return the first block of the requested type in the reactor, or return first block.
        exact=True will only match fuel, not testfuel, for example.

        Parameters
        ----------
        blockType : Flags, optional
            The type of block to return

        exact : bool, optional
            Requires an exact match on blockType

        Returns
        -------
        b : Block object (or None if no such block exists)
        """
        for a in self:
            for b in a:
                if b.hasFlags(blockType, exact):
                    return b

        return None

    def getFirstAssembly(self, typeSpec=None, exact=False) -> assemblies.Assembly:
        """
        Gets the first assembly in the reactor.

        Warning
        -------
        This function should be used with great care. There are **very** few
        circumstances in which one wants the "first" of a given sort of assembly,
        `whichever that may happen to be`. Precisely which assembly is returned is
        sensitive to all sorts of implementation details in Grids, etc., which make the
        concept of "first" rather slippery. Prefer using some sort of precise logic to
        pick a specific assembly from the Core.

        Parameters
        ----------
        typeSpec : Flags or iterable of Flags, optional
        """
        if typeSpec:
            try:
                return next(a for a in self if a.hasFlags(typeSpec, exact))
            except StopIteration:
                runLog.warning("No assem of type {0} in reactor".format(typeSpec))
                return None

        # Assumes at least one assembly in `self`
        return next(iter(self))

    def regenAssemblyLists(self):
        """
        If the attribute lists which contain assemblies are deleted (such as by reactors.detachAllAssemblies),
        then this function will call the other functions to regrow them.
        """
        self._getAssembliesByName()
        self._genBlocksByName()
        self._genChildByLocationLookupTable()

    def getAllXsSuffixes(self):
        """Return all XS suffices (e.g. AA, AB, etc.) in the core."""
        return sorted(set(b.getMicroSuffix() for b in self.iterBlocks()))

    def getNuclideCategories(self):
        """
        Categorize nuclides as coolant, fuel and structure.

        Notes
        -----
        This is used to categorize nuclides for Doppler broadening. Control nuclides are treated as structure.

        The categories are defined in the following way:

        1. Add nuclides from coolant components to coolantNuclides
        2. Add nuclides from fuel components to fuelNuclides (this may be incomplete, e.g.
           at BOL there are no fission products)
        3. Add nuclides from all other components to structureNuclides
        4. Since fuelNuclides may be incomplete, add anything else the user wants to model
           that isn't already listed in coolantNuclides or structureNuclides.

        Returns
        -------
        coolantNuclides : set
            set of nuclide names

        fuelNuclides : set
            set of nuclide names

        structureNuclides : set
            set of nuclide names
        """
        if not self._nuclideCategories:
            coolantNuclides = set()
            fuelNuclides = set()
            structureNuclides = set()
            for c in self.iterComponents():
                compNuclides = []
                # get only nuclides with non-zero number density
                # nuclides could be present at 0.0 density just for XS generation
                if c.p.numberDensities is None:
                    continue
                for nuc, dens in zip(c.p.nuclides, c.p.numberDensities):
                    if dens > 0.0:
                        compNuclides.append(nuc.decode())
                if c.getName() == "coolant":
                    coolantNuclides.update(compNuclides)
                elif "fuel" in c.getName():
                    fuelNuclides.update(compNuclides)
                else:
                    structureNuclides.update(compNuclides)
            structureNuclides -= coolantNuclides
            structureNuclides -= fuelNuclides
            remainingNuclides = set(self.parent.blueprints.allNuclidesInProblem) - structureNuclides - coolantNuclides
            fuelNuclides.update(remainingNuclides)
            self._nuclideCategories["coolant"] = coolantNuclides
            self._nuclideCategories["fuel"] = fuelNuclides
            self._nuclideCategories["structure"] = structureNuclides
            self.summarizeNuclideCategories()

        return (
            self._nuclideCategories["coolant"],
            self._nuclideCategories["fuel"],
            self._nuclideCategories["structure"],
        )

    def summarizeNuclideCategories(self):
        """Write summary table of the various nuclide categories within the reactor."""
        runLog.info(
            "Nuclide categorization for cross section temperature assignments:\n"
            + tabulate.tabulate(
                [
                    (
                        "Fuel",
                        createFormattedStrWithDelimiter(self._nuclideCategories["fuel"]),
                    ),
                    (
                        "Coolant",
                        createFormattedStrWithDelimiter(self._nuclideCategories["coolant"]),
                    ),
                    (
                        "Structure",
                        createFormattedStrWithDelimiter(self._nuclideCategories["structure"]),
                    ),
                ],
                headers=["Nuclide Category", "Nuclides"],
                tableFmt="armi",
            )
        )

    def getLocationContents(self, locs, assemblyLevel=False, locContents=None):
        """
        Given a list of locations, this goes through and finds the blocks or assemblies.

        Parameters
        ----------
        locs : list of location objects or strings
            The locations you'd like to find assemblies in
        assemblyLevel : bool, optional
            If True, will find assemblies rather than blocks
        locContents : dict, optional
            A lookup table with location string keys and block/assembly values
            useful if you want to call this function many times and would like a speedup.

        Returns
        -------
        blockList : iterable
            List of blocks or assemblies that correspond to the locations passed in

        Notes
        -----
        Useful in reading the db.

        See Also
        --------
        makeLocationLookup : allows caching to speed this up if you call it a lot.
        """
        # Why isn't locContents an attribute of reactor? It could be another
        # property that is generated on demand
        if not locContents:
            locContents = self.makeLocationLookup(assemblyLevel)
        try:
            # now look 'em up
            return [locContents[str(loc)] for loc in locs]
        except KeyError as e:
            raise KeyError("There is nothing in core location {0}.".format(e))

    def makeLocationLookup(self, assemblyLevel=False):
        """
        Build a location-keyed lookup table to figure out which block (or
        assembly, if assemblyLevel=True) is in which location. Used within
        getLocationContents, but can also be used to pre-build a cache for that
        function, speeding the lookup with a cache.

        See Also
        --------
        getLocationContents : can use this lookup table to go faster.
        """
        # build a lookup table one time.
        if assemblyLevel:
            return {a.getLocation(): a for a in self}
        else:
            return {b.getLocation(): b for a in self for b in a}

    def getFluxVector(self, energyOrder=0, adjoint=False, extSrc=False, volumeIntegrated=True):
        """
        Return the multigroup real or adjoint flux of the entire reactor as a vector.

        Order of meshes is based on getBlocks

        Parameters
        ----------
        energyOrder : int, optional
            A value of 0 implies that the flux will have all energy groups for the first mesh point,
            and then all energy groups for the next mesh point, etc.

            A value of 1 implies that the flux will have values for all mesh points of the first
            energy group first, followed by all mesh points for the second energy group, etc.

        adjoint : bool, optional
            If True, will return adjoint flux instead of real flux.

        extSrc : bool, optional
            If True, will return external source instead of real flux.

        volumeIntegrated : bool, optional
            If true (default), flux units will be #-cm/s. If false, they will be #-cm^2/s

        Returns
        -------
        vals : list
            The values you requested. length is NxG.
        """
        flux = []
        groups = range(self.lib.numGroups)

        # build in order 0
        for b in self.iterBlocks():
            if adjoint:
                vals = b.p.adjMgFlux
            elif extSrc:
                vals = b.p.extSrc
            else:
                vals = b.p.mgFlux

            if not volumeIntegrated:
                vol = b.getVolume()
                vals = [v / vol for v in vals]

            flux.extend(vals)

        if energyOrder == 1:
            # swap order
            newFlux = []
            for g in groups:
                oneGroup = [flux[i] for i in range(g, len(flux), len(groups))]
                newFlux.extend(oneGroup)
            flux = newFlux

        return np.array(flux)

    def getAssembliesOfType(self, typeSpec, exactMatch=False):
        """Return a list of assemblies in the core that are of type assemType."""
        return self.getChildrenWithFlags(typeSpec, exactMatch=exactMatch)

    def getAssembly(self, assemNum=None, locationString=None, assemblyName=None, *args, **kwargs):
        """
        Finds an assembly in the core.

        Parameters
        ----------
        assemNum : int, optional
            Returns the assembly with this assemNum
        locationString : str
            A location string
        assemblyName : str, optional
            The assembly name
        *args : additional optional arguments for self.getAssemblies

        Returns
        -------
        a : Assembly
            The assembly that matches, or None if nothing is found

        See Also
        --------
        getAssemblyByName
        getAssemblyWithStringLocation
        getLocationContents : a much more efficient way to look up assemblies in a list of locations
        """
        if assemblyName:
            return self.getAssemblyByName(assemblyName)

        for a in self.getAssemblies(*args, **kwargs):
            if a.getLocation() == locationString:
                return a
            if a.getNum() == assemNum:
                return a

        return None

    def getAssemblyWithAssemNum(self, assemNum):
        """
        Retrieve assembly with a particular assembly number from the core.

        Parameters
        ----------
        assemNum : int
            The assembly number of interest

        Returns
        -------
        foundAssembly : Assembly object or None
            The assembly found, or None
        """
        return self.getAssembly(assemNum=assemNum)

    def getAssemblyWithStringLocation(self, locationString):
        """Returns an assembly or none if given a location string like '001-001'.

        .. impl:: Get assembly by location.
            :id: I_ARMI_R_GET_ASSEM1
            :implements: R_ARMI_R_GET_ASSEM

            This method returns the :py:class:`assembly <armi.reactor.core.assemblies.Assembly>`
            located in the requested location. The location is provided to this method as an input
            parameter in a string with the format "001-001". For a :py:class:`HexGrid
            <armi.reactor.grids.hexagonal.HexGrid>`, the first number indicates the hexagonal ring
            and the second number indicates the position within that ring. For a
            :py:class:`CartesianGrid <armi.reactor.grids.cartesian.CartesianGrid>`, the first number
            represents the x index and the second number represents the y index. If there is no
            assembly in the grid at the requested location, this method returns None.
        """
        ring, pos, _ = grids.locatorLabelToIndices(locationString)
        loc = self.spatialGrid.getLocatorFromRingAndPos(ring, pos)
        assem = self.childrenByLocator.get(loc)
        return assem

    def getAssemblyPitch(self):
        """
        Find the assembly pitch for the whole core.

        This returns the pitch according to the spatialGrid. To capture any thermal/hydraulic
        feedback of the core pitch, T/H modules will need to modify the grid pitch directly based
        on the relevant mechanical assumptions.

        Returns
        -------
        pitch : float
            The assembly pitch.
        """
        return self.spatialGrid.pitch

    def findNeighbors(self, a, showBlanks=True, duplicateAssembliesOnReflectiveBoundary=False):
        r"""
        Find assemblies that are next to this assembly.

        Return a list of neighboring assemblies.

        For a hexagonal grid, the list begins from the 30 degree point (point 1) then moves
        counterclockwise around.

        For a Cartesian grid, the order of the neighbors is east, north, west, south.

        .. impl:: Retrieve neighboring assemblies of a given assembly.
            :id: I_ARMI_R_FIND_NEIGHBORS
            :implements: R_ARMI_R_FIND_NEIGHBORS

            This method takes an :py:class:`Assembly
            <armi.reactor.assemblies.Assembly>` as an input parameter and returns
            a list of the assemblies neighboring that assembly. There are 6
            neighbors in a hexagonal grid and 4 neighbors in a Cartesian grid.
            The (i, j) indices of the neighbors are provided by
            :py:meth:`getNeighboringCellIndices
            <armi.reactor.grids.StructuredGrid.getNeighboringCellIndices>`. For
            a hexagonal grid, the (i, j) indices are converted to (ring,
            position) indexing using the ``core.spatialGrid`` instance attribute.

            The ``showBlanks`` option determines whether non-existing assemblies
            will be indicated with a ``None`` in the list or just excluded from
            the list altogether.

            The ``duplicateAssembliesOnReflectiveBoundary`` setting only works for
            1/3 core symmetry with periodic boundary conditions. For these types
            of geometries, if this setting is ``True``\ , neighbor lists for
            assemblies along a periodic boundary will include the assemblies
            along the opposite periodic boundary that are effectively neighbors.

        Parameters
        ----------
        a : Assembly object
            The assembly to find neighbors of.

        showBlanks : Boolean, optional
            If True, the returned array of 6 neighbors will return "None" for
            neighbors that do not explicitly exist in the 1/3 core model
            (including many that WOULD exist in a full core model).

            If False, the returned array will not include the "None" neighbors.
            If one or more neighbors does not explicitly exist in the 1/3 core
            model, the returned array will have a length of less than 6.

        duplicateAssembliesOnReflectiveBoundary : Boolean, optional
            If True, findNeighbors duplicates neighbor assemblies into their
            "symmetric identicals" so that even assemblies that border symmetry
            lines will have 6 neighbors. The only assemblies that will have
            fewer than 6 neighbors are those that border the outer core boundary
            (usually vacuum).

            If False, findNeighbors returns None for assemblies that do not
            exist in a 1/3 core model (but WOULD exist in a full core model).

            For example, applying findNeighbors for the central assembly (ring,
            pos) = (1, 1) in 1/3 core symmetry (with
            duplicateAssembliesOnReflectiveBoundary = True) would return a list
            of 6 assemblies, but those 6 would really only be assemblies (2, 1)
            and (2, 2) repeated 3 times each.

            Note that the value of duplicateAssembliesOnReflectiveBoundary only
            really matters if showBlanks == True. This will have no effect if
            the model is full core since asymmetric models could find many
            duplicates in the other thirds

        Notes
        -----
        The duplicateAssembliesOnReflectiveBoundary setting only works for third
        core symmetry.

        This uses the 'mcnp' index map (MCNP GEODST hex coordinates) instead of
        the standard (ring, pos) map. because neighbors have consistent indices
        this way. We then convert over to (ring, pos) using the lookup table
        that a reactor has.

        Returns
        -------
        neighbors : list of assembly objects
            This is a list of "nearest neighbors" to assembly a.

            If showBlanks = False, it will return fewer than the maximum number
            of neighbors if not all neighbors explicitly exist in the core
            model. For a hexagonal grid, the maximum number of neighbors is 6.
            For a Cartesian grid, the maximum number is 4.

            If showBlanks = True and duplicateAssembliesOnReflectiveBoundary =
            False, it will have a "None" for assemblies that do not exist in the
            1/3 model.

            If showBlanks = True and duplicateAssembliesOnReflectiveBoundary =
            True, it will return the existing "symmetric identical" assembly of
            a non-existing assembly. It will only return "None" for an assembly
            when that assembly is non-existing AND has no existing "symmetric
            identical".

        See Also
        --------
        grids.Grid.getSymmetricEquivalents
        """
        neighborIndices = self.spatialGrid.getNeighboringCellIndices(*a.spatialLocator.getCompleteIndices())

        dupReflectors = (
            self.symmetry.domain == geometry.DomainType.THIRD_CORE
            and self.symmetry.boundary == geometry.BoundaryType.PERIODIC
            and duplicateAssembliesOnReflectiveBoundary
        )

        neighbors = []
        for iN, jN, kN in neighborIndices:
            neighborLoc = self.spatialGrid[iN, jN, kN]
            neighbor = self.childrenByLocator.get(neighborLoc)
            if neighbor is not None:
                neighbors.append(neighbor)
            elif showBlanks:
                if dupReflectors:
                    symmetricAssem = self._getReflectiveDuplicateAssembly(neighborLoc)
                    neighbors.append(symmetricAssem)
                else:
                    neighbors.append(None)

        return neighbors

    def _getReflectiveDuplicateAssembly(self, neighborLoc):
        """
        Return duplicate assemblies across symmetry line.

        Notes
        -----
        If an existing symmetric identical has been found, return it.
        If an existing symmetric identical has NOT been found, return a None (it's empty).
        """
        duplicates = []
        otherTwoLocations = self.spatialGrid.getSymmetricEquivalents(neighborLoc)
        for i, j in otherTwoLocations:
            neighborLocation2 = self.spatialGrid[i, j, 0]
            duplicateAssem = self.childrenByLocator.get(neighborLocation2)
            if duplicateAssem is not None:
                duplicates.append(duplicateAssem)

        # should always be 0 or 1
        nDuplicates = len(duplicates)
        if nDuplicates == 1:
            return duplicates[0]
        elif nDuplicates > 1:
            raise ValueError("Too many neighbors found!")
        return None

    def setMoveList(self, cycle, oldLoc, newLoc, enrichList, assemblyType, assemName):
        """Tracks the movements in terms of locations and enrichments."""
        data = (oldLoc, newLoc, enrichList, assemblyType, assemName)
        if self.moves.get(cycle) is None:
            self.moves[cycle] = []
        if data in self.moves[cycle]:
            # remove the old version and throw the new on at the end.
            self.moves[cycle].remove(data)
        self.moves[cycle].append(data)

    def createFreshFeed(self, cs=None):
        """
        Creates a new feed assembly.

        Parameters
        ----------
        cs : Settings
            Global settings for the case

        See Also
        --------
        createAssemblyOfType: creates an assembly
        """
        return self.createAssemblyOfType(assemType=self._freshFeedType, cs=cs)

    def createAssemblyOfType(self, assemType=None, enrichList=None, cs=None):
        """
        Create an assembly of a specific type and apply enrichments if they are specified.

        Parameters
        ----------
        assemType : str
            The assembly type to create
        enrichList : list
            weight percent enrichments of each block
        cs : Settings
            Global settings for the case

        Returns
        -------
        a : Assembly
            A new assembly

        Notes
        -----
        This and similar fuel shuffle-enabling functionality on the Core are responsible
        for coupling between the Core and Blueprints. Technically, it should not be
        required to involve Blueprints at all in the construction of a Reactor model.
        Therefore in some circumstances, this function will not work. Ultimately, this
        should be purely the domain of blueprints themselves, and may be migrated out of
        Core in the future.

        See Also
        --------
        armi.fuelHandler.doRepeatShuffle : uses this to repeat shuffling
        """
        a = self.parent.blueprints.constructAssem(cs, name=assemType)

        # check to see if a default bol assembly is being used or we are adding more information
        if enrichList:
            # got an enrichment list that should be the same height as the fuel blocks
            if isinstance(enrichList, float):
                # make endlessly iterable if float was passed in
                enrichList = itertools.cycle([enrichList])
            elif len(a) != len(enrichList):
                raise RuntimeError("{0} and enrichment list do not have the same number of blocks.".format(a))

            for b, enrich in zip(a, enrichList):
                if enrich == 0.0:
                    # don't change blocks when enrich specified as 0
                    continue
                if abs(b.getUraniumMassEnrich() - enrich) > 1e-10:
                    # only adjust block enrichment if it's different.
                    # WARNING: If this is not fresh fuel, this messes up the number of moles of HM at BOL and
                    # therefore breaks the burnup metric.
                    b.adjustUEnrich(enrich)

        if not self._detailedAxialExpansion:
            # if detailedAxialExpansion: False, make sure that the assembly being created has the correct core mesh
            a.setBlockMesh(self.p.referenceBlockAxialMesh[1:], conserveMassFlag="auto")  # pass [1:] to skip 0.0

        return a

    def saveAllFlux(self, fName="allFlux.txt"):
        """Dump all flux to file for debugging purposes."""
        groups = range(self.lib.numGroups)
        with open(fName, "w") as f:
            for block in self.iterBlocks():
                for gi in groups:
                    f.write(
                        "{:10s} {:10d} {:12.5E} {:12.5E} {:12.5E}\n".format(
                            block.getName(),
                            gi,
                            block.p.mgFlux[gi],
                            block.p.adjMgFlux[gi],
                            block.getVolume(),
                        )
                    )
                if len(block.p.mgFlux) > len(groups) or len(block.p.adjMgFlux) > len(groups):
                    raise ValueError(
                        "Too many flux values: {}\n{}\n{}".format(block, block.p.mgFlux, block.p.adjMgFlux)
                    )

    def getAssembliesOnSymmetryLine(self, symmetryLineID):
        """Find assemblies that are on a symmetry line in a symmetric core."""
        assembliesOnLine = []
        for a in self:
            if a.isOnWhichSymmetryLine() == symmetryLineID:
                assembliesOnLine.append(a)

        # in order of innermost to outermost (for averaging)
        assembliesOnLine.sort(key=lambda a: a.spatialLocator.getRingPos())
        return assembliesOnLine

    def getCoreRadius(self):
        """Returns a radius that the core would fit into."""
        return self.getNumRings(indexBased=True) * self.getFirstBlock().getPitch()

    def findAllMeshPoints(self, assems=None, applySubMesh=True):
        """
        Return all mesh positions in core including both endpoints.

        .. impl:: Construct a mesh based on core blocks.
            :id: I_ARMI_R_MESH
            :implements: R_ARMI_R_MESH

            This method iterates through all of the assemblies provided, or all
            assemblies in the core if no list of ``assems`` is provided, and
            constructs a tuple of three lists which contain the unique i, j, and
            k mesh coordinates, respectively. The ``applySubMesh`` setting
            controls whether the mesh will include the submesh coordinates. For
            a standard assembly-based reactor geometry with a hexagonal or
            Cartesian assembly grid, this method is only used to produce axial
            (k) mesh points. If multiple assemblies are provided with different
            axial meshes, the axial mesh list will contain the union of all
            unique mesh points. Duplicate mesh points are removed.

        Parameters
        ----------
        assems : list, optional
            assemblies to consider when determining the mesh points. If not given, all in-core assemblies are used.
        applySubMesh : bool, optional
            Apply submeshing parameters to make mesh points smaller than blocks. Default=True.

        Returns
        -------
        meshVals : tuple
            ((i-vals), (j-vals,), (k-vals,))

        See Also
        --------
        armi.reactor.assemblies.Assembly.getAxialMesh : get block mesh

        Notes
        -----
        These include all mesh points, not just block boundaries. There may be multiple mesh points
        per block.

        If a large block with multiple mesh points is in the same core as arbitrarily-expanded fuel blocks
        from fuel performance, an imbalanced axial mesh may result.

        There is a challenge with TRZ blocks because we need the mesh centroid in terms of RZT, not XYZ

        When determining the submesh, it is important to not use too small of a rounding precision. It was
        found that when using a precision of units.FLOAT_DIMENSION_DECIMALS, that the division in `step`
        can produce mesh points that are the same up to the 9th or 10th digit, resulting in a repeated
        mesh point. This repetition results in problems in downstream methods, such as the uniform mesh converter.
        """
        runLog.debug("Finding all mesh points.")
        if assems is None:
            assems = list(self)

        iMesh, jMesh, kMesh = set(), set(), set()
        for a in assems:
            for b in a:
                # these params should be combined into a new b.p.meshSubdivisions tuple
                numPoints = (a.p.AziMesh, a.p.RadMesh, b.p.axMesh) if applySubMesh else (1, 1, 1)
                base = b.spatialLocator.getGlobalCellBase()
                # make sure this is in mesh coordinates (important to have TRZ, not XYZ in TRZ cases
                top = b.spatialLocator.getGlobalCellTop()
                for axis, (collection, subdivisions) in enumerate(zip((iMesh, jMesh, kMesh), numPoints)):
                    axisVal = float(base[axis])  # convert from np.float64
                    step = float(top[axis] - axisVal) / subdivisions
                    for _subdivision in range(subdivisions):
                        collection.add(round(axisVal, units.FLOAT_DIMENSION_DECIMALS))
                        axisVal += step
                    # add top too (only needed for last point)
                    collection.add(round(axisVal, units.FLOAT_DIMENSION_DECIMALS))

        iMesh, jMesh, kMesh = map(sorted, (iMesh, jMesh, kMesh))

        return iMesh, jMesh, kMesh

    def findAllAxialMeshPoints(self, assems=None, applySubMesh=True):
        """Return a list of all z-mesh positions in the core including zero and the top."""
        _i, _j, k = self.findAllMeshPoints(assems, applySubMesh)
        return k

    def updateAxialMesh(self):
        """
        Update axial mesh based on perturbed meshes of the assemblies that are linked to the ref assem.

        Notes
        -----
        While processLoading finds *all* axial mesh points, this method only updates the values of the
        known mesh with the current assembly heights. **This does not change the number of mesh points**.

        If ``detailedAxialExpansion`` is active, the global axial mesh param still only tracks the refAssem.
        Otherwise, thousands upon thousands of mesh points would get created.

        See Also
        --------
        processLoading : sets up the primary mesh that this perturbs.
        """
        # most of the time, we want fuel, but they should mostly have the same number of blocks
        # if this becomes a problem, we might find either the
        #  1. mode: (len(a) for a in self).mode(), or
        #  2. max: max(len(a) for a in self)
        # depending on what makes the most sense
        refAssem = self.refAssem
        refMesh = self.findAllAxialMeshPoints([refAssem])
        avgHeight = average1DWithinTolerance(
            np.array(
                [
                    [h for b in a for h in [(b.p.ztop - b.p.zbottom) / b.p.axMesh] * b.p.axMesh]
                    for a in self
                    if self.findAllAxialMeshPoints([a]) == refMesh
                ]
            )
        )
        self.p.axialMesh = list(np.append([0.0], avgHeight.cumsum()))

    def findAxialMeshIndexOf(self, heightCm):
        """
        Return the axial index of the axial node corresponding to this height.

        If the height lies on the boundary between two nodes, the lower node index
        is returned.

        Parameters
        ----------
        heightCm : float
            The height (cm) from the assembly bottom.

        Returns
        -------
        zIndex : int
            The axial index (beginning with 0) of the mesh node containing the given height.
        """
        for zi, currentHeightCm in enumerate(self.p.axialMesh[1:]):
            if currentHeightCm >= heightCm:
                return zi
        raise ValueError(
            "The value {} cm is not within range of the reactor axial mesh with max {}".format(
                heightCm, currentHeightCm
            )
        )

    def addMoreNodes(self, meshList):
        """Add additional mesh points in the the meshList so that the ratio of mesh sizes does not vary too fast."""
        ratio = self._minMeshSizeRatio
        for i, innerMeshVal in enumerate(meshList[1:-1], start=1):
            dP0 = innerMeshVal - meshList[i - 1]
            dP1 = meshList[i + 1] - innerMeshVal

            if dP0 / (dP0 + dP1) < ratio:
                runLog.warning("Mesh gap too small. Adjusting mesh to be more reasonable.")
                meshList.append(innerMeshVal + dP1 * ratio)
                meshList.sort()
                return meshList, False
            elif dP0 / (dP0 + dP1) > (1.0 - ratio):
                runLog.warning("Mesh gap too large. Adjusting mesh to be more reasonable.")
                meshList.append(meshList[i - 1] + dP0 * (1.0 - ratio))
                meshList.sort()
                return meshList, False

        return meshList, True

    def findAllAziMeshPoints(self, extraAssems=None, applySubMesh=True):
        """
        Returns a list of all azimuthal (theta)-mesh positions in the core.

        Parameters
        ----------
        extraAssems : list
            additional assemblies to consider when determining the mesh points.
            They may be useful in the MCPNXT models to represent the fuel management dummies.

        applySubMesh : bool
            generates submesh points to further discretize the theta reactor mesh
        """
        i, _, _ = self.findAllMeshPoints(extraAssems, applySubMesh)
        return i

    def findAllRadMeshPoints(self, extraAssems=None, applySubMesh=True):
        """
        Return a list of all radial-mesh positions in the core.

        Parameters
        ----------
        extraAssems : list
            additional assemblies to consider when determining the mesh points. They may be useful
            in the MCPNXT models to represent the fuel management dummies.

        applySubMesh : bool
            (not implemented) generates submesh points to further discretize the radial reactor mesh
        """
        _, j, _ = self.findAllMeshPoints(extraAssems, applySubMesh)
        return j

    def getMaxBlockParam(self, *args, **kwargs):
        """Get max param over blocks."""
        if "generationNum" in kwargs:
            raise ValueError("Cannot getMaxBlockParam over anything but blocks. Prefer `getMaxParam`.")
        kwargs["generationNum"] = 2
        return self.getMaxParam(*args, **kwargs)

    def getTotalBlockParam(self, *args, **kwargs):
        """Get total param over blocks."""
        if "generationNum" in kwargs:
            raise ValueError("Cannot getTotalBlockParam over anything but blocks. Prefer `calcTotalParam`.")
        kwargs["generationNum"] = 2
        return self.calcTotalParam(*args, **kwargs)

    def getMaxNumPins(self):
        """Find max number of pins of any block in the reactor."""
        return max(b.getNumPins() for b in self.iterBlocks())

    def getMinimumPercentFluxInFuel(self, target=0.005):
        """
        Starting with the outer ring, this method goes through the entire Reactor to determine what
        percentage of flux occurs at each ring.

        Parameters
        ----------
        target : float
            This is the fraction of the total reactor fuel flux compared to the flux in a specific
            assembly in a ring

        Returns
        -------
        targetRing, fraction of flux : tuple
            targetRing is the ring with the fraction of flux that best meets the target.
        """
        # get the total number of assembly rings
        numRings = self.getNumRings()

        # old target assembly fraction
        fluxFraction = 0
        targetRing = numRings

        allFuelBlocks = self.getBlocks(Flags.FUEL)

        # loop there all of the rings
        for ringNumber in range(numRings, 0, -1):
            # Compare to outer most ring. flatten list into one list of all blocks
            blocksInRing = list(
                itertools.chain.from_iterable([a.iterBlocks(Flags.FUEL) for a in self.getAssembliesInRing(ringNumber)])
            )

            totalPower = self.getTotalBlockParam("flux", objs=allFuelBlocks)
            ringPower = self.getTotalBlockParam("flux", objs=blocksInRing)

            # make sure that there is a non zero return
            if fluxFraction == 0 and ringPower > 0:
                fluxFraction = ringPower / totalPower
                targetRing = ringNumber

            # this will only get the leakage if the target fraction isn't too low
            if ringPower / totalPower < target and ringPower / totalPower > fluxFraction:
                fluxFraction = ringPower / totalPower
                targetRing = ringNumber

        return targetRing, fluxFraction

    def getAvgTemp(self, typeSpec, blockList=None, flux2Weight=False):
        """
        Get the volume-average fuel, cladding, coolant temperature in core.

        Parameters
        ----------
        typeSpec : Flags or list of Flags
            Component types to consider. If typeSpec is a list, then you get the volume average
            temperature of all components. For instance, getAvgTemp([Flags.CLAD, Flags.WIRE,
            Flags.DUCT]) returns the avg. structure temperature.

        blockList : list, optional
            Blocks to consider. If None, all blocks in core will be considered

        flux2Weight : bool, optional
            If true, will weight temperature against flux**2

        Returns
        -------
        avgTemp : float
            The average temperature in C.
        """
        num = 0.0
        denom = 0.0
        if not blockList:
            blockList = self.getBlocks()

        for b in blockList:
            if flux2Weight:
                weight = b.p.flux**2.0
            else:
                weight = 1.0
            for c in b.iterComponents(typeSpec):
                vol = c.getVolume()
                num += c.temperatureInC * vol * weight
                denom += vol * weight

        if denom:
            return num / denom
        else:
            raise RuntimeError("no temperature average for {0}".format(typeSpec))

    def growToFullCore(self, cs):
        """Copies symmetric assemblies to build a full core model out of a 1/3 core model.

        Returns
        -------
        converter : GeometryConverter
            Geometry converter used to do the conversion.
        """
        from armi.reactor.converters.geometryConverters import (
            ThirdCoreHexToFullCoreChanger,
        )

        converter = ThirdCoreHexToFullCoreChanger(cs)
        converter.convert(self.r)

        return converter

    def setPitchUniform(self, pitchInCm):
        """Set the pitch in all blocks."""
        for b in self.iterBlocks():
            b.setPitch(pitchInCm)

        # have to update the 2-D reactor mesh too.
        self.spatialGrid.changePitch(pitchInCm)

    def calcBlockMaxes(self):
        """
        Searches all blocks for maximum values of key params.

        See Also
        --------
        armi.physics.optimize.OptimizationInterface.interactBOL : handles these maxes in optimization cases
        """
        # restrict to fuel
        for k in self.p.paramDefs.inCategory("block-max").names:
            try:
                maxVal = self.getMaxBlockParam(k.replace("max", ""), Flags.FUEL)
                if maxVal != 0.0:
                    self.p[k] = maxVal
            except KeyError:
                continue

        # add maxes based on pin-level max if it exists, block level max otherwise.
        self.p.maxBuF = max(
            (a.getMaxParam("percentBu") for a in self.getAssemblies(Flags.FEED | Flags.FUEL)),
            default=0.0,
        )
        self.p.maxBuI = max(
            (
                a.getMaxParam("percentBu")
                for a in self.getAssemblies(
                    [
                        Flags.IGNITER | Flags.FUEL,
                        Flags.DRIVER | Flags.FUEL,
                        Flags.STARTER | Flags.FUEL,
                    ]
                )
            ),
            default=0.0,
        )

    def getFuelBottomHeight(self):
        """
        Obtain the height of the lowest fuel in the core.

        This is the "axial coordinate shift" between ARMI and SASSYS.
        While ARMI sets z=0 at the bottom of the lowest block (usually the
        grid plate), SASSYS sets z=0 at the bottom of the fuel.

        Returns
        -------
        lowestFuelHeightInCm : float
            The height (cm) of the lowest fuel in this core model.
        """
        lowestFuelHeightInCm = self[0].getHeight()
        fuelBottoms = []
        for a in self.getAssemblies(Flags.FUEL):
            fuelHeightInCm = 0.0
            for b in a:
                if b.hasFlags(Flags.FUEL):
                    break
                else:
                    fuelHeightInCm += b.getHeight()
            if fuelHeightInCm < lowestFuelHeightInCm:
                lowestFuelHeightInCm = fuelHeightInCm
            fuelBottoms.append(fuelHeightInCm)
        return lowestFuelHeightInCm

    def processLoading(self, cs, dbLoad: bool = False):
        """
        After nuclide densities are loaded, this goes through and prepares the reactor.

        Notes
        -----
        This does a few operations :
         * It process boosters,
         * sets axial snap lists,
         * checks the geometry,
         * sets up location tables (tracks where the initial feeds were (for moderation or something)

        See Also
        --------
        updateAxialMesh : Perturbs the axial mesh originally set up here.
        """
        self.setOptionsFromCs(cs)
        runLog.header("=========== Initializing Mesh, Assembly Zones, and Nuclide Categories =========== ")

        for b in self.iterBlocks():
            if b.p.molesHmBOL > 0.0:
                break
        else:
            # Good easter egg, but sometimes a user will want to use the framework do
            # only decay analyses and heavy metals are not required.
            runLog.warning(
                "The system has no heavy metal and therefore is not a nuclear reactor.\n"
                "Please make sure that this is intended and not a input error."
            )

        if dbLoad:
            # reactor.blueprints.assemblies need to be populated this normally happens during
            # blueprint constructAssem. But for DB load, this is not called so it must be here.
            self.parent.blueprints._prepConstruction(cs)
        else:
            # set reactor level meshing params
            nonUniformAssems = [Flags.fromStringIgnoreErrors(t) for t in cs[CONF_NON_UNIFORM_ASSEM_FLAGS]]
            # Some assemblies, like control assemblies, have a non-conforming mesh and should not be
            # included in self.p.referenceBlockAxialMesh and self.p.axialMesh
            uniformAssems = [a for a in self.getAssemblies() if not any(a.hasFlags(f) for f in nonUniformAssems)]
            self.p.referenceBlockAxialMesh = self.findAllAxialMeshPoints(
                assems=uniformAssems,
                applySubMesh=False,
            )
            self.p.axialMesh = self.findAllAxialMeshPoints(
                assems=uniformAssems,
                applySubMesh=True,
            )

        self.getNuclideCategories()

        # Generate list of flags that are to be stationary during assembly shuffling
        stationaryBlockFlags = []

        for stationaryBlockFlagString in cs[CONF_STATIONARY_BLOCK_FLAGS]:
            stationaryBlockFlags.append(Flags.fromString(stationaryBlockFlagString))

        self.stationaryBlockFlagsList = stationaryBlockFlags
        self.setBlockMassParams()
        self.p.maxAssemNum = self.getMaxParam("assemNum")

        getPluginManagerOrFail().hook.onProcessCoreLoading(core=self, cs=cs, dbLoad=dbLoad)

    def buildManualZones(self, cs):
        """
        Build the Zones that are defined in the given Settings, in the
        `zoneDefinitions` or `zonesFile` case setting.

        Parameters
        ----------
        cs : Settings
            The standard ARMI settings object

        Examples
        --------
        Manual zones will be defined in a special string format, e.g.:

        >>> zoneDefinitions:
        >>>     - ring-1: 001-001
        >>>     - ring-2: 002-001, 002-002
        >>>     - ring-3: 003-001, 003-002, 003-003

        Notes
        -----
        This function will just define the Zones it sees in the settings, it does not do any
        validation against a Core object to ensure those manual zones make sense.
        """
        if cs[CONF_ZONE_DEFINITIONS]:
            runLog.info(f"Building Zones by manual definitions in {CONF_ZONE_DEFINITIONS} setting")

            stripper = lambda s: s.strip()
            self.zones = zones.Zones()

            # parse the special input string for zone definitions
            for zoneString in cs[CONF_ZONE_DEFINITIONS]:
                zoneName, zoneLocs = zoneString.split(":")
                zoneLocs = zoneLocs.split(",")
                zone = zones.Zone(zoneName.strip())
                zone.addLocs(map(stripper, zoneLocs))
                self.zones.addZone(zone)

        elif cs[CONF_ZONES_FILE]:
            runLog.info(f"Custom zoning strategy applied from {CONF_ZONES_FILE}.")

            self.zones = Zones()
            with open(cs[CONF_ZONES_FILE]) as stream:
                zonesDict = yaml.safe_load(stream)

            for assemblyLocation, zoneName in zonesDict["customZonesMap"].items():
                # if the the zoneName isn't already a Zones key, then add a new Zone
                if zoneName not in self.zones:
                    self.zones.addZone(Zone(zoneName, [assemblyLocation]))
                # if the zoneName is already a Zones key, then add the location to the existing Zone
                else:
                    self.zones[zoneName].addLoc(assemblyLocation)

            # sort the Zones
            self.zones.sortZones()

        else:
            runLog.warn(f"No zones defined in either {CONF_ZONE_DEFINITIONS} or {CONF_ZONES_FILE} settings")

    def iterBlocks(
        self,
        typeSpec: Optional[flags.TypeSpec] = None,
        exact=False,
        predicate: Callable[[blocks.Block], bool] = None,
    ) -> Iterator[blocks.Block]:
        """Iterate over the blocks in the core.

        Useful for operations that just want to find all the blocks in the core with light
        filtering.

        Parameters
        ----------
        typeSpec: armi.reactor.flags.TypeSpec, optional
            Limit the traversal to blocks that have these flags.
        exact: bool, optional
            Strictness on the usage of ``typeSpec`` used in :meth:`armi.reactor.composites.hasFlags`
        predicate: f(block) -> bool, optional
            Limit the traversal to blocks that pass this predicate. Can be used in addition to
            ``typeSpec`` to perform more advanced filtering.

        Returns
        -------
        iterator[Block]
            Iterator over blocks in the core that meet the conditions provided.

        Examples
        --------
        Iterate over all fuel blocks::

        >>> for b in r.core.iterBlocks(Flags.FUEL):
        ...     pass

        See Also
        --------
        :meth:`getBlocks` has more control over what is included in the returned list
        including looking at the spent fuel pool and assemblies that may not exist now
        but existed at BOL (via :meth:`getAssemblies`). But if you're just interested in
        the blocks in the core now, maybe with a flag attached to that block, this is what
        you should use.

        Notes
        -----
        Assumes your composite tree is structured ``Core`` -> ``Assembly`` -> ``Block``. If
        this is not the case, consider using :meth:`iterChildren`.
        """
        if typeSpec is not None:
            typeChecker = lambda b: b.hasFlags(typeSpec, exact=exact)
        else:
            typeChecker = lambda _: True
        if predicate is not None:
            blockChecker = lambda b: typeChecker(b) and predicate(b)
        else:
            blockChecker = typeChecker
        return self.iterChildren(generationNum=2, predicate=blockChecker)
