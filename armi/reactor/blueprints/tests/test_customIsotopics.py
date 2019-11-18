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

import unittest

import yamlize

from armi.reactor import blueprints
from armi import settings
from armi.reactor.blueprints import isotopicOptions
from armi.reactor.flags import Flags
from armi.nucDirectory import nuclideBases


class TestCustomIsotopics(unittest.TestCase):

    yamlString = r"""
nuclide flags:
    U238: {burn: true, xs: true}
    U235: {burn: true, xs: true}
    U234: {burn: true, xs: true}
    ZR: {burn: false, xs: true}
    AL: {burn: false, xs: true}
    FE: {burn: false, xs: true}
    C: {burn: false, xs: true}
    DUMP2: {burn: true, xs: true}
    DUMP1: {burn: true, xs: true}
    LFP35: {burn: true, xs: true}
    PU239: {burn: true, xs: true}
    NP237: {burn: true, xs: true}
    LFP38: {burn: true, xs: true}
    LFP39: {burn: true, xs: true}
    PU240: {burn: true, xs: true}
    PU236: {burn: true, xs: true}
    PU238: {burn: true, xs: true}
    U236: {burn: true, xs: true}
    LFP40: {burn: true, xs: true}
    PU241: {burn: true, xs: true}
    AM241: {burn: true, xs: true}
    LFP41: {burn: true, xs: true}
    PU242: {burn: true, xs: true}
    AM243: {burn: true, xs: true}
    CM244: {burn: true, xs: true}
    CM242: {burn: true, xs: true}
    AM242: {burn: true, xs: true}
    CM245: {burn: true, xs: true}
    NP238: {burn: true, xs: true}
    CM243: {burn: true, xs: true}
    CM246: {burn: true, xs: true}
    CM247: {burn: true, xs: true}
    NI: {burn: true, xs: true}
    W: {burn: true, xs: true, expandTo: ["W182", "W183", "W184", "W186"]}
    MN: {burn: true, xs: true}
    CR: {burn: true, xs: true}
    V: {burn: true, xs: true}
    SI: {burn: true, xs: true}
    MO: {burn: true, xs: true}

custom isotopics:
    uranium isotopic mass fractions:
        input format: mass fractions
        U238: 0.992742
        U235: 0.007204
        U234: 0.000054
        density: 19.1

    # >>> from armi.nucDirectory import elements, nuclideBases
    # >>> import numpy
    # >>> u = elements.bySymbol['U']
    # >>> w_i = numpy.array([n.abundance for n in u.getNaturalIsotopics()])
    # >>> Mi = numpy.array([n.weight for n in u.getNaturalIsotopics()])
    # >>> Ni = w_i * 19.1 * 6.0221e23 / Mi
    # >>> N_norm = Ni / sum(Ni)
    # >>> N_norm.round(6)
    # array([  5.50000000e-05,   7.29500000e-03,   9.92650000e-01])
    uranium isotopic number fractions:
        input format: number fractions
        U238: 0.992650
        U235: 0.007295
        U234: 0.000055
        density: 19.1

    # >>> from armi.nucDirectory import elements, nuclideBases
    # >>> import numpy
    # >>> u = elements.bySymbol['U']
    # >>> Mi = numpy.array([n.weight for n in u.getNaturalIsotopics()])
    # >>> w_i = numpy.array([n.abundance for n in u.getNaturalIsotopics()])
    # >>> Ni = 19.1 * w_i * 6.0221e23 / Mi
    # array([  2.65398007e+18,   3.52549755e+20,   4.79692055e+22])
    # >>> for n, ni in zip(u.getNaturalIsotopics(), Ni):
    # >>>     print '        {}: {:.7e}'.format(n.name, ni) # requires 7 decimal places!
    uranium isotopic number densities: &u_isotopics
        input format: number densities
        U234: 2.6539102e-06
        U235: 3.5254048e-04
        U238: 4.7967943e-02

    linked uranium number densities: *u_isotopics

    steel:
        input format: mass fractions
        FE: 0.7
        C: 0.3
        density: 7.0

blocks:
    uzr fuel: &block_0
        fuel: &basic_fuel
            shape: Hexagon
            material: UZr
            Tinput: 25.0
            Thot: 600.0
            ip: 0.0
            mult: 1.0
            op: 10.0

        clad:
            shape: Circle
            material: HT9
            Tinput: 25.0
            Thot: 600.0
            id: 0.0
            mult: 1.0
            od: 10.0

    uranium fuel from isotopic mass fractions : &block_1
        fuel:
            <<: *basic_fuel
            material: Custom
            isotopics: uranium isotopic mass fractions

    wrong material: &block_2
        fuel:
            <<: *basic_fuel
            isotopics: uranium isotopic mass fractions

    uranium fuel from number fractions: &block_3
        fuel:
            <<: *basic_fuel
            material: Custom
            isotopics: uranium isotopic number fractions

    uranium fuel from number densities: &block_4
        fuel:
            <<: *basic_fuel
            material: Custom
            isotopics: uranium isotopic number densities

    uranium fuel from nd link: &block_5
        fuel:
            <<: *basic_fuel
            material: Custom
            isotopics: linked uranium number densities

    steel: &block_6
        clad:
            shape: Hexagon
            material: Custom
            isotopics: steel
            Tinput: 25.0
            Thot: 600.0
            ip: 0.0
            mult: 169.0
            op: 0.86602



assemblies:
    fuel a: &assembly_a
        specifier: IC
        blocks: [*block_0, *block_1, *block_2, *block_3, *block_4, *block_5, *block_6]
        height: [10, 10, 10, 10, 10, 10,10]
        axial mesh points: [1, 1, 1, 1, 1, 1,1]
        xs types: [A, A, A, A, A, A,A]
"""

    @classmethod
    def setUpClass(cls):
        cs = settings.Settings()
        # Need to init burnChain first.
        # see armi.cases.case.Case._initBurnChain
        with open(cs["burnChainFileName"]) as burnChainStream:
            nuclideBases.imposeBurnChain(burnChainStream)
        cs["xsKernel"] = "MC2v2"
        cls.bp = blueprints.Blueprints.load(cls.yamlString)
        cls.a = cls.bp.constructAssem("hex", cs, name="fuel a")
        cls.numUZrNuclides = 29  # Number of nuclides defined `nuclide flags`
        cls.numCustomNuclides = (
            28  # Number of nuclides defined in `nuclide flags` without Zr
        )

    def test_unmodified(self):
        """Ensure that unmodified components have the correct isotopics"""
        fuel = self.a[0].getComponent(Flags.FUEL)
        self.assertEqual(
            self.numUZrNuclides,
            len(fuel.p.numberDensities),
            msg=fuel.p.numberDensities.keys(),
        )
        # Note this density does not come from the material but is based on number densities
        self.assertAlmostEqual(15.5, fuel.density(), 0)  # i.e. it is not 19.1

    def test_massFractionsAreApplied(self):
        fuel0 = self.a[0].getComponent(Flags.FUEL)
        fuel1 = self.a[1].getComponent(Flags.FUEL)
        fuel2 = self.a[2].getComponent(Flags.FUEL)
        self.assertEqual(self.numCustomNuclides, len(fuel1.p.numberDensities))
        self.assertAlmostEqual(19.1, fuel1.density())

        # density only works with a Custom material type.
        self.assertAlmostEqual(fuel0.density(), fuel2.density())
        self.assertEqual(
            set(fuel2.p.numberDensities.keys()), set(fuel1.p.numberDensities.keys())
        )  # keys are same

    def test_numberFractions(self):
        # fuel 2 and 3 should be the same, one is defined as mass fractions, and the other as number fractions
        fuel2 = self.a[1].getComponent(Flags.FUEL)
        fuel3 = self.a[3].getComponent(Flags.FUEL)
        self.assertAlmostEqual(fuel2.density(), fuel3.density())

        for nuc in fuel2.p.numberDensities.keys():
            self.assertAlmostEqual(
                fuel2.p.numberDensities[nuc], fuel3.p.numberDensities[nuc]
            )

    def test_numberDensities(self):
        # fuel 2 and 3 should be the same, one is defined as mass fractions, and the other as number fractions
        fuel2 = self.a[1].getComponent(Flags.FUEL)
        fuel3 = self.a[4].getComponent(Flags.FUEL)
        self.assertAlmostEqual(fuel2.density(), fuel3.density())

        for nuc in fuel2.p.numberDensities.keys():
            self.assertAlmostEqual(
                fuel2.p.numberDensities[nuc], fuel3.p.numberDensities[nuc]
            )

    def test_numberDensitiesAnchor(self):
        fuel4 = self.a[4].getComponent(Flags.FUEL)
        fuel5 = self.a[5].getComponent(Flags.FUEL)
        self.assertAlmostEqual(fuel4.density(), fuel5.density())

        for nuc in fuel4.p.numberDensities.keys():
            self.assertAlmostEqual(
                fuel4.p.numberDensities[nuc], fuel5.p.numberDensities[nuc]
            )

    def test_expandedNatural(self):
        cs = settings.Settings()
        cs["xsKernel"] = "MC2v3"
        bp = blueprints.Blueprints.load(self.yamlString)
        a = bp.constructAssem("hex", cs, name="fuel a")
        b = a[-1]
        c = b.getComponent(Flags.CLAD)
        self.assertIn("FE56", c.getNumberDensities())  # natural isotopic
        self.assertNotIn("FE51", c.getNumberDensities())  # un-natural
        self.assertNotIn("FE", c.getNumberDensities())

    def test_unrepresentedAreOnlyNatural(self):
        """Make sure nuclides specified as In-Problem but not actually in any material are only natural isotopics."""
        self.assertIn("AL27", self.bp.allNuclidesInProblem)
        self.assertNotIn("AL26", self.bp.allNuclidesInProblem)


