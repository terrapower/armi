"""Unit tests for input modifiers"""
import unittest
import os
import io

from armi.utils import directoryChangers
from armi import cases
from armi.cases import suiteBuilder
from armi.reactor import blueprints
from armi.reactor import systemLayoutInput
from armi import settings
from armi.cases.inputModifiers import (
    neutronicsModifiers,
    inputModifiers,
    pinTypeInputModifiers,
)
from armi.reactor.tests import test_reactors


class MockGeom:
    geomType = "hex"


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

GEOM_INPUT = io.StringIO(
    """<?xml version="1.0" ?>
<reactor geom="hex" symmetry="third core periodic">
    <assembly name="A1" pos="1"  ring="1"/>
    <assembly name="A2" pos="2"  ring="2"/>
    <assembly name="A3" pos="1"  ring="2"/>
    <assembly name="A4" pos="3"  ring="3"/>
    <assembly name="A5" pos="2"  ring="3"/>
    <assembly name="A6" pos="12" ring="3"/>
    <assembly name="A7" pos="4"  ring="3"/>
    <assembly name="A8" pos="1"  ring="3"/>
</reactor>
"""
)


class TestsuiteBuilderIntegrations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        geom = systemLayoutInput.SystemLayoutInput()
        geom.readGeomFromStream(GEOM_INPUT)
        bp = blueprints.Blueprints.load(BLUEPRINT_INPUT_LINKS)
        cs = settings.Settings()
        bp._prepConstruction(cs)
        cls.baseCase = cases.Case(cs=cs, bp=bp, geom=geom)

    def test_SmearDensityFail(self):
        builder = suiteBuilder.FullFactorialSuiteBuilder(self.baseCase)
        builder.addDegreeOfFreedom(
            pinTypeInputModifiers.SmearDensityModifier(v) for v in (0.5, 0.6)
        )
        builder.addDegreeOfFreedom(
            pinTypeInputModifiers.CladThicknessByIDModifier(v) for v in (0.05, 0.01)
        )
        self.assertEqual(4, len(builder))

        with self.assertRaisesRegex(RuntimeError, "before .*SmearDensityModifier"):
            builder.buildSuite()

    def test_example(self):
        builder = suiteBuilder.SeparateEffectsSuiteBuilder(self.baseCase)
        builder.addDegreeOfFreedom(
            inputModifiers.SettingsModifier("fpModel", v)
            for v in ("noFissionProducts", "infinitelyDilute", "MO99")
        )
        builder.addDegreeOfFreedom(
            inputModifiers.SettingsModifier("detailedAxialExpansion", v)
            for v in (True,)
        )
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


class TestSettingsModifiers(unittest.TestCase):
    def test_NeutronicConvergenceModifier(self):
        cs = settings.Settings()

        with self.assertRaises(ValueError):
            neutronicsModifiers.NeutronicConvergenceModifier(0.0)

        with self.assertRaises(ValueError):
            neutronicsModifiers.NeutronicConvergenceModifier(1e-2 + 1e-15)

        neutronicsModifiers.NeutronicConvergenceModifier(1e-2)(cs, None, None)
        self.assertAlmostEqual(cs["epsEig"], 1e-2)
        self.assertAlmostEqual(cs["epsFSAvg"], 1.0)
        self.assertAlmostEqual(cs["epsFSPoint"], 1.0)


class NeutronicsKernelOpts(inputModifiers.InputModifier):
    def __init__(self, neutronicsKernelOpts):
        inputModifiers.InputModifier.__init__(self)
        self.neutronicsKernelOpts = neutronicsKernelOpts

    def __call__(self, cs, bp, geom):
        cs.update(self.neutronicsKernelOpts)


class TestFullCoreModifier(unittest.TestCase):
    """Ensure full core conversion works"""

    def test_fullCoreConversion(self):
        cs = settings.Settings(os.path.join(test_reactors.TEST_ROOT, "armiRun.yaml"))
        case = cases.Case(cs=cs)
        mod = inputModifiers.FullCoreModifier()
        self.assertEqual(case.bp.gridDesigns["core"].symmetry, "third periodic")
        mod(case, case.bp, None)
        self.assertEqual(case.bp.gridDesigns["core"].symmetry, "full")


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
