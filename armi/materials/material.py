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
# pylint: disable=unused-argument
import copy
import warnings

from scipy.optimize import fsolve
import numpy

from armi import runLog
from armi.nucDirectory import nuclideBases
from armi.reactor.flags import TypeSpec
from armi.utils import densityTools
from armi.utils.units import getTk, getTc

# globals
FAIL_ON_RANGE = False


class Material:
    """
    A material is made up of elements or isotopes. It has bulk properties like mass density.

    Attributes
    ----------
    parent : Component
        The component to which this material belongs
    massFrac : dict
        Mass fractions for all nuclides in the material keyed on the nuclide symbols
    refDens : float
        A reference density used by some materials, for instance `SimpleSolid`s,
        during thermal expansion
    theoreticalDensityFrac : float
        Fraction of the material's density in reality, which is commonly different
        from 1.0 in solid materials due to the manufacturing process.
        Can often be set from the blueprints input via the TD_frac material modification.
        For programmatic setting, use `adjustTD()`.

    Notes
    -----
    Specific material classes may have many more attributes specific to the implementation
    for that material.
    """

    DATA_SOURCE = "ARMI"
    """Indication of where the material is loaded from (may be plugin name)"""

    name = "Material"
    """String identifying the material"""

    references = {}
    """The literature references {property : citation}"""

    enrichedNuclide = None
    """Name of enriched nuclide to be interpreted by enrichment modification methods"""

    modelConst = {}
    """Constants that may be used in intepolation functions for property lookups"""

    propertyValidTemperature = {}
    """Dictionary of valid temperatures over which the property models are valid in the format
    'Property Name': ((Temperature_Lower_Limit, Temperature_Upper_Limit), Temperature_Units)"""

    thermalScatteringLaws = ()
    """A tuple of :py:class:`~armi.nucDirectory.thermalScattering.ThermalScattering` instances
    with information about thermal scattering."""

    def __init__(self):
        self.parent = None
        self.massFrac = {}
        self.refDens = 0.0
        self.theoreticalDensityFrac = 1.0
        self.cached = {}
        self._backupCache = None

        # call subclass implementations
        self.setDefaultMassFracs()

    def __repr__(self):
        return "<Material: {0}>".format(self.getName())

    def getName(self):
        return self.name

    def getChildren(
        self, deep=False, generationNum=1, includeMaterials=False, predicate=None
    ):
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
        r"""copy without needing a deepcopy."""
        m = self.__class__()

        m.massFrac = {}
        for key, val in self.massFrac.items():
            m.massFrac[key] = val

        m.parent = self.parent
        m.refDens = self.refDens
        m.theoreticalDensityFrac = self.theoreticalDensityFrac

        return m

    def linearExpansion(self, Tk: float = None, Tc: float = None) -> float:
        r"""
        the instantaneous linear expansion coefficient (dL/L)/dT

        This is used for reactivity coefficients, etc. but will not affect
        density or dimensions.

        See Also
        --------
        linearExpansionPercent : average linear thermal expansion to affect dimensions and density
        """
        raise NotImplementedError(
            f"{self} does not have a linear expansion property defined"
        )

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
        return 0.0

    def linearExpansionFactor(self, Tc: float, T0: float) -> float:
        """
        Return a dL/L factor relative to T0 instead of to the material-dependent reference
        temperature. This factor dL/Lc is a ratio and will be used in dimensions through the
        formula::

            dim = dim0*(1+dLL).

        If there is no dLL, it should return 0.0

        calculate thermal expansion based on dL/L0, which is dependent on the mat-dep ref temp.::

             L(T) = L0(1+dL/L0)
             (Lh-Lc)/L0 = dL/L0(Th) - dL/L0(Tc)
             (Lh-Lc)/Lc = (Lh-Lc)/L0 * L0/Lc = (dL/L0(Th)-dL/L0(Tc)/L0 / (dL/L0(Tc)+1.0)

        Parameters
        ----------
        Tc : float
            Current (hot) temperature in C
        T0 : float
            Cold temperature in C

        Returns
        -------
        dL/L_fromCold : float
            The average thermal expansion between T_current and T0

        See Also
        --------
        linearExpansionPercent
        components.Component.getThermalExpansionFactor
        """
        dLLhot = self.linearExpansionPercent(Tc=Tc)
        dLLcold = self.linearExpansionPercent(Tc=T0)

        return (dLLhot - dLLcold) / (100.0 + dLLcold)

    def getThermalExpansionDensityReduction(
        self, prevTempInC: float, newTempInC: float
    ) -> float:
        """
        Return the factor required to update thermal expansion going from temperatureInC to temperatureInCNew.
        """
        dLL = self.linearExpansionFactor(Tc=newTempInC, T0=prevTempInC)
        return 1.0 / (1 + dLL) ** 2

    def setDefaultMassFracs(self):
        r"""mass fractions"""
        pass

    def setMassFrac(self, nucName: str, massFrac: float) -> None:
        self.massFrac[nucName] = massFrac

    def applyInputParams(self):
        """Apply material-specific material input parameters."""
        pass

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
        Likewise, enriching ZR in UZr would enrich ZR relative to uranium.

        The method maintains a constant number of atoms, and adjusts ``refDens`` accordingly.

        Parameters
        ----------
        nuclideName : str
            Name of nuclide to enrich.

        massFraction : float
            New mass fraction to achieve.
        """
        if massFraction > 1.0 or massFraction < 0.0:
            raise ValueError(
                "Cannot enrich to massFraction of {}, must be between 0 and 1".format(
                    massFraction
                )
            )

        nucsNames = list(self.massFrac)

        # refDens could be zero, but cannot normalize to zero.
        density = self.refDens or 1.0
        massDensities = numpy.array([self.massFrac[nuc] for nuc in nucsNames]) * density
        atomicMasses = numpy.array(
            [nuclideBases.byName[nuc].weight for nuc in nucsNames]
        )  # in AMU
        molesPerCC = massDensities / atomicMasses  # item-wise division

        enrichedIndex = nucsNames.index(nuclideName)
        isoAndEles = nuclideBases.byName[nuclideName].element.nuclides
        allIndicesUpdated = [
            nucsNames.index(nuc.name) for nuc in isoAndEles if nuc.name in self.massFrac
        ]

        if len(allIndicesUpdated) == 1:
            if isinstance(
                nuclideBases.byName[nuclideName], nuclideBases.NaturalNuclideBase
            ) or nuclideBases.isMonoIsotopicElement(nuclideName):
                # if there are not any other nuclides, assume we are enriching an entire element
                # consequently, allIndicesUpdated is no longer the element's indices, but the materials indices
                allIndicesUpdated = range(len(nucsNames))
            else:
                raise ValueError(  # could be warning if problematic
                    "Nuclide {} was to be enriched in material {}, but there were no other isotopes of "
                    "that element. Could not assume the enrichment of the entire element as there were "
                    "other possible isotopes that did not exist in this material.".format(
                        nuclideName, self
                    )
                )

        if massFraction == 1.0:
            massDensities[allIndicesUpdated] = 0.0
            massDensities[enrichedIndex] = 1.0
        else:
            balanceWeight = (
                massDensities[allIndicesUpdated].sum() - massDensities[enrichedIndex]
            )
            if balanceWeight == 0.0:
                onlyOneOtherFracToDetermine = len(allIndicesUpdated) == 2
                if not onlyOneOtherFracToDetermine:
                    raise ValueError(
                        "Material {} has too many masses set to zero. cannot enrich {} to {}. Current "
                        "mass fractions: {}".format(
                            self, nuclideName, massFraction, self.massFrac
                        )
                    )
                # massDensities get normalized later when conserving atoms; these are just ratios
                massDensities[allIndicesUpdated] = (
                    1 - massFraction
                )  # there is only one other.
                massDensities[enrichedIndex] = massFraction
            else:
                # derived from solving the following equation for enrchedWeight:
                # massFraction = enrichedWeight / (enrichedWeight + balanceWeight)
                massDensities[enrichedIndex] = (
                    massFraction * balanceWeight / (1 - massFraction)
                )
        # ratio is set by here but atoms not conserved yet

        updatedNucsMolesPerCC = (
            massDensities[allIndicesUpdated] / atomicMasses[allIndicesUpdated]
        )
        updatedNucsMolesPerCC *= (
            molesPerCC[allIndicesUpdated].sum() / updatedNucsMolesPerCC.sum()
        )  # conserve atoms
        molesPerCC[allIndicesUpdated] = updatedNucsMolesPerCC

        updatedMassDensities = molesPerCC * atomicMasses
        updatedDensity = updatedMassDensities.sum()
        massFracs = updatedMassDensities / updatedDensity

        if not numpy.isclose(sum(massFracs), 1.0, atol=1e-10):
            raise RuntimeError(
                f"The mass fractions {massFracs} in {self} do not sum to 1.0."
            )

        self.massFrac = {nuc: weight for nuc, weight in zip(nucsNames, massFracs)}
        if self.refDens != 0.0:  # don't update density if not assigned
            self.refDens = updatedDensity

    def volumetricExpansion(self, Tk=None, Tc=None):
        pass

    def getTemperatureAtDensity(
        self, targetDensity: float, temperatureGuessInC: float
    ) -> float:
        """Get the temperature at which the perturbed density occurs."""
        densFunc = (
            lambda temp: self.density(Tc=temp) - targetDensity
        )  # 0 at tempertature of targetDensity
        tAtTargetDensity = float(
            fsolve(densFunc, temperatureGuessInC)
        )  # is a numpy array if fsolve is called
        return tAtTargetDensity

    @property
    def liquidPorosity(self) -> float:
        return 0.0 if self.parent is None else self.parent.liquidPorosity

    @property
    def gasPorosity(self) -> float:
        return 0.0 if self.parent is None else self.parent.gasPorosity

    def density(self, Tk: float = None, Tc: float = None) -> float:
        """
        Return density that preserves mass when thermally expanded in 2D.

        Warning
        -------
        This density will not agree with the component density since this method only expands in 2 dimensions.
        The component has been manually expanded axially with the manually entered block hot height.
        The density returned by this should be a factor of 1 + dLL higher than the density on the component.
        density3 should be in agreement at both cold and hot temperatures as long as the block height is correct for
        the specified temperature.
        In the case of Fluids, density and density3 are the same as density is not driven by linear expansion, but
        rather an explicit density function dependent on Temperature. linearExpansionPercent is zero for a fluid.

        See Also
        --------
        armi.materials.density3:
            component density should be in agreement with this density
        armi.reactor.blueprints._applyBlockDesign:
            2D expansion and axial density reduction occurs here.
        """
        Tk = getTk(Tc, Tk)
        dLL = self.linearExpansionPercent(Tk=Tk)
        if self.refDens is None:
            runLog.warning(
                "{0} has no reference density".format(self),
                single=True,
                label="No refD " + self.getName(),
            )
            self.refDens = 0.0

        f = (1.0 + dLL / 100.0) ** 2
        return self.refDens / f  # g/cm^3

    def densityKgM3(self, Tk: float = None, Tc: float = None) -> float:
        """
        Return density that preserves mass when thermally expanded in 2D in units of kg/m^3

        See Also
        --------
        armi.materials.density:
            Arguments are forwarded to the g/cc version
        """
        return self.density(Tk, Tc) * 1000.0

    def density3(self, Tk: float = None, Tc: float = None) -> float:
        """
        Return density that preserves mass when thermally expanded in 3D.

        Notes
        -----
        Since refDens is specified at the material-dep reference case, we don't
        need to specify the reference temperature. It is already consistent with linearExpansion
        Percent.
        - p*(dp/p(T) + 1) =p*( p + dp(T) )/p = p + dp(T) = p(T)
        - dp/p = (1-(1 + dL/L)**3)/(1 + dL/L)**3
        """
        Tk = getTk(Tc, Tk)
        dLL = self.linearExpansionPercent(Tk=Tk)
        refD = self.refDens
        if refD is None:
            runLog.warning(
                "{0} has no reference density".format(self),
                single=True,
                label="No refD " + self.getName(),
            )
            return None
        f = (1.0 + dLL / 100.0) ** 3
        return refD / f

    def density3KgM3(self, Tk: float = None, Tc: float = None) -> float:
        """Return density that preserves mass when thermally expanded in 3D in units of kg/m^3.

        See Also
        --------
        armi.materials.density3:
            Arguments are forwarded to the g/cc version
        """
        return self.density3(Tk, Tc) * 1000.0

    def getCorrosionRate(self, Tk: float = None, Tc: float = None) -> float:
        r"""
        given a temperature, get the corrosion rate of the material
        """
        return 0.0

    def getLifeMetalCorrelation(self, days: float, Tk: float) -> float:
        r"""
        life-metal correlation calculates the wastage of the material due to fission products.
        """
        return 0.0

    def getReverseLifeMetalCorrelation(
        self, thicknessFCCIWastageMicrons: float, Tk: float
    ) -> float:
        r"""
        Life metal correlation reverse lookup.  Knowing wastage and Temperature
        determine the effective time at that temperature.
        """
        return 0.0

    def getLifeMetalConservativeFcciCoeff(self, Tk: float) -> float:
        """
        Return the coefficient to be used in the LIFE-METAL correlation
        """
        return 0.0

    def yieldStrength(self, Tk: float = None, Tc: float = None) -> float:
        r"""returns yield strength at given T in MPa"""
        pass

    def thermalConductivity(self, Tk: float = None, Tc: float = None) -> float:
        r"""thermal conductivity in given T in K"""
        pass

    def getProperty(
        self, propName: str, Tk: float = None, Tc: float = None, **kwargs
    ) -> float:
        r"""gets properties in a way that caches them."""
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

    def getMassFrac(
        self,
        nucName=None,
        normalized=True,
        expandFissionProducts=False,
    ):
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
        self.massFrac are modified mass fractions that may not add up to 1.0
        (for instance, after a axial expansion, the modified mass fracs will sum to less than one.
        The alternative is to put a multiplier on the density. They're mathematically equivalent.

        This function returns the normalized mass fraction (they will add to 1.0) as long as
        the mass fracs are modified only by get and setMassFrac

        This is a performance-critical method as it is called millions of times in a
        typical ARMI run.

        See Also
        --------
        setMassFrac
        """
        return self.massFrac.get(nucName, 0.0)

    def clearMassFrac(self) -> None:
        r"""zero out all nuclide mass fractions."""
        self.massFrac.clear()

    def removeNucMassFrac(self, nuc: str) -> None:
        self.setMassFrac(nuc, 0)
        try:
            del self.massFrac[nuc]
        except KeyError:
            # the nuc isn't in the mass Frac vector
            pass

    def getMassFracCopy(self):
        return copy.deepcopy(self.massFrac)

    def checkPropertyTempRange(self, label, val):
        r"""Checks if the given property / value combination fall between the min and max valid
        temperatures provided in the propertyValidTemperature object.

        Parameters
        ----------
        label : str
            The name of the function or property that is being checked.

        val : float
            The value to check whether it is between minT and maxT.

        Notes
        -----
        This was designed as a convience method for ``checkTempRange``.
        """
        (minT, maxT) = self.propertyValidTemperature[label][0]
        self.checkTempRange(minT, maxT, val, label)

    def checkTempRange(self, minT, maxT, val, label=""):
        r"""
        Checks if the given temperature (val) is between the minT and maxT temperature limits supplied.
        Label identifies what material type or element is being evaluated in the check.

        Parameters
        ----------
        minT, maxT : float
            The minimum and maximum values that val is allowed to have.

        val : float
            The value to check whether it is between minT and maxT.

        label : str
            The name of the function or property that is being checked.
        """
        if not minT <= val <= maxT:
            msg = "Temperature {0} out of range ({1} to {2}) for {3} {4}".format(
                val, minT, maxT, self.name, label
            )
            if FAIL_ON_RANGE or numpy.isnan(val):
                runLog.error(msg)
                raise ValueError
            else:
                runLog.warning(
                    msg,
                    single=True,
                    label="T out of bounds for {} {}".format(self.name, label),
                )

    def densityTimesHeatCapacity(self, Tk: float = None, Tc: float = None) -> float:
        r"""
        Return heat capacity * density at a temperature
        Parameters
        ----------
        Tk : float, optional
            Temperature in Kelvin.
        Tc : float, optional
            Temperature in degrees Celsius.

        Returns
        -------
        rhoCP : float
            Calculated value for the HT9 density* heat capacity
            unit (J/m^3-K)
        """
        Tc = getTc(Tc, Tk)

        rhoCp = self.density3(Tc=Tc) * 1000.0 * self.heatCapacity(Tc=Tc)

        return rhoCp

    def getNuclides(self):
        """
        Return nuclides in the component that contains this Material.

        Notes
        -----
        This method is the only reason Materials still have self.parent.
        Essentially, we want to change that, but right now the logic for finding
        nuclides in the Reactor is recursive and considers Materials first.
        The bulk of the work in finally removing this method will come in
        downstream repos, where users have fully embraced this method and call
        it directly in many, many places.
        Please do not use this method, as it is being deprecated.
        """
        warnings.warn("Material.getNuclides is being deprecated.", DeprecationWarning)
        return self.parent.getNuclides()

    def getTempChangeForDensityChange(
        self, Tc: float, densityFrac: float, quiet: bool = True
    ) -> float:
        """Return a temperature difference for a given density perturbation."""
        linearExpansion = self.linearExpansion(Tc=Tc)
        linearChange = densityFrac ** (-1.0 / 3.0) - 1.0
        deltaT = linearChange / linearExpansion
        if not quiet:
            runLog.info(
                "The linear expansion for {} at initial temperature of {} C is {}.\nA change in density of {} "
                "percent at would require a change in temperature of {} C.".format(
                    self.getName(),
                    Tc,
                    linearExpansion,
                    (densityFrac - 1.0) * 100.0,
                    deltaT,
                ),
                single=True,
            )
        return deltaT

    def heatCapacity(self, Tk=None, Tc=None):
        raise NotImplementedError(
            f"Material {type(self).__name__} does not implement heatCapacity"
        )

    def getTD(self):
        """Get the fraction of theoretical density for this material."""
        return self.theoreticalDensityFrac

    def adjustTD(self, val):
        """Set or change the fraction of theoretical density for this material."""
        self.theoreticalDensityFrac = val
        self.clearCache()


