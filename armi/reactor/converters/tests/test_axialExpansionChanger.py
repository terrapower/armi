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

from statistics import mean
import unittest
from numpy import linspace, ones, array, vstack, zeros
from armi.reactor.tests.test_reactors import loadTestReactor
from armi.tests import TEST_ROOT
from armi.reactor.assemblies import grids
from armi.reactor.assemblies import HexAssembly
from armi.reactor.blocks import HexBlock
from armi.reactor.components import DerivedShape
from armi.reactor.components.basicShapes import Circle, Hexagon
from armi.reactor.converters.axialExpansionChanger import AxialExpansionChanger
from armi.reactor.flags import Flags

class Base(unittest.TestCase):
    """common methods and variables for unit tests"""

    Steel_Component_Lst = [
        Flags.DUCT,
        Flags.GRID_PLATE,
        Flags.HANDLING_SOCKET,
        Flags.INLET_NOZZLE,
        Flags.CLAD,
        Flags.WIRE,
        Flags.ACLP,
        Flags.GUIDE_TUBE,
    ]

    def setUp(self):
        self._converterSettings = {}
        self.obj = AxialExpansionChanger(self._converterSettings)
        self.massAndDens = {}
        self.steelMass = []
        self.blockHeights = {}
    
    def getConservationMetrics(self, a):
        """retrieves and stores various conservation metrics

        - useful for verification and unittesting
        - Finds and stores:
            1. mass and density of target components
            2. mass of assembly steel
            3. block heights
        """
        mass = 0.0
        for b in a:
            for c in b:
                ## store mass and density of target component
                if self.obj.expansionData.isTargetComponent(c):
                    self._storeTargetComponentMassAndDensity(c)
                ## store steel mass for assembly
                if c.p.flags in self.Steel_Component_Lst:
                    mass += c.getMass()

            # store block heights
            tmp = array([b.p.zbottom, b.p.ztop, b.p.height, b.getVolume()])
            if b.name not in self.blockHeights:
                self.blockHeights[b.name] = tmp
            else:
                self.blockHeights[b.name] = vstack((self.blockHeights[b.name], tmp))

        self.steelMass.append(mass)
    
    def _storeTargetComponentMassAndDensity(self, c):
        tmp = array(
            [
                c.getMass(),
                c.material.getProperty("density", c.temperatureInK),
            ]
        )
        if c.parent.name not in self.massAndDens:
            self.massAndDens[c.parent.name] = tmp
        else:
            self.massAndDens[c.parent.name] = vstack(
                (self.massAndDens[c.parent.name], tmp)
            )

class Temperature:
    """create and store temperature grid/field"""

    def __init__(
        self, L, coldTemp=25.0, hotInletTemp=360.0, numTempGridPts=25, tempSteps=100, uniform=False,
    ):
        """
        Parameters
        ----------
        L : float
            length of self.tempGrid. Should be the height of the corresponding assembly.
        coldTemp : float
            component as-built temperature
        hotInletTemp : float
            temperature closest to bottom of assembly. Interpreted as
            inlet temp at nominal operations.
        numTempGridPts : integer
            the number of temperature measurement locations along the
            z-axis of the assembly
        tempSteps : integer
            the number of temperatures to create (analogous to time steps)
        """
        self.tempSteps = tempSteps
        self.tempGrid = linspace(0.0, L, num=numTempGridPts)
        self.tempField = zeros((tempSteps, numTempGridPts))
        self.generateTempField(coldTemp, hotInletTemp, uniform)

    def generateTempField(self, coldTemp, hotInletTemp, uniform):
        """
        generate temperature field and grid

        - all temperatures are in C
        - temperature field : temperature readings (e.g., from T/H calculation)
        - temperature grid : physical locations in which
                            temperature is measured
        """
        ## Generate temp field
        self.tempField[0, :] = coldTemp
        if not uniform:
            for i in range(1, self.tempSteps):
                self.tempField[i, :] = (
                    coldTemp
                    + (i + 1) / (self.tempSteps / 3) * self.tempGrid
                    + (hotInletTemp - coldTemp) * (i + 1) / self.tempSteps
                )
        else:
            tmp = linspace(coldTemp, hotInletTemp, self.tempSteps)
            for i in range(1,self.tempSteps):
                self.tempField[i, :] = tmp[i]

