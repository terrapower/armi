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

"""Alloy-200 are wrought commercially pure nickel.

The data in this file exists for testing and demonstration purposes only. Developers of ARMI applications can refer to
this file for a fully worked example of an ARMI material. And this material has proven useful for testing. The data
contained in this file should not be used in production simulations.
"""

from numpy import interp

from armi.materials.material import Material
from armi.utils.units import getTk


class Alloy200(Material):
    references = {
        "linearExpansion": [
            "Alloy 200/201 Data Sheet http://www.jacquet.biz/JACQUET/USA/files/JCQusa-alloy-200-201.pdf"
        ],
        "refDens": ["Alloy 200/201 Data Sheet http://www.jacquet.biz/JACQUET/USA/files/JCQusa-alloy-200-201.pdf"],
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

    propertyValidTemperature = {"linear expansion": ((73.15, 1273.15), "K")}

    referenceMaxPercentImpurites = [
        ("C", 0.15),
        ("MN", 0.35),
        ("S", 0.01),
        ("SI", 0.35),
        ("CU", 0.25),
        ("FE", 0.40),
    ]

    linearExpansionTableK = [
        73.15,
        173.15,
        373.15,
        473.15,
        573.15,
        673.15,
        773.15,
        873.15,
        973.15,
        1073.15,
        1173.15,
        1273.15,
    ]

    linearExpansionTable = [
        10.1e-6,
        11.3e-6,
        13.3e-6,
        13.9e-6,
        14.3e-6,
        14.8e-6,
        15.2e-6,
        15.6e-6,
        15.8e-6,
        16.2e-6,
        16.5e-6,
        16.7e-6,
    ]

    def linearExpansion(self, Tk=None, Tc=None):
        r"""
        Returns instantaneous coefficient of thermal expansion of Alloy 200.

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
        Tk = getTk(Tc, Tk)
        self.checkPropertyTempRange("linear expansion", Tk)

        return interp(Tk, self.linearExpansionTableK, self.linearExpansionTable)

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
        self.refDens = 8.9
