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
Mixed-oxide (MOX) ceramic fuel.

A definitive source for these properties is [#ornltm20002]_.

.. [#ornltm20002] Thermophysical Properties of MOX and UO2 Fuels Including the Effects of Irradiation. S.G. Popov, et.al. 
    Oak Ridge National Laboratory. ORNL/TM-2000/351 https://rsicc.ornl.gov/fmdp/tm2000-351.pdf

"""
from armi.materials.uraniumOxide import UraniumOxide
from armi.materials import material
from armi.nucDirectory import nucDir


class MOX(UraniumOxide):
    """
    MOX fuel.

    Some parameters (density, thermal conductivity, etc) are inherited from UraniumOxide.
    These parameters are sufficiently equivalent to pure UO2 in the literature to leave them unchanged.

    Specific MOX mixtures may be defined in blueprints under custom isotopics.
    """

    name = "MOX"

    theoreticalDensityFrac = 1.0  # Default value

    enrichedNuclide = "U235"

    def applyInputParams(
        self, U235_wt_frac=None, TD_frac=None, mass_frac_PU02=None, *args, **kwargs
    ):
        if U235_wt_frac:
            self.adjustMassEnrichment(U235_wt_frac)

        td = TD_frac
        if td:
            self.adjustTD(td)
        else:
            self.adjustTD(1.00)  # default to fully dense.

        if mass_frac_PU02:
            self.setMassFracPuO2(mass_frac_PU02)
        material.FuelMaterial.applyInputParams(self, *args, **kwargs)

    def getMassFracPuO2(self):
        massFracPu = sum(
            [self.getMassFrac(n) for n in nucDir.getNuclideNames(elementSymbol="PU")]
        )
        massFracU = sum(
            [self.getMassFrac(n) for n in nucDir.getNuclideNames(elementSymbol="U")]
        )
        return massFracPu / (massFracPu + massFracU)

    def setMassFracPuO2(self, massFracPuO2):
        massFracPu = sum(
            [self.getMassFrac(n) for n in nucDir.getNuclideNames(elementSymbol="PU")]
        )
        massFracU = sum(
            [self.getMassFrac(n) for n in nucDir.getNuclideNames(elementSymbol="U")]
        )
        total = massFracU + massFracPu

        for Pu in nucDir.getNuclideNames("PU"):
            self.setMassFrac(
                Pu, self.getMassFrac(Pu) / massFracPu * massFracPuO2 * total
            )

        for U in nucDir.getNuclideNames("PU"):
            self.setMassFrac(
                U, self.getMassFrac(U) / massFracU * (1 - massFracPuO2) * total
            )

    def getMolFracPuO2(self):
        molweightUO2 = (
            270.02771  # Approximation, does not include variance due to isotopes
        )
        molweightPuO2 = (
            275.9988  # Approximation, does not include variance due to isotopes
        )

        massFracPuO2 = self.getMassFracPuO2()
        massFracUO2 = 1 - massFracPuO2
        return massFracPuO2 * molweightUO2 / massFracUO2 / molweightPuO2

    def setDefaultMassFracs(self):

        r""" UO2 + PuO2 mixture mass fractions.

        Pu238: 238.0495599 g/mol
        Pu239: 239.0521634 g/mol
        Pu240: 240.0538135 g/mol
        Pu241: 241.0568515 g/mol
        Pu242: 242.0587426 g/mol
        Am241: 241.0568291 g/mol
        U-235: 235.0439299 g/mol
        U-238: 238.0507882 g/mol
        Oxygen: 15.9994 g/mol

        JOYO MOX mass fraction calculation:
        Pu mixture: 0.1% Pu238 + 76.82% Pu239 + 19.23% Pu240 + 2.66% Pu241 + 0.55% Pu242 + 0.64% Am241
        Pu atomic mass: 239.326469 g/mol

        U mixture: 22.99% U-235 + 77.01% U-238
        U atomic mass: 237.359511 g/mol

        UPu mixture: 17.7% Pu mixture + 82.3% U mixture
        UPu atomic mass: 237.70766 g/mol

        2 moles of oxygen/1 mole of UPu

        grams of UPu = 237.70766 g/mol* 1 mol  = 237.70766 g
        grams of oxygen= 15.9994 g/mol * 2 mol =  31.9988 g

        total= 269.70646 g.

        Mass fraction UPu : 237.70766/269.70646 = 0.881357
        Mass fraction Pu mixture: 0.177*237.70766/269.70646 = 0.156000
        Mass fraction U mixture: 0.823*237.70766/269.70646 = 0.725356

        Mass fraction Pu238: 0.001*42.074256/269.70646   = 0.000156
        Mass fraction Pu239: 0.7682*42.074256/269.70646  = 0.119839
        Mass fraction Pu240: 0.1923*42.074256/269.70646  = 0.029999
        Mass fraction Pu241: 0.0266*42.074256/269.70646  = 0.004150
        Mass fraction Pu242: 0.0055*42.074256/269.70646  = 0.000858
        Mass fraction Am241: 0.0064*42.074256/269.70646  = 0.000998
        Mass fraction U-235: 0.2299*195.633404/269.70646 = 0.166759
        Mass fraction U-238: 0.7701*195.633404/269.70646 = 0.558597
        Mass fraction O:     31.9988/269.70646           = 0.118643
        """
        self.setMassFrac("PU238", 0.000156)
        self.setMassFrac("PU239", 0.119839)
        self.setMassFrac("PU240", 0.029999)
        self.setMassFrac("PU241", 0.004150)
        self.setMassFrac("PU242", 0.000858)
        self.setMassFrac("AM241", 0.000998)
        self.setMassFrac("U235", 0.166759)
        self.setMassFrac("U238", 0.558597)
        self.setMassFrac("O16", 0.118643)

    def meltingPoint(self):
        """
        Melting point in K - ORNL/TM-2000/351

        Melting point is a function of PuO2 mol fraction.
        The liquidus Tl and solidus Ts temperatures in K are given by:
        Tl(y) = 3120.0 - 388.1*y - 30.4*y^2
        Ts(y) = 3120.0 - 655.3*y + 336.4*y^2 - 99.9*y^3
        where y is the mole fraction of PuO2
        This function returns the solidus temperature.
        Does not take into account changes in the melting temp due to burnup.
        """
        molFracPuO2 = self.getMolFracPuO2()
        return (
            3120.0
            - 655.3 * molFracPuO2
            + 336.4 * molFracPuO2 ** 2
            - 99.9 * molFracPuO2 ** 3
        )