class TestAxialExpansionHeight(Base,unittest.TestCase):
    """verify that test assembly is expanded correctly"""

    def setUp(self):
        Base.setUp(self)
        self.a = buildTestAssemblyWithFakeMaterial(name='Fake')
        self.obj.setAssembly(self.a)

        self.temp = Temperature(
            self.a.getTotalHeight(), numTempGridPts=11, tempSteps=10
        )

        # get the right/expected answer
        self.generateComponentWiseExpectedHeight()

        # do the axial expansion
        self.axialMeshLocs = zeros((self.temp.tempSteps, len(self.a)))
        for idt in range(self.temp.tempSteps):
            self.obj.mapHotTempToBlocks(self.temp.tempGrid, self.temp.tempField[idt,:])
            self.obj.expansionData.computeThermalExpansionFactors()
            self.obj.axiallyExpandAssembly()
            self.getConservationMetrics(self.a)
            self.axialMeshLocs[idt, :] = self.a.getAxialMesh()

    def test_AssemblyAxialExpansionHeight(self):
        """test the axial expansion gives correct heights for component-based expansion"""
        for idt in range(self.temp.tempSteps):
            for ib, b in enumerate(self.a):
                self.assertAlmostEqual(
                    self.trueZtop[ib, idt],
                    self.blockHeights[b.name][idt][1],
                    places=7,
                    msg="Block height is not correct.\
                         Temp Step = {0:d}, Block ID = {1:}.".format(
                        idt, b.name
                    ),
                )

    def test_AxialMesh(self):
        """test that mesh aligns with block tops for component-based expansion"""
        for idt in range(self.temp.tempSteps):
            for ib, b in enumerate(self.a):
                self.assertEqual(
                    self.axialMeshLocs[idt][ib],
                    self.blockHeights[b.name][idt][1],
                    msg="\
                        Axial mesh and block top do not align and invalidate the axial mesh.\
                        Block ID = {0:s},\n\
                            Top = {1:.12e}\n\
                        Mesh Loc = {2:.12e}".format(
                        str(b.name),
                        self.blockHeights[b.name][idt][1],
                        self.axialMeshLocs[idt][ib],
                    ),
                )

    def generateComponentWiseExpectedHeight(self):
        """calculate the expected height, external of AssemblyAxialExpansion()"""
        assem = buildTestAssemblyWithFakeMaterial(name="Fake")
        aveBlockTemp = zeros((len(assem), self.temp.tempSteps))
        self.trueZtop = zeros((len(assem), self.temp.tempSteps))
        self.trueHeight = zeros((len(assem), self.temp.tempSteps))
        self.trueZtop[-1, :] = assem[-1].p.ztop

        for idt in range(self.temp.tempSteps):
            # get average block temp
            for ib in range(len(assem)):
                aveBlockTemp[ib, idt] = self.getAveTemp(ib, idt, assem)
            # get block ztops
            for ib, b in enumerate(assem[:-1]):
                if ib > 0:
                    b.p.zbottom = assem[ib - 1].p.ztop
                if idt > 0:
                    dll = (
                        0.02 * aveBlockTemp[ib, idt] - 0.02 * aveBlockTemp[ib, idt - 1]
                    ) / (100.0 + 0.02 * aveBlockTemp[ib, idt - 1])
                    thermExpansionFactor = 1.0 + dll
                    b.p.ztop = thermExpansionFactor * b.p.height + b.p.zbottom
                self.trueZtop[ib, idt] = b.p.ztop
            # get block heights
            for ib, b in enumerate(assem):
                b.p.height = b.p.ztop - b.p.zbottom
                self.trueHeight[ib, idt] = b.p.height

    def getAveTemp(self, ib, idt, assem):
        tmpMapping = []
        for idz, z in enumerate(self.temp.tempGrid):
            if assem[ib].p.zbottom <= z <= assem[ib].p.ztop:
                tmpMapping.append(self.temp.tempField[idt][idz])
            if z > assem[ib].p.ztop:
                break

        return mean(tmpMapping)

