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
Uranium metal.

Much info is from [AAAFuels]_.

.. [AAAFuels]  Kim, Y S, and Hofman, G L. AAA fuels handbook.. United States: N. p., 2003. Web. doi:10.2172/822554. .
"""

from numpy import interp

from armi import runLog
from armi.materials.material import FuelMaterial
from armi.nucDirectory import nuclideBases as nb
from armi.utils.units import getTk


class Uranium(FuelMaterial):
    enrichedNuclide = "U235"

    materialIntro = ""

    propertyNotes = {"thermal conductivity": ""}

    propertyRawData = {"thermal conductivity": ""}

    propertyUnits = {"thermal conductivity": "W/m-K", "heat capacity": "J/kg-K"}

    propertyEquation = {"thermal conductivity": "21.73 + 0.01591T + 5.907&#215;10<super>-6</super>T<super>2</super>"}

    _heatCapacityTableK = [
        298,
        300,
        400,
        500,
        600,
        700,
        800,
        900,
        941.9,
        942,
        1000,
        1048.9,
        1049,
        1100,
        1200,
        1300,
        1400,
        1407.9,
        1408,
        1500,
        1600,
        1700,
        1800,
        1900,
        2000,
        2100,
        2200,
        2400,
    ]

    _heatCapacityTable = [
        27.665,
        27.700,
        29.684,
        31.997,
        34.762,
        38.021,
        41.791,
        46.081,
        48.038,
        42.928,
        42.928,
        42.928,
        38.284,
        38.284,
        38.284,
        38.284,
        38.284,
        38.284,
        48.660,
        48.660,
        48.660,
        48.660,
        48.660,
        48.660,
        48.660,
        48.660,
        48.660,
        48.660,
    ]  # J/K/mol

    _densityTableK = [
        293,
        400,
        500,
        600,
        700,
        800,
        900,
        940.9,
        941,
        1000,
        1047.9,
        1048,
        1100,
        1200,
        1400,
        1407.9,
        1408,
        1500,
        1600,
    ]

    _densityTable = [
        19.07,
        18.98,
        18.89,
        18.79,
        18.68,
        18.55,
        18.41,
        18.39,
        18.16,
        18.11,
        18.07,
        17.94,
        17.88,
        17.76,
        17.53,
        17.52,
        16.95,
        16.84,
        16.71,
    ]  # g/cc

    _linearExpansionPercent = [
        0.000,
        0.157,
        0.315,
        0.494,
        0.697,
        0.924,
        1.186,
        1.300,
        1.635,
        1.737,
        1.820,
        2.050,
        2.168,
        2.398,
        2.855,
        2.866,
        4.006,
        4.232,
        4.502,
    ]  # %

    _linearExpansionTable = [
        13.9,
        15.2,
        16.9,
        19.0,
        21.4,
        24.3,
        27.7,
        29.1,
        17.3,
        17.3,
        17.3,
        22.9,
        22.9,
        22.9,
        22.9,
        22.9,
        25.5,
        25.5,
        25.5,
    ]  # 1e6/K

    propertyValidTemperature = {
        "thermal conductivity": ((255.4, 1173.2), "K"),
        "heat capacity": ((_heatCapacityTableK[0], _heatCapacityTableK[-1]), "K"),
        "density": ((_densityTableK[0], _densityTableK[-1]), "K"),
        "linear expansion": ((_densityTableK[0], _densityTableK[-1]), "K"),
        "linear expansion percent": ((_densityTableK[0], _densityTableK[-1]), "K"),
    }

    references = {
        "thermal conductivity": ["AAA Fuels Handbook by YS Kim and G.L. Hofman, ANL, Section 6.1.1"],
        "heat capacity": ["AAA Fuels Handbook by YS Kim and GL Hofman, Table 2-14"],
        "melting point": ["AAA Fuels Handbook by YS Kim and GL Hofman, Table 2-13"],
        "density": ["Metallic Fuels Handbook, ANL-NSE-3, Table B.3.3-1"],
        "linear expansion": ["Metallic Fuels Handbook, ANL-NSE-3, Table B.3.3-1"],
        "linear expansion percent": ["Metallic Fuels Handbook, ANL-NSE-3, Table B.3.3-1"],
    }

    refDens = 19.07  # the value corresponding to linearExpansionPercent = 0

    def thermalConductivity(self, Tk: float = None, Tc: float = None) -> float:
        """The thermal conductivity of pure U in W-m/K."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("thermal conductivity", Tk)

        kU = 21.73 + (0.01591 * Tk) + (0.000005907 * Tk**2)
        return kU

    def heatCapacity(self, Tk: float = None, Tc: float = None) -> float:
        """Heat capacity in J/kg-K."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("heat capacity", Tk)

        return interp(Tk, self._heatCapacityTableK, self._heatCapacityTable)

    def setDefaultMassFracs(self) -> None:
        u235 = nb.byLabel["U235"]
        u238 = nb.byLabel["U238"]

        u238Abundance = 1.0 - u235.abundance  # neglect U234 and keep U235 at natural level
        gramsIn1Mol = u235.abundance * u235.weight + u238Abundance * u238.weight

        self.setMassFrac("U235", u235.weight * u235.abundance / gramsIn1Mol)
        self.setMassFrac("U238", u238.weight * u238Abundance / gramsIn1Mol)

    def applyInputParams(self, U235_wt_frac: float = None, TD_frac: float = None, *args, **kwargs):
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

        FuelMaterial.applyInputParams(self, *args, **kwargs)

    def meltingPoint(self):
        """Melting point in K."""
        return 1408

    def density(self, Tk: float = None, Tc: float = None) -> float:
        """Density in g/cc."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("density", Tk)

        return interp(Tk, self._densityTableK, self._densityTable) * self.getTD()

    def pseudoDensity(self, Tk: float = None, Tc: float = None) -> float:
        """2D-expanded density in g/cc."""
        return super().pseudoDensity(Tk=Tk, Tc=Tc) * self.getTD()

    def linearExpansion(self, Tk: float = None, Tc: float = None) -> float:
        """Linear expansion coefficient in 1/K."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion", Tk)

        return interp(Tk, self._densityTableK, self._linearExpansionTable) / 1e6

    def linearExpansionPercent(self, Tk: float = None, Tc: float = None) -> float:
        """Linear expansion percent."""
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion percent", Tk)

        return interp(Tk, self._densityTableK, self._linearExpansionPercent)
