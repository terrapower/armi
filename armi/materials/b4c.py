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
Boron carbide; a very typical reactor control material.

Note that this material defaults to a theoretical density fraction of 0.9, reflecting
the difficulty of producing B4C at 100% theoretical density in real life. To get
different fraction, use the `TD_frac` material modification in your assembly definition.
"""

from armi import runLog
from armi.materials import material
from armi.nucDirectory import nuclideBases
from armi.utils.units import getTc

DEFAULT_THEORETICAL_DENSITY_FRAC = 0.90
DEFAULT_MASS_DENSITY = 2.52
NATURAL_B10_NUM_FRAC = 0.199


class B4C(material.Material):
    enrichedNuclide = "B10"
    propertyValidTemperature = {"linear expansion percent": ((25, 500), "C")}

    def __init__(self):
        self.b10WtFrac = None
        # TODO notes for PR: need to make this a class attribute so 1. a class that inherits from it has it and 2. so
        # we can have a natural default that can be edited according to material modifications. I want this here because
        # downstream there's a different natural b10 frac used and I need the set default mass fracs to work for both
        # fracs
        self.b10NumFrac = NATURAL_B10_NUM_FRAC
        super().__init__()

    def applyInputParams(self, B10_wt_frac=None, theoretical_density=None, TD_frac=None, *args, **kwargs):
        if B10_wt_frac is not None:
            # we can't just use the generic enrichment adjustment here because the
            # carbon has to change with enrich.
            self.b10WtFrac = B10_wt_frac
            self.b10NumFrac = self.getNumEnrichFromMassEnrich(self.b10WtFrac)
            self.adjustMassEnrichment(B10_wt_frac)
        if theoretical_density is not None:
            runLog.warning(
                "The 'theoretical_density' material modification for B4C will be "
                "deprecated. Update your inputs to use 'TD_frac' instead.",
                single=True,
            )
            if TD_frac is not None:
                runLog.warning(
                    f"Both 'theoretical_density' and 'TD_frac' are specified for {self}. 'TD_frac' will be used."
                )
            else:
                self.updateTD(theoretical_density)
        if TD_frac is not None:
            self.updateTD(TD_frac)

    def updateTD(self, td: float) -> None:
        self.theoreticalDensityFrac = td
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
            raise ValueError("massEnrichment {} is unphysical for B4C".format(massEnrichment))

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
            self.parent.setMassFracs({"B10": boron10MassGrams, "B11": boron11MassGrams, "C": carbonMassGrams})

        return boron10MassGrams, boron11MassGrams, carbonMassGrams

    def setDefaultMassFracs(self) -> None:
        r"""B4C mass fractions. Using Natural B4C. 19.9% B-10/ 80.1% B-11
        Boron: 10.811 g/mol
        Carbon:  12.0107 g/mol.

        4 moles of boron/1 mole of carbon

        grams of boron-10 = 10.01 g/mol* 4 mol * 0.199   =  7.96796 g
        grams of boron-11 = 11.01 g/mol* 4 mol * 0.801   = 35.27604 g
        grams of carbon= 12.0107 g/mol * 1 mol = 12.0107 g

        total=55.2547 g.
        Mass fractions are computed from this.
        """
        massEnrich = self.getMassEnrichmentFromNumEnrich(self.b10NumFrac)

        gBoron10, gBoron11, gCarbon = self.setNewMassFracsFromMassEnrich(massEnrichment=massEnrich)
        self.setMassFrac("B10", gBoron10)
        self.setMassFrac("B11", gBoron11)
        self.setMassFrac("C", gCarbon)
        self.refDens = DEFAULT_MASS_DENSITY
        # TD reference : Dunner, Heuvel, "Absorber Materials for control rod systems of fast breeder reactors"
        # Journal of nuclear materials, 124, 185-194, (1984)."
        self.theoreticalDensityFrac = DEFAULT_THEORETICAL_DENSITY_FRAC  # normally is around 0.88-93.

    # TODO there are two opposite methods here, which may be able to get cleaned up with better class design. Come back
    # to this.
    @staticmethod
    def getNumEnrichFromMassEnrich(b10WtFrac) -> float:
        """Given a B10 weight fraction, give the B10 number fraction."""
        b10AtomicMass = nuclideBases.byName["B10"].weight
        b11AtomicMass = nuclideBases.byName["B11"].weight
        b10NumFrac = b10WtFrac / b10AtomicMass / (b10WtFrac / b10AtomicMass + (1.0 - b10WtFrac) / b11AtomicMass)
        return b10NumFrac

    @staticmethod
    def getMassEnrichmentFromNumEnrich(b10NumFrac) -> float:
        """Given a B10 number fraction, give the B10 weight fraction."""
        b10AtomicMass = nuclideBases.byName["B10"].weight
        b11AtomicMass = nuclideBases.byName["B11"].weight
        return b10NumFrac * b10AtomicMass / (b10NumFrac * b10AtomicMass + (1.0 - b10NumFrac) * b11AtomicMass)

    def pseudoDensity(self, Tk: float = None, Tc: float = None) -> float:
        """
        Return density that preserves mass when thermally expanded in 2D.

        Notes
        -----
        - applies theoretical density of B4C to parent method
        """
        return material.Material.pseudoDensity(self, Tk, Tc) * self.theoreticalDensityFrac

    def density(self, Tk: float = None, Tc: float = None) -> float:
        """
        Return density that preserves mass when thermally expanded in 3D.

        Notes
        -----
        - applies theoretical density of B4C to parent method
        """
        return material.Material.density(self, Tk, Tc) * self.theoreticalDensityFrac

    def linearExpansionPercent(self, Tk: float = None, Tc: float = None) -> float:
        """Boron carbide expansion. Very preliminary."""
        Tc = getTc(Tc, Tk)
        self.checkPropertyTempRange("linear expansion percent", Tc)
        deltaT = Tc - 25
        dLL = deltaT * 4.5e-6
        return dLL * 100
