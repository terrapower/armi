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

# cython: profile=False
"""
Uranium Oxide properties. 

UO2 is a common ceramic nuclear fuel form. It's properties are well known. This mostly
uses data from [#ornltm2000]_.

.. [#ornltm2000] Thermophysical Properties of MOX and UO2 Fuels Including the Effects of Irradiation. S.G. Popov,
    et.al. Oak Ridge National Laboratory. ORNL/TM-2000/351 https://rsicc.ornl.gov/fmdp/tm2000-351.pdf
"""
import math
import collections

from numpy import interp

from armi.nucDirectory import nuclideBases
from armi.utils.units import getTk
from armi.materials import material
from armi import runLog

HeatCapacityConstants = collections.namedtuple(
    "HeatCapacityConstants", ["c1", "c2", "c3", "theta", "Ea"]
)


class UraniumOxide(material.FuelMaterial):
    name = "Uranium Oxide"
    references = {
        "thermal conductivity": "Thermal conductivity of uranium dioxide by nonequilibrium molecular dynamics simulation. S. Motoyama. Physical Review B, Volume 60, Number 1, July 1999",
        "linear expansion": "Thermophysical Properties of MOX and UO2 Fuels Including the Effects of Irradiation. S.G. Popov, et.al. Oak Ridge National Laboratory. ORNL/TM-2000/351",
        "heat capacity": "ORNL/TM-2000/351",
    }
    propertyUnits = {"heat capacity": "J/mol-K"}

    theoreticalDensityFrac = 1.0  # Default value
    """Thermal conductivity values taken from:
    Thermal conductivity of uranium dioxide by nonequilibrium molecular dynamics simulation. S. Motoyama. Physical Review B, Volume 60, Number 1, July 1999"""
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

    # ORNL/TM-2000/351 section 4.3
    heatCapacityConstants = HeatCapacityConstants(
        c1=302.27, c2=8.463e-3, c3=8.741e7, theta=548.68, Ea=18531.7
    )

    enrichedNuclide = "U235"

    def adjustTD(self, val):
        self.theoreticalDensityFrac = val

    def getTD(self):
        return self.theoreticalDensityFrac

    def applyInputParams(self, U235_wt_frac=None, TD_frac=None, *args, **kwargs):
        if U235_wt_frac:
            self.adjustMassEnrichment(U235_wt_frac)

        td = TD_frac
        if td:
            if td > 1.0:
                runLog.warning(
                    "Theoretical density frac for {0} is {1}, which is >1"
                    "".format(self, td),
                    single=True,
                    label="Large theoretical density",
                )
            self.adjustTD(td)
        else:
            self.adjustTD(1.00)  # default to fully dense.
        material.FuelMaterial.applyInputParams(self, *args, **kwargs)

    def setDefaultMassFracs(self):
        r"""
        UO2 mass fractions. Using Natural Uranium without U234
        """
        u235 = nuclideBases.byName["U235"]
        u238 = nuclideBases.byName["U238"]
        oxygen = nuclideBases.byName["O"]

        u238Abundance = (
            1.0 - u235.abundance
        )  # neglect U234 and keep U235 at natural level
        gramsIn1Mol = (
            2 * oxygen.weight
            + u235.abundance * u235.weight
            + u238Abundance * u238.weight
        )

        self.setMassFrac("U235", u235.weight * u235.abundance / gramsIn1Mol)
        self.setMassFrac("U238", u238.weight * u238Abundance / gramsIn1Mol)
        self.setMassFrac("O", 2 * oxygen.weight / gramsIn1Mol)

    def meltingPoint(self):
        """
        Melting point in K

        From [#ornltm2000]_.
        """
        return 3123.0

    def density(self, Tk=None, Tc=None):
        """
        Density in (g/cc)

        Polynomial line fit to data from [#ornltm2000]_ on page 11.
        """
        Tk = getTk(Tc, Tk)
        self.checkTempRange(300, 3100, Tk, "thermal conductivity")
        return (-1.01147e-7 * Tk ** 2 - 1.29933e-4 * Tk + 1.09805e1) * self.getTD()

    def thermalConductivity(self, Tk=None, Tc=None):
        """
        Thermal conductivity

        Ref: Thermal conductivity of uranium dioxide by nonequilibrium molecular dynamics
        simulation. S. Motoyama. Physical Review B, Volume 60, Number 1, July 1999
        """
        Tk = getTk(Tc, Tk)
        self.checkTempRange(300, 3000, Tk, "density")
        return interp(Tk, self.thermalConductivityTableK, self.thermalConductivityTable)

    def linearExpansion(self, Tk=None, Tc=None):
        """
        Linear expansion coefficient.

        Curve fit from data in [#ornltm2000]_"""
        Tk = getTk(Tc, Tk)
        self.checkTempRange(273, 3120, Tk, "linear expansion")
        return 1.06817e-12 * Tk ** 2 - 1.37322e-9 * Tk + 1.02863e-5

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """
        Return dL/L

        From Section 3.3 of [#ornltm2000]_
        """
        Tk = getTk(Tc, Tk)
        self.checkTempRange(273, self.meltingPoint(), Tk, "linear expansion percent")
        if Tk >= 273.0 and Tk < 923.0:
            return (
                -2.66e-03 + 9.802e-06 * Tk - 2.705e-10 * Tk ** 2 + 4.391e-13 * Tk ** 3
            ) * 100.0
        else:
            return (
                -3.28e-03 + 1.179e-05 * Tk - 2.429e-09 * Tk ** 2 + 1.219e-12 * Tk ** 3
            ) * 100.0

    def heatCapacity(self, Tk=None, Tc=None):
        """
        Heat capacity in J/kg-K.

        From Section 4.3 in  [#ornltm2000]_
        """
        Tk = getTk(Tc, Tk)
        self.checkTempRange(298.15, 3120, Tk, "heat capacity")
        hcc = self.heatCapacityConstants
        # eq 4.2
        specificHeatCapacity = (
            hcc.c1
            * (hcc.theta / Tk) ** 2
            * math.exp(hcc.theta / Tk)
            / (math.exp(hcc.theta / Tk) - 1.0) ** 2
            + 2 * hcc.c2 * Tk
            + hcc.c3 * hcc.Ea * math.exp(-hcc.Ea / Tk) / Tk ** 2
        )
        return specificHeatCapacity


class UO2(UraniumOxide):
    r"""Another name for UraniumOxide"""
    pass
