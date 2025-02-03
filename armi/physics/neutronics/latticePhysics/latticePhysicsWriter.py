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
Lattice Physics Writer.

Parent class for lattice physics writers.

Seeks to provide access to common methods used by general lattice
physics codes.
"""

import collections
import math

import numpy as np
import ordered_set

from armi import interfaces, runLog
from armi.nucDirectory import nuclideBases
from armi.physics import neutronics
from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.physics.neutronics.fissionProductModel.fissionProductModelSettings import (
    CONF_FP_MODEL,
)
from armi.physics.neutronics.settings import (
    CONF_GEN_XS,
    CONF_MINIMUM_FISSILE_FRACTION,
    CONF_MINIMUM_NUCLIDE_DENSITY,
)
from armi.reactor import components
from armi.reactor.flags import Flags
from armi.settings.fwSettings.globalSettings import CONF_DETAILED_AXIAL_EXPANSION
from armi.utils.customExceptions import warn_when_root

# number of decimal places to round temperatures to in _groupNuclidesByTemperature
_NUM_DIGITS_ROUND_TEMPERATURE = 3
# index of the temperature in the nuclide dictionary: {nuc: (density, temp, category)}
_NUCLIDE_VALUES_TEMPERATURE_INDEX = 1


@warn_when_root
def nuclideNameFoundMultipleTimes(nuclideName):
    return "Nuclide `{}' was found multiple times.".format(nuclideName)


class LatticePhysicsWriter(interfaces.InputWriter):
    """
    Parent class for creating the inputs for lattice physics codes.

    Contains methods for extracting all nuclides for a given problem.
    """

    _SPACE = " "
    _SEPARATOR = " | "
    # Nuclide categories
    UNUSED_CATEGORY = "Unused" + 3 * _SPACE
    FUEL_CATEGORY = "Fuel" + 5 * _SPACE
    STRUCTURE_CATEGORY = "Structure"
    COOLANT_CATEGORY = "Coolant" + 2 * _SPACE
    FISSION_PRODUCT_CATEGORY = "Fission Product"
    # Nuclide attributes
    DEPLETABLE = "Depletable" + 4 * _SPACE
    UNDEPLETABLE = "Non-Depletable"
    REPRESENTED = "Represented" + 2 * _SPACE
    INF_DILUTE = "Inf Dilute"

    def __init__(
        self,
        representativeBlock,
        r=None,
        externalCodeInterface=None,
        xsLibrarySuffix="",
        generateExclusiveGammaXS=False,
    ):
        interfaces.InputWriter.__init__(
            self, r=r, externalCodeInterface=externalCodeInterface
        )
        self.cs = self.eci.cs
        self.block = representativeBlock
        if not isinstance(xsLibrarySuffix, str):
            raise TypeError(
                "xsLibrarySuffix should be a string; got {}".format(
                    type(xsLibrarySuffix)
                )
            )
        self.xsLibrarySuffix = xsLibrarySuffix
        self.generateExclusiveGammaXS = generateExclusiveGammaXS
        if self.generateExclusiveGammaXS and not neutronics.gammaXsAreRequested(
            self.cs
        ):
            raise ValueError(
                "Invalid `{}` setting to generate gamma XS for {}.".format(
                    CONF_GEN_XS, self.block
                )
            )
        self.xsId = representativeBlock.getMicroSuffix()
        self.xsSettings = self.cs[CONF_CROSS_SECTION][self.xsId]
        self.mergeIntoClad = self.xsSettings.mergeIntoClad
        self.mergeIntoFuel = self.xsSettings.mergeIntoFuel
        self.driverXsID = self.xsSettings.driverID
        self.numExternalRings = self.xsSettings.numExternalRings
        self.criticalBucklingSearchActive = self.xsSettings.criticalBuckling
        self.ductHeterogeneous = self.xsSettings.ductHeterogeneous
        self.traceIsotopeThreshold = self.xsSettings.traceIsotopeThreshold

        self.executeExclusive = self.xsSettings.xsExecuteExclusive
        self.priority = self.xsSettings.xsPriority
        self.maxAtomNumberToModelInfDilute = (
            self.xsSettings.xsMaxAtomNumber
            if self.xsSettings.xsMaxAtomNumber is not None
            else 999
        )
        # would prefer this in 1D but its used in 0D in _writeSourceComposition
        self.minDriverDensity = self.xsSettings.minDriverDensity

        blockNeedsFPs = (
            representativeBlock.getLumpedFissionProductCollection() is not None
        )

        self.modelFissionProducts = (
            blockNeedsFPs and self.cs[CONF_FP_MODEL] != "noFissionProducts"
        )
        self.explicitFissionProducts = (
            self.cs[CONF_FP_MODEL] == "explicitFissionProducts"
        )
        self.diluteFissionProducts = (
            blockNeedsFPs and self.cs[CONF_FP_MODEL] == "infinitelyDilute"
        )
        self.minimumNuclideDensity = self.cs[CONF_MINIMUM_NUCLIDE_DENSITY]
        self.infinitelyDiluteDensity = self.minimumNuclideDensity
        self._unusedNuclides = set()
        self._allNuclideObjects = None

    def __repr__(self):
        suffix = (
            " with Suffix:`{}`".format(self.xsLibrarySuffix)
            if self.xsLibrarySuffix
            else ""
        )
        if self.generateExclusiveGammaXS:
            xsFlag = neutronics.GAMMA
        elif (
            neutronics.gammaXsAreRequested(self.cs) and self._isGammaXSGenerationEnabled
        ):
            xsFlag = neutronics.NEUTRONGAMMA
        else:
            xsFlag = neutronics.NEUTRON
        return "<{} - XS ID {} ({} XS){}>".format(
            self.__class__.__name__, self.xsId, xsFlag, suffix
        )

    def _writeTitle(self, fileObj):
        self._writeComment(
            fileObj,
            "ARMI generated case for caseTitle {}, block {}\n".format(
                self.cs.caseTitle, self.block
            ),
        )

    def write(self):
        raise NotImplementedError

    @property
    def _isSourceDriven(self):
        return bool(self.driverXsID)

    @property
    def _isGammaXSGenerationEnabled(self):
        """Gamma transport is not available generically across all lattice physic solvers."""
        return False

    def _getAllNuclidesByTemperatureInC(self, component=None):
        """
        Returns a dictionary where all nuclides in the block are grouped by temperature.

        Some lattice physics codes, like ``SERPENT`` create mixtures of nuclides
        at similar temperatures to construct a problem. The dictionary returned is of the form ::

            {temp1: {n1: (d1, temp1, category1),
                     n2: (d2, temp1, category2)}
             temp2: {n3: (d3, temp2, category3),
                     n4: (d4, temp2, category4)}
             ...
             }

        """
        nuclides = self._getAllNuclideObjects(component)
        return _groupNuclidesByTemperature(nuclides)

    def _getAllNuclideObjects(self, component=None):
        """
        Returns a single dictionary of all nuclides in the component.

        Calls :py:meth:`_getAllNuclidesByCategory`, which returns two dictionaries:
        one with just fission products and another with the remaining nuclides.
        This method just updates ``self._allNuclideObjects`` to contain the fission
        products as well.

        The dictionaries are structured with :py:class:`armi.nucDirectory.nuclideBases.NuclideBase`
        objects, with `(density, temperatureInC, and category)`` tuples for that nuclide object.

        """
        nucs, fissProds = self._getAllNuclidesByCategory(component)
        nucs.update(fissProds)
        return nucs

    def _getAllNuclidesByCategory(self, component=None):
        """
        Determine number densities and temperatures for each nuclide.

        Temperatures are a bit complex due to some special cases:
            Nuclides that build up like Pu239 have zero density at BOL but need cross sections.
            Nuclides like Mo99 are sometimes in structure and sometimes in lumped fission products. What temp to use?
            Nuclides like B-10 are in control blocks but these aren't candidates for XS creation. What temperature?

        To deal with this, we compute (flux-weighted) average temperatures of each nuclide based on its current
        component temperatures.

        """
        dfpDensities = self._getDetailedFPDensities()
        (
            coolantNuclides,
            fuelNuclides,
            structureNuclides,
        ) = self.r.core.getNuclideCategories()
        nucDensities = {}
        subjectObject = component or self.block
        depletableNuclides = nuclideBases.getDepletableNuclides(
            self.r.blueprints.activeNuclides, self.block
        )
        objNuclides = subjectObject.getNuclides()

        # If the explicit fission product model is enabled then the number densities
        # on the components will already contain all the nuclides required to be
        # modeled by the lattice physics writer. Otherwise, assume that `allNuclidesInProblem`
        # should be modeled.
        if self.explicitFissionProducts:
            # If detailed axial expansion is active, mapping between blocks occurs on uniform mesh
            # and this can cause blocks to have isotopes that they don't have cross sections for.
            # Fix this by adding all isotopes so they are present in lattice physics.
            if self.cs[CONF_DETAILED_AXIAL_EXPANSION]:
                nuclides = self.r.blueprints.allNuclidesInProblem
            else:
                nuclides = ordered_set.OrderedSet(sorted(objNuclides))
        else:
            nuclides = self.r.blueprints.allNuclidesInProblem

        nuclides = nuclides.union(self.r.blueprints.nucsToForceInXsGen)

        numDensities = subjectObject.getNuclideNumberDensities(nuclides)

        for nucName, dens in zip(nuclides, numDensities):
            nuc = nuclideBases.byName[nucName]
            if isinstance(nuc, nuclideBases.LumpNuclideBase):
                continue  # skip LFPs here but add individual FPs below.

            if isinstance(subjectObject, components.Component):
                if self.ductHeterogeneous and "Homogenized" in subjectObject.name:
                    # Nuclide temperatures representing heterogeneous model component temperatures
                    nucTemperatureInC = self._getAvgNuclideTemperatureInC(nucName)
                else:
                    # Heterogeneous number densities and temperatures
                    nucTemperatureInC = subjectObject.temperatureInC
            else:
                # Homogeneous number densities and temperatures
                nucTemperatureInC = self._getAvgNuclideTemperatureInC(nucName)

            density = max(dens, self.minimumNuclideDensity)
            if nuc in nucDensities:
                nuclideNameFoundMultipleTimes(nucName)
                dens, nucTemperatureInC, nucCategory = nucDensities[nuc]
                density = dens + density
                nucDensities[nuc] = (density, nucTemperatureInC, nucCategory)
                continue

            nucCategory = ""
            # Remove nuclides from detailed fission product dictionary if they are a part of the core materials
            # (e.g., Zr in the U10Zr which is at fuel temperature and Mo in HT9 which is at structure temp)
            if nuc in dfpDensities:
                density += dfpDensities[nuc]
                nucCategory += self.FISSION_PRODUCT_CATEGORY + self._SEPARATOR
                del dfpDensities[nuc]
            elif nucName in self._unusedNuclides:
                nucCategory += self.UNUSED_CATEGORY + self._SEPARATOR
            elif nucName in fuelNuclides:
                nucCategory += self.FUEL_CATEGORY + self._SEPARATOR
            elif nucName in coolantNuclides:
                nucCategory += self.COOLANT_CATEGORY + self._SEPARATOR
            elif nucName in structureNuclides:
                nucCategory += self.STRUCTURE_CATEGORY + self._SEPARATOR

            # Add additional `attributes` to the nuclide categories
            if nucName in objNuclides:
                nucCategory += self.REPRESENTED + self._SEPARATOR
            else:
                nucCategory += self.INF_DILUTE + self._SEPARATOR

            if nucName in depletableNuclides:
                nucCategory += self.DEPLETABLE
            else:
                nucCategory += self.UNDEPLETABLE

            nucDensities[nuc] = (density, nucTemperatureInC, nucCategory)

        if not self._isSourceDriven:
            nucDensities = self._adjustPuFissileDensity(nucDensities)
        fissionProductDensities = self._getDetailedFissionProducts(dfpDensities)

        if self._unusedNuclides:
            runLog.debug(
                "The following unused nuclides (defined in the loading file) are being added to {} at {} C: {}".format(
                    subjectObject,
                    self._getFuelTemperature(),
                    list(self._unusedNuclides),
                )
            )

        # the sortFunc makes orders the nucideDensities and fissionProductDensities by name.
        sortFunc = lambda nb_data_tuple: nb_data_tuple[0].name
        nucDensities = collections.OrderedDict(
            sorted(nucDensities.items(), key=sortFunc)
        )
        fissionProductDensities = collections.OrderedDict(
            sorted(fissionProductDensities.items(), key=sortFunc)
        )
        return nucDensities, fissionProductDensities

    def _getAvgNuclideTemperatureInC(self, nucName):
        """Return the block fuel temperature and the nuclides average temperature in C."""
        # Get the temperature of the nuclide in the block
        xsgm = self.getInterface("xsGroups")
        nucTemperatureInC = xsgm.getNucTemperature(self.xsId, nucName)
        if not nucTemperatureInC or math.isnan(nucTemperatureInC):
            # Assign the fuel temperature to the nuclide if it is None or NaN.
            nucTemperatureInC = (
                self._getFuelTemperature()
            )  # NBD b/c the nuclide is not in problem.
            self._unusedNuclides.add(nucName)

        return nucTemperatureInC

    def _getFuelTemperature(self):
        fuelComponents = self.block.getComponents(Flags.FUEL)
        if not fuelComponents:
            fuelTemperatureInC = self.block.getAverageTempInC()
        else:
            fuelTemperatureInC = np.mean([fc.temperatureInC for fc in fuelComponents])
        if not fuelTemperatureInC or math.isnan(fuelTemperatureInC):
            raise ValueError(
                "The fuel temperature of block {0} is {1} and is not valid".format(
                    self.block, fuelTemperatureInC
                )
            )
        return fuelTemperatureInC

    def _getDetailedFissionProducts(self, dfpDensities):
        """Return a dictionary of fission products not provided in the reactor blueprint nuclides.

        Notes
        -----
        Assumes that all fission products are at the same temperature of the lumped fission product of U238 within the
        block.
        """
        if self.cs[CONF_FP_MODEL] != "noFissionProducts":
            fissProductTemperatureInC = self._getAvgNuclideTemperatureInC("LFP38")
            return {
                fp: (dens, fissProductTemperatureInC, self.FISSION_PRODUCT_CATEGORY)
                for fp, dens in dfpDensities.items()
            }
        return {}

    def _getDetailedFPDensities(self):
        """
        Expands the nuclides in the LFP based on their yields.

        Returns
        -------
        dfpDensities : dict
            Detailed Fission Product Densities. keys are FP names, values are block number densities in atoms/bn-cm.

        Raises
        ------
        IndexError
            The lumped fission products were not initialized on the blocks.
        """
        dfpDensities = {}
        if not self.modelFissionProducts:
            return dfpDensities
        lfpCollection = self.block.getLumpedFissionProductCollection()
        if self.diluteFissionProducts:
            if lfpCollection is None:
                raise ValueError(
                    "Lumped fission products are not initialized. Did interactAll BOL run?"
                )
            dfps = lfpCollection.getAllFissionProductNuclideBases()
            for individualFpBase in dfps:
                dfpDensities[individualFpBase] = self.minimumNuclideDensity
        else:
            # expand densities and sum
            dfpDensitiesByName = lfpCollection.getNumberDensities(self.block)
            # now, go through the list and make sure that there aren't any values less than the
            # minimumNuclideDensity; we need to keep trace amounts of nuclides in the problem
            for fpName, fpDens in dfpDensitiesByName.items():
                fp = nuclideBases.byName[fpName]
                dfpDensities[fp] = max(fpDens, self.minimumNuclideDensity)
        return dfpDensities

    def _writeNuclide(
        self, fileObj, nuclide, density, nucTemperatureInC, category, xsIdSpecified=None
    ):
        raise NotImplementedError

    @property
    def _isCriticalBucklingSearchActive(self):
        return self.criticalBucklingSearchActive

    def _writeComment(self, fileObj, msg):
        raise NotImplementedError()

    def _writeGroupStructure(self, fileObj):
        raise NotImplementedError()

    def _adjustPuFissileDensity(self, nucDensities):
        """
        Checks if the minimum fissile composition is lower than the allowed minimum fissile fraction and adds
        additional Pu-239.

        Notes
        -----
        We're going to increase the Pu-239 density to make the ratio of fissile mass to heavy metal mass equal to the
        target ``CONF_MINIMUM_FISSILE_FRACTION``::

            minFrac = (fiss - old + new) / (hm - old + new)
            minFrac * (hm - old + new) = fiss - old + new
            minFrac * (hm - old) + old - fiss = new * (1 - minFrac)
            new = (minFrac * (hm - old) + old - fiss) / (1 - minFrac)

        where::

            minFrac = ``CONF_MINIMUM_FISSILE_FRACTION`` setting
            fiss = fissile mass of block
            hm = heavy metal mass of block
            old = number density of Pu-239 before adjustment
            new = number density of Pu-239 after adjustment

        """
        minFrac = self.cs[CONF_MINIMUM_FISSILE_FRACTION]
        fiss = sum(dens[0] for nuc, dens in nucDensities.items() if nuc.isFissile())
        hm = sum(dens[0] for nuc, dens in nucDensities.items() if nuc.isHeavyMetal())

        if fiss / hm < minFrac:
            pu239 = nuclideBases.byName["PU239"]
            old, temp, msg = nucDensities[pu239]
            new = (minFrac * (hm - old) + old - fiss) / (1 - minFrac)
            nucDensities[pu239] = (new, temp, msg)
            runLog.warning(
                f"Adjusting Pu-239 number densities in {self.block} from {old} to {new} "
                f"to meet minimum fissile fraction of {minFrac}."
            )
        return nucDensities

    def _getDriverBlock(self):
        """Return the block that is driving the representative block for this writer."""
        xsgm = self.getInterface("xsGroups")
        return xsgm.representativeBlocks.get(self.driverXsID, None)


def _groupNuclidesByTemperature(nuclides):
    """
    Creates a dictionary of temperatures and nuclides at those temperatures.

    Nuclides is a dictionary with ``NuclideBase`` objects as keys, and
    the density, temperature, and category of those nuclides as values.

    Notes
    -----
    The temperature will be rounded to a number of digits according to ``_NUM_DIGITS_ROUND_TEMPERATURE``,
    because the average temperature for each nuclide can vary down to numerical precision,
    i.e. 873.15 and 873.15000000001

    """
    tempDict = {}
    for nuclide, values in nuclides.items():
        temperature = round(
            values[_NUCLIDE_VALUES_TEMPERATURE_INDEX], _NUM_DIGITS_ROUND_TEMPERATURE
        )
        if temperature not in tempDict:
            tempDict[temperature] = {nuclide: values}
        else:
            tempDict[temperature][nuclide] = values
    return tempDict
