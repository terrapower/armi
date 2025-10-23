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
"""Unit tests for input modifiers."""

import os
import unittest

from ruamel import yaml

from armi import cases, settings
from armi.cases import suiteBuilder
from armi.cases.inputModifiers import (
    inputModifiers,
    neutronicsModifiers,
    pinTypeInputModifiers,
)
from armi.physics.neutronics.fissionProductModel.fissionProductModelSettings import (
    CONF_FP_MODEL,
)
from armi.physics.neutronics.settings import (
    CONF_EPS_EIG,
    CONF_EPS_FSAVG,
    CONF_EPS_FSPOINT,
)
from armi.reactor import blueprints
from armi.reactor.tests import test_reactors
from armi.utils import directoryChangers

FLAGS_INPUT = """nuclide flags:
    U: {burn: false, xs: true}
    ZR: {burn: false, xs: true}
    MN: {burn: false, xs: true}
    FE: {burn: false, xs: true}
    SI: {burn: false, xs: true}
    C: {burn: false, xs: true}
    CR: {burn: false, xs: true}
    MO: {burn: false, xs: true}
    NI: {burn: false, xs: true}
    V: {burn: false, xs: true}
    W: {burn: false, xs: true}"""
CLAD = """clad: &fuel_1_clad
            Tinput: 350.0
            Thot: 350.0
            shape: circle
            id: 1.0
            od: 1.1
            material: HT9"""
CLAD_LINKED = """clad: &fuel_1_clad
            Tinput: 350.0
            Thot: 350.0
            shape: circle
            id: fuel.od
            od: 1.1
            material: HT9"""
BLOCKS_INPUT = """blocks:
    fuel 1: &fuel_1
        fuel: &fuel_1_fuel
            Tinput: 350.0
            Thot: 350.0
            shape: circle
            id: 0.0
            od: 0.5
            material: UZr
        {clad}
        hex: &fuel_1_hex
            Tinput: 350.0
            Thot: 350.0
            shape: hexagon
            ip: 1.0
            op: 10.0
            material: HT9
    fuel 2: *fuel_1
    block 3: *fuel_1                                        # non-fuel blocks
    block 4: {{<<: *fuel_1}}                                  # non-fuel blocks
    block 5: {{fuel: *fuel_1_fuel, clad: *fuel_1_clad, hex: *fuel_1_hex}}       # non-fuel blocks"""
BLOCKS_INPUT_1 = BLOCKS_INPUT.format(clad=CLAD)
BLOCKS_INPUT_2 = BLOCKS_INPUT.format(clad=CLAD_LINKED)
BLUEPRINT_INPUT = f"""
{FLAGS_INPUT}
{BLOCKS_INPUT_1}
assemblies: {{}}
"""
BLUEPRINT_INPUT_LINKS = f"""
{FLAGS_INPUT}
{BLOCKS_INPUT_2}
assemblies: {{}}
"""

CORE_INPUT = """
systems:
    core:
        grid name: core
        origin:
            x: 0.0
            y: 0.0
            z: 0.0
grids:
    core:
        geom: hex
        symmetry: third core periodic
        grid contents:
            [0, 0]: A1
            [1, 0]: A2
            [1, 1]: A3
            [2, -2]: A4
            [2, -1]: A5
            [2, 0]: A6
            [2, 1]: A7
            [2, 2]: A8
"""


