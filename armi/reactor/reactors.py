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
Reactor objects represent the highest level in the hierarchy of structures that compose the system
to be modeled. Core objects represent collections of assemblies.

Core is a high-level object in the data model in ARMI. They contain assemblies which in turn contain
more refinement in representing the physical reactor. The reactor is the owner of many of the
plant-wide state variables such as keff, cycle, and node.

"""
from __future__ import print_function
import collections
import copy
import itertools
import math
import re
import os
import tabulate
import time
from typing import Optional

from six import moves
import numpy
from ordered_set import OrderedSet
import matplotlib.pyplot as plt
import matplotlib.text as mpl_text
import matplotlib.collections
import matplotlib.patches

import armi
from armi import nuclearDataIO
from armi import runLog
from armi import settings
from armi.reactor import assemblies
from armi.reactor import assemblyLists
from armi.reactor import composites
from armi.reactor import geometry
from armi.reactor import locations
from armi.reactor import parameters
from armi.reactor import zones
from armi.reactor import reactorParameters
from armi import materials
from armi import utils
from armi.utils import units
from armi.utils.iterables import Sequence
from armi.utils import directoryChangers
from armi.reactor.flags import Flags
from armi.settings.fwSettings.globalSettings import CONF_MATERIAL_NAMESPACE_ORDER


class Reactor(composites.Composite):
    """
    Top level of the composite structure, potentially representing all components in a reactor.

    This class contains the core and any ex-core structures that are to be represented in the ARMI
    model. Historically, the `Reactor` contained only the core. To support better representation of
    ex-core structures, the old `Reactor` functionality was moved to the newer `Core` class, which
    has a `Reactor` parent.
    """

    pDefs = reactorParameters.defineReactorParameters()

    def __init__(self, name, blueprints):
        composites.Composite.__init__(self, "R-{}".format(name))

        self.o = None
        self.spatialGrid = None
        self.spatialLocator = None
        self.p.cycle = 0
        self.p.flags |= Flags.REACTOR
        self.core = None
        self.blueprints = blueprints

    def __getstate__(self):
        r"""applies a settings and parent to the reactor and components. """
        state = composites.Composite.__getstate__(self)
        state["o"] = None
        return state

    def __setstate__(self, state):
        composites.Composite.__setstate__(self, state)

    def __deepcopy__(self, memo):
        memo[id(self)] = newR = self.__class__.__new__(self.__class__)
        newR.__setstate__(copy.deepcopy(self.__getstate__(), memo))
        newR.name = self.name + "-copy"
        return newR

    def __repr__(self):
        return "<{}: {} id:{}>".format(self.__class__.__name__, self.name, id(self))

    def add(self, container):
        composites.Composite.add(self, container)
        cores = self.getChildrenWithFlags(Flags.CORE)
        if cores:
            if len(cores) != 1:
                raise ValueError(
                    "Only 1 core may be specified at this time. Please adjust input. "
                    "Cores found: {}".format(cores)
                )
            self.core = cores[0]


def loadFromCs(cs):
    """
    Load a Reactor based on the input settings.
    """
    from armi.reactor import blueprints

    bp = blueprints.loadFromCs(cs)
    return factory(cs, bp)


def factory(cs, bp, geom: Optional[geometry.SystemLayoutInput] = None):
    """
    Build a reactor from input settings, blueprints and geometry.
    """
    from armi.reactor import blueprints

    runLog.header("=========== Constructing Reactor and Verifying Inputs ===========")
    # just before reactor construction, update the material "registry" with user settings,
    # if it is set. Often it is set by the application.
    if cs[CONF_MATERIAL_NAMESPACE_ORDER]:
        materials.setMaterialNamespaceOrder(cs[CONF_MATERIAL_NAMESPACE_ORDER])
    r = Reactor(cs.caseTitle, bp)

    if cs["geomFile"]:
        blueprints.migrate(bp, cs)

    with directoryChangers.DirectoryChanger(cs.inputDirectory, dumpOnException=False):
        # always construct the core first (for assembly serial number purposes)
        core = bp.systemDesigns["core"]
        core.construct(cs, bp, r, geom=geom)
        for structure in bp.systemDesigns:
            if structure.name.lower() != "core":
                structure.construct(cs, bp, r)

    runLog.debug("Reactor: {}".format(r))
    return r


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

    cs : CaseSettings object
        Global settings for the case

    """

    pDefs = reactorParameters.defineCoreParameters()

    def __init__(self, name):
        """
        Initialize the reactor object.

        Parameters
        ----------
        name : str
            Name of the object. Flags will inherit from this.
        geom : SystemLayoutInput object
            Contains face-map
        cs : CaseSettings object, optional
            the calculation settings dictionary
        """
        composites.Composite.__init__(self, name)
        self.p.flags = Flags.fromStringIgnoreErrors(name)
        self.assembliesByName = {}
        self.circularRingList = {}
        self.blocksByName = {}  # lookup tables
        self.locationIndexLookup = {}
        self.numRings = 0
        self.spatialGrid = None
        self.xsIndex = {}
        self.p.numMoves = 0
        self.p.beta = 0.0
        self.p.betaComponents = [0.0] * 6
        self.p.betaDecayConstants = [0.0] * 6

        # build a spent fuel pool for this reactor
        runLog.debug("Building spent fuel pools")
        self.sfp = assemblyLists.SpentFuelPool("Spent Fuel Pool", self)
        self.cfp = assemblyLists.ChargedFuelPool("Charged Fuel Pool", self)
        self._lib = None  # placeholder for ISOTXS object
        self.locParams = {}  # location-based parameters
        # overridden in case.py to include pre-reactor time.
        self.timeOfStart = time.time()
        self.zones = None
        # initialize the list that holds all shuffles
        self.moveList = {}
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

    def setOptionsFromCs(self, cs):
        # these are really "user modifiable modeling constants"
        self.p.jumpRing = cs["jumpRingNum"]
        self._freshFeedType = cs["freshFeedType"]
        self._trackAssems = cs["trackAssems"]
        self._circularRingMode = cs["circularRingMode"]
        self._circularRingPitch = cs["circularRingPitch"]
        self._automaticVariableMesh = cs["automaticVariableMesh"]
        self._minMeshSizeRatio = cs["minMeshSizeRatio"]

    def __getstate__(self):
        """Applies a settings and parent to the core and components. """
        state = composites.Composite.__getstate__(self)
        return state

    def __setstate__(self, state):
        composites.Composite.__setstate__(self, state)
        self.cfp.r = self
        self.sfp.r = self
        self.regenAssemblyLists()

    def __deepcopy__(self, memo):
        memo[id(self)] = newC = self.__class__.__new__(self.__class__)
        newC.__setstate__(copy.deepcopy(self.__getstate__(), memo))
        newC.name = self.name + "-copy"
        return newC

    def __repr__(self):
        return "<{}: {} id:{}>".format(self.__class__.__name__, self.name, id(self))

    def __iter__(self):
        """
        Override the base Composite __iter__ to produce stable sort order.

        See Also
        --------
        getAssemblies()
        """
        return iter(sorted(self._children))

    @property
    def r(self):
        if isinstance(self.parent, Reactor):
            return self.parent

        return None

    @property
    def symmetry(self):
        return self.spatialGrid.symmetry

    @symmetry.setter
    def symmetry(self, val):
        self.spatialGrid.symmetry = val
        self.clearCache()

    @property
    def geomType(self):
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
        return geometry.SYMMETRY_FACTORS[self.symmetry]

    @property
    def lib(self):
        """"Get the microscopic cross section library."""
        if self._lib is None:
            runLog.info("Loading microscopic cross section library ISOTXS")
            self._lib = nuclearDataIO.ISOTXS()
        return self._lib

    @lib.setter
    def lib(self, value):
        """"Set the microscopic cross section library."""
        self._lib = value

    @property
    def isFullCore(self):
        """Return True if reactor is full core, otherwise False."""
        # Avoid using `not core.isFullCore` to check if third core geometry
        # use `core.symmetry == geometry.THIRD_CORE + geometry.PERIODIC`
        return self.symmetry == geometry.FULL_CORE

    @property
    def refAssem(self):
        return self.getFirstAssembly(Flags.FUEL) or self.getFirstAssembly()

    def summarizeReactorStats(self):
        """Writes a summary of the reactor to check the mass and volume of all of the blocks."""
        totalMass = 0.0
        fissileMass = 0.0
        heavyMetalMass = 0.0
        totalVolume = 0.0
        numBlocks = len(self.getBlocks())
        for block in self.getBlocks():
            totalMass += block.getMass()
            fissileMass += block.getFissileMass()
            heavyMetalMass += block.getHMMass()
            totalVolume += block.getVolume()
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
                tablefmt="armi",
            )
        )

    def getScalarEvolution(self, key):
        return self.scalarVals[key]

    def locateAllAssemblies(self):
        """
        Store the current location of all assemblies.

        This is required for shuffle printouts, repeat shuffling, and
        MCNP shuffling.
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

        Originally, this held onto all assemblies in the spend fuel pool. However, having this sitting in memory
        becomes constraining for large problems. It is more memory-efficient to only save the assemblies
        that are required for detailed history tracking. In fact, there's no need to save the assembly object at all,
        just have the history interface save the relevant parameters. This is an important cleanup.

        See Also
        --------
        add : adds an assembly
        """
        paramDefs = set(parameters.ALL_DEFINITIONS)
        paramDefs.difference_update(set(parameters.forType(Core)))
        paramDefs.difference_update(set(parameters.forType(Reactor)))
        for paramDef in paramDefs:
            if paramDef.assigned & parameters.SINCE_ANYTHING:
                paramDef.assigned = parameters.SINCE_ANYTHING
        if discharge:
            runLog.debug("Removing {0} from {1}".format(a1, self))
        else:
            runLog.debug("Purging  {0} from {1}".format(a1, self))

        self.childrenByLocator.pop(a1.spatialLocator)
        a1.p.dischargeTime = self.r.p.time
        self.remove(a1)

        if discharge and self._trackAssems:
            self.sfp.add(a1)
        else:
            self._removeListFromAuxiliaries(a1)

    def removeAssembliesInRing(self, ringNum):
        """
        Removes all of the assemblies in a given ring
        """
        for a in self.getAssembliesInRing(ringNum):
            self.removeAssembly(a)
        self.processLoading(settings.getMasterCs())

    def _removeListFromAuxiliaries(self, assembly):
        """
        Remove an assembly from all auxiliary reference tables and lists

        Otherwise it will get added back into assembliesByName, etc.

        History will fail if it tries to summarize an assembly that has been purged.
        """
        del self.assembliesByName[assembly.getName()]
        for b in assembly:
            try:
                del self.blocksByName[b.getName()]
            except KeyError:
                runLog.warning(
                    "Cannot delete block {0}. It is not in the Core.blocksByName structure"
                    "".format(b),
                    single=True,
                    label="cannot dereference: lost block",
                )

    def removeAllAssemblies(self, discharge=True):
        """
        Clears the core.

        Notes
        -----
        must clear auxiliary bookkeeping lists as well or else a regeneration step will auto-add 
        assemblies back in.
        """
        assems = set(self)
        for a in assems:
            self.removeAssembly(a, discharge)
        self.cfp.removeAll()
        self.sfp.removeAll()
        self.blocksByName = {}
        self.assembliesByName = {}

    def add(self, a, spatialLocator=None):
        """
        Adds an assembly to the reactor.

        An object must be added before it is placed in a particular cell
        in the reactor's spatialGrid. When an object is added to a reactor
        it get placed in a generic location at the center of the reactor unless
        a spatialLocator is passed in as well.

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
            raise RuntimeError(
                "Cannot add {} because location {} is already filled by {}."
                "".format(
                    aName, a.spatialLocator, self.childrenByLocator[a.spatialLocator]
                )
            )

        if spatialLocator is not None:
            # transfer spatialLocator to reactor one
            spatialLocator = self.spatialGrid[tuple(spatialLocator.indices)]
            a.moveTo(spatialLocator)

        self.childrenByLocator[spatialLocator] = a
        # build a lookup table for history tracking.
        if aName in self.assembliesByName and self.assembliesByName[aName] != a:
            # try to keep assem numbering correct
            runLog.error(
                "The assembly {1} in the reactor already has the name {0}.\nCannot add {2}. "
                "Current assemNum is {3}"
                "".format(
                    aName, self.assembliesByName[aName], a, assemblies.getAssemNum()
                )
            )
            raise RuntimeError("Core already contains an assembly with the same name.")
        self.assembliesByName[aName] = a
        for b in a:
            self.blocksByName[b.getName()] = b

        if self.geomType == geometry.HEX:
            ring, _loc = self.spatialGrid.getRingPos(
                a.spatialLocator.getCompleteIndices()
            )
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

        This uses the reactor's cycle parameter and the assemblies' chargeCycle
        parameters.
        """

        for a in self:
            if a.p.chargeCycle == self.r.p.cycle:
                yield a

    def getNumRings(self, indexBased=False):
        """
        Returns the number of rings in this reactor. Based on location so indexing will start at 1.

        WARNING: If you loop through range(maxRing) then ring+1 is the one you want!!

        Parameters
        ----------
        indexBased : bool, optional
            If true, will force location-index interpretation, even if "circular shuffling" is enabled.

        When circular ring shuffling is activated, this changes interpretation.
        Developers plan on making this another method for the secondary interpretation.

        """
        if self.circularRingList and not indexBased:
            return max(self.circularRingList)
        else:
            return self.getNumHexRings()

    def getNumHexRings(self):
        """
        Returns the number of hex rings in this reactor. Based on location so indexing will start at 1.
        """
        maxRing = 0
        for a in self.getAssemblies():
            ring, _pos = self.spatialGrid.getRingPos(a.spatialLocator)
            maxRing = max(maxRing, ring)
        return maxRing

    def getNumAssembliesWithAllRingsFilledOut(self, nRings):
        """
        Returns nAssmWithBlanks (see description immediately below).

        Parameters
        ----------
        nRings : int
            The number of hex assembly rings in this core, including
            partially-complete (non-full) rings.

        Returns
        -------
        nAssmWithBlanks: int
            The number of assemblies that WOULD exist in this core if
            all outer assembly hex rings were "filled out".

        """
        if self.powerMultiplier == 1:
            return 3 * nRings * (nRings - 1) + 1
        else:
            return nRings * (nRings - 1) + (nRings + 1) // 2

    def getNumEnergyGroups(self):
        """"
        Return the number of energy groups used in the problem

        See Also
        --------
        armi.nuclearDataIO.ISOTXS.read1D : reads the number of energy groups off the ISOTXS library.
        """
        return self.lib.numGroups

    # NOTE: this method is never used
    def countAssemblies(self, typeList, ring=None, fullCore=False):
        """
        Counts the number of assemblies of type in ring (or in full reactor)

        Parameters
        ----------
        typeList : iterable, optional
            Restruct counts to this assembly type.

        rings : int
            The reactor ring to find assemblies in

        fullCore : bool, optional
            If True, will consider the core symmetry. Default: False
        """
        assems = (a for a in self if a.hasFlags(typeList, exact=True))

        if ring is not None:
            assems = (a for a in assems if a.spatialLocator.getRingPos()[0] == ring)

        if not fullCore:
            return sum(1 for _a in assems)

        pmult = self.powerMultiplier  # value is loop-independent

        rings = (a.spatialLocator.getRingPos()[0] for a in assems)

        return sum(1 if r == 1 else pmult for r in rings)

    def countBlocksWithFlags(self, blockTypeSpec, assemTypeSpec=None):
        """
        Return the total number of blocks in an assembly in the reactor that
        meets the specified type

        Parameters
        ----------
        blockTypeSpec : Flags or list of Flags
            The types of blocks to be counted in a single assembly

        assemTypeSpec : Flags or list of Flags
            The types of assemblies that are to be examine for the blockTypes
            of interest.  None is every assembly

        Returns
        -------
        maxBlocks : int
            The maximum number of blocks of the specified types in a single
            assembly in the entire core
        """
        assems = self.getAssemblies(typeSpec=assemTypeSpec)
        try:
            return max(sum(b.hasFlags(blockTypeSpec) for b in a) for a in assems)
        except ValueError:
            ## In case assems is empty
            return 0

    def countFuelAxialBlocks(self):
        r"""
        return the maximum number of fuel type blocks in any assembly in
        the reactor

        See Also
        --------
        getFirstFuelBlockAxialNode
        """
        fuelblocks = (
            a.getBlocks(Flags.FUEL) for a in self.getAssemblies(includeBolAssems=True)
        )
        try:
            return max(len(fuel) for fuel in fuelblocks)
        except ValueError:  ## thrown when iterator is empty
            return 0

    def getFirstFuelBlockAxialNode(self):
        """
        Determine the offset of the fuel from the grid plate in the assembly
        with the lowest fuel block.

        This assembly will dictate at what block level the SASSYS reactivity
        coefficients will start to be generated
        """
        try:
            return min(
                i
                for a in self.getAssemblies(includeBolAssems=True)
                for (i, b) in enumerate(a)
                if b.hasFlags(Flags.FUEL)
            )
        except ValueError:
            ## ValueError is thrown if min is called on an empty sequence.
            ## Since this is expected to be a rare case, try/except is more
            ## efficient than an if/else condition that checks whether the
            ## iterator is empty (the latter would require generating a list
            ## or tuple, which further adds to the inefficiency). Hence Python's
            ## mantra, "It's easier to ask forgiveness than permission." In fact
            ## it's quicker to ask forgiveness than permission.
            return float("inf")

    def getAssembliesInRing(
        self, ring, typeSpec=None, exactType=False, exclusions=None
    ):
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

        Returns
        -------
        aList : list of assemblies
            A list of assemblies that match the criteria within the ring

        """
        if self._circularRingMode:
            getter = self.getAssembliesInCircularRing
        else:
            getter = self.getAssembliesInSquareOrHexRing

        return getter(
            ring=ring, typeSpec=typeSpec, exactType=exactType, exclusions=exclusions
        )

    def getMaxAssembliesInHexRing(self, ring, fullCore=False):
        """
        Returns the maximum number of assemblies possible for a given Hexagonal ring.

        ring - The ring of interest to calculate the maximum number of assemblies.
        numEdgeAssems - The number of edge assemblies in the reactor model (1/3 core).

        Notes
        -----
        Assumes that odd rings do not have an edge assembly in third core geometry. 
        These should be removed in: self._modifyGeometryAfterLoad during importGeom

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
    ):
        """
        Returns the assemblies in a specified ring.  Definitions of rings can change
        with problem parameters

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

        ## filter based on geomType
        if (
            self.geomType == geometry.CARTESIAN
        ):  # a ring in cartesian is basically a square.
            assems.select(
                lambda a: any(xy == ring for xy in abs(a.spatialLocator.indices[:2]))
            )
        else:
            assems.select(lambda a: (a.spatialLocator.getRingPos()[0] == ring))

        ## filter based on typeSpec
        if typeSpec:
            assems.select(lambda a: a.hasFlags(typeSpec, exact=exactType))

        return list(assems)

    def getAssembliesInCircularRing(
        self, ring, typeSpec=None, exactType=False, exclusions=None
    ):
        """
        Gets an assemblies within a circular range of the center of the core.  This
        function allows for more circular styled assembly shuffling instead of the
        current hex approach.

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

        if self.geomType == geometry.CARTESIAN:
            # a ring in cartesian is basically a square.
            raise RuntimeError(
                "A circular ring in cartesian coordinates has not been defined yet."
            )

        # determine if the circularRingList has been generated
        ## TODO: make circularRingList a property that is generated on request
        if not self.circularRingList:
            self.circularRingList = self.buildCircularRingDictionary(
                self._circularRingPitch
            )

        assems = Sequence(self)

        ## Remove exclusions
        if exclusions:
            exclusions = set(exclusions)
            assems.drop(lambda a: a in exclusions)

        ## get assemblies at locations
        locSet = self.circularRingList[ring]
        assems.select(lambda a: a.getLocation() in locSet)

        if typeSpec:
            assems.select(lambda a: a.hasFlags(typeSpec, exact=exactType))

        return list(assems)

    def buildCircularRingDictionary(self, ringPitch=1.0):
        """
        Builds a dictionary of all circular rings in the core.  This is required information for getAssembliesInCircularRing.

        The purpose of this function is to allow for more circular core shuffling in the hex design.

        Parameters
        ----------
        ringPitch : float, optional
            The relative pitch that should be used to define the spacing between each ring.

        """
        runLog.extra(
            "Building a circular ring dictionary with ring pitch {}".format(ringPitch)
        )
        referenceAssembly = self.getAssemblyWithStringLocation("A1001")
        refLocation = referenceAssembly.getLocationObject()

        circularRingDict = collections.defaultdict(set)

        for a in self:
            loc = a.getLocationObject()
            dist = refLocation.getDistanceOfLocationToPoint(loc, pitch=ringPitch)
            ## To reduce numerical sensitivity, round distance to 6 decimal places
            ## before truncating.
            index = int(round(dist, 6)) or 1  # 1 is the smallest ring.
            circularRingDict[index].add(loc.label)

        return circularRingDict

    def getPowerProductionMassFromFissionProducts(self):
        """
        Determines the power produced by Pu isotopes and Uranium isotopes by examining
        the fission products in the block

        The percentage of energy released adjusted mass produced by each LFP can be used to
        determine the relative power production of each parent isotope.

        Returns
        -------
        resultsEnergyCorrected : list of tuples
            Contains the nuclide name, energy released adjusted mass
        """
        # get the energy in Joules from the ISOTXS
        energyDict = {}
        nuclides = ["U235", "U238", "PU239", "PU240", "PU241"]
        fissionProducts = ["LFP35", "LFP38", "LFP39", "LFP40", "LFP41"]

        # initialize the energy in each nuclide
        totEnergy = 0.0
        for nuc in nuclides:
            n = self.lib.getNuclide(nuc)
            energyDict[nuc] = n.isotxsMetadata["efiss"]
            totEnergy += n.isotxsMetadata["efiss"]

        fissPower = {}
        for b in self.getBlocks(Flags.FUEL):
            for nuc, lfp in zip(nuclides, fissionProducts):
                energy = fissPower.get(nuc, 0.0)
                energy += b.getMass(lfp) * energyDict[nuc]
                fissPower[nuc] = energy

        resultsEnergyCorrected = []
        # scale the energy mass by energy to get the corrected energy mass of each isotope
        for nuc in nuclides:
            resultsEnergyCorrected.append(fissPower[nuc] / totEnergy)
        return zip(nuclides, resultsEnergyCorrected)

    def _getAssembliesByName(self):
        """
        If the assembly name-to-assembly object map is deleted or out of date, then this will 
        regenerate it.
        """
        runLog.extra("Generating assemblies-by-name map.")

        ## NOTE: eliminated unnecessary repeated lookups in self for self.assembliesByName
        self.assembliesByName = assymap = {}
        # don't includeAll b/c detailed ones are not ready yet
        for assem in self.getAssemblies(
            includeBolAssems=True, includeSFP=True, includeCFP=True
        ):
            aName = assem.getName()
            if aName in assymap and assymap[aName] != assem:
                # dangerous situation that can occur in restart runs where the global assemNum isn't updated.
                # !=assem clause added because sometimes an assem is in one of the includeAll lists that is also in the
                # core and that's ok.
                runLog.error(
                    "Two (or more) assemblies in the reactor (and associated lists) have the name {0},\n"
                    "including {1} and {2}.".format(aName, assem, assymap[aName])
                )
                raise RuntimeError("Assembly name collision.")

            assymap[aName] = assem

    def getAssemblyByName(self, name):
        """
        Find the assembly that has this name.

        Parameters
        ----------
        name : str
            the assembly name e.g. 'A0001'

        Returns
        -------
        assembly

        See Also
        --------
        getAssembly : more general version of this method

        """
        return self.assembliesByName[name]

    def getAssemblies(
        self,
        typeSpec=None,
        includeBolAssems=False,
        includeSFP=False,
        includeCFP=False,
        includeAll=False,
        zones=None,
        exact=False,
    ):
        """
        Return a list of all the assemblies in the reactor.

        Assemblies from the Core itself are sorted based on the Assemblies' comparison
        operators (location-based). This is done so that two reactors with physically
        identical properties are more likely to behave similarly when their assemblies
        may have been added in different orders. In the future this will likely be
        replaced by sorting the _children list itself internally, as there is still
        opportunity for inconsistencies.

        Parameters
        ----------
        typeSpec : Flags or iterable of Flags, optional
            List of assembly types that will be returned

        includeBolAssems : bool, optional
            Include the BOL assemblies as well as the ones that are in the core.
            Default: False

        includeSFP : bool, optional
            Include assemblies in the SFP

        includeCFP : bool, optional
            Include Charged fuel pool

        includeAll : bool, optional
            Will include ALL assemblies.

        zones : str or iterable, optional
            Only include assemblies that are in this zone/these zones

        Notes
        -----
        Attempts have been made to make this a generator but there were some Cython
        incompatibilities that we could not get around and so we are sticking with a
        list.

        """
        if includeAll:
            includeBolAssems = includeSFP = includeCFP = True

        assems = []
        if (
            includeBolAssems
            and self.parent is not None
            and self.parent.blueprints is not None
        ):
            assems.extend(self.parent.blueprints.assemblies.values())
        assems.extend(a for a in sorted(self))

        if includeSFP:
            assems.extend(self.sfp.getChildren())
        if includeCFP:
            assems.extend(self.cfp.getChildren())

        if typeSpec:
            assems = [a for a in assems if a.hasFlags(typeSpec, exact=exact)]

        if zones:
            zoneLocs = self.zones.getZoneLocations(zones)
            assems = [a for a in assems if a.getLocation() in zoneLocs]

        return assems

    def getBlockByName(self, name):
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

    def getBlocksByIndices(self, indices):
        """Get blocks in assemblies by block indices."""
        blocks = []
        for i, j, k in indices:
            assem = self.childrenByLocator[self.spatialGrid[i, j, 0]]
            blocks.append(assem[k])
        return blocks

    def _genBlocksByName(self):
        """If self.blocksByName is deleted, then this will regenerate it."""
        self.blocksByName = {
            block.getName(): block for block in self.getBlocks(includeAll=True)
        }

    ## An idea: wrap this in an "if not self.blocksByLocName:"
    ## This will likely fail, but it will help diagnose why property approach
    ## wasn't working correctly
    def genBlocksByLocName(self):
        """
        If self.blocksByLocName is deleted, then this will regenerate it or update it if things change
        """
        self.blocksByLocName = {
            block.getLocation(): block for block in self.getBlocks(includeAll=True)
        }

    def getBlocks(self, bType=None, **kwargs):
        """
        Returns an iterator over all blocks in the reactor in order

        Parameters
        ----------
        bType : list or Flags, optional
            Restrict results to a specific block type such as Flags.FUEL, Flags.SHIELD, etc.

        includeBolAssems : bool, optional
            Include the BOL-Assembly blocks as well. These blocks are created at BOL
            and used to create new assemblies, etc. If true, the blocks in these
            assemblies will be returned as well as the ones in the reactor.

        kwargs : dict
            Any keyword argument from R.getAssemblies()

        Returns
        -------
        blocks : iterator
            all blocks in the reactor (or of type requested)

        See Also
        --------
        getAssemblies : locates the assemblies in the search
        """
        blocks = [b for a in self.getAssemblies(**kwargs) for b in a]
        if bType:
            blocks = [b for b in blocks if b.hasFlags(bType)]
        return blocks

    def getFirstBlock(self, blockType=None, exact=False):
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

    def getFirstAssembly(self, typeSpec=None, exact=False):
        """
        Gets the first assembly in the reactor.

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

        ## Assumes at least one assembly in `self`.
        return next(iter(self))

    def regenAssemblyLists(self):
        """
        If the attribute lists which contain assemblies are deleted (such as by reactors.detachAllAssemblies),
        then this function will call the other functions to regrow them.
        """
        self._getAssembliesByName()
        self._genBlocksByName()
        self._buildLocationIndexLookup()  # for converting indices to locations.
        runLog.important("Regenerating Core Zones")
        self.buildZones(
            settings.getMasterCs()
        )  # TODO: this call is questionable... the cs should correspond to analysis
        self._genChildByLocationLookupTable()

    def getAllXsSuffixes(self):
        """Return all XS suffices (e.g. AA, AB, etc.) in the core."""
        return sorted(set(b.getMicroSuffix() for b in self.getBlocks()))

    def getNuclideCategories(self):
        """
        Categorize nuclides as coolant, fuel and structure.

        Notes
        -----
        This is used to categorize nuclides for Doppler broadening. Control nuclides are treated as structure.

        The categories are defined in the following way:
        1. Add nuclides from coolant components to coolantNuclides
        2. Add nuclides from fuel components to fuelNuclides (this may be incomplete, e.g. at BOL there are no fission
           products)
        3. Add nuclides from all other components to structureNuclides
        4. Since fuelNuclides may be incomplete, add anything else the user wants to model that isn't already listed
           in coolantNuclides or structureNuclides.

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
            for b in self.getBlocks():
                for c in b:
                    if c.getName() == "coolant":
                        coolantNuclides.update(c.getNuclides())
                    elif "fuel" in c.getName():
                        fuelNuclides.update(c.getNuclides())
                    else:
                        structureNuclides.update(c.getNuclides())
            structureNuclides -= coolantNuclides
            structureNuclides -= fuelNuclides
            remainingNuclides = (
                set(self.parent.blueprints.allNuclidesInProblem)
                - structureNuclides
                - coolantNuclides
            )
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
                        utils.createFormattedStrWithDelimiter(
                            self._nuclideCategories["fuel"]
                        ),
                    ),
                    (
                        "Coolant",
                        utils.createFormattedStrWithDelimiter(
                            self._nuclideCategories["coolant"]
                        ),
                    ),
                    (
                        "Structure",
                        utils.createFormattedStrWithDelimiter(
                            self._nuclideCategories["structure"]
                        ),
                    ),
                ],
                headers=["Nuclide Category", "Nuclides"],
                tablefmt="armi",
            )
        )

    def whichBlockIsAtCoords(self, x, y, z):
        """
        Find block closest to a x,y,z tuple.

        Parameters
        ----------
        x, y, z : float
            points in cm

        """
        closestAssem = (float("inf"), [])
        for a in self.getChildren():
            xyDist = a.getLocationObject().getDistanceOfLocationToPoint(
                (x, y), pitch=a.getPitch()
            )
            if xyDist < closestAssem[0]:
                closestAssem = (xyDist, a)

        for b in closestAssem[1]:
            if b.p.zbottom <= z <= b.p.ztop:
                return b

        raise ValueError("No block was found at ({} {} {})".format(x, y, z))

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
            A master lookup table with location string keys and block/assembly values
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
        whichAssemblyIsIn : does the same thing with easier interface but no caching (slower)
        """

        ## Why isn't locContents an attribute of reactor? It could be another
        ## property that is generated on demand
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

    ## Can be cleaned up, but need test case to guard agains breakage
    def getFluxVector(
        self, energyOrder=0, adjoint=False, extSrc=False, volumeIntegrated=True
    ):
        """
        Return the multigroup real or adjoint flux of the entire reactor as a vector

        Order of meshes is based on getBlocks

        Parameters
        ----------
        energyOrder : int, optional
            A value of 0 implies that the flux will have all energy groups for
            the first mesh point, and then all energy groups for the next mesh point, etc.

            A value of 1 implies that the flux will have values for all mesh points
            of the first energy group first, followed by all mesh points for the second energy
            group, etc.

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
        blocks = list(self.getBlocks())
        groups = range(self.lib.numGroups)

        # build in order 0
        for b in blocks:
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
            # swap order.
            newFlux = []
            for g in groups:
                oneGroup = [flux[i] for i in range(g, len(flux), len(groups))]
                newFlux.extend(oneGroup)
            flux = newFlux

        return numpy.array(flux)

    def getAssembliesOfType(self, typeSpec, exactMatch=False):
        """Return a list of assemblies in the core that are of type assemType."""
        return self.getChildrenWithFlags(typeSpec, exactMatch=exactMatch)

    def getAssembly(
        self, assemNum=None, locationString=None, assemblyName=None, *args, **kwargs
    ):
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
        """
        Returns an assembly or none if given a location string like 'B0014'.
        """
        loc = locations.locationFactory(self.geomType)()
        loc.fromLabel(locationString)
        i, j = loc.indices()
        assem = self.childrenByLocator.get(self.spatialGrid[i, j, 0])
        return assem

    def getAssembliesInSector(self, theta1, theta2):
        """
        Locate assemblies in an angular sector.

        0 degrees is due north, angles increase clockwise.
        To comply with design team, north is defined as
        the 120 degree symmetry line in ARMI models.

        Parameters
        ----------
        theta1, theta2 : float
            The angles (in degrees) in which assemblies shall be drawn.

        Returns
        -------
        aList : list
            List of assemblies in this sector
        """
        aList = []
        from armi.reactor.converters import geometryConverters

        converter = geometryConverters.EdgeAssemblyChanger(quiet=True)
        converter.addEdgeAssemblies(self.r.core)
        for a in self:
            loc = a.getLocationObject()
            theta = loc.getAngle(degrees=True)
            phi = theta
            if (
                theta1 <= phi <= theta2
                or abs(theta1 - phi) < 0.001
                or abs(theta2 - phi) < 0.001
            ):
                aList.append(a)
        converter.removeEdgeAssemblies(self.r.core)

        if not aList:
            raise ValueError(
                "There are no assemblies in {} between angles of {} and {}".format(
                    self, theta1, theta2
                )
            )

        return aList

    def getAssemblyPitch(self):
        """
        Find the representative assembly pitch for the whole core.

        This loops over all fuel blocks to find the best pitch.

        Returns
        -------
        avgPitch : float
            The average pitch of fuel assems in cm.

        """
        pitches = numpy.array([b.getPitch() for b in self.getBlocks(Flags.FUEL)])
        avgPitch = pitches.mean()
        if max((avgPitch - pitches.min()), abs(avgPitch - pitches.max())) > 1e-10:
            raise RuntimeError(
                "Not all fuel blocks have the same pitch (in cm). Min: {}, Mean: {}, Max: {}".format(
                    pitches.min(), avgPitch, pitches.max()
                )
            )
        return avgPitch

    def whichAssemblyIsIn(self, i1=None, i2=None, typeFlags=None, excludeFlags=None):
        """
        Find the assembly in a particular location.

        This method is no longer preferred, it's better to use the grid system::

        assemLoc = reactor.core.spatialGrid[1,2,0]
        assem = reactor.core.childrenByLocator[assemLoc]

        Parameters
        ----------
        i1 : int, optional
            The first index of the location (ring number)
        i2 : int, optional
            The second index of the location (postion in ring). If None and i1,
            all assemblies in ring i1 will be returned
        typeFlags : Flags or list of Flags, optional
            Only assemblies of this type will be returned.
        excludeFlags : Flags or list of Flags, optional
            Assembly types that will be excluded

        Returns
        -------
        a : an assembly in the location
        -OR-
        aList: a list of assemblies.

        See Also
        --------
        getLocationContents : does the same thing, but can allow caching

        """
        assems = Sequence(self)

        if i2 is not None:
            pred = lambda a: a.spatialLocator.getRingPos() == (i1, i2)
            return next(assems.select(pred), None)

        ## Filter on location
        assems.select(lambda a: a.spatialLocator.getRingPos()[0] == i1)

        if typeFlags:
            ## Filter on type
            assems.select(lambda a: a.hasFlags(typeFlags))

        if excludeFlags:
            ## Exclude types
            assems.drop(lambda a: a.hasFlags(excludeFlags))

        return list(assems)

    def findNeighbors(
        self, a, showBlanks=True, duplicateAssembliesOnReflectiveBoundary=False
    ):
        """
        Find assemblies that are next this assembly.

        Return a list of neighboring assemblies from the 30 degree point (point 1) then counterclockwise around.

        Parameters
        ----------
        a : Assembly object
            The assembly to find neighbors of.

        showBlanks : Boolean, optional
            If True, the returned array of 6 neighbors will return "None" for neighbors that do not explicitly
                exist in the 1/3 core model (including many that WOULD exist in a full core model).
            If False, the returned array will not include the "None" neighbors. If one or more neighbors does
                not explicitly exist in the 1/3 core model, the returned array will have a length of less than 6.

        duplicateAssembliesOnReflectiveBoundary : Boolean, optional
            If True, findNeighbors duplicates neighbor assemblies into their "symmetric identicals" so that
                even assemblies that border symmetry lines will have 6 neighbors. The only assemblies that
                will have fewer than 6 neighbors are those that border the outer core boundary (usually vacuum).
            If False, findNeighbors returns None for assemblies that do not exist in a 1/3 core model
                (but WOULD exist in a full core model).
            For example, applying findNeighbors for the central assembly (ring, pos) = (1, 1) in 1/3 core symmetry
                (with duplicateAssembliesOnReflectiveBoundary = True) would return a list of 6 assemblies, but
                those 6 would really only be assemblies (2, 1) and (2, 2) repeated 3 times each.
            Note that the value of duplicateAssembliesOnReflectiveBoundary only really if showBlanks = True.
            This will have no effect if the model is full core since asymmetric models could find many
            duplicates in the other thirds


        Notes
        -----
        This only works for 1/3 or full core symmetry.

        This uses the 'mcnp' index map (MCNP GEODST hex coordinates)
        instead of the standard (ring, pos) map. because neighbors have consistent indices this way.
        We then convert over to (ring, pos) using the lookup table that a reactor has.


        Returns
        -------
        neighbors : list of assembly objects
            This is a list of "nearest neighbors" to assembly a.
            If showBlanks = False, it will return fewer than 6 neighbors if not all 6 neighbors explicitly exist in the core model.
            If showBlanks = True and duplicateAssembliesOnReflectiveBoundary = False, it will have a "None" for assemblies
                that do not exist in the 1/3 model.
            If showBlanks = True and duplicateAssembliesOnReflectiveBoundary = True, it will return the existing "symmetric identical"
                assembly of a non-existing assembly. It will only return "None" for an assembly when that assembly is non-existing AND
                has no existing "symmetric identical".


        See Also
        --------
        reactors.whichAssemblyIsIn
        locations.getSymmetricIdenticalsThird
        """
        neighborIndices = self.spatialGrid.getNeighboringCellIndices(
            *a.spatialLocator.getCompleteIndices()
        )

        ## TODO: where possible, move logic out of loops
        neighbors = []
        for iN, jN, kN in neighborIndices:
            neighborLoc = self.spatialGrid[iN, jN, kN]
            neighbor = self.childrenByLocator.get(neighborLoc)
            if neighbor is not None:
                neighbors.append(neighbor)
            elif showBlanks:
                if (
                    self.symmetry == geometry.THIRD_CORE + geometry.PERIODIC
                    and duplicateAssembliesOnReflectiveBoundary
                ):
                    symmetricAssem = self._getReflectiveDuplicateAssembly(neighborLoc)
                    neighbors.append(symmetricAssem)
                else:
                    neighbors.append(None)

        return neighbors

    def _getReflectiveDuplicateAssembly(self, neighborLoc):
        """
        Return duplicate assemblies accross symmetry line.

        Notes
        -----
        If an existing symmetric identical has been found, return it.
        If an existing symmetric identical has NOT been found, return a None (it's empty).
        """
        duplicates = []
        otherTwoLocations = self.spatialGrid.getSymmetricIdenticalsThird(neighborLoc)
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
        ## NOTE: moveList is actually a moveDict (misnomer)
        if self.moveList.get(cycle) is None:
            self.moveList[cycle] = []
        if data in self.moveList[cycle]:
            # remove the old version and throw the new on at the end.
            self.moveList[cycle].remove(data)
        self.moveList[cycle].append(data)

    def createFreshFeed(self):
        """
        Creates a new feed assembly.

        See Also
        --------
        createAssemblyOfType: creates an assembly

        Notes
        -----
        createFreshFeed and createAssemblyOfType and this
        all need to be merged together somehow.

        """
        return self.createAssemblyOfType(assemType=self._freshFeedType)

    def createAssemblyOfType(self, assemType=None, enrichList=None, cs=None):
        """
        Create an assembly of a specific type and apply enrichments if they are specified

        Parameters
        ----------
        assemType : str
            The assembly type to create
        enrichList : list
            weight percent enrichments of each block

        Returns
        -------
        a : Assembly
            A new assembly

        See Also
        --------
        armi.fuelHandler.doRepeatShuffle : uses this to repeat shuffling

        """
        a = self.parent.blueprints.constructAssem(
            self.geomType, cs or settings.getMasterCs(), name=assemType
        )

        # check to see if a default bol assembly is being used or we are adding more information
        if enrichList:
            # got an enrichment list that should be the same height as the fuel blocks
            if isinstance(enrichList, float):
                # make endlessly iterable if float was passed in
                enrichList = itertools.cycle([enrichList])
            elif len(a) != len(enrichList):
                raise RuntimeError(
                    "{0} and enrichment list do not have the same number of blocks. Check repeat shuffles file".format(
                        a
                    )
                )

            for b, enrich in zip(a, enrichList):
                if enrich == 0.0:
                    # don't change blocks when enrich specified as 0
                    continue
                if abs(b.getUraniumMassEnrich() - enrich) > 1e-10:
                    # only adjust block enrichment if it's different.
                    # WARNING: If this is not fresh fuel, this messes up the number of moles of HM at BOL and
                    # therefore breaks the burnup metric.
                    b.adjustUEnrich(enrich)

        # see if there are tracked assemblies and add this to the list if so
        if self._trackAssems:
            self.cfp.add(a)

        self.p.numAssembliesFabricated += int(
            self.powerMultiplier
        )  # in 1/3 symmetry you're creating 3 assems.
        return a

    def _createFaceMapLegend(self, legendMap, cmap, norm):
        """Make special assembly-legend for the assembly face map plot with assembly counts."""

        class AssemblyLegend(object):
            """
            Custom Legend artist handler.

            Matplotlib allows you to define a class that implements ``legend_artist`` to give you
            full control over how the legend keys and labels are drawn. This is done here to get
            Hexagons with Letters in them on the legend, which is not a built-in legend option.

            See: http://matplotlib.org/users/legend_guide.html#implementing-a-custom-legend-handler

            """

            def legend_artist(self, legend, orig_handle, fontsize, handlebox):
                letter, index = orig_handle
                x0, y0 = handlebox.xdescent, handlebox.ydescent
                width, height = handlebox.width, handlebox.height
                x = x0 + width / 2.0
                y = y0 + height / 2.0
                normVal = norm(index)
                colorRgb = cmap(normVal)
                patch = matplotlib.patches.RegularPolygon(
                    (x, y),
                    6,
                    height,
                    orientation=math.pi / 2.0,
                    facecolor=colorRgb,
                    transform=handlebox.get_transform(),
                )
                handlebox.add_artist(patch)
                txt = mpl_text.Text(
                    x=x, y=y, text=letter, ha="center", va="center", size=7
                )
                handlebox.add_artist(txt)
                return (patch, txt)

        ax = plt.gca()
        keys = []
        labels = []

        for value, label, description in legendMap:
            keys.append((label, value))
            labels.append(description)

        legend = ax.legend(
            keys,
            labels,
            handler_map={tuple: AssemblyLegend()},
            loc="center left",
            bbox_to_anchor=(1.0, 0.5),
            frameon=False,
            prop={"size": 9},
        )
        return legend

    def plotFaceMap(
        self,
        param="pdens",
        vals="peak",
        data=None,
        fName=None,
        bare=False,
        cmapName="jet",
        labels=(),
        labelFmt="{0:.3f}",
        legendMap=None,
        fontSize=None,
        extraXSpace=200,
        minScale=None,
        maxScale=None,
        axisEqual=False,
        makeColorBar=False,
        cBarLabel="",
        title="",
        shuffleArrows=False,
        titleSize=25,
    ):
        """
        Plot a face map of the core.

        Parameters
        ----------
        param : str, optional
            The block-parameter to plot. Default: pdens

        vals : ['peak', 'average', 'sum'], optional
            the type of vals to produce. Will find peak, average, or sum of block values
            in an assembly. Default: peak

        data : list(numeric)
            rather than using param and vals, use the data supplied as is. It must be in the same order as iter(r).

        fName : str, optional
            File name to create. If none, will show on screen.

        bare : bool, optional
            If True, will skip axis labels, etc.

        cmapName : str
            The name of the matplotlib colormap to use. Default: jet
            Other possibilities: http://matplotlib.org/examples/pylab_examples/show_colormaps.html

        labels : iterable(str), optional
            Data labels corresponding to data values.

        labelFmt : str, optional
            A format string that determines how the data is printed if ``labels`` is not provided.

        fontSize : int, optional
            Font size in points

        extraXSpace : int, optional
            The extra space provided for the legend, if one exists.

        minScale : float, optional
            The minimum value for the low color on your colormap (to set scale yourself)
            Default: autoscale

        maxScale : float, optional
            The maximum value for the high color on your colormap (to set scale yourself)
            Default: autoscale

        axisEqual : Boolean, optional
            If True, horizontal and vertical axes are scaled equally such that a circle
                appears as a circle rather than an ellipse.
            If False, this scaling constraint is not imposed.

        makeColorBar : Boolean, optional
            If True, a vertical color bar is added on the right-hand side of the plot.
            If False, no color bar is added.

        cBarLabel : String, optional
            If True, this string is the color bar quantity label.
            If False, the color bar will have no label.
            When makeColorBar=False, cBarLabel affects nothing.

        title : String, optional
            If True, the string is added as the plot title.
            If False, no plot title is added.

        shuffleArrows : bool, optional
            Adds arrows indicating fuel shuffling maneuvers


        Examples
        --------
        Plotting a BOL assembly type facemap with a legend:
        >>> r.core.plotFaceMap(param='typeNumAssem', cmapName='RdYlBu')

        """
        plt.figure(figsize=(15, 15), dpi=300)
        ax = plt.gca()

        plt.title(title, size=titleSize)

        patches = []
        colors = []

        assemLetters = self.getAssemTypeLetters()

        hexPitch = self.getFirstBlock(
            Flags.FUEL
        ).getPitch()  # use single hex for all assemblies.
        maxX = 0.0
        maxY = 0.0

        if data is None:
            data = []
            for a in self:
                if vals == "peak":
                    data.append(a.getMaxParam(param))
                elif vals == "average":
                    data.append(a.calcAvgParam(param))
                elif vals == "sum":
                    data.append(a.calcTotalParam(param))
                else:
                    raise ValueError(
                        "{0} is an invalid entry for `vals` in plotFaceMap. Use peak, average, or sum.".format(
                            vals
                        )
                    )

        for a, val, label in moves.zip_longest(self, data, labels):
            sideLength = hexPitch / math.sqrt(3)
            x, y = a.getLocationObject().coords(hexPitch)
            assemPatch = matplotlib.patches.RegularPolygon(
                (x, y), 6, sideLength, orientation=math.pi / 2.0
            )
            patches.append(assemPatch)
            colors.append(val)

            if label is None and labelFmt is not None:
                labelText = labelFmt.format(val)
                plt.text(
                    x,
                    y,
                    labelText,
                    zorder=1,
                    ha="center",
                    va="center",
                    fontsize=fontSize,
                )

            elif label is not None:
                plt.text(
                    x, y, label, zorder=1, ha="center", va="center", fontsize=fontSize
                )

            if x > maxX:
                maxX = x
            if y > maxY:
                maxY = y

        cmap = matplotlib.cm.get_cmap(cmapName)

        collection = matplotlib.collections.PatchCollection(
            patches, cmap=cmap, alpha=1.0
        )

        if makeColorBar:  # allow a color bar option
            collection2 = matplotlib.collections.PatchCollection(
                patches, cmap=cmapName, alpha=1.0
            )
            collection2.set_array(numpy.array(colors))

            if not "radial" in cBarLabel:
                colbar = plt.colorbar(collection2)
            else:
                colbar = plt.colorbar(
                    collection2, ticks=[x + 1 for x in range(max(colors))]
                )

            colbar.set_label(cBarLabel, size=20)
            colbar.ax.tick_params(labelsize=16)

        collection.set_array(numpy.array(colors))
        if minScale or maxScale:
            collection.set_clim([minScale, maxScale])
        ax.add_collection(collection)
        collection.norm.autoscale(numpy.array(colors))

        if legendMap is not None:
            legend = self._createFaceMapLegend(legendMap, cmap, collection.norm)
        else:
            legend = None

        if axisEqual:  # don't "squish" hexes vertically or horizontally
            ax.set_aspect("equal", "datalim")

        ax.autoscale_view(tight=True)

        if shuffleArrows:
            # make it 2-D, for now...
            for (sourceCoords, destinationCoords) in shuffleArrows:
                ax.annotate(
                    "",
                    xy=destinationCoords[:2],
                    xytext=sourceCoords[:2],
                    arrowprops={"arrowstyle": "->", "color": "white"},
                )
        if bare:
            ax.set_xticks([])
            ax.set_yticks([])
            ax.spines["right"].set_visible(False)
            ax.spines["top"].set_visible(False)
            ax.spines["left"].set_visible(False)
            ax.spines["bottom"].set_visible(False)

        else:
            plt.xlabel("x (cm)")
            plt.ylabel("y (cm)")

        if fName:
            try:
                if legend:
                    # expand so the legend fits if necessary
                    plt.savefig(
                        fName,
                        bbox_extra_artists=(legend,),
                        bbox_inches="tight",
                        dpi=150,
                    )
                else:
                    plt.savefig(fName, dpi=150)
            except IOError:
                runLog.warning(
                    "Cannot update facemap at {0}: IOError. Is the file open?"
                    "".format(fName)
                )
        else:
            plt.show()

        plt.close()
        return fName

    def plotAssemblyTypes(
        self, assems=None, plotNumber=1, maxAssems=None, showBlockAxMesh=True
    ):
        """
        Generate a plot showing the axial block and enrichment distributions of each assembly type in the core.

        Parameters
        ----------
        assems: list
            list of assembly objects to be plotted.

        plotNumber: integer
            number of uniquely identify the assembly plot from others and to prevent plots from being overwritten.

        maxAssems: integer
            maximum number of assemblies to plot in the assems list.

        showBlockAxMesh: bool
            if true, the axial mesh information will be displayed on the right side of the assembly plot.
        """

        if assems is None:
            assems = self.parent.blueprints.assemblies.values()
        if not isinstance(assems, (list, set, tuple)):
            assems = [assems]
        if not isinstance(plotNumber, int):
            raise TypeError("Plot number should be an integer")
        if not isinstance(maxAssems, int):
            raise TypeError("Maximum assemblies should be an integer")

        numAssems = len(assems)
        if maxAssems is None:
            maxAssems = numAssems

        # Set assembly/block size constants
        yBlockHeights = []
        yBlockAxMesh = OrderedSet()
        assemWidth = 5.0
        assemSeparation = 0.3
        xAssemLoc = 0.5
        xAssemEndLoc = numAssems * (assemWidth + assemSeparation) + assemSeparation

        # Setup figure
        fig, ax = plt.subplots(figsize=(15, 15), dpi=300)
        for index, assem in enumerate(assems):
            isLastAssem = True if index == (numAssems - 1) else False
            (xBlockLoc, yBlockHeights, yBlockAxMesh) = self._plotBlocksInAssembly(
                ax,
                assem,
                isLastAssem,
                yBlockHeights,
                yBlockAxMesh,
                xAssemLoc,
                xAssemEndLoc,
                showBlockAxMesh,
            )
            xAxisLabel = re.sub(" ", "\n", assem.getType().upper())
            ax.text(
                xBlockLoc + assemWidth / 2.0,
                -5,
                xAxisLabel,
                fontsize=13,
                ha="center",
                va="top",
            )
            xAssemLoc += assemWidth + assemSeparation

        # Set up plot layout
        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.yaxis.set_ticks_position("left")
        yBlockHeights.insert(0, 0.0)
        yBlockHeights.sort()
        yBlockHeightDiffs = numpy.diff(
            yBlockHeights
        )  # Compute differential heights between each block
        ax.set_yticks([0.0] + list(set(numpy.cumsum(yBlockHeightDiffs))))
        ax.xaxis.set_visible(False)

        ax.set_title("Assembly Designs for {}".format(self.name), y=1.03)
        ax.set_ylabel("Thermally Expanded Axial Heights (cm)".upper(), labelpad=20)
        ax.set_xlim([0.0, 0.5 + maxAssems * (assemWidth + assemSeparation)])

        # Plot and save figure
        ax.plot()
        figName = self.name + "AssemblyTypes{}.png".format(plotNumber)
        runLog.debug("Writing assem layout {} in {}".format(figName, os.getcwd()))
        fig.savefig(figName)
        plt.close(fig)
        return figName

    def _plotBlocksInAssembly(
        self,
        axis,
        assem,
        isLastAssem,
        yBlockHeights,
        yBlockAxMesh,
        xAssemLoc,
        xAssemEndLoc,
        showBlockAxMesh,
    ):
        import matplotlib.patches as mpatches

        # Set dictionary of pre-defined block types and colors for the plot
        lightsage = "xkcd:light sage"
        blockTypeColorMap = collections.OrderedDict(
            {
                "fuel": "tomato",
                "shield": "cadetblue",
                "reflector": "darkcyan",
                "aclp": "lightslategrey",
                "plenum": "white",
                "duct": "plum",
                "control": lightsage,
                "handling socket": "lightgrey",
                "grid plate": "lightgrey",
                "inlet nozzle": "lightgrey",
            }
        )

        # Initialize block positions
        blockWidth = 5.0
        yBlockLoc = 0
        xBlockLoc = xAssemLoc
        xTextLoc = xBlockLoc + blockWidth / 20.0
        for b in assem:
            blockHeight = b.getHeight()
            blockXsId = b.p.xsType
            yBlockCenterLoc = yBlockLoc + blockHeight / 2.5

            # Get the basic text label for the block
            try:
                blockType = [
                    bType
                    for bType in blockTypeColorMap.keys()
                    if b.hasFlags(Flags.fromString(bType))
                ][0]
                color = blockTypeColorMap[blockType]
            except IndexError:
                blockType = b.getType()
                color = "grey"

            # Get the detailed text label for the block
            dLabel = ""
            if b.hasFlags(Flags.FUEL):
                dLabel = " {:0.2f}%".format(b.getFissileMassEnrich() * 100)
            elif b.hasFlags(Flags.CONTROL):
                blockType = "ctrl"
                dLabel = " {:0.2f}%".format(b.getBoronMassEnrich() * 100)
            dLabel += " ({})".format(blockXsId)

            # Set up block rectangle
            blockPatch = mpatches.Rectangle(
                (xBlockLoc, yBlockLoc),
                blockWidth,
                blockHeight,
                facecolor=color,
                alpha=0.7,
                edgecolor="k",
                lw=1.0,
                ls="solid",
            )
            axis.add_patch(blockPatch)
            axis.text(
                xTextLoc,
                yBlockCenterLoc,
                blockType.upper() + dLabel,
                ha="left",
                fontsize=10,
            )
            yBlockLoc += blockHeight
            yBlockHeights.append(yBlockLoc)

            # Add location, block heights, and axial mesh points to ordered set
            yBlockAxMesh.add((yBlockCenterLoc, blockHeight, b.p.axMesh))

        # Add the block heights, block number of axial mesh points on the far right of the plot.
        if isLastAssem and showBlockAxMesh:
            xEndLoc = 0.5 + xAssemEndLoc
            for bCenter, bHeight, axMeshPoints in yBlockAxMesh:
                axis.text(
                    xEndLoc,
                    bCenter,
                    "{} cm ({})".format(bHeight, axMeshPoints),
                    fontsize=10,
                    ha="left",
                )

        return xBlockLoc, yBlockHeights, yBlockAxMesh

    def getAssemTypeLetters(self):
        """
        Builds a list of unique capital letters for each assembly.

        Tries with the first letter of each word, then goes to just continuous letters.
        If nothing unique, just pulls from the alphabet.

        Returns
        -------
        assemTypeLetters : dict
            keys are assembly types, vals are capital letters.
        """

        assemTypeLetters = {}
        doneLetters = []
        candidate = None
        alphabet = frozenset([chr(units.ASCII_LETTER_A + i) for i in range(26)])
        for a in self:
            aType = a.getType()

            if aType not in assemTypeLetters:
                # build list of candidate letters. Start with first letter,
                # then first letter of second word, then all following letters.
                candidates = [aType[0]]
                for word in aType.split()[1:]:
                    # add first letter of each word
                    candidates.append(word[0])
                candidates.extend(aType.replace(" ", "")[1:])  # no spaces allowed
                # add in remaining letters in alphabet
                done2 = frozenset(
                    doneLetters
                )  # frozensets allow - to be a difference operator. Very nice.
                candidates.extend([a for a in alphabet - done2])

                # find a unique candidate letter
                for candidate in candidates:
                    candidate = candidate.upper()
                    if candidate not in doneLetters:
                        doneLetters.append(candidate)
                        break

                if not candidate:
                    runLog.error(
                        "Cannot determine type letter of {0} assemblies. Are there more "
                        "than 26 assembly types? If so, upgrade assembly type ID system."
                        "Done letters are: {1}".format(aType, doneLetters)
                    )
                    raise RuntimeError("Failed to determine assembly type letter.")
                assemTypeLetters[aType] = candidate

        return assemTypeLetters

    def saveAllFlux(self, fName="allFlux.txt"):
        """Dump all flux to file for debugging purposes."""
        blocks = list(self.getBlocks())
        groups = range(self.lib.numGroups)
        with open(fName, "w") as f:
            for block in blocks:
                for gi in groups:
                    f.write(
                        "{:10s} {:10d} {:12.5E} {:12.5E} {:12.5E}\n"
                        "".format(
                            block.getName(),
                            gi,
                            block.p.mgFlux[gi],
                            block.p.adjMgFlux[gi],
                            block.getVolume(),
                        )
                    )
                if len(block.p.mgFlux) > len(groups) or len(block.p.adjMgFlux) > len(
                    groups
                ):
                    raise ValueError(
                        "Too many flux values: {}\n{}\n{}".format(
                            block, block.p.mgFlux, block.p.adjMgFlux
                        )
                    )

    def getAssembliesOnSymmetryLine(self, symmetryLineID):
        """
        Find assemblies that are on a symmetry line in a symmetric core.
        """
        assembliesOnLine = []
        for a in self:
            if a.isOnWhichSymmetryLine() == symmetryLineID:
                assembliesOnLine.append(a)

        assembliesOnLine.sort()  # in order of innermost to outermost (for averaging)
        return assembliesOnLine

    def _addBlockToXsIndex(self, block):
        """
        Build cross section index as required by subdivide.
        """
        mats, _samples = block.getDominantMaterial(None)
        mTuple = ("", 0)
        blockVol = block.getVolume()
        for matName, volume in mats.items():
            if volume > mTuple[1]:
                mTuple = (matName, volume / blockVol, False)
        self.xsIndex[block.p.xsType] = mTuple

    def buildZones(self, cs):
        """Update the zones on the reactor."""
        self.zones = zones.buildZones(self, cs)
        self.zones = zones.splitZones(self, cs, self.zones)

    def getCoreRadius(self):
        """Returns a radius that the core would fit into. """
        return self.getNumRings(indexBased=True) * self.getFirstBlock().getPitch()

    def findAllMeshPoints(self, assems=None, applySubMesh=True):
        """
        Return all mesh positions in core including both endpoints.

        Parameters
        ----------
        assems : list, optional
            assemblies to consider when determining the mesh points. If not given, all in-core assemblies are used.
        applySubMesh : bool, optional
            Apply submeshing parameters to make the mesh smaller on a block-by-block basis. Default=True.


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
        """
        runLog.debug("Finding all mesh points.")
        if assems is None:
            assems = list(self)

        iMesh, jMesh, kMesh = set(), set(), set()
        for a in assems:
            for b in a:
                # these params should be combined into a new b.p.meshSubdivisions tuple
                numPoints = (
                    (a.p.AziMesh, a.p.RadMesh, b.p.axMesh)
                    if applySubMesh
                    else (1, 1, 1)
                )
                base = b.spatialLocator.getGlobalCellBase()
                top = (
                    b.spatialLocator.getGlobalCellTop()
                )  # make sure this is in mesh coordinates (important to have TRZ, not XYZ in TRZ cases.
                for axis, (collection, subdivisions) in enumerate(
                    zip((iMesh, jMesh, kMesh), numPoints)
                ):
                    axisVal = float(base[axis])  # convert from numpy.float64
                    step = float(top[axis] - axisVal) / subdivisions
                    for _subdivision in range(subdivisions):
                        collection.add(round(axisVal, units.FLOAT_DIMENSION_DECIMALS))
                        axisVal += step
                    collection.add(
                        round(axisVal, units.FLOAT_DIMENSION_DECIMALS)
                    )  # add top too (only needed for last point)

        iMesh, jMesh, kMesh = map(sorted, (iMesh, jMesh, kMesh))

        return iMesh, jMesh, kMesh

    def findAllAxialMeshPoints(self, assems=None, applySubMesh=True):
        """
        Return a list of all z-mesh positions in the core including zero and the top.
        """
        _i, _j, k = self.findAllMeshPoints(assems, applySubMesh)
        return k

    def updateAxialMesh(self):
        """
        Update axial mesh based on perturbed meshes of all the assemblies.

        Notes
        -----
        While processLoading finds all axial mesh points, this method simply updates the values of the
        known mesh with the current assembly heights. This does not change the number of mesh points.

        If `detailedAxialExpansion` is active, the global axial mesh param still only tracks the refAssem.
        Otherwise, thousands upon thousands of mesh points would get created.
        """
        # most of the time, we want fuel, but they should mostly have the same number of blocks
        # if this becomes a problem, we might find either the
        #  1. mode: (len(a) for a in self).mode(), or
        #  2. max: max(len(a) for a in self)
        # depending on what makes the most sense
        refAssem = self.getFirstAssembly(Flags.FUEL) or self.getFirstAssembly()

        avgHeight = utils.average1DWithinTolerance(
            numpy.array(
                [
                    [
                        h
                        for b in a
                        for h in [(b.p.ztop - b.p.zbottom) / b.p.axMesh] * b.p.axMesh
                    ]
                    for a in self
                    if self.findAllAxialMeshPoints([a])
                    == self.findAllAxialMeshPoints([refAssem])
                ]
            )
        )

        self.p.axialMesh = list(numpy.append([0.0], avgHeight.cumsum()))

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
            "The value {} cm is not within range of the reactor axial mesh with max {}"
            "".format(heightCm, currentHeightCm)
        )

    def addMoreNodes(self, meshList):
        """
        Add additional mesh points in the the meshList so that the ratio of mesh sizes does not vary too fast.
        """
        ratio = self._minMeshSizeRatio
        for i, innerMeshVal in enumerate(meshList[1:-1], start=1):
            dP0 = innerMeshVal - meshList[i - 1]
            dP1 = meshList[i + 1] - innerMeshVal

            if dP0 / (dP0 + dP1) < ratio:
                runLog.warning(
                    "Mesh gap too small. Adjusting mesh to be more reasonable."
                )
                meshList.append(innerMeshVal + dP1 * ratio)
                meshList.sort()
                return meshList, False
            elif dP0 / (dP0 + dP1) > (1.0 - ratio):
                runLog.warning(
                    "Mesh gap too large. Adjusting mesh to be more reasonable."
                )
                meshList.append(meshList[i - 1] + dP0 * (1.0 - ratio))
                meshList.sort()
                return meshList, False

        return meshList, True

    def findAllAziMeshPoints(self, extraAssems=None, applySubMesh=True):
        r"""
        returns a list of all azimuthal (theta)-mesh positions in the core.

        Parameters
        ----------
        extraAssems : list
            additional assemblies to consider when determining the mesh points.
            They may be useful in the MCPNXT models to represent the fuel management dummies.

        applySubMesh : bool
            generates submesh points to further discretize the theta reactor mesh

        """
        i, j, k = self.findAllMeshPoints(extraAssems, applySubMesh)
        return i

    def findAllRadMeshPoints(self, extraAssems=None, applySubMesh=True):
        r"""
        returns a list of all radial-mesh positions in the core.

        Notes
        -----

        Parameters
        ----------
        extraAssems : list
            additional assemblies to consider when determining the mesh points.
            They may be useful in the MCPNXT models to represent the fuel management dummies.

        applySubMesh : bool
            (not implemented) generates submesh points to further discretize the radial reactor mesh

        """
        i, j, k = self.findAllMeshPoints(extraAssems, applySubMesh)
        return j

    def getMaxBlockParam(self, *args, **kwargs):
        """Get max param over blocks"""
        if "generationNum" in kwargs:
            raise ValueError(
                "Cannot getMaxBlockParam over anything but blocks. Prefer `getMaxParam`."
            )
        kwargs["generationNum"] = 2
        return self.getMaxParam(*args, **kwargs)

    def getTotalBlockParam(self, *args, **kwargs):
        """Get total param over blocks."""
        if "generationNum" in kwargs:
            raise ValueError(
                "Cannot getTotalBlockParam over anything but blocks. Prefer `calcTotalParam`."
            )
        kwargs["generationNum"] = 2
        return self.calcTotalParam(*args, **kwargs)

    def getMaxNumPins(self):
        """find max number of pins of any block in the reactor"""
        return max(b.getNumPins() for b in self.getBlocks())

    def getMinimumPercentFluxInFuel(self, target=0.005):
        r"""
        Goes through the entire reactor to determine what percentage of flux occures at
        each ring.  Starting with the outer ring, this function helps determine the effective
        size of the core where additional assemblies will not help the breeding in the TWR.

        Parameters
        ----------

        target : float
            This is the fraction of the total reactor fuel flux compared to the flux in a
            specific assembly in a ring

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

        allFuelBlocks = list(self.getBlocks(Flags.FUEL))

        # loop there all of the rings
        for ringNumber in range(numRings, 0, -1):

            # compare to outer most ring
            # flatten list into one list of all blocks
            blocksInRing = list(
                itertools.chain(
                    *[
                        a.getBlocks(Flags.FUEL)
                        for a in self.getAssembliesInRing(ringNumber)
                    ]
                )
            )
            # TODO: itertools.chain.from_iterable(...)

            totalPower = self.getTotalBlockParam("flux", objs=allFuelBlocks)
            ringPower = self.getTotalBlockParam("flux", objs=blocksInRing)

            # make sure that there is a non zero return
            if fluxFraction == 0 and ringPower > 0:
                fluxFraction = ringPower / totalPower
                targetRing = ringNumber

            # this will only get the leakage if the target fraction isn't too low
            if (
                ringPower / totalPower < target
                and ringPower / totalPower > fluxFraction
            ):
                fluxFraction = ringPower / totalPower
                targetRing = ringNumber

        return targetRing, fluxFraction

    def _buildLocationIndexLookup(self):
        r"""builds lookup to convert ring/pos to index for MCNP or finding neighbors or
        whatever else you may think of. """
        self.locationIndexLookup = {}

        # make sure to get one extra ring because when neighbors are searched for, it will look
        # for neighbors of the outer ring, which will look in ring+1.
        # don't worry though, whichASsemblyIsIn will return None for those guys.
        if self.geomType == geometry.RZT:
            n1 = len(self.findAllAziMeshPoints())
            n2 = len(self.findAllRadMeshPoints())
            for i1 in range(1, n1):
                for i2 in range(1, n2):
                    self.locationIndexLookup[i1, i2] = (i1, i2)
        else:
            dumLocClass = locations.locationFactory(self.geomType)
            dumLoc = dumLocClass()
            for ring in range(self.getNumRings(indexBased=True) + 1):
                rebusRing = ring + 1
                for pos in range(dumLoc.getNumPosInRing(rebusRing)):
                    # convert rebus numbering (starts at 1)
                    rebPos = pos + 1
                    dumLoc.i1 = rebusRing
                    dumLoc.i2 = rebPos
                    dumLoc.makeLabel()
                    i, j = dumLoc.indices()
                    self.locationIndexLookup[i, j] = (rebusRing, rebPos)

    def getAvgTemp(self, typeSpec, blockList=None, flux2Weight=False):
        r"""
        get the volume-average fuel, cladding, coolant temperature in core

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
            blockList = list(self.getBlocks())
            ## TODO: this doesn't need to be a list
        for b in blockList:
            if flux2Weight:
                weight = b.p.flux ** 2.0
            else:
                weight = 1.0
            for c in b.getComponents(typeSpec):
                vol = c.getVolume()
                num += c.temperatureInC * vol * weight
                denom += vol * weight

        if denom:
            return num / denom
        else:
            raise RuntimeError("no temperature average for {0}".format(typeSpec))

    def getDominantMaterial(self, typeSpec, blockList=None):
        r"""
        return the most common material in the compositions of the blocks.

        If you pass ['clad', 'duct'], you might get HT9, for example.
        This allows generality in reading material properties on groups of blocks.
        Dominant is defined by most volume.

        Parameters
        ----------
        typeSpec : Flags or iterable of Flags
            The types of components to search through (e.g. Flags.CLAD, Flags.DUCT)

        blockList : iterable, optional
            A list of blocks that will be considered in the search for a dominant material.
            If blank, will consider all blocks in the reactor

        Returns
        -------
        maxMat : A material object that represents the dominant material

        See Also
        --------
        armi.reactor.blocks.Blocks.getDominantMaterial : block level helper for this.
        """
        mats = {}
        samples = {}

        # new style
        if not blockList:
            blockList = list(self.getBlocks())
            ## TODO: no need for list
        for b in blockList:
            bMats, bSamples = b.getDominantMaterial(typeSpec)
            for matName, blockVolume in bMats.items():
                previousVolume = mats.get(matName, 0.0)
                mats[matName] = previousVolume + blockVolume
            samples.update(bSamples)

        # find max volume
        maxVol = 0.0
        maxMat = None
        for mName, vol in mats.items():
            if vol > maxVol:
                maxVol = vol
                maxMat = mName
        if maxMat:
            # return a copy of this material. Note that if this material
            # has properties like Zr-frac, enrichment, etc. then this will
            # just return one in the batch, not an average.
            return samples[maxMat]

    def getAllNuclidesIn(self, mats):
        """
        Find all nuclides that are present in these materials anywhere in the core.

        Parameters
        ----------
        mats : iterable or Material
            List (or single) of materials to scan the full core for, accumulating a master nuclide list

        Returns
        -------
        allNucNames : list
            All nuclide names in this material anywhere in the reactor

        See Also
        --------
        getDominantMaterial : finds the most prevalent material in a certain type of blocks
        Block.adjustDensity : modifies nuclides in a block

        Notes
        -----
        If you need to know the nuclides in a fuel pin, you can't just use the sample returned
        from getDominantMaterial, because it may be a fresh fuel material (U and Zr) even though
        there are burned materials elsewhere (with U, Zr, Pu, LFP, etc.).

        """
        if not isinstance(mats, list):
            # single material passed in
            mats = [mats]
        names = set(m.name for m in mats)
        allNucNames = set()
        for b in self.getBlocks():
            for c in b.getComponents():
                if c.material.name in names:
                    allNucNames.update(c.getNuclides())
        return list(allNucNames)

    def growToFullCore(self, cs):
        r"""copies symmetric assemblies to build a full core model out of a 1/3 core model

        Returns
        -------

        converter : GeometryConverter
            Geometry converter used to do the conversion.

        """
        import armi.reactor.converters.geometryConverters as gc

        converter = gc.ThirdCoreHexToFullCoreChanger(cs)
        converter.convert(self.r)

        return converter

    def setPitchUniform(self, pitchInCm, updateNumberDensityParams=True):
        """
        set the pitch in all blocks
        """
        for b in self.getBlocks():
            b.setPitch(pitchInCm, updateNumberDensityParams=updateNumberDensityParams)

        # have to update the 2-D reactor mesh too.
        self.spatialGrid.changePitch(pitchInCm)

    def getAverageAssemblyPower(self, ringZoneNum=None):
        r"""return the average assembly power in Watts in this ring zone or the full core. """
        if ringZoneNum is not None:
            # consider only a single ring zone.
            ringZoneRings = self.zones.getRingZoneRings()
            if ringZoneNum > len(ringZoneRings):
                runLog.warning(
                    "Cannot produce zone summary for zone {0} since there are "
                    "only {1} zones defined".format(ringZoneNum, len(ringZoneRings))
                )
                return []

            ringsInThisZone = ringZoneRings[ringZoneNum]
        else:
            # do full core.
            ringsInThisZone = range(self.getNumRings() + 1)

        assemCount = 0.0
        totPow = 0.0
        for ring in ringsInThisZone:
            assembliesInThisRing = self.whichAssemblyIsIn(ring, typeFlags=Flags.FUEL)
            # assume all fuel assemblies have the same number of blocks.
            if not assembliesInThisRing:
                # skip this non-fueled ring and go to the next.
                continue

            # Add up slab power and flow rates
            for a in assembliesInThisRing:
                totPow += a.calcTotalParam("power")
                assemCount += 1

        if not assemCount:
            avgPow = 0.0
        else:
            avgPow = totPow / assemCount
        return avgPow

    def calcBlockMaxes(self):
        r"""
        searches all blocks for maximum values of key params

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
        # may want to use percentBuMax for pin-detailed cases.
        self.p.maxBuF = max(
            (
                a.getMaxParam("percentBu")
                for a in self.getAssemblies(Flags.FEED | Flags.FUEL)
            ),
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
        r"""
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

    def processLoading(self, cs):
        """
        After nuclide densities are loaded, this goes through and prepares the reactor.

        Notes
        -----
        This does a few operations :
         * It process boosters,
         * sets axial snap lists,
         * checks the geometry,
         * sets up location tables ( tracks where the initial feeds were (for moderation or something)

        """
        runLog.header(
            "=========== Initializing Mesh, Assembly Zones, and Nuclide Categories =========== "
        )

        self.p.power = cs["power"]

        for b in self.getBlocks():
            if b.p.molesHmBOL > 0.0:
                break
        else:
            # Good easter egg, but sometimes a user will want to use the framework do
            # only decay analyses and heavy metals are not required.
            runLog.warning(
                "The system has no heavy metal and therefore is not a nuclear reactor.\n"
                "Please make sure that this is intended and not a input error."
            )

        self.p.axialMesh = self.findAllAxialMeshPoints()

        if not cs["detailedAxialExpansion"]:
            for a in self.getAssemblies(includeBolAssems=True):
                # prepare for mesh snapping during axial expansion
                a.makeAxialSnapList(self.refAssem)

        self.numRings = self.getNumRings()  # TODO: why needed?
        self._buildLocationIndexLookup()  # for converting indices to locations.

        self.getNuclideCategories()

        # some blocks will not move in the core like grid plates... Find them and fix them in place
        stationaryBlocks = []
        # look for blocks that should not be shuffled in an assembly.  It is assumed that the
        # reference assembly has all the fixed block information and it is the same for all assemblies
        for i, b in enumerate(self.refAssem):
            if b.hasFlags(Flags.GRID_PLATE):
                stationaryBlocks.append(i)
                runLog.extra(
                    "Detected a grid plate {}.  Adding to stationary blocks".format(b)
                )  # TODO: remove hard-coded assumption of grid plates (T3019)

        cs["stationaryBlocks"] = stationaryBlocks

        # Perform initial zoning task
        self.buildZones(cs)

        self.p.maxAssemNum = self.getMaxParam("assemNum")

        armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=self, cs=cs)
