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
Module for testing componentBlueprint
"""

import inspect
import unittest

from armi import settings
from armi.reactor.components import Component
from armi.reactor.particleFuel import ParticleFuel
from armi.reactor import blueprints
from armi.reactor.flags import Flags
from armi.nucDirectory import nucDir


class TestComponentBlueprint(unittest.TestCase):

    componentString = r"""
blocks:
    block: &block
        component:
            flags: {flags}
            shape: Hexagon
            material: {material} # This is being used to format a string to allow for different materials to be added
            {isotopics} # This is being used to format a string to allow for different isotopics to be added
            Tinput: 25.0
            Thot: 600.0
            ip: 0.0
            mult: 169.0
            op: 0.86602
assemblies:
    assembly: &assembly_a
        specifier: IC
        blocks: [*block]
        height: [1.0]
        axial mesh points: [1]
        xs types: [A]
"""

    def test_componentInitializationIncompleteBurnChain(self):
        nuclideFlagsFuelWithBurn = (
            inspect.cleandoc(
                r"""
            nuclide flags:
                U238: {burn: true, xs: true}
                U235: {burn: true, xs: true}
                ZR: {burn: false, xs: true}
            """
            )
            + "\n"
        )
        bp = blueprints.Blueprints.load(
            nuclideFlagsFuelWithBurn
            + self.componentString.format(material="UZr", isotopics="", flags="")
        )
        cs = settings.Settings()
        with self.assertRaises(ValueError):
            bp.constructAssem(cs, "assembly")

    def test_componentInitializationControlCustomIsotopics(self):
        nuclideFlags = (
            inspect.cleandoc(
                r"""
            nuclide flags:
                U234: {burn: true, xs: true}
                U235: {burn: true, xs: true}
                U238: {burn: true, xs: true}
                B10: {burn: true, xs: true}
                B11: {burn: true, xs: true}
                C: {burn: true, xs: true}
                DUMP1: {burn: true, xs: true}
            custom isotopics:
                B4C:
                    input format: number densities
                    B10: 1.0
                    B11: 1.0
                    C: 1.0
            """
            )
            + "\n"
        )
        bp = blueprints.Blueprints.load(
            nuclideFlags
            + self.componentString.format(
                material="Custom", isotopics="isotopics: B4C", flags=""
            )
        )
        cs = settings.Settings()
        _ = bp.constructAssem(cs, "assembly")

    def test_autoDepletable(self):
        nuclideFlags = (
            inspect.cleandoc(
                r"""
            nuclide flags:
                U234: {burn: true, xs: true}
                U235: {burn: true, xs: true}
                U238: {burn: true, xs: true}
                B10: {burn: true, xs: true}
                B11: {burn: true, xs: true}
                C: {burn: true, xs: true}
                DUMP1: {burn: true, xs: true}
            custom isotopics:
                B4C:
                    input format: number densities
                    B10: 1.0
                    B11: 1.0
                    C: 1.0
            """
            )
            + "\n"
        )
        bp = blueprints.Blueprints.load(
            nuclideFlags
            + self.componentString.format(
                material="Custom", isotopics="isotopics: B4C", flags=""
            )
        )
        cs = settings.Settings()
        a = bp.constructAssem(cs, "assembly")
        expectedNuclides = ["B10", "B11", "C", "DUMP1"]
        unexpectedNuclides = ["U234", "U325", "U238"]
        for nuc in expectedNuclides:
            self.assertIn(nuc, a[0][0].getNuclides())
        for nuc in unexpectedNuclides:
            self.assertNotIn(nuc, a[0][0].getNuclides())

        c = a[0][0]

        # Since we didn't supply flags, we should get the DEPLETABLE flag added
        # automatically, since this one has depletable nuclides
        self.assertEqual(c.p.flags, Flags.DEPLETABLE)
        # More robust test, but worse unittest.py output when it fails
        self.assertTrue(c.hasFlags(Flags.DEPLETABLE))

        # repeat the process with some flags set explicitly
        bp = blueprints.Blueprints.load(
            nuclideFlags
            + self.componentString.format(
                material="Custom", isotopics="isotopics: B4C", flags="fuel test"
            )
        )
        cs = settings.Settings()
        a = bp.constructAssem(cs, "assembly")
        c = a[0][0]

        # Since we supplied flags, we should NOT get the DEPLETABLE flag added
        self.assertEqual(c.p.flags, Flags.FUEL | Flags.TEST)
        # More robust test, but worse unittest.py output when it fails
        self.assertTrue(c.hasFlags(Flags.FUEL | Flags.TEST))

    def test_componentInitializationAmericiumCustomIsotopics(self):
        nuclideFlags = (
            inspect.cleandoc(
                r"""
            nuclide flags:
                CM242: {burn: true, xs: true}
                PU241: {burn: true, xs: true}
                AM242G: {burn: true, xs: true}
                AM242M: {burn: true, xs: true}
                AM242M: {burn: true, xs: true}
                AM241: {burn: true, xs: true}
                LFP41: {burn: true, xs: true}
                PU240: {burn: true, xs: true}
                AM243: {burn: true, xs: true}
                NP238: {burn: true, xs: true}
                PU242: {burn: true, xs: true}
                CM243: {burn: true, xs: true}
                PU238: {burn: true, xs: true}
                DUMP2: {burn: true, xs: true}
                DUMP1: {burn: true, xs: true}
                U238: {burn: true, xs: true}
                CM244: {burn: true, xs: true}
                LFP40: {burn: true, xs: true}
                U236: {burn: true, xs: true}
                PU236: {burn: true, xs: true}
                U234: {burn: true, xs: true}
                CM245: {burn: true, xs: true}
                PU239: {burn: true, xs: true}
                NP237: {burn: true, xs: true}
                U235: {burn: true, xs: true}
                LFP39: {burn: true, xs: true}
                LFP35: {burn: true, xs: true}
                LFP38: {burn: true, xs: true}
                CM246: {burn: true, xs: true}
                CM247: {burn: true, xs: true}
                B10: {burn: true, xs: true}
                B11: {burn: true, xs: true}
                W186: {burn: true, xs: true}
                C: {burn: true, xs: true}
                S: {burn: true, xs: true}
                P: {burn: true, xs: true}
            custom isotopics:
                AM:
                    input format: number densities
                    AM241: 1.0
            """
            )
            + "\n"
        )
        bp = blueprints.Blueprints.load(
            nuclideFlags
            + self.componentString.format(
                material="Custom", isotopics="isotopics: AM", flags=""
            )
        )
        cs = settings.Settings()
        a = bp.constructAssem(cs, "assembly")
        expectedNuclides = [
            "AM241",
            "U238",
            "AM243",
            "AM242",
            "NP237",
            "NP238",
            "U234",
            "U235",
            "LFP38",
            "LFP39",
            "PU239",
            "PU238",
            "LFP35",
            "U236",
            "CM247",
            "CM246",
            "CM245",
            "CM244",
            "PU240",
            "PU241",
            "PU242",
            "PU236",
            "CM243",
            "CM242",
            "DUMP2",
            "LFP41",
            "LFP40",
        ]
        unexpectedNuclides = ["B10", "B11", "W186", "C", "S", "P"]
        for nuc in expectedNuclides:
            self.assertIn(nuc, a[0][0].getNuclides())
        for nuc in unexpectedNuclides:
            self.assertNotIn(nuc, a[0][0].getNuclides())

    def test_componentInitializationThoriumBurnCustomIsotopics(self):
        nuclideFlags = (
            inspect.cleandoc(
                r"""
            nuclide flags:
                TH232: {burn: true, xs: true}
                PA233: {burn: true, xs: true}
                PA231: {burn: true, xs: true}
                U232: {burn: true, xs: true}
                U233: {burn: true, xs: true}
                CM242: {burn: true, xs: true}
                PU241: {burn: true, xs: true}
                AM242G: {burn: true, xs: true}
                AM242M: {burn: true, xs: true}
                AM242M: {burn: true, xs: true}
                AM241: {burn: true, xs: true}
                LFP41: {burn: true, xs: true}
                PU240: {burn: true, xs: true}
                AM243: {burn: true, xs: true}
                NP238: {burn: true, xs: true}
                PU242: {burn: true, xs: true}
                CM243: {burn: true, xs: true}
                PU238: {burn: true, xs: true}
                DUMP2: {burn: true, xs: true}
                DUMP1: {burn: true, xs: true}
                U238: {burn: true, xs: true}
                CM244: {burn: true, xs: true}
                LFP40: {burn: true, xs: true}
                U236: {burn: true, xs: true}
                PU236: {burn: true, xs: true}
                U234: {burn: true, xs: true}
                CM245: {burn: true, xs: true}
                PU239: {burn: true, xs: true}
                NP237: {burn: true, xs: true}
                U235: {burn: true, xs: true}
                LFP39: {burn: true, xs: true}
                LFP35: {burn: true, xs: true}
                LFP38: {burn: true, xs: true}
                CM246: {burn: true, xs: true}
                CM247: {burn: true, xs: true}
            custom isotopics:
                Thorium:
                    input format: number densities
                    TH232: 1.0
            """
            )
            + "\n"
        )
        bp = blueprints.Blueprints.load(
            nuclideFlags
            + self.componentString.format(
                material="Custom", isotopics="isotopics: Thorium", flags=""
            )
        )
        cs = settings.Settings()
        a = bp.constructAssem(cs, "assembly")
        expectedNuclides = ["TH232", "PA233", "PA231", "DUMP2", "LFP35"]
        for nuc in expectedNuclides:
            self.assertIn(nuc, a[0][0].getNuclides())

    def test_componentInitializationThoriumNoBurnCustomIsotopics(self):
        nuclideFlags = (
            inspect.cleandoc(
                r"""
            nuclide flags:
                TH232: {burn: false, xs: true}
            custom isotopics:
                Thorium:
                    input format: number densities
                    TH232: 1.0
            """
            )
            + "\n"
        )
        bp = blueprints.Blueprints.load(
            nuclideFlags
            + self.componentString.format(
                material="Custom", isotopics="isotopics: Thorium", flags=""
            )
        )
        cs = settings.Settings()
        a = bp.constructAssem(cs, "assembly")
        expectedNuclides = ["TH232"]
        for nuc in expectedNuclides:
            self.assertIn(nuc, a[0][0].getNuclides())


class TestCompsWithParticleFuel(unittest.TestCase):
    componentString = """
