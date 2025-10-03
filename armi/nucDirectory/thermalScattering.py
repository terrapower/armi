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

Here we provide objects representing the thermal scattering law (TSL) information. But we do not provide special
versions of various NuclideBases like C12 because of potential errors in choosing one over the other

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
from dataclasses import dataclass

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


@dataclass(slots=True)
class ThermalScatteringLabels:
    """TODO: JOHN."""
    name: str
    compound: str
    endf8Label: str
    aceLabel: str


byNameAndCompound = {
    ("AL27", None): ("tsl-013_Al_027.endf", "al-27"),
    ("BE", BE_METAL): (f"tsl-{BE_METAL}.endf", "be-met"),
    ("BE", BEO): (BEO, "be-beo"),
    ("C", SIC): ("tsl-CinSiC.endf", "c-sic"),
    ("C", GRAPHITE_10P): (f"tsl-{GRAPHITE_10P}.endf", "grph10"),
    ("C", GRAPHITE_30P): (f"tsl-{GRAPHITE_30P}.endf", "grph30"),
    ("C", CRYSTALLINE_GRAPHITE): (f"tsl-{CRYSTALLINE_GRAPHITE}.endf", "grph"),
    ("FE56", None): ("tsl-026_Fe_056.endf", "fe-56"),
    ("H2", D2O): (f"tsl-Din{D2O}.endf", "d-d2o"),
    ("H", H2O): ("tsl-HinH2O.endf", "h-h2o"),
    ("H", ZRH): ("tsl-HinZrH.endf", "h-zrh"),
    ("N", UN): ("tsl-NinUN.endf", "n-un"),
    ("O", BEO): ("tsl-OinBeO.endf", "o-beo"),
    ("O", D2O): (f"tsl-Oin{D2O}.endf", "o-d2o"),
    ("O", UO2): ("tsl-OinUO2.endf", "o-uo2"),
    ("SI", SIC): ("tsl-SIinSiC.endf", "si-sic"),
    ("U", UO2): ("tsl-UinUO2.endf", "u-uo2"),
    ("U", UN): ("tsl-UinUN.endf", "u-un"),
    ("ZR", ZRH): ("tsl-ZRinZrH.endf", "zr-zrh"),

}


def fromNameAndCompound(name: str, compound: str):
    """TODO: JOHN."""
    if (name, compound) in byNameAndCompound:
        endf, ace = byNameAndCompound[(name, compound)]
        return ThermalScatteringLabels(name, compound, endf, ace)
    else:
        raise ValueError(f"No thermal scattering labels are known for name/compound: {name}/{compound}")
