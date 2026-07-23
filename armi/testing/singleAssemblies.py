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
"""
Importable testing utilities for assembly-related machinery.

This is a very limited set of ARMI block testing tools, meant to be importable as part of the ARMI API. The goal is to
provide a small set of high quality assembly-related tools to help downstream ARMI developers write tests.

Notes
-----
This will not be a catch-all for random unit test functions. Be very sparing here.
"""

import io

from armi.reactor import assemblies, blocks, grids
from armi.reactor.assemblies import copy
from armi.reactor.blueprints import Blueprints
from armi.reactor.components import Circle, Hexagon
from armi.settings import Settings

BLOCK_DEFINITIONS_2PIN = """
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
"""

BLOCK_DEFINITIONS_3PIN = """
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

    axial shield threePin: &block_fuel_multiPin_axial_shield
        grid name: threePin
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
        annular void: &shield_annular_void
            shape: Circle
            material: Void
            Tinput: 25.0
            Thot: 600.0
            id: 0.0
            od: annular shield test.id
            latticeIDs: [3]
        annular shield test:
            shape: Circle
            material: HT9
            Tinput: 25.0
            Thot: 600.0
            id: 0.600
            od: 0.950
            latticeIDs: [3]
        gap1:
            shape: Circle
            material: Void
            Tinput: 25.0
            Thot: 600.0
            id: annular shield test.od
            od: liner.id
            latticeIDs: [3]
        liner:
            shape: Circle
            material: Zr
            Tinput: 25.0
            Thot: 600.0
            id: 0.950
            od: 1.000
            latticeIDs: [3]
        gap2:
            shape: Circle
            material: Void
            Tinput: 25.0
            Thot: 600.0
            id: liner.od
            od: annular clad test.id
            latticeIDs: [3]
        annular clad test:
            shape: Circle
            material: HT9
            Tinput: 25.0
            Thot: 600.0
            id: 1.000
            od: 1.090
            latticeIDs: [3]
        coolant: *component_coolant
        duct: *component_duct
        intercoolant: *component_intercoolant
        axial expansion target component: shield

    fuel threePin: &block_fuel_multiPin
        grid name: threePin
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
        annular void: &fuel_annular_void
            <<: *shield_annular_void
            od: annular fuel test.id
        annular fuel test: &fuel_annular_test
            shape: Circle
            material: UZr
            Tinput: 25.0
            Thot: 600.0
            id: 0.600
            od: 0.950
            latticeIDs: [3]
        gap1: &annular_test_gap1
            shape: Circle
            material: Void
            Tinput: 25.0
            Thot: 600.0
            id: annular fuel test.od
            od: liner.id
            latticeIDs: [3]
        liner: &liner
            shape: Circle
            material: Zr
            Tinput: 25.0
            Thot: 600.0
            id: 0.950
            od: 1.000
            latticeIDs: [3]
        gap2: &annular_test_gap2
            shape: Circle
            material: Void
            Tinput: 25.0
            Thot: 600.0
            id: liner.od
            od: annular clad test.id
            latticeIDs: [3]
        annular clad test: &annular_clad_test
            shape: Circle
            material: HT9
            Tinput: 25.0
            Thot: 600.0
            id: 1.000
            od: 1.090
            latticeIDs: [3]
        coolant: *component_coolant
        duct: *component_duct
        intercoolant: *component_intercoolant
        axial expansion target component: fuel

    plenum 3pin: &block_plenum_multiPin
        grid name: threePin
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
        annular void:
            <<: *fuel_annular_void
            od: liner.id
            latticeIDs: [3]
        liner: *liner
        gap2: *annular_test_gap2
        annular clad test: *annular_clad_test
        coolant: *component_coolant
        duct: *component_duct
        intercoolant: *component_intercoolant
        axial expansion target component: clad test

    mixed fuel plenum 3pin: &block_mixed_multiPin
        grid name: threePin
        gap: *component_plenummultiPin_gap1
        clad: *component_fuelmultiPin_clad1
        wire: *component_fuelmultiPin_wire1
        fuel test: *component_fuelmultiPin_fuel2
        bond test: *component_fuelmultiPin_bond2
        clad test: *component_fuelmultiPin_clad2
        annular void: *fuel_annular_void
        annular fuel test: *fuel_annular_test
        gap1: *annular_test_gap1
        liner: *liner
        gap2: *annular_test_gap2
        annular clad test: *annular_clad_test
        coolant: *component_coolant
        duct: *component_duct
        intercoolant: *component_intercoolant
        axial expansion target component: fuel test

    aclp plenum 3pin: &block_aclp_multiPin
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
"""