class TestsuiteBuilderIntegrations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bp = blueprints.Blueprints.load(BLUEPRINT_INPUT_LINKS + CORE_INPUT)
        cs = settings.Settings()
        bp._prepConstruction(cs)
        cls.baseCase = cases.Case(cs=cs, bp=bp)

    def test_smearDensityFail(self):
        builder = suiteBuilder.FullFactorialSuiteBuilder(self.baseCase)

        builder.addDegreeOfFreedom(pinTypeInputModifiers.SmearDensityModifier(v) for v in (0.5, 0.6))
        builder.addDegreeOfFreedom(pinTypeInputModifiers.CladThicknessByIDModifier(v) for v in (0.05, 0.01))
        self.assertEqual(4, len(builder))

        with self.assertRaisesRegex(RuntimeError, "before .*SmearDensityModifier"):
            builder.buildSuite()

    def test_settingsModifier(self):
        builder = suiteBuilder.SeparateEffectsSuiteBuilder(self.baseCase)
        builder.addDegreeOfFreedom(
            inputModifiers.SettingsModifier(CONF_FP_MODEL, v) for v in ("noFissionProducts", "infinitelyDilute", "MO99")
        )
        builder.addDegreeOfFreedom(inputModifiers.SettingsModifier("detailedAxialExpansion", v) for v in (True,))
        builder.addDegreeOfFreedom(
            inputModifiers.SettingsModifier("buGroups", v)
            for v in (
                [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 100],
                [3, 5, 7, 9, 10, 20, 100],
                [3, 5, 10, 15, 20, 100],
            )
        )
        builder.addDegreeOfFreedom((inputModifiers.FullCoreModifier(),))

        with directoryChangers.TemporaryDirectoryChanger():
            suite = builder.buildSuite()
            for c in suite:
                c.writeInputs()

            self.assertTrue(os.path.exists("case-suite"))

    def test_bluePrintBlockModifier(self):
        """Test BluePrintBlockModifier with build suite naming function argument."""
        case_nbr = 1
        builder = suiteBuilder.FullFactorialSuiteBuilder(self.baseCase)

        builder.addDegreeOfFreedom(
            [inputModifiers.BluePrintBlockModifier("fuel 1", "clad", "od", float("{:.2f}".format(22 / 7)))]
        )
        builder.addDegreeOfFreedom([inputModifiers.BluePrintBlockModifier("block 5", "clad", "od", 3.14159)])

        def SuiteNaming(index, _case, _mods):
            uniquePart = "{:0>4}".format(index + case_nbr)
            return os.path.join(
                ".",
                "case-suite-testBPBM",
                uniquePart,
                self.baseCase.title + "-" + uniquePart,
            )

        with directoryChangers.TemporaryDirectoryChanger():
            suite = builder.buildSuite(namingFunc=SuiteNaming)
            suite.writeInputs()

            self.assertTrue(os.path.exists("case-suite-testBPBM"))

            yamlfile = open(
                f"case-suite-testBPBM/000{case_nbr}/armi-000{case_nbr}-blueprints.yaml",
                "r",
            )
            bp_dict = yaml.YAML().load(yamlfile)
            yamlfile.close()

            self.assertEqual(bp_dict["blocks"]["fuel 1"]["clad"]["od"], 3.14)
            self.assertEqual(bp_dict["blocks"]["block 5"]["clad"]["od"], 3.14159)


class TestSettingsModifiers(unittest.TestCase):
    def test_NeutronicConvergenceModifier(self):
        cs = settings.Settings()

        with self.assertRaises(ValueError):
            _ = neutronicsModifiers.NeutronicConvergenceModifier(0.0)

        with self.assertRaises(ValueError):
            _ = neutronicsModifiers.NeutronicConvergenceModifier(1e-2 + 1e-15)

        cs, _ = neutronicsModifiers.NeutronicConvergenceModifier(1e-2)(cs, None)
        self.assertAlmostEqual(cs[CONF_EPS_EIG], 1e-2)
        self.assertAlmostEqual(cs[CONF_EPS_FSAVG], 1.0)
        self.assertAlmostEqual(cs[CONF_EPS_FSPOINT], 1.0)


class NeutronicsKernelOpts(inputModifiers.InputModifier):
    def __init__(self, neutronicsKernelOpts):
        inputModifiers.InputModifier.__init__(self)
        self.neutronicsKernelOpts = neutronicsKernelOpts

    def __call__(self, cs, bp):
        cs = cs.modified(self.neutronicsKernelOpts)
        return cs, bp


class TestFullCoreModifier(unittest.TestCase):
    """Ensure full core conversion works."""

    def test_fullCoreConversion(self):
        cs = settings.Settings(os.path.join(test_reactors.TEST_ROOT, "armiRun.yaml"))
        case = cases.Case(cs=cs)
        mod = inputModifiers.FullCoreModifier()
        self.assertEqual(case.bp.gridDesigns["core"].symmetry, "third periodic")
        case, case.bp = mod(case, case.bp)
        self.assertEqual(case.bp.gridDesigns["core"].symmetry, "full")

    def test_fullCoreConversionWithOrientation(self):
        """Tests modifying a reactor to full core that includes beginning of life orientations."""
        cs = settings.Settings(os.path.join(test_reactors.TEST_ROOT, "armiRun.yaml"))
        case = cases.Case(cs=cs)
        mod = inputModifiers.FullCoreModifier()
        self.assertEqual(case.bp.gridDesigns["core"].symmetry, "third periodic")

        # Add beginning of life orientations
        case.bp.gridDesigns["core"].orientationBOL = {(2, 1): 30.0}

        # Modify to full core
        case, case.bp = mod(case, case.bp)

        # Check results
        self.assertEqual(case.bp.gridDesigns["core"].symmetry, "full")
        self.assertIn((2, 3), case.bp.gridDesigns["core"].orientationBOL)
        self.assertEqual(150.0, case.bp.gridDesigns["core"].orientationBOL[(2, 3)])
        self.assertIn((2, 5), case.bp.gridDesigns["core"].orientationBOL)
        self.assertEqual(270.0, case.bp.gridDesigns["core"].orientationBOL[(2, 5)])
