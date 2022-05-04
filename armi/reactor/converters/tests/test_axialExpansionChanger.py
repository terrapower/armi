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
from armi.reactor.converters.axialExpansionChanger import (
    AxialExpansionChanger,
    ExpansionData,
)
from armi.reactor.flags import Flags
from armi import materials
from armi.utils import units

# set namespace order for materials so that fake HT9 material can be found
materials.setMaterialNamespaceOrder(
    ["armi.reactor.converters.tests.test_axialExpansionChanger", "armi.materials"]
)


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
        self.obj = AxialExpansionChanger()
        self.massAndDens = {}
        self.steelMass = []
        self.blockHeights = {}

    def _getConservationMetrics(self, a):
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
                # store mass and density of target component
                if self.obj.expansionData.isTargetComponent(c):
                    self._storeTargetComponentMassAndDensity(c)
                # store steel mass for assembly
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
        self,
        L,
        coldTemp=25.0,
        hotInletTemp=360.0,
        numTempGridPts=25,
        tempSteps=100,
        uniform=False,
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
        self._generateTempField(coldTemp, hotInletTemp, uniform)

    def _generateTempField(self, coldTemp, hotInletTemp, uniform):
        """
        generate temperature field and grid

        - all temperatures are in C
        - temperature field : temperature readings (e.g., from T/H calculation)
        - temperature grid : physical locations in which
                            temperature is measured
        """
        # Generate temp field
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
            for i in range(1, self.tempSteps):
                self.tempField[i, :] = tmp[i]


class TestAxialExpansionHeight(Base, unittest.TestCase):
    """verify that test assembly is expanded correctly"""

    def setUp(self):
        Base.setUp(self)
        self.a = buildTestAssemblyWithFakeMaterial(name="FakeMat")

        self.temp = Temperature(
            self.a.getTotalHeight(), numTempGridPts=11, tempSteps=10
        )

        # get the right/expected answer
        self._generateComponentWiseExpectedHeight()

        # do the axial expansion
        self.axialMeshLocs = zeros((self.temp.tempSteps, len(self.a)))
        for idt in range(self.temp.tempSteps):
            self.obj.performThermalAxialExpansion(
                self.a, self.temp.tempGrid, self.temp.tempField[idt, :], setFuel=True
            )
            self._getConservationMetrics(self.a)
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

    def _generateComponentWiseExpectedHeight(self):
        """calculate the expected height, external of AssemblyAxialExpansion()"""
        assem = buildTestAssemblyWithFakeMaterial(name="FakeMat")
        aveBlockTemp = zeros((len(assem), self.temp.tempSteps))
        self.trueZtop = zeros((len(assem), self.temp.tempSteps))
        self.trueHeight = zeros((len(assem), self.temp.tempSteps))
        self.trueZtop[-1, :] = assem[-1].p.ztop

        for idt in range(self.temp.tempSteps):
            # get average block temp
            for ib in range(len(assem)):
                aveBlockTemp[ib, idt] = self._getAveTemp(ib, idt, assem)
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

    def _getAveTemp(self, ib, idt, assem):
        tmpMapping = []
        for idz, z in enumerate(self.temp.tempGrid):
            if assem[ib].p.zbottom <= z <= assem[ib].p.ztop:
                tmpMapping.append(self.temp.tempField[idt][idz])
            if z > assem[ib].p.ztop:
                break

        return mean(tmpMapping)


class TestCoreExpansion(Base, unittest.TestCase):
    """verify core-based expansion changes r.core.p.axialMesh

    Notes
    -----
    - Just checks that the mesh changes after expansion.
    - Actual verification of axial expansion occurs in class TestAxialExpansionHeight
    """

    def setUp(self):
        Base.setUp(self)
        self.o, self.r = loadTestReactor(TEST_ROOT)
        self.temp = Temperature(self.r.core.refAssem.getTotalHeight())
        # populate test temperature and percent expansion data
        self.tempGrid = {}
        self.tempField = {}
        self.componentLst = {}
        self.percents = {}
        # just use self.tempField[-1], no need to use all steps in temp.tempField
        for a in self.r.core.getAssemblies(includeBolAssems=True):
            self.tempGrid[a] = self.temp.tempGrid
            self.tempField[a] = self.temp.tempField[-1]
            self.componentLst[a] = [c for b in a for c in b]
            self.percents[a] = list(0.01 * ones(len(self.componentLst[a])))

    def test_axiallyExpandCoreThermal(self):
        oldMesh = self.r.core.p.axialMesh
        self.obj.axiallyExpandCoreThermal(self.r, self.tempGrid, self.tempField)
        self.assertNotEqual(
            oldMesh,
            self.r.core.p.axialMesh,
            msg="The core mesh has not changed with the expansion. That's not right.",
        )

    def test_axiallyExpandCorePercent(self):
        oldMesh = self.r.core.p.axialMesh
        self.obj.axiallyExpandCorePercent(self.r, self.componentLst, self.percents)
        self.assertNotEqual(
            oldMesh,
            self.r.core.p.axialMesh,
            msg="The core mesh has not changed with the expansion. That's not right.",
        )


