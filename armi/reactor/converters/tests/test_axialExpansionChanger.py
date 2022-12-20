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
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
from statistics import mean
import os
import unittest

from numpy import linspace, array, vstack, zeros

from armi.materials import material
from armi.reactor.assemblies import grids
from armi.reactor.assemblies import HexAssembly
from armi.reactor.blocks import HexBlock
from armi.reactor.components import DerivedShape, UnshapedComponent
from armi.reactor.tests.test_reactors import loadTestReactor, reduceTestReactorRings
from armi.tests import TEST_ROOT
from armi.reactor.components.basicShapes import (
    Circle,
    Hexagon,
    Rectangle,
)
from armi.reactor.components.complexShapes import Helix
from armi.reactor.converters.axialExpansionChanger import (
    AxialExpansionChanger,
    ExpansionData,
    _determineLinked,
)
from armi import materials
from armi.materials import custom
from armi.reactor.flags import Flags
from armi.tests import mockRunLogs
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


class TestConservation(Base, unittest.TestCase):
    """verify that conservation is maintained in assembly-level axial expansion"""

    def setUp(self):
        Base.setUp(self)
        self.a = buildTestAssemblyWithFakeMaterial(name="FakeMat")

    def expandAssemForMassConservationTest(self):
        """initialize class variables for mass conservation checks"""
        # pylint: disable=attribute-defined-outside-init
        self.oldMass = {}
        for b in self.a:
            self.oldMass[b.name] = 0.0

        # do the expansion and store mass and density info
        self.temp = Temperature(
            self.a.getTotalHeight(), coldTemp=1.0, hotInletTemp=1000.0
        )
        for idt in range(self.temp.tempSteps):
            self.obj.performThermalAxialExpansion(
                self.a,
                self.temp.tempGrid,
                self.temp.tempField[idt, :],
                setFuel=True,
                updateNDensForRadialExp=False,
            )
            self._getConservationMetrics(self.a)

    def test_ColdThermalExpansionContractionConservation(self):
        """thermally expand and then contract to ensure original state is recovered

        Notes:
        - temperature field is isothermal and initially at 25 C
        """
        isothermalTempList = [20.0, 25.0, 30.0]
        a = buildTestAssemblyWithFakeMaterial(name="FakeMat")
        originalMesh = a.getAxialMesh()
        axialExpChngr = AxialExpansionChanger(detailedAxialExpansion=True)

        tempGrid = linspace(0.0, a.getHeight())
        for temp in isothermalTempList:
            # Set hot isothermal temp and expand
            tempField = array([temp] * len(tempGrid))
            axialExpChngr.performThermalAxialExpansion(
                a, tempGrid, tempField, updateNDensForRadialExp=False
            )
            if temp == 25.0:
                for new, old in zip(
                    a.getAxialMesh()[:-1], originalMesh[:-1]
                ):  # skip dummy block
                    self.assertAlmostEqual(
                        new,
                        old,
                        msg="At original temp (250 C) block height is {0:.5f}. "
                        "Current temp is {1:.5f} and block height is {2:.5f}".format(
                            old, temp, new
                        ),
                        places=3,
                    )
            else:
                for new, old in zip(
                    a.getAxialMesh()[:-1], originalMesh[:-1]
                ):  # skip dummy block
                    self.assertNotEqual(
                        new,
                        old,
                        msg="At original temp (250 C) block height is {0:.5f}. "
                        "Current temp is {1:.5f} and block height is {2:.5f}".format(
                            old, temp, new
                        ),
                    )

    def test_HotThermalExpansionContractionConservation(self):
        """thermally expand and then contract to ensure original state is recovered

        Notes:
        - temperature field is isothermal and initially at 250 C
        """
        isothermalTempList = [200.0, 250.0, 300.0]
        a = buildTestAssemblyWithFakeMaterial(name="FakeMat", hot=True)
        originalMesh = a.getAxialMesh()
        axialExpChngr = AxialExpansionChanger(detailedAxialExpansion=True)

        tempGrid = linspace(0.0, a.getHeight())
        for temp in isothermalTempList:
            # Set hot isothermal temp and expand
            tempField = array([temp] * len(tempGrid))
            axialExpChngr.performThermalAxialExpansion(
                a, tempGrid, tempField, updateNDensForRadialExp=False
            )
            if temp == 250.0:
                for new, old in zip(
                    a.getAxialMesh()[:-1], originalMesh[:-1]
                ):  # skip dummy block
                    self.assertAlmostEqual(
                        new,
                        old,
                        msg="At original temp (250 C) block height is {0:.5f}. "
                        "Current temp is {1:.5f} and block height is {2:.5f}".format(
                            old, temp, new
                        ),
                        places=1,
                    )
            else:
                for new, old in zip(
                    a.getAxialMesh()[:-1], originalMesh[:-1]
                ):  # skip dummy block
                    self.assertNotEqual(
                        new,
                        old,
                        msg="At original temp (250 C) block height is {0:.5f}. "
                        "Current temp is {1:.5f} and block height is {2:.5f}".format(
                            old, temp, new
                        ),
                    )

    def test_PrescribedExpansionContractionConservation(self):
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
            oldMasses = [
                c.getMass()
                for b in a
                for c in b
                if not isinstance(c.material, material.Fluid)
            ]
            # do the expansion
            obj.performPrescribedAxialExpansion(a, componentLst, percents, setFuel=True)
            newMasses = [
                c.getMass()
                for b in a
                for c in b
                if not isinstance(c.material, material.Fluid)
            ]
            for old, new in zip(oldMasses, newMasses):
                self.assertAlmostEqual(old, new)

        self.assertEqual(
            oldMesh,
            a.getAxialMesh(),
            msg="Axial mesh is not the same after the expansion and contraction!",
        )

    def test_TargetComponentMassConservation(self):
        """tests mass conservation for target components"""
        self.expandAssemForMassConservationTest()
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
        self.expandAssemForMassConservationTest()
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
        assembly.add(_buildTestBlock("shield", "FakeMat", 25.0, 10.0))
        assembly.add(_buildTestBlock("fuel", "FakeMat", 25.0, 10.0))
        assembly.add(_buildTestBlock("fuel", "FakeMat", 25.0, 10.0))
        assembly.add(_buildTestBlock("plenum", "FakeMat", 25.0, 10.0))
        assembly.add(
            _buildTestBlock("aclp", "FakeMat", 25.0, 10.0)
        )  # "aclp plenum" also works
        assembly.add(_buildTestBlock("plenum", "FakeMat", 25.0, 10.0))
        assembly.add(_buildDummySodium(25.0, 10.0))
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

    def test_reset(self):
        self.obj.setAssembly(self.a)
        self.obj.reset()
        self.assertIsNone(self.obj.linked)
        self.assertIsNone(self.obj.expansionData)

    def test_computeThermalExpansionFactors(self):
        """ensure expansion factors are as expected"""
        self.obj.setAssembly(self.a)
        stdThermExpFactor = {}
        newTemp = 500.0
        # apply new temp to the pin and clad components of each block
        for b in self.a:
            for c in b[0:2]:
                stdThermExpFactor[c] = c.getThermalExpansionFactor() - 1.0
                self.obj.expansionData.updateComponentTemp(b, c, newTemp)

        self.obj.expansionData.computeThermalExpansionFactors()

        # skip dummy block, it's just coolant and doesn't expand.
        for b in self.a[:-1]:
            for ic, c in enumerate(b):
                if ic <= 1:
                    self.assertNotEqual(
                        stdThermExpFactor[c],
                        self.obj.expansionData.getExpansionFactor(c),
                        msg=f"Block {b}, Component {c}, thermExpCoeff not right.\n",
                    )
                else:
                    self.assertEqual(
                        self.obj.expansionData.getExpansionFactor(c),
                        0.0,
                        msg=f"Block {b}, Component {c}, thermExpCoeff not right.\n",
                    )


