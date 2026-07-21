# Copyright 2026 TerraPower, LLC
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

from armi import settings
from armi.reactor import assemblies, blocks, grids
from armi.reactor.assemblies import copy
from armi.reactor.components import Circle, Hexagon


def _createHexBlockTemplate(blockType: str):
    """
    This builds a simple :class:`armi.reactor.blocks.HexBlock` object.

    The HexBlock object has the following dimensions:
        - 200 pins with an OD of 1.0
        - isothermal (flat) temperature gradient
        - cladding OD of 1.0
        - embedded in a sodium matrix

    There are two options for the HexBlock:
        'hexUZr': A HexBlock filled with all UZr pins.
        'hexUZrUTh': A HexBlock filled with half UZr pins and half UTh pins

    Parameters
    ----------
    blockType : str
        {'hexUZr', 'hexUZrUTh'}

    Returns
    -------
    block : armi.reactor.blocks.HexBlock
        A block object with half UZr pins and half UTh pins.
    block2 : armi.reactor.blocks.HexBlock
        A HexBlock object with all UZr pins.
    """
    if blockType not in ["hexUZr", "hexUZrUTh"]:
        raise ValueError(
            f"Invalid blockType for _createHexBlockTemplate: {blockType}only 'hexUZr' and 'hexUZrUTh' are allowed"
        )
    settings.Settings()

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
        block.p.molesHmBOL = 1.0
    else:
        block.add(fuelUZrB)
        block.p.molesHmBOL = 2
    block.add(clad)
    block.add(interSodium)
    block.p.axMesh = 1
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


def buildHexAssemblySingleUZr():
    """Create a :class:`armi.reactor.assemblies.HexAssembly` object with a single `hexUZr` template block (see
    docstring for the :func:`_createHexBlockTemplate` function.
    """
    blockTemplate = _createHexBlockTemplate("hexUZr")
    numBlocks = 1
    return _constructHexAssemblyFromBlockTemplate(blockTemplate, numBlocks)


def buildHexAssemblySingleUZrUTh():
    """Create a :class:`armi.reactor.assemblies.HexAssembly` object with a single `hexUZrUTh` template block (see
    docstring for the :func:`_createHexBlockTemplate` function.
    """
    blockTemplate = _createHexBlockTemplate("hexUZrUTh")
    numBlocks = 1
    return _constructHexAssemblyFromBlockTemplate(blockTemplate, numBlocks)


def buildHexAssemblyFiveUZr():
    """Create a :class:`armi.reactor.assemblies.HexAssembly` object with five `hexUZrUTh` template blocks (see
    docstring for the :func:`_createHexBlockTemplate` function.
    """
    blockTemplate = _createHexBlockTemplate("hexUZr")
    numBlocks = 5
    return _constructHexAssemblyFromBlockTemplate(blockTemplate, numBlocks)


def buildHexAssemblyFourUZr():
    """Create a :class:`armi.reactor.assemblies.HexAssembly` object with four `hexUZrUTh` template blocks (see
    docstring for the :func:`_createHexBlockTemplate` function.
    """
    blockTemplate = _createHexBlockTemplate("hexUZr")
    numBlocks = 4
    return _constructHexAssemblyFromBlockTemplate(blockTemplate, numBlocks)
