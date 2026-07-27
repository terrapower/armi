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
Importable testing utilities for block-related machinery.

This is a very limited set of ARMI block testing tools, meant to be importable as part of the ARMI API. The goal is to
provide a small set of high quality block-related tools to help downstream ARMI developers write tests.

Notes
-----
This will not be a catch-all for random unit test functions. Be very sparing here.
"""

from armi import runLog, settings
from armi.physics.neutronics.settings import CONF_XS_KERNEL
from armi.reactor import blocks
from armi.reactor.components import Circle, DerivedShape, Helix, Hexagon
from armi.reactor.flags import Flags


def _buildSimpleFuelHexBlockHelper(linkedBond=False):
    """Returns a simple hex block containing fuel, clad, duct, and coolant, with an optional
    linked bond.

    Parameters
    ----------
    linkedBond : bool
        Whether or not to include the linked bond in the returned block.

    Returns
    -------
    b : :py:class:`armi.reactor.blocks.HexBlock`
        The simple fuel hex block.
    """
    if linkedBond:
        name = "simple-fuel-linked"
    else:
        name = "simple-fuel"
    # name was formerly "fuel"
    b = blocks.HexBlock(name, height=10.0)

    fuelDims = {"Tinput": 25.0, "Thot": 600, "od": 0.76, "id": 0.00, "mult": 127.0}
    bondDims = {
        "Tinput": 25.0,
        "Thot": 450,
        "od": "clad.id",
        "id": "fuel.od",
        "mult": 127.0,
    }
    cladDims = {"Tinput": 25.0, "Thot": 450, "od": 0.80, "id": 0.77, "mult": 127.0}
    ductDims = {"Tinput": 25.0, "Thot": 400, "op": 16, "ip": 15.3, "mult": 1.0}
    intercoolantDims = {
        "Tinput": 400,
        "Thot": 400,
        "op": 17.0,
        "ip": ductDims["op"],
        "mult": 1.0,
    }
    coolDims = {"Tinput": 25.0, "Thot": 400}

    fuel = Circle("fuel", "UZr", **fuelDims)
    clad = Circle("clad", "HT9", **cladDims)

    if linkedBond:
        bondDims["components"] = {"clad": clad, "fuel": fuel}
        bond = Circle("bond", "HT9", **bondDims)
    duct = Hexagon("duct", "HT9", **ductDims)

    coolant = DerivedShape("coolant", "Sodium", **coolDims)
    intercoolant = Hexagon("intercoolant", "Sodium", **intercoolantDims)

    b.add(fuel)
    if linkedBond:
        b.add(bond)
    b.add(clad)
    b.add(duct)
    b.add(coolant)
    b.add(intercoolant)
    return b


def buildSimpleFuelHexBlock():
    """Return a simple hex block containing fuel, clad, duct, and coolant."""
    return _buildSimpleFuelHexBlockHelper()


def buildLinkedFuelHexBlock():
    """Return a simple hex block containing containing fuel, clad, duct, linked bond, and coolant."""
    return _buildSimpleFuelHexBlockHelper(linkedBond=True)


NUM_PINS_IN_COMPLEX_HEX_BLOCK = 217


def buildComplexHexBlock(cold=True, depletable=False) -> blocks.HexBlock:
    """Build an annular hex block representing a more realistic SFR fuel pin structure, including an anulus and
    voids/gaps between fuel, liner, and cladding. Use for evaluating unit tests.

    Parameters
    ----------
    cold : bool
        Whether or not the block is cold.
    depeletable : bool
        Whether or not the block is depletable.

    Returns
    -------
    block : :py:class:`armi.reactor.blocks.HexBlock`
        Annular hex block.

    """
    from armi.testing import buildEmptyHexAssembly, getEmptyHexReactor

    caseSetting = settings.Settings()
    caseSetting[CONF_XS_KERNEL] = "MC2v2"
    runLog.setVerbosity("error")
    caseSetting["nCycles"] = 1
    r = getEmptyHexReactor()

    assemNum = 3
    # name was formerly TestHexBlock
    block = blocks.HexBlock("ComplexHexBlock")
    block.setType("defaultType")
    block.p.nPins = NUM_PINS_IN_COMPLEX_HEX_BLOCK
    assembly = buildEmptyHexAssembly(assemNum, 1, r=r)

    # NOTE: temperatures are supposed to be in C
    coldTemp = 25.0
    hotTempCoolant = 430.0
    hotTempStructure = 25.0 if cold else hotTempCoolant
    hotTempFuel = 25.0 if cold else 600.0

    fuelDims = {
        "Tinput": coldTemp,
        "Thot": hotTempFuel,
        "od": 0.84,
        "id": 0.6,
        "mult": NUM_PINS_IN_COMPLEX_HEX_BLOCK,
    }
    fuel = Circle("fuel", "UZr", **fuelDims)
    if depletable:
        fuel.p.flags = Flags.fromString("fuel depletable")

    bondDims = {
        "Tinput": coldTemp,
        "Thot": hotTempCoolant,
        "od": "fuel.id",
        "id": 0.3,
        "mult": NUM_PINS_IN_COMPLEX_HEX_BLOCK,
    }
    bondDims["components"] = {"fuel": fuel}
    bond = Circle("bond", "Sodium", **bondDims)

    annularVoidDims = {
        "Tinput": hotTempStructure,
        "Thot": hotTempStructure,
        "od": "bond.id",
        "id": 0.0,
        "mult": NUM_PINS_IN_COMPLEX_HEX_BLOCK,
    }
    annularVoidDims["components"] = {"bond": bond}
    annularVoid = Circle("annular void", "Void", **annularVoidDims)

    innerLinerDims = {
        "Tinput": coldTemp,
        "Thot": hotTempStructure,
        "od": 0.90,
        "id": 0.85,
        "mult": NUM_PINS_IN_COMPLEX_HEX_BLOCK,
    }
    innerLiner = Circle("inner liner", "Graphite", **innerLinerDims)

    fuelLinerGapDims = {
        "Tinput": hotTempStructure,
        "Thot": hotTempStructure,
        "od": "inner liner.id",
        "id": "fuel.od",
        "mult": NUM_PINS_IN_COMPLEX_HEX_BLOCK,
    }
    fuelLinerGapDims["components"] = {"inner liner": innerLiner, "fuel": fuel}
    fuelLinerGap = Circle("gap1", "Void", **fuelLinerGapDims)

    outerLinerDims = {
        "Tinput": coldTemp,
        "Thot": hotTempStructure,
        "od": 0.95,
        "id": 0.90,
        "mult": NUM_PINS_IN_COMPLEX_HEX_BLOCK,
    }
    outerLiner = Circle("outer liner", "HT9", **outerLinerDims)

    linerLinerGapDims = {
        "Tinput": hotTempStructure,
        "Thot": hotTempStructure,
        "od": "outer liner.id",
        "id": "inner liner.od",
        "mult": NUM_PINS_IN_COMPLEX_HEX_BLOCK,
    }
    linerLinerGapDims["components"] = {
        "outer liner": outerLiner,
        "inner liner": innerLiner,
    }
    linerLinerGap = Circle("gap2", "Void", **linerLinerGapDims)

    claddingDims = {
        "Tinput": coldTemp,
        "Thot": hotTempStructure,
        "od": 1.05,
        "id": 0.95,
        "mult": NUM_PINS_IN_COMPLEX_HEX_BLOCK,
    }
    cladding = Circle("clad", "HT9", **claddingDims)
    if depletable:
        cladding.p.flags = Flags.fromString("clad depletable")

    linerCladGapDims = {
        "Tinput": hotTempStructure,
        "Thot": hotTempStructure,
        "od": "clad.id",
        "id": "outer liner.od",
        "mult": NUM_PINS_IN_COMPLEX_HEX_BLOCK,
    }
    linerCladGapDims["components"] = {"clad": cladding, "outer liner": outerLiner}
    linerCladGap = Circle("gap3", "Void", **linerCladGapDims)

    wireDims = {
        "Tinput": coldTemp,
        "Thot": hotTempStructure,
        "od": 0.1,
        "id": 0.0,
        "axialPitch": 30.0,
        "helixDiameter": 1.1,
        "mult": NUM_PINS_IN_COMPLEX_HEX_BLOCK,
    }
    wire = Helix("wire", "HT9", **wireDims)
    if depletable:
        wire.p.flags = Flags.fromString("wire depletable")

    coolantDims = {"Tinput": hotTempCoolant, "Thot": hotTempCoolant}
    coolant = DerivedShape("coolant", "Sodium", **coolantDims)

    ductDims = {
        "Tinput": coldTemp,
        "Thot": hotTempStructure,
        "ip": 16.6,
        "op": 17.3,
        "mult": 1,
    }
    duct = Hexagon("duct", "HT9", **ductDims)
    if depletable:
        duct.p.flags = Flags.fromString("duct depletable")

    interDims = {
        "Tinput": hotTempCoolant,
        "Thot": hotTempCoolant,
        "op": 17.8,
        "ip": "duct.op",
        "mult": 1,
    }
    interDims["components"] = {"duct": duct}
    interSodium = Hexagon("interCoolant", "Sodium", **interDims)

    block.add(annularVoid)
    block.add(bond)
    block.add(fuel)
    block.add(fuelLinerGap)
    block.add(innerLiner)
    block.add(linerLinerGap)
    block.add(outerLiner)
    block.add(linerCladGap)
    block.add(cladding)

    block.add(wire)
    block.add(coolant)
    block.add(duct)
    block.add(interSodium)

    block.setHeight(16.0)

    block.autoCreateSpatialGrids(r.core.spatialGrid)
    assembly.add(block)
    r.core.add(assembly)
    return block


def applyDummyData(block):
    """Add some dummy data to a block for physics-like tests."""
    from armi.nuclearDataIO.cccc import isotxs
    from armi.tests import ISOAA_PATH

    # typical SFR-ish flux in 1/cm^2/s
    flux = [
        161720716762.12997,
        2288219224332.647,
        11068159130271.139,
        26473095948525.742,
        45590249703180.945,
        78780459664094.23,
        143729928505629.06,
        224219073208464.06,
        229677567456769.22,
        267303906113313.16,
        220996878365852.22,
        169895433093246.28,
        126750484612975.31,
        143215138794766.53,
        74813432842005.5,
        32130372366225.85,
        21556243034771.582,
        6297567411518.368,
        22365198294698.45,
        12211256796917.86,
        5236367197121.363,
        1490736020048.7847,
        1369603135573.731,
        285579041041.55945,
        73955783965.98692,
        55003146502.73623,
        18564831886.20426,
        4955747691.052108,
        3584030491.076041,
        884015567.3986057,
        4298964991.043116,
        1348809158.0353086,
        601494405.293505,
    ]
    xslib = isotxs.readBinary(ISOAA_PATH)
    # Slight hack here because the test block was created by hand rather than via blueprints and so
    # elemental expansion of isotopics did not occur. But, the ISOTXS library being used did go
    # through an isotopic expansion, so we map nuclides here.
    xslib._nuclides["NAAA"] = xslib._nuclides["NA23AA"]
    xslib._nuclides["WAA"] = xslib._nuclides["W184AA"]
    xslib._nuclides["MNAA"] = xslib._nuclides["MN55AA"]
    block.p.mgFlux = flux
    block.core.lib = xslib
