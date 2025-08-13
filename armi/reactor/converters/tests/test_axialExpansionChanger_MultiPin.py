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

import collections
import copy
import os
from typing import TYPE_CHECKING

from dataclasses import dataclass
from numpy import zeros

from armi.reactor.converters.axialExpansionChanger.axialExpansionChanger import AxialExpansionChanger
from armi.reactor.converters.axialExpansionChanger.expansionData import iterSolidComponents
from armi.reactor.converters.tests.test_axialExpansionChanger import AxialExpansionTestBase
from armi.reactor.flags import Flags, TypeSpec
from armi.testing import loadTestReactor
from armi.tests import TEST_ROOT

if TYPE_CHECKING:
    from armi.reactor.assemblies import HexAssembly
    from armi.reactor.blocks import HexBlock
    from armi.reactor.components.component import Component

@dataclass
class StoreMass:
    cFlags: TypeSpec
    mass: float

class TestMultiPinConservationBase(AxialExpansionTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _oCold, rCold = loadTestReactor(
            os.path.join(TEST_ROOT, "detailedAxialExpansion"),
            customSettings={"inputHeightsConsideredHot": True},
        )
        cls.aRef = list(filter(lambda a: a.getType() == "multi pin fuel", rCold.blueprints.assemblies.values()))[0]
        cls.places = 12

    def setUp(self):
        self.a = copy.deepcopy(self.aRef)
        self.axialExpChngr = AxialExpansionChanger()
        self.axialExpChngr.setAssembly(self.a)


class TestRedistributeMass(TestMultiPinConservationBase):
    b0: "HexBlock"
    b1: "HexBlock"
    c0: "Component"
    origC0Temp: float
    c1: "Component"
    origC1Temp: float

    def setUp(self):
        super().setUp()
        self.b0 = self.a.getFirstBlock(Flags.FUEL)
        self.b1 = self.axialExpChngr.linked.linkedBlocks[self.b0].upper
        self.c0 = next(filter(lambda c: c.getType() == "fuel test", self.b0))
        self.c1 = self.axialExpChngr.linked.linkedComponents[self.c0].upper

    def test_shiftLinkedCompsForDelta(self):
        """Ensure that given a deltaZTop, component elevations are adjusted appropriately."""
        self._initializeComponentElevations(growFrac=1.0)
        # set what they should be after adjusting
        delta = 0.1
        refC0Height = self.c0.height + delta
        refC0Ztop = self.c0.ztop + delta
        refC1Height = self.c1.height - delta
        refC1Zbottom = self.c1.zbottom + delta
        self.axialExpChngr._shiftLinkedCompsForDelta(self.c0, self.c1, delta)
        self.assertAlmostEqual(refC0Height, self.c0.height, places=self.places)
        self.assertAlmostEqual(refC1Height, self.c1.height, places=self.places)
        self.assertAlmostEqual(refC0Ztop, self.c0.ztop, places=self.places)
        self.assertAlmostEqual(refC1Zbottom, self.c1.zbottom, places=self.places)

    def test_redistributeMass_nonTargetExpansion_noThermal(self):
        """Perform prescribed expansion of the test fuel component by calling ``redistributeMass``

        This test ensures that self.c0 and self.c1 change by the same expected amount.
        """
        growFrac = 1.10
        # update the ndens of c0 for the change in height too
        self.c0.changeNDensByFactor(1.0 / growFrac)
        self._initializeComponentElevations(growFrac)
        # set the original mass of the components post expansion and pre redistribution
        # multiply c0.getMass() by growFrac since b0.p.height does not have that factor.
        # Doing so gets you to the true c0 mass.
        preRedistributionC0Mass = self.c0.getMass() * growFrac
        preRedistributionC1Mass = self.c1.getMass()
        # set the original temp of the components, post expansion, pre redistrubution
        preRedistributionC0Temp = self.c0.temperatureInC
        preRedistributionC1Temp = self.c1.temperatureInC
        # calculate deltaZTop, the amount of mass getting moved, and perform the redistribution
        deltaZTop = self.b0.p.ztop - self.c0.ztop
        amountBeingRedistributed = preRedistributionC0Mass * abs(deltaZTop) / self.c0.height

        # perform the redistrubtion in its entirety
        self.axialExpChngr.redistributeMass(fromComp=self.c0, toComp=self.c1, deltaZTop=deltaZTop)
        # assert the temperatures do not change
        self.assertEqual(self.c0.temperatureInC, preRedistributionC0Temp)
        self.assertEqual(self.c1.temperatureInC, preRedistributionC1Temp)
        # Ensure that c0 and c1 change by the anticipated amount
        self.assertAlmostEqual(
            self.c0.getMass(),
            preRedistributionC0Mass - amountBeingRedistributed,
            places=self.places,
        )
        # ensure that the c1 mass has increased by deltaZTop/self.c0.height.
        # change b1.p.height for mass calculation.
        # This effectively sets the c1 mass calculation relative to the new comp height (10% shorter since 10% was
        # given to c0.)
        self.b1.p.height = self.c1.ztop - (self.c1.zbottom + deltaZTop)
        self.b1.clearCache()
        self.assertAlmostEqual(
            self.c1.getMass(),
            preRedistributionC1Mass + amountBeingRedistributed,
            places=self.places,
        )

    def test_addMassToComponent_nonTargetCompression_noThermal(self):
        """With no temperature changes anywere, shrink c0 by 10% and show that 10% of the c1 mass is moved to c0.

        Notes
        -----
        C0 shrinks resulting in c1 giving 10% of its mass to c0. c1 height does not change so it's mass loses 10%.
        """
        growFrac = 0.9
        # update the ndens of c0 for the change in height too
        self.c0.changeNDensByFactor(1.0 / growFrac)
        self._initializeComponentElevations(growFrac)
        # set the original mass of the components post expansion and pre redistribution
        # multiply c0.getMass() by growFrac since b0.p.height does not have that factor.
        # Doing so gets you to the true c0 mass.
        preRedistributionC0Mass = self.c0.getMass() * growFrac
        preRedistributionC1Mass = self.c1.getMass()
        # set the original temp of the components, post expansion, pre redistrubution
        preRedistributionC0Temp = self.c0.temperatureInC
        preRedistributionC1Temp = self.c1.temperatureInC

        # calculate deltaZTop, the amount of mass getting moved, and perform the redistribution
        deltaZTop = self.b0.p.ztop - self.c0.ztop
        amountBeingRedistributed = preRedistributionC1Mass * abs(deltaZTop) / self.c1.height
        # perform the mass redistrbution from c1 to c0
        self.axialExpChngr._addMassToComponent(
            fromComp=self.c1,
            toComp=self.c0,
            deltaZTop=deltaZTop,
        )
        # ensure there is no difference in c1 mass
        self.assertAlmostEqual(self.c1.getMass(), preRedistributionC1Mass, places=self.places)
        # ensure that the c0 mass has increased by amountBeingRedistributed
        self.assertAlmostEqual(
            self.c0.getMass(),
            preRedistributionC0Mass + amountBeingRedistributed,
            places=self.places,
        )
        # assert the temperatures do not change
        self.assertEqual(self.c0.temperatureInC, preRedistributionC0Temp)
        self.assertEqual(self.c1.temperatureInC, preRedistributionC1Temp)

        # now remove the c1 mass and ensure it's mass decreases by amountBeingRedistributed
        self.axialExpChngr._removeMassFromComponent(fromComp=self.c1, deltaZTop=-deltaZTop)
        # change b1.p.height for mass calculation.
        # This effectively sets the c1 mass calculation relative to the new comp height (10% shorter since 10% was
        # given to c0.)
        self.b1.p.height = self.c1.ztop - (self.c1.zbottom + deltaZTop)
        self.b1.clearCache()
        self.assertAlmostEqual(
            self.c1.getMass(), preRedistributionC1Mass - amountBeingRedistributed, places=self.places
        )
        # assert the temperatures still do not change
        self.assertEqual(self.c0.temperatureInC, preRedistributionC0Temp)
        self.assertEqual(self.c1.temperatureInC, preRedistributionC1Temp)

    def test_addMassToComponent_nonTargetCompression_yesThermal(self):
        """Decrease c0 by 100 deg C and and show that c1 mass is moved to c0.

        Notes
        -----
        C0 shrinks resulting in c1 giving X% of its mass to c0. c1 height does not change so it's mass loses X%.
        """
        newTemp = self.c0.temperatureInC - 100.0
        # updateComponentTemp updates ndens for update in AREA only
        self.axialExpChngr.expansionData.updateComponentTemp(self.c0, newTemp)
        self.axialExpChngr.expansionData.computeThermalExpansionFactors()
        growFrac = self.axialExpChngr.expansionData.getExpansionFactor(self.c0)
        # update the ndens of c0 for the change in height too
        self.c0.changeNDensByFactor(1.0 / growFrac)
        self._initializeComponentElevations(growFrac)
        # set the original mass of the components post expansion and pre redistribution
        # multiply c0.getMass() by growFrac since b0.p.height does not have that factor.
        # Doing so gets you to the true c0 mass.
        preRedistributionC0Mass = self.c0.getMass() * growFrac
        preRedistributionC1Mass = self.c1.getMass()
        # set the original temp of the components, post expansion, pre redistrubution
        preRedistributionC0Temp = self.c0.temperatureInC
        preRedistributionC1Temp = self.c1.temperatureInC

        # calculate deltaZTop, the amount of mass getting moved, and perform the redistribution
        deltaZTop = self.b0.p.ztop - self.c0.ztop
        amountBeingRedistributed = preRedistributionC1Mass * abs(deltaZTop) / self.c1.height
        # perform the mass redistrbution from c1 to c0
        self.axialExpChngr._addMassToComponent(
            fromComp=self.c1,
            toComp=self.c0,
            deltaZTop=deltaZTop,
        )
        # ensure there is no difference in c1 mass
        self.assertAlmostEqual(self.c1.getMass(), preRedistributionC1Mass, places=self.places)
        # ensure that the c0 mass has increased by amountBeingRedistributed
        self.assertAlmostEqual(
            self.c0.getMass(),
            preRedistributionC0Mass + amountBeingRedistributed,
            places=self.places,
        )
        # assert that the temperature of c1 is the same and that c0 has increased
        self.assertEqual(self.c1.temperatureInC, preRedistributionC1Temp)
        self.assertGreater(self.c0.temperatureInC, preRedistributionC0Temp)

        # now remove the c1 mass and ensure it's mass decreases by amountBeingRedistributed
        self.axialExpChngr._removeMassFromComponent(fromComp=self.c1, deltaZTop=-deltaZTop)
        # change b1.p.height for mass calculation.
        # This effectively sets the c1 mass calculation relative to the new comp height (10% shorter since 10% was
        # given to c0.)
        self.b1.p.height = self.c1.ztop - (self.c1.zbottom + deltaZTop)
        self.b1.clearCache()
        self.assertAlmostEqual(
            self.c1.getMass(), preRedistributionC1Mass - amountBeingRedistributed, places=self.places
        )
        # assert the temperatures do not change
        self.assertEqual(self.c1.temperatureInC, preRedistributionC1Temp)
        self.assertGreater(self.c0.temperatureInC, preRedistributionC0Temp)

    def test_addMassToComponent_nonTargetExpansion_yesThermal(self):
        """Decrease c0 by 100 deg C and and show that c1 mass is moved to c0.

        Notes
        -----
        C0 expands resulting in c0 giving X% of its mass to c1. c0 height does not change so its mass loses X%.
        """
        newTemp = self.c0.temperatureInC + 100.0
        # updateComponentTemp updates ndens for update in AREA only
        self.axialExpChngr.expansionData.updateComponentTemp(self.c0, newTemp)
        self.axialExpChngr.expansionData.computeThermalExpansionFactors()
        growFrac = self.axialExpChngr.expansionData.getExpansionFactor(self.c0)
        # update the ndens of c0 for the change in height too
        self.c0.changeNDensByFactor(1.0 / growFrac)
        # set the height of the components post expansion
        self.c0.zbottom = self.b0.p.zbottom
        self.c0.height = self.b0.getHeight() * growFrac
        self.c0.ztop = self.c0.zbottom + self.c0.height
        self.c1.zbottom = self.b1.p.zbottom
        self.c1.height = self.b1.getHeight()
        self.c1.ztop = self.c1.zbottom + self.c1.height
        # set the original mass of the components post expansion and pre redistribution
        # multiply c0.getMass() by growFrac since b0.p.height does not have that factor.
        # Doing so gets you to the true c0 mass.
        preRedistributionC0Mass = self.c0.getMass() * growFrac
        preRedistributionC1Mass = self.c1.getMass()
        # set the original temp of the components, post expansion, pre redistrubution
        preRedistributionC0Temp = self.c0.temperatureInC
        preRedistributionC1Temp = self.c1.temperatureInC

        # calculate deltaZTop, the amount of mass getting moved, and perform the redistribution
        deltaZTop = self.b0.p.ztop - self.c0.ztop
        amountBeingRedistributed = preRedistributionC0Mass * abs(deltaZTop) / self.c0.height
        # perform the mass redistrbution from c0 to c1
        self.axialExpChngr._addMassToComponent(fromComp=self.c0, toComp=self.c1, deltaZTop=deltaZTop)
        # ensure there is no difference in c0 mass
        self.assertAlmostEqual(preRedistributionC0Mass, self.c0.getMass() * growFrac, places=self.places)
        # ensure that the c1 mass has increased by deltaZTop/self.c0.height.
        # change b1.p.height for mass calculation.
        # This effectively sets the c1 mass calculation relative to the new comp height (10% shorter since 10% was
        # given to c0.)
        self.b1.p.height = self.c1.ztop - (self.c1.zbottom + deltaZTop)
        self.b1.clearCache()
        self.assertAlmostEqual(
            self.c1.getMass(),
            preRedistributionC1Mass + amountBeingRedistributed,
            places=self.places,
        )
        # assert that the temperature of c0 is the same and that c1 has increased
        self.assertEqual(self.c0.temperatureInC, preRedistributionC0Temp)
        self.assertGreater(self.c1.temperatureInC, preRedistributionC1Temp)

        # now remove the c0 mass and assert it is deltaZTop/self.c0.height less than its pre-redistribution value
        self.axialExpChngr._removeMassFromComponent(fromComp=self.c0, deltaZTop=deltaZTop)
        self.assertAlmostEqual(
            self.c0.getMass(), preRedistributionC0Mass - amountBeingRedistributed, places=self.places
        )
        # assert the c0 temperature does not change
        self.assertEqual(self.c0.temperatureInC, preRedistributionC0Temp)

    def _initializeComponentElevations(self, growFrac: float):
        """Set the height of the components post expansion."""
        self.c0.zbottom = self.b0.p.zbottom
        self.c0.height = self.b0.getHeight() * growFrac
        self.c0.ztop = self.c0.zbottom + self.c0.height
        self.c1.zbottom = self.b1.p.zbottom
        self.c1.height = self.b1.getHeight()
        self.c1.ztop = self.c1.zbottom + self.c1.height


class TestMultiPinConservation(TestMultiPinConservationBase):
    def setUp(self):
        super().setUp()
        _origBHeight, _origCMassesByBlock, self.origTotalCMassByFlag = self.getMassesForTest(self.a)

    @staticmethod
    def getMassesForTest(a: "HexAssembly"):
        blockHeights: dict["HexBlock", float] = {}
        compMassByBlock: dict["HexBlock", StoreMass] = collections.defaultdict(list)
        totalCMassByFlags: dict[Flags, float] = collections.defaultdict(float)
        for b in a:
            blockHeights[b] = b.getHeight()
            for c in iterSolidComponents(b):
                totalCMassByFlags[c.p.flags] += c.getMass()
                compMassByBlock[b].append(StoreMass(c.p.flags, c.getMass()))

        return blockHeights, compMassByBlock, totalCMassByFlags

    def test_expandAndContractThermal(self):
        """Test both.

        Change fuel and test fuel isothermal pass
        change fuel non-isothermal and test fuel isothermal pass
        change test fuel non-isothermal fail
        """
        for i, b in enumerate(filter(lambda b: b.hasFlags(Flags.FUEL), self.a), start=1):
            for c in b.iterChildrenWithFlags(Flags.FUEL):
                if c.hasFlags(Flags.TEST):
                    newTemp = c.temperatureInC + 150.0 * i
                else:
                    newTemp = c.temperatureInC + 50.0 * i
                self.axialExpChngr.expansionData.updateComponentTemp(c, newTemp)
        self.axialExpChngr.expansionData.computeThermalExpansionFactors()
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_roundTripThermal(self):
        """Ensure that the original state of the assembly is recovered through thermal expansion."""
        tempAdjust = [50, -50]
        for temp in tempAdjust:
            for i, b in enumerate(filter(lambda b: b.hasFlags(Flags.FUEL), self.a), start=1):
                for c in b.iterChildrenWithFlags(Flags.FUEL):
                    if c.hasFlags(Flags.TEST):
                        testTemp = temp + 25 if temp > 0 else temp - 25
                        newTemp = c.temperatureInC + testTemp * i
                    else:
                        newTemp = c.temperatureInC + temp * i
                    self.axialExpChngr.expansionData.updateComponentTemp(c, newTemp)
            self.axialExpChngr.expansionData.computeThermalExpansionFactors()
            self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_expandThermal(self):
        """Test expansion.

        Change fuel: isothermal and non-isothermal pass
        Change test fuel: isothermal pass, non-isothermal fail
        """
        for i, b in enumerate(filter(lambda b: b.hasFlags(Flags.FUEL), self.a), start=1):
            for c in b.iterChildrenWithFlags([Flags.FUEL, Flags.TEST, Flags.DEPLETABLE], exactMatch=True):
                newTemp = c.temperatureInC + 100.0 * i
                self.axialExpChngr.expansionData.updateComponentTemp(c, newTemp)
        self.axialExpChngr.expansionData.computeThermalExpansionFactors()
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_contractThermal(self):
        """Test contraction.

        Change fuel: isothermal and non-isothermal pass
        Change test fuel: isothermal pass, non-isothermal fail
        """
        for i, b in enumerate(filter(lambda b: b.hasFlags(Flags.FUEL), self.a), start=1):
            for c in b.iterChildrenWithFlags([Flags.FUEL, Flags.TEST, Flags.DEPLETABLE], exactMatch=True):
                newTemp = c.temperatureInC - 100.0 * i
                self.axialExpChngr.expansionData.updateComponentTemp(c, newTemp)
        self.axialExpChngr.expansionData.computeThermalExpansionFactors()
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_expandPrescribed(self):
        cList = []
        for b in filter(lambda b: b.hasFlags(Flags.FUEL), self.a):
            for c in b.iterChildrenWithFlags([Flags.FUEL, Flags.TEST, Flags.DEPLETABLE], exactMatch=True):
                cList.append(c)
        pList = zeros(len(cList)) + 1.2
        self.axialExpChngr.expansionData.setExpansionFactors(cList, pList)
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_contractPrescribed(self):
        cList = []
        for b in filter(lambda b: b.hasFlags(Flags.FUEL), self.a):
            for c in filter(lambda c: c.hasFlags(Flags.FUEL) and c.hasFlags(Flags.TEST), b):
                cList.append(c)
        pList = zeros(len(cList)) + 0.9
        self.axialExpChngr.expansionData.setExpansionFactors(cList, pList)
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_expandAndContractPrescribed(self):
        cList = []
        pList = []
        for i, b in enumerate(filter(lambda b: b.hasFlags(Flags.FUEL), self.a), start=1):
            for c in b.iterChildrenWithFlags(Flags.FUEL):
                if c.hasFlags(Flags.TEST):
                    pList.append(1.0 + 0.01 * i)
                else:
                    pList.append(1.0 - 0.01 * i)
                cList.append(c)
        self.axialExpChngr.expansionData.setExpansionFactors(cList, pList)
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def checkConservation(self):
        _newBHeight, _newCMassesByBlock, newTotalCMassByFlag = self.getMassesForTest(self.a)

        for origMass, (cFlag, newMass) in zip(self.origTotalCMassByFlag.values(), newTotalCMassByFlag.items()):
            self.assertAlmostEqual(origMass, newMass, places=self.places, msg=f"{cFlag} are not the same!")

        self.assertAlmostEqual(self.aRef.getTotalHeight(), self.a.getTotalHeight(), self.places)
