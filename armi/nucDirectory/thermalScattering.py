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
Handle awareness of Thermal Scattering Laws.

Scattering characteristics of thermal neutrons are often significantly different between a free atom and one bound in a
particular molecule. Nuclear data libraries often have special tables to account for the bound states. These data are
commonly represented as S(alpha, beta) tables.

Here we provide objects representing the thermal scattering law (TSL) information. We expect them to be most useful as
class attributes on :py:class:`~armi.materials.material.Material` subclasses to inform physics solvers that support
thermal scattering of the TSLs. See :py:class:`~armi.materials.graphite.Graphite` for an example.

We do not provide special versions of various NuclideBases like C12 because of potential errors in choosing one over the
other

The information contained in here is based on Parsons, LA-UR-18-25096,
https://mcnp.lanl.gov/pdf_files/la-ur-18-25096.pdf

Scattering law data are currently available for a variety of classifications:

* Element in Compound (H in H2O, Be in BeO)
* Element in structure (C in Graphite, Be in metal)

    * Can be separated as crystalline, 30% porous, 10% porous, etc.

* Element in spin isomer (para H, ortho H, para D, ortho D, etc.)
* Compound in phase (solid CH4, liquid CH4, SiO2-alpha, SiO2-beta).
* Just compound (benzene)
* Just isotope (Fe56, Al27)

The labels for these vary across evaluations (e.g. ENDF/B-VII, ENDF/B-VIII, etc.). We provide ENDF/B-III.0 and ACE
labels. Other physics kernels will have to derive their own labels as appropriate in client code.

Like NuclideBase and Element, we want to have only one ThermalScattering instance for each TSL, so we use a module-level
directory called ``byNbAndCompound``. This improves efficiency and allows better cross-referencing when thousands of
material instances would otherwise have identical instances of these.