class TestManageCoreMesh(unittest.TestCase):
    """verify that manage core mesh unifies the mesh for detailedAxialExpansion: False"""

    def setUp(self):
        self.axialExpChngr = AxialExpansionChanger()
        o, self.r = loadTestReactor(TEST_ROOT)
        reduceTestReactorRings(self.r, o.cs, 3)

        self.oldAxialMesh = self.r.core.p.axialMesh
        # expand refAssem by 10%
        componentLst = [c for b in self.r.core.refAssem for c in b]
        percents = 0.01 + zeros(len(componentLst))
        self.axialExpChngr.performPrescribedAxialExpansion(
            self.r.core.refAssem, componentLst, percents, setFuel=True
        )

    def test_manageCoreMesh(self):
        self.axialExpChngr.manageCoreMesh(self.r)
        newAxialMesh = self.r.core.p.axialMesh
        # skip first and last entries as they do not change
        for old, new in zip(self.oldAxialMesh[1:-1], newAxialMesh[1:-1]):
            self.assertLess(old, new)


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
        assembly.add(_buildTestBlock("shield", "FakeMat", 25.0, 10.0))
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

    def test_updateComponentTempsBy1DTempFieldValueError(self):
        tempGrid = [5.0, 15.0, 35.0]
        tempField = linspace(25.0, 310.0, 3)
        with self.assertRaises(ValueError) as cm:
            self.obj.expansionData.updateComponentTempsBy1DTempField(
                tempGrid, tempField
            )
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_updateComponentTempsBy1DTempFieldRuntimeError(self):
        tempGrid = [5.0, 15.0, 35.0]
        tempField = linspace(25.0, 310.0, 10)
        with self.assertRaises(RuntimeError) as cm:
            self.obj.expansionData.updateComponentTempsBy1DTempField(
                tempGrid, tempField
            )
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_AssemblyAxialExpansionException(self):
        """test that negative height exception is caught"""
        temp = Temperature(self.a.getTotalHeight(), numTempGridPts=11, tempSteps=10)
        with self.assertRaises(ArithmeticError) as cm:
            for idt in range(temp.tempSteps):
                self.obj.expansionData.updateComponentTempsBy1DTempField(
                    temp.tempGrid, temp.tempField[idt, :]
                )
                self.obj.expansionData.computeThermalExpansionFactors()
                self.obj.axiallyExpandAssembly()

            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_determineTargetComponentRuntimeErrorFirst(self):
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
            self.obj.expansionData.determineTargetComponent(b)

            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_determineTargetComponentRuntimeErrorSecond(self):
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
            self.obj.expansionData.determineTargetComponent(b)

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
            expdata._isFuelLocked(b_TwoFuel)

            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

        b_NoFuel = HexBlock("fuel", height=10.0)
        shield = Circle("shield", "FakeMat", **fuelDims)
        b_NoFuel.add(shield)
        with self.assertRaises(RuntimeError) as cm:
            expdata._isFuelLocked(b_NoFuel)

            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_determineLinked(self):
        compDims = {"Tinput": 25.0, "Thot": 25.0}
        compA = UnshapedComponent("unshaped_1", "FakeMat", **compDims)
        compB = UnshapedComponent("unshaped_2", "FakeMat", **compDims)
        self.assertFalse(_determineLinked(compA, compB))

    def test_getLinkedComponents(self):
        """test for multiple component axial linkage"""
        shieldBlock = self.obj.linked.a[0]
        shieldComp = shieldBlock[0]
        shieldComp.setDimension("od", 0.785, cold=True)
        with self.assertRaises(RuntimeError) as cm:
            self.obj.linked._getLinkedComponents(shieldBlock, shieldComp)
            self.assertEqual(cm.exception, 3)


