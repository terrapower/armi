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
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access

import unittest

from numpy.testing import assert_allclose

from armi import materials
from armi import settings
from armi.reactor import blueprints
from armi.reactor.blueprints.blockBlueprint import BlockBlueprint


class TestMaterialModifications(unittest.TestCase):
    uZrInput = r"""
nuclide flags:
    U: {burn: false, xs: true}
    ZR: {burn: false, xs: true}
blocks:
    fuel: &block_fuel
        fuel1: &component_fuel_fuel1
            shape: Hexagon
            material: UZr
            Tinput: 600.0
            Thot: 600.0
            ip: 0.0
            mult: 1
            op: 10.0
        fuel2: &component_fuel_fuel2
            shape: Hexagon
            material: UZr
            Tinput: 600.0
            Thot: 600.0
            ip: 0.0
            mult: 1
            op: 10.0
assemblies:
    fuel a: &assembly_a
        specifier: IC
        blocks: [*block_fuel]
        height: [1.0]
        axial mesh points: [1]
        xs types: [A]
"""

    boronInput = uZrInput.replace("UZr", "B")

    def loadUZrAssembly(self, materialModifications):
        yamlString = self.uZrInput + "\n" + materialModifications
        design = blueprints.Blueprints.load(yamlString)
        design._prepConstruction(settings.Settings())
        return design.assemblies["fuel a"]

    def test_noMaterialModifications(self):
        a = self.loadUZrAssembly("")
        # mass fractions should be whatever UZr is
        uzr = materials.UZr()
        fuelComponent = a[0][0]
        totalMass = fuelComponent.getMass()
        for nucName in uzr.massFrac:
            massFrac = fuelComponent.getMass(nucName) / totalMass
            assert_allclose(uzr.massFrac[nucName], massFrac)

    def test_u235_wt_frac_modification(self):
        a = self.loadUZrAssembly(
            """
        material modifications:
            U235_wt_frac: [0.20]
        """
        )
        fuelComponent = a[0][0]
        u235 = fuelComponent.getMass("U235")
        u = fuelComponent.getMass("U")
        assert_allclose(0.20, u235 / u)

        fuelComponent = a[0][1]
        u235 = fuelComponent.getMass("U235")
        u = fuelComponent.getMass("U")
        assert_allclose(0.20, u235 / u)

    def test_u235_wt_frac_byComponent_modification1(self):
        a = self.loadUZrAssembly(
            """
        material modifications:
            by component:
                fuel1:
                    U235_wt_frac: [0.20]
            U235_wt_frac: [0.30]
        """
        )
        fuelComponent = a[0][0]
        u235 = fuelComponent.getMass("U235")
        u = fuelComponent.getMass("U")
        assert_allclose(0.20, u235 / u)

        fuelComponent = a[0][1]
        u235 = fuelComponent.getMass("U235")
        u = fuelComponent.getMass("U")
        assert_allclose(0.30, u235 / u)

    def test_u235_wt_frac_byComponent_modification2(self):
        a = self.loadUZrAssembly(
            """
        material modifications:
            by component:
                fuel1:
                    U235_wt_frac: [0.20]
                fuel2:
                    U235_wt_frac: [0.50]
            U235_wt_frac: [0.30]
        """
        )
        fuelComponent = a[0][0]
        u235 = fuelComponent.getMass("U235")
        u = fuelComponent.getMass("U")
        assert_allclose(0.20, u235 / u)

        fuelComponent = a[0][1]
        u235 = fuelComponent.getMass("U235")
        u = fuelComponent.getMass("U")
        assert_allclose(0.50, u235 / u)

    def test_invalid_component_modification(self):
        with self.assertRaises(ValueError):
            _a = self.loadUZrAssembly(
                """
        material modifications:
            by component:
                invalid component:
                    U235_wt_frac: [0.2]
        """
            )

    def test_zr_wt_frac_modification(self):
        a = self.loadUZrAssembly(
            """
        material modifications:
            ZR_wt_frac: [0.077]
        """
        )
        fuelComponent = a[0][0]
        totalMass = fuelComponent.getMass()
        zr = fuelComponent.getMass("ZR")
        assert_allclose(0.077, zr / totalMass)

    def test_both_u235_zr_wt_frac_modification(self):
        a = self.loadUZrAssembly(
            """
        material modifications:
            ZR_wt_frac: [0.077]
            U235_wt_frac: [0.20]
        """
        )
        fuelComponent = a[0][0]

        # check u235 enrichment
        u235 = fuelComponent.getMass("U235")
        u = fuelComponent.getMass("U")
        assert_allclose(0.20, u235 / u)

        # check zr frac
        totalMass = fuelComponent.getMass()
        zr = fuelComponent.getMass("ZR")
        assert_allclose(0.077, zr / totalMass)

    def test_checkByComponentMaterialInput(self):
        a = self.loadUZrAssembly("")
        materialInput = {"fake_material": {"ZR_wt_frac": 0.5}}
        with self.assertRaises(ValueError):
            BlockBlueprint._checkByComponentMaterialInput(a, materialInput)

    def test_filterMaterialInput(self):
        a = self.loadUZrAssembly("")
        materialInput = {
            "byBlock": {"ZR_wt_frac": 0.1, "U235_wt_frac": 0.1},
            "fuel1": {"U235_wt_frac": 0.2},
            "fuel2": {"ZR_wt_frac": 0.3, "U235_wt_frac": 0.3},
        }
        componentDesign = a[0][0]
        filteredMaterialInput, _ = BlockBlueprint._filterMaterialInput(
            materialInput, componentDesign
        )

        filteredMaterialInput_reference = {"ZR_wt_frac": 0.1, "U235_wt_frac": 0.2}

        self.assertEqual(filteredMaterialInput, filteredMaterialInput_reference)

    def test_invalidMatModName(self):
        """
        This test shows proves that we can detect invalid material modification
        names when they are specified on an assembly blueprint. We happen to know
        that ZR_wt_frac is a valid modification for the UZr material class, so we
        use that in the first call to prove that things initially work fine.
        """
        a = self.loadUZrAssembly(
            """
        material modifications:
            ZR_wt_frac: [1]
            by component:
                fuel2:
                    ZR_wt_frac: [0]
        """
        )
        # just to prove that the above works fine before we modify it
        self.assertAlmostEqual(a[0][0].getMassFrac("ZR"), 1)
        self.assertAlmostEqual(a[0][1].getMassFrac("ZR"), 0)

        with self.assertRaises(ValueError):
            a = self.loadUZrAssembly(
                """
        material modifications:
            this_is_a_fake_name: [1]
            by component:
                fuel2:
                    ZR_wt_frac: [0]
        """
            )

        with self.assertRaises(ValueError):
            a = self.loadUZrAssembly(
                """
        material modifications:
            ZR_wt_frac: [1]
            by component:
                fuel2:
                    this_is_a_fake_name: [0]
        """
            )

    def test_matModsUpTheMRO(self):
        """
        Make sure that valid/invalid material modifications are searched up
        the MRO for a material class.
        """
        a = self.loadUZrAssembly(
            """
        material modifications:
            ZR_wt_frac: [1]
            class1_wt_frac: [1]
            class1_custom_isotopics: [dummy]
            class2_custom_isotopics: [dummy]
            by component:
                fuel2:
                    ZR_wt_frac: [0]
                    class1_wt_frac: [1]
                    class1_custom_isotopics: [dummy]
                    class2_custom_isotopics: [dummy]
custom isotopics:
    dummy:
        input format: mass fractions
        density: 1
        U: 1
"""
        )

        with self.assertRaises(ValueError):
            a = self.loadUZrAssembly(
                """
        material modifications:
            ZR_wt_frac: [1]
            klass1_wt_frac: [1]
            klass1_custom_isotopics: [dummy]
            klass2_custom_isotopics: [dummy]
            by component:
                fuel2:
                    ZR_wt_frac: [0]
                    klass1_wt_frac: [1]
                    klass1_custom_isotopics: [dummy]
                    klass2_custom_isotopics: [dummy]
custom isotopics:
    dummy:
        input format: mass fractions
        density: 1
        U: 1
"""
            )


if __name__ == "__main__":
    unittest.main()