Thus, in practice, users should rarely instantiate these on their own.
"""

from typing import Tuple, Union

from armi.nucDirectory import elements
from armi.nucDirectory import nuclideBases as nb

BE_METAL = "Be-metal"
BEO = "BeO"
SIC = "SiC"
D2O = "D2O"
H2O = "H2O"
UN = "UN"
UO2 = "UO2"
ZRH = "ZrH"
CRYSTALLINE_GRAPHITE = "crystalline-graphite"
GRAPHITE_10P = "reactor-graphite-10P"
GRAPHITE_30P = "reactor-graphite-30P"


byNbAndCompound = {}


class ThermalScattering:
    """
    Thermal Scattering data.

    Parameters
    ----------
    nuclideBases : INuclide or tuple of INuclide
        One or more nuclide bases whose existence would trigger the inclusion of the TSL. Generally items here will be a
        NaturalNuclideBase like ``nb.byName["C"]`` for Carbon but it is a tuple to capture, e.g. the C and H in
        *methane*.
    compoundName : str, optional
        Label indicating what the subjects are in (e.g. ``"Graphite"`` or ``"H2O"``.
        Can be left off for, e.g. Fe56.
    endf8Label : str, optional
        Label for endf8 evaluation
    aceLabel: str, optional
        ace label
    """

    def __init__(
        self,
        nuclideBases: Union[nb.INuclide, Tuple[nb.INuclide]],
        compoundName: str = None,
        endf8Label: str = None,
        aceLabel: str = None,
    ):
        if isinstance(nuclideBases, nb.INuclide):
            # handle common single entry for convenience
            nuclideBases = [nuclideBases]
        self.nbs = frozenset(set(nuclideBases))
        self.compoundName = compoundName
        self.endf8Label = endf8Label or self._genENDFB8Label()
        self.aceLabel = aceLabel or self._genACELabel()

    def __repr__(self):
        return f"<ThermalScatteringLaw - Compound: {self.compoundName}, Nuclides: {self.nbs}"

    def __hash__(self):
        return hash((self.compoundName, self.nbs))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def getSubjectNuclideBases(self):
        """
        Return all nuclide bases that could be subject to this law.

        In cases where the law is defined by a NaturalNuclideBase, all potential isotopes of the element as well as the
        element it self should trigger it. This helps handle cases where, for example, C or C12 is present.
        """
        subjectNbs = set()
        for nbi in self.nbs:
            subjectNbs.add(nbi)
            if isinstance(nbi, nb.NaturalNuclideBase):
                for nuc in nbi.element.nuclides:
                    subjectNbs.add(nuc)
        subjectNbs = sorted(subjectNbs)
        return subjectNbs

    def _genENDFB8Label(self):
        """
        Generate the ENDF/B-VIII.0 label.

        Several ad-hoc assumptions are made in converting this object to a ENDF/B-VIII label which may not apply in all
        cases.

        It is believed that these rules cover most ENDF TSLs listed in
        Parsons, LA-UR-18-25096, https://mcnp.lanl.gov/pdf_files/la-ur-18-25096.pdf

        Unfortunately, the ace labels are not as easily derived.

        * If nuclideBases is length one and contains a ``NaturalNuclideBase``, then the name will be assumed to be
          ``Element_in_compoundName``
        * If nuclideBases is length one and is a NuclideBase, it is assumed to be an isotope like Fe-56 and  the label
          will be (for example) 026_Fe_056
        * If nuclideBases has length greater than one, the compoundName will form the entire of the label. So, if Si and
          O are in the bases, the compoundName must be ``SiO2-alpha`` in order to get ``tsl-SiO2-alpha.endf`` as a endf8
          label.
        """
        first = next(iter(self.nbs))
        if len(self.nbs) > 1:
            # just compound (like SiO2)
            label = f"tsl-{self.compoundName}.endf"
        elif isinstance(first, nb.NaturalNuclideBase):
            # element in compound
            label = f"tsl-{first.element.symbol}in{self.compoundName}.endf"
        elif isinstance(first, nb.NuclideBase):
            # just isotope
            element = elements.byZ[first.z]
            label = f"tsl-{first.z:03d}_{element.symbol.capitalize()}_{first.a:03d}.endf"
        else:
            raise ValueError(f"{self} label cannot be generated")
        return label

    def _genACELabel(self):
        """
        Attempt to derive the ACE label of a TSL.

        There are certain exceptions that cannot be derived and must be provided by the user upon instantiation, for
        example:

        * ``grph10``
        * ``grph30``
        * ``grph``

        """
        first = next(iter(self.nbs))
        if len(self.nbs) > 1:
            # just compound (like SiO2)
            label = f"{self.compoundName[:4].lower()}"
        elif isinstance(first, nb.NaturalNuclideBase):
            # element in compound
            label = f"{first.element.symbol.lower()}-{self.compoundName.lower()}"
        elif isinstance(first, nb.NuclideBase):
            # just isotope
            element = elements.byZ[first.z]
            label = f"{element.symbol.lower()}-{first.a:d}"
        else:
            raise ValueError(f"{self} label cannot be generated")

        return label


def factory(byName):
    """
    Generate the :class:`ThermalScattering` instances.

    The logic for these is a bit complex so we skip reading a text file and code it up here.

    This is called by the nuclideBases factory since it must ALWAYS be re-run when the nuclideBases are rebuilt.

    See Also
    --------
    armi.nucDirectory.nuclideBases.factory
        Calls this during ARMI initialization.
    """
    print("xxxxxxxxxxxxxxxxxxxxxxxxxx Thermal Scattering factory xxxxxxxxxxxxxxxxxxxxxxxxxx")
    global byNbAndCompound
    byNbAndCompound.clear()

    if "AL27" in byName:
        al27 = byName["AL27"]
        byNbAndCompound[al27, None] = ThermalScattering(al27)

    if "BE" in byName:
        be = byName["BE"]
        byNbAndCompound[be, BE_METAL] = ThermalScattering(
            be, BE_METAL, endf8Label=f"tsl-{BE_METAL}.endf", aceLabel="be-met"
        )
        byNbAndCompound[be, BEO] = ThermalScattering(be, BEO, endf8Label=BEO, aceLabel="be-beo")

    if "C" in byName:
        c = byName["C"]
        byNbAndCompound[c, SIC] = ThermalScattering(c, SIC)
        byNbAndCompound[c, GRAPHITE_10P] = ThermalScattering(c, GRAPHITE_10P, f"tsl-{GRAPHITE_10P}.endf", "grph10")
        byNbAndCompound[c, GRAPHITE_30P] = ThermalScattering(c, GRAPHITE_30P, f"tsl-{GRAPHITE_30P}.endf", "grph30")
        byNbAndCompound[c, CRYSTALLINE_GRAPHITE] = ThermalScattering(
            c, CRYSTALLINE_GRAPHITE, f"tsl-{CRYSTALLINE_GRAPHITE}.endf", "grph"
        )

    if "FE56" in byName:
        fe56 = byName["FE56"]
        byNbAndCompound[fe56, None] = ThermalScattering(fe56)

    if "H2" in byName:
        h = byName["H"]

    if "H2" in byName:
        d = byName["H2"]
        byNbAndCompound[d, D2O] = ThermalScattering(d, D2O, f"tsl-Din{D2O}.endf", "d-d2o")
        byNbAndCompound[h, H2O] = ThermalScattering(h, H2O)
        byNbAndCompound[h, ZRH] = ThermalScattering(h, ZRH)

    if "N" in byName:
        n = byName["N"]
        byNbAndCompound[n, UN] = ThermalScattering(n, UN)

    if "O" in byName:
        o = byName["O"]
        byNbAndCompound[o, BEO] = ThermalScattering(o, BEO)
        byNbAndCompound[o, D2O] = ThermalScattering(o, D2O, f"tsl-Oin{D2O}.endf", "o-d2o")
        byNbAndCompound[o, UO2] = ThermalScattering(o, UO2)

    if "SI" in byName:
        si = byName["SI"]
        byNbAndCompound[si, SIC] = ThermalScattering(si, SIC)

    if "U" in byName:
        u = byName["U"]
        byNbAndCompound[u, UO2] = ThermalScattering(u, UO2)
        byNbAndCompound[u, UN] = ThermalScattering(u, UN)

    if "ZR" in byName:
        zr = byName["ZR"]
        byNbAndCompound[zr, ZRH] = ThermalScattering(zr, ZRH)