class TestDetermineTargetComponent(unittest.TestCase):
    """verify determineTargetComponent method is properly updating _componentDeterminesBlockHeight"""

    def setUp(self):
        self.obj = AxialExpansionChanger()
        self.a = buildTestAssemblyWithFakeMaterial(name="FakeMatException")
        self.obj.setAssembly(self.a)
        # need an empty dictionary because we want to test for the added component only
        self.obj.expansionData._componentDeterminesBlockHeight = {}

    def test_determineTargetComponent(self):
        # build a test block
        b = HexBlock("fuel", height=10.0)
        fuelDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.76, "id": 0.00, "mult": 127.0}
        cladDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.80, "id": 0.77, "mult": 127.0}
        fuel = Circle("fuel", "FakeMat", **fuelDims)
        clad = Circle("clad", "FakeMat", **cladDims)
        b.add(fuel)
        b.add(clad)
        # call method, and check that target component is correct
        self.obj.expansionData.determineTargetComponent(b)
        self.assertTrue(
            self.obj.expansionData.isTargetComponent(fuel),
            msg="determineTargetComponent failed to recognize intended component: {}".format(
                fuel
            ),
        )

    def test_determineTargetComponentBlockWithMultipleFlags(self):
        # build a block that has two flags as well as a component matching each
        # flag
        b = HexBlock("fuel poison", height=10.0)
        fuelDims = {"Tinput": 25.0, "Thot": 600.0, "od": 0.9, "id": 0.5, "mult": 200.0}
        poisonDims = {"Tinput": 25.0, "Thot": 400.0, "od": 0.5, "id": 0.0, "mult": 10.0}
        fuel = Circle("fuel", "FakeMat", **fuelDims)
        poison = Circle("poison", "FakeMat", **poisonDims)
        b.add(fuel)
        b.add(poison)
        # call method, and check that target component is correct
        self.obj.expansionData.determineTargetComponent(b)
        self.assertTrue(
            self.obj.expansionData.isTargetComponent(fuel),
            msg="determineTargetComponent failed to recognize intended component: {}".format(
                fuel
            ),
        )

    def test_specifyTargetComponet_BlueprintSpecified(self):
        b = HexBlock("SodiumBlock", height=10.0)
        sodiumDims = {"Tinput": 25.0, "Thot": 25.0, "op": 17, "ip": 0.0, "mult": 1.0}
        ductDims = {"Tinput": 25.0, "Thot": 25.0, "op": 16, "ip": 15.0, "mult": 1.0}
        dummy = Hexagon("coolant", "Sodium", **sodiumDims)
        dummyDuct = Hexagon("duct", "FakeMat", **sodiumDims)
        b.add(dummy)
        b.add(dummyDuct)
        b.getVolumeFractions()
        b.setType("DuctBlock")

        # check for no target component found
        with self.assertRaises(RuntimeError) as cm:
            self.obj.expansionData.determineTargetComponent(b)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

        # check that target component is explicitly specified
        b.setAxialExpTargetComp(dummyDuct)
        self.assertEqual(
            b.axialExpTargetComponent,
            dummyDuct,
        )

        # check that target component is stored on expansionData object correctly
        self.obj.expansionData._componentDeterminesBlockHeight[
            b.axialExpTargetComponent
        ] = True
        self.assertTrue(
            self.obj.expansionData._componentDeterminesBlockHeight[
                b.axialExpTargetComponent
            ]
        )

        # get coverage for runLog statements on origination of target components
        # axial exp changer skips formal expansion of the top most block so we
        # need three blocks.
        b0 = _buildTestBlock("b0", "FakeMat", 25.0, 10.0)
        b2 = _buildTestBlock("b1", "FakeMat", 25.0, 10.0)
        assembly = HexAssembly("testAssemblyType")
        assembly.spatialGrid = grids.axialUnitGrid(numCells=1)
        assembly.spatialGrid.armiObject = assembly
        assembly.add(b0)
        assembly.add(b)
        assembly.add(b2)
        assembly.calculateZCoords()
        assembly.reestablishBlockOrder()
        with mockRunLogs.BufferLog() as mock:
            self.obj.performPrescribedAxialExpansion(assembly, [dummy], [0.01])
            self.assertIn("(blueprints defined)", mock._outputStream)
            self.assertIn("(inferred)", mock._outputStream)