class TestConservation(Base, unittest.TestCase):
    """verify that conservation is maintained in assembly-level axial expansion"""

    def setUp(self):
        Base.setUp(self)
        self.o, self.r = loadTestReactor(TEST_ROOT)
        self.a = self.r.core.refAssem
        self.obj.setAssembly(self.a)

        # initialize class variables for conservation checks
        self.oldMass = {}
        for b in self.a:
            self.oldMass[b.name] = 0.0

        # do the expansion and store mass and density info
        self.temp = Temperature(
            self.a.getTotalHeight(), coldTemp=1.0, hotInletTemp=1000.0
        )
        for idt in range(self.temp.tempSteps):
            self.obj.mapHotTempToBlocks(self.temp.tempGrid, self.temp.tempField[idt,:])
            self.obj.expansionData.computeThermalExpansionFactors()
            self.obj.axiallyExpandAssembly()
            self.getConservationMetrics(self.a)

    def test_TargetComponentMassConservation(self):
        """tests mass conservation for target components"""
        for idt in range(self.temp.tempSteps):
            for b in self.a[:-1]:  # skip the dummy sodium block
                if idt != 0:
                    self.assertAlmostEqual(
                        self.oldMass[b.name],
                        self.massAndDens[b.name][idt][0],
                        places=7,
                        msg="Conservation of Mass Failed on time step {0:d}, block name {1:s},\
                            with old mass {2:.7e}, and new mass {3:.7e}.".format(
                            idt,
                            b.name,
                            self.oldMass[b.name],
                            self.massAndDens[b.name][idt][0],
                        ),
                    )
                self.oldMass[b.name] = self.massAndDens[b.name][idt][0]

    def test_SteelConservation(self):
        """tests mass conservation for total assembly steel

        Component list defined by, Steel_Component_List, in GetSteelMass()
        """
        for idt in range(self.temp.tempSteps - 1):
            self.assertAlmostEqual(
                self.steelMass[idt],
                self.steelMass[idt + 1],
                places=7,
                msg="Conservation of steel mass failed on time step {0:d}".format(idt),
            )


class TestExceptions(Base, unittest.TestCase):
    """Verify exceptions are caught"""

    def setUp(self):
        Base.setUp(self)
        self.a = buildTestAssemblyWithFakeMaterial(name='FakeException')
        self.obj.setAssembly(self.a)

    def test_setExpansionFactors(self):
        with self.assertRaises(RuntimeError) as cm:
            cList = self.a.getChildren()
            percents = range(len(cList) + 1)
            self.obj.expansionData.setExpansionFactors(cList, percents)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_mapHotTempToBlockValueError(self):
        tempGrid = [5.0, 15.0, 35.0]
        tempField = linspace(25.0, 310.0, 3)
        with self.assertRaises(ValueError) as cm:
            self.obj.mapHotTempToBlocks(tempGrid, tempField)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_mapHotTempToBlockRuntimeError(self):
        tempGrid = [5.0, 15.0, 35.0]
        tempField = linspace(25.0, 310.0, 10)
        with self.assertRaises(RuntimeError) as cm:
            self.obj.mapHotTempToBlocks(tempGrid, tempField)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_AssemblyAxialExpansionException(self):
        """test that negative height exception is caught"""
        coldTemp = 25.0
        hotInletTemp = 310.0
        tempSteps = 10
        numTempGridPts = 11
        tempGrid = linspace(0.0, self.a.getTotalHeight(), numTempGridPts)
        tempField = coldTemp * ones(numTempGridPts)
        with self.assertRaises(ArithmeticError) as cm:
            for idt in range(1, tempSteps):
                self.obj.mapHotTempToBlocks(tempGrid, tempField)
                self.obj.expansionData.computeThermalExpansionFactors()
                self.obj.axiallyExpandAssembly()
                # increment temperature
                tempField = (
                    coldTemp
                    + (idt + 1) / (tempSteps / 3) * tempGrid
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


def buildTestAssemblyWithFakeMaterial(name):
    """Create test assembly consisting of list of fake material
    
    Parameters
    ----------
    name : string
        determines which fake material to use
    """
    assembly = HexAssembly("testAssemblyType")
    assembly.spatialGrid = grids.axialUnitGrid(numCells=1)
    # The ArmiObject that this grid describes.
    # https://terrapower.github.io/armi/.apidocs/armi.reactor.grids.html#armi.reactor.grids.Grid
    # this feels recursive and not super clear....?
    assembly.spatialGrid.armiObject = assembly
    assembly.add(_buildTestBlock("shield", name))
    assembly.add(_buildTestBlock("fuel", name))
    assembly.add(_buildTestBlock("fuel", name))
    assembly.add(_buildTestBlock("plenum", name))
    assembly.add(_buildDummySodium())
    assembly.calculateZCoords()
    assembly.reestablishBlockOrder()
    return assembly


def _buildTestBlock(blockType, name):
    """Return a simple pin type block filled with coolant and surrounded by duct.

    Parameters
    ----------
    blockType : string
        determines which type of block you're building

    name : string
        determines which fake material to use
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
    mainType = Circle(blockType, name, **fuelDims)
    clad = Circle("clad", name, **cladDims)
    duct = Hexagon("duct", name, **ductDims)

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
    """Build a dummy sodium block."""
    b = HexBlock("dummy", height=10.0)

    sodiumDims = {"Tinput": 25.0, "Thot": 25.0, "op": 17, "ip": 0.0, "mult": 1.0}
    dummy = Hexagon("dummy coolant", "Sodium", **sodiumDims)

    b.add(dummy)
    b.getVolumeFractions()
    b.setType("dummy")

    return b
