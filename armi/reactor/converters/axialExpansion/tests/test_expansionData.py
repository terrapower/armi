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

import unittest
from numpy import zeros, linspace, ones

from armi.reactor.flags import Flags
from armi.reactor.blocks import HexBlock
from armi.reactor.components import DerivedShape
from armi.reactor.components.basicShapes import Circle, Hexagon
from armi.reactor.converters.axialExpansion.tests import AxialExpansionTestBase
from armi.reactor.converters.axialExpansion.expansionData import (
    ExpansionData,
    getSolidComponents,
)
from armi.reactor.converters.axialExpansion.tests.buildAxialExpAssembly import (
    buildTestAssembly,
)


class TestSetExpansionFactors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = buildTestAssembly("HT9")
        cls.expData = ExpansionData(cls.a, False, False)

    def test_getExpansionFactor(self):
        expansionFactor = 1.15
        shieldComp = self.a[0].getComponent(Flags.SHIELD)
        cladComp = self.a[0].getComponent(Flags.CLAD)
        self.expData.setExpansionFactors([shieldComp], [expansionFactor])
        self.assertEqual(self.expData.getExpansionFactor(shieldComp), expansionFactor)
        self.assertEqual(self.expData.getExpansionFactor(cladComp), 1.0)

    def test_setExpansionFactors(self):
        cList = self.a[0].getChildren()
        expansionGrowthFracs = range(1, len(cList) + 1)
        self.expData.setExpansionFactors(cList, expansionGrowthFracs)
        for c, expFrac in zip(cList, expansionGrowthFracs):
            self.assertEqual(self.expData._expansionFactors[c], expFrac)

    def test_setExpansionFactors_Exceptions(self):
        with self.assertRaises(RuntimeError) as cm:
            cList = self.a[0].getChildren()
            expansionGrowthFracs = range(len(cList) + 1)
            self.expData.setExpansionFactors(cList, expansionGrowthFracs)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

        with self.assertRaises(RuntimeError) as cm:
            cList = self.a[0].getChildren()
            expansionGrowthFracs = zeros(len(cList))
            self.expData.setExpansionFactors(cList, expansionGrowthFracs)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

        with self.assertRaises(RuntimeError) as cm:
            cList = self.a[0].getChildren()
            expansionGrowthFracs = zeros(len(cList)) - 10.0
            self.expData.setExpansionFactors(cList, expansionGrowthFracs)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)


class TestComputeThermalExpansionFactors(AxialExpansionTestBase):
    def setUp(self):
        AxialExpansionTestBase.setUp(self)
        self.a = buildTestAssembly("FakeMat", hot=True)

    def tearDown(self):
        AxialExpansionTestBase.tearDown(self)

    def test_computeThermalExpansionFactors_FromTinput2Thot(self):
        """Expand from Tinput to Thot."""
        self.expData = ExpansionData(self.a, False, True)
        self.expData.computeThermalExpansionFactors()
        for b in self.a:
            for c in getSolidComponents(b):
                self.assertEqual(self.expData._expansionFactors[c], 1.044776119402985)

    def test_computeThermalExpansionFactors_NoRefTemp(self):
        """Occurs when not expanding from Tinput to Thot and no new temperature prescribed."""
        self.expData = ExpansionData(self.a, False, False)
        self.expData.computeThermalExpansionFactors()
        for b in self.a:
            for c in getSolidComponents(b):
                self.assertEqual(self.expData._expansionFactors[c], 1.0)

    def test_computeThermalExpansionFactors_withRefTemp(self):
        """Occurs when expanding from some reference temp (not equal to Tinput) to Thot."""
        self.expData = ExpansionData(self.a, False, False)
        for b in self.a:
            for c in getSolidComponents(b):
                self.expData.updateComponentTemp(c, 175.0)
        self.expData.computeThermalExpansionFactors()
        for b in self.a:
            for c in getSolidComponents(b):
                self.assertEqual(self.expData._expansionFactors[c], 0.9857142857142858)