blocks:
    block: &block
        duct:
            shape: Hexagon
            material: Graphite
            Tinput: 600
            Thot: 600
            ip: 20
            op: 21
        component:
            flags: MATRIX
            shape: Circle
            material: SiC
            Tinput: 600.0
            Thot: 600.0
            id: 0.0
            od: 0.8660
            particleFuelSpec: dual
            particleFuelPackingFraction: {pf}
assemblies:
    assembly: &assembly_a
        specifier: IC
        blocks: [*block]
        height: [1.0]
        axial mesh points: [1]
        xs types: [A]
particle fuel:
    dual:
        kernel:
            material: UraniumOxide
            Thot: 900
            Tinput: 900
            id: {innerID}
            od: {innerOD}
            flags: DEPLETABLE
        shell:
            material: SiC
            Tinput: 800
            Thot: 800
            id: {outerID}
            od: {outerOD}
nuclide flags:
    U235: {{burn: false, xs: true}}
    U238: {{burn: false, xs: true}}
    C: {{burn: false, xs: true}}
    SI: {{burn: false, xs: true}}
    O: {{burn: false, xs: true}}
"""
    DEF_PF = 0.4
    DEF_INNER_ID = 0.0
    DEF_INNER_OD = 0.6
    DEF_OUTER_ID = 0.6
    DEF_OUTER_OD = 0.7

    def render(self, **kwargs):
        kwargs.setdefault("pf", self.DEF_PF)
        kwargs.setdefault("innerID", self.DEF_INNER_ID)
        kwargs.setdefault("innerOD", self.DEF_INNER_OD)
        kwargs.setdefault("outerID", self.DEF_OUTER_ID)
        kwargs.setdefault("outerOD", self.DEF_OUTER_OD)
        return self.componentString.format(**kwargs)

    def getCompWithParticleFuel(self, **kwargs) -> Component:
        spec = self.render(**kwargs)
        bp = blueprints.Blueprints.load(spec)
        cs = settings.Settings()
        assem = bp.constructAssem(cs, "assembly")
        return assem[0][1]

    def test_valid(self):
        comp = self.getCompWithParticleFuel()
        packedSpec = comp.particleFuel
        self.assertIsNotNone(packedSpec)
        self.assertEqual(packedSpec.name, "dual")
        self.assertEqual(comp.p.get("packingFractionBOL"), self.DEF_PF)
        spheres = packedSpec.layers
        self.assertEqual(len(spheres), 2)

        inner, outer = spheres
        self.assertEqual(inner.getDimension("id"), self.DEF_INNER_ID)
        self.assertEqual(inner.getDimension("od"), self.DEF_INNER_OD)
        self.assertEqual(inner.material.name, "Uranium Oxide")
        self.assertTrue(inner.hasFlags(Flags.DEPLETABLE))

        self.assertEqual(outer.getDimension("id"), self.DEF_OUTER_ID)
        self.assertEqual(outer.getDimension("od"), self.DEF_OUTER_OD)
        self.assertEqual(outer.material.name, "Silicon Carbide")

    def test_invalidPF(self):
        # yamlize intercepts the exception raised during validation
        # and instead raises an yamlize error. We don't care for the
        # specific type of exception, just that one is raised indicating
        # invalid packing fraction
        with self.assertRaisesRegex(
            Exception, "Packing fraction.*must be between 0 and 1"
        ):
            self.getCompWithParticleFuel(pf=-1)

    def test_invalidLayerDims(self):
        spec = self.render(outerOD=0.95 * self.DEF_OUTER_ID)
        bp = blueprints.Blueprints.load(spec)
        cs = settings.Settings()
        with self.assertRaisesRegex(
            ValueError,
            "^shell outer diameter must be greater than inner",
        ):
            bp.constructAssem(cs, "assembly")

        spec = self.render(innerID=-1)
        bp = blueprints.Blueprints.load(spec)
        with self.assertRaisesRegex(
            ValueError, "^kernel inner diameter must be non-negative"
        ):
            bp.constructAssem(cs, "assembly")

    def test_specWithGaps(self):
        # Define a spec where the outer bound of one layer
        # is not the inner bound of the next layer
        # zero = inner_id < inner_od < outer_id < outer_od
        # where we should have inner_od == outer_id
        outerID = 1.1 * self.DEF_INNER_OD
        spec = self.render(outerID=outerID, outerOD=1.1 * outerID)

        bp = blueprints.Blueprints.load(spec)
        cs = settings.Settings()

        with self.assertRaisesRegex(ValueError, "consistent boundaries"):
            bp.constructAssem(cs, "assembly")

    def test_specWithOverlaps(self):
        # Define a spec where the two layers overlap
        # zero = inner_id < outer_id < inner_od < outer_od
        outerID = 0.5 * (self.DEF_INNER_ID + self.DEF_INNER_OD)
        spec = self.render(outerID=outerID)

        bp = blueprints.Blueprints.load(spec)
        cs = settings.Settings()

        with self.assertRaisesRegex(ValueError, "consistent boundaries"):
            bp.constructAssem(cs, "assembly")

    def test_noZeroID(self):
        # Define a spec that does not start at zero
        innerID = 0.5 * (self.DEF_INNER_ID + self.DEF_INNER_OD)
        spec = self.render(innerID=innerID)

        bp = blueprints.Blueprints.load(spec)
        cs = settings.Settings()

        with self.assertRaisesRegex(
            ValueError, ".*dual does not start at radius of zero"
        ):
            bp.constructAssem(cs, "assembly")

    def test_weirdOrdering(self):
        # Define a specification where both rings start at r=0 but have
        # different outer diameters
        spec = self.render(
            outerID=self.DEF_INNER_ID,
        )

        bp = blueprints.Blueprints.load(spec)
        cs = settings.Settings()

        with self.assertRaisesRegex(ValueError, "inconsistent inner diameters"):
            bp.constructAssem(cs, "assembly")

    def test_fuelFlag(self):
        # Test if FUEL flag was added to particle kernel
        fuelBlock = self.getCompWithParticleFuel().parent

        hasHeavyMetal = False
        for child in fuelBlock:
            spec = child.particleFuel
            if spec is not None:
                for component in spec.layers:
                    if any(
                        nucDir.isHeavyMetal(nucName)
                        for nucName in component.getNuclides()
                    ):
                        self.assertIn(Flags.FUEL, component.p.flags)
                        hasHeavyMetal = True
                    else:
                        self.assertNotIn(Flags.FUEL, component.p.flags)
        self.assertTrue(hasHeavyMetal)

    def test_particleParent(self):
        # check the parent/child relationship for a component and particle fuel
        comp = self.getCompWithParticleFuel()
        spec = comp.particleFuel

        self.assertIs(spec.parent, comp)

        for layer in spec.layers:
            self.assertIs(layer.parent, spec)
            self.assertIn(layer, spec)

    def test_multipleParticleFuelChildren(self):
        comp = self.getCompWithParticleFuel()

        comp.add(ParticleFuel("extra"))

        with self.assertRaisesRegex(ValueError, "^Multiple"):
            comp.particleFuel

    def test_noParticleFuel(self):
        comp = self.getCompWithParticleFuel()
        comp.remove(comp.particleFuel)

        with self.assertRaisesRegex(ValueError, "^No"):
            comp.particleFuel


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'TestComponentBlueprint.test_componentInitializationAmericiumCustomIsotopics']
    unittest.main()
