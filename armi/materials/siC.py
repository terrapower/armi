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

"""Silicon Carbide."""

import math

from armi.materials.material import Material
from armi.nucDirectory import thermalScattering as tsl
from armi.utils.units import getTc


class SiC(Material):
    """Silicon Carbide."""

    thermalScatteringLaws = (tsl.fromNameAndCompound("C", tsl.SIC), tsl.fromNameAndCompound("SI", tsl.SIC))
    references = {
        "heat capacity": ["Munro, Material Properties of a-SiC, J. Phys. Chem. Ref. Data, Vol. 26, No. 5, 1997"],
        "cumulative linear expansion": [
            "Munro, Material Properties of a-SiC, J. Phys. Chem. Ref. Data, Vol. 26, No. 5, 1997"
        ],
        "density": ["Munro, Material Properties of a-SiC, J. Phys. Chem. Ref. Data, Vol. 26, No. 5, 1997"],
        "thermal conductivity": ["Munro, Material Properties of a-SiC, J. Phys. Chem. Ref. Data, Vol. 26, No. 5, 1997"],
    }

    propertyEquation = {
        "heat capacity": "1110 + 0.15*Tc - 425*math.exp(-0.003*Tc)",
        "cumulative linear expansion": "(4.22 + 8.33E-4*Tc-3.51*math.exp(-0.00527*Tc))*1.0E-6",
        "density": "(rho0*(1 + cA*(Tc - Tc0))**(-3))*1.0E3",
        "thermal conductivity": "(52000*math.exp(-1.24E-5*Tc))/(Tc+437)",
    }

    propertyUnits = {
        "melting point": "K",
        "heat capacity": "J kg^-1 K^-1",
        "cumulative linear expansion": "K^-1",
        "density": "kg m^-3",
        "thermal conductivity": "W m^-1 K^-1",
    }

    propertyNotes = {}

    propertyValidTemperature = {
        "cumulative linear expansion": ((0, 1500), "C"),
        "density": ((0, 1500), "C"),
        "heat capacity": ((0, 2000), "C"),
        "thermal conductivity": ((0, 2000), "C"),
    }

    refTempK = 298.15

    def setDefaultMassFracs(self):
        self.setMassFrac("C", 0.299547726)
        self.setMassFrac("SI", 0.700452274)

        self.refDens = 3.21

    def meltingPoint(self):
        return 3003.0

    def heatCapacity(self, Tc=None, Tk=None):
        Tc = getTc(Tc, Tk)
        self.checkPropertyTempRange("heat capacity", Tc)
        return 1110 + 0.15 * Tc - 425 * math.exp(-0.003 * Tc)

    def cumulativeLinearExpansion(self, Tk=None, Tc=None):
        Tc = getTc(Tc, Tk)
        self.checkPropertyTempRange("cumulative linear expansion", Tc)
        return (4.22 + 8.33e-4 * Tc - 3.51 * math.exp(-0.00527 * Tc)) * 1.0e-6

    def pseudoDensity(self, Tc=None, Tk=None):
        Tc = getTc(Tc, Tk)
        self.checkPropertyTempRange("density", Tc)
        rho0 = 3.16
        Tc0 = 0.0
        cA = self.cumulativeLinearExpansion(Tc=Tc)
        return rho0 * (1 + cA * (Tc - Tc0)) ** (-3)

    def thermalConductivity(self, Tc=None, Tk=None):
        Tc = getTc(Tc, Tk)
        self.checkPropertyTempRange("thermal conductivity", Tc)
        return (52000 * math.exp(-1.24e-5 * Tc)) / (Tc + 437)
