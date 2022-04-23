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
"""Tests for thermal scattering metadata"""
# pylint: disable=protected-access

import unittest

from armi.reactor import blocks
from armi.reactor import components

from .. import thermalScattering as ts
from .. import nuclideBases as nb


def buildBlockWithTSL():
    """Return a simple block containing something with a TSL (graphite)."""
    b = blocks.HexBlock("fuel", height=10.0)

    fuelDims = {"Tinput": 25.0, "Thot": 600, "od": 0.76, "id": 0.00, "mult": 127.0}
    cladDims = {"Tinput": 25.0, "Thot": 450, "od": 0.80, "id": 0.77, "mult": 127.0}
    coolDims = {"Tinput": 25.0, "Thot": 400}

    fuel = components.Circle("fuel", "UZr", **fuelDims)
    clad = components.Circle("clad", "Graphite", **cladDims)
    coolant = components.DerivedShape("coolant", "Sodium", **coolDims)

    b.add(fuel)
    b.add(clad)
    b.add(coolant)

    return b


class TestThermalScattering(unittest.TestCase):
    """Tests for thermal scattering on the reactor model"""

    def test_graphiteOnReactor(self):
        b = buildBlockWithTSL()
        tsl = getNuclideThermalScatteringData(b)
        carbon = nb.byName["C"]
        carbon12 = nb.byName["C12"]
        self.assertIn(carbon, tsl)
        self.assertNotIn(carbon12, tsl)

        b.expandElementalToIsotopics(carbon)

        tsl = getNuclideThermalScatteringData(b)
        self.assertNotIn(carbon, tsl)
        self.assertIn(carbon12, tsl)

        self.assertIs(tsl[carbon12], ts.byNbAndCompound[carbon, ts.GRAPHITE_10P])

    def test_endf8Compound(self):
        si = nb.byName["SI"]
        o = nb.byName["O"]
        sio2 = ts.ThermalScattering((si, o), "SiO2-alpha")
        self.assertEqual(sio2._genENDFB8Label(), "tsl-SiO2-alpha.endf")

    def test_endf8ElementInCompound(self):
        hyd = nb.byName["H"]
        hInH2O = ts.ThermalScattering(hyd, "H2O")
        self.assertEqual(hInH2O._genENDFB8Label(), "tsl-HinH2O.endf")

    def test_endf8Isotope(self):
        fe56 = nb.byName["FE56"]
        fe56tsl = ts.ThermalScattering(fe56)
        self.assertEqual(fe56tsl._genENDFB8Label(), "tsl-026_Fe_056.endf")

    def test_ACECompound(self):
        si = nb.byName["SI"]
        o = nb.byName["O"]
        sio2 = ts.ThermalScattering((si, o), "SiO2-alpha")
        self.assertEqual(sio2._genACELabel(), "sio2")

    def test_ACEElementInCompound(self):
        hyd = nb.byName["H"]
        hInH2O = ts.ThermalScattering(hyd, "H2O")
        self.assertEqual(hInH2O._genACELabel(), "h-h2o")

    def test_ACEIsotope(self):
        fe56 = nb.byName["FE56"]
        fe56tsl = ts.ThermalScattering(fe56)
        self.assertEqual(fe56tsl._genACELabel(), "fe-56")

    def test_failOnMultiple(self):
        """HT9 has carbon in it with no TSL, while graphite has C with TSL. This should crash"""
        b = buildBlockWithTSL()
        cladDims = {"Tinput": 25.0, "Thot": 450, "od": 0.80, "id": 0.79, "mult": 127.0}
        clad2 = components.Circle("clad", "HT9", **cladDims)
        b.add(clad2)
        with self.assertRaises(RuntimeError):
            getNuclideThermalScatteringData(b)


def getNuclideThermalScatteringData(armiObj):
    """
    Make a mapping between nuclideBases in an armiObj and relevant thermal scattering laws.

    In some cases, a nuclide will be present both with a TSL and without (e.g. hydrogen in water
    and hydrogen in concrete in the same armiObj). While this could conceptually be handled
    somehow, we simply error out at this time.

    Notes
    -----
    Clients can use code like this to access TSL data. This is not an official framework
    method because it's not general enough to cover all use cases in all reactors.

    Returns
    -------
    tslByNuclideBase : dict
        A dictionary with NuclideBase keys and ThermalScattering values

    Raises
    ------
    RuntimeError
        When a armiObj has nuclides subject to more than one TSL, or subject to a TLS
        in one case and no TSL in another.

    Examples
    --------
    >>> tslInfo = getNuclideThermalScatteringData(armiObj)
    >>> if nucBase in tslInfo:
    >>>     aceLabel = tslInfo[nucBase].aceLabel
    """
    tslByNuclideBase = {}
    freeNuclideBases = set()
    for c in armiObj.iterComponents():
        nucs = {nb.byName[nn] for nn in c.getNuclides()}
        freeNucsHere = set()
        freeNucsHere.update(nucs)
        for tsl in c.material.thermalScatteringLaws:
            for subjectNb in tsl.getSubjectNuclideBases():
                if subjectNb in nucs:
                    if (
                        subjectNb in tslByNuclideBase
                        and tslByNuclideBase[subjectNb] is not tsl
                    ):
                        raise RuntimeError(
                            f"{subjectNb} in {armiObj} is subject to more than 1 different TSL: "
                            f"{tsl} and {tslByNuclideBase[subjectNb]}"
                        )
                    tslByNuclideBase[subjectNb] = tsl
                    freeNucsHere.remove(subjectNb)
        freeNuclideBases.update(freeNucsHere)

    freeAndBound = freeNuclideBases.intersection(set(tslByNuclideBase.keys()))
    if freeAndBound:
        raise RuntimeError(
            f"{freeAndBound} is/are present in both bound and free forms in {armiObj}"
        )

    return tslByNuclideBase


if __name__ == "__main__":
    unittest.main()
