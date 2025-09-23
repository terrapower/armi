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

"""Module for testing componentBlueprint."""

import inspect
import unittest

from armi import settings
from armi.reactor import blueprints
from armi.reactor.flags import Flags


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

    def test_compInitIncompleteBurnChain(self):
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
            nuclideFlagsFuelWithBurn + self.componentString.format(material="UZr", isotopics="", flags="")
        )
        cs = settings.Settings()
        with self.assertRaises(ValueError):
            bp.constructAssem(cs, "assembly")

    def test_compInitControlCustomIso(self):
        nuclideFlags = (
            inspect.cleandoc(
                """
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
            nuclideFlags + self.componentString.format(material="Custom", isotopics="isotopics: B4C", flags="")
        )
        cs = settings.Settings()
        _ = bp.constructAssem(cs, "assembly")

    def test_autoDepletable(self):
        nuclideFlags = (
            inspect.cleandoc(
                """
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
            nuclideFlags + self.componentString.format(material="Custom", isotopics="isotopics: B4C", flags="")
        )
        cs = settings.Settings()
        a = bp.constructAssem(cs, "assembly")
        expectedNuclides = ["B10", "B11", "C", "DUMP1"]
        unexpectedNuclides = ["U234", "U325", "U238"]
        print(a[0][0].getNuclides())
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
            nuclideFlags + self.componentString.format(material="Custom", isotopics="isotopics: B4C", flags="fuel test")
        )
        cs = settings.Settings()
        a = bp.constructAssem(cs, "assembly")
        c = a[0][0]

        # Since we supplied flags, we should NOT get the DEPLETABLE flag added
        self.assertEqual(c.p.flags, Flags.FUEL | Flags.TEST)
        # More robust test, but worse unittest.py output when it fails
        self.assertTrue(c.hasFlags(Flags.FUEL | Flags.TEST))

    def test_compInitAmericiumCustomIso(self):
        nuclideFlags = (
            inspect.cleandoc(
                r"""
            nuclide flags:
                CM242: {burn: true, xs: true}
                PU241: {burn: true, xs: true}
                AM242G: {burn: true, xs: true}
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
            nuclideFlags + self.componentString.format(material="Custom", isotopics="isotopics: AM", flags="")
        )
        cs = settings.Settings()
        a = bp.constructAssem(cs, "assembly")
        expectedNuclides = [
            "AM241",
            "U238",
            "AM243",
            "AM242M",
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

    def test_compInitThoriumBurnCustomIso(self):
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
            nuclideFlags + self.componentString.format(material="Custom", isotopics="isotopics: Thorium", flags="")
        )
        cs = settings.Settings()
        a = bp.constructAssem(cs, "assembly")
        expectedNuclides = ["TH232", "PA233", "PA231", "DUMP2", "LFP35"]
        for nuc in expectedNuclides:
            self.assertIn(nuc, a[0][0].getNuclides())

    def test_compInitThoriumNoBurnCustomIso(self):
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
            nuclideFlags + self.componentString.format(material="Custom", isotopics="isotopics: Thorium", flags="")
        )
        cs = settings.Settings()
        a = bp.constructAssem(cs, "assembly")
        expectedNuclides = ["TH232"]
        for nuc in expectedNuclides:
            self.assertIn(nuc, a[0][0].getNuclides())
