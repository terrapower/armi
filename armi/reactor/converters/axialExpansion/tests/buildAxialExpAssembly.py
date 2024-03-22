# Copyright 2023 TerraPower, LLC
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

from armi import materials
from armi.utils import units
from armi.reactor.assemblies import HexAssembly, grids
from armi.reactor.blocks import HexBlock
from armi.reactor.components.basicShapes import Circle, Hexagon
from armi.reactor.components import DerivedShape


def buildTestAssembly(materialName: str, hot: bool = False):
    """Create test assembly.

    Parameters
    ----------
    materialName: string
        determines which material to use
    hot: boolean
        determines if assembly should be at hot temperatures
    """
    if not hot:
        hotTemp = 25.0
        height = 10.0
    else:
        hotTemp = 250.0
        height = 10.0 + 0.02 * (250.0 - 25.0)

    assembly = HexAssembly("testAssemblyType")
    assembly.spatialGrid = grids.axialUnitGrid(numCells=1)
    assembly.spatialGrid.armiObject = assembly
    assembly.add(buildTestBlock("shield", materialName, hotTemp, height))
    assembly.add(buildTestBlock("fuel", materialName, hotTemp, height))
    assembly.add(buildTestBlock("fuel", materialName, hotTemp, height))
    assembly.add(buildTestBlock("plenum", materialName, hotTemp, height))
    assembly.add(buildDummySodium(hotTemp, height))
    assembly.calculateZCoords()
    assembly.reestablishBlockOrder()
    return assembly


def buildTestBlock(blockType: str, materialName: str, hotTemp: float, height: float):
    """Return a simple pin type block filled with coolant and surrounded by duct.

    Parameters
    ----------
    blockType : string
        determines which type of block you're building
    materialName : string
        determines which material to use
    """
    b = HexBlock(blockType, height=height)

    fuelDims = {"Tinput": 25.0, "Thot": hotTemp, "od": 0.76, "id": 0.00, "mult": 127.0}
    cladDims = {"Tinput": 25.0, "Thot": hotTemp, "od": 0.80, "id": 0.77, "mult": 127.0}
    ductDims = {"Tinput": 25.0, "Thot": hotTemp, "op": 16, "ip": 15.3, "mult": 1.0}
    intercoolantDims = {
        "Tinput": 25.0,
        "Thot": hotTemp,
        "op": 17.0,
        "ip": ductDims["op"],
        "mult": 1.0,
    }
    coolDims = {"Tinput": 25.0, "Thot": hotTemp}
    mainType = Circle(blockType, materialName, **fuelDims)
    clad = Circle("clad", materialName, **cladDims)
    duct = Hexagon("duct", materialName, **ductDims)

    coolant = DerivedShape("coolant", "Sodium", **coolDims)
    intercoolant = Hexagon("intercoolant", "Sodium", **intercoolantDims)

    b.add(mainType)
    b.add(clad)
    b.add(duct)
    b.add(coolant)
    b.add(intercoolant)
    b.setType(blockType)

    b.getVolumeFractions()

    return b


def buildDummySodium(hotTemp: float, height: float):
    """Build a dummy sodium block."""
    b = HexBlock("dummy", height=height)

    sodiumDims = {"Tinput": 25.0, "Thot": hotTemp, "op": 17, "ip": 0.0, "mult": 1.0}
    dummy = Hexagon("dummy coolant", "Sodium", **sodiumDims)

    b.add(dummy)
    b.getVolumeFractions()
    b.setType("dummy")

    return b


class FakeMat(materials.ht9.HT9):
    """Fake material used to verify armi.reactor.converters.axialExpansionChanger.

    Notes
    -----
    - specifically used in TestAxialExpansionHeight to verify axialExpansionChanger produces
      expected heights from hand calculation
    - also used to verify mass and height conservation resulting from even amounts of expansion
      and contraction. See TestConservation.
    """

    name = "FakeMat"

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """A fake linear expansion percent."""
        Tc = units.getTc(Tc, Tk)
        return 0.02 * Tc


class FakeMatException(FakeMat):
    """Fake material used to verify TestExceptions.

    Notes
    -----
    - higher thermal expansion factor to ensure that a negative block height
      is caught in TestExceptions:test_AssemblyAxialExpansionException.
    """

    name = "FakeMatException"

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """A fake linear expansion percent."""
        Tc = units.getTc(Tc, Tk)
        return 0.08 * Tc