class Fluid(Material):
    """A material that fills its container. Could also be a gas."""

    name = "Fluid"

    def getThermalExpansionDensityReduction(self, prevTempInC, newTempInC):
        """
        Return the factor required to update thermal expansion going from temperatureInC to temperatureInCNew.
        """
        rho0 = self.density(Tc=prevTempInC)
        if not rho0:
            return 1.0
        rho1 = self.density(Tc=newTempInC)
        return rho1 / rho0

    def linearExpansion(self, Tk=None, Tc=None):
        """for void, lets just not allow temperature changes to change dimensions
        since it is a liquid it will fill its space."""
        return 0.0

    def getTempChangeForDensityChange(
        self, Tc: float, densityFrac: float, quiet: bool = True
    ) -> float:
        """Return a temperature difference for a given density perturbation."""
        currentDensity = self.density(Tc=Tc)
        perturbedDensity = currentDensity * densityFrac
        tAtPerturbedDensity = self.getTemperatureAtDensity(perturbedDensity, Tc)
        deltaT = tAtPerturbedDensity - Tc
        if not quiet:
            runLog.info(
                "A change in density of {} percent in {} at an initial temperature of {} C would require "
                "a change in temperature of {} C.".format(
                    (densityFrac - 1.0) * 100.0, self.getName(), Tc, deltaT
                ),
                single=True,
            )
        return deltaT

    def density3(self, Tk=None, Tc=None):
        """
        Return the density at the specified temperature for 3D expansion.

        Notes
        -----
        For fluids, there is no such thing as 2D expansion so density() is already 3D.
        """
        return self.density(Tk=Tk, Tc=Tc)