class TestUpdateComponentTemps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        a = buildTestAssembly("HT9")
        cls.expData = ExpansionData(a, False, False)

    def test_updateComponentTemp(self):
        newTemp = 250.0
        shieldB = self.expData._a[0]
        shieldComp = shieldB.getComponent(Flags.SHIELD)
        self.expData.updateComponentTemp(shieldComp, newTemp)
        self.assertEqual(
            self.expData.componentReferenceTemperature[shieldComp],
            shieldComp.inputTemperatureInC,
        )
        self.assertEqual(shieldComp.temperatureInC, newTemp)

    def test_updateComponentTempsBy1DTempField(self):
        newTemp = 125.0
        bottom = self.expData._a[0].p.zbottom
        top = self.expData._a[-1].p.ztop
        tempGrid = linspace(bottom, top, 11)
        tempField = ones(11) * newTemp
        self.expData.updateComponentTempsBy1DTempField(tempGrid, tempField)
        for b in self.expData._a:
            for c in b:
                self.assertEqual(c.temperatureInC, newTemp)

    def test_updateComponentTempsBy1DTempFieldValueError(self):
        tempGrid = [5.0, 15.0, 35.0]
        tempField = linspace(25.0, 310.0, 3)
        with self.assertRaises(ValueError) as cm:
            self.expData.updateComponentTempsBy1DTempField(tempGrid, tempField)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_updateComponentTempsBy1DTempFieldRuntimeError(self):
        tempGrid = [5.0, 15.0, 35.0]
        tempField = linspace(25.0, 310.0, 10)
        with self.assertRaises(RuntimeError) as cm:
            self.expData.updateComponentTempsBy1DTempField(tempGrid, tempField)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)


class TestSetTargetComponents(unittest.TestCase):
    """Runs through _setTargetComponents in the init and checks to make sure they're all set right.

    Coverage for isTargetComponent is provided when querying each component for their target component
    """

    @classmethod
    def setUpClass(cls):
        cls.a = buildTestAssembly("HT9")

    def test_checkTargetComponents(self):
        """Make sure target components are set right. Skip the dummy block."""
        expData = ExpansionData(self.a, False, False)
        for b in self.a[-1]:
            for c in b:
                if b.hasFlags(Flags.PLENUM):
                    if c.hasFlags(Flags.CLAD):
                        self.assertTrue(expData.isTargetComponent(c))
                    else:
                        self.assertFalse(expData.isTargetComponent(c))
                else:
                    if c.p.flags == b.p.flags:
                        self.assertTrue(expData.isTargetComponent(c))
                    else:
                        self.assertFalse(expData.isTargetComponent(c))

    def test_isFuelLocked(self):
        """Ensures that the RuntimeError statement in ExpansionData::_isFuelLocked is raised appropriately.

        Notes
        -----
        This is implemented by modifying the fuel block to contain no fuel component
        and passing it to ExpansionData::_isFuelLocked.
        """
        expData = ExpansionData(self.a, False, False)
        fuelBlock = self.a[1]
        fuelComp = fuelBlock.getComponent(Flags.FUEL)
        self.assertEqual(fuelBlock.p.axialExpTargetComponent, fuelComp.name)
        ## Delete fuel comp and throw the error
        fuelBlock.remove(fuelComp)
        with self.assertRaises(RuntimeError) as cm:
            expData._isFuelLocked(fuelBlock)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)


