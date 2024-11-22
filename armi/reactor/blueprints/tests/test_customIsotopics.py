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

"""Unit test custom isotopics."""
import unittest
from logging import DEBUG

import yamlize

from armi import settings
from armi.physics.neutronics.settings import CONF_XS_KERNEL
from armi.reactor import blueprints
from armi.reactor.blueprints import isotopicOptions
from armi.reactor.flags import Flags
from armi import runLog
from armi.tests import mockRunLogs


class TestCustomIsotopics(unittest.TestCase):
    yamlPreamble = r"""
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

    uranium isotopic number fractions:
        input format: number fractions
        U238: 0.992650
        U235: 0.007295
        U234: 0.000055
        density: 19.1

    uranium isotopic number densities: &u_isotopics
        input format: number densities
        U234: 2.6539102e-06
        U235: 3.5254048e-04
        U238: 4.7967943e-02

    bad uranium isotopic mass fractions:
        input format: mass fractions
        U238: 0.992742
        U235: 0.007204
        U234: 0.000054
        density: 0

    negative uranium isotopic mass fractions:
        input format: mass fractions
        U238: 0.992742
        U235: 0.007204
        U234: 0.000054
        density: -1

    linked uranium number densities: *u_isotopics

    steel:
        input format: mass fractions
        FE: 0.7
        C: 0.3
        density: 7.0

"""

    yamlGoodBlocks = r"""
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

    fuel with no modifications: &block_6  # after a custom density has been set
        fuel:
            <<: *basic_fuel

    overspecified fuel: &block_7
        fuel:
            <<: *basic_fuel
            material: UraniumOxide
            isotopics: uranium isotopic number densities

    density set via number density: &block_8
        fuel:
            <<: *basic_fuel
            isotopics: uranium isotopic number densities

    steel: &block_9
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
        blocks: [*block_0, *block_1, *block_2, *block_3, *block_4, *block_5, *block_6, *block_7, *block_8, *block_9]
        height: [10, 10, 10, 10, 10, 10, 10, 10, 10, 10]
        axial mesh points: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        xs types: [A, A, A, A, A, A, A, A, A, A]
        material modifications:
            TD_frac: ["", "", "", "", "", "", "", 0.1, "", ""]

"""

    yamlBadBlocks = r"""
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

    custom void: &block_1
        fuel:
            <<: *basic_fuel
            material: Void
            isotopics: uranium isotopic number densities

    steel: &block_2
        clad:
            shape: Hexagon
            material: Custom
            isotopics: steel
            Tinput: 25.0
            Thot: 600.0
            ip: 0.0
            mult: 169.0
            op: 0.86602

    no density uo2: &block_3
        fuel:
            <<: *basic_fuel
            material: UraniumOxide
            isotopics: uranium isotopic number densities

    no density uo2: &block_4
        fuel:
            <<: *basic_fuel
            material: UraniumOxide
            isotopics: bad uranium isotopic mass fractions
    
    no density uo2: &block_5
        fuel:
            <<: *basic_fuel
            material: UraniumOxide
            isotopics: bad uranium isotopic mass fractions


assemblies:
    fuel a: &assembly_a
        specifier: IC
        blocks: [*block_0, *block_1, *block_2]
        height: [10, 10, 10]
        axial mesh points: [1, 1, 1]
        xs types: [A, A, A]
        material modifications:
            TD_frac: ["", "", ""]
    
    fuel b: &assembly_b
        specifier: IC
        blocks: [*block_0, *block_3, *block_2]
        height: [10, 10, 10]
        axial mesh points: [1, 1, 1]
        xs types: [A, A, A]
        material modifications:
            TD_frac: ["", "0.0", ""]  # set density to 0 to cause error in custom density

    fuel c: &assembly_c
        specifier: IC
        blocks: [*block_0, *block_4, *block_2]
        height: [10, 10, 10]
        axial mesh points: [1, 1, 1]
        xs types: [A, A, A]

    fuel d: &assembly_d
        specifier: IC
        blocks: [*block_0, *block_5, *block_2]
        height: [10, 10, 10]
        axial mesh points: [1, 1, 1]
        xs types: [A, A, A]

"""

    # this yaml is supposed to successfully build
    yamlString = yamlPreamble + yamlGoodBlocks

    # This yaml is designed to raise an error when built
    yamlStringWithError = yamlPreamble + yamlBadBlocks
    """:meta hide-value:"""

    @classmethod
    def setUpClass(cls):
        cs = settings.Settings()
        cs = cs.modified(newSettings={CONF_XS_KERNEL: "MC2v2"})

        cls.bp = blueprints.Blueprints.load(cls.yamlString)
        cls.a = cls.bp.constructAssem(cs, name="fuel a")
        cls.numUZrNuclides = 29  # Number of nuclides defined `nuclide flags`
        cls.numCustomNuclides = (
            28  # Number of nuclides defined in `nuclide flags` without Zr
        )

    def test_unmodified(self):
        """Ensure that unmodified components have the correct isotopics."""
        fuel = self.a[0].getComponent(Flags.FUEL)
        self.assertEqual(
            self.numUZrNuclides,
            len(fuel.p.numberDensities),
            msg=fuel.p.numberDensities.keys(),
        )
        # Note this density does not come from the material but is based on number densities
        self.assertAlmostEqual(15.5, fuel.density(), 0)  # i.e. it is not 19.1

    def test_massFractionsAreApplied(self):
        """Ensure that the custom isotopics can be specified via mass fractions.

        .. test:: Test that custom isotopics can be specified via mass fractions.
            :id: T_ARMI_MAT_USER_INPUT3
            :tests: R_ARMI_MAT_USER_INPUT
        """
        fuel1 = self.a[1].getComponent(Flags.FUEL)
        fuel2 = self.a[2].getComponent(Flags.FUEL)
        self.assertEqual(self.numCustomNuclides, len(fuel1.p.numberDensities))
        self.assertAlmostEqual(19.1, fuel1.density())

        self.assertEqual(
            set(fuel2.p.numberDensities.keys()), set(fuel1.p.numberDensities.keys())
        )  # keys are same

    def test_densitiesAppliedToNonCustomMaterials(self):
        """Ensure that a density can be set in custom isotopics for components using library materials."""
        # The template block
        fuel0 = self.a[0].getComponent(Flags.FUEL)
        # The block with custom density but not the 'Custom' material
        fuel2 = self.a[2].getComponent(Flags.FUEL)
        # A block like the template block, but made after the custom block
        fuel6 = self.a[6].getComponent(Flags.FUEL)
        # A block with custom density set via number density
        fuel8 = self.a[8].getComponent(Flags.FUEL)

        # Check that the density is set correctly on the custom density block,
        # and that it is not the same as the original
        self.assertAlmostEqual(19.1, fuel2.density())
        self.assertNotAlmostEqual(fuel0.density(), fuel2.density(), places=2)
        # Check that the custom density block has the correct material
        self.assertEqual("UZr", fuel2.material.name)
        # Check that the block with only number densities set has a new density
        self.assertAlmostEqual(19.1, fuel8.density())
        # original material density should not be changed after setting a custom density component,
        # so a new block without custom isotopics and density should have the same density as the original
        self.assertAlmostEqual(fuel6.density(), fuel0.density())
        self.assertEqual(fuel6.material.name, fuel0.material.name)
        self.assertEqual("UZr", fuel0.material.name)

    def test_customDensityLogsAndErrors(self):
        """Test that the right warning messages and errors are emitted when applying custom densities."""
        # Check for warnings when specifying both TD_frac and custom isotopics
        with mockRunLogs.BufferLog() as mockLog:
            # we should start with a clean slate
            self.assertEqual("", mockLog.getStdout())
            runLog.LOG.startLog("test_customDensityLogsAndErrors")
            runLog.LOG.setVerbosity(DEBUG)

            # rebuild the input to capture the logs
            cs = settings.Settings()
            cs = cs.modified(newSettings={CONF_XS_KERNEL: "MC2v2"})
            bp = blueprints.Blueprints.load(self.yamlString)
            bp.constructAssem(cs, name="fuel a")

            # Check for log messages
            streamVal = mockLog.getStdout()
            self.assertIn("Both TD_frac and a custom density", streamVal, msg=streamVal)
            self.assertIn(
                "A custom material density was specified", streamVal, msg=streamVal
            )
            self.assertIn(
                "A custom density or number densities has been specified",
                streamVal,
                msg=streamVal,
            )

        # Check that assigning a custom density to the Void material fails
        cs = settings.Settings()
        cs = cs.modified(newSettings={CONF_XS_KERNEL: "MC2v2"})
        bp = blueprints.Blueprints.load(self.yamlStringWithError)
        # Ensure we have some Void
        self.assertEqual(bp.blockDesigns["custom void"]["fuel"].material, "Void")
        # Can't have stuff in Void
        with self.assertRaises(ValueError):
            bp.constructAssem(cs, name="fuel a")

        # Try making a 0 density non-Void material by setting TD_frac to 0.0
        with self.assertRaises(ValueError):
            bp.constructAssem(cs, name="fuel b")

        # Try making a material with mass fractions with a density of 0
        with self.assertRaises(ValueError):
            bp.constructAssem(cs, name="fuel c")

        # Try making a material with mass fractions with a negative density
        with self.assertRaises(ValueError):
            bp.constructAssem(cs, name="fuel d")

    def test_numberFractions(self):
        """Ensure that the custom isotopics can be specified via number fractions.

        .. test:: Test that custom isotopics can be specified via number fractions.
            :id: T_ARMI_MAT_USER_INPUT4
            :tests: R_ARMI_MAT_USER_INPUT
        """
        # fuel blocks 2 and 4 should be the same, one is defined as mass fractions, and the other as number fractions
        fuel2 = self.a[1].getComponent(Flags.FUEL)
        fuel4 = self.a[3].getComponent(Flags.FUEL)
        self.assertAlmostEqual(fuel2.density(), fuel4.density())

        for nuc in fuel2.p.numberDensities.keys():
            self.assertAlmostEqual(
                fuel2.p.numberDensities[nuc], fuel4.p.numberDensities[nuc]
            )

    def test_numberDensities(self):
        """Ensure that the custom isotopics can be specified via number densities.

        .. test:: Test that custom isotopics can be specified via number fractions.
            :id: T_ARMI_MAT_USER_INPUT5
            :tests: R_ARMI_MAT_USER_INPUT
        """
        # fuel blocks 2 and 5 should be the same, one is defined as mass fractions, and the other as number densities
        fuel2 = self.a[1].getComponent(Flags.FUEL)
        fuel5 = self.a[4].getComponent(Flags.FUEL)
        self.assertAlmostEqual(fuel2.density(), fuel5.density())

        for nuc in fuel2.p.numberDensities.keys():
            self.assertAlmostEqual(
                fuel2.p.numberDensities[nuc], fuel5.p.numberDensities[nuc]
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
        cs = cs.modified(newSettings={CONF_XS_KERNEL: "MC2v3"})

        bp = blueprints.Blueprints.load(self.yamlString)
        a = bp.constructAssem(cs, name="fuel a")
        b = a[-1]
        c = b.getComponent(Flags.CLAD)
        self.assertIn("FE56", c.getNumberDensities())  # natural isotopic
        self.assertNotIn("FE51", c.getNumberDensities())  # un-natural
        self.assertNotIn("FE", c.getNumberDensities())

    def test_infDiluteAreOnlyNatural(self):
        """Make sure nuclides specified as In-Problem but not actually in any material are only natural isotopics."""
        self.assertIn("AL27", self.bp.allNuclidesInProblem)
        self.assertNotIn("AL26", self.bp.allNuclidesInProblem)


class TestCustomIsotopics_ErrorConditions(unittest.TestCase):
    def test_densityMustBePositive(self):
        with self.assertRaises(yamlize.YamlizingError):
            _ = isotopicOptions.CustomIsotopic.load(
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
            _ = isotopicOptions.CustomIsotopic.load(
                r"""
            name: non-upper case
            input format: number densities
            Au: 0.01
            """
            )

    def test_numberDensitiesCannotSpecifyDensity(self):
        with self.assertRaises(yamlize.YamlizingError):
            _ = isotopicOptions.CustomIsotopic.load(
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
        cs = cs.modified(newSettings={CONF_XS_KERNEL: "MC2v3"})

        bp = blueprints.Blueprints.load(self.yamlString)
        a = bp.constructAssem(cs, name="fuel a")
        b = a[-1]
        c = b.getComponent(Flags.CLAD)
        nd = c.getNumberDensities()
        self.assertIn("FE54", nd)  # natural isotopic as requested
        self.assertNotIn("FE56", nd)  # natural isotopic not requested
        self.assertNotIn("FE51", nd)  # un-natural
        self.assertNotIn("FE", nd)
