# Copyright 2025 TerraPower, LLC
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

FULL_BP = """
blocks:
    grid plate: &block_grid_plate
        grid:
            shape: Hexagon
            material: HT9
            Tinput: 25.0
            Thot: 450.0
            ip: 15.277
            mult: 1.0
            op: 16.577
        coolant: &component_coolant
            shape: DerivedShape
            material: Sodium
            Tinput: 25.0
            Thot: 450.0
        intercoolant:
            shape: Hexagon
            material: Sodium
            Tinput: 25.0
            Thot: 450.0
            ip: grid.op
            mult: 1.0
            op: 19.0

    duct: &block_duct
        coolant: *component_coolant
        duct: &component_duct
            shape: Hexagon
            material: HT9
            Tinput: 25.0
            Thot: 450.0
            ip: 18.0
            mult: 1.0
            op: 18.5
        intercoolant: &component_intercoolant
            shape: Hexagon
            material: Sodium
            Tinput: 25.0
            Thot: 450.0
            ip: duct.op
            mult: 1.0
            op: 19.0

    axial shield twoPin: &block_fuel_multiPin_axial_shield
        grid name: twoPin
        shield: &component_shield_shield1
            shape: Circle
            material: HT9
            Tinput: 25.0
            Thot: 600.0
            id: 0.0
            od: 0.86602
            latticeIDs: [1]
        bond: &component_shield_bond1
            shape: Circle
            material: Sodium
            Tinput: 25.0
            Thot: 470.0
            id: shield.od
            od: clad.id
            latticeIDs: [1]
        clad: &component_shield_clad1
            shape: Circle
            material: HT9
            Tinput: 25.0
            Thot: 470.0
            id: 1.0
            od: 1.09
            latticeIDs: [1]
        wire: &component_shield_wire1
            shape: Helix
            material: HT9
            Tinput: 25.0
            Thot: 470.0
            axialPitch: 30.15
            helixDiameter: 1.19056
            id: 0.0
            od: 0.10056
            latticeIDs: [1]
        shield test:
            <<: *component_shield_shield1
            latticeIDs: [2]
        bond test:
            <<: *component_shield_bond1
            id: shield test.od
            od: clad test.id
            latticeIDs: [2]
        clad test:
            <<: *component_shield_clad1
            latticeIDs: [2]
        wire test:
            <<: *component_shield_wire1
            latticeIDs: [2]
        coolant: *component_coolant
        duct: *component_duct
        intercoolant: *component_intercoolant
        axial expansion target component: shield

    fuel twoPin: &block_fuel_multiPin
        grid name: twoPin
        fuel: &component_fuelmultiPin
            shape: Circle
            material: UZr
            Tinput: 25.0
            Thot: 600.0
            id: 0.0
            od: 0.86602
            latticeIDs: [1]
        bond: &component_fuelmultiPin_bond
            shape: Circle
            material: Sodium
            Tinput: 25.0
            Thot: 470.0
            id: fuel.od
            od: clad.id
            latticeIDs: [1]
        clad: &component_fuelmultiPin_clad1
            shape: Circle
            material: HT9
            Tinput: 25.0
            Thot: 470.0
            id: 1.0
            od: 1.09
            latticeIDs: [1]
        wire: &component_fuelmultiPin_wire1
            shape: Helix
            material: HT9
            Tinput: 25.0
            Thot: 470.0
            axialPitch: 30.15
            helixDiameter: 1.19056
            id: 0.0
            od: 0.10056
            latticeIDs: [1]
        fuel test: &component_fuelmultiPin_fuel2
            <<: *component_fuelmultiPin
            latticeIDs: [2]
        bond test: &component_fuelmultiPin_bond2
            <<: *component_fuelmultiPin_bond
            id: fuel test.od
            od: clad test.id
            latticeIDs: [2]
        clad test: &component_fuelmultiPin_clad2
            <<: *component_fuelmultiPin_clad1
            latticeIDs: [2]
        wire test: &component_fuelmultiPin_wire2
            <<: *component_fuelmultiPin_wire1
            latticeIDs: [2]
        coolant: *component_coolant
        duct: *component_duct
        intercoolant: *component_intercoolant
        axial expansion target component: fuel

    plenum 2pin: &block_plenum_multiPin
        grid name: twoPin
        gap: &component_plenummultiPin_gap1
            shape: Circle
            material: Void
            Tinput: 25.0
            Thot: 600.0
            id: 0.0
            od: clad.id
            latticeIDs: [1]
        clad: *component_fuelmultiPin_clad1
        wire: *component_fuelmultiPin_wire1
        gap test:
            <<: *component_plenummultiPin_gap1
            od: clad test.id
            latticeIDs: [2]
        clad test: *component_fuelmultiPin_clad2
        wire test: *component_fuelmultiPin_wire2
        coolant: *component_coolant
        duct: *component_duct
        intercoolant: *component_intercoolant
        axial expansion target component: clad test

    mixed fuel plenum 2pin: &block_mixed_multiPin
        grid name: twoPin
        gap: *component_plenummultiPin_gap1
        clad: *component_fuelmultiPin_clad1
        wire: *component_fuelmultiPin_wire1
        fuel test: *component_fuelmultiPin_fuel2
        bond test: *component_fuelmultiPin_bond2
        clad test: *component_fuelmultiPin_clad2
        wire test: *component_fuelmultiPin_wire2
        coolant: *component_coolant
        duct: *component_duct
        intercoolant: *component_intercoolant
        axial expansion target component: fuel test

    aclp plenum 2pin: &block_aclp_multiPin
        <<: *block_plenum_multiPin

    SodiumBlock: &block_dummy
        flags: dummy
        coolant:
            shape: Hexagon
            material: Sodium
            Tinput: 25.0
            Thot: 450.0
            ip: 0.0
            mult: 1.0
            op: 19.0

assemblies:
    multi pin fuel:
        specifier: LA
        blocks: [*block_grid_plate, *block_fuel_multiPin_axial_shield, *block_fuel_multiPin, *block_fuel_multiPin, *block_fuel_multiPin, *block_mixed_multiPin, *block_aclp_multiPin, *block_plenum_multiPin, *block_duct, *block_dummy]
        height: [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        axial mesh points: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        material modifications:
            U235_wt_frac: ['', '', 0.2, 0.2, 0.2, 0.2, '', '', '', '']
            ZR_wt_frac: ['', '', 0.07, 0.07, 0.07, 0.07, '', '', '', '']
        xs types: [A, A, B, C, C, D, A, A, A, A]
grids:
    core:
        geom: hex
        symmetry: third periodic
        lattice map: LA
    twoPin:
        geom: hex_corners_up
        symmetry: full
        lattice map: |
          - - -  1 1 1 1
            - - 1 1 2 1 1
             - 1 1 2 2 1 1
              1 1 2 2 2 1 1
               1 1 2 2 1 1
                1 1 2 1 1
                 1 1 1 1
"""

import io
from armi.settings import Settings
from armi.reactor.blueprints import Blueprints

def buildMixedPinAssembly():
    cs = Settings()
    with io.StringIO(FULL_BP) as stream:
        blueprints = Blueprints.load(stream)
        blueprints._prepConstruction(cs)

    return list(blueprints.assemblies.values())[0]
