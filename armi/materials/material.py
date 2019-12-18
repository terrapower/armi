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

All temperatures are in K, but Tc can be specified and the functions will convert for you.

.. Caution:: ARMI uses these objects for all material properties. Under the hood,
     A system called MAT_PROPS is in charge of several material properties. It
     is a more industrial-strength material property system that is currently
     a TerraPower proprietary system. You will see references to it in this module.

"""
import copy
import warnings

from scipy.optimize import fsolve
import numpy

from armi import runLog
from armi.nucDirectory import nuclideBases
from armi.reactor import composites
from armi.materials import materialParameters
from armi.utils.units import getTk, getTc
from armi.utils import densityTools

# globals
FAIL_ON_RANGE = False


class Material(composites.Leaf):
    r"""
    A material is made up of elements or isotopes. It has bulk properties like mass density.

    Attributes
    ----------
    params : dict
        scalar parameters.

    massFrac : dict
        The mass fractions of each nuclide in this material. These will not always sum to 1.0 after
        situations like axial expansion.

    massFracNorm : float
        The sum of massFrac, tracked by the setters so it doesn't have to be added up a lot.

    cache : dict
        Fast storage for commonly computed values.

    reference : str
        The literature reference.

    """
    pDefs = materialParameters.getMaterialParameterDefinitions()

    DATA_SOURCE = "ARMI"

    name = "Material"
    references = {}  # property : citation
    enrichedNuclide = None
    correctDensityAfterApplyInputParams = True
    modelConst = {}

    def __init__(self):
        composites.Leaf.__init__(self, self.__class__.name)
        self.p.massFrac = {}

        # track sum of massFrac (which are modified and won't always sum to 1.0!)
        self.p.massFracNorm = 0.0

        # so it doesn't have to be summed each time ( O(1) vs. O(N))
        self.p.atomFracDenom = 0.0
        self.references = {}  # reference dictionary for each method
        self.p.refDens = 0.0

        # call subclass implementations
        self.setDefaultMassFracs()
        self.propertyRangeUpdated = False

    def __repr__(self):
        return "<Material: {0}>".format(self.getName())

    def duplicate(self):
        r"""copy without needing a deepcopy."""
        m = self.__class__()
        for key, val in self.p.items():
            m.p[key] = val
        m.p.massFrac = {}
        for key, val in self.p.massFrac.items():
            m.p.massFrac[key] = val
        m.parent = self.parent

        return m

    def linearExpansion(self, Tk=None, Tc=None):
        r"""
        the instantaneous linear expansion coefficient (dL/L)/dT

        This is used for reactivity coefficients, etc.
        """
        raise NotImplementedError(
            f"{self} does not have a linear expansion property defined"
        )

    def linearExpansionPercent(self, Tk=None, Tc=None):
        r"""
        average thermal expansion dL/L. Used for computing hot dimensions

        Defaults to 0.0 for materials that don't expand.

        Parameters
        ----------
        Tk : float
            temperature in (K)
        Tc : float
            Temperature in (C)

        Returns
        -------
        %dLL(T) in m/m/K

        """
        return 0.0

    def linearExpansionFactor(self, Tc, T0):
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

    def getThermalExpansionDensityReduction(self, prevTempInC, newTempInC):
        """
        Return the factor required to update thermal expansion going from temperatureInC to temperatureInCNew.
        """
        dLL = self.linearExpansionFactor(Tc=newTempInC, T0=prevTempInC)
        return 1.0 / (1 + dLL) ** 2

    def setDefaultMassFracs(self):
        r"""mass fractions"""
        pass

    def setMassFrac(self, nucName, massFrac):
        self.p.massFrac[nucName] = massFrac

    def applyInputParams(self):
        """Apply material-specific material input parameters."""
        pass

    def adjustMassEnrichment(self, massEnrichment):
        """
        Adjust the enrichment of the material.

        See Also
        --------
        adjustMassFrac
        """
        self.adjustMassFrac(self.enrichedNuclide, massEnrichment)

    def adjustMassFrac(self, nuclideName, massFraction):
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

        nucsNames = list(self.p.massFrac)

        # refDens could be zero, but cannot normalize to zero.
        density = self.p.refDens or 1.0
        massDensities = (
            numpy.array([self.p.massFrac[nuc] for nuc in nucsNames]) * density
        )
        atomicMasses = numpy.array(
            [nuclideBases.byName[nuc].weight for nuc in nucsNames]
        )  # in AMU
        molesPerCC = massDensities / atomicMasses  # item-wise division

        enrichedIndex = nucsNames.index(nuclideName)
        isoAndEles = nuclideBases.byName[nuclideName].element.nuclideBases
        allIndicesUpdated = [
            nucsNames.index(nuc.name)
            for nuc in isoAndEles
            if nuc.name in self.p.massFrac
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
                            self, nuclideName, massFraction, self.p.massFrac
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
        self.p.massFrac = {nuc: weight for nuc, weight in zip(nucsNames, massFracs)}

        if self.p.refDens != 0.0:  # don't update density if not assigned
            self.p.refDens = updatedDensity

    def volumetricExpansion(self, Tk=None, Tc=None):
        pass

    def getTemperatureAtDensity(self, targetDensity, temperatureGuessInC):
        """Get the temperature at which the perturbed density occurs."""
        densFunc = (
            lambda temp: self.density(Tc=temp) - targetDensity
        )  # 0 at tempertature of targetDensity
        tAtTargetDensity = float(
            fsolve(densFunc, temperatureGuessInC)
        )  # is a numpy array if fsolve is called
        return tAtTargetDensity

    @property
    def liquidPorosity(self):
        return 0.0 if self.parent is None else self.parent.liquidPorosity

    @property
    def gasPorosity(self):
        return 0.0 if self.parent is None else self.parent.gasPorosity

    def density(self, Tk=None, Tc=None):
        """Return density that preserves mass when thermally expanded in 2D.

        Warning
        -------
        This density will not agree with the component density since this method only expands in 2 dimensions.
        The component has been manually expanded axially with the manually entered block hot height.
        The density returned by this should be a factor of 1 + dLL higher than the density on the component.
        density3 should be in agreement at both cold and hot temperatures as long as the block height is correct for
        the specified temperature.
        In the case of Fluids, density and density3 are the same as density is not driven by linear expansion, but
        rather an exilicit density function dependent on Temperature. linearExpansionPercent is zero for a fluid.

        See Also
        --------
        armi.materials.density3:
            component density should be in agreement with this density
        armi.reactor.blueprints._applyBlockDesign:
            2D expansion and axial density reduction occurs here.
        """
        Tk = getTk(Tc, Tk)
        dLL = self.linearExpansionPercent(Tk=Tk)
        if self.p.refDens is None:
            runLog.warning(
                "{0} has no reference density".format(self),
                single=True,
                label="No refD " + self.getName(),
            )
            self.p.refDens = 0.0
        f = (1.0 + dLL / 100.0) ** 2
        # dRhoOverRho = (1.0 - f)/f
        # rho = rho + dRho = (1 + dRho/rho) * rho
        return self.p.refDens / f  # g/cm^3

    def densityKgM3(self, Tk=None, Tc=None):
        """
        Return density that preserves mass when thermally expanded in 2D in units of kg/m^3

        See Also
        --------
        armi.materials.density:
            Arguments are forwarded to the g/cc version
        """
        return self.density(Tk, Tc) * 1000.0

    def density3(self, Tk=None, Tc=None):
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
        refD = self.p.refDens
        if refD is None:
            runLog.warning(
                "{0} has no reference density".format(self),
                single=True,
                label="No refD " + self.getName(),
            )
            return None
        f = (1.0 + dLL / 100.0) ** 3
        dRhoOverRho = (1.0 - f) / f
        return refD * (dRhoOverRho + 1)

    def density3KgM3(self, Tk=None, Tc=None):
        """Return density that preserves mass when thermally expanded in 3D in units of kg/m^3.

        See Also
        --------
        armi.materials.density3:
            Arguments are forwarded to the g/cc version
        """
        return self.density3(Tk, Tc) * 1000.0

    def getCorrosionRate(self, Tk=None, Tc=None):
        r"""
        given a temperature, get the corrosion rate of the material
        """
        return 0.0

    def getLifeMetalCorrelation(self, days, Tk):
        r"""
        life-metal correlation calculates the wastage of the material due to fission products.
        """
        return 0.0

    def getReverseLifeMetalCorrelation(self, thicknessFCCIWastageMicrons, Tk):
        r"""
        Life metal correlation reverse lookup.  Knowing wastage and Temperature
        determine the effective time at that temperature.
        """
        return 0.0

    def getLifeMetalConservativeFcciCoeff(self, Tk):
        """
        Return the coefficient to be used in the LIFE-METAL correlation
        """

        return 0.0

    def yieldStrength(self, Tk=None, Tc=None):
        r"""
        returns yield strength at given T in MPa
        """
        return self.p.yieldStrength

    def thermalConductivity(self, Tk=None, Tc=None):
        r"""
        thermal conductivity in given T in K
        """
        return self.p.thermalConductivity

    def getProperty(self, propName, Tk=None, Tc=None, **kwargs):
        r"""gets properties in a way that caches them. """
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
        elementSymbol=None,
        nucList=None,
        normalized=True,
        expandFissionProducts=False,
    ):
        """
        Return mass fraction of nucName.

        Parameters
        ----------
        nucName : str, optional
            Nuclide name to return ('ZR','PU239',etc.)

        elementSymbol :str, optional
             Return mass fractions of all isotopes of this element (example: 'Pu', 'U')

        nucList : optional, list
            List of nuclides to sum up and return the total

        normalized : bool, optional
            Return the mass fraction such that the sum of all nuclides is sum to 1.0. Default True

        Notes
        -----

        self.p.massFrac are modified mass fractions that may not add up to 1.0
        (for instance, after a axial expansion, the modified mass fracs will sum to less than one.
        The alternative is to put a multiplier on the density. They're mathematically equivalent.

        This function returns the normalized mass fraction (they will add to 1.0) as long as
        the mass fracs are modified only by get and setMassFrac

        This is a performance-critical method as it is called millions of times in a
        typical ARMI run.

        See Also
        --------
        setMassFrac
        getNDens

        """
        return self.p.massFrac.get(nucName, 0.0)

    def clearMassFrac(self):
        r"""zero out all nuclide mass fractions. """
        self.p.massFrac.clear()
        self.p.massFracNorm = 0.0

    def removeNucMassFrac(self, nuc):
        self.setMassFrac(nuc, 0)
        try:
            del self.p.massFrac[nuc]
        except KeyError:
            # the nuc isn't in the mass Frac vector
            pass

    def removeLumpedFissionProducts(self):
        for nuc in self.getNuclides():
            if "LF" in nuc:
                # this component has a lumped fission product to remove
                self.removeNucMassFrac(nuc)

    def getMassFracCopy(self):
        return copy.deepcopy(self.p.massFrac)

    def checkTempRange(self, minV, maxV, val, label=""):
        r"""
        Checks if the given temperature (val) is between the minV and maxV temperature limits supplied.
        Label identifies what material type or element is being evaluated in the check.

        Parameters
        ----------
        minV, maxV : float
            The minimum and maximum values that val is allowed to have.

        val : float
            The value to check whether it is between minV and maxV.

        label : str
            The name of the function or property that is being checked.

        """

        if not minV <= val <= maxV:
            msg = "Temperature {0} out of range ({1} to {2}) for {3} {4}".format(
                val, minV, maxV, self.name, label
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

    def isBeyondIncubationDose(self, totalDPA):
        r"""
        Checks if the materials is beyond is incubation dose. Passes if the material
        does not have an incubation dose assigned (self.modelConst['Rincu']

        Parameters
        ----------

        totalDPA : float
            Total DPA accumulated in the material

        Returns
        -------
        Bool indicating whether the material is beyond its incubation dose or not.

        """

        if not self.modelConst["Rincu"]:
            msg = "Material missing incubation dose"
            runLog.warning(msg, single=True, label="Missing incubation dose")
        elif totalDPA > self.modelConst["Rincu"]:
            return True
        else:
            return False

    def updateDeltaDPApastIncubation(self, totalDPA, deltaDPA):
        r"""
        If a material has passed its incubation dose, this method updates deltaDPA. The concern
        here is when a step in DPA crosses the incubation threshold, the amount of DPA input into a
        calculation is more than is actually contributing to deformation.

        Parameters
        ----------

        totalDPA : float
            Total DPA accumulated in the material.

        deltaDPA : float
            Change in DPA over a time step.

        Returns
        -------
        deltaDPA past the incubation dose of the material.

        """
        if not self.modelConst["Rincu"]:
            msg = "Material missing incubation dose"
            runLog.warning(msg, single=True, label="Missing incubation dose")
        elif (totalDPA > self.modelConst["Rincu"]) and (
            (totalDPA - self.modelConst["Rincu"]) < deltaDPA
        ):
            return totalDPA - self.modelConst["Rincu"]
        else:
            return deltaDPA

    def densityTimesHeatCapacity(self, Tk=None, Tc=None):
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

        rhoCp = self.density(Tc=Tc) * 1000.0 * self.heatCapacity(Tc=Tc)

        return rhoCp

    def getNuclides(self):
        warnings.warn("Material.getNuclides is being deprecated.", DeprecationWarning)
        return self.parent.getNuclides()

    def getTempChangeForDensityChange(self, Tc, densityFrac, quiet=True):
        """Return a temperature difference for a given density perturbation."""
        linearExpansion = self.linearExpansion(Tc=Tc)
        volFrac = densityFrac ** (-1.0 / 3.0) - 1.0
        deltaT = volFrac / linearExpansion
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
        since it is a liquid it will fill its space. """
        return 0.0

    def getTempChangeForDensityChange(self, Tc, densityFrac, quiet=True):
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
        for fluids, there is no such thing as 2 d expansion so density() is already 3D.
        """
        return self.density(Tk=Tk, Tc=Tc)


class FuelMaterial(Material):
    """
    Material that is considered a nuclear fuel.

    All this really does is enable the special class 1/class 2 isotopics input option.
    """
    pDefs = materialParameters.getFuelMaterialParameterDefinitions()

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
        # Save class data for future reconstructions (e.g. in closed cycles)
        self.p.class1_wt_frac = class1_wt_frac
        self.p.class1_custom_isotopics = class1_custom_isotopics
        self.p.class2_custom_isotopics = class2_custom_isotopics
        if class1_wt_frac:
            self._applyIsotopicsMixFromCustomIsotopicsInput(customIsotopics)

    def _applyIsotopicsMixFromCustomIsotopicsInput(self, customIsotopics):
        """
        Apply a Class 1/Class 2 mixture of custom isotopics at input.

        Only adjust heavy metal.

        This may also be needed for building charge assemblies during reprocessing, but
        will take input from the SFP rather than from the input external feeds.
        """
        class1Isotopics = customIsotopics[self.p.class1_custom_isotopics]
        class2Isotopics = customIsotopics[self.p.class2_custom_isotopics]
        densityTools.applyIsotopicsMix(self, class1Isotopics, class2Isotopics)