REGULAR_ASSEMBLY_DEF = """
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
"""  # noqa: E501

GRID_DEFINITION = """
grids:
    core:
        geom: hex
        symmetry: third periodic
        lattice map: LA
    twoPin:
        geom: hex_corners_up
        symmetry: full
        lattice map: |
            -  2 1
              2 1 2
               1 2
    threePin:
        geom: hex_corners_up
        symmetry: full
        lattice map: |
            -  2 1
              3 1 3
               1 2
"""


def buildMixedPinAssembly(
    blockDefs: str = BLOCK_DEFINITIONS_2PIN,
    assemDef: str = REGULAR_ASSEMBLY_DEF,
    gridDef: str = GRID_DEFINITION,
):
    """Builds a hex-shaped mixed-pin assembly for a sodium fast reactor. This assembly consists of 2 pin types
    arranged as specified in the lattice map.
    """
    completeBlueprints = blockDefs + assemDef + gridDef
    cs = Settings()
    with io.StringIO(completeBlueprints) as stream:
        blueprints = Blueprints.load(stream)
        blueprints._prepConstruction(cs)

    return list(blueprints.assemblies.values())[0]


def buildMixedThreePinAssembly(
    blockDefs: str = BLOCK_DEFINITIONS_3PIN,
    assemDef: str = REGULAR_ASSEMBLY_DEF,
    gridDef: str = GRID_DEFINITION,
):
    """Builds a hex-shaped mixed-pin assembly for a sodium fast reactor. This assembly consists of 3 pin types
    arranged as specified in the lattice map.
    """
    completeBlueprints = blockDefs + assemDef + gridDef
    cs = Settings()
    with io.StringIO(completeBlueprints) as stream:
        blueprints = Blueprints.load(stream)
        blueprints._prepConstruction(cs)

    return list(blueprints.assemblies.values())[0]


def _createHexBlockTemplate(blockType: str):
    """
    This builds a simple :py:class:`armi.reactor.blocks.HexBlock` object.

    The HexBlock object has the following dimensions:
        - 200 pins with an OD of 1.0
        - isothermal (flat) temperature gradient
        - cladding OD of 1.0
        - embedded in a sodium matrix

    There are two options for the HexBlock:
        'hexUZrUTh': A HexBlock filled with half UZr pins and half UTh pins
        'hexUZr': A HexBlock filled with all UZr pins.

    Parameters
    ----------
    blockType : str
        {'hexUZr', 'hexUZrUTh'}

    Returns
    -------
    block : armi.reactor.blocks.HexBlock
    """
    if blockType not in ["hexUZrUTh", "hexUZr"]:
        raise ValueError(
            f"Invalid blockType for _createHexBlockTemplate: {blockType}only 'hexUZrUTh' and 'hexUZr' are allowed."
        )
    Settings()

    temperature = 273.0
    fuelID = 0.0
    fuelOD = 1.0
    cladOD = 1.1
    nPins = 100

    fuelDims = {
        "Tinput": temperature,
        "Thot": temperature,
        "od": fuelOD,
        "id": fuelID,
        "mult": nPins,
    }

    fuelUZr = Circle("fuel", "UZr", **fuelDims)
    fuelUTh = Circle("fuel UTh", "ThU", **fuelDims)

    fuelDims2nPins = {
        "Tinput": temperature,
        "Thot": temperature,
        "od": fuelOD,
        "id": fuelID,
        "mult": 2 * nPins,
    }

    fuelUZrB = Circle("fuel B", "UZr", **fuelDims2nPins)

    cladDims = {
        "Tinput": temperature,
        "Thot": temperature,
        "od": cladOD,
        "id": fuelOD,
        "mult": 2 * nPins,
    }

    clad = Circle("clad", "HT9", **cladDims)

    interDims = {
        "Tinput": temperature,
        "Thot": temperature,
        "op": 16.8,
        "ip": 16.0,
        "mult": 1.0,
    }

    interSodium = Hexagon("interCoolant", "Sodium", **interDims)

    block = blocks.HexBlock("fuel")
    block.setType("fuel")
    block.setHeight(10.0)
    if blockType == "hexUZrUTh":
        block.add(fuelUZr)
        block.add(fuelUTh)
    else:
        block.add(fuelUZrB)
    block.add(clad)
    block.add(interSodium)
    block.p.axMesh = 1
    if blockType == "hexUZrUTh":
        block.p.molesHmBOL = 1.0
    else:
        block.p.molesHmBOL = 2
    block.p.molesHmNow = 1.0

    return block