class SimpleSolid(Material):
    """
    Base material for a simple material that primarily defines density

    Notes
    -----
    This function assumed the density is defined on the _density method and
    this base class keeps density, density3 and linearExpansion all in sync

    class SimpleMaterial(SimpleSolid):

        def _density(self, Tk=None, Tc=None):
            "
            density that preserves mass when thermally expanded in 3D.
            "
            ...

    See Also
    --------
    armi.materials.density:
    armi.materials.density3:
    """

    refTempK = 300

    def __init__(self):
        Material.__init__(self)
        self.refDens = self.density3(Tk=self.refTempK)

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

        Notes
        -----
        This only method only works for Simple Solid Materials which assumes
        the density3 function returns 'free expansion' density as a function
        temperature
        """
        density1 = self.density3(Tk=self.refTempK)
        density2 = self.density3(Tk=Tk, Tc=Tc)

        if density1 == density2:
            return 0
        else:
            return 100 * ((density1 / density2) ** (1.0 / 3.0) - 1)

    def density3(self, Tk: float = None, Tc: float = None) -> float:
        return 0.0

    def density(self, Tk: float = None, Tc: float = None) -> float:
        """
        The same method as the parent class, but with the ability to apply a
        non-unity theoretical density.
        """
        return Material.density(self, Tk=Tk, Tc=Tc) * self.getTD()


class FuelMaterial(Material):
    """
    Material that is considered a nuclear fuel.

    All this really does is enable the special class 1/class 2 isotopics input option.
    """

    def __init__(self):
        Material.__init__(self)
        # support for custom isotopics
        self.class1_wt_frac = None
        self.class1_custom_isotopics = None
        self.class2_custom_isotopics = None
        # tracking depletion status
        self.puFrac = 0.0
        self.uFrac = 0.0
        self.zrFrac = 0.0

    def applyInputParams(
        self,
        class1_custom_isotopics=None,
        class2_custom_isotopics=None,
        class1_wt_frac=None,
        customIsotopics=None,
    ):
        """Apply optional class 1/class 2 custom enrichment input.

        Notes
        -----
        This is often overridden to insert customized material modification parameters
        but then this parent should always be called at the end in case users want to
        use this style of custom input.

        This is only applied to materials considered fuel so we don't apply these
        kinds of parameters to coolants and structural material, which are often
        not parameterized with any kind of enrichment.
        """
        if class1_wt_frac:
            if not 0 <= class1_wt_frac <= 1:
                raise ValueError(
                    "class1_wt_frac must be between 0 and 1 (inclusive)."
                    f" Right now it is {class1_wt_frac}."
                )

            validIsotopics = customIsotopics.keys()
            errMsg = "{} '{}' not found in the defined custom isotopics."
            if class1_custom_isotopics not in validIsotopics:
                raise KeyError(
                    errMsg.format("class1_custom_isotopics", class1_custom_isotopics)
                )
            if class2_custom_isotopics not in validIsotopics:
                raise KeyError(
                    errMsg.format("class2_custom_isotopics", class2_custom_isotopics)
                )
            if class1_custom_isotopics == class2_custom_isotopics:
                runLog.warning(
                    "The custom isotopics specified for the class1/class2 materials"
                    f" are both '{class1_custom_isotopics}'. You are not actually blending anything!"
                )

            self.class1_wt_frac = class1_wt_frac
            self.class1_custom_isotopics = class1_custom_isotopics
            self.class2_custom_isotopics = class2_custom_isotopics

            self._applyIsotopicsMixFromCustomIsotopicsInput(customIsotopics)

    def _applyIsotopicsMixFromCustomIsotopicsInput(self, customIsotopics):
        """
        Apply a Class 1/Class 2 mixture of custom isotopics at input.

        Only adjust heavy metal.

        This may also be needed for building charge assemblies during reprocessing, but
        will take input from the SFP rather than from the input external feeds.
        """
        class1Isotopics = customIsotopics[self.class1_custom_isotopics]
        class2Isotopics = customIsotopics[self.class2_custom_isotopics]
        densityTools.applyIsotopicsMix(self, class1Isotopics, class2Isotopics)

    def duplicate(self):
        r"""copy without needing a deepcopy."""
        m = self.__class__()

        m.massFrac = {}
        for key, val in self.massFrac.items():
            m.massFrac[key] = val

        m.parent = self.parent
        m.refDens = self.refDens
        m.theoreticalDensityFrac = self.theoreticalDensityFrac

        # Handle the case where a developer creates a FuelMaterial,
        # but only calls the Material.__init__().
        m.class1_wt_frac = (
            self.class1_wt_frac if hasattr(self, "class1_wt_frac") else None
        )
        m.class1_custom_isotopics = (
            self.class1_custom_isotopics
            if hasattr(self, "class1_custom_isotopics")
            else None
        )
        m.class2_custom_isotopics = (
            self.class2_custom_isotopics
            if hasattr(self, "class2_custom_isotopics")
            else None
        )
        m.puFrac = self.puFrac if hasattr(self, "puFrac") else 0.0
        m.uFrac = self.uFrac if hasattr(self, "uFrac") else 0.0
        m.zrFrac = self.zrFrac if hasattr(self, "zrFrac") else 0.0

        return m