class TestInputHeightsConsideredHot(unittest.TestCase):
    """verify thermal expansion for process loading of core"""

    def setUp(self):
        """This test uses a different armiRun.yaml than the default"""

        o, r = loadTestReactor(
            os.path.join(TEST_ROOT, "detailedAxialExpansion"),
            customSettings={"inputHeightsConsideredHot": True},
        )
        reduceTestReactorRings(r, o.cs, 3)

        self.stdAssems = [a for a in r.core.getAssemblies()]

        oCold, rCold = loadTestReactor(
            os.path.join(TEST_ROOT, "detailedAxialExpansion"),
            customSettings={"inputHeightsConsideredHot": False},
        )
        reduceTestReactorRings(rCold, oCold.cs, 3)

        self.testAssems = [a for a in rCold.core.getAssemblies()]

    def test_coldAssemblyExpansion(self):
        """block heights are cold and should be expanded

        Notes
        -----
        Two assertions here:
            1. total assembly height should be preserved (through use of top dummy block)
            2. in armi.tests.detailedAxialExpansion.refSmallReactorBase.yaml,
               Thot > Tinput resulting in a non-zero DeltaT. Each block in the
               expanded case should therefore be a different height than that of the standard case.
               - The one exception is for control assemblies. These designs can be unique from regular
                 pin type assemblies by allowing downward expansion. Because of this, they are skipped
                 for axial expansion.
        """
        for aStd, aExp in zip(self.stdAssems, self.testAssems):
            self.assertAlmostEqual(
                aStd.getTotalHeight(),
                aExp.getTotalHeight(),
                msg="Std Assem {0} ({1}) and Exp Assem {2} ({3}) are not the same height!".format(
                    aStd, aStd.getTotalHeight(), aExp, aExp.getTotalHeight()
                ),
            )
            for bStd, bExp in zip(aStd, aExp):
                hasCustomMaterial = any(
                    isinstance(c.material, custom.Custom) for c in bStd
                )
                if (aStd.hasFlags(Flags.CONTROL)) or (hasCustomMaterial):
                    checkColdBlockHeight(bStd, bExp, self.assertAlmostEqual, "the same")
                else:
                    checkColdBlockHeight(bStd, bExp, self.assertNotEqual, "different")
                if bStd.hasFlags(Flags.FUEL):
                    # fuel mass should grow because heights are considered cold heights
                    # and a cold 1 cm column has more mass than a hot 1 cm column
                    if not isinstance(
                        bStd.getComponent(Flags.FUEL).material, custom.Custom
                    ):
                        # custom materials don't expand
                        self.assertGreater(bExp.getMass("U235"), bStd.getMass("U235"))

                if not aStd.hasFlags(Flags.CONTROL) and not aStd.hasFlags(Flags.TEST):
                    if not hasCustomMaterial:
                        # skip blocks of custom material where liner is merged with clad
                        for cExp in bExp:
                            if not isinstance(cExp.material, custom.Custom):
                                matDens = cExp.material.density3(Tc=cExp.temperatureInC)
                                compDens = cExp.getMassDensity()
                                msg = (
                                    f"{cExp} {cExp.material} in {bExp} was not at correct density. \n"
                                    + f"expansion = {bExp.p.height / bStd.p.height} \n"
                                    + f"density3 = {matDens}, component density = {compDens} \n"
                                )
                                self.assertAlmostEqual(
                                    matDens,
                                    compDens,
                                    places=7,
                                    msg=msg,
                                )