def _constructHexAssemblyFromBlockTemplate(blockTemplate: blocks.HexBlock, numBlocks: int):
    """
    Build a HexAssembly based on a template block with a specified number of blocks.

    Parameters
    ----------
    blockTemplate : armi.reactor.blocks.HexBlock
        Template block to use.
    numBlocks : int
        Number of duplcates of blockTemplate to add to the assembly.

    Returns
    -------
    assembly : armi.reactor.assembies.HexAssembly
    """
    assembly = assemblies.HexAssembly("testAssemblyType")
    assembly.spatialGrid = grids.AxialGrid.fromNCells(numBlocks)
    assembly.spatialGrid.armiObject = assembly
    for _i in range(numBlocks):
        newBlock = copy.deepcopy(blockTemplate)
        assembly.add(newBlock)
    assembly.calculateZCoords()
    assembly.reestablishBlockOrder()

    return assembly


def buildHexAssemblySingleUZrUTh():
    """Create a `HexAssembly` object with a single `hexUZr` template block (see docstring for the
    :func:`_createHexBlockTemplate` function.
    """
    blockTemplate = _createHexBlockTemplate("hexUZrUTh")
    numBlocks = 1
    return _constructHexAssemblyFromBlockTemplate(blockTemplate, numBlocks)


def buildHexAssemblySingleUZr():
    """Create a :py:class:`armi.reactor.assemblies.HexAssembly` object with a single `hexUZrUTh` template block (see
    docstring for the :func:`_createHexBlockTemplate` function.
    """
    blockTemplate = _createHexBlockTemplate("hexUZr")
    numBlocks = 1
    return _constructHexAssemblyFromBlockTemplate(blockTemplate, numBlocks)


def buildHexAssemblyFiveUZrUTh():
    """Create a :py:class:`armi.reactor.assemblies.HexAssembly` object with five `hexUZrUTh` template blocks (see
    docstring for the :func:`_createHexBlockTemplate` function.
    """
    blockTemplate = _createHexBlockTemplate("hexUZrUTh")
    numBlocks = 5
    return _constructHexAssemblyFromBlockTemplate(blockTemplate, numBlocks)


def buildHexAssemblyFourUZrUTh():
    """Create a :py:class:`armi.reactor.assemblies.HexAssembly` object with four `hexUZrUTh` template blocks (see
    docstring for the :func:`_createHexBlockTemplate` function.
    """
    blockTemplate = _createHexBlockTemplate("hexUZrUTh")
    numBlocks = 4
    return _constructHexAssemblyFromBlockTemplate(blockTemplate, numBlocks)
