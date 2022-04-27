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
Alloy-200 are wrought commercially pure nickel.
"""

from armi.materials.material import Material
from armi.utils.units import getTc


class Alloy200(Material):

    name = "Alloy200"
    references = {
        "linearExpansion": [
            "Alloy 200/201 Data Sheet http://www.jacquet.biz/JACQUET/USA/files/JCQusa-alloy-200-201.pdf"
        ],
        "refDens": [
            "Alloy 200/201 Data Sheet http://www.jacquet.biz/JACQUET/USA/files/JCQusa-alloy-200-201.pdf"
        ],
        "referenceMaxPercentImpurites": [
            "Alloy 200/201 Data Sheet http://www.jacquet.biz/JACQUET/USA/files/JCQusa-alloy-200-201.pdf"
        ],
    }

    modelConst = {
        "a0": 1.21620e-5,
        "a1": 8.30010e-9,
        "a2": -3.94985e-12,
        "TRefa": 20,  # Constants for thermal expansion
    }

    referenceMaxPercentImpurites = [
        ("C", 0.15),
        ("MN", 0.35),
        ("S", 0.01),
        ("SI", 0.35),
        ("CU", 0.25),
        ("FE", 0.40),
    ]

    def linearExpansionPercent(self, Tk=None, Tc=None):
        r"""
        Returns percent linear thermal expansion of Alloy 200

        Parameters
        ----------
        Tk : float, optional
            temperature in degrees Kelvin
        Tc : float, optional
            temperature in degrees Celsius

        Returns
        -------
        linearExpansionPercent : float
            percent linear thermal expansion of Alloy 200 (%)
        """
        Tc = getTc(Tc, Tk)
        self.checkTempRange(-200, 1000, Tc, "linear expansion percent")
        linearExpansionPercent = self.calcLinearExpansionPercentMetal(T=Tc)
        return linearExpansionPercent

    def linearExpansion(self, Tk=None, Tc=None):
        r"""
        Returns instantaneous coefficient of thermal expansion of Alloy 200

        Parameters
        ----------
        Tk : float, optional
            temperature in degrees Kelvin
        Tc : float, optional
            temperature in degrees Celsius

        Returns
        -------
        linearExpansion : float
            instantaneous coefficient of thermal expansion of Alloy 200 (1/C)
        """
        Tc = getTc(Tc, Tk)
        self.checkTempRange(-200, 1000, Tc, "linear expansion")
        linearExpansion = self.calcLinearExpansionMetal(T=Tc)
        return linearExpansion

    def setDefaultMassFracs(self):
        """
        Notes
        -----
        It is assumed half the max composition for the impurities and the rest is Ni.
        """
        nickleMassFrac = 1.0

        for elementSymbol, massFrac in self.referenceMaxPercentImpurites:
            assumedMassFrac = massFrac * 0.01 / 2.0
            self.setMassFrac(elementSymbol, assumedMassFrac)
            nickleMassFrac -= assumedMassFrac

        self.setMassFrac("NI", nickleMassFrac)

        self.p.refDens = 8.9
