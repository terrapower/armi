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
Handle awareness of Thermal Scattering labels for ENDF/B-VIII and ACE.

The information below is based on Parsons, LA-UR-18-25096, https://mcnp.lanl.gov/pdf_files/la-ur-18-25096.pdf

Scattering law labels are currently available for a variety of classifications:

* Element in Compound (H in H2O, Be in BeO)
* Element in structure (C in Graphite, Be in metal)

    * Can be separated as crystalline, 30% porous, 10% porous, etc.

* Element in spin isomer (para H, ortho H, para D, ortho D, etc.)
* Compound in phase (solid CH4, liquid CH4, SiO2-alpha, SiO2-beta).
* Just compound (benzene)
* Just isotope (Fe56, Al27)

The labels for these vary across evaluations (e.g. ENDF/B-VII, ENDF/B-VIII, etc.). We provide ENDF/B-III.0 and ACE
labels. Other physics kernels will have to derive their own labels as appropriate in client code.
"""

from dataclasses import dataclass

# strings that users might want to reference downstream
BE_METAL = "Be-metal"
BEO = "BeO"
CRYSTALLINE_GRAPHITE = "crystalline-graphite"
D2O = "D2O"
GRAPHITE_10P = "reactor-graphite-10P"
GRAPHITE_30P = "reactor-graphite-30P"
H2O = "H2O"
SIC = "SiC"
UN = "UN"
UO2 = "UO2"
ZRH = "ZrH"

# thermal scattering label data
BY_NAME_AND_COMPOUND = {
    ("AL27", None): ("tsl-013_Al_027.endf", "al-27"),
    ("BE", BE_METAL): (f"tsl-{BE_METAL}.endf", "be-met"),
    ("BE", BEO): (BEO, "be-beo"),
    ("C", CRYSTALLINE_GRAPHITE): (f"tsl-{CRYSTALLINE_GRAPHITE}.endf", "grph"),
    ("C", GRAPHITE_10P): (f"tsl-{GRAPHITE_10P}.endf", "grph10"),
    ("C", GRAPHITE_30P): (f"tsl-{GRAPHITE_30P}.endf", "grph30"),
    ("C", SIC): ("tsl-CinSiC.endf", "c-sic"),
    ("FE56", None): ("tsl-026_Fe_056.endf", "fe-56"),
    ("H", H2O): ("tsl-HinH2O.endf", "h-h2o"),
    ("H", ZRH): ("tsl-HinZrH.endf", "h-zrh"),
    ("H2", D2O): (f"tsl-Din{D2O}.endf", "d-d2o"),
    ("N", UN): ("tsl-NinUN.endf", "n-un"),
    ("O", BEO): ("tsl-OinBeO.endf", "o-beo"),
    ("O", D2O): (f"tsl-Oin{D2O}.endf", "o-d2o"),
    ("O", UO2): ("tsl-OinUO2.endf", "o-uo2"),
    ("SI", SIC): ("tsl-SIinSiC.endf", "si-sic"),
    ("U", UN): ("tsl-UinUN.endf", "u-un"),
    ("U", UO2): ("tsl-UinUO2.endf", "u-uo2"),
    ("ZR", ZRH): ("tsl-ZRinZrH.endf", "zr-zrh"),
}


@dataclass
class ThermalScatteringLabels:
    """Container for the labels for a particular nuclide/compound combination.

    Attributes
    ----------
    name: str
        Name of the nuclide. This should match the string in the "byName" field in nuclideBases.
    compound: str
        Label indicating what the subjects are in (e.g. ``"Graphite"`` or ``"H2O"``. Can be left off for, e.g. Fe56.
    endf8Label: str
        Label for ENDF/B-VIII evaluation.
    aceLabel: str
        Lavel for ACE.
    """

    name: str
    compound: str
    endf8Label: str
    aceLabel: str


def fromNameAndCompound(name: str, compound: str):
    """The standard interface for getting ENDF/B-VIII and ACE labels for a given nuclide.

    Parameters
    ----------
    name: str
        Name of the nuclide.
    compound: str
        Name of the compound (can be None).

    Returns
    -------
    ThermalScatteringLabels
        An instance of the data class used to contain the ENDF/ACE labels for this nuclide/componound combination.

    Raises
    ------
    ValueError
        ARMI does not store a large data set of labels. If the user requests one ARMI does not have, they get an error.
    """
    if (name, compound) in BY_NAME_AND_COMPOUND:
        endf, ace = BY_NAME_AND_COMPOUND[(name, compound)]
        return ThermalScatteringLabels(name, compound, endf, ace)
    else:
        raise ValueError(f"No thermal scattering labels are known for name/compound: {name}/{compound}")
