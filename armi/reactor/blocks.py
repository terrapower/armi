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
Defines blocks, which are axial chunks of assemblies. They contain
most of the state variables, including power, flux, and homogenized number densities.

Assemblies are made of blocks.

Blocks are made of components.
"""
import math
import copy
import collections
import os
from typing import Optional, Type, Tuple, ClassVar

import matplotlib.pyplot as plt
import numpy

from armi.reactor import composites
from armi import runLog
from armi import settings
from armi.nucDirectory import nucDir, nuclideBases
from armi.reactor import locations
from armi.reactor import geometry
from armi.reactor.locations import AXIAL_CHARS
from armi.reactor import parameters
from armi.reactor import blockParameters
from armi.reactor import grids
from armi.reactor.flags import Flags
from armi.reactor import components
from armi.utils import units
from armi.bookkeeping import report
from armi.physics import constants
from armi.utils.units import TRACE_NUMBER_DENSITY
from armi.utils.densityTools import calculateNumberDensity
from armi.utils import hexagon
from armi.utils import densityTools
from armi.physics.neutronics import NEUTRON
from armi.physics.neutronics import GAMMA

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
    A homogenized axial slab of material.

    Blocks are stacked together to form assemblies.
    """

    # nuclides that will be put in A.NIP3 but not A.bURN (these will not deplete!)
    inerts = []
    uniqID = 0

    # dimension used to determine which component defines the block's pitch
    PITCH_DIMENSION = "op"

    # component type that can be considered a candidate for providing pitch
    PITCH_COMPONENT_TYPE: ClassVar[_PitchDefiningComponent] = None

    # armi.reactor.locations.Location subclass, overridden on Block subclasses
    LOCATION_CLASS: Optional[Type[locations.Location]] = None

    pDefs = blockParameters.getBlockParameterDefinitions()

    def __init__(self, name, height=1.0, location=None):
        """
        Builds a new ARMI block

        caseSettings : Settings object, optional
            The settings object to use to build the block

        name : str, optional
            The name of this block

        height : float, optional
            The height of the block in cm. Defaults to 1.0 so that
            `getVolume` assumes unit height.
        """
        composites.Composite.__init__(self, name)
        self.makeUnique()
        self.p.height = height

        if location:
            k = location.axial
            self.spatialLocator = grids.IndexLocation(0, 0, k, None)
        self.p.orientation = numpy.array((0.0, 0.0, 0.0))

        self.nuclides = (
            []
        )  # TODO: list of nuclides present in this block (why not just density.keys()?)
        self.points = []
        self.macros = None

        self.numLfpLast = {}  # for FGremoval
        self.history = []  # memory of shuffle locations
        self.lastkInf = 0.0  # for tracking k-inf vs. time slope.

        # flag to indicated when DerivedShape children must be updated.
        self.derivedMustUpdate = False

        # which component to use to determine block pitch, along with its 'op'
        self._pitchDefiningComponent = (None, 0.0)

        # TODO: what's causing these to have wrong values at BOL?
        for problemParam in ["THcornTemp", "THedgeTemp"]:
            self.p[problemParam] = []
        for problemParam in [
            "residence",
            "bondRemoved",
            "fluence",
            "fastFluence",
            "fastFluencePeak",
            "displacementX",
            "displacementY",
            "fluxAdj",
            "bu",
            "buRate",
            "eqRegion",
            "fissileFraction",
        ]:
            self.p[problemParam] = 0.0

    def __repr__(self):
        # be warned, changing this might break unit tests on input file generations
        return "<{type} {name} at {loc} XS: {xs} BU GP: {bu}>".format(
            type=self.getType(),
            name=self.getName(),
            xs=self.p.xsType,
            bu=self.p.buGroup,
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

    @property
    def core(self):
        from armi.reactor.reactors import Core

        c = self.getAncestor(lambda c: isinstance(c, Core))
        return c

    @property
    def r(self):
        """
        A block should only have a reactor through a parent assembly.

        It may make sense to try to factor out usage of ``b.r``.

        For now, this is presumptive of the structure of the composite hierarchy; i.e.
        the parent of a CORE must be the reactor. Fortunately, we probably don't
        ultimately want to return the reactor in the first place. Rather, we probably want the core
        anyways, since practically all `b.r` calls are historically `b.r.core`. It may be
        prefereable to remove this property, replace with `self.core`, which can return the core.
        Then refactor all of the b.r.cores, to b.core.
        """

        from armi.reactor.reactors import Reactor

        core = self.core
        if core is None:
            return None

        if not isinstance(core.parent, Reactor):
            raise TypeError(
                "Parent of Block ({}) core is not a Reactor. Got {} instead".format(
                    core.parent, type(core.parent)
                )
            )

        return core.parent

    @property
    def location(self):
        """
        Patch to keep code working while location system is refactored to use spatialLocators.

        Just creates a new location object based on current spatialLocator.
        """
        return self.getLocationObject()

    @location.setter
    def location(self, value):
        """
        Set spatialLocator based on a (old-style) location object.

        Patch to keep code working while location system is refactored to use spatialLocators.

        Blocks only have 1-D grid info so we only look at the axial portion.
        """
        k = value.axial
        self.spatialLocator = self.parent.spatialGrid[0, 0, k]

    def makeName(self, assemNum, axialIndex):
        """
        Generate a standard block from assembly number.

        This also sets the block-level assembly-num param.

        Examples
        --------
        >>> makeName(120, 5)
        'B0120E'
        """
        self.p.assemNum = assemNum
        return "B{0:04d}{1}".format(assemNum, AXIAL_CHARS[axialIndex])

    def makeUnique(self):
        """
        Assign a unique id (integer value) for each block.

        This should be called whenever creating a block that is intended to be treated
        as a unique object. For example, if you were to broadcast or pickle a block it
        should have the same ID across all nodes. Likewise, if you deepcopy a block for
        a temporary purpose to it should have the same ID.  However, ARMI's assembly
        construction also uses deepcopy, and in order to keep that functionality, this
        method needs to be called after creating a fresh assembly (from deepcopy).
        """

        self.p.id = self.__class__.uniqID
        self.__class__.uniqID += 1

    def getSmearDensity(self, cold=True):
        """
        Compute the smear density of this block.

        Notes
        -----
        1 - Smear density is the area of the fuel divided by the area of the space
            available for fuel inside the cladding. Other space filled with solid
            materials is not considered available. If all the area is fuel, it has 100%
            smear density. Lower smear density allows more room for swelling.
        2 - Negative areas can exist for void gaps in the fuel pin. A negative area in a
            gap represents overlap area between two solid components. To account for
            this additional space within the pin cladding the abs(negativeArea) is added
            to the inner cladding area.

        Parameters
        -----------
        cold : bool, optional
            If false, returns the smear density at hot temperatures

        Returns
        -------
        smearDensity : float
            The smear density as a fraction

        """
        fuels = self.getComponents(Flags.FUEL)
        if not fuels:
            return 0.0  # Smear density is not computed for non-fuel blocks

        if not self.getComponentsOfShape(components.Circle):
            raise ValueError(
                "Cannot get smear density of {}. There are no circular components.".format(
                    self
                )
            )
        clads = self.getComponents(Flags.CLAD)
        if not clads:
            raise ValueError(
                "Cannot get smear density of {}. There are no clad components.".format(
                    self
                )
            )

        # Compute component areas
        cladID = numpy.mean([clad.getDimension("id", cold=cold) for clad in clads])
        innerCladdingArea = (
            math.pi * (cladID ** 2) / 4.0 * self.getNumComponents(Flags.FUEL)
        )
        fuelComponentArea = 0.0
        unmovableComponentArea = 0.0
        negativeArea = 0.0
        for c in self.getSortedComponentsInsideOfComponent(clads[0]):
            componentArea = c.getArea(cold=cold)
            if c.isFuel():
                fuelComponentArea += componentArea
            elif c.hasFlags(Flags.SLUG):
                # this flag designates that this clad/slug combination isn't fuel and shouldn't be counted in the average
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
                "Negative component areas exist on {}. Check that the cold dimensions are properly aligned "
                "and no components overlap.".format(self)
            )
        innerCladdingArea += negativeArea  # See note 2
        totalMovableArea = innerCladdingArea - unmovableComponentArea
        smearDensity = fuelComponentArea / totalMovableArea

        return smearDensity

    def getTemperature(self, key, sigma=0):
        """
        Return the best temperature for key in degrees C.

        Uses thInterface values if they exist

        Parameters
        ----------
        key : str
            a key identifying the object we want the temperature of. Options include
            cladOD, cladID,

        sigma : int
            Specification of which sigma-value we want. 0-sigma is nominal, 1-sigma is + 1 std.dev, etc.

        Returns
        -------
        tempInC : float
            temperature in C

        SingleWarnings will be issued if a non-zero sigma value is requested but does not exist.
        Nominal Thermo values will be returned in that case.
        """

        if key == "cladOD":
            options = ["TH{0}SigmaCladODT".format(sigma), "TH0SigmaCladODT"]
        elif key == "cladID":
            options = ["TH{0}SigmaCladIDT".format(sigma), "TH0SigmaCladIDT"]

        # return the first non-zero value
        for okey in options:
            tempInC = self.p[okey]
            if not tempInC and "Sigma" in okey and sigma > 0:
                runLog.warning(
                    "No {0}-sigma temperature available for {1}. Run subchan. Returning nominal"
                    "".format(sigma, self),
                    single=True,
                    label="no {0}-sigma temperature".format(sigma),
                )
            if tempInC:
                break
        else:
            raise ValueError(
                "{} has no non-zero {}-sigma {} temperature. Check T/H results.".format(
                    self, sigma, key
                )
            )

        return tempInC

    def getEnrichment(self):
        """
        Return the mass enrichment of the fuel in the block.

        If multiple fuel components exist, this returns the average enrichment.
        """
        enrichment = 0.0
        if self.hasFlags(Flags.FUEL):
            fuels = self.getComponents(Flags.FUEL)
            if len(fuels) == 1:
                # short circuit to avoid expensive mass read.
                return fuels[0].getMassEnrichment()
            hm = 0.0
            fissile = 0.0
            for c in fuels:
                hmMass = c.getHMMass()
                fissile += c.getMassEnrichment() * hmMass
                hm += hmMass
            enrichment = fissile / hm
        return enrichment

    def getMgFlux(self, adjoint=False, average=False, volume=None, gamma=False):
        """
        Returns the multigroup neutron flux in [n/cm^2/s]

        The first entry is the first energy group (fastest neutrons). Each additional
        group is the next energy group, as set in the ISOTXS library.

        It is stored integrated over volume on self.p.mgFlux

        Parameters
        ----------
        adjoint : bool, optional
            Return adjoint flux instead of real

        average : bool, optional
            If true, will return average flux between latest and previous. Doesn't work
            for pin detailed yet

        volume: float, optional
            If average=True, the volume-integrated flux is divided by volume before being returned.
            The user may specify a volume here, or the function will obtain the block volume directly.

        gamma : bool, optional
            Whether to return the neutron flux or the gamma flux.

        Returns
        -------
        flux : multigroup neutron flux in [n/cm^2/s]
        """
        flux = composites.ArmiObject.getMgFlux(
            self, adjoint=adjoint, average=False, volume=volume, gamma=gamma
        )
        if average and numpy.any(self.p.lastMgFlux):
            volume = volume or self.getVolume()
            lastFlux = self.p.lastMgFlux / volume
            flux = (flux + lastFlux) / 2.0
        return flux

    def setPinMgFluxes(self, fluxes, numPins, adjoint=False, gamma=False):
        """
        Store the pin-detailed multi-group neutron flux

        The [g][i] indexing is transposed to be a list of lists, one for each pin. This makes it
        simple to do depletion for each pin, etc.

        Parameters
        ----------
        fluxes : 2-D list of floats
            The block-level pin multigroup fluxes. fluxes[g][i] represents the flux in group g for pin i.
            Flux units are the standard n/cm^2/s.
            The "ARMI pin ordering" is used, which is counter-clockwise from 3 o'clock.

        numPins : int
            The number of pins in this block.

        adjoint : bool, optional
            Whether to set real or adjoint data.

        gamma : bool, optional
            Whether to set gamma or neutron data.

        Outputs
        -------
        self.p.pinMgFluxes : 2-D array of floats
            The block-level pin multigroup fluxes. pinMgFluxes[g][i] represents the flux in group g for pin i.
            Flux units are the standard n/cm^2/s.
            The "ARMI pin ordering" is used, which is counter-clockwise from 3 o'clock.
        """
        pinFluxes = []

        G, nPins = fluxes.shape

        for pinNum in range(1, nPins + 1):
            thisPinFlux = []

            if self.hasFlags(Flags.FUEL):
                pinLoc = self.p.pinLocation[pinNum - 1]
            else:
                pinLoc = pinNum

            for g in range(G):
                thisPinFlux.append(fluxes[g][pinLoc - 1])
            pinFluxes.append(thisPinFlux)

        pinFluxes = numpy.array(pinFluxes)
        if gamma:
            if adjoint:
                raise ValueError("Adjoint gamma flux is currently unsupported.")
            else:
                self.p.pinMgFluxesGamma = pinFluxes
        else:
            if adjoint:
                self.p.pinMgFluxesAdj = pinFluxes
            else:
                self.p.pinMgFluxes = pinFluxes

    def getPowerPinName(self):
        """
        Determine the component name where the power is being produced.

        Returns
        -------
        powerPin : str
            The name of the pin that is producing power, if any. could be 'fuel' or 'control', or
            anything else.

        Notes
        -----
        If there is fuel and control, this will return fuel based on hard-coded priorities.

        Examples
        --------
        >>> b.getPowerPinName()
        'fuel'

        >>> b.getPowerPinName()
        'control'

        >>> b.getPowerPinName()
        None

        """

        for candidate in [Flags.FUEL, Flags.CONTROL]:
            if self.getComponent(candidate):
                return candidate

    def getMicroSuffix(self):
        """
        Returns the microscopic library suffix (e.g. 'AB') for this block.

        DIF3D and MC2 are limited to 6 character nuclide labels. ARMI by convention uses
        the first 4 for nuclide name (e.g. U235, PU39, etc.) and then uses the 5th
        character for cross-section type and the 6th for burnup group. This allows a
        variety of XS sets to be built modeling substantially different blocks.

        Notes
        -----
        The single-letter use for xsType and buGroup limit users to 26 groups of each.
        ARMI will allow 2-letter xsType designations if and only if the `buGroups`
        setting has length 1 (i.e. no burnup groups are defined). This is useful for
        high-fidelity XS modeling of V&V models such as the ZPPRs.
        """

        bu = self.p.buGroup
        if not bu:
            raise RuntimeError(
                "Cannot get MicroXS suffix because {0} in {1} does not have a burnup group"
                "".format(self, self.parent)
            )
        xsType = self.p.xsType
        if len(xsType) == 2 and len(settings.getMasterCs()["buGroups"]) == 1:
            return xsType
        else:
            return xsType + bu

    def setNumberDensity(self, nucName, newHomogNDens):
        """
        Adds an isotope to the material or changes an existing isotope's number density

        Parameters
        ----------
        nuc : str
            a nuclide name like U235, PU240, FE
        newHomogNDens : float
            number density to set in units of atoms/barn-cm, which are equal to
            atoms/cm^3*1e24

        See Also
        --------
        getNumberDensity : gets the density of a nuclide
        """
        composites.Composite.setNumberDensity(self, nucName, newHomogNDens)
        self.setNDensParam(nucName, newHomogNDens)

    def setNumberDensities(self, numberDensities):
        """
        Update number densities.

        Any nuclide in the block but not in numberDensities will be set to zero.

        Special behavior for blocks: update block-level params for DB viewing/loading.
        """
        composites.Composite.setNumberDensities(self, numberDensities)
        for nucName in self.getNuclides():
            # make sure to clear out any non-listed number densities
            self.setNDensParam(nucName, numberDensities.get(nucName, 0.0))

    def updateNumberDensities(self, numberDensities):
        """Set one or more multiple number densities. Leaves unlisted number densities alone."""
        composites.Composite.updateNumberDensities(self, numberDensities)
        for nucName, ndens in numberDensities.items():
            self.setNDensParam(nucName, ndens)

    def setNDensParam(self, nucName, ndens):
        """
        Set a block-level param with the homog. number density of a nuclide.

        This can be read by the database in restart runs.
        """
        n = nuclideBases.byName[nucName]
        self.p[n.getDatabaseName()] = ndens

    def setMass(self, nucName, mass, **kwargs):
        """
        Sets the mass in a block and adjusts the density of the nuclides in the block.

        Parameters
        ----------
        nucName : str
            Nuclide name to set mass of
        mass : float
            Mass in grams to set.

        """
        d = calculateNumberDensity(nucName, mass, self.getVolume())
        self.setNumberDensity(nucName, d)

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
            Nuclides that will be conserved in conserving mass in the block. It is recommended to pass a list of
            all nuclides in the block.

        Notes
        -----
        There is a coupling between block heights, the parent assembly axial mesh,
        and the ztop/zbottom/z params of the sibling blocks. When you set a height,
        all those things are invalidated. Thus, this method has to go through and
        update them via ``parent.calculateZCoords``. This could be inefficient
        though it has not been identified as a bottleneck. Possible improvements
        include deriving z/ztop/zbottom on the fly and invalidating the parent mesh
        with some kind of flag, signaling it to recompute itself on demand.
        Developers can get around some of the O(N^2) scaling of this by setting
        ``p.height`` directly but they must know to update the dependent objects
        after they do that. Use with care.

        See Also
        --------
        reactors.Core.updateAxialMesh : May need to be called after this.
        assemblies.Assembly.calculateZCoords : Recalculates z-coords, automatically called by this.
        """
        originalHeight = self.getHeight()  # get before modifying
        if modifiedHeight <= 0.0:
            raise ValueError(
                "Cannot set height of block {} to height of {} cm".format(
                    self, modifiedHeight
                )
            )
        self.p.height = modifiedHeight
        self.clearCache()
        if conserveMass:
            if originalHeight != modifiedHeight:
                if not adjustList:
                    raise ValueError(
                        "Nuclides in ``adjustList`` must be provided to conserve mass."
                    )
                self.adjustDensity(originalHeight / modifiedHeight, adjustList)
        if self.parent:
            self.parent.calculateZCoords()

    def getWettedPerimeter(self):
        """Return wetted perimeter per pin with duct averaged in."""
        duct = self.getComponent(Flags.DUCT)
        clad = self.getComponent(Flags.CLAD)
        wire = self.getComponent(Flags.WIRE)
        if not (duct and clad):
            raise ValueError(
                "Wetted perimeter cannot be computed in {}. No duct and clad components exist.".format(
                    self
                )
            )
        return math.pi * (
            clad.getDimension("od") + wire.getDimension("od")
        ) + 6 * duct.getDimension("ip") / math.sqrt(3) / clad.getDimension("mult")

    def getFlowAreaPerPin(self):
        """
        Return the flowing coolant area in cm^2.

        NumPins looks for max number of fuel, clad, control, etc.
        See Also
        --------
        getNumPins :  figures out numPins.
        """

        numPins = self.getNumPins()
        try:
            return self.getComponent(Flags.COOLANT, exact=True).getArea() / numPins
        except ZeroDivisionError:
            raise ZeroDivisionError(
                "Block {} has 0 pins (fuel, clad, control, shield, etc.). Thus, its flow area "
                "per pin is undefined.".format(self)
            )

    def getHydraulicDiameter(self):
        """
        Return the hydraulic diameter in this block in cm.

        Hydraulic diameter is 4A/P where A is the flow area and P is the wetted perimeter.
        In a hex assembly, the wetted perimeter includes the cladding, the wire wrap, and the
        inside of the duct. The flow area is the inner area of the duct minus the area of the
        pins and the wire.

        To convert the inner hex pitch into a perimeter, first convert to side, then
        multiply by 6.

        p=sqrt(3)*s
         l = 6*p/sqrt(3)
        """

        return 4.0 * self.getFlowAreaPerPin() / self.getWettedPerimeter()

    def getCladdingOR(self):
        clad = self.getComponent(Flags.CLAD)
        return clad.getDimension("od") / 2.0

    def getCladdingIR(self):
        clad = self.getComponent(Flags.CLAD)
        return clad.getDimension("id") / 2.0

    def getFuelRadius(self):
        fuel = self.getComponent(Flags.FUEL)
        return fuel.getDimension("od") / 2.0

    def adjustUEnrich(self, newEnrich):
        """
        Adjust U-235/U-238 mass ratio to a mass enrichment

        Parameters
        ----------
        newEnrich : float
            New U-235 enrichment in mass fraction

        completeInitialLoading must be run because adjusting the enrichment actually
        changes the mass slightly and you can get negative burnups, which you do not want.
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

        # fix up the params and burnup tracking.
        self.buildNumberDensityParams()
        self.completeInitialLoading()

    def adjustSmearDensity(self, value, bolBlock=None):
        r"""
        modifies the *cold* smear density of a fuel pin by adding or removing fuel dimension.

        Adjusts fuel dimension while keeping cladding ID constant

        sd = fuel_r**2/clad_ir**2  =(fuel_od/2)**2 / (clad_id/2)**2 = fuel_od**2 / clad_id**2
        new fuel_od = sqrt(sd*clad_id**2)

        useful for optimization cases

        Parameters
        ----------

        value : float
            new smear density as a fraction.  This fraction must
            evaluate between 0.0 and 1.0

        bolBlock : Block, optional
            See completeInitialLoading. Required for ECPT cases

        """
        if 0.0 >= value or value > 1.0:
            raise ValueError(
                "Cannot modify smear density of {0} to {1}. Must be a positive fraction"
                "".format(self, value)
            )
        fuel = self.getComponent(Flags.FUEL)
        if not fuel:
            runLog.warning(
                "Cannot modify smear density of {0} because it is not fuel".format(
                    self
                ),
                single=True,
                label="adjust smear density",
            )
            return

        clad = self.getComponent(Flags.CLAD)
        cladID = clad.getDimension("id", cold=True)
        fuelID = fuel.getDimension("id", cold=True)

        if fuelID > 0.0:  # Annular fuel (Adjust fuel ID to get new smear density)
            fuelOD = fuel.getDimension("od", cold=True)
            newID = fuelOD * math.sqrt(1.0 - value)
            fuel.setDimension("id", newID)
        else:  # Slug fuel (Adjust fuel OD to get new smear density)
            newOD = math.sqrt(value * cladID ** 2)
            fuel.setDimension("od", newOD)

        # update things like hm at BOC and smear density parameters.
        self.buildNumberDensityParams()
        self.completeInitialLoading(bolBlock=bolBlock)

    def adjustCladThicknessByOD(self, value):
        """Modifies the cladding thickness by adjusting the cladding outer diameter."""
        clad = self._getCladdingComponentToModify(value)
        if clad is None:
            return
        innerDiam = clad.getDimension("id", cold=True)
        clad.setDimension("od", innerDiam + 2.0 * value)

    def adjustCladThicknessByID(self, value):
        """
        Modifies the cladding thickness by adjusting the cladding inner diameter.

        Notes
        -----
        This WILL adjust the fuel smear density
        """
        clad = self._getCladdingComponentToModify(value)
        if clad is None:
            return
        od = clad.getDimension("od", cold=True)
        clad.setDimension("id", od - 2.0 * value)

    def _getCladdingComponentToModify(self, value):
        clad = self.getComponent(Flags.CLAD)
        if not clad:
            runLog.warning(
                "{} does not have a cladding component to modify.".format(self)
            )
        if value < 0.0:
            raise ValueError(
                "Cannot modify {} on {} due to a negative modifier {}".format(
                    clad, self, value
                )
            )
        return clad

    def getLocation(self):
        """Return a string representation of the location."""
        if self.core and self.parent.spatialGrid and self.spatialLocator:
            return self.core.spatialGrid.getLabel(
                self.spatialLocator.getCompleteIndices()
            )
        else:
            return "ExCore"

    def getLocationObject(self):
        """
        Return a new location object based on current position.

        Notes
        -----
        This is slated for deletion, to be replaced by spatialGrid operations.
        """
        loc = self.LOCATION_CLASS()
        loc.fromLocator(self.spatialLocator.getCompleteIndices())
        return loc

    def coords(self, rotationDegreesCCW=0.0):
        if rotationDegreesCCW:
            raise NotImplementedError("Cannot get coordinates with rotation.")
        return self.spatialLocator.getGlobalCoordinates()

    def setBuLimitInfo(self, cs):
        r"""Sets burnup limit based on igniter, feed, etc.  (will implement general grouping later)"""
        if self.p.buRate == 0:
            # might be cycle 1 or a non-burning block
            self.p.timeToLimit = 0.0
        else:
            timeLimit = (
                self.p.buLimit - self.p.percentBu
            ) / self.p.buRate + self.p.residence
            self.p.timeToLimit = (timeLimit - self.p.residence) / units.DAYS_PER_YEAR

    def getMaxArea(self):
        raise NotImplementedError

    def getMaxVolume(self):
        """
        The maximum volume of this object if it were totally full.

        Returns
        -------
        vol : float
            volume in cm^3.
        """
        return self.getMaxArea() * self.getHeight()

    def getArea(self, cold=False):
        """
        Return the area of a block for a full core or a 1/3 core model.

        Area is consistent with the area in the model, so if you have a central
        assembly in a 1/3 symmetric model, this will return 1/3 of the total
        area of the physical assembly. This way, if you take the sum
        of the areas in the core (or count the atoms in the core, etc.),
        you will have the proper number after multiplying by the model symmetry.

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
        getMaxArea : return the full area of the physical assembly disregarding model symmetry

        """
        # this caching requires that you clear the cache every time you adjust anything
        # including temperature and dimensions.
        area = self._getCached("area")
        if area:
            return area

        a = 0.0
        for c in self.getChildren():
            myArea = c.getArea(cold=cold)
            a += myArea
        fullArea = a

        # correct the fullHexArea by the symmetry factor
        # this factor determines if the hex has been clipped by symmetry lines
        area = fullArea / self.getSymmetryFactor()

        self._setCache("area", area)
        return area

    def getAverageTempInC(self):
        """
        Returns the average temperature of the block in C using the block components

        This supercedes self.getAvgFuelTemp()
        """

        blockAvgTemp = 0.0
        for component, volFrac in self.getVolumeFractions():
            componentTemp = component.temperatureInC
            blockAvgTemp += componentTemp * volFrac

        return blockAvgTemp

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

        In 1/3 symmetric cases, the central assembly is 1/3 a full area.
        If edge assemblies are included in a model, the symmetry factor along
        both edges for overhanging assemblies should be 2.0. However,
        ARMI runs in most scenarios with those assemblies on the 120-edge removed,
        so the symmetry factor should generally be just 1.0.

        See Also
        --------
        armi.reactor.reactors.Core.addEdgeAssemblies
        terrapower.physics.neutronics.dif3d.dif3dInterface.Dif3dReader.scaleParamsRelatedToSymmetry
        """
        return 1.0

    def isOnWhichSymmetryLine(self):
        """Block symmetry lines are determined by the reactor, not the parent."""
        grid = self.core.spatialGrid
        return grid.overlapsWhichSymmetryLine(self.spatialLocator.getCompleteIndices())

    def adjustDensity(self, frac, adjustList, returnMass=False):
        """
        adjusts the total density of each nuclide in adjustList by frac.

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
        for nuclideName in adjustList:
            dens = self.getNumberDensity(nuclideName)
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
            # BOL assems get expanded to a reference so the first check is needed so it
            # won't call .blueprints on None since BOL assems don't have a core/r
            return
        if any(nuc in self.r.blueprints.activeNuclides for nuc in adjustList):
            self.p.detailedNDens *= frac
            # Other power densities do not need to be updated as they are calculated in
            # the global flux interface, which occurs after axial expansion from crucible
            # on the interface stack.
            self.p.pdensDecay *= frac

    def completeInitialLoading(self, bolBlock=None):
        """
        Does some BOL bookkeeping to track things like BOL HM density for burnup tracking.

        This should run after this block is loaded up at BOC (called from
        Reactor.initialLoading).

        The original purpose of this was to get the moles HM at BOC for the moles
        Pu/moles HM at BOL calculation.

        This also must be called after modifying something like the smear density or zr
        fraction in an optimization case. In ECPT cases, a BOL block must be passed or
        else the burnup will try to get based on a pre-burned value.

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
        self.p.molesHmBOL = self.getHMMoles()
        self.p.nHMAtBOL = hmDens
        try:
            # non-pinned reactors (or ones without cladding) will not use smear density
            self.p.smearDensity = self.getSmearDensity()
        except ValueError:
            pass
        self.p.enrichmentBOL = self.getEnrichment()
        massHmBOL = 0.0
        sf = self.getSymmetryFactor()
        for child in self:
            child.p.massHmBOL = child.getHMMass() * sf  # scale to full block
            massHmBOL += child.p.massHmBOL
        self.p.massHmBOL = massHmBOL
        return hmDens

    def replaceBlockWithBlock(self, bReplacement):
        """
        Replace the current block with the replacementBlock.

        Typically used in the insertion of control rods.
        """
        paramsToSkip = set(
            self.p.paramDefs.inCategory(parameters.Category.retainOnReplacement).names
        )

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
    def plotFlux(core, fName, bList=None, peak=False, adjoint=False, bList2=None):
        """
        Produce energy spectrum plot of real and/or adjoint flux in one or more blocks.

        core : Core
            Core object
        fName : str
            the name of the plot file to produce. If none, plot will be shown
        bList : iterable, optional
            is a single block or a list of blocks to average over. If no bList, full core is assumed.
        peak : bool, optional
            a flag that will produce the peak as well as the average on the plot.
        adjoint : bool, optional
            plot the adjoint as well.
        bList2 :
            a separate list of blocks that will also be plotted on a separate axis on the same plot.
            This is useful for comparing flux in some blocks with flux in some other blocks.
        """
        # process arguments
        if bList is None:
            bList = core.getBlocks()
        elif not isinstance(bList, list):
            # convert single block to single entry list
            bList = [bList]

        if bList2 is None:
            bList2 = []

        if adjoint and bList2:
            runLog.warning("Cannot plot adjoint flux with bList2 argument")
            return
        elif adjoint:
            # reuse bList2 for adjoint flux.
            bList2 = bList
        G = len(bList[0].getMgFlux())
        avg = numpy.zeros(G)
        if bList2 or adjoint:
            avg2 = numpy.zeros(G)
            peakFlux2 = numpy.zeros(G)
        peakFlux = numpy.zeros(G)
        for b in bList:
            thisFlux = numpy.array(b.getMgFlux())  # this block's flux.
            avg += thisFlux
            if sum(thisFlux) > sum(peakFlux):
                # save the peak block flux as the peakFlux
                peakFlux = thisFlux

        for b in bList2:
            thisFlux = numpy.array(b.getMgFlux(adjoint=adjoint))
            avg2 += abs(thisFlux)
            if sum(abs(thisFlux)) > sum(abs(peakFlux2)):
                peakFlux2 = abs(thisFlux)

        avg = avg / len(bList)
        if bList2:
            avg2 = avg2 / len(bList2)

        title = os.path.splitext(fName)[0] + ".txt"  # convert pdf name to txt name.

        # lib required to get the energy structure of the groups for plotting.
        lib = core.lib
        if not lib:
            runLog.warning("No ISOTXS library attached so no flux plots.")
            return

        # write a little flux text file.
        with open(title, "w") as f:
            f.write("Energy_Group Average_Flux Peak_Flux\n")
            for g, eMax in enumerate(lib.neutronEnergyUpperBounds):
                f.write("{0} {1} {2}\n".format(eMax / 1e6, avg[g], peakFlux[g]))

        x = []
        yAvg = []
        yPeak = []
        if bList2:
            yAvg2 = []
            yPeak2 = []

        fluxList = avg
        for g, eMax in enumerate(lib.neutronEnergyUpperBounds):
            x.append(eMax / 1e6)
            try:
                yAvg.append(fluxList[g])
            except:
                runLog.error(fluxList)
                raise
            yPeak.append(peakFlux[g])
            if bList2:
                yAvg2.append(avg2[g])
                yPeak2.append(peakFlux2[g])
            # make a "histogram" by adding the same val at the next x-point
            if g < lib.numGroups - 1:
                x.append(lib.neutronEnergyUpperBounds[g + 1] / 1e6)
                yAvg.append(fluxList[g])
                yPeak.append(peakFlux[g])
                if bList2:
                    yAvg2.append(avg2[g])
                    yPeak2.append(peakFlux2[g])

        # visual hack for the lowest energy (last group). Make it flat, but can't go to 0.
        x.append(lib.neutronEnergyUpperBounds[g] / 2e6)
        yAvg.append(yAvg[-1])  # re-add the last point to get the histogram effect.
        yPeak.append(yPeak[-1])
        if bList2:
            yPeak2.append(yPeak2[-1])
            yAvg2.append(yAvg2[-1])

        maxVal = max(yAvg)
        if maxVal <= 0.0:
            runLog.warning(
                "Cannot plot flux with maxval=={0} in {1}".format(maxVal, bList[0])
            )
            return
        plt.figure()
        plt.plot(x, yAvg, "-", label="Average Flux")
        if peak:
            plt.plot(x, yPeak, "-", label="Peak Flux")
        ax = plt.gca()
        ax.set_xscale("log")
        ax.set_yscale("log")
        plt.xlabel("Energy (MeV)")
        plt.ylabel("Flux (n/cm$^2$/s)")
        if peak or bList2:
            plt.legend(loc="lower right")
        plt.grid(color="0.70")
        if bList2:
            if adjoint:
                label1 = "Average Adjoint Flux"
                label2 = "Peak Adjoint Flux"
                plt.twinx()
                plt.ylabel("Adjoint Flux [n/cm$^2$/s]", rotation=270)
                ax2 = plt.gca()
                ax2.set_yscale("log")
            else:
                label1 = "Average Flux 2"
                label2 = "Peak Flux 2"
            plt.plot(x, yAvg2, "r--", label=label1)
            if peak and not adjoint:
                plt.plot(x, yPeak2, "k--", label=label2)
            plt.legend(loc="lower left")
        plt.title("Group flux for {0}".format(title))

        if fName:
            plt.savefig(fName)
            report.setData(
                "Flux Plot {}".format(os.path.split(fName)[1]),
                os.path.abspath(fName),
                report.FLUX_PLOT,
            )
        else:
            plt.show()

    def _updatePitchComponent(self, c):
        """
        Update the component that defines the pitch.

        Given a Component, compare it to the current component that defines the pitch of the Block.
        If bigger, replace it.
        We need different implementations of this to support different logic for determining the
        form of pitch and the concept of "larger".

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
        mult = int(c.getDimension("mult"))
        if self.p.percentBuByPin is None or len(self.p.percentBuByPin) < mult:
            # this may be a little wasteful, but we can fix it later...
            self.p.percentBuByPin = [0.0] * mult

        self._updatePitchComponent(c)

    def addComponent(self, c):
        """adds a component for component-based blocks."""
        self.add(c)

    def removeComponent(self, c):
        """ Removes a component from the component-based blocks."""
        self.remove(c)

    def removeAll(self, recomputeAreaFractions=True):
        for c in self.getChildren():
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

    def getDominantMaterial(self, typeSpec):
        """
        compute the total volume of each distinct material type in this object.

        Parameters
        ----------
        typeSpec : Flags or iterable of Flags
            The types of components to consider (e.g. [Flags.FUEL, Flags.CONTROL])

        Returns
        -------
        mats : dict
            keys are material names, values are the total volume of this material in cm*2
        samples : dict
            keys are material names, values are Material objects

        See Also
        --------
        getComponentsOfMaterial : gets components made of a particular material
        getComponent : get component of a particular type (e.g. Flags.COOLANT)
        getNuclides : list all nuclides in a block or component
        armi.reactor.reactors.Core.getDominantMaterial : gets dominant material in core
        """
        mats = {}
        samples = {}
        for c in self.getComponents(typeSpec):
            vol = c.getVolume()
            matName = c.material.getName()
            mats[matName] = mats.get(matName, 0.0) + vol
            samples[matName] = c.material
        return mats, samples

    def getComponentsThatAreLinkedTo(self, comp, dim):
        """
        Determine which dimensions of which components are linked to a specific dimension of a particular component.

        Useful for breaking fuel components up into individuals and making sure
        anything that was linked to the fuel mult (like the cladding mult) stays correct.

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
        for c in self.getComponents():
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

    def hasComponents(self, typeSpec):
        """
        Return true if all of the named components exist on this block.

        Parameters
        ----------
        typeSpec : Flags or iterable of Flags
            Component types to check for. If None, will check for any components
        """
        # Wrap the typeSpec in a tuple if we got a scalar
        try:
            iterator = iter(typeSpec)
        except TypeError:
            typeSpec = (typeSpec,)

        for t in typeSpec:
            if not self.getComponents(t):
                return False
        return True

    def getComponentByName(self, name):
        """
        Gets a particular component from this block, based on its name

        Parameters
        ----------
        name : str
            The blueprint name of the component to return
        """
        components = [c for c in self if c.name == name]
        nComp = len(components)
        if nComp == 0:
            return None
        elif nComp > 1:
            raise ValueError(
                "More than one component named '{}' in {}".format(self, name)
            )
        else:
            return components[0]

    def getComponent(self, typeSpec, exact=False, returnNull=False, quiet=False):
        """
        Gets a particular component from this block.

        Parameters
        ----------
        typeSpec : flags.Flags or list of Flags
            The type specification of the component to return

        exact : boolean, optional
            Demand that the component flags be exactly equal to the typespec. Default: False

        quiet : boolean, optional
            Warn if the component is not found. Default: False

        Careful with multiple similar names in one block

        Returns
        -------
        Component : The component that matches the critera or None

        """
        results = self.getComponents(typeSpec, exact=exact)
        if len(results) == 1:
            return results[0]
        elif not results:
            if not quiet:
                runLog.warning(
                    "No component matched {0} in {1}. Returning None".format(
                        typeSpec, self
                    ),
                    single=True,
                    label="None component returned instead of {0}".format(typeSpec),
                )
            return None
        else:
            raise ValueError(
                "Multiple components match in {} match typeSpec {}: {}".format(
                    self, typeSpec, results
                )
            )

    def getComponentsOfShape(self, shapeClass):
        """
        Return list of components in this block of a particular shape.

        Parameters
        ----------
        shapeClass : Component
            The class of component, e.g. Circle, Helix, Hexagon, etc.

        Returns
        -------
        param : list
            List of components in this block that are of the given shape.
        """
        return [c for c in self.getComponents() if isinstance(c, shapeClass)]

    def getComponentsOfMaterial(self, material=None, materialName=None):
        """
        Return list of components in this block that are made of a particular material

        Only one of the selectors may be used

        Parameters
        ----------
        material : Material object, optional
            The material to match
        materialName : str, optional
            The material name to match.

        Returns
        -------
        componentsWithThisMat : list

        """

        if materialName is None:
            materialName = material.getName()
        else:
            assert (
                material is None
            ), "Cannot call with more than one selector. Choose one or the other."

        componentsWithThisMat = []
        for c in self.getComponents():
            if c.getProperties().getName() == materialName:
                componentsWithThisMat.append(c)
        return componentsWithThisMat

    def getSortedComponentsInsideOfComponent(self, component):
        """
        Returns a list of components inside of the given component sorted from innermost to outermost.

        Parameters
        ----------
        component : object
            Component to look inside of.

        Notes
        -----
        If you just want sorted components in this block, use ``sorted(self)``.
        This will never include any ``DerivedShape`` objects. Since they have a derived
        area they don't have a well-defined dimension. For now we just ignore them.
        If they are desired in the future some knowledge of their dimension will be
        required while they are being derived.
        """
        sortedComponents = sorted(self)
        componentIndex = sortedComponents.index(component)
        sortedComponents = sortedComponents[:componentIndex]
        return sortedComponents

    def getNumComponents(self, typeSpec):
        """
        Get the number of components that have these flags, taking into account multiplicity. Useful
        for getting nPins even when there are pin detailed cases.

        Parameters
        ----------
        typeSpec : Flags
            Expected flags of the component to get. e.g. Flags.FUEL

        Returns
        -------
        total : int
            the number of components of this type in this block, including multiplicity.
        """
        total = 0
        for c in self.iterComponents(typeSpec):
            total += int(c.getDimension("mult"))
        return total

    def getNumPins(self):
        """Return the number of pins in this block."""
        nPins = [self.getNumComponents(compType) for compType in PIN_COMPONENTS]
        return 0 if not nPins else max(nPins)

    def mergeWithBlock(self, otherBlock, fraction):
        """
        Turns this block into a mixture of this block and some other block

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
        control.  In this case, a control block would be merged with a duct block. It is also used
        when a control rod is specified as a certain length but that length does not fit exactly
        into a full block.
        """

        # reduce this block's number densities
        for nuc in self.getNuclides():
            self.setNumberDensity(nuc, (1.0 - fraction) * self.getNumberDensity(nuc))

        # now add the other blocks densities.
        for nuc in otherBlock.getNuclides():
            self.setNumberDensity(
                nuc,
                self.getNumberDensity(nuc)
                + otherBlock.getNumberDensity(nuc) * fraction,
            )

    def getComponentAreaFrac(self, typeSpec, exact=True):
        """
        Returns the area fraction of the specified component(s) among all components in the block.

        Parameters
        ----------
        typeSpec : Flags or list of Flags
            Component types to look up
        exact : bool, optional
            Match exact names only

        Examples
        ---------
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
                "No component {0} exists on {1}, so area fraction is zero.".format(
                    typeSpec, self
                ),
                single=True,
                label="{0} areaFrac is zero".format(typeSpec),
            )
            return 0.0

    def getCoolantMaterial(self):
        c = self.getComponent(Flags.COOLANT, exact=True)
        return c.getProperties()

    def getCladMaterial(self):
        c = self.getComponent(Flags.CLAD)
        return c.getProperties()

    def getFuelMaterial(self):
        c = self.getComponent(Flags.FUEL)
        return c.getProperties()

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
        >>> getDim(Flags.WIRE,'od')
        0.01

        """
        for c in self:
            if c.hasFlags(typeSpec):
                return c.getDimension(dimName.lower())

    def getPinCenterFlatToFlat(self, cold=False):
        """Return the flat-to-flat distance between the centers of opposing pins in the outermost ring."""
        raise NotImplementedError  # no geometry can be assumed

    def getWireWrapCladGap(self, cold=False):
        """Return the gap betwen the wire wrap and the clad."""
        clad = self.getComponent(Flags.CLAD)
        wire = self.getComponent(Flags.WIRE)
        wireOuterRadius = wire.getBoundingCircleOuterDiameter(cold=cold) / 2.0
        wireInnerRadius = wireOuterRadius - wire.getDimension("od", cold=cold)
        cladOuterRadius = clad.getDimension("od", cold=cold) / 2.0
        return wireInnerRadius - cladOuterRadius

    def getPlenumPin(self):
        """Return the plenum pin if it exists."""
        for c in self.getComponents(Flags.GAP):
            if self.isPlenumPin(c):
                return c
        return None

    def isPlenumPin(self, c):
        """Return True if the specified component is a plenum pin."""
        # This assumes that anything with the GAP flag will have a valid 'id' dimension. If that
        # were not the case, then we would need to protect the call to getDimension with a
        # try/except
        cIsCenterGapGap = (
            isinstance(c, components.Component)
            and c.hasFlags(Flags.GAP)
            and c.getDimension("id") == 0
        )
        if self.hasFlags([Flags.PLENUM, Flags.ACLP]) and cIsCenterGapGap:
            return True
        return False

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
            Hex pitch in cm, if well-defined. If there is no clear component for determining pitch,
            returns None
        component : Component or None
            Component that has the max pitch, if returnComp == True. If no component is found to
            define the pitch, returns None

        Notes
        -----
        The block stores a reference to the component that defines the pitch, making the assumption
        that while the dimensions can change, the component containing the largest dimension will
        not. This lets us skip the search for largest component. We still need to ask the largest
        component for its current dimension in case its temperature changed, or was otherwise
        modified.

        See Also
        --------
        setPitch : sets pitch

        """
        c, p = self._pitchDefiningComponent

        # Admittedly awkward here, but allows for a clean comparison when adding components to the
        # block as opposed to initializing _pitchDefiningComponent to (None, None)
        if c is None:
            p = None
        else:
            # ask component for dimensions, since they could have changed
            p = c.getDimension("op")

        if returnComp:
            return p, c
        else:
            return p

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
        for c in self.getChildren():
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
        for c in self.getComponents():
            try:
                dimVal = c.getDimension(dimension)
            except parameters.ParameterError:
                continue
            if dimVal is not None and dimVal > maxDim:
                maxDim = dimVal
                largestComponent = c
        return largestComponent

    def setPitch(self, val, updateBolParams=False, updateNumberDensityParams=True):
        """
        Sets outer pitch to some new value.

        This sets the settingPitch and actually sets the dimension of the outer hexagon.

        During a load (importGeom), the setDimension doesn't usually do anything except
        set the setting See Issue 034

        But during a actual case modification (e.g. in an optimization sweep, then the dimension
        has to be set as well.

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
        if updateNumberDensityParams:
            # may not want to do this if you will do it shortly thereafter.
            self.buildNumberDensityParams()

    def getMfp(self, gamma=False):
        r"""calculates the mean free path for neutron or gammas in this block.

                    Sum_E(flux_e*macro_e*dE)     Sum_E(flux_e*d*sum_type(micro_e) * dE)
        <Macro> = --------------------------- =  -------------------------------------
                     Sum_E (flux_e*dE)                Sum_E (flux_e*dE)

        Block macro is the sum of macros of all nuclides.

        phi_g = flux*dE already in multigroup method.

        Returns
        -------
        mfp, mfpAbs, diffusionLength : tuple(float, float float)
        """
        lib = self.r.core.lib
        flux = self.getMgFlux(gamma=gamma)
        flux = [fi / max(flux) for fi in flux]
        mfpNumerator = numpy.zeros(len(flux))
        absMfpNumerator = numpy.zeros(len(flux))
        transportNumerator = numpy.zeros(len(flux))
        # vol = self.getVolume()
        for nuc in self.getNuclides():
            dens = self.getNumberDensity(nuc)  # [1/bn-cm]
            nucMc = nucDir.getMc2Label(nuc) + self.getMicroSuffix()
            if gamma:
                micros = lib[nucMc].gammaXS
            else:
                micros = lib[nucMc].micros
            total = micros.total[:, 0]  # 0th order
            transport = micros.transport[:, 0]  # 0th order, [bn]
            absorb = sum(micros.getAbsorptionXS())
            mfpNumerator += dens * total  # [cm]
            absMfpNumerator += dens * absorb
            transportNumerator += dens * transport
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

    def setComponentDimensionsReport(self):
        """Makes a summary of the dimensions of the components in this block."""
        compList = self.getComponentNames()

        reportGroups = []
        for c in self.getComponents():
            reportGroups.append(c.setDimensionReport())

        return reportGroups

    def printDensities(self, expandFissionProducts=False):
        """Get lines that have the number densities of a block."""
        numberDensities = self.getNumberDensities(
            expandFissionProducts=expandFissionProducts
        )
        lines = []
        for nucName, nucDens in numberDensities.items():
            lines.append("{0:6s} {1:.7E}".format(nucName, nucDens))
        return lines

    def buildNumberDensityParams(self, nucNames=None):
        """Copy homogenized density onto self.p for storing in the DB."""
        if nucNames is None:
            nucNames = self.getNuclides()
        nucBases = [nuclideBases.byName[nn] for nn in nucNames]
        nucDensities = self.getNuclideNumberDensities(nucNames)
        for nb, ndens in zip(nucBases, nucDensities):
            self.p[nb.getDatabaseName()] = ndens

    def calcReactionRates(self):
        r"""
        Computes 1-group reaction rates for this block.

        Notes
        -----
        Values include:
        Fission
        nufission
        n2n
        capture
        maybe scatter (will take a long time)

        Rxn rates are Sigma*Flux = Sum_Nuclides(Sum_E(Sigma*Flux*dE))
        S*phi
        n*s*phiV/V [#/bn-cm] * [bn] * [#/cm^2/s] = [#/cm^3/s]

                      (Integral_E in g(phi(E)*sigma(e) dE)
         sigma_g =   ---------------------------------
                          Int_E in g (phi(E) dE)
        """
        lib = self.r.core.lib
        keff = self.r.core.p.keff
        vol = self.getVolume()
        rate = {}
        basicAbs = ["nGamma", "fission", "nalph", "np", "nd", "nt"]
        labels = ["rateCap", "rateFis", "rateProdN2n", "rateProdFis", "rateAbs"]
        for simple in labels:
            rate[simple] = 0.0

        for nuc in self.getNuclides():
            nucrate = {}
            for simple in labels:
                nucrate[simple] = 0.0
            tot = 0.0

            d = self.getNumberDensity(nuc)
            nucMc = nucDir.getMc2Label(nuc) + self.getMicroSuffix()
            micros = lib[nucMc].micros
            for g in range(lib.numGroups):
                flux = (
                    self.p.mgFlux[g] / vol
                )  # this is integrated flux*volume so we divide to get n/cm2/s

                # dE = flux_e*dE
                dphi = d * flux

                tot += micros.total[g, 0] * dphi
                # absorption is fission + capture (no n2n here)
                for name in basicAbs:
                    nucrate["rateAbs"] += dphi * micros[name][g]

                for name in basicAbs:
                    if name != "fission":
                        nucrate["rateCap"] += dphi * micros[name][g]

                fis = micros.fission[g]
                nucrate["rateFis"] += dphi * fis
                nucrate["rateProdFis"] += (
                    dphi * fis * micros.neutronsPerFission[g] / keff
                )  # scale nu by keff.
                nucrate["rateProdN2n"] += (
                    2.0 * dphi * micros.n2n[g]
                )  # this n2n xs is reaction based. Multiply by 2.

            for simple in labels:
                if nucrate[simple]:
                    rate[simple] += nucrate[simple]

        for label, val in rate.items():
            self.p[label] = val  # put in #/cm^3/s

        self.p.vol = vol

    def expandAllElementalsToIsotopics(self):
        reactorNucs = self.getNuclides()
        for elemental in nuclideBases.where(
            lambda nb: isinstance(nb, nuclideBases.NaturalNuclideBase)
            and nb.name in reactorNucs
        ):
            self.expandElementalToIsotopics(elemental)

    def expandElementalToIsotopics(self, elementalNuclide):
        """
        Expands the density of a specific elemental nuclides to its natural isotopics.

        Parameters
        ----------
        elementalNuclide : :class:`armi.nucDirectory.nuclideBases.NaturalNuclide`
            natural nuclide to replace.
        """
        natName = elementalNuclide.name
        for component in self.getComponents():
            elementalDensity = component.getNumberDensity(natName)
            if elementalDensity == 0.0:
                continue
            component.setNumberDensity(natName, 0.0)  # clear the elemental
            del component.p.numberDensities[natName]
            # add in isotopics
            for natNuc in elementalNuclide.getNaturalIsotopics():
                component.setNumberDensity(
                    natNuc.name, elementalDensity * natNuc.abundance
                )
        try:
            # not all blocks have the same nuclides, but we don't actually care if it did or not, just delete the
            # parameter...
            del self.p[elementalNuclide.getDatabaseName()]
        except KeyError:
            pass

    def enforceBondRemovalFraction(self, bondRemovedFrac):
        r"""
        Update the distribution of coolant in this block to agree with a fraction

        This pulls coolant material out of the bond component and adds it to the other
        coolant-containing components while conserving mass.

        Useful after db load with sodium bond. See armi.bookkeeping.db.database.updateFromDB

        :math:`N_{hom} = \sum_{i} a_i N_i`

        We want :math:`f = \frac{a_{bond} N_{bond}}{N_{hom}}`
        So we can solve this for :math:`N_{bond}` and reduce the other
        number densities accordingly.

        Should work for coolants with more than 1 nuclide (e.g. H2O, Pb-Bi, NaK,...)

        Parameters
        ----------
        bondRemovedFrac : float
            Fraction of the bond that has been removed.

        See Also
        --------
        armi.reactor.assemblies.Assembly.applyBondRemovalFractions : does this in the original case
        """

        bond = self.getComponent(Flags.BOND, quiet=True)
        if not bond or not bondRemovedFrac:
            return
        volFracs = self.getVolumeFractions()
        vBond = self.getComponentAreaFrac(Flags.BOND)
        nuclides = bond.getNuclides()
        # reduce to components of the same material.
        coolantFracs = []

        totalCoolantFrac = 0.0
        for comp, vFrac in volFracs:
            if comp.getProperties().getName() == bond.getProperties().getName():
                coolantFracs.append((comp, vFrac))
                totalCoolantFrac += vFrac

        ndensHomog = []
        for nuc in nuclides:
            nh = 0.0  # homogenized number density of bond material (e.g. sodium)
            for comp, vFrac in coolantFracs:
                nh += comp.getNumberDensity(nuc) * vFrac
            ndensHomog.append(nh)

        # adjust bond values Nb'=(1-f)*Nb_bol
        newBondNdens = []
        for nuc, nh in zip(nuclides, ndensHomog):
            ni = self.p.bondBOL * (1.0 - bondRemovedFrac)
            newBondNdens.append(ni)
            bond.setNumberDensity(nuc, ni)

        # adjust values of other components (e.g. coolant, interCoolant)
        for nuc, nh, nbNew in zip(nuclides, ndensHomog, newBondNdens):
            newOtherDens = (nh - nbNew * vBond) / (totalCoolantFrac - vBond)
            for comp, vFrac in coolantFracs:
                if comp is bond:
                    continue
                comp.setNumberDensity(nuc, newOtherDens)

    def getBurnupPeakingFactor(self):
        """
        Get the radial peaking factor to be applied to burnup and DPA

        This may be informed by previous runs which used
        detailed pin reconstruction and rotation. In that case,
        it should be set on the cs setting ``burnupPeakingFactor``.

        Otherwise, it just takes the current flux peaking, which
        is typically conservatively high.

        Returns
        -------
        burnupPeakingFactor : float
            The peak/avg factor for burnup and DPA.

        See Also
        --------
        armi.physics.neutronics.globalFlux.globalFluxInterface.GlobalFluxInterface.updateFluenceAndDPA : uses this
        terrapower.physics.neutronics.depletion.depletion.DepletionInterface._updateBlockParametersAfterDepletion : also uses this
        """
        burnupPeakingFactor = settings.getMasterCs()["burnupPeakingFactor"]
        if not burnupPeakingFactor and self.p.fluxPeak:
            burnupPeakingFactor = self.p.fluxPeak / self.p.flux
        elif not burnupPeakingFactor:
            # no peak available. Finite difference model?
            burnupPeakingFactor = 1.0

        return burnupPeakingFactor

    def getBlocks(self):
        """
        This method returns all the block(s) included in this block
        its implemented so that methods could iterate over reactors, assemblies
        or single blocks without checking to see what the type of the
        reactor-family object is.
        """
        return [self]

    def updateComponentDims(self):
        """
        This method updates all the dimensions of the components

        Notes
        -----
        This is VERY useful for defining a ThRZ core out of
        differentialRadialSegements whose dimensions are connected together
        some of these dimensions are derivative and can be updated by changing
        dimensions in a Parameter Component or other linked components

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

    def isAnnular(self):
        """True if contains annular fuel."""
        fuelPin = self.getComponent(Flags.FUEL)
        if not fuelPin:
            return False

        if abs(fuelPin.getDimension("id") - 0.0) < 1e-6:
            return False

        return True

    def getDpaXs(self):
        """Determine which cross sections should be used to compute dpa for this block."""
        if settings.getMasterCs()["gridPlateDpaXsSet"] and self.hasFlags(
            Flags.GRID_PLATE
        ):
            dpaXsSetName = settings.getMasterCs()["gridPlateDpaXsSet"]
        else:
            dpaXsSetName = settings.getMasterCs()["dpaXsSet"]

        if not dpaXsSetName:
            return None
        try:
            return constants.DPA_CROSS_SECTIONS[dpaXsSetName]
        except KeyError:
            raise KeyError(
                "DPA cross section set {} does not exist".format(dpaXsSetName)
            )

    def breakFuelComponentsIntoIndividuals(self):
        """
        Split block-level components (in fuel blocks) into pin-level components.

        The fuel component will be broken up according to its multiplicity.

        Order matters! The first pin component will be located at a particular (x, y), which
        will be used in the fluxRecon module to determine the interpolated flux.

        The fuel will become fuel001 through fuel169 if there are 169 pins.
        """

        fuels = self.getChildrenWithFlags(Flags.FUEL)
        if len(fuels) != 1:
            runLog.error(
                "This block contains {0} fuel components: {1}".format(len(fuels), fuels)
            )
            raise RuntimeError(
                "Cannot break {0} into multiple fuel components b/c there is not a single fuel"
                " component.".format(self)
            )
        fuel = fuels[0]
        fuelFlags = fuel.p.flags
        nPins = self.getNumPins()
        runLog.info(
            "Creating {} individual {} components on {}".format(nPins, fuel, self)
        )

        # handle all other components that may be linked to the fuel multiplicity.
        # by unlinking them and setting them directly
        # XXX: what about other (actual) dimensions? This is a limitation in that only fuel
        # compuents are duplicated, and not the entire pin. It is also a reasonable assumption with
        # current/historical usage of ARMI.
        for comp, dim in self.getComponentsThatAreLinkedTo(fuel, "mult"):
            comp.setDimension(dim, nPins)

        # finish the first pin as a single pin
        fuel.setDimension("mult", 1)
        fuel.setName("fuel001")
        fuel.p.pinNum = 1

        # create all the new pin components and add them to the block with 'fuel001' names
        for i in range(nPins - 1):
            # wow, only use of a non-deepcopy
            newC = copy.copy(fuel)
            newC.setName("fuel{0:03d}".format(i + 2))  # start with 002.
            newC.p.pinNum = i + 2
            self.addComponent(newC)

        # update moles at BOL for each pin
        self.p.molesHmBOLByPin = []
        for pinNum, pin in enumerate(self.iterComponents(Flags.FUEL)):
            pin.p.flags = fuelFlags  # Update the fuel component flags to be the same as before the split (i.e., DEPLETABLE)
            self.p.molesHmBOLByPin.append(pin.getHMMoles())
            pin.p.massHmBOL /= nPins

    def getIntegratedMgFlux(self, adjoint=False, gamma=False):
        """
        Return the volume integrated multigroup neutron tracklength in [n-cm/s].

        The first entry is the first energy group (fastest neutrons). Each additional
        group is the next energy group, as set in the ISOTXS library.

        Parameters
        ----------
        adjoint : bool, optional
            Return adjoint flux instead of real

        gamma : bool, optional
            Whether to return the neutron flux or the gamma flux.

        Returns
        -------
        integratedFlux : numpy.array
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

        return numpy.array(integratedFlux)

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

    def getReactionRates(self, nucName, nDensity=None):
        """
        Parameters
        ----------
        nucName - str
            nuclide name -- e.g. 'U235'
        nDensity - float
            number Density

        Returns
        -------
        rxnRates : dict
            dictionary of reaction rates (rxn/s) for nG, nF, n2n, nA and nP

        Note
        ----
        If you set nDensity to 1/CM2_PER_BARN this makes 1 group cross section generation easier
        """
        if nDensity is None:
            nDensity = self.getNumberDensity(nucName)
        try:
            return components.component.getReactionRateDict(
                nucName,
                self.r.core.lib,
                self.p.xsType,
                self.getIntegratedMgFlux(),
                nDensity,
            )
        except AttributeError:
            # AttributeError because there was no library because no parent.r -- this is a armiObject without flux so
            # send it some zeros
            return {"nG": 0, "nF": 0, "n2n": 0, "nA": 0, "nP": 0}


class HexBlock(Block):

    LOCATION_CLASS = locations.HexLocation

    PITCH_COMPONENT_TYPE: ClassVar[_PitchDefiningComponent] = (
        components.UnshapedComponent,
        components.Hexagon,
    )

    def __init__(self, name, height=1.0, location=None):
        Block.__init__(self, name, height, location)

    def coords(self, rotationDegreesCCW=0.0):
        x, y, _z = self.spatialLocator.getGlobalCoordinates()
        x += self.p.displacementX * 100.0
        y += self.p.displacementY * 100.0
        return (
            round(x, units.FLOAT_DIMENSION_DECIMALS),
            round(y, units.FLOAT_DIMENSION_DECIMALS),
        )

    def getMaxArea(self):
        """Compute the max area of this block if it was totally full."""
        pitch = self.getPitch()
        if not pitch:
            return 0.0
        return hexagon.area(pitch)

    def getDuctIP(self):
        duct = self.getComponent(Flags.DUCT, exact=True)
        return duct.getDimension("ip")

    def getDuctOP(self):
        duct = self.getComponent(Flags.DUCT, exact=True)
        return duct.getDimension("op")

    def initializePinLocations(self):
        nPins = self.getNumPins()
        self.p.pinLocation = list(range(1, nPins + 1))

    def setPinPowers(
        self,
        powers,
        numPins,
        imax,
        jmax,
        gamma=False,
        removeSixCornerPins=False,
        powerKeySuffix="",
    ):
        """
        Updates the pin powers of this block for the current rotation.

        Parameters
        ----------
        powers : list of floats
            The block-level pin linear power densities. pinPowers[i] represents the average linear
            power density of pin i.
            Power units are Watts/cm (Watts produced per cm of pin length).
            The "ARMI pin ordering" is used, which is counter-clockwise from 3 o'clock.

        Notes
        -----
        This handles rotations using the pinLocation parameters.

        Outputs
        -------
        self.p.pinPowers : list of floats
            The block-level pin linear power densities. pinPowers[i] represents the average linear
            power density of pin i.
            Power units are Watts/cm (Watts produced per cm of pin length).
            The "ARMI pin ordering" is used, which is counter-clockwise from 3 o'clock.
        """
        # numPins = self.getNumPins()
        self.p.pinPowers = [
            0 for _n in range(numPins)
        ]  # leave as a list. maybe go to dictionary later.
        j0 = jmax[imax - 1] / 6
        pinNum = 0
        cornerPinCount = 0

        self.p["linPowByPin" + powerKeySuffix] = []
        for i in range(imax):  # loop through rings
            for j in range(jmax[i]):  # loop through positions in ring i
                pinNum += 1

                if (
                    removeSixCornerPins
                    and (i == imax - 1)
                    and (math.fmod(j, j0) == 0.0)
                ):
                    linPow = 0.0
                else:
                    if self.hasFlags(Flags.FUEL):
                        pinLoc = self.p.pinLocation[pinNum - 1]
                    else:
                        pinLoc = pinNum

                    linPow = powers[
                        pinLoc - 1
                    ]  # -1 to map from pinLocations to list index

                self.p.pinPowers[pinNum - 1 - cornerPinCount] = linPow
                self.p["linPowByPin" + powerKeySuffix].append(linPow)

        if powerKeySuffix == GAMMA:
            self.p.pinPowersGamma = self.p.pinPowers
        elif powerKeySuffix == NEUTRON:
            self.p.pinPowersNeutron = self.p.pinPowers

        if gamma:
            self.p.pinPowers = self.p.pinPowersNeutron + self.p.pinPowersGamma
        else:
            self.p.pinPowers = self.p.pinPowersNeutron

    def rotatePins(self, rotNum, justCompute=False):
        """
        Rotate an assembly, which means rotating the indexing of pins.

        Notes
        -----
        Changing (x,y) positions of pins does NOT constitute rotation, because the indexing of pin
        atom densities must be re-ordered.  Re-order indexing of pin-level quantities, NOT (x,y)
        locations of pins.  Otherwise, subchannel input will be in wrong order.

        How rotations works is like this. There are pins with unique pin numbers in each block.
        These pin numbers will not change no matter what happens to a block, so if you have pin 1,
        you always have pin 1. However, these pins are all in pinLocations, and these are what
        change with rotations. At BOL, a pin's pinLocation is equal to its pin number, but after
        a rotation, this will no longer be so.

        So, all params that don't care about exactly where in space the pin is (such as depletion)
        can just use the pin number, but anything that needs to know the spatial location (such as
        fluxRecon, which interpolates the flux spatially, or subchannel codes, which needs to know where the
        power is) need to map through the pinLocation parameters.

        This method rotates the pins by changing the pinLocations.

        Parameters
        ----------
        rotNum : int
            An integer from 0 to 5, indicating the number of counterclockwise 60-degree rotations
            from the CURRENT orientation. Degrees of counter-clockwise rotation = 60*rot

        justCompute : Boolean, optional
            If True, rotateIndexLookup will be returned but NOT assigned to the object variable
            self.rotateIndexLookup.
            If False, rotateIndexLookup will be returned AND assigned to the object variable
            self.rotateIndexLookup.  Useful for figuring out which rotation is best to minimize
            burnup, etc.

        Returns
        -------
        rotateIndexLookup : dict of ints
            This is an index lookup (or mapping) between pin ids and pin locations
            The pin indexing is 1-D (not ring,pos or GEODST).
            The "ARMI pin ordering" is used for location, which is counter-clockwise from 3 o'clock.
            Pin numbers start at 1, pin locations also start at 1.

        Examples
        --------
        rotateIndexLookup[i_after_rotation-1] = i_before_rotation-1
        """
        if not 0 <= rotNum <= 5:
            raise ValueError(
                "Cannot rotate {0} to rotNum {1}. Must be 0-5. ".format(self, rotNum)
            )
        # pin numbers start at 1.
        numPins = self.getNumComponents(Flags.CLAD)  # number of pins in this assembly
        rotateIndexLookup = dict(zip(range(1, numPins + 1), range(1, numPins + 1)))

        currentRotNum = self.getRotationNum()
        # look up the current orientation and add this to it. The math below just rotates from the
        # reference point so we need a total rotation.
        rotNum = currentRotNum + rotNum % 6

        # non-trivial rotation requested
        for pinNum in range(
            2, numPins + 1
        ):  # start at 2 because pin 1 never changes (it's in the center!)
            if rotNum == 0:
                # rotation to reference orientation. Pin locations are pin IDs.
                pass
            else:
                # Determine the pin ring (courtesy of Robert Petroski from subchan.py). Rotation does not change the pin ring!
                ring = int(
                    math.ceil((3.0 + math.sqrt(9.0 - 12.0 * (1.0 - pinNum))) / 6.0)
                )
                # Determine the total number of pins in THIS ring PLUS all interior rings.
                tot_pins = 1 - 6 * (ring - 1) + 3 * (ring - 1) * (ring + 2)
                # Rotate the pin position (within the ring, which does not change)
                newPinLocation = pinNum + (ring - 1) * rotNum
                if newPinLocation > tot_pins:
                    newPinLocation -= (ring - 1) * 6
                # Assign "before" and "after" pin indices to the index lookup
                rotateIndexLookup[pinNum] = newPinLocation

            if not justCompute:
                self.p["pinLocation", rotateIndexLookup[pinNum]] = pin = pinNum

        if not justCompute:
            self.setRotationNum(rotNum)
        return rotateIndexLookup

    def verifyBlockDims(self):
        """Perform some checks on this type of block before it is assembled."""
        try:
            wireComp = self.getComponent(Flags.WIRE)
            ductComps = self.getComponents(Flags.DUCT)
            cladComp = self.getComponent(Flags.CLAD)
        except ValueError:
            # there are probably more that one clad/wire, so we really dont know what this block looks like
            runLog.info(
                "Block design {} is too complicated to verify dimensions. Make sure they "
                "are correct!".format(self)
            )
            return
        # check wire wrap in contact with clad
        if (
            self.getComponent(Flags.CLAD) is not None
            and self.getComponent(Flags.WIRE) is not None
        ):
            wwCladGap = self.getWireWrapCladGap(cold=True)
            if round(wwCladGap, 6) != 0.0:
                runLog.warning(
                    "The gap between wire wrap and clad in block {} was {} cm. Expected 0.0."
                    "".format(self, wwCladGap),
                    single=True,
                )
        # check clad duct overlap
        pinToDuctGap = self.getPinToDuctGap(cold=True)
        # Allow for some tolerance; user input precision may lead to slight negative
        # gaps
        if pinToDuctGap is not None and pinToDuctGap < -0.005:
            raise ValueError(
                "Gap between pins and duct is {0:.4f} cm in {1}. Make more room.".format(
                    pinToDuctGap, self
                )
            )
            wire = self.getComponent(Flags.WIRE)
            wireThicknesses = wire.getDimension("od", cold=False)
            if pinToDuctGap < wireThicknesses:
                raise ValueError(
                    "Gap between pins and duct is {0:.4f} cm in {1} which does not allow room for the wire "
                    "with diameter {2}".format(pinToDuctGap, self, wireThicknesses)
                )
        elif pinToDuctGap is None:
            # only produce a warning if pin or clad are found, but not all of pin, clad and duct. We
            # may need to tune this logic a bit
            ductComp = next(iter(ductComps), None)
            if (cladComp is not None or wireComp is not None) and any(
                [c is None for c in (wireComp, cladComp, ductComp)]
            ):
                runLog.warning(
                    "Some component was missing in {} so pin-to-duct gap not calculated"
                    "".format(self)
                )

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
            Returns the diameteral gap between the outer most pins in a hex pack to the duct inner
            face to face in cm.
        """
        if self.LOCATION_CLASS is None:
            return None  # can't assume anything about dimensions if there is no location type

        wire = self.getComponent(Flags.WIRE)
        ducts = sorted(self.getChildrenWithFlags(Flags.DUCT))
        duct = None
        if any(ducts):
            duct = ducts[0]
            if not isinstance(duct, components.Hexagon):
                # getPinCenterFlatToFlat only works for hexes
                # inner most duct might be circle or some other shape
                duct = None
        clad = self.getComponent(Flags.CLAD)
        if any(c is None for c in (duct, wire, clad)):
            return None

        # note, if nRings was a None, this could be for a non-hex packed fuel assembly
        # see thermal hydraulic design basis for description of equation
        pinCenterFlatToFlat = self.getPinCenterFlatToFlat(cold=cold)
        pinOuterFlatToFlat = (
            pinCenterFlatToFlat
            + clad.getDimension("od", cold=cold)
            + 2.0 * wire.getDimension("od", cold=cold)
        )
        ductMarginToContact = duct.getDimension("ip", cold=cold) - pinOuterFlatToFlat
        pinToDuctGap = ductMarginToContact / 2.0

        return pinToDuctGap

    def getRotationNum(self):
        """
        Get index 0 through 5 indicating number of rotations counterclockwise around the z-axis.
        """
        return (
            numpy.rint(self.p.orientation[2] / 360.0 * 6) % 6
        )  # assume rotation only in Z

    def setRotationNum(self, rotNum):
        """
        Set orientation based on a number 0 through 5 indicating number of rotations
        counterclockwise around the z-axis.
        """
        self.p.orientation[2] = 60.0 * rotNum

    def getSymmetryFactor(self):
        """
        Return a factor between 1 and N where 1/N is how much cut-off by symmetry lines this mesh
        cell is.

        Reactor-level meshes have symmetry information so we have a reactor for this to work. That's
        why it's not implemented on the grid/locator level.

        When edge-assemblies are included on both edges (i.e. MCNP or DIF3D-FD 1/3-symmetric cases),
        the edge assemblies have symmetry factors of 2.0. Otherwise (DIF3D-nodal) there's a full
        assembly on the bottom edge (overhanging) and no assembly at the top edge so the ones at the
        bottom are considered full (symmetryFactor=1).

        If this block is not in any grid at all, then there can be no symmetry so return 1.
        """
        if (
            self.core is not None
            and self.spatialLocator.grid
            and self.core.symmetry == geometry.THIRD_CORE + geometry.PERIODIC
        ):
            indices = self.spatialLocator.getCompleteIndices()
            if indices[0] == 0 and indices[1] == 0:
                # central location
                return 3.0
            else:
                symmetryLine = self.r.core.spatialGrid.overlapsWhichSymmetryLine(
                    indices
                )
                # detect if upper edge assemblies are included. Doing this is the only way to know
                # definitively whether or not the edge assemblies are half-assems or full.
                # seeing the first one is the easiest way to detect them.
                # Check it last in the and statement so we don't waste time doing it.
                upperEdgeLoc = self.r.core.spatialGrid[-1, 2, 0]
                if symmetryLine in [
                    grids.BOUNDARY_0_DEGREES,
                    grids.BOUNDARY_120_DEGREES,
                ] and bool(self.r.core.childrenByLocator.get(upperEdgeLoc)):
                    return 2.0
        return 1.0

    def getPinCoordinates(self):
        """
        Compute the centroid coordinates of any pins in this block.

        Returns
        -------
        localCoordinates : list
            list of (x,y,z) pairs representing each pin in the order they are listed as children

        Notes
        -----
        This assumes hexagonal pin lattice and needs to be upgraded once more generic geometry
        options are needed.

        A block with fully-defined pins could just use their individual spatialLocators in a
        block-level 2-D grid. However most cases do not have this to minimize overhead and maximize
        speed. Thus we want to just come up with a uniform mesh of pins if they're not explicitly
        placed in the grid.

        """
        return self._getPinCoordinatesHex()

    def _getPinCoordinatesHex(self):
        coordinates = []
        numPins = self.getNumPins()
        numPinRings = hexagon.numRingsToHoldNumCells(numPins)
        pinPitch = self.getPinPitch()
        if pinPitch is None:
            return []
        # pin lattice is rotated 30 degrees from assembly lattice
        grid = grids.hexGridFromPitch(pinPitch, numPinRings, self, pointedEndUp=True)
        for ring in range(numPinRings):
            for pos in range(hexagon.numPositionsInRing(ring + 1)):
                i, j = grids.getIndicesFromRingAndPos(ring + 1, pos + 1)
                xyz = grid[i, j, 0].getLocalCoordinates()
                coordinates.append(xyz)
        return coordinates

    def getPinCenterFlatToFlat(self, cold=False):
        """Return the flat-to-flat distance between the centers of opposing pins in the outermost ring."""
        clad = self.getComponent(Flags.CLAD)
        loc = self.LOCATION_CLASS()
        nRings = loc.getNumRings(clad.getDimension("mult"), silent=True)
        pinPitch = self.getPinPitch(cold=cold)
        pinCenterCornerToCorner = 2 * (nRings - 1) * pinPitch
        pinCenterFlatToFlat = math.sqrt(3.0) / 2.0 * pinCenterCornerToCorner
        return pinCenterFlatToFlat

    def hasPinPitch(self):
        """Return True if the block has enough information to calculate pin pitch."""
        return self.getComponent(Flags.CLAD) and self.getComponent(Flags.WIRE)

    def getPinPitch(self, cold=False):
        """
        Get the pin pitch in cm.

        Assumes that the pin pitch is defined entirely by contacting cladding tubes
        and wire wraps. Grid spacers not yet supported.

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
            clad = self.getComponent(Flags.CLAD)
            wire = self.getComponent(Flags.WIRE)
        except ValueError:
            runLog.info(
                "Block {} has multiple clad and wire components,"
                " so pin pitch is not well-defined.".format(self)
            )
            return

        if wire and clad:
            return clad.getDimension("od", cold=cold) + wire.getDimension(
                "od", cold=cold
            )
        else:
            raise ValueError(
                "Cannot get pin pitch in {} because it does not have a wire and a clad".format(
                    self
                )
            )


class CartesianBlock(Block):

    LOCATION_CLASS = locations.CartesianLocation

    PITCH_DIMENSION = "widthOuter"
    PITCH_COMPONENT_TYPE = (components.UnshapedComponent, components.Rectangle)

    def getMaxArea(self):
        """Get area of this block if it were totally full."""
        xw, yw = self.getPitch()
        return xw * yw

    def setPitch(self, val, updateBolParams=False, updateNumberDensityParams=True):
        raise NotImplementedError(
            "Directly setting the pitch of a cartesian block is currently "
            "not supported"
        )

    def getPitch(self, returnComp=False):
        """
        Get xw and yw of the block.

        See Also
        --------
        Block.getPitch
        """
        c, _p = self._pitchDefiningComponent

        # Admittedly awkward here, but allows for a clean comparison when adding components to the
        # block as opposed to initializing _pitchDefiningComponent to (None, None)
        if c is None:
            raise ValueError("{} has no valid pitch".format(self))
        else:
            # ask component for dimensions, since they could have changed
            maxLength = c.getDimension("lengthOuter")
            maxWidth = c.getDimension("widthOuter")

        if returnComp:
            return (maxLength, maxWidth), c
        else:
            return (maxLength, maxWidth)

    def getSymmetryFactor(self):
        """
        Return a factor between 1 and N where 1/N is how much cut-off by symmetry lines this mesh
        cell is.
        """
        if self.r is not None:
            indices = self.spatialLocator.getCompleteIndices()
            if geometry.THROUGH_CENTER_ASSEMBLY in self.r.core.symmetry:
                if indices[0] == 0 and indices[1] == 0:
                    # central location
                    return 4.0
                elif indices[0] == 0 or indices[1] == 0:
                    # edge location
                    return 2.0
        return 1.0

    def getPinCenterFlatToFlat(self, cold=False):
        """
        Return the flat-to-flat distance between the centers of opposing pins in the outermost ring.
        """
        clad = self.getComponent(Flags.CLAD)
        loc = self.LOCATION_CLASS()
        nRings = loc.getNumRings(clad.getDimension("mult"), silent=True)
        pinPitch = self.getPinPitch(cold=cold)
        return 2 * (nRings - 1) * pinPitch


class ThRZBlock(Block):

    LOCATION_CLASS = locations.ThetaRZLocation
    # be sure to fill ThRZ blocks with only 3D components - components with explicit getVolume methods

    def getMaxArea(self):
        """Return the area of the Theta-R-Z block if it was totally full."""
        raise NotImplementedError(
            "Cannot get max area of a TRZ block. Fully specify your geometry."
        )

    def radialInner(self):
        """Return a smallest radius of all the components."""
        innerRadii = self.getDimensions("inner_radius")
        smallestInner = min(innerRadii) if innerRadii else None
        return smallestInner

    def radialOuter(self):
        """Return a largest radius of all the components."""
        outerRadii = self.getDimensions("outer_radius")
        largestOuter = max(outerRadii) if outerRadii else None
        return largestOuter

    def thetaInner(self):
        """Return a smallest theta of all the components."""
        innerTheta = self.getDimensions("inner_theta")
        smallestInner = min(innerTheta) if innerTheta else None
        return smallestInner

    def thetaOuter(self):
        """Return a largest theta of all the components."""
        outerTheta = self.getDimensions("outer_theta")
        largestOuter = min(outerTheta) if outerTheta else None
        return largestOuter

    def axialInner(self):
        """Return the lower z-coordinate."""
        return self.getDimensions("inner_axial")

    def axialOuter(self):
        """Return the upper z-coordinate."""
        return self.getDimensions("outer_axial")

    def verifyBlockDims(self):
        """Perform dimension checks related to ThetaRZ blocks."""
        return


class Point(Block):
    """
    Points quack like blocks.
    This Point object represents a single point in space within a Block.
    The Point object masquerades as a Block so that any Block parameter
    (such as DPA) can be assigned to it with the same functionality.
    """

    LOCATION_CLASS = locations.HexLocation

    def __init__(self, name=None):

        super(Point, self).__init__(name)

        self.xyz = [
            0.0,
            0.0,
            0.0,
        ]  # initialize the x,y,z coordinates of this Point object.

        params = ["detailedDpaRate", "detailedDpaPeakRate"]
        for param in params:
            self.p[param] = 0.0

    def getVolume(self):
        return (
            1.0  # points have no volume scaling; point flux are not volume-integrated
        )

    def getBurnupPeakingFactor(self):
        return 1.0  # peaking makes no sense for points
