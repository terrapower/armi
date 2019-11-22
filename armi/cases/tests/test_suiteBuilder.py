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
Unit tests for the SuiteBuilder
"""
import os
import unittest
import math
import six
import io

from armi.utils import directoryChangers
from armi import settings
from armi import cases
from armi.cases import suiteBuilder
from armi.reactor import blueprints
from armi.reactor import geometry
from armi.physics import neutronics


class MockGeom(object):
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


class TestBlueprintModifiers(unittest.TestCase):
    def setUp(self):
        self.bp = blueprints.Blueprints.load(BLUEPRINT_INPUT)
        self.bp._prepConstruction(settings.Settings())

    def tearDown(self):
        del self.bp

    def test_AdjustSmearDensity(self):
        r"""
        Compute the smear density where clad.id is 1.0.

        .. math::

            areaFuel = smearDensity * innerCladArea
            fuelOD^2 / 4 = 0.5 * cladID^2 / 4  
            fuelOD = \sqrt{0.5}
            

        .. note:: the area of fuel is 0.5 * inner area of clad

        """
        bp = self.bp
        self.assertEqual(1.0, bp.blockDesigns["fuel 1"]["clad"].id)
        self.assertEqual(0.5, bp.blockDesigns["fuel 1"]["fuel"].od)
        self.assertEqual(0.5, bp.blockDesigns["fuel 2"]["fuel"].od)
        self.assertEqual(0.5, bp.blockDesigns["block 3"]["fuel"].od)
        self.assertEqual(0.5, bp.blockDesigns["block 4"]["fuel"].od)
        self.assertEqual(0.5, bp.blockDesigns["block 5"]["fuel"].od)

        suiteBuilder.SmearDensityModifier(0.5)(settings.Settings(), bp, MockGeom)

        self.assertEqual(math.sqrt(0.5), bp.blockDesigns["fuel 1"]["fuel"].od)
        self.assertEqual(math.sqrt(0.5), bp.blockDesigns["fuel 2"]["fuel"].od)
        self.assertEqual(math.sqrt(0.5), bp.blockDesigns["block 3"]["fuel"].od)
        self.assertEqual(math.sqrt(0.5), bp.blockDesigns["block 4"]["fuel"].od)
        self.assertEqual(0.5, bp.blockDesigns["block 5"]["fuel"].od)  # unique instance

    def test_CladThickenessByODModifier(self):
        """
        Adjust the clad thickness by outer diameter.

        .. math::

            cladThickness = (clad.od - clad.id) / 2
            clad.od = 2 * cladThicness - clad.id

        when ``clad.id = 1.0`` and ``cladThickness = 0.12``,

        .. math::

            clad.od = 2 * 0.12 - 1.0
            clad.od = 1.24
        """
        bp = self.bp
        self.assertEqual(1.1, bp.blockDesigns["fuel 1"]["clad"].od)
        self.assertEqual(1.1, bp.blockDesigns["fuel 2"]["clad"].od)
        self.assertEqual(1.1, bp.blockDesigns["block 3"]["clad"].od)
        self.assertEqual(1.1, bp.blockDesigns["block 4"]["clad"].od)
        self.assertEqual(1.1, bp.blockDesigns["block 5"]["clad"].od)

        suiteBuilder.CladThicknessByODModifier(0.12)(settings.Settings(), bp, MockGeom)

        self.assertEqual(1.24, bp.blockDesigns["fuel 1"]["clad"].od)
        self.assertEqual(1.24, bp.blockDesigns["fuel 2"]["clad"].od)
        self.assertEqual(1.24, bp.blockDesigns["block 3"]["clad"].od)
        self.assertEqual(1.24, bp.blockDesigns["block 4"]["clad"].od)
        self.assertEqual(
            1.24, bp.blockDesigns["block 5"]["clad"].od
        )  # modifies all blocks

    def test_CladThickenessByIDModifier(self):
        """
        Adjust the clad thickness by inner diameter.

        .. math::

            cladThickness = (clad.od - clad.id) / 2
            clad.id = cladod - 2 * cladThicness

        when ``clad.id = 1.1`` and ``cladThickness = 0.025``,

        .. math::

            clad.od = 1.1 - 2 * 0.025
            clad.od = 1.05
        """
        bp = self.bp
        self.assertEqual(1.0, bp.blockDesigns["fuel 1"]["clad"].id)
        self.assertEqual(1.0, bp.blockDesigns["fuel 2"]["clad"].id)
        self.assertEqual(1.0, bp.blockDesigns["block 3"]["clad"].id)
        self.assertEqual(1.0, bp.blockDesigns["block 4"]["clad"].id)
        self.assertEqual(1.0, bp.blockDesigns["block 5"]["clad"].id)

        suiteBuilder.CladThicknessByIDModifier(0.025)(settings.Settings(), bp, MockGeom)

        self.assertEqual(1.05, bp.blockDesigns["fuel 1"]["clad"].id)
        self.assertEqual(1.05, bp.blockDesigns["fuel 2"]["clad"].id)
        self.assertEqual(1.05, bp.blockDesigns["block 3"]["clad"].id)
        self.assertEqual(1.05, bp.blockDesigns["block 4"]["clad"].id)
        self.assertEqual(
            1.05, bp.blockDesigns["block 5"]["clad"].id
        )  # modifies all blocks


class TestSettingsModifiers(unittest.TestCase):
    def test_NeutronicConvergenceModifier(self):
        cs = settings.Settings()

        with self.assertRaises(ValueError):
            suiteBuilder.NeutronicConvergenceModifier(0.0)

        with self.assertRaises(ValueError):
            suiteBuilder.NeutronicConvergenceModifier(1e-2 + 1e-15)

        suiteBuilder.NeutronicConvergenceModifier(1e-2)(cs, None, None)
        self.assertAlmostEqual(cs["epsEig"], 1e-2)
        self.assertAlmostEqual(cs["epsFSAvg"], 1.0)
        self.assertAlmostEqual(cs["epsFSPoint"], 1.0)

        # since there is a specific test to adjust these, we should maybe not allow a generic
        # settings modifier to work...
        with six.assertRaisesRegex(
            self, ValueError, "use .*NeutronicConvergenceModifier"
        ):
            suiteBuilder.SettingsModifier("epsEig", 1e-5)

        with six.assertRaisesRegex(
            self, ValueError, "use .*NeutronicConvergenceModifier"
        ):
            suiteBuilder.SettingsModifier("epsFSAvg", 1e-5)

        with six.assertRaisesRegex(
            self, ValueError, "use .*NeutronicConvergenceModifier"
        ):
            suiteBuilder.SettingsModifier("epsFSPoint", 1e-5)


class NeutronicsKernelOpts(suiteBuilder.InputModifier):
    def __init__(self, neutronicsKernelOpts):
        suiteBuilder.InputModifier.__init__(self)
        self.neutronicsKernelOpts = neutronicsKernelOpts

    def __call__(self, cs, bp, geom):
        cs.update(self.neutronicsKernelOpts)


class TestsuiteBuilderIntegrations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        geom = geometry.SystemLayoutInput()
        geom.readGeomFromStream(GEOM_INPUT)
        bp = blueprints.Blueprints.load(BLUEPRINT_INPUT_LINKS)
        cs = settings.Settings()
        bp._prepConstruction(cs)
        cls.baseCase = cases.Case(cs=cs, bp=bp, geom=geom)

    def test_SmearDensityFail(self):
        builder = suiteBuilder.FullFactorialSuiteBuilder(self.baseCase)
        builder.addDegreeOfFreedom(
            suiteBuilder.SmearDensityModifier(v) for v in (0.5, 0.6)
        )
        builder.addDegreeOfFreedom(
            suiteBuilder.CladThicknessByIDModifier(v) for v in (0.05, 0.01)
        )
        self.assertEqual(4, len(builder))

        with six.assertRaisesRegex(self, RuntimeError, "before .*SmearDensityModifier"):
            builder.buildSuite()

    def test_example(self):
        builder = suiteBuilder.SeparateEffectsSuiteBuilder(self.baseCase)
        builder.addDegreeOfFreedom(
            suiteBuilder.SettingsModifier("fpModel", v)
            for v in ("noFissionProducts", "infinitelyDilute", "MO99")
        )
        builder.addDegreeOfFreedom(
            suiteBuilder.SettingsModifier("detailedAxialExpansion", v) for v in (True,)
        )
        builder.addDegreeOfFreedom(
            suiteBuilder.SettingsModifier("buGroups", v)
            for v in (
                [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 100],
                [3, 5, 7, 9, 10, 20, 100],
                [3, 5, 10, 15, 20, 100],
            )
        )
        builder.addDegreeOfFreedom((suiteBuilder.FullCoreModifier(),))

        neutronicKernelOpts = (
            {"neutronicsKernel": neutronics.DIF3DFD, "numberMeshPerEdge": 1},
            {"neutronicsKernel": neutronics.DIF3DFD, "numberMeshPerEdge": 2},
            {"neutronicsKernel": neutronics.DIF3DFD, "numberMeshPerEdge": 3},
            {"neutronicsKernel": neutronics.VARIANT, "epsEig": 1e-7, "epsFSAvg": 1e-5},
            {"neutronicsKernel": neutronics.VARIANT, "epsEig": 1e-9, "epsFSAvg": 1e-6},
            {"neutronicsKernel": neutronics.VARIANT, "epsEig": 1e-12, "epsFSAvg": 1e-7},
            {"neutronicsKernel": neutronics.VARIANT, "epsEig": 1e-13, "epsFSAvg": 1e-8},
        )
        builder.addDegreeOfFreedom(
            NeutronicsKernelOpts(opts) for opts in neutronicKernelOpts
        )

        with directoryChangers.TemporaryDirectoryChanger():
            suite = builder.buildSuite()
            for c in suite:
                c.writeInputs()

            self.assertTrue(os.path.exists("case-suite"))


if __name__ == "__main__":
    unittest.main()
