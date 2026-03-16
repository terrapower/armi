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
Base Material classes.

Most temperatures may be specified in either K or C and the functions will convert for you.
"""

import pickle

import numpy as np

from armi import runLog
from armi.matProps.material import Material as MatPropsMaterial
from armi.nucDirectory import nuclideBases
from armi.reactor.flags import TypeSpec
from armi.utils import densityTools
from armi.utils.units import getTc, getTk

# Setting this to False will globally allow you to access material properties outside their defined bounds. This only
# works for material properties defined purely in Python.
FAIL_ON_RANGE = True

# Need for an memoization optimization to cache YAML-mased materials
PICKLED_YAML_MATS = {}


class Material(MatPropsMaterial):
    r"""
    A material is made up of elements or isotopes. It has bulk properties like density.

    .. impl:: The abstract material class.
        :id: I_ARMI_MAT_PROPERTIES
        :implements: R_ARMI_MAT_PROPERTIES

        The ARMI Materials library is based on the Object-Oriented Programming design approach, and uses this generic
        ``Material`` base class. In this class we define a large number of material properties like density, heat
        capacity, or linear expansion coefficient. Specific materials then subclass this base class to assign particular
        values to those properties.

    .. impl:: Materials generate nuclide mass fractions at instantiation.
        :id: I_ARMI_MAT_FRACS
        :implements: R_ARMI_MAT_FRACS

        An ARMI material is meant to be able to represent real world materials that might be used in the construction of
        a nuclear reactor. As such, they are not just individual nuclides, but practical materials like a particular
        concrete, steel, or water. One of the main things that will be needed to describe such a material is the exact
        nuclide fractions. As such, the constructor of every Material subclass attempts to set these mass fractions.

    Attributes
    ----------
    parent : Component
        The component to which this material belongs
    massFrac : dict
        Mass fractions for all nuclides in the material keyed on the nuclide symbols
    refDens : float
        A reference density used by some materials, for instance `SimpleSolid`\ s, during thermal expansion
    theoreticalDensityFrac : float
        Fraction of the material's density in reality, which is commonly different from 1.0 in solid materials due to
        the manufacturing process. Can often be set from the blueprints input via the TD_frac material modification. For
        programmatic setting, use `adjustTD()`.

    Notes
    -----
    Specific material classes may have many more attributes specific to the implementation for that material.
    """

    DATA_SOURCE = "ARMI"
    """Indication of where the material is loaded from (may be plugin name)"""

    references = {}
    """The literature references {property : citation}"""

    enrichedNuclide = None
    """Name of enriched nuclide to be interpreted by enrichment modification methods"""

    propertyValidTemperature = {}
    """Dictionary of valid temperatures over which the property models are valid in the format
    'Property Name': ((Temperature_Lower_Limit, Temperature_Upper_Limit), Temperature_Units)"""

    def __new__(cls):
        # split the creation of new Material objects between YAML/cached and pure Python
        if cls.YAML_PATH is not None:
            # handle matProps / YAML materials
            if cls.YAML_PATH not in PICKLED_YAML_MATS:
                mat = MatPropsMaterial.__new__(cls)
                mat.__init__()
                PICKLED_YAML_MATS[cls.YAML_PATH] = pickle.dumps(mat)
                return mat
            else:
                return pickle.loads(PICKLED_YAML_MATS[cls.YAML_PATH])
        else:
            # pure Python materials
            mat = super().__new__(cls)
            return mat

    def __init__(self):
        MatPropsMaterial.__init__(self)
        if hasattr(self, "cached"):
            #print(f"TODO: OKAY, skipping Material init: {self.name}")
            return

        self.parent = None
        self.massFrac = {}
        self.refDens = 0.0
        self.theoreticalDensityFrac = 1.0
        self.cached = {}
        self._backupCache = None

        if self.name is None:
            #print(self.name)
            # This material does not have a YAML file to pull the name from.
            self.name = self.__class__.__name__
            #print(self.name)

        # call subclass implementations
        self.setDefaultMassFracs()

    def __repr__(self):
        return f"<Material: {self.name}>"

    def __reduce__(self):
        """Tell pickle how to reconstruct this class.

        Since we are unpickling in the __new__ constructor, we need this helper to avoid recursion.
        """
        return (object.__new__, (self.__class__,), self.__dict__)

    def getName(self):
        """Duplicate of name property, kept for backwards compatibility."""
        return self.name

    def getChildren(self, deep=False, generationNum=1, includeMaterials=False, predicate=None):
        """Return empty list, representing that materials have no children."""
        return []

    def getChildrenWithFlags(self, typeSpec: TypeSpec, exactMatch=True):
        """Return empty list, representing that this object has no children."""
        return []

    def backUp(self):
        """Create and store a backup of the state."""
        self._backupCache = (self.cached, self._backupCache)
        self.cached = {}  # don't .clear(), using reference above!

    def restoreBackup(self, paramsToApply):
        """Restore the parameters from previously created backup."""
        self.cached, self._backupCache = self._backupCache

    def clearCache(self):
        """Clear the cache so all new values are recomputed."""
        self.cached = {}

    def _getCached(self, name):
        """Obtain a value from the cache."""
        return self.cached.get(name, None)

    def _setCache(self, name, val):
        """
        Set a value in the cache.

        See Also
        --------
        _getCached : returns a previously-cached value
        """
        self.cached[name] = val

    def duplicate(self):
        """Copy without needing a deepcopy."""
        m = self.__class__()

        m.massFrac = {}
        for key, val in self.massFrac.items():
            m.massFrac[key] = val

        m.parent = self.parent
        m.refDens = self.refDens
        m.theoreticalDensityFrac = self.theoreticalDensityFrac

        # handle some special cases for subclasses, like fuels
        if hasattr(self, "class1_wt_frac"):
            m.class1_wt_frac = self.class1_wt_frac
        if hasattr(self, "class1_custom_isotopics"):
            m.class1_custom_isotopics = self.class1_custom_isotopics
        if hasattr(self, "class2_custom_isotopics"):
            m.class2_custom_isotopics = self.class2_custom_isotopics

        return m

    def linearExpansion(self, Tk: float = None, Tc: float = None) -> float:
        """
        The instantaneous linear expansion coefficient (dL/L)/dT.

        This is used for reactivity coefficients, etc. but will not affect density or dimensions.

        See Also
        --------
        linearExpansionPercent : average linear thermal expansion to affect dimensions and density
        """
        if hasattr(self, "alpha_inst") and self.alpha_inst is not None:
            Tc = getTc(Tc, Tk)
            return self.alpha_inst(T=Tc)
        else:
            Tk = getTk(Tc, Tk)
            deltaStrain = self.linearExpansionPercent(Tk + 1.0) / 100.0 - self.linearExpansionPercent(Tk - 1.0) / 100.0
            return deltaStrain / 2.0

    def linearExpansionPercent(self, Tk: float = None, Tc: float = None) -> float:
        """
        Average thermal expansion dL/L. Used for computing hot dimensions and density.

        Defaults to 0.0 for materials that don't expand.

        Parameters
        ----------
        Tk : float
            temperature in (K)
        Tc : float
            Temperature in (C)

        Returns
        -------
        dLL(T) in % m/m/K

        See Also
        --------
        linearExpansion : handle instantaneous thermal expansion coefficients
        """
        if hasattr(self, "dl_l") and self.dl_l is not None:
            Tc = getTc(Tc, Tk)
            return self.dl_l(T=Tc)
        else:
            return 0.0

    def linearExpansionFactor(self, Tc: float, T0: float) -> float:
        """
        Return a dL/L factor relative to T0 instead of the material-dependent reference temperature.

        Notes
        -----
        For a detailed description of the linear expansion methodology, see "thermalExpansion" in the documentation.

        Parameters
        ----------
        Tc : float
            Current (hot) temperature in C
        T0 : float
            Cold temperature in C

        Returns
        -------
        dLL: float
            The average thermal expansion between Tc and T0. If there is no dLL, it should return 0.0.

        See Also
        --------
        linearExpansionPercent
        """
        dLLhot = self.linearExpansionPercent(Tc=Tc)
        dLLcold = self.linearExpansionPercent(Tc=T0)

        return (dLLhot - dLLcold) / (100.0 + dLLcold)

    def getThermalExpansionDensityReduction(self, prevTempInC: float, newTempInC: float) -> float:
        """Return the factor required to update thermal expansion going from temperatureInC to temperatureInCNew."""
        dLL = self.linearExpansionFactor(Tc=newTempInC, T0=prevTempInC)
        return 1.0 / (1 + dLL) ** 2

    def setDefaultMassFracs(self):
        """
        Mass fractions.

        This method pulls the material composition from the material YAML definition file. Alternatively, this method
        can be over-riden by in Python to declare the default mass fractions using some custom logic.
        """
        # If there is a YAML file, try to pull the material composition from there.
        massFracs = {}
        balanceNuc = None
        for constituent in self.composition:
            nomen = constituent.name.upper()
            if constituent.isBalance:
                massFracs[nomen] = "balance"
                balanceNuc = nomen
            else:
                # If the YAML defines a range of possible fractions, take the average.
                massFracs[nomen] = (constituent.maxValue + constituent.minValue) / 200.0

        if balanceNuc:
            massFracs[balanceNuc] = 1.0 - sum(v for k, v in massFracs.items() if k != balanceNuc)

        for nucName in sorted(massFracs.keys()):
            self.setMassFrac(nucName, massFracs[nucName])

    def setMassFrac(self, nucName: str, massFrac: float) -> None:
        """
        Assigns the mass fraction of a nuclide within the material.

        Notes
        -----
        This will try to convert the provided ``massFrac`` into a float for assignment. If the conversion cannot occur
        then an error will be thrown.
        """
        try:
            massFrac = float(massFrac)
        except Exception as ee:
            raise TypeError(
                f"Error in converting the mass fraction of {massFrac} for nuclide {nucName} in {self} to a float. "
                f"Exception: {ee}"
            )

        if massFrac < 0.0 or massFrac > 1.0:
            raise ValueError(f"Mass fraction of {massFrac} for {nucName} is not between 0 and 1.")

        self.massFrac[nucName] = massFrac

    def applyInputParams(self, **kwargs) -> None:
        """Apply material-specific material input parameters."""
        # handle a common use-case where people set the theoretical density fraction
        if "TD_frac" in kwargs:
            td = kwargs["TD_frac"]
            if td is not None:
                if td > 1.0 or td <= 0.0:
                    runLog.warning(f"Theoretical density frac for {self} is out of range: {td}", single=True)
                self.adjustTD(td)

        # If this material declares an enrichment nuclide, see if we need to enrich this material
        if self.enrichedNuclide:
            enrichFrac = f"{self.enrichedNuclide}_wt_frac"
            if enrichFrac in kwargs and kwargs[enrichFrac] is not None:
                self.adjustMassEnrichment(kwargs[enrichFrac])

    def adjustMassEnrichment(self, massEnrichment: float) -> None:
        """
        Adjust the enrichment of the material.

        See Also
        --------
        adjustMassFrac
        """
        self.adjustMassFrac(self.enrichedNuclide, massEnrichment)

    def adjustMassFrac(self, nuclideName: str, massFraction: float) -> None:
        """
        Change the mass fraction of the specified nuclide.

        This adjusts the mass fraction of a specified nuclide relative to other nuclides of the same element. If there
        are no other nuclides within the element, then it is enriched relative to the entire material. For example,
        enriching U235 in UZr would enrich U235 relative to U238 and other naturally occurring uranium isotopes.
        Likewise, enriching ZR in UZr would enrich ZR relative to Uranium.

        The method maintains a constant number of atoms, and adjusts ``refDens`` accordingly.

        Parameters
        ----------
        nuclideName : str
            Name of nuclide to enrich.
        massFraction : float
            New mass fraction to achieve.
        """
        if massFraction > 1.0 or massFraction < 0.0:
            raise ValueError(f"Cannot enrich to massFraction of {massFraction}, must be between 0 and 1")

        nucsNames = list(self.massFrac)

        # refDens could be zero, but cannot normalize to zero
        density = self.refDens or 1.0
        massDensities = np.array([self.massFrac[nuc] for nuc in nucsNames]) * density
        atomicMasses = np.array([nuclideBases.byName[nuc].weight for nuc in nucsNames])  # in AMU
        molesPerCC = massDensities / atomicMasses  # item-wise division

        enrichedIndex = nucsNames.index(nuclideName)
        isoAndEles = nuclideBases.byName[nuclideName].element.nuclides
        allIndicesUpdated = [nucsNames.index(nuc.name) for nuc in isoAndEles if nuc.name in self.massFrac]

        if len(allIndicesUpdated) == 1:
            if isinstance(
                nuclideBases.byName[nuclideName], nuclideBases.NaturalNuclideBase
            ) or nuclideBases.isMonoIsotopicElement(nuclideName):
                # If there are not any other nuclides, assume we are enriching an entire element. Consequently,
                # allIndicesUpdated is no longer the element's indices, but the materials indices
                allIndicesUpdated = range(len(nucsNames))
            else:
                raise ValueError(  # could be warning if problematic
                    f"Nuclide {nuclideName} was to be enriched in material {self}, but there were no other isotopes of "
                    "that element. Could not assume the enrichment of the entire element as there were other possible "
                    "isotopes that did not exist in this material."
                )

        if massFraction == 1.0:
            massDensities[allIndicesUpdated] = 0.0
            massDensities[enrichedIndex] = 1.0
        else:
            balanceWeight = massDensities[allIndicesUpdated].sum() - massDensities[enrichedIndex]
            if balanceWeight == 0.0:
                onlyOneOtherFracToDetermine = len(allIndicesUpdated) == 2
                if not onlyOneOtherFracToDetermine:
                    raise ValueError(
                        f"Material {self} has too many masses set to zero. cannot enrich {nuclideName} to "
                        f"{massFraction}. Current mass fractions: {self.massFrac}"
                    )
                # massDensities get normalized later when conserving atoms; these are just ratios
                massDensities[allIndicesUpdated] = 1 - massFraction  # there is only one other.
                massDensities[enrichedIndex] = massFraction
            else:
                # derived from solving the following equation for enrchedWeight:
                # massFraction = enrichedWeight / (enrichedWeight + balanceWeight)
                massDensities[enrichedIndex] = massFraction * balanceWeight / (1 - massFraction)

        # ratio is set by here but atoms not conserved yet
        updatedNucsMolesPerCC = massDensities[allIndicesUpdated] / atomicMasses[allIndicesUpdated]
        updatedNucsMolesPerCC *= molesPerCC[allIndicesUpdated].sum() / updatedNucsMolesPerCC.sum()  # conserve atoms
        molesPerCC[allIndicesUpdated] = updatedNucsMolesPerCC

        updatedMassDensities = molesPerCC * atomicMasses
        updatedDensity = updatedMassDensities.sum()
        massFracs = updatedMassDensities / updatedDensity

        if not np.isclose(sum(massFracs), 1.0, atol=1e-10):
            raise RuntimeError(f"The mass fractions {massFracs} in {self} do not sum to 1.0.")

        self.massFrac = {nuc: weight for nuc, weight in zip(nucsNames, massFracs)}
        if self.refDens != 0.0:
            # Do not update density if not assigned.
            self.refDens = updatedDensity

    @property
    def liquidPorosity(self) -> float:
        """Fraction of the material that is liquid void (unitless)."""
        return 0.0 if self.parent is None else self.parent.liquidPorosity

    @property
    def gasPorosity(self) -> float:
        """Fraction of the material that is gas void (unitless)."""
        return 0.0 if self.parent is None else self.parent.gasPorosity

    def pseudoDensity(self, Tk: float = None, Tc: float = None) -> float:
        """
        Return density that preserves mass when thermally expanded in 2D (in g/cm^3).

        This is not a material property that is physically measurable in the laboratory. This is merely the product of
        real density with a factor derived from linear expansion. This method is purely a helper method, useful to
        people modeling pin-type reactors.

        See Also
        --------
        armi.reactor.components.component.Component.density
        """
        Tk = getTk(Tc, Tk)
        density = self.density(Tk=Tk)
        dLL = self.linearExpansionPercent(Tk=Tk)

        f = 1.0 + dLL / 100.0
        return density * f

    def density(self, Tk: float = None, Tc: float = None) -> float:
        """
        Return density that preserves mass when thermally expanded in 3D (in g/cm^3).

        Notes
        -----
        If this material has a parent, Component.density and Material.density can diverge. Thus, careful attention must
        be paid to which of these you call in your downstream code.

        Since refDens is specified at the material-dep reference case, we don't need to specify the reference
        temperature. It is already consistent with linearExpansion Percent.
        - p*(dp/p(T) + 1) =p*( p + dp(T) )/p = p + dp(T) = p(T)
        - dp/p = (1-(1 + dL/L)**3)/(1 + dL/L)**3
        """
        # try the YAML file first
        if hasattr(self, "rho") and self.rho is not None:
            Tc = getTc(Tc, Tk)
            # matProps does density is in kg/m3, and this method is in g/cm3
            return self.rho(T=Tc, TD=self.getTD()) / 1000.0

        # no YAML, use linear expansion
        Tk = getTk(Tc, Tk)
        dLL = self.linearExpansionPercent(Tk=Tk)
        refD = self.refDens
        if refD is None:
            runLog.warning(f"{self} has no reference density", single=True, label=f"No refD {self.getName()}")
            return None

        f = (1.0 + dLL / 100.0) ** 3
        return refD / f

    def dynamicVisc(self, Tk: float = None, Tc: float = None) -> float:
        """Dynamic viscosity in Pa-s."""
        Tc = getTc(Tc, Tk)
        return self.mu_d(T=Tc)

    def enthalpy(self, Tk: float = None, Tc: float = None) -> float:
        """Return enthalpy in J/kg."""
        Tc = getTc(Tc, Tk)
        return self.H(T=Tc)

    def yieldStrength(self, Tk: float = None, Tc: float = None) -> float:
        """Returns yield strength at given T in MPa."""
        Tc = getTc(Tc, Tk)
        return self.Sy(T=Tc)

    def thermalConductivity(self, Tk: float = None, Tc: float = None) -> float:
        """Thermal conductivity for given T (in units of W/m/K)."""
        Tc = getTc(Tc, Tk)
        return self.k(T=Tc)

    def getProperty(self, propName: str, Tk: float = None, Tc: float = None, **kwargs) -> float:
        """
        Gets properties in a way that caches them.

        Notes
        -----
        Try not to use this method. This exists for backwards compatibility only. Use methods like density instead.
        """
        Tk = getTk(Tc, Tk)

        cached = self._getCached(propName)
        if cached and cached[0] == Tk:
            # only use cached value if the temperature at which it is cached is the same.
            return cached[1]
        else:
            # go look it up from material properties.
            val = getattr(self, propName)(Tk=Tk, **kwargs)
            # cache only one value for each property. Prevents unbounded cache explosion.
            self._setCache(propName, (Tk, val))
            return val

    def getMassFrac(self, nucName=None, normalized=True, expandFissionProducts=False):
        """
        Return mass fraction of nucName.

        Parameters
        ----------
        nucName : str, optional
            Nuclide name to return ('ZR','PU239',etc.)
        normalized : bool, optional
            Return the mass fraction such that the sum of all nuclides is sum to 1.0. Default True

        Notes
        -----
        self.massFrac are modified mass fractions that may not add up to 1.0 (for instance, after a axial expansion, the
        modified mass fracs will sum to less than one. The alternative is to put a multiplier on the density. They are
        mathematically equivalent.

        This function returns the normalized mass fraction (they will add to 1.0) as long as the mass fracs are modified
        only by get and setMassFrac.

        This is a performance-critical method as it is called millions of times in a typical ARMI run.

        See Also
        --------
        setMassFrac
        """
        return self.massFrac.get(nucName, 0.0)

    def clearMassFrac(self) -> None:
        """Zero out all nuclide mass fractions."""
        self.massFrac.clear()

    def checkPropertyTempRange(self, label, val):
        """Checks if the given property / value combination fall between the min and max valid temperatures provided in
        the propertyValidTemperature object.

        Parameters
        ----------
        label : str
            The name of the function or property that is being checked.
        val : float
            The value to check whether it is between minT and maxT.

        Notes
        -----
        - This is a wrapper method around ``checkTempRange``.
        - This method is used to aid defining pure Python materials outside of a matProps YAML file.
        """
        (minT, maxT) = self.propertyValidTemperature[label][0]
        self.checkTempRange(minT, maxT, val, label)

    def checkTempRange(self, minT, maxT, val, label=""):
        """
        Checks if the given temperature (val) is between the minT and maxT temperature limits supplied.

        Label identifies what material type or element is being evaluated in the check.

        This method is used to aid defining pure Python materials outside of a matProps YAML file.

        Parameters
        ----------
        minT, maxT : float
            The minimum and maximum values that val is allowed to have.
        val : float
            The value to check whether it is between minT and maxT.
        label : str
            The name of the function or property that is being checked.

        Notes
        -----
        This method is used to aid defining pure Python materials outside of a matProps YAML file.
        """
        if not minT <= val <= maxT:
            msg = f"Temperature {val} out of range ({minT} to {maxT}) for {self.name} {label}"
            if FAIL_ON_RANGE or np.isnan(val):
                runLog.error(msg)
                raise ValueError(msg)
            else:
                runLog.warning(msg, single=True, label=f"T out of bounds for {self.name} {label}")

    def heatCapacity(self, Tk=None, Tc=None):
        """Returns heat capacity in units of J/kg/C."""
        if hasattr(self, "c_p") and self.c_p is not None:
            Tc = getTc(Tc, Tk)
            return self.c_p(T=Tc)
        else:
            raise NotImplementedError(f"Material {type(self).__name__} does not implement heatCapacity")

    def getTD(self):
        """Get the fraction of theoretical density for this material."""
        return self.theoreticalDensityFrac

    def adjustTD(self, val):
        """Set or change the fraction of theoretical density for this material."""
        self.theoreticalDensityFrac = val
        self.clearCache()


class Fluid(Material):
    """A material that fills its container. Could also be a gas."""

    def pseudoDensity(self, Tk: float = None, Tc: float = None) -> float:
        """Density and pseudoDensity are the same for Fluids."""
        return self.density(Tk=Tk, Tc=Tc)

    def getThermalExpansionDensityReduction(self, prevTempInC, newTempInC):
        """Return the factor required to update thermal expansion going from one temperature (in C) to a another."""
        rho0 = self.density(Tc=prevTempInC)
        if not rho0:
            return 1.0

        rho1 = self.density(Tc=newTempInC)
        return rho1 / rho0

    def linearExpansion(self, Tk=None, Tc=None):
        """For fluids, lets just not allow temperature changes to change dimensions since it is a liquid it will fill
        its space.

        .. impl:: Fluid materials are not thermally expandable.
            :id: I_ARMI_MAT_FLUID
            :implements: R_ARMI_MAT_FLUID

            ARMI does not model thermal expansion of fluids. The ``Fluid`` superclass therefore sets the thermal
            expansion coefficient to zero. All fluids subclassing  the ``Fluid`` material will inherit this method which
            sets the linear expansion coefficient to zero at all temperatures.
        """
        return 0.0

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """By default, fluids are considered incompresible."""
        return 0.0


class SimpleSolid(Material):
    """Base material for a simple material that primarily defines density."""

    refTempK = 300

    def __init__(self):
        Material.__init__(self)
        self.refDens = self.density(Tk=self.refTempK)

    def pseudoDensity(self, Tk: float = None, Tc: float = None) -> float:
        """A 2D density, for materials linearly expanding (in g/cm^3)."""
        return Material.pseudoDensity(self, Tk=Tk, Tc=Tc) * self.getTD()


class FuelMaterial(Material):
    """
    Material that is considered a nuclear fuel.

    All this really does is enable the special class 1/class 2 isotopics input option.
    """

    def __init__(self):
        Material.__init__(self)
        self.class1_wt_frac = None
        self.class1_custom_isotopics = None
        self.class2_custom_isotopics = None

    def applyInputParams(
        self,
        class1_custom_isotopics=None,
        class2_custom_isotopics=None,
        class1_wt_frac=None,
        customIsotopics=None,
        *args,
        **kwargs,
    ):
        """Apply optional class 1/class 2 custom enrichment input.

        Notes
        -----
        This is often overridden to insert customized material modification parameters but then this parent should
        always be called at the end in case users want to use this style of custom input.

        This is only applied to materials considered fuel so we don't apply these kinds of parameters to coolants and
        structural material, which are often not parameterized with any kind of enrichment.
        """
        if class1_wt_frac:
            if not 0 <= class1_wt_frac <= 1:
                raise ValueError(
                    f"class1_wt_frac must be between 0 and 1 (inclusive). Right now it is {class1_wt_frac}."
                )

            validIsotopics = customIsotopics.keys()
            errMsg = "{} '{}' not found in the defined custom isotopics."
            if class1_custom_isotopics not in validIsotopics:
                raise KeyError(errMsg.format("class1_custom_isotopics", class1_custom_isotopics))
            if class2_custom_isotopics not in validIsotopics:
                raise KeyError(errMsg.format("class2_custom_isotopics", class2_custom_isotopics))
            if class1_custom_isotopics == class2_custom_isotopics:
                runLog.warning(
                    "The custom isotopics specified for the class1/class2 materials are both "
                    f"'{class1_custom_isotopics}'. You are not actually blending anything!"
                )

            self.class1_wt_frac = class1_wt_frac
            self.class1_custom_isotopics = class1_custom_isotopics
            self.class2_custom_isotopics = class2_custom_isotopics

            self._applyIsotopicsMixFromCustomIsotopicsInput(customIsotopics)

        Material.applyInputParams(self, *args, **kwargs)

    def _applyIsotopicsMixFromCustomIsotopicsInput(self, customIsotopics):
        """
        Apply a Class 1/Class 2 mixture of custom isotopics at input.

        Only adjust heavy metal.

        This may also be needed for building charge assemblies during reprocessing, but will take input from the SFP
        rather than from the input external feeds.
        """
        class1Isotopics = customIsotopics[self.class1_custom_isotopics]
        class2Isotopics = customIsotopics[self.class2_custom_isotopics]
        densityTools.applyIsotopicsMix(self, class1Isotopics, class2Isotopics)
