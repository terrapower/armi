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
from typing import Union

import numpy as np

from armi import materials, runLog
from armi.bookkeeping import report
from armi.materials import custom, material, void
from armi.nucDirectory import nuclideBases
from armi.reactor import composites, flags, parameters
from armi.reactor.components import componentParameters
from armi.utils import densityTools
from armi.utils.units import C_TO_K

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
        otherDimension = other.resolveDimension() if isinstance(other, _DimensionLink) else other
        return self.resolveDimension() == otherDimension

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        """Return a string representation of a dimension link.

        These look like ``otherComponentName.otherDimensionName``. For example, if a link were to a
        ``fuel`` component's ``od`` param, the link would render as ``fuel.od``.
        """
        return f"{self[0].name}.{self[1]}"


class ComponentType(composites.CompositeModelType):
    """
    ComponetType is a metaclass for storing and initializing Component subclass types.

    The construction of Component subclasses is being done through factories for ease of user input. As a consequence,
    the ``__init__`` methods' arguments need to be known in order to conform them to the correct format. Additionally,
    the constructors arguments can be used to determine the Component subclasses dimensions.

    Warning
    -------
    The import-time metaclass-based component subclass registration was a good idea, but in practice has caused
    significant confusion and trouble. We will replace this soon with an explicit plugin-based component subclass
    registration system.
    """

    TYPES = dict()  #: :meta hide-value:

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

        # The co_varnames attribute contains arguments and then locals so we must restrict it to just the arguments.
        signature = newType.__init__.__code__.co_varnames[1 : newType.__init__.__code__.co_argcount]

        # INIT_SIGNATURE and DIMENSION_NAMES are in the same order as the method signature
        newType.INIT_SIGNATURE = tuple(signature)
        newType.DIMENSION_NAMES = tuple(k for k in newType.INIT_SIGNATURE if k not in ComponentType.NON_DIMENSION_NAMES)
        return newType


