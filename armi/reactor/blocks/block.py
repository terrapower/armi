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
The generic Block base class. This is meant to be the basis of all Blocks you use in your modeling. ARMI encourages you
to build your own subclass of an ARMI Block type, to simplify your reactor blueprints.

Blocks are axial chunks of assemblies. They contain most of the state variables, including power, flux, and homogenized
number densities. Blocks are further divided into components.
"""

import collections
import copy
import math
from typing import ClassVar, Optional, Tuple, Type

import numpy as np

from armi import runLog
from armi.bookkeeping import report
from armi.nuclearDataIO import xsCollections
from armi.reactor import (
    blockParameters,
    components,
    composites,
    grids,
    parameters,
)
from armi.reactor.components import basicShapes
from armi.reactor.flags import Flags
from armi.utils import densityTools, units
from armi.utils.plotting import plotBlockFlux
from armi.utils.units import TRACE_NUMBER_DENSITY

PIN_COMPONENTS = [
    Flags.CONTROL,
    Flags.PLENUM,
    Flags.SHIELD,
    Flags.FUEL,
    Flags.CLAD,
    Flags.PIN,
    Flags.WIRE,
]

_PitchDefiningComponent = Optional[Tuple[Type[components.Component], ...]]


class Block(composites.Composite):
    """
    An axial slice of an assembly.

    Blocks are Composite objects with extra parameter bindings, and utility methods that let them
    play nicely with their containing Assembly.
    """

    uniqID = 0

    # dimension used to determine which component defines the block's pitch
    PITCH_DIMENSION = "op"

    # component type that can be considered a candidate for providing pitch
    PITCH_COMPONENT_TYPE: ClassVar[_PitchDefiningComponent] = None

    pDefs = blockParameters.getBlockParameterDefinitions()

    def __init__(self, name: str, height: float = 1.0):
        """
        Builds a new ARMI block.

        name : str
            The name of this block
        height : float, optional
            The height of the block in cm. Defaults to 1.0 so that ``getVolume`` assumes unit height.
        """
        composites.Composite.__init__(self, name)
        self.p.height = height
        self.p.heightBOL = height
        self.p.orientation = np.array((0.0, 0.0, 0.0))

        self.points = []
        self.macros = None

        # flag to indicated when DerivedShape children must be updated.
        self.derivedMustUpdate = False

        # which component to use to determine block pitch, along with its 'op'
        self._pitchDefiningComponent = (None, 0.0)

        # Manually set some parameters at BOL
        for problemParam in ["THcornTemp", "THedgeTemp"]:
            self.p[problemParam] = []

    def __repr__(self):
        # be warned, changing this might break unit tests on input file generations
        return "<{type} {name} at {loc} XS: {xs} ENV GP: {env}>".format(
            type=self.getType(),
            name=self.getName(),
            xs=self.p.xsType,
            env=self.p.envGroup,
            loc=self.getLocation(),
        )

    def __deepcopy__(self, memo):
        """
        Custom deepcopy behavior to prevent duplication of macros and _lumpedFissionProducts.

        We detach the recursive links to the parent and the reactor to prevent blocks carrying large
        independent copies of stale reactors in memory. If you make a new block, you must add it to
        an assembly and a reactor.
        """
        # add self to memo to prevent child objects from duplicating the parent block
        memo[id(self)] = b = self.__class__.__new__(self.__class__)

        # use __getstate__ and __setstate__ pickle-methods to initialize
        state = self.__getstate__()  # __getstate__ removes parent
        del state["macros"]
        del state["_lumpedFissionProducts"]
        b.__setstate__(copy.deepcopy(state, memo))

        # assign macros and LFP
        b.macros = self.macros
        b._lumpedFissionProducts = self._lumpedFissionProducts

        return b

    def createHomogenizedCopy(self, pinSpatialLocators=False):
        """
        Create a copy of a block.

        Notes
        -----
        Used to implement a copy function for specific block types that can be much faster than a
        deepcopy by glossing over details that may be unnecessary in certain contexts.

        This base class implementation is just a deepcopy of the block, in full detail (not
        homogenized).
        """
        return copy.deepcopy(self)

    @property
    def core(self):
        from armi.reactor.reactors import Core

        c = self.getAncestor(lambda c: isinstance(c, Core))
        return c

    def makeName(self, assemNum, axialIndex):
        """
        Generate a standard block from assembly number.

        This also sets the block-level assembly-num param.

        Once, we used a axial-character suffix to represent the axial index, but this is inherently limited so we
        switched to a numerical name. The axial suffix needs can be brought in to plugins that require them.

        Examples
        --------
        >>> makeName(120, 5)
        'B0120-005'
        """
        self.p.assemNum = assemNum
        return "B{0:04d}-{1:03d}".format(assemNum, axialIndex)

    def getSmearDensity(self, cold=True):
        """
        Compute the smear density of pins in this block.

        Smear density is the area of the fuel divided by the area of the space available for fuel inside the cladding.
        Other space filled with solid materials is not considered available. If all the area is fuel, it has 100% smear
        density. Lower smear density allows more room for swelling.

        Warning
        -------
        This requires circular fuel and circular cladding. Designs that vary from this will be wrong. It may make sense
        in the future to put this somewhere a bit more design specific.

        Notes
        -----
        This only considers circular objects. If you have a cladding that is not a circle, it will be ignored.

        Negative areas can exist for void gaps in the fuel pin. A negative area in a gap represents overlap area between
        two solid components. To account for this additional space within the pin cladding the abs(negativeArea) is
        added to the inner cladding area.

        Parameters
        ----------
        cold : bool, optional
            If false, returns the smear density at hot temperatures

        Returns
        -------
        float
            The smear density as a fraction.
        """
        fuels = self.getComponents(Flags.FUEL)
        if not fuels:
            # smear density is not computed for non-fuel blocks
            return 0.0
        elif not self.getNumPins():
            # smear density is only defined for pinned blocks
            return 0.0

        circles = self.getComponentsOfShape(components.Circle)
        if not circles:
            raise ValueError(f"Cannot get smear density of {self}. There are no circular components.")

        clads = set(self.getComponents(Flags.CLAD)).intersection(set(circles))
        if not clads:
            raise ValueError(f"Cannot get smear density of {self}. There are no clad components.")

        # Compute component areas
        innerCladdingArea = sum(
            math.pi * clad.getDimension("id", cold=cold) ** 2 / 4.0 * clad.getDimension("mult") for clad in clads
        )
        sortedClads = sorted(clads)
        sortedCompsInsideClad = self.getSortedComponentsInsideOfComponent(sortedClads.pop())

        return self.computeSmearDensity(innerCladdingArea, sortedCompsInsideClad, cold)

    @staticmethod
    def computeSmearDensity(innerCladdingArea: float, sortedCompsInsideClad: list[components.Component], cold: bool):
        """Compute the smear density for a sorted list of components.

        Parameters
        ----------
        innerCladdingArea : float
            Circular area inside the cladding.
        sortedCompsInsideClad : list
            A sorted list of Components inside the cladding.
        cold : bool
            If false, returns the smear density at hot temperatures

        Returns
        -------
        float
            The smear density as a fraction.
        """
        fuelComponentArea = 0.0
        unmovableComponentArea = 0.0
        negativeArea = 0.0
        for c in sortedCompsInsideClad:
            componentArea = c.getArea(cold=cold)
            if c.isFuel():
                fuelComponentArea += componentArea
            elif c.hasFlags(Flags.CLAD):
                # this is another component's clad; don't count it towards unmoveable area
                pass
            elif c.hasFlags([Flags.SLUG, Flags.DUMMY]):
                # this flag designates that this clad/slug combination isn't fuel and shouldn't be in the average
                pass
            else:
                if c.containsSolidMaterial():
                    unmovableComponentArea += componentArea
                elif c.containsVoidMaterial() and componentArea < 0.0:
                    if cold:  # will error out soon
                        runLog.error(
                            "{} with id {} and od {} has negative area at cold dimensions".format(
                                c,
                                c.getDimension("id", cold=True),
                                c.getDimension("od", cold=True),
                            )
                        )
                    negativeArea += abs(componentArea)

        if cold and negativeArea:
            raise ValueError(
                "Negative component areas found. Check the cold dimensions are properly aligned and no components "
                "overlap."
            )

        innerCladdingArea += negativeArea  # See note 2 of self.getSmearDensity
        totalMovableArea = innerCladdingArea - unmovableComponentArea
        if totalMovableArea <= 0.0:
            return 0.0
        else:
            return fuelComponentArea / totalMovableArea

    def autoCreateSpatialGrids(self, systemSpatialGrid=None):
        """
        Creates a spatialGrid for a Block.

        Blocks do not always have a spatialGrid from Blueprints, but some Blocks can have their
        spatialGrids inferred based on the multiplicity of their components. This would add the
        ability to create a spatialGrid for a Block and give its children the corresponding
        spatialLocators if certain conditions are met.

        Parameters
        ----------
        systemSpatialGrid : Grid, optional
            Spatial Grid of the system-level parent of this Assembly that contains this Block.

        Raises
        ------
        ValueError
            If the multiplicities of the block are not only 1 or N or if generated ringNumber leads
            to more positions than necessary.
        """
        if self.spatialGrid is None:
            self.spatialGrid = systemSpatialGrid

    def assignPinIndices(self):
        pass

    def getMgFlux(self, adjoint=False, average=False, gamma=False):
        """
        Returns the multigroup neutron flux in [n/cm^2/s].

        The first entry is the first energy group (fastest neutrons). Each additional group is the next energy group, as
        set in the ISOTXS library.

        It is stored integrated over volume on self.p.mgFlux

        Parameters
        ----------
        adjoint : bool, optional
            Return adjoint flux instead of real
        average : bool, optional
            If true, will return average flux between latest and previous. Doesn't work for pin detailed yet.
        gamma : bool, optional
            Whether to return the neutron flux or the gamma flux.

        Returns
        -------
        flux : multigroup neutron flux in [n/cm^2/s]
        """
        flux = composites.ArmiObject.getMgFlux(self, adjoint=adjoint, average=False, gamma=gamma)
        if average and np.any(self.p.lastMgFlux):
            volume = self.getVolume()
            lastFlux = self.p.lastMgFlux / volume
            flux = (flux + lastFlux) / 2.0

        return flux

    def setPinMgFluxes(self, fluxes, adjoint=False, gamma=False):
        """
        Store the pin-detailed multi-group neutron flux.

        Parameters
        ----------
        fluxes : np.ndarray
            The block-level pin multigroup fluxes. ``fluxes[i, g]`` represents the flux in group g for
            pin ``i`` located at ``self.getPinLocations()[i]``. Flux units are the standard n/cm^2/s.
        adjoint : bool, optional
            Whether to set real or adjoint data.
        gamma : bool, optional
            Whether to set gamma or neutron data.
        """
        if gamma:
            if adjoint:
                raise ValueError("Adjoint gamma flux is currently unsupported.")
            else:
                self.p.pinMgFluxesGamma = fluxes
        else:
            if adjoint:
                self.p.pinMgFluxesAdj = fluxes
            else:
                self.p.pinMgFluxes = fluxes

    def getMicroSuffix(self):
        """
        Returns the microscopic library suffix (e.g. 'AB') for this block.

        DIF3D and MC2 are limited to 6 character nuclide labels. ARMI by convention uses the first 4
        for nuclide name (e.g. U235, PU39, etc.) and then uses the 5th character for cross-section
        type and the 6th for burnup group. This allows a variety of XS sets to be built modeling
        substantially different blocks.

        Notes
        -----
        The single-letter use for xsType and envGroup limit users to 52 groups of each. ARMI will
        allow 2-letter xsType designations if and only if the `envGroup` setting has length 1 (i.e.
        no burnup/temp groups are defined). This is useful for high-fidelity XS modeling.
        """
        env = self.p.envGroup
        if not env:
            raise RuntimeError(
                "Cannot get MicroXS suffix because {0} in {1} does not have a environment(env) group".format(
                    self, self.parent
                )
            )

        xsType = self.p.xsType
        if len(xsType) == 1:
            return xsType + env
        elif len(xsType) == 2 and ord(env) != ord("A"):
            # default is "A" so if we got an off default 2 char, there is no way to resolve.
            raise ValueError("Use of non-default env groups is not allowed with multi-character xs groups!")
        else:
            # ignore env group, multi Char XS type to support assigning 2 chars in blueprints
            return xsType

    def getHeight(self):
        """Return the block height."""
        return self.p.height

    def setHeight(self, modifiedHeight, conserveMass=False, adjustList=None):
        """
        Set a new height of the block.

        Parameters
        ----------
        modifiedHeight : float
            The height of the block in cm

        conserveMass : bool, optional
            Conserve mass of nuclides in ``adjustList``.

        adjustList : list, optional
            Nuclides that will be conserved in conserving mass in the block. It is recommended to
            pass a list of all nuclides in the block.

        Notes
        -----
        There is a coupling between block heights, the parent assembly axial mesh, and the
        ztop/zbottom/z params of the sibling blocks. When you set a height, all those things are
        invalidated. Thus, this method has to go through and update them via
        ``parent.calculateZCoords``.

        See Also
        --------
        armi.reactor.reactors.Core.updateAxialMesh
            May need to be called after this.
        armi.reactor.assemblies.Assembly.calculateZCoords
            Recalculates z-coords, automatically called by this.
        """
        originalHeight = self.getHeight()  # get before modifying
        if modifiedHeight < 0.0:
            raise ValueError(f"Cannot set height of block {self} to height of {modifiedHeight} cm")
        self.p.height = modifiedHeight
        self.clearCache()
        if conserveMass:
            if originalHeight != modifiedHeight:
                if not adjustList:
                    raise ValueError("Nuclides in ``adjustList`` must be provided to conserve mass.")
                self.adjustDensity(originalHeight / modifiedHeight, adjustList)
        if self.parent:
            self.parent.calculateZCoords()

    def getWettedPerimeter(self):
        raise NotImplementedError

    def getFlowAreaPerPin(self):
        """
        Return the flowing coolant area of the block in cm^2, normalized to the number of pins in the block.

        NumPins looks for max number of fuel, clad, control, etc.

        See Also
        --------
        armi.reactor.blocks.Block.getNumPins
            figures out numPins
        """
        numPins = self.getNumPins()
        try:
            return self.getComponent(Flags.COOLANT, exact=True).getArea() / numPins
        except ZeroDivisionError:
            raise ZeroDivisionError(
                f"Block {self} has 0 pins (fuel, clad, control, shield, etc.). Thus, its flow area "
                "per pin is undefined."
            )

    def getHydraulicDiameter(self):
        raise NotImplementedError

    def adjustUEnrich(self, newEnrich):
        """
        Adjust U-235/U-238 mass ratio to a mass enrichment.

        Parameters
        ----------
        newEnrich : float
            New U-235 enrichment in mass fraction

        Notes
        -----
        completeInitialLoading must be run because adjusting the enrichment actually changes the
        mass slightly and you can get negative burnups, which you do not want.
        """
        fuels = self.getChildrenWithFlags(Flags.FUEL)

        if fuels:
            for fuel in fuels:
                fuel.adjustMassEnrichment(newEnrich)
        else:
            # no fuel in this block
            tU = self.getNumberDensity("U235") + self.getNumberDensity("U238")
            if tU:
                self.setNumberDensity("U235", tU * newEnrich)
                self.setNumberDensity("U238", tU * (1.0 - newEnrich))

        self.completeInitialLoading()

    def getLocation(self):
        """Return a string representation of the location.

        .. impl:: Location of a block is retrievable.
            :id: I_ARMI_BLOCK_POSI0
            :implements: R_ARMI_BLOCK_POSI

            If the block does not have its ``core`` attribute set, if the block's parent does not
            have a ``spatialGrid`` attribute, or if the block does not have its location defined by
            its ``spatialLocator`` attribute, return a string indicating that it is outside of the
            core.

            Otherwise, use the :py:class:`~armi.reactor.grids.Grid.getLabel` static method to
            convert the block's indices into a string like "XXX-YYY-ZZZ". For hexagonal geometry,
            "XXX" is the zero-padded hexagonal core ring, "YYY" is the zero-padded position in that
            ring, and "ZZZ" is the zero-padded block axial index from the bottom of the core.
        """
        if self.core and self.parent.spatialGrid and self.spatialLocator:
            return self.core.spatialGrid.getLabel(self.spatialLocator.getCompleteIndices())
        else:
            return "ExCore"

    def coords(self):
        """
        Returns the coordinates of the block.

        .. impl:: Coordinates of a block are queryable.
            :id: I_ARMI_BLOCK_POSI1
            :implements: R_ARMI_BLOCK_POSI

            Calls to the :py:meth:`~armi.reactor.grids.locations.IndexLocation.getGlobalCoordinates`
            method of the block's ``spatialLocator`` attribute, which recursively calls itself on
            all parents of the block to get the coordinates of the block's centroid in 3D cartesian
            space.
        """
        return self.spatialLocator.getGlobalCoordinates()

    def setBuLimitInfo(self):
        """Sets burnup limit based on igniter, feed, etc."""
        if self.p.buRate == 0:
            # might be cycle 1 or a non-burning block
            self.p.timeToLimit = 0.0
        else:
            timeLimit = (self.p.buLimit - self.p.percentBu) / self.p.buRate + self.p.residence
            self.p.timeToLimit = (timeLimit - self.p.residence) / units.DAYS_PER_YEAR

    def getMaxArea(self):
        raise NotImplementedError

    def getArea(self, cold=False):
        """
        Return the area of a block for a full core or a 1/3 core model.

        Area is consistent with the area in the model, so if you have a central assembly in a 1/3
        symmetric model, this will return 1/3 of the total area of the physical assembly. This way,
        if you take the sum of the areas in the core (or count the atoms in the core, etc.), you
        will have the proper number after multiplying by the model symmetry.

        Parameters
        ----------
        cold : bool
            flag to indicate that cold (as input) dimensions are required

        Notes
        -----
        This might not work for a 1/6 core model (due to symmetry line issues).

        Returns
        -------
        area : float (cm^2)

        See Also
        --------
        armi.reactor.blocks.Block.getMaxArea
            return the full area of the physical assembly disregarding model symmetry
        """
        # this caching requires that you clear the cache every time you adjust anything including
        # temperature and dimensions.
        area = self._getCached("area")
        if area:
            return area

        a = 0.0
        for c in self:
            myArea = c.getArea(cold=cold)
            a += myArea
        fullArea = a

        # correct the fullHexArea by the symmetry factor this factor determines if the hex has been
        # clipped by symmetry lines
        area = fullArea / self.getSymmetryFactor()

        self._setCache("area", area)
        return area

    def getVolume(self):
        """
        Return the volume of a block.

        Returns
        -------
        volume : float
            Block or component volume in cm^3
        """
        # use symmetryFactor in case the assembly is sitting on a boundary and needs to be cut in half, etc.
        vol = sum(c.getVolume() for c in self)
        return vol / self.getSymmetryFactor()

    def getSymmetryFactor(self):
        """
        Return a scaling factor due to symmetry on the area of the block or its components.

        Takes into account assemblies that are bisected or trisected by symmetry lines

        In 1/3 symmetric cases, the central assembly is 1/3 a full area. If edge assemblies are
        included in a model, the symmetry factor along both edges for overhanging assemblies should
        be 2.0. However, ARMI runs in most scenarios with those assemblies on the 120-edge removed,
        so the symmetry factor should generally be just 1.0.

        See Also
        --------
        armi.reactor.converters.geometryConverter.EdgeAssemblyChanger.scaleParamsRelatedToSymmetry
        """
        return 1.0

    def adjustDensity(self, frac, adjustList, returnMass=False):
        """
        Adjusts the total density of each nuclide in adjustList by frac.

        Parameters
        ----------
        frac : float
            The fraction of the current density that will remain after this operation

        adjustList : list
            List of nuclide names that will be adjusted.

        returnMass : bool
            If true, will return mass difference.

        Returns
        -------
        mass : float
            Mass difference in grams. If you subtract mass, mass will be negative.
            If returnMass is False (default), this will always be zero.
        """
        self._updateDetailedNdens(frac, adjustList)

        mass = 0.0
        if returnMass:
            # do this with a flag to enable faster operation when mass is not needed.
            volume = self.getVolume()

        numDensities = self.getNuclideNumberDensities(adjustList)

        for nuclideName, dens in zip(adjustList, numDensities):
            if not dens:
                # don't modify zeros.
                continue
            newDens = dens * frac
            # add a little so components remember
            self.setNumberDensity(nuclideName, newDens + TRACE_NUMBER_DENSITY)
            if returnMass:
                mass += densityTools.getMassInGrams(nuclideName, volume, newDens - dens)

        return mass

    def _updateDetailedNdens(self, frac, adjustList):
        """
        Update detailed number density which is used by hi-fi depleters such as ORIGEN.

        Notes
        -----
        This will perturb all number densities so it is assumed that if one of the active densities
        is perturbed, all of htem are perturbed.
        """
        if self.p.detailedNDens is None:
            # BOL assems get expanded to a reference so the first check is needed so it won't call
            # .blueprints on None since BOL assems don't have a core/r
            return
        if any(nuc in self.core.r.blueprints.activeNuclides for nuc in adjustList):
            self.p.detailedNDens *= frac
            # Other power densities do not need to be updated as they are calculated in the global
            # flux interface, which occurs after axial expansion on the interface stack.
            self.p.pdensDecay *= frac

    def completeInitialLoading(self, bolBlock=None):
        """
        Does some BOL bookkeeping to track things like BOL HM density for burnup tracking.

        This should run after this block is loaded up at BOC (called from Reactor.initialLoading).

        The original purpose of this was to get the moles HM at BOC for the moles Pu/moles HM at BOL
        calculation.

        This also must be called after modifying something like the smear density or zr fraction in
        an optimization case. In ECPT cases, a BOL block must be passed or else the burnup will try
        to get based on a pre-burned value.

        Parameters
        ----------
        bolBlock : Block, optional
            A BOL-state block of this block type, required for perturbed equilibrium cases.
            Must have the same enrichment as this block!

        Returns
        -------
        hmDens : float
            The heavy metal number density of this block.

        See Also
        --------
        Reactor.importGeom
        depletion._updateBlockParametersAfterDepletion
        """
        if bolBlock is None:
            bolBlock = self

        hmDens = bolBlock.getHMDens()  # total homogenized heavy metal number density
        self.p.nHMAtBOL = hmDens
        self.p.molesHmBOL = self.getHMMoles()
        self.p.puFrac = self.getPuMoles() / self.p.molesHmBOL if self.p.molesHmBOL > 0.0 else 0.0

        try:
            # non-pinned reactors (or ones without cladding) will not use smear density
            self.p.smearDensity = self.getSmearDensity()
        except ValueError:
            pass

        self.p.enrichmentBOL = self.getFissileMassEnrich()
        massHmBOL = 0.0
        for child in self:
            hmMass = child.getHMMass()
            massHmBOL += hmMass
            # Components have the following parameters but not every composite will massHmBOL,
            # molesHmBOL, puFrac, enrichmentBOL
            if isinstance(child, components.Component):
                child.p.massHmBOL = hmMass
                child.p.molesHmBOL = child.getHMMoles()
                if child.p.molesHmBOL:
                    child.p.enrichmentBOL = child.getFissileMassEnrich()

        self.p.massHmBOL = massHmBOL

        return hmDens

    def setB10VolParam(self, heightHot):
        """
        Set the b.p.initialB10ComponentVol param according to the volume of boron-10 containing components.

        Parameters
        ----------
        heightHot : Boolean
            True if self.height() is cold height
        """
        # exclude fuel components since they could have slight B10 impurity and
        # this metric is not relevant for fuel.
        b10Comps = [c for c in self if c.getNumberDensity("B10") and not c.isFuel()]
        if not b10Comps:
            return

        # get the highest density comp dont want to sum all because some comps might have very small
        # impurities of boron and adding this volume won't be conservative for captures per cc.
        b10Comp = sorted(b10Comps, key=lambda x: x.getNumberDensity("B10"))[-1]

        if len(b10Comps) > 1:
            runLog.warning(
                f"More than one boron10-containing component found in {self.name}. Only {b10Comp} "
                f"will be considered for calculation of initialB10ComponentVol Since adding "
                f"multiple volumes is not conservative for captures. All compos found {b10Comps}",
                single=True,
            )
        if self.isFuel():
            runLog.warning(
                f"{self.name} has both fuel and initial b10. b10 volume may not be conserved with axial expansion.",
                single=True,
            )

        # calc volume of boron components
        coldArea = b10Comp.getArea(cold=True)
        coldFactor = b10Comp.getThermalExpansionFactor() if heightHot else 1
        coldHeight = self.getHeight() / coldFactor
        self.p.initialB10ComponentVol = coldArea * coldHeight

    def replaceBlockWithBlock(self, bReplacement):
        """
        Replace the current block with the replacementBlock.

        Typically used in the insertion of control rods.
        """
        paramsToSkip = set(self.p.paramDefs.inCategory(parameters.Category.retainOnReplacement).names)

        tempBlock = copy.deepcopy(bReplacement)
        oldParams = self.p
        newParams = self.p = tempBlock.p
        for paramName in paramsToSkip:
            newParams[paramName] = oldParams[paramName]

        # update synchronization information
        self.p.assigned = parameters.SINCE_ANYTHING
        paramDefs = self.p.paramDefs
        for paramName in set(newParams.keys()) - paramsToSkip:
            paramDefs[paramName].assigned = parameters.SINCE_ANYTHING

        newComponents = tempBlock.getChildren()
        self.setChildren(newComponents)
        self.clearCache()

    @staticmethod
    def plotFlux(core, fName=None, bList=None, peak=False, adjoint=False, bList2=[]):
        """A simple pass-through method to a utils plotting function. This is here to preserve the API."""
        plotBlockFlux(core, fName, bList, peak, adjoint, bList2)

    def _updatePitchComponent(self, c):
        """
        Update the component that defines the pitch.

        Given a Component, compare it to the current component that defines the pitch of the Block.
        If bigger, replace it. We need different implementations of this to support different logic
        for determining the form of pitch and the concept of "larger".

        See Also
        --------
        CartesianBlock._updatePitchComponent
        """
        # Some block types don't have a clearly defined pitch (e.g. ThRZ)
        if self.PITCH_COMPONENT_TYPE is None:
            return

        if not isinstance(c, self.PITCH_COMPONENT_TYPE):
            return

        try:
            componentPitch = c.getDimension(self.PITCH_DIMENSION)
        except parameters.UnknownParameterError:
            # some components dont have the appropriate parameter
            return

        if componentPitch and (componentPitch > self._pitchDefiningComponent[1]):
            self._pitchDefiningComponent = (c, componentPitch)

    def add(self, c):
        composites.Composite.add(self, c)

        self.derivedMustUpdate = True
        self.clearCache()
        try:
            mult = int(c.getDimension("mult"))
            if self.p.percentBuByPin is None or len(self.p.percentBuByPin) < mult:
                # this may be a little wasteful, but we can fix it later...
                self.p.percentBuByPin = [0.0] * mult
        except AttributeError:
            # maybe adding a Composite of components rather than a single
            pass
        self._updatePitchComponent(c)

    def removeAll(self, recomputeAreaFractions=True):
        for c in list(self):
            self.remove(c, recomputeAreaFractions=False)
        if recomputeAreaFractions:  # only do this once
            self.getVolumeFractions()

    def remove(self, c, recomputeAreaFractions=True):
        composites.Composite.remove(self, c)
        self.clearCache()

        if c is self._pitchDefiningComponent[0]:
            self._pitchDefiningComponent = (None, 0.0)
            pc = self.getLargestComponent(self.PITCH_DIMENSION)
            if pc is not None:
                self._updatePitchComponent(pc)

        if recomputeAreaFractions:
            self.getVolumeFractions()

    def getComponentsThatAreLinkedTo(self, comp, dim):
        """
        Determine which dimensions of which components are linked to a specific dimension of a
        particular component.

        Useful for breaking fuel components up into individuals and making sure anything that was
        linked to the fuel mult (like the cladding mult) stays correct.

        Parameters
        ----------
        comp : Component
            The component that the results are linked to
        dim : str
            The name of the dimension that the results are linked to

        Returns
        -------
        linkedComps : list
            A list of (components,dimName) that are linked to this component, dim.
        """
        linked = []
        for c in self.iterComponents():
            for dimName, val in c.p.items():
                if c.dimensionIsLinked(dimName):
                    requiredComponent = val[0]
                    if requiredComponent is comp and val[1] == dim:
                        linked.append((c, dimName))
        return linked

    def getComponentsInLinkedOrder(self, componentList=None):
        """
        Return a list of the components in order of their linked-dimension dependencies.

        Parameters
        ----------
        components : list, optional
            A list of components to consider. If None, this block's components will be used.

        Notes
        -----
        This means that components other components are linked to come first.
        """
        if componentList is None:
            componentList = self.getComponents()
        cList = collections.deque(componentList)
        orderedComponents = []
        # Loop through the components until there are none left.
        counter = 0
        while cList:
            candidate = cList.popleft()  # take first item in list
            cleared = True  # innocent until proven guilty
            # loop through all dimensions in this component to determine its dependencies
            for dimName, val in candidate.p.items():
                if candidate.dimensionIsLinked(dimName):
                    # In linked dimensions, val = (component, dimName)
                    requiredComponent = val[0]
                    if requiredComponent not in orderedComponents:
                        # this component depends on one that is not in the ordered list yet.
                        # do not add it.
                        cleared = False
                        break  # short circuit. One failed lookup is enough to flag this component as dirty.
            if cleared:
                # this candidate is free of dependencies and is ready to be added.
                orderedComponents.append(candidate)
            else:
                cList.append(candidate)

            counter += 1
            if counter > 1000:
                cList.append(candidate)
                runLog.error(
                    "The component {0} in {1} contains a dimension that is linked to another component, "
                    " but the required component is not present in the block. They may also be other dependency fails. "
                    "The component dims are {2}".format(cList[0], self, cList[0].p)
                )
                raise RuntimeError("Cannot locate linked component.")
        return orderedComponents

    def getSortedComponentsInsideOfComponent(self, component):
        """
        Returns a list of components inside of the given component sorted from innermost to outermost.

        Parameters
        ----------
        component : object
            Component to look inside of.

        Notes
        -----
        If you just want sorted components in this block, use ``sorted(self)``. This will never
        include any ``DerivedShape`` objects. Since they have a derived area they don't have a well-
        defined dimension. For now we just ignore them. If they are desired in the future some
        knowledge of their dimension will be required while they are being derived.
        """
        sortedComponents = sorted(self)
        componentIndex = sortedComponents.index(component)
        sortedComponents = sortedComponents[:componentIndex]
        return sortedComponents

    def getNumPins(self):
        """Return the number of pins in this block.

        .. impl:: Get the number of pins in a block.
            :id: I_ARMI_BLOCK_NPINS
            :implements: R_ARMI_BLOCK_NPINS

            Uses some simple criteria to infer the number of pins in the block.

            For every flag in the module list :py:data:`~armi.reactor.blocks.PIN_COMPONENTS`, loop
            over all components of that type in the block. If the component is an instance of
            :py:class:`~armi.reactor.components.basicShapes.Circle`, add its multiplicity to a list,
            and sum that list over all components with each given flag.

            After looping over all possibilities, return the maximum value returned from the process
            above, or if no compatible components were found, return zero.
        """
        nPins = [
            sum(
                [
                    (int(c.getDimension("mult")) if isinstance(c, basicShapes.Circle) else 0)
                    for c in self.iterComponents(compType)
                ]
            )
            for compType in PIN_COMPONENTS
        ]
        return 0 if not nPins else max(nPins)

    def mergeWithBlock(self, otherBlock, fraction):
        """
        Turns this block into a mixture of this block and some other block.

        Parameters
        ----------
        otherBlock : Block
            The block to mix this block with. The other block will not be modified.

        fraction : float
            Fraction of the other block to mix in with this block. If 0.1 is passed in, this block
            will become 90% what it originally was and 10% what the other block is.

        Notes
        -----
        This merges on a high level (using number densities). Components will not be merged.

        This is used e.g. for inserting a control block partially to get a very tight criticality
        control. In this case, a control block would be merged with a duct block. It is also used
        when a control rod is specified as a certain length but that length does not fit exactly
        into a full block.
        """
        numDensities = self.getNumberDensities()
        otherBlockDensities = otherBlock.getNumberDensities()
        newDensities = {}

        # Make sure to hit all nuclides in union of blocks
        for nucName in set(numDensities.keys()).union(otherBlockDensities.keys()):
            newDensities[nucName] = (1.0 - fraction) * numDensities.get(
                nucName, 0.0
            ) + fraction * otherBlockDensities.get(nucName, 0.0)

        self.setNumberDensities(newDensities)

    def getComponentAreaFrac(self, typeSpec):
        """
        Returns the area fraction of the specified component(s) among all components in the block.

        Parameters
        ----------
        typeSpec : Flags or list of Flags
            Component types to look up

        Examples
        --------
        >>> b.getComponentAreaFrac(Flags.CLAD)
        0.15

        Returns
        -------
        float
            The area fraction of the component.
        """
        tFrac = sum(f for (c, f) in self.getVolumeFractions() if c.hasFlags(typeSpec))

        if tFrac:
            return tFrac
        else:
            runLog.warning(
                f"No component {typeSpec} exists on {self}, so area fraction is zero.",
                single=True,
                label=f"{typeSpec} areaFrac is zero",
            )
            return 0.0

    def verifyBlockDims(self):
        """Optional dimension checking."""
        return

    def getDim(self, typeSpec, dimName):
        """
        Search through blocks in this assembly and find the first component of compName.
        Then, look on that component for dimName.

        Parameters
        ----------
        typeSpec : Flags or list of Flags
            Component name, e.g. Flags.FUEL, Flags.CLAD, Flags.COOLANT, ...
        dimName : str
            Dimension name, e.g. 'od', ...

        Returns
        -------
        dimVal : float
            The dimension in cm.

        Examples
        --------
        >>> getDim(Flags.WIRE, "od")
        0.01
        """
        for c in self:
            if c.hasFlags(typeSpec):
                return c.getDimension(dimName.lower())

        raise ValueError(f"Cannot get Dimension because Flag not found: {typeSpec}")

    def getPinCenterFlatToFlat(self, cold=False):
        """Return the flat-to-flat distance between the centers of opposing pins in the outermost ring."""
        raise NotImplementedError  # no geometry can be assumed

    def getWireWrapCladGap(self, cold=False):
        """Return the gap between the wire wrap and the clad."""
        clad = self.getComponent(Flags.CLAD)
        wire = self.getComponent(Flags.WIRE)
        wireOuterRadius = wire.getBoundingCircleOuterDiameter(cold=cold) / 2.0
        wireInnerRadius = wireOuterRadius - wire.getDimension("od", cold=cold)
        cladOuterRadius = clad.getDimension("od", cold=cold) / 2.0
        return wireInnerRadius - cladOuterRadius

    def getPlenumPin(self):
        """Return the plenum pin if it exists."""
        for c in self.iterComponents(Flags.GAP):
            if self.isPlenumPin(c):
                return c
        return None

    def isPlenumPin(self, c):
        """Return True if the specified component is a plenum pin."""
        # This assumes that anything with the GAP flag will have a valid 'id' dimension.
        cIsCenterGapGap = isinstance(c, components.Component) and c.hasFlags(Flags.GAP) and c.getDimension("id") == 0
        return self.hasFlags([Flags.PLENUM, Flags.ACLP]) and cIsCenterGapGap

    def getPitch(self, returnComp=False):
        """
        Return the center-to-center hex pitch of this block.

        Parameters
        ----------
        returnComp : bool, optional
            If true, will return the component that has the maximum pitch as well

        Returns
        -------
        pitch : float or None
            Hex pitch in cm, if well-defined. If there is no clear component for determining pitch, returns None
        component : Component or None
            Component that has the max pitch, if returnComp == True. If no component is found to define the pitch,
            returns None.

        Notes
        -----
        The block stores a reference to the component that defines the pitch, making the assumption that while the
        dimensions can change, the component containing the largest dimension will not. This lets us skip the search for
        largest component. We still need to ask the largest component for its current dimension in case its temperature
        changed, or was otherwise modified.

        See Also
        --------
        setPitch : sets pitch
        """
        c, _p = self._pitchDefiningComponent
        if c is None:
            raise ValueError("{} has no valid pitch defining component".format(self))

        # ask component for dimensions, since they could have changed due to temperature
        p = c.getPitchData()
        return (p, c) if returnComp else p

    def hasPinPitch(self):
        """Return True if the block has enough information to calculate pin pitch."""
        return self.spatialGrid is not None

    def getPinPitch(self, cold=False):
        """
        Return sub-block pitch in blocks.

        This assumes the spatial grid is defined by unit steps
        """
        return self.spatialGrid.pitch

    def getDimensions(self, dimension):
        """Return dimensional values of the specified dimension."""
        dimVals = set()
        for c in self:
            try:
                dimVal = c.getDimension(dimension)
            except parameters.ParameterError:
                continue
            if dimVal is not None:
                dimVals.add(dimVal)
        return dimVals

    def getLargestComponent(self, dimension):
        """
        Find the component with the largest dimension of the specified type.

        Parameters
        ----------
        dimension: str
            The name of the dimension to find the largest component of.

        Returns
        -------
        largestComponent: armi.reactor.components.Component
            The component with the largest dimension of the specified type.
        """
        maxDim = -float("inf")
        largestComponent = None
        for c in self:
            try:
                dimVal = c.getDimension(dimension)
            except parameters.ParameterError:
                continue
            if dimVal is not None and dimVal > maxDim:
                maxDim = dimVal
                largestComponent = c
        return largestComponent

    def setPitch(self, val, updateBolParams=False):
        """
        Sets outer pitch to some new value.

        This sets the settingPitch and actually sets the dimension of the outer hexagon.

        During a load (importGeom), the setDimension doesn't usually do anything except set the
        setting See Issue 034

        But during a actual case modification (e.g. in an optimization sweep, then the dimension has
        to be set as well.

        See Also
        --------
        getPitch : gets the pitch
        """
        c, _p = self._pitchDefiningComponent
        if c:
            c.setDimension("op", val)
            self._pitchDefiningComponent = (c, val)
        else:
            raise RuntimeError("No pitch-defining component on block {}".format(self))

        if updateBolParams:
            self.completeInitialLoading()

    def getMfp(self, gamma=False):
        r"""
        Calculate the mean free path for neutron or gammas in this block.

        .. math::

            <\Sigma> = \frac{\sum_E(\phi_e \Sigma_e dE)}{\sum_E (\phi_e dE)}  =
            \frac{\sum_E(\phi_e N \sum_{\text{type}}(\sigma_e)  dE}{\sum_E (\phi_e dE))}

        Block macro is the sum of macros of all nuclides.

        phi_g = flux*dE already in multigroup method.

        Returns
        -------
        mfp, mfpAbs, diffusionLength : tuple(float, float float)
        """
        lib = self.core.lib
        flux = self.getMgFlux(gamma=gamma)
        flux = [fi / max(flux) for fi in flux]
        mfpNumerator = np.zeros(len(flux))
        absMfpNumerator = np.zeros(len(flux))
        transportNumerator = np.zeros(len(flux))

        numDensities = self.getNumberDensities()

        for nucName, nDen in numDensities.items():
            nucMc = self.nuclideBases.byName[nucName].label + self.getMicroSuffix()
            if gamma:
                micros = lib[nucMc].gammaXS
            else:
                micros = lib[nucMc].micros
            total = micros.total[:, 0]  # 0th order
            transport = micros.transport[:, 0]  # 0th order, [bn]
            absorb = sum(micros.getAbsorptionXS())
            mfpNumerator += nDen * total  # [cm]
            absMfpNumerator += nDen * absorb
            transportNumerator += nDen * transport

        denom = sum(flux)
        mfp = 1.0 / (sum(mfpNumerator * flux) / denom)
        sigmaA = sum(absMfpNumerator * flux) / denom
        sigmaTr = sum(transportNumerator * flux) / denom
        diffusionCoeff = 1 / (3.0 * sigmaTr)
        mfpAbs = 1 / sigmaA
        diffusionLength = math.sqrt(diffusionCoeff / sigmaA)
        return mfp, mfpAbs, diffusionLength

    def setAreaFractionsReport(self):
        for c, frac in self.getVolumeFractions():
            report.setData(
                c.getName(),
                ["{0:10f}".format(c.getArea()), "{0:10f}".format(frac)],
                report.BLOCK_AREA_FRACS,
            )

        # return the group the information went to
        return report.ALL[report.BLOCK_AREA_FRACS]

    def getBlocks(self):
        """
        This method returns all the block(s) included in this block its implemented so that methods
        could iterate over reactors, assemblies or single blocks without checking to see what the
        type of the reactor-family object is.
        """
        return [self]

    def updateComponentDims(self):
        """
        This method updates all the dimensions of the components.

        Notes
        -----
        This is VERY useful for defining a ThRZ core out of differentialRadialSegements whose
        dimensions are connected together some of these dimensions are derivative and can be updated
        by changing dimensions in a Parameter Component or other linked components

        See Also
        --------
        armi.reactor.components.DifferentialRadialSegment.updateDims
        armi.reactor.components.Parameters
        armi.physics.optimize.OptimizationInterface.modifyCase (look up 'ThRZReflectorThickness')
        """
        for c in self.getComponentsInLinkedOrder():
            try:
                c.updateDims()
            except NotImplementedError:
                runLog.warning("{0} has no updatedDims method -- skipping".format(c))

    def getIntegratedMgFlux(self, adjoint=False, gamma=False):
        """
        Return the volume integrated multigroup neutron tracklength in [n-cm/s].

        The first entry is the first energy group (fastest neutrons). Each additional group is the
        next energy group, as set in the ISOTXS library.

        Parameters
        ----------
        adjoint : bool, optional
            Return adjoint flux instead of real

        gamma : bool, optional
            Whether to return the neutron flux or the gamma flux.

        Returns
        -------
        integratedFlux : np.ndarray
            multigroup neutron tracklength in [n-cm/s]
        """
        if adjoint:
            if gamma:
                raise ValueError("Adjoint gamma flux is currently unsupported.")
            integratedFlux = self.p.adjMgFlux
        elif gamma:
            integratedFlux = self.p.mgFluxGamma
        else:
            integratedFlux = self.p.mgFlux

        return np.array(integratedFlux)

    def getLumpedFissionProductCollection(self):
        """
        Get collection of LFP objects. Will work for global or block-level LFP models.

        Returns
        -------
        lfps : LumpedFissionProduct
            lfpName keys , lfp object values

        See Also
        --------
        armi.physics.neutronics.fissionProductModel.lumpedFissionProduct.LumpedFissionProduct : LFP object
        """
        return composites.ArmiObject.getLumpedFissionProductCollection(self)

    def rotate(self, rad):
        """Function for rotating a block's spatially varying variables by a specified angle (radians).

        Parameters
        ----------
        rad: float
            Number (in radians) specifying the angle of counter clockwise rotation.
        """
        raise NotImplementedError

    def setAxialExpTargetComp(self, targetComponent):
        """Sets the targetComponent for the axial expansion changer.

        .. impl:: Set the target axial expansion components on a given block.
            :id: I_ARMI_MANUAL_TARG_COMP
            :implements: R_ARMI_MANUAL_TARG_COMP

            Sets the ``axialExpTargetComponent`` parameter on the block to the name of the Component
            which is passed in. This is then used by the
            :py:class:`~armi.reactor.converters.axialExpansionChanger.AxialExpansionChanger`
            class during axial expansion.

            This method is typically called from within
            :py:meth:`~armi.reactor.blueprints.blockBlueprint.BlockBlueprint.construct` during the
            process of building a Block from the blueprints.

        Parameter
        ---------
        targetComponent: :py:class:`Component <armi.reactor.components.component.Component>` object
            Component specified to be target component for axial expansion changer
        """
        self.p.axialExpTargetComponent = targetComponent.name

    def getPinLocations(self) -> list[grids.IndexLocation]:
        """Produce all the index locations for pins in the block.

        Returns
        -------
        list[grids.IndexLocation]
            Integer locations where pins can be found in the block.

        Notes
        -----
        Only components with ``Flags.CLAD`` are considered to define a pin's location.

        See Also
        --------
        :meth:`getPinCoordinates` - companion for this method.
        """
        items = []
        for clad in self.iterChildrenWithFlags(Flags.CLAD):
            if isinstance(clad.spatialLocator, grids.MultiIndexLocation):
                items.extend(clad.spatialLocator)
            else:
                items.append(clad.spatialLocator)
        return items

    def getPinCoordinates(self) -> np.ndarray:
        """
        Compute the local centroid coordinates of any pins in this block.

        The pins must have a CLAD-flagged component for this to work.

        Returns
        -------
        localCoords : numpy.ndarray
            ``(N, 3)`` array of coordinates for pins locations. ``localCoords[i]`` contains a triplet of
            the x, y, z location for pin ``i``. Ordered according to how they are listed as children

        See Also
        --------
        :meth:`getPinLocations` - companion for this method
        """
        indices = self.getPinLocations()
        coords = [location.getLocalCoordinates() for location in indices]
        return np.array(coords)

    def getTotalEnergyGenerationConstants(self):
        """
        Get the total energy generation group constants for a block.

        Gives the total energy generation rates when multiplied by the multigroup flux.

        Returns
        -------
        totalEnergyGenConstant: np.ndarray
            Total (fission + capture) energy generation group constants (Joules/cm)
        """
        return self.getFissionEnergyGenerationConstants() + self.getCaptureEnergyGenerationConstants()

    def getFissionEnergyGenerationConstants(self):
        """
        Get the fission energy generation group constants for a block.

        Gives the fission energy generation rates when multiplied by the multigroup flux.

        Returns
        -------
        fissionEnergyGenConstant: np.ndarray
            Energy generation group constants (Joules/cm)

        Raises
        ------
        RuntimeError:
            Reports if a cross section library is not assigned to a reactor.
        """
        if not self.core.lib:
            raise RuntimeError(
                "Cannot compute energy generation group constants without a library. Please ensure a library exists."
            )

        return xsCollections.computeFissionEnergyGenerationConstants(
            self.getNumberDensities(), self.core.lib, self.getMicroSuffix()
        )

    def getCaptureEnergyGenerationConstants(self):
        """
        Get the capture energy generation group constants for a block.

        Gives the capture energy generation rates when multiplied by the multigroup flux.

        Returns
        -------
        fissionEnergyGenConstant: np.ndarray
            Energy generation group constants (Joules/cm)

        Raises
        ------
        RuntimeError:
            Reports if a cross section library is not assigned to a reactor.
        """
        if not self.core.lib:
            raise RuntimeError(
                "Cannot compute energy generation group constants without a library. Please ensure a library exists."
            )

        return xsCollections.computeCaptureEnergyGenerationConstants(
            self.getNumberDensities(), self.core.lib, self.getMicroSuffix()
        )

    def getNeutronEnergyDepositionConstants(self):
        """
        Get the neutron energy deposition group constants for a block.

        Returns
        -------
        energyDepConstants: np.ndarray
            Neutron energy generation group constants (in Joules/cm)

        Raises
        ------
        RuntimeError:
            Reports if a cross section library is not assigned to a reactor.
        """
        if not self.core.lib:
            raise RuntimeError(
                "Cannot get neutron energy deposition group constants without "
                "a library. Please ensure a library exists."
            )

        return xsCollections.computeNeutronEnergyDepositionConstants(
            self.getNumberDensities(), self.core.lib, self.getMicroSuffix()
        )

    def getGammaEnergyDepositionConstants(self):
        """
        Get the gamma energy deposition group constants for a block.

        Returns
        -------
        energyDepConstants: np.ndarray
            Energy generation group constants (in Joules/cm)

        Raises
        ------
        RuntimeError:
            Reports if a cross section library is not assigned to a reactor.
        """
        if not self.core.lib:
            raise RuntimeError(
                "Cannot get gamma energy deposition group constants without a library. Please ensure a library exists."
            )

        return xsCollections.computeGammaEnergyDepositionConstants(
            self.getNumberDensities(), self.core.lib, self.getMicroSuffix()
        )

    def getBoronMassEnrich(self):
        """Return B-10 mass fraction."""
        b10 = self.getMass("B10")
        b11 = self.getMass("B11")
        total = b11 + b10
        if total == 0.0:
            return 0.0
        return b10 / total

    def getUraniumMassEnrich(self):
        """Returns fissile mass fraction of uranium."""
        totalU = self.getMass("U")
        if totalU < 1e-10:
            return 0.0

        fissileU = self.getMass(["U233", "U235"])
        return fissileU / totalU

    def getInputHeight(self) -> float:
        """Determine the input height from blueprints.

        Returns
        -------
        float
            Height for this block pulled from the blueprints.

        Raises
        ------
        AttributeError
            If no ancestor of this block contains the input blueprints. Blueprints are usually
            stored on the reactor object, which is typically an ancestor of the block
            (block -> assembly -> core -> reactor). However, this may be the case when creating
            blocks from scratch in testing where the entire composite tree may not exist.
        """
        ancestorWithBp = self.getAncestor(lambda o: getattr(o, "blueprints", None) is not None)
        if ancestorWithBp is not None:
            bp = ancestorWithBp.blueprints
            assemDesign = bp.assemDesigns[self.parent.getType()]
            heights = assemDesign.height
            myIndex = self.parent.index(self)
            return heights[myIndex]

        raise AttributeError(f"No ancestor of {self} has blueprints")

    def sort(self):
        """Sort the children on this block.

        If there is a spatial grid, the previous pin indices on the components
        is now invalid because the ordering of :meth:`getPinLocations` has maybe
        changed since the ordering of components has changed. Reassign the pin
        indices via :meth:`assignPinIndices` accordingly.
        """
        super().sort()
        if self.spatialGrid is not None:
            self.assignPinIndices()