class TestDetermineTargetComponent(unittest.TestCase):
    """Verify determineTargetComponent method is properly updating _componentDeterminesBlockHeight."""

    def setUp(self):
        self.expData = ExpansionData([], setFuel=True, expandFromTinputToThot=True)
        coolDims = {"Tinput": 25.0, "Thot": 25.0}
        self.coolant = DerivedShape("coolant", "Sodium", **coolDims)

    def test_determineTargetComponent(self):
        """Provides coverage for searching TARGET_FLAGS_IN_PREFERRED_ORDER."""
        b = HexBlock("fuel", height=10.0)
        fuelDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.76, "id": 0.00, "mult": 127.0}
        cladDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.80, "id": 0.77, "mult": 127.0}
        fuel = Circle("fuel", "HT9", **fuelDims)
        clad = Circle("clad", "HT9", **cladDims)
        b.add(fuel)
        b.add(clad)
        b.add(self.coolant)
        # make sure that b.p.axialExpTargetComponent is empty initially
        self.assertFalse(b.p.axialExpTargetComponent)
        # call method, and check that target component is correct
        self.expData.determineTargetComponent(b)
        self.assertTrue(
            self.expData.isTargetComponent(fuel),
            msg=f"determineTargetComponent failed to recognize intended component: {fuel}",
        )
        self.assertEqual(
            b.p.axialExpTargetComponent,
            fuel.name,
            msg=f"determineTargetComponent failed to recognize intended component: {fuel}",
        )

    def test_determineTargetComponentBlockWithMultipleFlags(self):
        """Provides coverage for searching TARGET_FLAGS_IN_PREFERRED_ORDER with multiple flags."""
        # build a block that has two flags as well as a component matching each
        b = HexBlock("fuel poison", height=10.0)
        fuelDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.9, "id": 0.5, "mult": 200.0}
        poisonDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.5, "id": 0.0, "mult": 10.0}
        fuel = Circle("fuel", "HT9", **fuelDims)
        poison = Circle("poison", "HT9", **poisonDims)
        b.add(fuel)
        b.add(poison)
        b.add(self.coolant)
        # call method, and check that target component is correct
        self.expData.determineTargetComponent(b)
        self.assertTrue(
            self.expData.isTargetComponent(fuel),
            msg=f"determineTargetComponent failed to recognize intended component: {fuel}",
        )

    def test_specifyTargetComponent_NotFound(self):
        """Ensure RuntimeError gets raised when no target component is found."""
        b = HexBlock("fuel", height=10.0)
        b.add(self.coolant)
        b.setType("fuel")
        with self.assertRaises(RuntimeError) as cm:
            self.expData.determineTargetComponent(b)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)
        with self.assertRaises(RuntimeError) as cm:
            self.expData.determineTargetComponent(b, Flags.FUEL)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_specifyTargetComponent_singleSolid(self):
        """Ensures that specifyTargetComponent is smart enough to set the only solid as the target component."""
        b = HexBlock("plenum", height=10.0)
        ductDims = {"Tinput": 25.0, "Thot": 25.0, "op": 17, "ip": 0.0, "mult": 1.0}
        duct = Hexagon("duct", "HT9", **ductDims)
        b.add(duct)
        b.add(self.coolant)
        b.getVolumeFractions()
        b.setType("plenum")
        self.expData.determineTargetComponent(b)
        self.assertTrue(
            self.expData.isTargetComponent(duct),
            msg=f"determineTargetComponent failed to recognize intended component: {duct}",
        )

    def test_specifyTargetComponet_MultipleFound(self):
        """Ensure RuntimeError is hit when multiple target components are found.

        Notes
        -----
        This can occur if a block has a mixture of fuel types. E.g., different fuel materials,
        or different fuel geometries.
        """
        b = HexBlock("fuel", height=10.0)
        fuelAnnularDims = {
            "Tinput": 25.0,
            "Thot": 25.0,
            "od": 0.9,
            "id": 0.5,
            "mult": 100.0,
        }
        fuelDims = {"Tinput": 25.0, "Thot": 25.0, "od": 1.0, "id": 0.0, "mult": 10.0}
        fuel = Circle("fuel", "HT9", **fuelDims)
        fuelAnnular = Circle("fuel annular", "HT9", **fuelAnnularDims)
        b.add(fuel)
        b.add(fuelAnnular)
        b.add(self.coolant)
        b.setType("FuelBlock")
        with self.assertRaises(RuntimeError) as cm:
            self.expData.determineTargetComponent(b, flagOfInterest=Flags.FUEL)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_manuallySetTargetComponent(self):
        """Ensures that target components can be manually set (is done in practice via blueprints).

        .. test:: Allow user-specified target axial expansion components on a given block.
            :id: T_ARMI_MANUAL_TARG_COMP
            :tests: R_ARMI_MANUAL_TARG_COMP
        """
        b = HexBlock("dummy", height=10.0)
        ductDims = {"Tinput": 25.0, "Thot": 25.0, "op": 17, "ip": 0.0, "mult": 1.0}
        duct = Hexagon("duct", "HT9", **ductDims)
        b.add(duct)
        b.add(self.coolant)
        b.getVolumeFractions()
        b.setType("duct")

        # manually set target component
        b.setAxialExpTargetComp(duct)
        self.assertEqual(
            b.p.axialExpTargetComponent,
            duct.name,
        )

        # check that target component is stored on expansionData object correctly
        self.expData._componentDeterminesBlockHeight[
            b.getComponentByName(b.p.axialExpTargetComponent)
        ] = True
        self.assertTrue(self.expData.isTargetComponent(duct))