def checkColdBlockHeight(bStd, bExp, assertType, strForAssertion):
    assertType(
        bStd.getHeight(),
        bExp.getHeight(),
        msg="Assembly: {0} -- Std Block {1} ({2}) and Exp Block {3} ({4}) should have {5:s} heights!".format(
            bStd.parent,
            bStd,
            bStd.getHeight(),
            bExp,
            bExp.getHeight(),
            strForAssertion,
        ),
    )


class TestLinkage(unittest.TestCase):
    """test axial linkage between components"""

    def setUp(self):
        """contains common dimensions for all component class types"""
        self.common = ("test", "FakeMat", 25.0, 25.0)  # name, material, Tinput, Thot

    def runTest(
        self,
        componentsToTest: dict,
        assertionBool: bool,
        name: str,
        commonArgs: tuple = None,
    ):
        """runs various linkage tests

        Parameters
        ----------
        componentsToTest : dict
            keys --> component class type; values --> dimensions specific to key
        assertionBool : boolean
            expected truth value for test
        name : str
            the name of the test
        commonArgs : tuple, optional
            arguments common to all Component class types

        Notes
        -----
        - components "typeA" and "typeB" are assumed to be vertically stacked
        - two assertions: 1) comparing "typeB" component to "typeA"; 2) comparing "typeA" component to "typeB"
        - the different assertions are particularly useful for comparing two annuli
        - to add Component class types to a test:
            Add dictionary entry with following:
              {Component Class Type: [{<settings for component 1>}, {<settings for component 2>}]
        """
        if commonArgs is None:
            common = self.common
        else:
            common = commonArgs
        for method, dims in componentsToTest.items():
            typeA = method(*common, **dims[0])
            typeB = method(*common, **dims[1])
            if assertionBool:
                self.assertTrue(
                    _determineLinked(typeA, typeB),
                    msg="Test {0:s} failed for component type {1:s}!".format(
                        name, str(method)
                    ),
                )
                self.assertTrue(
                    _determineLinked(typeB, typeA),
                    msg="Test {0:s} failed for component type {1:s}!".format(
                        name, str(method)
                    ),
                )
            else:
                self.assertFalse(
                    _determineLinked(typeA, typeB),
                    msg="Test {0:s} failed for component type {1:s}!".format(
                        name, str(method)
                    ),
                )
                self.assertFalse(
                    _determineLinked(typeB, typeA),
                    msg="Test {0:s} failed for component type {1:s}!".format(
                        name, str(method)
                    ),
                )

    def test_overlappingSolidPins(self):
        componentTypesToTest = {
            Circle: [{"od": 0.5, "id": 0.0}, {"od": 1.0, "id": 0.0}],
            Hexagon: [{"op": 0.5, "ip": 0.0}, {"op": 1.0, "ip": 0.0}],
            Rectangle: [
                {
                    "lengthOuter": 0.5,
                    "lengthInner": 0.0,
                    "widthOuter": 0.5,
                    "widthInner": 0.0,
                },
                {
                    "lengthOuter": 1.0,
                    "lengthInner": 0.0,
                    "widthOuter": 1.0,
                    "widthInner": 0.0,
                },
            ],
            Helix: [
                {"od": 0.5, "axialPitch": 1.0, "helixDiameter": 1.0},
                {"od": 1.0, "axialPitch": 1.0, "helixDiameter": 1.0},
            ],
        }
        self.runTest(componentTypesToTest, True, "test_overlappingSolidPins")

    def test_differentMultNotOverlapping(self):
        componentTypesToTest = {
            Circle: [{"od": 0.5, "mult": 10}, {"od": 0.5, "mult": 20}],
            Hexagon: [{"op": 0.5, "mult": 10}, {"op": 1.0, "mult": 20}],
            Rectangle: [
                {"lengthOuter": 1.0, "widthOuter": 1.0, "mult": 10},
                {"lengthOuter": 1.0, "widthOuter": 1.0, "mult": 20},
            ],
            Helix: [
                {"od": 0.5, "axialPitch": 1.0, "helixDiameter": 1.0, "mult": 10},
                {"od": 1.0, "axialPitch": 1.0, "helixDiameter": 1.0, "mult": 20},
            ],
        }
        self.runTest(componentTypesToTest, False, "test_differentMultNotOverlapping")

    def test_solidPinNotOverlappingAnnulus(self):
        componentTypesToTest = {
            Circle: [{"od": 0.5, "id": 0.0}, {"od": 1.0, "id": 0.6}],
        }
        self.runTest(componentTypesToTest, False, "test_solidPinNotOverlappingAnnulus")

    def test_solidPinOverlappingWithAnnulus(self):
        componentTypesToTest = {
            Circle: [{"od": 0.7, "id": 0.0}, {"od": 1.0, "id": 0.6}],
        }
        self.runTest(componentTypesToTest, True, "test_solidPinOverlappingWithAnnulus")

    def test_annularPinNotOverlappingWithAnnulus(self):
        componentTypesToTest = {
            Circle: [{"od": 0.6, "id": 0.3}, {"od": 1.0, "id": 0.6}],
        }
        self.runTest(
            componentTypesToTest, False, "test_annularPinNotOverlappingWithAnnulus"
        )

    def test_annularPinOverlappingWithAnnuls(self):
        componentTypesToTest = {
            Circle: [{"od": 0.7, "id": 0.3}, {"od": 1.0, "id": 0.6}],
        }
        self.runTest(componentTypesToTest, True, "test_annularPinOverlappingWithAnnuls")

    def test_thinAnnularPinOverlappingWithThickAnnulus(self):
        componentTypesToTest = {
            Circle: [{"od": 0.7, "id": 0.3}, {"od": 0.6, "id": 0.5}],
        }
        self.runTest(
            componentTypesToTest, True, "test_thinAnnularPinOverlappingWithThickAnnulus"
        )

    def test_AnnularHexOverlappingThickAnnularHex(self):
        componentTypesToTest = {
            Hexagon: [{"op": 1.0, "ip": 0.8}, {"op": 1.2, "ip": 0.8}]
        }
        self.runTest(
            componentTypesToTest, True, "test_AnnularHexOverlappingThickAnnularHex"
        )

    def test_liquids(self):
        componentTypesToTest = {
            Circle: [{"od": 1.0, "id": 0.0}, {"od": 1.0, "id": 0.0}],
            Hexagon: [{"op": 1.0, "ip": 0.0}, {"op": 1.0, "ip": 0.0}],
        }
        liquid = ("test", "Sodium", 425.0, 425.0)  # name, material, Tinput, Thot
        self.runTest(componentTypesToTest, False, "test_liquids", commonArgs=liquid)

    def test_unshapedComponentAndCircle(self):
        comp1 = Circle(*self.common, od=1.0, id=0.0)
        comp2 = UnshapedComponent(*self.common, area=1.0)
        self.assertFalse(_determineLinked(comp1, comp2))