class TestConservation(Base, unittest.TestCase):
    """verify that conservation is maintained in assembly-level axial expansion"""

    def setUp(self):
        Base.setUp(self)
        self.a = buildTestAssemblyWithFakeMaterial(name="FakeMat")

        # initialize class variables for conservation checks
        self.oldMass = {}
        for b in self.a:
            self.oldMass[b.name] = 0.0

        # do the expansion and store mass and density info
        self.temp = Temperature(
            self.a.getTotalHeight(), coldTemp=1.0, hotInletTemp=1000.0
        )
        for idt in range(self.temp.tempSteps):
            self.obj.performThermalAxialExpansion(
                self.a, self.temp.tempGrid, self.temp.tempField[idt, :], setFuel=True
            )
            self._getConservationMetrics(self.a)

    def test_ExpansionContractionConservation(self):
        """expand all components and then contract back to original state

        Notes
        -----
        - uniform expansion over all components within the assembly
        - 10 total expansion steps: 5 at +1%, and 5 at -1%
        - assertion on if original axial mesh matches the final axial mesh
        """
        a = buildTestAssemblyWithFakeMaterial(name="FakeMat")
        obj = AxialExpansionChanger()
        oldMesh = a.getAxialMesh()
        componentLst = [c for b in a for c in b]
        for i in range(0, 10):
            # get the percentage change
            if i < 5:
                percents = 0.01 + zeros(len(componentLst))
            else:
                percents = -0.01 + zeros(len(componentLst))
            # set the expansion factors
            oldMasses = [c.getMass() for b in a for c in b]
            # do the expansion
            obj.performPrescribedAxialExpansion(a, componentLst, percents, setFuel=True)
            newMasses = [c.getMass() for b in a for c in b]
            for old, new in zip(oldMasses, newMasses):
                self.assertAlmostEqual(old, new)

        self.assertEqual(
            oldMesh,
            a.getAxialMesh(),
            msg="Axial mesh is not the same after the expansion and contraction!",
        )

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

    def test_NoMovementACLP(self):
        """ensures that above core load pad (ACLP) does not move during fuel-only expansion"""
        # build test assembly with ACLP
        assembly = HexAssembly("testAssemblyType")
        assembly.spatialGrid = grids.axialUnitGrid(numCells=1)
        assembly.spatialGrid.armiObject = assembly
        assembly.add(_buildTestBlock("shield", "FakeMat"))
        assembly.add(_buildTestBlock("fuel", "FakeMat"))
        assembly.add(_buildTestBlock("fuel", "FakeMat"))
        assembly.add(_buildTestBlock("plenum", "FakeMat"))
        assembly.add(_buildTestBlock("aclp", "FakeMat"))  # "aclp plenum" also works
        assembly.add(_buildTestBlock("plenum", "FakeMat"))
        assembly.add(_buildDummySodium())
        assembly.calculateZCoords()
        assembly.reestablishBlockOrder()

        # get zCoords for aclp
        aclp = assembly.getChildrenWithFlags(Flags.ACLP)[0]
        aclpZTop = aclp.p.ztop
        aclpZBottom = aclp.p.zbottom

        # expand fuel
        # get fuel components
        cList = [c for b in assembly for c in b if c.hasFlags(Flags.FUEL)]
        # 10% growth of fuel components
        pList = zeros(len(cList)) + 0.1
        chngr = AxialExpansionChanger()
        chngr.performPrescribedAxialExpansion(assembly, cList, pList, setFuel=True)

        # do assertion
        self.assertEqual(
            aclpZBottom,
            aclp.p.zbottom,
            msg="ACLP zbottom has changed. It should not with fuel component only expansion!",
        )
        self.assertEqual(
            aclpZTop,
            aclp.p.ztop,
            msg="ACLP ztop has changed. It should not with fuel component only expansion!",
        )