class TestCustomIsotopics_ErrorConditions(unittest.TestCase):
    def test_densityMustBePositive(self):
        with self.assertRaises(yamlize.YamlizingError):
            ci = isotopicOptions.CustomIsotopic.load(
                r"""
            name: atom repellent
            input format: mass fractions
            U234: 2.6539102e-06
            U235: 3.5254048e-04
            U238: 4.7967943e-02
            density: -0.0001
            """
            )

    def test_nonConformantElementName(self):
        with self.assertRaises(yamlize.YamlizingError):
            ci = isotopicOptions.CustomIsotopic.load(
                r"""
            name: non-upper case
            input format: number densities
            Au: 0.01
            """
            )

    def test_numberDensitiesCannotSpecifyDensity(self):
        with self.assertRaises(yamlize.YamlizingError):
            ci = isotopicOptions.CustomIsotopic.load(
                r"""
            name: over-specified isotopics
            input format: number densities
            AU: 0.01
            density: 10.0
            """
            )


class TestNuclideFlagsExpansion(unittest.TestCase):
    yamlString = r"""
nuclide flags:
    U238: {burn: false, xs: true}
    U235: {burn: false, xs: true}
    ZR: {burn: false, xs: true}
    AL: {burn: false, xs: true}
    FE: {burn: false, xs: true, expandTo: ["FE54"]}
    C: {burn: false, xs: true}
    NI: {burn: true, xs: true}
    MN: {burn: true, xs: true}
    CR: {burn: true, xs: true}
    V: {burn: true, xs: true}
    SI: {burn: true, xs: true}
    MO: {burn: true, xs: true}
    W: {burn: true, xs: true}
blocks:
    uzr fuel: &block_0
        fuel:
            shape: Hexagon
            material: UZr
            Tinput: 25.0
            Thot: 600.0
            mult: 1.0
            op: 10.0
        clad:
            shape: Circle
            material: HT9
            Tinput: 25.0
            Thot: 600.0
            id: 0.0
            mult: 1.0
            od: 10.0
assemblies:
    fuel a: 
        specifier: IC
        blocks: [*block_0]
        height: [10]
        axial mesh points: [1]
        xs types: [A]
    """

    def test_expandedNatural(self):
        cs = settings.Settings()
        cs["xsKernel"] = "MC2v3"
        bp = blueprints.Blueprints.load(self.yamlString)
        a = bp.constructAssem("hex", cs, name="fuel a")
        b = a[-1]
        c = b.getComponent(Flags.CLAD)
        nd = c.getNumberDensities()
        self.assertIn("FE54", nd)  # natural isotopic as requested
        self.assertNotIn("FE56", nd)  # natural isotopic not requested
        self.assertNotIn("FE51", nd)  # un-natural
        self.assertNotIn("FE", nd)


if __name__ == "__main__":
    unittest.main()
