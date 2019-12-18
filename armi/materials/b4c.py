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

"""Boron carbide; a very typical reactor control material."""
from armi.materials import material
from armi.nucDirectory import nuclideBases
from armi import runLog
from armi.utils.units import getTc

DEFAULT_THEORETICAL_DENSITY_FRAC = 0.90
DEFAULT_MASS_DENSITY = 2.52


class B4C(material.Material):
    name = "B4C"
    enrichedNuclide = "B10"

    def applyInputParams(
        self, B10_wt_frac=None, theoretical_density=None, *args, **kwargs
    ):
        if B10_wt_frac:
            # we can't just use the generic enrichment adjustment here because the
            # carbon has to change with enrich.
            self.adjustMassEnrichment(B10_wt_frac)
        if theoretical_density is not None:
            self.p.theoreticalDensityFrac = theoretical_density
            self.clearCache()

    def setNewMassFracsFromMassEnrich(self, massEnrichment):
        r"""
        Calculate the mass fractions for a given  mass enrichment and set it on any parent.

        Parameters
        ----------
        massEnrichment : float
            The mass enrichment as a fraction.

        Returns
        -------
        boron10MassGrams, boron11MassGrams, carbonMassGrams : float
            The resulting mass of each nuclide/element

        Notes
        -----
        B-10: 10.012 g/mol
        B-11: 11.009 g/mol
        Carbon:  12.0107 g/mol

        4 moles of boron/1 mole of carbon

        grams of boron-10 = 10.012 g/mol* 4 mol * 0.199   =  7.969552 g
        grams of boron-11 = 11.009 g/mol* 4 mol * 0.801   = 35.272836 g
        grams of carbon= 12.0107 g/mol * 1 mol = 12.0107 g

        from number enrichment mi:
        mB10 = nB10*AB10 /(nB10*AB10 + nB11*AB11)
        """
        if massEnrichment < 0 or massEnrichment > 1:
            raise ValueError(
                "massEnrichment {} is unphysical for B4C".format(massEnrichment)
            )

        b10AtomicMass = nuclideBases.byName["B10"].weight
        b11AtomicMass = nuclideBases.byName["B11"].weight
        b10NumEnrich = (massEnrichment / b10AtomicMass) / (
            massEnrichment / b10AtomicMass + (1 - massEnrichment) / b11AtomicMass
        )
        b11NumEnrich = 1.0 - b10NumEnrich

        cAtomicMass = nuclideBases.byName["C"].weight

        boron10MassGrams = b10AtomicMass * b10NumEnrich * 4.0
        boron11MassGrams = b11AtomicMass * b11NumEnrich * 4.0
        carbonMassGrams = cAtomicMass

        gTotal = boron10MassGrams + boron11MassGrams + carbonMassGrams

        boron10MassGrams /= gTotal
        boron11MassGrams /= gTotal
        carbonMassGrams /= gTotal
        if self.parent:
            self.parent.setMassFracs(
                {"B10": boron10MassGrams, "B11": boron11MassGrams, "C": carbonMassGrams}
            )

        return boron10MassGrams, boron11MassGrams, carbonMassGrams

    def setDefaultMassFracs(self):
        r"""B4C mass fractions. Using Natural B4C. 19.9% B-10/ 80.1% B-11
        Boron: 10.811 g/mol
        Carbon:  12.0107 g/mol

        4 moles of boron/1 mole of carbon

        grams of boron-10 = 10.01 g/mol* 4 mol * 0.199   =  7.96796 g
        grams of boron-11 = 11.01 g/mol* 4 mol * 0.801   = 35.27604 g
        grams of carbon= 12.0107 g/mol * 1 mol = 12.0107 g

        total=55.2547 g.
        Mass fractions are computed from this.

        """
        massEnrich = self.getMassEnrichmentFromNumEnrich(naturalB10NumberFraction=0.199)

        gBoron10, gBoron11, gCarbon = self.setNewMassFracsFromMassEnrich(
            massEnrichment=massEnrich
        )
        self.setMassFrac("B10", gBoron10)
        self.setMassFrac("B11", gBoron11)
        self.setMassFrac("C", gCarbon)
        self.p.refDens = DEFAULT_MASS_DENSITY
        # TD reference : Dunner, Heuvel, "Absorber Materials for control rod systems of fast breeder reactors"
        # Journal of nuclear materials, 124, 185-194, (1984)."
        self.p.theoreticalDensityFrac = (
            DEFAULT_THEORETICAL_DENSITY_FRAC  # normally is around 0.88-93.
        )

    def getMassEnrichmentFromNumEnrich(self, naturalB10NumberFraction):
        b10AtomicMass = nuclideBases.byName["B10"].weight
        b11AtomicMass = nuclideBases.byName["B11"].weight
        return (
            naturalB10NumberFraction
            * b10AtomicMass
            / (
                naturalB10NumberFraction * b10AtomicMass
                + (1.0 - naturalB10NumberFraction) * b11AtomicMass
            )
        )

    def density(self, Tk=None, Tc=None):
        """
        mass density
        """
        density = material.Material.density(self, Tk, Tc)
        theoreticalDensityFrac = self.p.theoreticalDensityFrac
        if theoreticalDensityFrac is None:
            theoreticalDensityFrac = 1.0
            runLog.warning(
                "Assumption: 100% theoretical density",
                label="Assumption: B4C is at 100% theoretical density",
                single=True,
            )
        return density * theoreticalDensityFrac  # g/cc

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """Boron carbide expansion. Very preliminary"""
        Tc = getTc(Tc, Tk)
        self.checkTempRange(25, 500, Tc, "linear expansion percent")
        deltaT = Tc - 25
        dLL = deltaT * 4.5e-6 * 100  # percent
        return dLL
