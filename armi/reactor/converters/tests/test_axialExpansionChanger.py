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

"""Test axialExpansionChanger"""

import unittest
from numpy import linspace, ones

# from armi.reactor.tests.test_reactors import loadTestReactor
# from armi.tests import TEST_ROOT
from armi.reactor.assemblies import grids
from armi.reactor.assemblies import HexAssembly
from armi.reactor.blocks import HexBlock
from armi.reactor.components import DerivedShape
from armi.reactor.components.basicShapes import Circle, Hexagon
from armi.reactor.converters.axialExpansionChanger import AxialExpansionChanger


class TestExceptions(unittest.TestCase):
    """Verify exceptions are caught"""

    def setUp(self):
        self._converterSettings = {}
        self.obj = AxialExpansionChanger(self._converterSettings)
        self.a = buildTestAssemblyWithFakeMaterial()
        self.obj.setAssembly(self.a)

    def test_setExpansionFactors(self):
        with self.assertRaises(RuntimeError) as cm:
            cList = self.a.getChildren()
            percents = range(len(cList) + 1)
            self.obj.expansionData.setExpansionFactors(cList, percents)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_mapHotTempToBlockValueError(self):
        temp_grid = [5.0, 15.0, 35.0]
        temp_field = linspace(25.0, 310.0, 3)
        with self.assertRaises(ValueError) as cm:
            self.obj.mapHotTempToBlocks(temp_grid, temp_field)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_mapHotTempToBlockRuntimeError(self):
        temp_grid = [5.0, 15.0, 35.0]
        temp_field = linspace(25.0, 310.0, 10)
        with self.assertRaises(RuntimeError) as cm:
            self.obj.mapHotTempToBlocks(temp_grid, temp_field)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_AssemblyAxialExpansionException(self):
        """test that negative height exception is caught"""
        coldTemp = 25.0
        hotInletTemp = 310.0
        tempSteps = 10
        numTempGridPts = 11
        temp_grid = linspace(0.0, self.a.getTotalHeight(), numTempGridPts)
        temp_field = coldTemp * ones(numTempGridPts)
        with self.assertRaises(ArithmeticError) as cm:
            for idt in range(1, tempSteps):
                self.obj.mapHotTempToBlocks(temp_grid, temp_field)
                self.obj.expansionData.computeThermalExpansionFactors()
                self.obj.axiallyExpandAssembly()
                # increament temperature
                temp_field = (
                    coldTemp
                    + (idt + 1) / (tempSteps / 3) * temp_grid
                    + (hotInletTemp - coldTemp) * (idt + 1) / tempSteps
                )

            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_MapTempToComponent(self):
        # build single block assembly
        assembly = HexAssembly("testAssemblyType")
        assembly.spatialGrid = grids.axialUnitGrid(numCells=1)
        assembly.spatialGrid.armiObject = assembly
        # build block with unregistered flag
        b = HexBlock("noExist", 1.0)
        dims = {"Tinput": 1.0, "Thot": 1.0, "op": 1.0, "ip": 0.0, "mult": 1.0}
        dummy = Hexagon("noExist", "Sodium", **dims)
        b.add(dummy)
        b.getVolumeFractions()
        b.setType("noExist")
        # add block to assembly and run test
        assembly.add(b)
        obj = AxialExpansionChanger(self._converterSettings)
        obj.setAssembly(assembly)
        with self.assertRaises(ValueError) as cm:
            obj.expansionData.computeThermalExpansionFactors()

            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)


def buildTestAssemblyWithFakeMaterial():
    """Create test assembly consisting of list of fake material"""
    assembly = HexAssembly("testAssemblyType")
    assembly.spatialGrid = grids.axialUnitGrid(numCells=1)
    # The ArmiObject that this grid describes.
    # https://terrapower.github.io/armi/.apidocs/armi.reactor.grids.html#armi.reactor.grids.Grid
    # this feels recursive and not super clear....?
    assembly.spatialGrid.armiObject = assembly
    assembly.add(_buildTestBlock("shield"))
    assembly.add(_buildTestBlock("fuel"))
    assembly.add(_buildTestBlock("fuel"))
    assembly.add(_buildTestBlock("plenum"))
    assembly.add(_buildDummySodium())
    assembly.calculateZCoords()
    assembly.reestablishBlockOrder()
    return assembly


def _buildTestBlock(blockType):
    """Return a simple pin type block filled with coolant and surrounded by duct.

    Parameters
    ----------
    blockType : string
        determines which type of block you're building
    """
    b = HexBlock(blockType, height=10.0)

    fuelDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.76, "id": 0.00, "mult": 127.0}
    cladDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.80, "id": 0.77, "mult": 127.0}
    ductDims = {"Tinput": 25.0, "Thot": 25.0, "op": 16, "ip": 15.3, "mult": 1.0}
    intercoolantDims = {
        "Tinput": 25.0,
        "Thot": 25.0,
        "op": 17.0,
        "ip": ductDims["op"],
        "mult": 1.0,
    }
    coolDims = {"Tinput": 25.0, "Thot": 25.0}
    mainType = Circle(blockType, "FakeException", **fuelDims)
    clad = Circle("clad", "FakeException", **cladDims)
    duct = Hexagon("duct", "FakeException", **ductDims)

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


def _buildDummySodium():
    """Build a dummy sodium block.

    Parameters
    ----------
    height : float
        sets initial height of block

    Returns
    -------
    b:
        single block object containing sodium
    """
    b = HexBlock("dummy", height=10.0)

    sodiumDims = {"Tinput": 25.0, "Thot": 25.0, "op": 17, "ip": 0.0, "mult": 1.0}
    dummy = Hexagon("dummy coolant", "Sodium", **sodiumDims)

    b.add(dummy)
    b.getVolumeFractions()
    b.setType("dummy")

    return b