def buildTestAssemblyWithFakeMaterial(name: str, hot: bool = False):
    """Create test assembly consisting of list of fake material

    Parameters
    ----------
    name : string
        determines which fake material to use
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
    assembly.add(_buildTestBlock("shield", name, hotTemp, height))
    assembly.add(_buildTestBlock("fuel", name, hotTemp, height))
    assembly.add(_buildTestBlock("fuel", name, hotTemp, height))
    assembly.add(_buildTestBlock("plenum", name, hotTemp, height))
    assembly.add(_buildDummySodium(hotTemp, height))
    assembly.calculateZCoords()
    assembly.reestablishBlockOrder()
    return assembly


def _buildTestBlock(blockType: str, name: str, hotTemp: float, height: float):
    """Return a simple pin type block filled with coolant and surrounded by duct.

    Parameters
    ----------
    blockType : string
        determines which type of block you're building

    name : string
        determines which fake material to use
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


def _buildDummySodium(hotTemp: float, height: float):
    """Build a dummy sodium block."""
    b = HexBlock("dummy", height=height)

    sodiumDims = {"Tinput": 25.0, "Thot": hotTemp, "op": 17, "ip": 0.0, "mult": 1.0}
    dummy = Hexagon("dummy coolant", "Sodium", **sodiumDims)

    b.add(dummy)
    b.getVolumeFractions()
    b.setType("dummy")

    return b


class FakeMat(materials.ht9.HT9):
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
        """A fake linear expansion percent"""
        Tc = units.getTc(Tc, Tk)
        return 0.02 * Tc


class FakeMatException(materials.ht9.HT9):
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
        """A fake linear expansion percent"""
        Tc = units.getTc(Tc, Tk)
        return 0.08 * Tc