class TestExceptions(Base, unittest.TestCase):
    """Verify exceptions are caught"""

    def setUp(self):
        Base.setUp(self)
        self.a = buildTestAssemblyWithFakeMaterial(name="FakeMatException")
        self.obj.setAssembly(self.a)

    def test_isTopDummyBlockPresent(self):
        # build test assembly without dummy
        assembly = HexAssembly("testAssemblyType")
        assembly.spatialGrid = grids.axialUnitGrid(numCells=1)
        assembly.spatialGrid.armiObject = assembly
        assembly.add(_buildTestBlock("shield", "FakeMat"))
        assembly.calculateZCoords()
        assembly.reestablishBlockOrder()
        # create instance of expansion changer
        obj = AxialExpansionChanger(detailedAxialExpansion=True)
        with self.assertRaises(RuntimeError) as cm:
            obj.setAssembly(assembly)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_setExpansionFactors(self):
        with self.assertRaises(RuntimeError) as cm:
            cList = self.a[0].getChildren()
            percents = range(len(cList) + 1)
            self.obj.expansionData.setExpansionFactors(cList, percents)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_mapHotTempToComponentsValueError(self):
        tempGrid = [5.0, 15.0, 35.0]
        tempField = linspace(25.0, 310.0, 3)
        with self.assertRaises(ValueError) as cm:
            self.obj.expansionData.mapHotTempToComponents(tempGrid, tempField)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_mapHotTempToComponentsRuntimeError(self):
        tempGrid = [5.0, 15.0, 35.0]
        tempField = linspace(25.0, 310.0, 10)
        with self.assertRaises(RuntimeError) as cm:
            self.obj.expansionData.mapHotTempToComponents(tempGrid, tempField)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_AssemblyAxialExpansionException(self):
        """test that negative height exception is caught"""
        temp = Temperature(self.a.getTotalHeight(), numTempGridPts=11, tempSteps=10)
        with self.assertRaises(ArithmeticError) as cm:
            for idt in range(temp.tempSteps):
                self.obj.expansionData.mapHotTempToComponents(
                    temp.tempGrid, temp.tempField[idt, :]
                )
                self.obj.expansionData.computeThermalExpansionFactors()
                self.obj.axiallyExpandAssembly()

            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_specifyTargetComponentRuntimeErrorFirst(self):
        # build block for testing
        b = HexBlock("test", height=10.0)
        fuelDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.76, "id": 0.00, "mult": 127.0}
        cladDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.80, "id": 0.77, "mult": 127.0}
        mainType = Circle("main", "FakeMat", **fuelDims)
        clad = Circle("clad", "FakeMat", **cladDims)
        b.add(mainType)
        b.add(clad)
        b.setType("test")
        b.getVolumeFractions()
        # do test
        with self.assertRaises(RuntimeError) as cm:
            self.obj.expansionData.specifyTargetComponent(b)

            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_specifyTargetComponentRuntimeErrorSecond(self):
        # build block for testing
        b = HexBlock("test", height=10.0)
        fuelDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.76, "id": 0.00, "mult": 127.0}
        cladDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.80, "id": 0.77, "mult": 127.0}
        mainType = Circle("test", "FakeMat", **fuelDims)
        clad = Circle("test", "FakeMat", **cladDims)
        b.add(mainType)
        b.add(clad)
        b.setType("test")
        b.getVolumeFractions()
        # do test
        with self.assertRaises(RuntimeError) as cm:
            self.obj.expansionData.specifyTargetComponent(b)

            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_isFuelLocked(self):
        b_TwoFuel = HexBlock("fuel", height=10.0)
        fuelDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.76, "id": 0.00, "mult": 127.0}
        fuel2Dims = {
            "Tinput": 25.0,
            "Thot": 25.0,
            "od": 0.80,
            "id": 0.77,
            "mult": 127.0,
        }
        fuel = Circle("fuel", "FakeMat", **fuelDims)
        fuel2 = Circle("fuel", "FakeMat", **fuel2Dims)
        b_TwoFuel.add(fuel)
        b_TwoFuel.add(fuel2)
        b_TwoFuel.setType("test")
        expdata = ExpansionData(HexAssembly("testAssemblyType"), setFuel=True)
        # do test
        with self.assertRaises(RuntimeError) as cm:
            expdata._isFuelLocked(b_TwoFuel)  # pylint: disable=protected-access

            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

        b_NoFuel = HexBlock("fuel", height=10.0)
        shield = Circle("shield", "FakeMat", **fuelDims)
        b_NoFuel.add(shield)
        with self.assertRaises(RuntimeError) as cm:
            expdata._isFuelLocked(b_NoFuel)  # pylint: disable=protected-access

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


class FakeMat(materials.ht9.HT9):  # pylint: disable=abstract-method
    """Fake material used to verify armi.reactor.converters.axialExpansionChanger

    Notes
    -----
    - specifically used TestAxialExpansionHeight to verify axialExpansionChanger produces
      expected heights from hand calculation
    - also used to verify mass and height conservation resulting from even amounts of expansion
      and contraction. See TestConservation.
    """

    name = "FakeMat"

    def __init__(self):
        materials.ht9.HT9.__init__(self)

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """ A fake linear expansion percent"""
        Tc = units.getTc(Tc, Tk)
        return 0.02 * Tc


class FakeMatException(materials.ht9.HT9):  # pylint: disable=abstract-method
    """Fake material used to verify TestExceptions

    Notes
    -----
    - the only difference between this and `class Fake(HT9)` above is that the thermal expansion factor
      is higher to ensure that a negative block height is caught in TestExceptions:test_AssemblyAxialExpansionException.
    """

    name = "FakeMatException"

    def __init__(self):
        materials.ht9.HT9.__init__(self)

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """ A fake linear expansion percent"""
        Tc = units.getTc(Tc, Tk)
        return 0.08 * Tc