class Component(composites.Composite, metaclass=ComponentType):
    """
    A primitive object in a reactor that has definite area/volume, material and composition.

    Could be fuel pins, cladding, duct, wire wrap, etc. One component object may represent
    multiple physical components via the ``multiplicity`` mechanism.

    .. impl:: Define a physical piece of a reactor.
        :id: I_ARMI_COMP_DEF
        :implements: R_ARMI_COMP_DEF

        The primitive object in an ARMI reactor is a Component. A Component is comprised
        of a shape and composition. This class serves as a base class which all
        Component types within ARMI are built upon. All primitive shapes (such as a
        square, circle, holed hexagon, helix etc.) are derived from this base class.

        Fundamental capabilities of this class include the ability to store parameters
        and attributes which describe the physical state of each Component within the
        ARMI data model.

    .. impl:: Order Components by their outermost diameter (using the < operator).
        :id: I_ARMI_COMP_ORDER
        :implements: R_ARMI_COMP_ORDER

        Determining Component order by outermost diameters is implemented via
        the ``__lt__()`` method, which is used to control ``sort()`` as the
        standard approach in Python. However, ``__lt__()`` does not show up in the API.

    Attributes
    ----------
    temperatureInC : float
        Current temperature of component in celsius.
    inputTemperatureInC : float
        Reference temperature in C at which dimension definitions were input
    temperatureInC : float
        Temperature in C to which dimensions were thermally-expanded upon input.
    material : str or material.Material
        The material object that makes up this component and give it its thermo-mechanical properties.
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

    material: materials.Material

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
        loadFromDb=False,
    ):
        if components and name in components:
            raise ValueError(f"Non-unique component name {name} repeated in same block.")

        composites.Composite.__init__(self, str(name))
        self.p.area = area
        self.inputTemperatureInC = Tinput
        self.temperatureInC = Thot
        self.material = None
        self.setProperties(material)
        if loadFromDb:
            self.applyMaterialMassFracsToNumberDensities()  # not necessary when duplicating
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

        If the bounding circles for both components have identical size, then revert to checking the inner diameter of
        each component for sorting.

        This allows sorting because the Python sort functions only use this method.
        """
        thisOD = self.getBoundingCircleOuterDiameter(cold=True)
        thatOD = other.getBoundingCircleOuterDiameter(cold=True)
        try:
            if thisOD == thatOD:
                thisID = self.getCircleInnerDiameter(cold=True)
                thatID = other.getCircleInnerDiameter(cold=True)
                return thisID < thatID
            else:
                return thisOD < thatOD
        except (NotImplementedError, Exception) as e:
            if isinstance(e, NotImplementedError):
                raise NotImplementedError(f"getCircleInnerDiameter not implemented for at least one of {self}, {other}")
            else:
                raise ValueError(
                    f"Components 1 ({self} with OD {thisOD}) and 2 ({other} and OD {thatOD}) cannot be ordered because "
                    "their bounding circle outer diameters are not comparable."
                )

    def __setstate__(self, state):
        composites.Composite.__setstate__(self, state)
        self.material.parent = self

    def _linkAndStoreDimensions(self, components, **dims):
        """Link dimensions to another component."""
        for key, val in dims.items():
            self.setDimension(key, val)

        if components:
            self.resolveLinkedDims(components)

    def resolveLinkedDims(self, components):
        """Convert dimension link strings to actual links.

        .. impl:: The volume of some defined shapes depend on the solid components surrounding them.
            :id: I_ARMI_COMP_FLUID1
            :implements: R_ARMI_COMP_FLUID

            Some Components are fluids and are thus defined by the shapes surrounding them. This method cycles through
            each dimension defining the border of this Component and converts the name of that Component to a link to
            the object itself. This series of links is then used downstream to resolve dimensional information.
        """
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
                except Exception:
                    if value.count(".") > 1:
                        raise ValueError(
                            f"Name of {self} has a period in it. "
                            f"Components cannot not have periods in their names: `{value}`"
                        )
                    else:
                        raise KeyError(f"Bad component link `{dimName}` defined as `{value}` in {self}")

    def setLink(self, key, otherComp, otherCompKey):
        """Set the dimension link."""
        self.p[key] = _DimensionLink((otherComp, otherCompKey))

    def setProperties(self, properties):
        """Apply thermo-mechanical properties of a Material."""
        if isinstance(properties, str):
            mat = materials.resolveMaterialClassByName(properties)()
            # note that the material will not be expanded to natural isotopics here because the user-input blueprints
            # information is not available
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
        - the density returned accounts for the expansion of the component due to the difference in
          self.inputTemperatureInC and self.temperatureInC
        - After the expansion, the density of the component should reflect the 3D density of the material
        """
        # set material to initial density so it has populated nuclides and material can access nuclide fracs
        # (some properties like thermal expansion depend on nuclide fracs)
        density = 100.0  #  non-physical placeholder density to initialize number density fractions
        self.p.nuclides, self.p.numberDensities = densityTools.getNDensFromMasses(density, self.material.massFrac)

        # Sometimes material thermal expansion depends on its parent's composition (e.g. Pu frac) so setting number
        # densities can sometimes change thermal expansion behavior. Call again so the material has access to its
        # parent's comp when providing the reference initial density. "pseudoDensity" is not the actual material
        # density, but a 2D version of the normal 3D "density" defined for linear expansion.
        densityBasedOnParentComposition = self.material.getProperty("pseudoDensity", Tc=self.temperatureInC)
        self.p.nuclides, self.p.numberDensities = densityTools.getNDensFromMasses(
            densityBasedOnParentComposition, self.material.massFrac
        )

        # material needs to be expanded from the material's cold temp to hot, not components cold temp, so we don't use
        # mat.linearExpansionFactor or component.getThermalExpansionFactor.
        # Materials don't typically define the temperature for which their references density is defined so
        # linearExpansionPercent must be called
        coldMatAxialExpansionFactor = 1.0 + self.material.linearExpansionPercent(Tc=self.temperatureInC) / 100
        self.changeNDensByFactor(1.0 / coldMatAxialExpansionFactor)

    def adjustDensityForHeightExpansion(self, newHot):
        """
        Change the densities in cases where height of the block/component is changing with expansion.

        Notes
        -----
        Call before setTemperature since we need old hot temp. This works well if there is only 1 solid component. If
        there are multiple components expanding at different rates during thermal expansion this becomes more
        complicated and, and axial expansion should be used. Multiple expansion rates cannot trivially be accommodated.
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
        """Return the active Material object defining thermo-mechanical properties.

        .. impl:: Material properties are retrievable.
            :id: I_ARMI_COMP_MAT0
            :implements: R_ARMI_COMP_MAT

            This method returns the material object that is assigned to the Component.

        .. impl:: Components have one-and-only-one material.
            :id: I_ARMI_COMP_1MAT
            :implements: R_ARMI_COMP_1MAT

            This method returns the material object that is assigned to the Component.
        """
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
        """Duplicate a component, used for breaking fuel into separate components."""
        linkedDims = self._getLinkedDimsAndValues()
        newC = copy.deepcopy(self)
        self._restoreLinkedDims(linkedDims)
        newC._restoreLinkedDims(linkedDims)
        return newC

    def setLumpedFissionProducts(self, lfpCollection):
        """Sets lumped fission product collection on a lfp compatible material if possible."""
        try:
            self.getProperties().setLumpedFissionProducts(lfpCollection)
        except AttributeError:
            # This material doesn't setLumpedFissionProducts because it's a regular material, not a
            # lumpedFissionProductCompatable material
            pass

    def getArea(self, cold=False, Tc=None):
        """
        Get the area of a Component in cm^2.

        .. impl:: Get a dimension of a Component.
            :id: I_ARMI_COMP_VOL0
            :implements: R_ARMI_COMP_VOL

            This method returns the area of a Component.

        See Also
        --------
        block.getVolumeFractions: component coolant is typically the "leftover" and is calculated and set here
        """
        area = self.getComponentArea(cold=cold, Tc=Tc)
        if self.p.get("modArea", None):
            comp, arg = self.p.modArea
            if arg == "sub":
                area -= comp.getComponentArea(cold=cold, Tc=Tc)
            elif arg == "add":
                area += comp.getComponentArea(cold=cold, Tc=Tc)
            else:
                raise ValueError(f"Option {arg} does not exist")

        self._checkNegativeArea(area, cold)
        return area

    def getVolume(self):
        """
        Return the volume [cm^3] of the Component.

        .. impl:: Get a dimension of a Component.
            :id: I_ARMI_COMP_VOL1
            :implements: R_ARMI_COMP_VOL

            This method returns the volume of a Component.

        Notes
        -----
        ``self.p.volume`` is not set until this method is called, so under most circumstances it is probably not safe to
        access ``self.p.volume`` directly. This is because not all components (e.g., ``DerivedShape``) can compute their
        volume during initialization.
        """
        if self.p.volume is None:
            self._updateVolume()
            if self.p.volume is None:
                raise ValueError(f"{self} has undefined volume.")
        return self.p.volume

    def clearCache(self):
        """
        Invalidate the volume so that it will be recomputed from current dimensions upon next access.

        The updated value will be based on its shape and current dimensions. If there is a parent container and that
        container contains a DerivedShape, then that must be updated as well since its volume may be changing.

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

        Negative component area is allowed for Void materials (such as gaps) which may be placed between components that
        will overlap during thermal expansion (such as liners and cladding and annular fuel).

        Overlapping is allowed to maintain conservation of atoms while sticking close to the as-built geometry. Modules
        that need true geometries will have to handle this themselves.
        """
        if np.isnan(area):
            return

        if area < 0.0:
            if (cold and not self.containsVoidMaterial()) or self.containsSolidMaterial():
                negAreaFailure = (
                    f"Component {self} with {self.material} has cold negative area of {area} cm^2. "
                    "This can be caused by component overlap with component dimension linking or by invalid inputs."
                )
                raise ArithmeticError(negAreaFailure)

    def _checkNegativeVolume(self, volume):
        """Check for negative volume.

        See Also
        --------
        self._checkNegativeArea
        """
        if np.isnan(volume):
            return

        if volume < 0.0 and self.containsSolidMaterial():
            negVolFailure = (
                f"Component {self} with {self.material} has cold negative volume of {volume} cm^3. "
                "This can be caused by component overlap with component dimension linking or by invalid inputs."
            )
            raise ArithmeticError(negVolFailure)

    def containsVoidMaterial(self):
        """Returns True if component material is void."""
        return isinstance(self.material, void.Void)

    def containsSolidMaterial(self):
        """Returns True if the component material is a solid."""
        return not isinstance(self.material, material.Fluid)

    def getComponentArea(self, cold=False, Tc=None):
        """
        Get the area of this component in cm^2.

        Parameters
        ----------
        cold : bool, optional
            Compute the area with as-input dimensions instead of thermally-expanded
        Tc : float, optional
            Temperature to compute the area at
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

        This will cause thermal expansion or contraction of solid or liquid components and will accordingly adjust
        number densities to conserve mass.

        Liquids still have a number density adjustment, but some mass tends to expand in or out of the bounding area.

        Since some composites have multiple materials in them that thermally expand differently, the axial dimension is
        generally left unchanged. Hence, this a 2-D thermal expansion.

        Number density change is proportional to mass density change :math:`\frac{d\rho}{\rho}`. A multiplicative factor
        :math:`f_N` to apply to number densities when going from T to T' is as follows:

        .. math::

            N^{\prime} = N \cdot f_N \\
            \frac{dN}{N} = f_N - 1

        Since :math:`\frac{dN}{N} \sim\frac{d\rho}{\rho}`, we have:

        .. math::

            f_N  = \frac{d\rho}{\rho} + 1 = \frac{\rho^{\prime}}{\rho}

        """
        prevTemp, self.temperatureInC = self.temperatureInC, float(temperatureInC)
        f = self.material.getThermalExpansionDensityReduction(prevTemp, self.temperatureInC)
        self.changeNDensByFactor(f)
        self.clearLinkedCache()

    def getNuclides(self):
        """
        Return nuclides in this component.

        This includes anything that has been specified in here, including trace nuclides.
        """
        if self.p.nuclides is None:
            return []
        return [nucName.decode() for nucName in self.p.nuclides]

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
        i = np.where(self.p.nuclides == nucName.encode())[0]
        if i.size > 0:
            return self.p.numberDensities[i[0]]
        else:
            return 0.0

    def getNuclideNumberDensities(self, nucNames: list[str]) -> list[float]:
        """Return a list of number densities for the nuc names requested."""
        if isinstance(nucNames, (list, tuple, np.ndarray)):
            byteNucs = np.asanyarray(nucNames, dtype="S6")
        else:
            byteNucs = [nucName.encode() for nucName in nucNames]

        if self.p.numberDensities is None:
            return np.zeros(len(byteNucs), dtype=np.float64)

        # trivial case where nucNames is the full set of nuclides in the same order
        if np.array_equal(byteNucs, self.p.nuclides):
            return np.array(self.p.numberDensities)

        if len(byteNucs) < len(self.p.nuclides) / 10:
            return self._getNumberDensitiesArray(byteNucs)

        nDensDict = dict(zip(self.p.nuclides, self.p.numberDensities))
        return [nDensDict.get(nuc, 0.0) for nuc in byteNucs]

    def _getNumberDensitiesArray(self, byteNucs):
        """
        Get number densities using direct array lookup.

        When only a small subset of nuclide number densities are requested, it is likely faster to lookup the index for
        each nuclide than to recreate the entire dictionary for a lookup.

        Parameters
        ----------
        byteNucs : np.ndarray, dtype="S6"
            List of nuclides for which to retrieve number densities, as encoded byte strings
        """
        ndens = np.zeros(len(byteNucs), dtype=np.float64)
        nuclides = self.p.nuclides
        numberDensities = self.p.numberDensities

        # if it's just a small subset of nuclides, use np.where for direct index lookup
        for i, nuc in enumerate(byteNucs):
            j = np.where(nuclides == nuc)[0]
            if j.size > 0:
                ndens[i] = numberDensities[j[0]]
        return ndens

    def _getNdensHelper(self):
        nucs = self.getNuclides()
        return dict(zip(nucs, self.p.numberDensities)) if len(nucs) > 0 else {}

    def setName(self, name):
        """Components use name for type and name."""
        composites.Composite.setName(self, name)
        self.setType(name)

    def setNumberDensity(self, nucName, val):
        """
        Set heterogeneous number density.

        .. impl:: Setting nuclide fractions.
            :id: I_ARMI_COMP_NUCLIDE_FRACS0
            :implements: R_ARMI_COMP_NUCLIDE_FRACS

            The method allows a user or plugin to set the number density of a Component. It also
            indicates to other processes that may depend on a Component's status about this change
            via the ``assigned`` attribute.

        Parameters
        ----------
        nucName : str
            nuclide to modify
        val : float
            Number density to set in atoms/bn-cm (heterogeneous)
        """
        self.updateNumberDensities({nucName: val})

    def setNumberDensities(self, numberDensities):
        """
        Set one or more multiple number densities. Clears out any number density not listed.

        .. impl:: Setting nuclide fractions.
            :id: I_ARMI_COMP_NUCLIDE_FRACS1
            :implements: R_ARMI_COMP_NUCLIDE_FRACS

            The method allows a user or plugin to set the number densities of a Component. In
            contrast to the ``setNumberDensity`` method, it sets all densities within a Component.

        Parameters
        ----------
        numberDensities : dict
            nucName: ndens pairs.

        Notes
        -----
        We don't just call setNumberDensity for each nuclide because we don't want to call
        ``getVolumeFractions`` for each nuclide (it's inefficient).
        """
        self.updateNumberDensities(numberDensities, wipe=True)

    def updateNumberDensities(self, numberDensities, wipe=False):
        """
        Set one or more multiple number densities. Leaves unlisted number densities alone.

        Parameters
        ----------
        numberDensities : dict
            nucName: ndens pairs.
        wipe : bool, optional
            Controls whether the old number densities are wiped. Any nuclide densities not provided in numberDensities
            will be effectively set to 0.0.

        Notes
        -----
        Sometimes volume/dimensions change due to number density change when the material thermal expansion depends on
        the component's composition (e.g. its plutonium fraction). In this case, changing the density will implicitly
        change the area/volume. Since it is difficult to predict the new dimensions, and perturbation/depletion
        calculations almost exclusively assume constant volume, the densities sent are automatically adjusted to
        conserve mass with the original dimensions. That is, the component's densities are not exactly as passed, but
        whatever they would need to be to preserve volume integrated number densities (moles) from the pre-perturbed
        component's volume/dimensions.

        This has no effect if the material thermal expansion has no dependence on component composition. If this is not
        desired, `self.p.numberDensities` and `self.p.nuclides` can be set directly.
        """
        # prepare to change the densities with knowledge that dims could change due to material thermal expansion
        # dependence on composition
        if self.p.numberDensities is not None and self.p.numberDensities.size > 0:
            dLLprev = self.material.linearExpansionPercent(Tc=self.temperatureInC) / 100.0
            materialExpansion = True
        else:
            dLLprev = 0.0
            materialExpansion = False

        try:
            vol = self.getVolume()
        except (AttributeError, TypeError):
            # Either no parent to get height or parent's height is None. Which would be
            # AttributeError and TypeError respectively, but other errors could be possible.
            vol = None
            area = self.getArea()

        # change the densities
        if wipe:
            self.p.nuclides = np.asanyarray(list(numberDensities.keys()), dtype="S6")
            self.p.numberDensities = np.array(list(numberDensities.values()))
        else:
            newNucs = []
            newNumDens = []
            nucs = self.p.nuclides
            ndens = self.p.numberDensities
            for nucName, dens in numberDensities.items():
                i = np.where(nucs == nucName.encode())[0]
                if i.size > 0:
                    ndens[i[0]] = dens
                else:
                    newNucs.append(nucName.encode())
                    newNumDens.append(dens)
            self.p.nuclides = np.append(nucs, newNucs)
            self.p.numberDensities = np.append(ndens, newNumDens)

        # check if thermal expansion changed
        dLLnew = self.material.linearExpansionPercent(Tc=self.temperatureInC) / 100.0
        if dLLprev != dLLnew and materialExpansion:
            # the thermal expansion changed so the volume change is happening at same time as
            # density change was requested. Attempt to make mass consistent with old dims (since the
            # density change was for the old volume and otherwise mass wouldn't be conserved).

            self.clearLinkedCache()  # enable recalculation of volume, otherwise it uses cached
            if vol is not None:
                factor = vol / self.getVolume()
            else:
                factor = area / self.getArea()
            self.changeNDensByFactor(factor)

        # since we are updating the object the param points to but not the param itself, we have to
        # inform the param system to flag it as modified so it syncs during ``syncMpiState``.
        self.p.assigned = parameters.SINCE_ANYTHING
        self.p.paramDefs["numberDensities"].assigned = parameters.SINCE_ANYTHING

    def changeNDensByFactor(self, factor):
        """Change the number density of all nuclides within the object by a multiplicative factor."""
        if self.p.numberDensities is not None:
            self.p.numberDensities *= factor
        self._changeOtherDensParamsByFactor(factor)

    def _changeOtherDensParamsByFactor(self, factor):
        """Change the number density of all nuclides within the object by a multiplicative factor."""
        if self.p.detailedNDens is not None:
            self.p.detailedNDens *= factor
        # Update pinNDens
        if self.p.pinNDens is not None:
            self.p.pinNDens *= factor

    def getEnrichment(self):
        """Get the mass enrichment of this component, as defined by the material."""
        return self.getMassEnrichment()

    def getMassEnrichment(self):
        """
        Get the mass enrichment of this component, as defined by the material.

        Notes
        -----
        Getting mass enrichment on any level higher than this is ambiguous because you may have
        enriched boron in one pin and uranium in another and blending those doesn't make sense.
        """
        if self.material.enrichedNuclide is None:
            raise ValueError(f"Cannot get enrichment of {self.material} because `enrichedNuclide` is not defined.")
        enrichedNuclide = nuclideBases.byName[self.material.enrichedNuclide]
        baselineNucNames = [nb.name for nb in enrichedNuclide.element.nuclides]
        massFracs = self.getMassFracs()
        massFracEnrichedElement = sum(
            massFrac for nucName, massFrac in massFracs.items() if nucName in baselineNucNames
        )
        try:
            return massFracs.get(self.material.enrichedNuclide, 0.0) / massFracEnrichedElement
        except ZeroDivisionError:
            return 0.0

    def getMass(self, nuclideNames: Union[None, str, list[str]] = None) -> float:
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
        volume = self.getVolume() / (self.parent.getSymmetryFactor() if self.parent else 1.0)
        if nuclideNames is None:
            nDens = self._getNdensHelper()
        else:
            nuclideNames = self._getNuclidesFromSpecifier(nuclideNames)
            # densities comes from self.p.numberDensities
            if len(nuclideNames) > 0:
                densities = self.getNuclideNumberDensities(nuclideNames)
                nDens = dict(zip(nuclideNames, densities))
            else:
                nDens = {}
        return densityTools.calculateMassDensity(nDens) * volume

    def setDimension(self, key, val, retainLink=False, cold=True):
        """
        Set a single dimension on the component.

        .. impl:: Set a Component dimension, considering thermal expansion.
            :id: I_ARMI_COMP_EXPANSION1
            :implements: R_ARMI_COMP_EXPANSION

            Dimensions should be set considering the impact of thermal expansion. This method allows for a user or
            plugin to set a dimension and indicate if the dimension is for a cold configuration or not. If it is not for
            a cold configuration, the thermal expansion factor is considered when setting the dimension.

            If the ``retainLink`` argument is ``True``, any Components linked to this one will also have its dimensions
            changed consistently. After a dimension is updated, the ``clearLinkedCache`` method is called which sets the
            volume of this Component to ``None``. This ensures that when the volume is next accessed it is recomputed
            using the updated dimensions.

        Parameters
        ----------
        key : str
            The dimension key (op, ip, mult, etc.)
        val : float
            The value to set on the dimension
        retainLink : bool, optional
            If True, the val will be applied to the dimension of linked component which indirectly
            changes this component's dimensions.
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
                expansionFactor = self.getThermalExpansionFactor() if key in self.THERMAL_EXPANSION_DIMS else 1.0
                val /= expansionFactor
            self.p[key] = val

        self.clearLinkedCache()

    def getDimension(self, key, Tc=None, cold=False):
        """
        Return a specific dimension at temperature as determined by key.

        .. impl:: Retrieve a dimension at a specified temperature.
            :id: I_ARMI_COMP_DIMS
            :implements: R_ARMI_COMP_DIMS

            Due to thermal expansion, Component dimensions depend on their temperature. This method
            retrieves a dimension from the Component at a particular temperature, if provided. If
            the Component is a LinkedComponent then the dimensions are resolved to ensure that any
            thermal expansion that has occurred to the Components that the LinkedComponent depends
            on is reflected in the returned dimension.

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
        The inner circle is meaningful for annular shapes, i.e., circle with non-zero ID, hexagon
        with non-zero IP, etc. For shapes with corners (e.g., hexagon, rectangle, etc) the inner
        circle intersects the corners of the inner bound, opposed to intersecting the "flats".
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
        if self.parent:
            # changes in dimensions can affect cached variables such as pitch
            self.parent.cached = {}
            for c in self.getLinkedComponents():
                # no clearCache since parent already updated derivedMustUpdate in self.clearCache()
                c.p.volume = None

    def getLinkedComponents(self):
        """Find other components that are linked to this component."""
        dependents = []
        for child in self.parent:
            for dimName in child.DIMENSION_NAMES:
                isLinked = child.dimensionIsLinked(dimName)
                if isLinked and child.p[dimName].getLinkedComponent() is self:
                    dependents.append(child)
        return dependents

    def getThermalExpansionFactor(self, Tc=None, T0=None):
        """
        Retrieves the material thermal expansion fraction.

        .. impl:: Calculates radial thermal expansion factor.
            :id: I_ARMI_COMP_EXPANSION0
            :implements: R_ARMI_COMP_EXPANSION

            This method enables the calculation of the thermal expansion factor for a given material. If the material is
            solid, the difference between ``T0`` and ``Tc`` is used to calculate the thermal expansion factor. If a
            solid material does not have a linear expansion factor defined and the temperature difference is greater
            than a predetermined tolerance, an error is raised. Thermal expansion of fluids or custom materials is
            neglected, currently.

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
                f"Linear expansion percent may not be implemented in the {self.material} material class.\n"
                "This method needs to be implemented on the material to allow thermal expansion."
                f".\nReference temperature: {T0}, Adjusted temperature: {Tc}, Temperature difference: {(Tc - T0)}, "
                f"Specified tolerance: {self._TOLERANCE}",
                single=True,
            )
            raise RuntimeError(
                f"Linear expansion percent may not be implemented in the {self.material} material class."
            )
        return 1.0 + dLL

    def printContents(self, includeNuclides=True):
        """Print a listing of the dimensions and composition of this component."""
        runLog.important(self)
        runLog.important(self.setDimensionReport())
        if includeNuclides:
            for nuc in self.getNuclides():
                runLog.important(f"{nuc:10s} {self.getNumberDensity(nuc):.7e}")

    def setDimensionReport(self):
        """Gives a report of the dimensions of this component."""
        reportGroup = None
        for componentType, componentReport in self._COMP_REPORT_GROUPS.items():
            if componentType in self.getName():
                reportGroup = componentReport
                break
        if not reportGroup:
            return f"No report group designated for {self.getName()} component."
        reportGroup.header = [
            "",
            f"Tcold ({self.inputTemperatureInC})",
            f"Thot ({self.temperatureInC})",
        ]

        dimensions = {
            k: self.p[k] for k in self.DIMENSION_NAMES if k not in ("modArea", "area") and self.p[k] is not None
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
                runLog.warning(f"{self} has an invalid dimension for {dimName}. refVal: {refVal} hotVal: {hotVal}")

        # calculate thickness if applicable.
        suffix = None
        if "id" in dimensions:
            suffix = "d"
        elif "ip" in dimensions:
            suffix = "p"

        if suffix:
            coldIn = self.getDimension(f"i{suffix}", cold=True)
            hotIn = self.getDimension(f"i{suffix}")
            coldOut = self.getDimension(f"o{suffix}", cold=True)
            hotOut = self.getDimension(f"o{suffix}")

        if suffix and coldIn > 0.0:
            hotThick = (hotOut - hotIn) / 2.0
            coldThick = (coldOut - coldIn) / 2.0
            vals = (
                "Thickness (cm)",
                f"{coldThick:.7f}",
                f"{hotThick:.7f}",
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
        # if negative-area gap, treat is as 0.0 and return
        if aMe <= 0.0:
            return
        aMerge = compToMergeWith.getArea()
        meNDens = {nucName: aMe / aMerge * self.getNumberDensity(nucName) for nucName in self.getNuclides()}
        mergeNDens = {nucName: compToMergeWith.getNumberDensity(nucName) for nucName in compToMergeWith.getNuclides()}
        # set the new homogenized number densities from both. Allow overlapping nuclides.
        for nucName in set(meNDens) | set(mergeNDens):
            compToMergeWith.setNumberDensity(nucName, (meNDens.get(nucName, 0.0) + mergeNDens.get(nucName, 0.0)))

    def iterComponents(self, typeSpec=None, exact=False):
        if self.hasFlags(typeSpec, exact):
            yield self

    def backUp(self):
        """
        Create and store a backup of the state.

        This needed to be overridden due to linked components which actually have a parameter value of another ARMI
        component.
        """
        linkedDims = self._getLinkedDimsAndValues()
        composites.Composite.backUp(self)
        self._restoreLinkedDims(linkedDims)

    def restoreBackup(self, paramsToApply):
        """
        Restore the parameters from previously created backup.

        This needed to be overridden due to linked components which actually have a parameter value of another ARMI
        component.
        """
        linkedDims = self._getLinkedDimsAndValues()
        composites.Composite.restoreBackup(self, paramsToApply)
        self._restoreLinkedDims(linkedDims)

    def _getLinkedDimsAndValues(self):
        linkedDims = []

        for dimName in self.DIMENSION_NAMES:
            # backUp and restore are called in tight loops, getting the value and checking here is faster than calling
            # self.dimensionIsLinked because that requires and extra p.__getitem__
            try:
                val = self.p[dimName]
            except Exception:
                raise RuntimeError(
                    f"Could not find parameter {dimName} defined for {self}. Is the desired Component class?"
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

        If you have 20 mass % Uranium and adjust the enrichment, you will still have 20% Uranium mass. But, the actual
        mass actually might change a bit because the enriched nuclide weighs less.

        See Also
        --------
        Material.enrichedNuclide
        """
        if self.material.enrichedNuclide is None:
            raise ValueError(f"Cannot adjust enrichment of {self.material} because `enrichedNuclide` is not defined.")

        enrichedNuclide = nuclideBases.byName[self.material.enrichedNuclide]
        baselineNucNames = [nb.name for nb in enrichedNuclide.element.nuclides]
        massFracsBefore = self.getMassFracs()
        massFracEnrichedElement = sum(
            massFrac for nucName, massFrac in massFracsBefore.items() if nucName in baselineNucNames
        )

        adjustedMassFracs = {self.material.enrichedNuclide: massFracEnrichedElement * massFraction}

        baselineNucNames.remove(self.material.enrichedNuclide)
        massFracTotalUnenriched = massFracEnrichedElement - massFracsBefore[self.material.enrichedNuclide]
        for baseNucName in baselineNucNames:
            # maintain relative mass fractions of baseline nuclides.
            frac = massFracsBefore.get(baseNucName, 0.0) / massFracTotalUnenriched
            if not frac:
                continue
            adjustedMassFracs[baseNucName] = massFracEnrichedElement * (1 - massFraction) * frac
        self.setMassFracs(adjustedMassFracs)

    def getMgFlux(self, adjoint=False, average=False, gamma=False):
        """
        Return the multigroup neutron flux in [n/cm^2/s].

        The first entry is the first energy group (fastest neutrons). Each additional group is the next energy group, as
        set in the ISOTXS library.

        Parameters
        ----------
        adjoint : bool, optional
            Return adjoint flux instead of real
        average : bool, optional
            If True, will return average flux between latest and previous. Does not work for pin detailed.
        gamma : bool, optional
            Whether to return the neutron flux or the gamma flux.

        Returns
        -------
        flux : np.ndarray
            multigroup neutron flux in [n/cm^2/s]
        """
        if average:
            raise NotImplementedError("Component has no method for producing average MG flux -- tryusing blocks")

        volume = self.getVolume() / self.parent.getSymmetryFactor()
        return self.getIntegratedMgFlux(adjoint=adjoint, gamma=gamma) / volume

    def getIntegratedMgFlux(self, adjoint=False, gamma=False):
        """
        Return the multigroup neutron tracklength in [n-cm/s].

        The first entry is the first energy group (fastest neutrons). Each additional group is the next energy group, as
        set in the ISOTXS library.

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
                return np.zeros(1)

            volumeFraction = (self.getVolume() / self.parent.getSymmetryFactor()) / self.parent.getVolume()
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

        return pinFluxes[self.p.pinNum - 1] * self.getVolume() / self.parent.getSymmetryFactor()

    def getPinMgFluxes(self, adjoint: bool = False, gamma: bool = False) -> np.ndarray[tuple[int, int], float]:
        """Retrieves the pin multigroup fluxes for the component.

        Parameters
        ----------
        adjoint : bool, optional
            Return adjoint flux instead of real
        gamma : bool, optional
            Whether to return the neutron flux or the gamma flux.

        Returns
        -------
        np.ndarray
            A ``(N, nGroup)`` array of pin multigroup fluxes, where ``N`` is the equivalent to the multiplicity of the
            component (``self.p.mult``) and ``nGroup`` is the number of energy groups of the flux.

        Raises
        ------
        ValueError
            If the location(s) of the component are not aligned with pin indices from the block. This would happen if
            this component is not actually a pin.
        """
        # If we get a None, for a non-pin thing, the exception block at the bottom will catch that and inform the user.
        # So we don't need to add extra guard rails here.
        indexMap = self.getPinIndices()

        # Get the parameter name we are trying to retrieve
        if gamma:
            if adjoint:
                raise ValueError("Adjoint gamma flux is currently unsupported.")
            else:
                param = "pinMgFluxesGamma"
        else:
            if adjoint:
                param = "pinMgFluxesAdj"
            else:
                param = "pinMgFluxes"

        try:
            return self.parent.p[param][indexMap]
        except Exception as ee:
            msg = f"Failure getting {param} from {self} via parent {self.parent}"
            runLog.error(msg)
            runLog.error(ee)
            raise ValueError(msg) from ee

    def getPinIndices(self) -> np.ndarray[tuple[int], np.uint16]:
        """Find the indices for the locations where this component can be found in the block.

        Returns
        -------
        np.array[int]
            The indices in various Block-level pin methods, e.g., :meth:`armi.reactor.blocks.Block.getPinLocations`,
            that correspond to this component.

        Raises
        ------
        ValueError
            If this does not have pin indices. This can be the case for components that live on blocks without spatial
            grids, or if they do not share lattice sites, via ``spatialLocator`` with other pins.

        See Also
        --------
        :meth`:armi.reactor.blocks.HexBlock.assignPinIndices`
        """
        ix = self.p.pinIndices
        if isinstance(ix, np.ndarray):
            return ix
        # Find a sibling that has pin indices and has the same spatial locator as us
        withPinIndices = (c for c in self.parent if c is not self and c.p.pinIndices is not None)
        for sibling in withPinIndices:
            if sibling.spatialLocator == self.spatialLocator:
                return sibling.p.pinIndices

        msg = f"{self} on {self.parent} has no pin indices."
        raise ValueError(msg)

    def density(self) -> float:
        """Returns the mass density of the object in g/cc."""
        density = composites.Composite.density(self)

        if not density and not isinstance(self.material, void.Void):
            # Possible that there are no nuclides in this component yet. In that case, defer to Material.
            # Material.density is wrapped to warn if it's attached to a parent. Avoid that by calling the inner function
            # directly
            density = self.material.density.__wrapped__(self.material, Tc=self.temperatureInC)

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
        armi.physics.neutronics.fissionProductModel.lumpedFissionProduct.LumpedFissionProduct
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
        This pitch data should only be used if this is the pitch defining component in a block. The block is responsible
        for determining which component in it is the pitch defining component.
        """
        raise NotImplementedError(
            f"Method not implemented on component {self}. "
            "Please implement if this component type can be a pitch defining component."
        )

    def getFuelMass(self) -> float:
        """Return the mass in grams if this is a fueled component."""
        return self.getMass() if self.hasFlags(flags.Flags.FUEL) else 0.0

    def finalizeLoadingFromDB(self):
        """Apply any final actions after creating the component from database.

        This should **only** be called internally by the database loader. Otherwise some properties could be doubly
        applied.

        This exists because the theoretical density is initially defined as a material modification, and then stored as
        a Material attribute. When reading from blueprints, the blueprint loader sets the theoretical density parameter
        from the Material attribute. Component parameters are also set when reading from the database. But, we need to
        set the Material attribute so routines that fetch a material's density property account for the theoretical
        density.
        """
        self.material.adjustTD(self.p.theoreticalDensityFrac)


class ShapedComponent(Component):
    """A component with well-defined dimensions."""
