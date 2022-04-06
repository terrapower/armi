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

from armi import settings
from armi.reactor import blueprints


class TestMaterialModifications(unittest.TestCase):
    twoBlockInput_correct = r"""
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
        blocks: [*block_fuel, *block_fuel]
        height: [1.0, 1.0]
        axial mesh points: [1, 1]
        xs types: [A, A]
"""

    twoBlockInput_wrongMeshPoints = r"""
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
        blocks: [*block_fuel, *block_fuel]
        height: [1.0, 1.0]
        axial mesh points: [1]
        xs types: [A, A]
"""

    twoBlockInput_wrongHeights = r"""
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
        blocks: [*block_fuel, *block_fuel]
        height: [1.0]
        axial mesh points: [1, 1]
        xs types: [A, A]
"""

    twoBlockInput_wrongXSTypes = r"""
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
        blocks: [*block_fuel, *block_fuel]
        height: [1.0, 1.0]
        axial mesh points: [1, 1]
        xs types: [A]
"""

    twoBlockInput_wrongMatMods = r"""
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
        blocks: [*block_fuel, *block_fuel]
        height: [1.0, 1.0]
        axial mesh points: [1, 1]
        xs types: [A, A]
        material modifications:
            U235_wt_frac: [0.5]
"""

    def loadCustomAssembly(self, assemblyInput):
        yamlString = assemblyInput
        design = blueprints.Blueprints.load(yamlString)
        design._prepConstruction(settings.getMasterCs())
        return design.assemblies["fuel a"]

    def test_checkParamConsistency(self):
        # make sure a good example doesn't error
        a = self.loadCustomAssembly(self.twoBlockInput_correct)
        blockAxialMesh = a.getAxialMesh()
        blockXSTypes = [a[0].p.xsType, a[1].p.xsType]
        self.assertAlmostEqual(blockAxialMesh, [1.0, 2.0])
        self.assertEqual(blockXSTypes, ["A", "A"])

        with self.assertRaises(ValueError):
            a = self.loadCustomAssembly(self.twoBlockInput_wrongMeshPoints)

        with self.assertRaises(ValueError):
            a = self.loadCustomAssembly(self.twoBlockInput_wrongHeights)

        with self.assertRaises(ValueError):
            a = self.loadCustomAssembly(self.twoBlockInput_wrongXSTypes)

        with self.assertRaises(ValueError):
            a = self.loadCustomAssembly(self.twoBlockInput_wrongMatMods)


if __name__ == "__main__":
    unittest.main()
