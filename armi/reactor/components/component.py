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
Components represent geometric objects within an assembly such as fuel, bond, coolant, ducts, wires, etc.

This module contains the abstract definition of a Component.
"""
import copy
import re

import numpy

from armi.materials import material
from armi.materials import custom
from armi import runLog
from armi.bookkeeping import report
from armi.reactor import composites
from armi.reactor import parameters
from armi.reactor.components import componentParameters
from armi.utils import densityTools
from armi.utils.units import C_TO_K
from armi.materials import void
from armi.nucDirectory import nuclideBases
from armi import materials

COMPONENT_LINK_REGEX = re.compile(r"^\s*(.+?)\s*\.\s*(.+?)\s*$")


_NICE_DIM_NAMES = {
    "id": "Inner Diameter (cm)",
    "od": "Outer Diameter (cm)",
    "ip": "Inner Pitch (cm)",
    "op": "Outer Pitch (cm)",
    "mult": "Multiplicity",
    "axialPitch": "Axial Pitch (cm)",
    "helixDiameter": "Helix Diameter (cm)",
    "length": "Length (cm)",
    "height": "Height (cm)",
    "width": "Width (cm)",
    "areaMod": "Area Mod. Factor",
}


def componentTypeIsValid(component, name):
    """
    Checks that the component assigned component type is valid

    Notes
    -----
    - `Coolant` components are can no longer be defined as a general `Component` and should be specfied as a
      `DerivedShape` if the coolant dimensions are not provided.

    """
    from armi.reactor.components import NullComponent

    if name.lower() == "coolant":
        invalidComponentTypes = [Component, NullComponent]
        if component.__class__ in invalidComponentTypes:
            raise ValueError(
                "Coolant components cannot be defined as a `Component`. Either define coolant as a "
                "`DerivedShape` or specify its dimensions explicitly using another component type."
            )


class _DimensionLink(tuple):
    """
    A linked dimension, where one component uses a dimension from another.

    Useful when the boundaries are physically shared and should move together.

    The tuple contains (linkedComponent, linkedDimensionName).

    In equating two components, we need the linked dimensions to resolve responsibly/precisely.
    """

    def getLinkedComponent(self):
        """Return the linked component."""
        return self[0]

    def resolveDimension(self, Tc=None, cold=False):
        """Return the current value of the linked dimension."""
        linkedComponent = self[0]
        dimID = self[1]
        return linkedComponent.getDimension(dimID, Tc=Tc, cold=cold)

    def __eq__(self, other):
        otherDimension = (
            other.resolveDimension() if isinstance(other, _DimensionLink) else other
        )
        return self.resolveDimension() == otherDimension

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        """Return a string representation of a dimension link.

        These look like ``otherComponentName.otherDimensionName``.
        For example, if a link were to a ``fuel`` component's
        ``od`` param, the link would render as ``fuel.od``.
        """
        return f"{self[0].name}.{self[1]}"


class ComponentType(composites.CompositeModelType):
    """
    ComponetType is a metaclass for storing and initializing Component subclass types.

    The construction of Component subclasses is being done through factories for ease of
    user input.  As a consequence, the ``__init__`` methods' arguments need to be known
    in order to conform them to the correct format. Additionally, the constructors
    arguments can be used to determine the Component subclasses dimensions.

    .. warning:: The import-time metaclass-based component subclass registration was a
        good idea, but in practice has caused significant confusion and trouble. We will
        replace this soon with an explicit plugin-based component subclass registration
        system.
    """

    TYPES = dict()

    NON_DIMENSION_NAMES = (
        "Tinput",
        "Thot",
        "isotopics",
        "mergeWith",
        "material",
        "name",
        "components",
        "area",
    )

    def __new__(cls, name, bases, attrs):
        newType = composites.CompositeModelType.__new__(cls, name, bases, attrs)
        ComponentType.TYPES[name.lower()] = newType

        # the co_varnames attribute contains arguments and then locals so we must
        # restrict it to just the arguments.
        signature = newType.__init__.__code__.co_varnames[
            1 : newType.__init__.__code__.co_argcount
        ]

        # INIT_SIGNATURE and DIMENSION_NAMES are in the same order as the method signature
        newType.INIT_SIGNATURE = tuple(signature)
        newType.DIMENSION_NAMES = tuple(
            k
            for k in newType.INIT_SIGNATURE
            if k not in ComponentType.NON_DIMENSION_NAMES
        )
        return newType


class Component(composites.Composite, metaclass=ComponentType):
    """
    A primitive object in a reactor that has definite area/volume, material and composition.

    Could be fuel pins, cladding, duct, wire wrap, etc. One component object may represent
    multiple physical components via the ``multiplicity`` mechanism.

    Attributes
    ----------
    temperatureInC : float
        Current temperature of component in celcius.
    inputTemperatureInC : float
        Reference temperature in C at which dimension definitions were input
    temperatureInC : float
        Temperature in C to which dimensions were thermally-expanded upon input.
    material : str or material.Material
        The material object that makes up this component and give it its thermo-mechanical properties.

    .. impl:: ARMI allows for thermal expansion of all components by user-defined custom curves.
       :id: IMPL_REACTOR_THERMAL_EXPANSION_0
       :links: REQ_REACTOR_THERMAL_EXPANSION
    """

    DIMENSION_NAMES = tuple()  # will be assigned by ComponentType
    INIT_SIGNATURE = tuple()  # will be assigned by ComponentType

    is3D = False  # flag to show that area is 2D by default

    _COMP_REPORT_GROUPS = {
        "intercoolant": report.INTERCOOLANT_DIMS,
        "bond": report.BOND_DIMS,
        "duct": report.DUCT_DIMS,
        "coolant": report.COOLANT_DIMS,
        "clad": report.CLAD_DIMS,
        "fuel": report.FUEL_DIMS,
        "wire": report.WIRE_DIMS,
        "liner": report.LINER_DIMS,
        "gap": report.GAP_DIMS,
    }

    _TOLERANCE = 1e-10

    THERMAL_EXPANSION_DIMS = set()

    pDefs = componentParameters.getComponentParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        area=None,
        isotopics="",
        mergeWith="",
        components=None,
    ):
        if components and name in components:
            raise ValueError(
                "Non-unique component name {} repeated in same block.".format(name)
            )

        composites.Composite.__init__(self, str(name))
        componentTypeIsValid(self, str(name))
        self.p.area = area
        self.inputTemperatureInC = Tinput
        self.temperatureInC = Thot
        self.material = None
        self.setProperties(material)
        self.applyMaterialMassFracsToNumberDensities()  # not necessary when duplicating...
        self.setType(name)
        self.p.mergeWith = mergeWith
        self.p.customIsotopicsName = isotopics

    @property
    def temperatureInC(self):
        """Return the hot temperature in Celsius."""
        return self.p.temperatureInC

    @temperatureInC.setter
    def temperatureInC(self, value):
        """Set the hot temperature in Celsius."""
        self.p.temperatureInC = value

    @property
    def temperatureInK(self):
        """Current hot temperature in Kelvin."""
        return self.temperatureInC + C_TO_K

    def __lt__(self, other):
        """
        True if a circle encompassing this object has a smaller diameter than one encompassing another component.

        This allows sorting because the Python sort functions only use this method.
        """
        thisOD = self.getBoundingCircleOuterDiameter(cold=True)
        thatOD = other.getBoundingCircleOuterDiameter(cold=True)
        try:
            return thisOD < thatOD
        except:
            raise ValueError(
                "Components 1 ({} with OD {}) and 2 ({} and OD {}) cannot be ordered because their "
                "bounding circle outer diameters are not comparable.".format(
                    self, thisOD, other, thatOD
                )
            )

    def __setstate__(self, state):
        composites.Composite.__setstate__(self, state)
        self.material.parent = self

    def _linkAndStoreDimensions(self, components, **dims):
        """Link dimensions to another component"""
        for key, val in dims.items():
            self.setDimension(key, val)

        if components:
            self.resolveLinkedDims(components)

    def resolveLinkedDims(self, components):
        """Convert dimension link strings to actual links."""
        for dimName in self.DIMENSION_NAMES:
            value = self.p[dimName]
            if not isinstance(value, str):
                continue

            match = COMPONENT_LINK_REGEX.search(value)

            if match:
                try:
                    name = match.group(1)
                    comp = components[name]
                    linkedKey = match.group(2)
                    self.p[dimName] = _DimensionLink((comp, linkedKey))
                except:
                    if value.count(".") > 1:
                        raise ValueError(
                            "Component names should not have periods in them: `{}`".format(
                                value
                            )
                        )
                    else:
                        raise KeyError(
                            "Bad component link `{}` defined as `{}`".format(
                                dimName, value
                            )
                        )

    def setLink(self, key, otherComp, otherCompKey):
        """Set the dimension link."""
        self.p[key] = _DimensionLink((otherComp, otherCompKey))

    def setProperties(self, properties):
        """Apply thermo-mechanical properties of a Material."""
        if isinstance(properties, str):
            mat = materials.resolveMaterialClassByName(properties)()
            # note that the material will not be expanded to natural isotopics
            # here because the user-input blueprints information is not available
        else:
            mat = properties
        self.material = mat
        self.material.parent = self
        self.clearLinkedCache()

    def applyMaterialMassFracsToNumberDensities(self):
        """
        Set the hot number densities for the component based on material mass fractions/density.

        Notes
        -----
        - the density returned accounts for the expansion of the component
          due to the difference in self.inputTemperatureInC and self.temperatureInC
        - After the expansion, the density of the component should reflect the 3d
          density of the material
        """
        # note, that this is not the actual material density, but rather 2D expanded
        # `density3` is 3D density
        # call getProperty to cache and improve speed
        density = self.material.getProperty("density", Tc=self.temperatureInC)

        self.p.numberDensities = densityTools.getNDensFromMasses(
            density, self.material.p.massFrac
        )

        # material needs to be expanded from the material's cold temp to hot,
        # not components cold temp, so we don't use mat.linearExpansionFactor or
        # component.getThermalExpansionFactor.
        # Materials don't typically define the temperature for which their references
        # density is defined so linearExpansionPercent must be called
        coldMatAxialExpansionFactor = (
            1.0 + self.material.linearExpansionPercent(Tc=self.temperatureInC) / 100
        )
        self.changeNDensByFactor(1.0 / coldMatAxialExpansionFactor)

    def adjustDensityForHeightExpansion(self, newHot):
        """
        Change the densities in cases where height of the block/component is changing with expansion.

        Notes
        -----
        Call before setTemperature since we need old hot temp.
        This works well if there is only 1 solid component.
        If there are multiple components expanding at different rates during thermal
        expansion this becomes more complicated and, and axial expansion should be used.
        Multiple expansion rates cannot trivially be accommodated.
        See AxialExpansionChanger.
        """
        self.changeNDensByFactor(1.0 / self.getHeightFactor(newHot))

    def getHeightFactor(self, newHot):
        """
        Return the factor by which height would change by if we did 3D expansion.

        Notes
        -----
        Call before setTemperature since we need old hot temp.
        """
        return self.getThermalExpansionFactor(Tc=newHot, T0=self.temperatureInC)

    def getProperties(self):
        """Return the active Material object defining thermo-mechanical properties."""
        return self.material

    @property
    def liquidPorosity(self):
        return self.parent.p.liquidPorosity

    @liquidPorosity.setter
    def liquidPorosity(self, porosity):
        self.parent.p.liquidPorosity = porosity

    @property
    def gasPorosity(self):
        return self.parent.p.gasPorosity

    @gasPorosity.setter
    def gasPorosity(self, porosity):
        self.parent.p.gasPorosity = porosity

    def __copy__(self):
        """
        Duplicate a component, used for breaking fuel into separate components.
        """
        linkedDims = self._getLinkedDimsAndValues()
        newC = copy.deepcopy(self)
        self._restoreLinkedDims(linkedDims)
        newC._restoreLinkedDims(linkedDims)
        return newC

    def setLumpedFissionProducts(self, lfpCollection):
        """Sets lumped fission product collection on a lfp compatible material if possible"""
        try:
            self.getProperties().setLumpedFissionProducts(lfpCollection)
        except AttributeError:
            # This material doesn't setLumpedFissionProducts because it's a regular
            # material, not a lumpedFissionProductCompatable material
            pass

    def getArea(self, cold=False):
        """
        Get the area of a component in cm^2.

        See Also
        --------
        block.getVolumeFractions: component coolant is typically the "leftover" and is calculated and set here
        """
        area = self.getComponentArea(cold=cold)
        if self.p.get("modArea", None):  # pylint: disable=no-member
            comp, arg = self.p.modArea
            if arg == "sub":
                area -= comp.getComponentArea(cold=cold)
            elif arg == "add":
                area += comp.getComponentArea(cold=cold)
            else:
                raise ValueError("Option {} does not exist".format(arg))

        self._checkNegativeArea(area, cold)
        return area

    def getVolume(self):
        """
        Return the volume [cm^3] of the component.

        Notes
        -----
        ``self.p.volume`` is not set until this method is called,
        so under most circumstances it is probably not safe to
        access ``self.p.volume`` directly. This is because not
        all components (e.g., ``DerivedShape``) can compute
        their volume during initialization.
        """
        if self.p.volume is None:
            self._updateVolume()
            if self.p.volume is None:
                raise ValueError("{} has undefined volume.".format(self))
        return self.p.volume

    def clearCache(self):
        """
        Invalidate the volume so that it will be recomputed from current dimensions upon next access.

        The updated value will be based on its shape and current dimensions.
        If there is a parent container and that container contains a DerivedShape, then that must be
        updated as well since its volume may be changing.

        See Also
        --------
        clearLinkedCache: Clears cache of components that depend on this component's dimensions.
        """
        self.p.volume = None
        if self.parent:
            self.parent.derivedMustUpdate = True

    def _updateVolume(self):
        """Recompute and store volume."""
        self.p.volume = self.computeVolume()

    def computeVolume(self):
        """Compute volume."""
        if not self.is3D:
            volume = self.getArea() * self.parent.getHeight()
        else:
            volume = self.getComponentVolume()

        self._checkNegativeVolume(volume)
        return volume

    def _checkNegativeArea(self, area, cold):
        """
        Check for negative area and warn/error when appropriate.

        Negative component area is allowed for Void materials (such as gaps)
        which may be placed between components that will overlap during thermal expansion
        (such as liners and cladding and annular fuel).

        Overlapping is allowed to maintain conservation of atoms while sticking close
        to the as-built geometry. Modules that need true geometries will have to
        handle this themselves.

        """
        if numpy.isnan(area):
            return

        if area < 0.0:
            if (
                cold and not self.containsVoidMaterial()
            ) or self.containsSolidMaterial():
                negAreaFailure = (
                    "Component {} with {} has cold negative area of {} cm^2. "
                    "This can be caused by component "
                    "overlap with component dimension linking or by invalid inputs.".format(
                        self, self.material, area
                    )
                )
                raise ArithmeticError(negAreaFailure)

    def _checkNegativeVolume(self, volume):
        """Check for negative volume

        See Also
        --------
        self._checkNegativeArea
        """
        if numpy.isnan(volume):
            return

        if volume < 0.0 and self.containsSolidMaterial():
            negVolFailure = (
                "Component {} with {} has cold negative volume of {} cm^3. "
                "This can be caused by component "
                "overlap with component dimension linking or by invalid inputs.".format(
                    self, self.material, volume
                )
            )
            raise ArithmeticError(negVolFailure)

    def containsVoidMaterial(self):
        """Returns True if component material is void."""
        return isinstance(self.material, void.Void)

    def containsSolidMaterial(self):
        """Returns True if the component material is a solid."""
        return not isinstance(self.material, material.Fluid)

    def getComponentArea(self, cold=False):
        """
        Get the area of this component in cm^2.

        Parameters
        ----------
        cold : bool, optional
            Compute the area with as-input dimensions instead of thermally-expanded
        """
        raise NotImplementedError

    def getComponentVolume(self):
        return self.p.volume

    def setVolume(self, val):
        raise NotImplementedError

    def setArea(self, val):
        raise NotImplementedError

    def setTemperature(self, temperatureInC):
        r"""
        Adjust temperature of this component.

        This will cause thermal expansion or contraction of solid or liquid components and will
        accordingly adjust number densities to conserve mass.

        Liquids still have a number density adjustment, but some mass tends to expand in or out of
        the bounding area.

        Since some composites have multiple materials in them that thermally expand differently,
        the axial dimension is generally left unchanged. Hence, this a 2-D thermal expansion.

        Number density change is proportional to mass density change :math:`\frac{d\rho}{\rho}`.
        A multiplicative factor :math:`f_N` to apply to number densities when going from T to T'
        is as follows:

        .. math::

            N^{\prime} = N \cdot f_N \\
            \frac{dN}{N} = f_N - 1

        Since :math:`\frac{dN}{N} \sim\frac{d\rho}{\rho}`, we have:

        .. math::

            f_N  = \frac{d\rho}{\rho} + 1 = \frac{\rho^{\prime}}{\rho}

        """
        prevTemp, self.temperatureInC = self.temperatureInC, float(temperatureInC)
        f = self.material.getThermalExpansionDensityReduction(
            prevTemp, self.temperatureInC
        )
        self.changeNDensByFactor(f)
        self.clearLinkedCache()

    def getNuclides(self):
        """
        Return nuclides in this component.

        This includes anything that has been specified in here, including trace nuclides.
        """
        return list(self.p.numberDensities.keys())

    def getNumberDensity(self, nucName):
        """
        Get the number density of nucName, return zero if it does not exist here.

        Parameters
        ----------
        nucName : str
            Nuclide name

        Returns
        -------
        number density : float
            number density in atoms/bn-cm.
        """
        return self.p.numberDensities.get(nucName, 0.0)

    def getNuclideNumberDensities(self, nucNames):
        """Return a list of number densities for the nuc names requested."""
        return [self.p.numberDensities.get(nucName, 0.0) for nucName in nucNames]

    def _getNdensHelper(self):
        return dict(self.p.numberDensities)

    def setName(self, name):
        """Components use name for type and name."""
        composites.Composite.setName(self, name)
        self.setType(name)

    def setNumberDensity(self, nucName, val):
        """
        Set heterogeneous number density.

        Parameters
        ----------
        nucName : str
            nuclide to modify
        val : float
            Number density to set in atoms/bn-cm (heterogeneous)
        """
        self.p.numberDensities[nucName] = val
        self.p.assigned = parameters.SINCE_ANYTHING
        # necessary for syncMpiState
        parameters.ALL_DEFINITIONS[
            "numberDensities"
        ].assigned = parameters.SINCE_ANYTHING

    def setNumberDensities(self, numberDensities):
        """
        Set one or more multiple number densities. Clears out any number density not listed.

        Parameters
        ----------
        numberDensities : dict
            nucName: ndens pairs.

        Notes
        -----
        We don't just call setNumberDensity for each nuclide because we don't want to call ``getVolumeFractions``
        for each nuclide (it's inefficient).
        """
        self.p.numberDensities = numberDensities

    def updateNumberDensities(self, numberDensities):
        """
        Set one or more multiple number densities. Leaves unlisted number densities alone.

        Parameters
        ----------
        numberDensities : dict
            nucName: ndens pairs.

        """
        self.p.numberDensities.update(numberDensities)
        # since we're updating the object the param points to but not the param itself, we have to inform
        # the param system to flag it as modified so it properly syncs during ``syncMpiState``.
        self.p.assigned = parameters.SINCE_ANYTHING
        self.p.paramDefs["numberDensities"].assigned = parameters.SINCE_ANYTHING

    def getEnrichment(self):
        """Get the mass enrichment of this component, as defined by the material."""
        return self.getMassEnrichment()

    def getMassEnrichment(self):
        """
        Get the mass enrichment of this component, as defined by the material.

        Notes
        -----
        Getting mass enrichment on any level higher than this is ambiguous because you may
        have enriched boron in one pin and enriched uranium in another and blending those doesn't make sense.
        """
        if self.material.enrichedNuclide is None:
            raise ValueError(
                "Cannot get enrichment of {} because `enrichedNuclide` is not defined."
                "".format(self.material)
            )
        enrichedNuclide = nuclideBases.byName[self.material.enrichedNuclide]
        baselineNucNames = [nb.name for nb in enrichedNuclide.element.nuclideBases]
        massFracs = self.getMassFracs()
        massFracEnrichedElement = sum(
            massFrac
            for nucName, massFrac in massFracs.items()
            if nucName in baselineNucNames
        )
        try:
            return (
                massFracs.get(self.material.enrichedNuclide, 0.0)
                / massFracEnrichedElement
            )
        except ZeroDivisionError:
            return 0.0

    def getMass(self, nuclideNames=None):
        r"""
        Determine the mass in grams of nuclide(s) and/or elements in this object.

        .. math::

            \text{mass} = \frac{\sum_i (N_i \cdot V \cdot  A_i)}{N_A \cdot 10^{-24}}

        where
            :math:`N_i` is number density of nuclide i in (1/bn-cm),

            :math:`V` is the object volume in :math:`cm^3`

            :math:`N_A` is Avogadro's number in 1/moles,

            :math:`A_i` is the atomic weight of of nuclide i in grams/mole

        Parameters
        ----------
        nuclideNames : str, optional
            The nuclide/element specifier to get the mass of in the object.
            If omitted, total mass is returned.

        Returns
        -------
        mass : float
            The mass in grams.
        """
        volume = self.getVolume() / (
            self.parent.getSymmetryFactor() if self.parent else 1.0
        )
        return self.getMassDensity(nuclideNames) * volume

    def getMassDensity(self, nuclideNames=None):
        """
        Return the mass density of the component, in g/cc.

        Parameters
        ----------
        nuclideNames : str, optional
            The nuclide/element specifier to get the partial density of in
            the object. If omitted, total density is returned.

        Returns
        -------
        density : float
            The density in grams/cc.
        """
        nuclideNames = self._getNuclidesFromSpecifier(nuclideNames)
        # densities comes from self.p.numberDensities
        densities = self.getNuclideNumberDensities(nuclideNames)
        nDens = {nuc: dens for nuc, dens in zip(nuclideNames, densities)}
        massDensity = densityTools.calculateMassDensity(nDens)
        return massDensity

    def setDimension(self, key, val, retainLink=False, cold=True):
        """
        Set a single dimension on the component.

        Parameters
        ----------
        key : str
            The dimension key (op, ip, mult, etc.)
        val : float
            The value to set on the dimension
        retainLink : bool, optional
            If True, the val will be applied to the dimension of linked
            component which indirectly changes this component's dimensions.
        cold : bool, optional
            If True sets the component cold dimension to the specified value.
        """
        if not key:
            return
        if retainLink and self.dimensionIsLinked(key):
            linkedComp, linkedDimName = self.p[key]
            linkedComp.setDimension(linkedDimName, val, cold=cold)
        else:
            if not cold:
                expansionFactor = (
                    self.getThermalExpansionFactor()
                    if key in self.THERMAL_EXPANSION_DIMS
                    else 1.0
                )
                val /= expansionFactor
            self.p[key] = val

        self.clearLinkedCache()

    def getDimension(self, key, Tc=None, cold=False):
        """
        Return a specific dimension at temperature as determined by key

        Parameters
        ----------
        key : str
            The dimension key (op, ip, mult, etc.)
        Tc : float
            Temperature in C. If None, the current temperature of the component is used.
        cold : bool, optional
            If true, will return cold (input) value of the requested dimension
        """
        dimension = self.p[key]

        if isinstance(dimension, _DimensionLink):
            return dimension.resolveDimension(Tc=Tc, cold=cold)

        if not dimension or cold or key not in self.THERMAL_EXPANSION_DIMS:
            return dimension

        return self.getThermalExpansionFactor(Tc) * dimension

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        """Abstract bounding circle method that should be overwritten by each shape subclass."""
        raise NotImplementedError

    def getCircleInnerDiameter(self, Tc=None, cold=False):
        """Abstract inner circle method that should be overwritten by each shape subclass.

        Notes
        -----
        The inner circle is meaningful for annular shapes, i.e., circle with non-zero ID,
        hexagon with non-zero IP, etc. For shapes with corners (e.g., hexagon, rectangle, etc)
        the inner circle intersects the corners of the inner bound, opposed to intersecting
        the "flats".
        """
        raise NotImplementedError

    def dimensionIsLinked(self, key):
        """True if a the specified dimension is linked to another dimension."""
        return key in self.p and isinstance(self.p[key], _DimensionLink)

    def getDimensionNamesLinkedTo(self, otherComponent):
        """Find dimension names linked to the other component in this component."""
        dimNames = []
        for dimName in self.DIMENSION_NAMES:
            isLinked = self.dimensionIsLinked(dimName)
            if isLinked and self.p[dimName].getLinkedComponent() is otherComponent:
                dimNames.append((dimName, self.p[dimName][1]))
        return dimNames

    def clearLinkedCache(self):
        """Clear this cache and any other dependent volumes."""
        self.clearCache()
        if self.parent:  # pylint: disable=no-member
            # changes in dimensions can affect cached variables such as pitch
            self.parent.cached = {}
            for c in self.getLinkedComponents():
                # no clearCache since parent already updated derivedMustUpdate in self.clearCache()
                c.p.volume = None

    def getLinkedComponents(self):
        """Find other components that are linked to this component."""
        dependents = []
        for child in self.parent.getChildren():
            for dimName in child.DIMENSION_NAMES:
                isLinked = child.dimensionIsLinked(dimName)
                if isLinked and child.p[dimName].getLinkedComponent() is self:
                    dependents.append(child)
        return dependents

    def getThermalExpansionFactor(self, Tc=None, T0=None):
        """
        Retrieves the material thermal expansion fraction.

        Parameters
        ----------
        Tc : float, optional
            Adjusted temperature to get the thermal expansion factor at relative to the reference temperature

        Returns
        -------
        Thermal expansion factor as a percentage (1.0 + dLL), where dLL is the linear expansion factor.
        """
        if isinstance(self.material, (material.Fluid, custom.Custom)):
            return 1.0  # No thermal expansion of fluids or custom materials

        if T0 is None:
            T0 = self.inputTemperatureInC
        if Tc is None:
            Tc = self.temperatureInC

        dLL = self.material.linearExpansionFactor(Tc=Tc, T0=T0)
        if not dLL and abs(Tc - T0) > self._TOLERANCE:
            runLog.error(
                "Linear expansion percent may not be implemented in the {} material class.\n"
                "This method needs to be implemented on the material to allow thermal expansion."
                ".\nReference temperature: {}, Adjusted temperature: {}, Temperature difference: {}, "
                "Specified tolerance: {}".format(
                    self.material, T0, Tc, (Tc - T0), self._TOLERANCE, single=True
                )
            )
            raise RuntimeError(
                "Linear expansion percent may not be implemented in the {} material "
                "class.".format(self.material)
            )
        return 1.0 + dLL

    def printContents(self, includeNuclides=True):
        """Print a listing of the dimensions and composition of this component."""
        runLog.important(self)
        runLog.important(self.setDimensionReport())
        if includeNuclides:
            for nuc in self.getNuclides():
                runLog.important(
                    "{0:10s} {1:.7e}".format(nuc, self.getNumberDensity(nuc))
                )

    def setDimensionReport(self):
        """Gives a report of the dimensions of this component."""
        reportGroup = None
        for componentType, componentReport in self._COMP_REPORT_GROUPS.items():
            if componentType in self.getName():
                reportGroup = componentReport
                break
        if not reportGroup:
            return "No report group designated for {} component.".format(self.getName())
        reportGroup.header = [
            "",
            "Tcold ({0})".format(self.inputTemperatureInC),
            "Thot ({0})".format(self.temperatureInC),
        ]

        dimensions = {
            k: self.p[k]
            for k in self.DIMENSION_NAMES
            if k not in ("modArea", "area") and self.p[k] is not None
        }  # py3 cannot format None
        # Set component name and material
        report.setData("Name", [self.getName(), ""], reportGroup)
        report.setData("Material", [self.getProperties().name, ""], reportGroup)

        for dimName in dimensions:
            niceName = _NICE_DIM_NAMES.get(dimName, dimName)
            refVal = self.getDimension(dimName, cold=True)
            hotVal = self.getDimension(dimName)
            try:
                report.setData(niceName, [refVal, hotVal], reportGroup)
            except ValueError:
                runLog.warning(
                    "{0} has an invalid dimension for {1}. refVal: {2} hotVal: {3}".format(
                        self, dimName, refVal, hotVal
                    )
                )

        # calculate thickness if applicable.
        suffix = None
        if "id" in dimensions:
            suffix = "d"
        elif "ip" in dimensions:
            suffix = "p"

        if suffix:
            coldIn = self.getDimension("i{0}".format(suffix), cold=True)
            hotIn = self.getDimension("i{0}".format(suffix))
            coldOut = self.getDimension("o{0}".format(suffix), cold=True)
            hotOut = self.getDimension("o{0}".format(suffix))

        if suffix and coldIn > 0.0:
            hotThick = (hotOut - hotIn) / 2.0
            coldThick = (coldOut - coldIn) / 2.0
            vals = (
                "Thickness (cm)",
                "{0:.7f}".format(coldThick),
                "{0:.7f}".format(hotThick),
            )
            report.setData(vals[0], [vals[1], vals[2]], reportGroup)

        return report.ALL[reportGroup]

    def updateDims(self, key="", val=None):
        self.setDimension(key, val)

    def mergeNuclidesInto(self, compToMergeWith):
        """
        Set another component's number densities to reflect this one merged into it.

        You must also modify the geometry of the other component and remove this component to conserve atoms.
        """
        # record pre-merged number densities and areas
        aMe = self.getArea()
        aMerge = compToMergeWith.getArea()
        meNDens = {
            nucName: aMe / aMerge * self.getNumberDensity(nucName)
            for nucName in self.getNuclides()
        }
        mergeNDens = {
            nucName: compToMergeWith.getNumberDensity(nucName)
            for nucName in compToMergeWith.getNuclides()
        }
        # set the new homogenized number densities from both. Allow
        # overlapping nuclides.
        for nucName in set(meNDens) | set(mergeNDens):
            compToMergeWith.setNumberDensity(
                nucName, (meNDens.get(nucName, 0.0) + mergeNDens.get(nucName, 0.0))
            )

    def iterComponents(self, typeSpec=None, exact=False):
        if self.hasFlags(typeSpec, exact):
            yield self

    def backUp(self):
        """
        Create and store a backup of the state.

        This needed to be overridden due to linked components which actually have a parameter value of another
        ARMI component.
        """
        linkedDims = self._getLinkedDimsAndValues()
        composites.Composite.backUp(self)
        self._restoreLinkedDims(linkedDims)

    def restoreBackup(self, paramsToApply):
        r"""
        Restore the parameters from perviously created backup.

        This needed to be overridden due to linked components which actually have a parameter value of another
        ARMI component.
        """
        linkedDims = self._getLinkedDimsAndValues()
        composites.Composite.restoreBackup(self, paramsToApply)
        self._restoreLinkedDims(linkedDims)

    def _getLinkedDimsAndValues(self):
        linkedDims = []

        for dimName in self.DIMENSION_NAMES:
            # backUp and restore are called in tight loops, getting the value and
            # checking here is faster than calling self.dimensionIsLinked because that
            # requires and extra p.__getitem__
            try:
                val = self.p[dimName]
            except:
                raise RuntimeError(
                    "Could not find parameter {} defined for {}. Is the desired "
                    "Component class?".format(dimName, self)
                )
            if isinstance(val, _DimensionLink):
                linkedDims.append((self.p.paramDefs[dimName].fieldName, val))
                del self.p[dimName]

        return linkedDims

    def _restoreLinkedDims(self, linkedDims):
        # force update without setting the ".assigned" flag
        for fieldName, value in linkedDims:
            setattr(self.p, fieldName, value)

    def adjustMassEnrichment(self, massFraction):
        """
        Change the mass fraction of this component.

        The nuclides to adjust are defined by the material. This changes whichever nuclides are to
        be enriched vs. the baseline nuclides of that element while holding mass constant. For
        example it might adjust boron or uranium enrichment.

        Conceptually, you could hold number of atoms, volume, or mass constant during this
        operation. Historically ARMI adjusted mass fractions which was meant to keep mass constant.

        If you have 20 mass % Uranium and adjust the enrichment, you will still have 20% Uranium
        mass. But, the actual mass actually might change a bit because the enriched nuclide weighs
        less.

        See Also
        --------
        Material.enrichedNuclide
        """
        if self.material.enrichedNuclide is None:
            raise ValueError(
                "Cannot adjust enrichment of {} because `enrichedNuclide` is not defined."
                "".format(self.material)
            )
        enrichedNuclide = nuclideBases.byName[self.material.enrichedNuclide]
        baselineNucNames = [nb.name for nb in enrichedNuclide.element.nuclideBases]
        massFracsBefore = self.getMassFracs()
        massFracEnrichedElement = sum(
            massFrac
            for nucName, massFrac in massFracsBefore.items()
            if nucName in baselineNucNames
        )

        adjustedMassFracs = {
            self.material.enrichedNuclide: massFracEnrichedElement * massFraction
        }

        baselineNucNames.remove(self.material.enrichedNuclide)
        massFracTotalUnenriched = (
            massFracEnrichedElement - massFracsBefore[self.material.enrichedNuclide]
        )
        for baseNucName in baselineNucNames:
            # maintain relative mass fractions of baseline nuclides.
            frac = massFracsBefore.get(baseNucName, 0.0) / massFracTotalUnenriched
            if not frac:
                continue
            adjustedMassFracs[baseNucName] = (
                massFracEnrichedElement * (1 - massFraction) * frac
            )
        self.setMassFracs(adjustedMassFracs)

    def getIntegratedMgFlux(self, adjoint=False, gamma=False):
        """
        Return the multigroup neutron tracklength in [n-cm/s]

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
        integratedFlux : multigroup neutron tracklength in [n-cm/s]
        """
        if self.p.pinNum is None:
            # no pin-level flux is available
            if not self.parent:
                return numpy.zeros(1)
            volumeFraction = self.getVolume() / self.parent.getVolume()
            return volumeFraction * self.parent.getIntegratedMgFlux(adjoint, gamma)

        # pin-level flux is available. Note that it is NOT integrated on the param level.
        if gamma:
            if adjoint:
                raise ValueError("Adjoint gamma flux is currently unsupported.")
            else:
                pinFluxes = self.parent.p.pinMgFluxesGamma
        else:
            if adjoint:
                pinFluxes = self.parent.p.pinMgFluxesAdj
            else:
                pinFluxes = self.parent.p.pinMgFluxes
        return pinFluxes[self.p.pinNum - 1] * self.getVolume()

    def density(self):
        """Returns the mass density of the object in g/cc."""
        density = composites.Composite.density(self)

        if not density:
            # possible that there are no nuclides in this component yet. In that case, defer to Material.
            density = self.material.density(Tc=self.temperatureInC)

        return density

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
        if self.parent:
            return self.parent.getLumpedFissionProductCollection()
        else:
            return composites.ArmiObject.getLumpedFissionProductCollection(self)

    def getMicroSuffix(self):
        return self.parent.getMicroSuffix()

    def getPitchData(self):
        """
        Return the pitch data that should be used to determine block pitch.

        Notes
        -----
        This pitch data should only be used if this is the pitch defining component in
        a block. The block is responsible for determining which component in it is the
        pitch defining component.
        """
        raise NotImplementedError(
            f"Method not implemented on component {self}. "
            "Please implement if this component type can be a pitch defining component."
        )


class ShapedComponent(Component):
    """A component with well-defined dimensions."""

    pass
