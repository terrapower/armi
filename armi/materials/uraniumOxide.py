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
Uranium Oxide properties.

UO2 is a common ceramic nuclear fuel form. It's properties are well known. This mostly
uses data from [#ornltm2000]_.

.. [#ornltm2000] Thermophysical Properties of MOX and UO2 Fuels Including the Effects of Irradiation. S.G. Popov,
    et.al. Oak Ridge National Laboratory. ORNL/TM-2000/351 https://rsicc.ornl.gov/fmdp/tm2000-351.pdf
"""

import collections
import math

from numpy import interp

from armi import runLog
from armi.materials import material
from armi.nucDirectory import nuclideBases as nb
from armi.nucDirectory import thermalScattering as tsl
from armi.utils.units import getTk

HeatCapacityConstants = collections.namedtuple("HeatCapacityConstants", ["c1", "c2", "c3", "theta", "Ea"])


class UraniumOxide(material.FuelMaterial, material.SimpleSolid):
    enrichedNuclide = "U235"

    REFERENCE_TEMPERATURE = 27

    # ORNL/TM-2000/351 section 4.3
    heatCapacityConstants = HeatCapacityConstants(c1=302.27, c2=8.463e-3, c3=8.741e7, theta=548.68, Ea=18531.7)

    __meltingPoint = 3123.0

    propertyUnits = {"heat capacity": "J/mol-K"}

    propertyValidTemperature = {
        "density": ((300, 3100), "K"),
        "heat capacity": ((298.15, 3120), "K"),
        "linear expansion": ((273, 3120), "K"),
        "linear expansion percent": ((273, __meltingPoint), "K"),
        "thermal conductivity": ((300, 3000), "K"),
    }

    references = {
        "thermal conductivity": "Thermal conductivity of uranium dioxide by nonequilibrium molecular dynamics "
        + "simulation. S. Motoyama. Physical Review B, Volume 60, Number 1, July 1999",
        "linear expansion": "Thermophysical Properties of MOX and UO2 Fuels Including the Effects of Irradiation. "
        + "S.G. Popov, et.al. Oak Ridge National Laboratory. ORNL/TM-2000/351",
        "heat capacity": "ORNL/TM-2000/351",
    }

    thermalScatteringLaws = (
        tsl.byNbAndCompound[nb.byName["U"], tsl.UO2],
        tsl.byNbAndCompound[nb.byName["O"], tsl.UO2],
    )

    # Thermal conductivity values taken from:
    # Thermal conductivity of uranium dioxide by nonequilibrium molecular dynamics simulation. S. Motoyama.
    #    Physical Review B, Volume 60, Number 1, July 1999
    thermalConductivityTableK = [
        300,
        600,
        900,
        1200,
        1500,
        1800,
        2100,
        2400,
        2700,
        3000,
    ]

    thermalConductivityTable = [
        7.991,
        4.864,
        3.640,
        2.768,
        2.567,
        2.294,
        2.073,
        1.891,
        1.847,
        1.718,
    ]

    def __init__(self):
        material.FuelMaterial.__init__(self)
        self.refDens = self.density(Tk=self.refTempK)

    def applyInputParams(self, U235_wt_frac: float = None, TD_frac: float = None, *args, **kwargs) -> None:
        if U235_wt_frac is not None:
            self.adjustMassEnrichment(U235_wt_frac)

        td = TD_frac
        if td is not None:
            if td > 1.0:
                runLog.warning(
                    "Theoretical density frac for {0} is {1}, which is >1".format(self, td),
                    single=True,
                    label="Large theoretical density",
                )
            elif td == 0:
                runLog.warning(
                    f"Theoretical density frac for {self} is zero!",
                    single=True,
                    label="Zero theoretical density",
                )
            self.adjustTD(td)

        material.FuelMaterial.applyInputParams(self, *args, **kwargs)

    def setDefaultMassFracs(self) -> None:
        """UO2 mass fractions. Using Natural Uranium without U234."""
        u235Weight = 235.043929425
        u238Weight = 238.050788298
        oxygenWeight = 15.999304875697801
        u235Abundance = 0.007204
        u238Abundance = 1.0 - u235Abundance  # neglect U234 and keep U235 at natural level
        gramsIn1Mol = 2 * oxygenWeight + u235Abundance * u235Weight + u238Abundance * u238Weight

        self.setMassFrac("U235", u235Weight * u235Abundance / gramsIn1Mol)
        self.setMassFrac("U238", u238Weight * u238Abundance / gramsIn1Mol)
        self.setMassFrac("O", 2 * oxygenWeight / gramsIn1Mol)

    def meltingPoint(self):
        """
        Melting point in K.

        From [#ornltm2000]_.
        """
        return self.__meltingPoint

    def density(self, Tk: float = None, Tc: float = None) -> float:
        """
        Density in (g/cc).

        Polynomial line fit to data from [#ornltm2000]_ on page 11.
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("density", Tk)

        return (-1.01147e-7 * Tk**2 - 1.29933e-4 * Tk + 1.09805e1) * self.getTD()

    def heatCapacity(self, Tk: float = None, Tc: float = None) -> float:
        """
        Heat capacity in J/kg-K.

        From Section 4.3 in  [#ornltm2000]_
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("heat capacity", Tk)

        hcc = self.heatCapacityConstants
        # eq 4.2
        specificHeatCapacity = (
            hcc.c1 * (hcc.theta / Tk) ** 2 * math.exp(hcc.theta / Tk) / (math.exp(hcc.theta / Tk) - 1.0) ** 2
            + 2 * hcc.c2 * Tk
            + hcc.c3 * hcc.Ea * math.exp(-hcc.Ea / Tk) / Tk**2
        )
        return specificHeatCapacity

    def linearExpansion(self, Tk: float = None, Tc: float = None) -> float:
        """
        Linear expansion coefficient.

        Curve fit from data in [#ornltm2000]_
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion", Tk)

        return 1.06817e-12 * Tk**2 - 1.37322e-9 * Tk + 1.02863e-5

    def linearExpansionPercent(self, Tk: float = None, Tc: float = None) -> float:
        """
        Return dL/L.

        From Section 3.3 of [#ornltm2000]_
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion percent", Tk)

        if Tk >= 273.0 and Tk < 923.0:
            return (-2.66e-03 + 9.802e-06 * Tk - 2.705e-10 * Tk**2 + 4.391e-13 * Tk**3) * 100.0
        else:
            return (-3.28e-03 + 1.179e-05 * Tk - 2.429e-09 * Tk**2 + 1.219e-12 * Tk**3) * 100.0

    def thermalConductivity(self, Tk: float = None, Tc: float = None) -> float:
        """
        Thermal conductivity.

        Ref: Thermal conductivity of uranium dioxide by nonequilibrium molecular dynamics
        simulation. S. Motoyama. Physical Review B, Volume 60, Number 1, July 1999
        """
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("thermal conductivity", Tk)

        return interp(Tk, self.thermalConductivityTableK, self.thermalConductivityTable)


class UO2(UraniumOxide):
    """Another name for UraniumOxide."""

    def __init__(self):
        UraniumOxide.__init__(self)
        self._name = "UraniumOxide"
