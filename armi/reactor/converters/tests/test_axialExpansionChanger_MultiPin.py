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
import io
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from numpy import full

from armi.materials.material import Fluid
from armi.reactor.blueprints import Blueprints
from armi.reactor.components.component import Component
from armi.reactor.converters.axialExpansionChanger.axialExpansionChanger import AxialExpansionChanger
from armi.reactor.converters.axialExpansionChanger.expansionData import iterSolidComponents
from armi.reactor.converters.tests.test_axialExpansionChanger import AxialExpansionTestBase
from armi.reactor.flags import Flags, TypeSpec
from armi.settings.caseSettings import Settings
from armi.testing.singleMixedAssembly import BLOCK_DEFINITIONS, GRID_DEFINITION, buildMixedPinAssembly

if TYPE_CHECKING:
    from armi.reactor.assemblies import HexAssembly
    from armi.reactor.blocks import HexBlock

FINE_ASSEMBLY_DEF = """
assemblies:
    multi pin fuel:
        specifier: LA
        blocks: [
            *block_grid_plate, *block_fuel_multiPin_axial_shield,
            *block_fuel_multiPin, *block_fuel_multiPin, *block_fuel_multiPin,
            *block_fuel_multiPin, *block_fuel_multiPin, *block_fuel_multiPin,
            *block_fuel_multiPin, *block_fuel_multiPin, *block_mixed_multiPin,
            *block_mixed_multiPin, *block_aclp_multiPin, *block_plenum_multiPin,
            *block_duct, *block_dummy
        ]
        height: [
            1.0, 1.0,
            0.5, 0.5, 0.5,
            0.5, 0.5, 0.5,
            0.5, 0.5, 1.0,
            1.0, 1.0, 1.0,
            1.0, 1.0
        ]
        axial mesh points: [
            1, 1,
            1, 1, 1,
            1, 1, 1,
            1, 1, 1,
            1, 1, 1,
            1, 1
        ]
        xs types: [
            A, A,
            B, B, B,
            B, B, B,
            B, B, C,
            C, D, D,
            A, A
        ]
"""  # noqa: E501


@dataclass
class StoreMassAndTemp:
    cType: str
    mass: float
    HMmass: float
    HMmassBOL: float
    HMmolesBOL: float
    temp: float


class TestMultiPinConservationBase(AxialExpansionTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.aRef = buildMixedPinAssembly()
        cls.places = 12

    def setUp(self):
        self.a = copy.deepcopy(self.aRef)
        self.axialExpChngr = AxialExpansionChanger()
        self.axialExpChngr.setAssembly(self.a)

    def _iterFuelBlocks(self):
        """Iterate over blocks in self.a that have Flags.FUEL. Enumerator index starts at 1 to support scaling
        block-wise values.
        """
        yield from enumerate(filter(lambda b: b.hasFlags(Flags.FUEL), self.a), start=1)


class TestRedistributeMass(TestMultiPinConservationBase):
    b0: "HexBlock"
    b1: "HexBlock"
    c0: Component
    origC0Temp: float
    c1: Component
    origC1Temp: float

    def setUp(self):
        super().setUp()
        self.b0 = self.a.getFirstBlock(Flags.FUEL)
        self.b1 = self.axialExpChngr.linked.linkedBlocks[self.b0].upper
        self.c0 = next(filter(lambda c: c.getType() == "fuel test", self.b0))
        self.c1 = self.axialExpChngr.linked.linkedComponents[self.c0].upper

    def test_shiftLinkedCompsForDelta(self):
        """Ensure that given a deltaZTop, component elevations are adjusted appropriately."""
        self._initializeTest(growFrac=1.0, fromComp=self.c0)  # setting fromComp is meaningless here
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
        """With no temperature changes anywere, grow c0 by 10% and show that 10% of the c0 mass is moved to c1.

        Notes
        -----
        - C0 grows resulting in c0 giving 10% of its mass to c1. c1 height does not change so its mass gains 10%.
        - Additional assertions on temperature exist to ensure that the component temperatures are managed correctly
        during the transfer of mass. For this test, since this is not thermal expansion, we show that the component
        temperatures do not change.
        """
        growFrac = 1.10
        self._initializeTest(growFrac, fromComp=self.c0)
        self._redistributeMassWithTempAssert(fromComp=self.c0, toComp=self.c1, thermalExp=False)

    def test_addMassToComponent_nonTargetCompression_noThermal(self):
        """With no temperature changes anywere, shrink c0 by 10% and show that 10% of the c1 mass is moved to c0.

        Notes
        -----
        - C0 shrinks resulting in c1 giving 10% of its mass to c0. c1 height does not change so it's mass loses 10%.
        - Additional assertions on temperature exist to ensure that the component temperatures are managed correctly
        during the transfer of mass. For this test, since this is not thermal expansion, we show that the component
        temperatures do not change.
        """
        growFrac = 0.9
        self._initializeTest(growFrac, fromComp=self.c1)
        self._redistributeMassWithTempAssert(fromComp=self.c1, toComp=self.c0, thermalExp=False)

    def test_addMassToComponent_nonTargetCompression_yesThermal(self):
        """Decrease c0 by 100 deg C and and show that c1 mass is moved to c0.

        Notes
        -----
        - C0 shrinks resulting in c1 giving X% of its mass to c0. c1 height does not change so its mass loses X%.
        - Additional assertions on temperature exist to ensure that the component temperatures are managed correctly
        during the transfer of mass. For this test, we show that the temperature of c0 increases and the temperature of
        c1 does not change. The increase in temperature for c0 is due to the contribution from the hotter c1 component.
        """
        newTemp = self.c0.temperatureInC - 100.0
        # updateComponentTemp updates ndens for update in AREA only
        self.axialExpChngr.expansionData.updateComponentTemp(self.c0, newTemp)
        self.axialExpChngr.expansionData.computeThermalExpansionFactors()
        growFrac = self.axialExpChngr.expansionData.getExpansionFactor(self.c0)

        self._initializeTest(growFrac, fromComp=self.c1)
        self._redistributeMassWithTempAssert(fromComp=self.c1, toComp=self.c0, thermalExp=True)

    def test_addMassToComponent_nonTargetExpansion_yesThermal(self):
        """Increase c0 by 100 deg C and and show that c0 mass is moved to c1.

        Notes
        -----
        - C0 expands resulting in c0 giving X% of its mass to c1. c0 height does not change so its mass loses X%.
        - Additional assertions on temperature exist to ensure that the component temperatures are managed correctly
        during the transfer of mass. For this test, we show that the temperature of c1 increases and the temperature of
        c0 does not change. The increase in temperature is due to the contribution from the hotter c0 component.
        """
        newTemp = self.c0.temperatureInC + 100.0
        # updateComponentTemp updates ndens for update in AREA only
        self.axialExpChngr.expansionData.updateComponentTemp(self.c0, newTemp)
        self.axialExpChngr.expansionData.computeThermalExpansionFactors()
        growFrac = self.axialExpChngr.expansionData.getExpansionFactor(self.c0)

        self._initializeTest(growFrac, fromComp=self.c0)
        self._redistributeMassWithTempAssert(fromComp=self.c0, toComp=self.c1, thermalExp=True)

    def _updateToCompElevations(self, toComp: Component):
        """Shift ``toComp`` based on expansion or contraction of ``fromComp``, as indicated by ``self.deltaZTop``.

        Notes
        -----
        If deltaZTop is negative, this indicates that ``fromComp`` has expanded and ``toComp`` needs to be shifted
        upwards. If deltaZtop is positive, this indicates that ``fromComp`` has contracted and ``toComp`` need to be
        shifted downwards.
        """
        if self.deltaZTop < 0.0:
            toComp.zbottom -= self.deltaZTop
            toComp.height -= self.deltaZTop
            toComp.ztop = toComp.zbottom + toComp.height
        else:
            toComp.ztop += self.deltaZTop
            toComp.height += self.deltaZTop
        # adjust b1 elevations based on c1
        toComp.parent.ztop = toComp.ztop
        toComp.parent.zbottom = toComp.zbottom
        toComp.parent.p.height = toComp.height
        toComp.parent.clearCache()

    def _updateFromCompElevations(self, fromComp: Component):
        if self.deltaZTop < 0.0:
            # adjust b1 elevations based on c1
            fromComp.ztop += self.deltaZTop
            fromComp.height += self.deltaZTop
        else:
            fromComp.zbottom += self.deltaZTop
            fromComp.height -= self.deltaZTop
        # adjust b0 elevations based on c0
        fromComp.parent.ztop = fromComp.ztop
        fromComp.parent.zbottom = fromComp.zbottom
        fromComp.parent.p.height = fromComp.parent.ztop - fromComp.parent.zbottom
        # clear the cache to update volume calculations
        fromComp.parent.clearCache()

    def _initializeTest(self, growFrac: float, fromComp: Component):
        """Initialize the tests.

        Notes
        -----
        1) Store reference mass and temperature information.
        1) Set elevations of components and blocks post-expansion.
        3) Store the amount of mass expeceted to be redistributed between components.
        """
        # set the original mass and temperature of the components post expansion and pre redistribution

        self.originalC0 = StoreMassAndTemp(
            self.c0.parent.name,
            self.c0.getMass(),
            self.c0.getHMMass(),
            self.c0.p.massHmBOL,
            self.c0.p.molesHmBOL,
            self.c0.temperatureInC,
        )
        self.originalC1 = StoreMassAndTemp(
            self.c1.parent.name,
            self.c1.getMass(),
            self.c1.getHMMass(),
            self.c1.p.massHmBOL,
            self.c1.p.molesHmBOL,
            self.c1.temperatureInC,
        )

        # adjust c0 elevations per growFrac
        self.c0.zbottom = self.b0.p.zbottom
        self.c0.height = self.b0.getHeight() * growFrac
        self.c0.ztop = self.c0.zbottom + self.c0.height
        # update the ndens of c0 for the change in height
        self.c0.changeNDensByFactor(1.0 / growFrac)

        # calculate deltaZTop to inform how much mass will be redistributed
        self.deltaZTop = self.b0.p.ztop - self.c0.ztop

        # set b0 elevations to match c0
        self.b0.p.zbottom = self.c0.zbottom
        self.b0.p.ztop = self.c0.ztop
        self.b0.p.height = self.b0.p.ztop - self.b0.p.zbottom
        # clear the cache to update volume calculations
        self.b0.clearCache()

        # initialize component elevations for self.b1
        for c in self.b1:
            c.zbottom = self.b1.p.zbottom
            c.height = self.b1.getHeight()
            c.ztop = c.zbottom + c.height
        self.b1.clearCache()

        if fromComp is self.c0:
            self.amountBeingRedistributed = self.originalC0.mass * abs(self.deltaZTop) / self.c0.height
            self.amountBeingRedistributedBOLMass = self.originalC0.HMmassBOL * abs(self.deltaZTop) / self.b0.p.heightBOL
            self.amountBeingRedistributedBOLMoles = (
                self.originalC0.HMmolesBOL * abs(self.deltaZTop) / self.b0.p.heightBOL
            )
        else:
            self.amountBeingRedistributed = self.originalC1.mass * abs(self.deltaZTop) / self.c1.height
            self.amountBeingRedistributedBOLMass = self.originalC1.HMmassBOL * abs(self.deltaZTop) / self.b1.p.heightBOL
            self.amountBeingRedistributedBOLMoles = (
                self.originalC1.HMmolesBOL * abs(self.deltaZTop) / self.b1.p.heightBOL
            )

    def _getReferenceData(self, fromComp: Component, toComp: Optional[Component]):
        """Pull the reference data needed for ``fromComp`` and ``toComp``."""
        fromCompRefData = self.originalC0 if fromComp.parent.name == self.originalC0.cType else self.originalC1
        if toComp is None:
            toCompRefData = None
        else:
            toCompRefData = self.originalC0 if toComp.parent.name == self.originalC0.cType else self.originalC1
        return fromCompRefData, toCompRefData

    def _redistributeMassWithTempAssert(self, fromComp: Component, toComp: Component, thermalExp: bool):
        """Perform the mass redistribution from ``fromComp`` to ``toComp``.

        Notes
        -----
        Two assertions are done: 1) the correct amount of mass is moved to ``toComp``. 2) the resulting temperatures
        for ``fromComp`` and ``toComp`` are correct.
        """
        # move mass from ``fromComp`` to ``toComp``
        self.axialExpChngr.redistributeMass(fromComp=fromComp, toComp=toComp, deltaZTop=self.deltaZTop)

        fromCompRefData, toCompRefData = self._getReferenceData(fromComp, toComp)
        self._updateToCompElevations(toComp=toComp)
        self._updateFromCompElevations(fromComp=fromComp)

        # ensure the toComp mass increases by amountBeingRedistributed
        self.assertAlmostEqual(
            toComp.getMass(),
            toCompRefData.mass + self.amountBeingRedistributed,
            places=self.places,
        )
        HMfrac = toCompRefData.HMmass / toCompRefData.mass
        self.assertAlmostEqual(
            toComp.getHMMass(),
            toCompRefData.HMmass + self.amountBeingRedistributed * HMfrac,
            places=self.places,
        )
        self.assertAlmostEqual(
            toComp.p.massHmBOL,
            toCompRefData.HMmassBOL + self.amountBeingRedistributedBOLMass,
            places=self.places,
        )
        self.assertAlmostEqual(
            toComp.p.molesHmBOL,
            toCompRefData.HMmolesBOL + self.amountBeingRedistributedBOLMoles,
            places=self.places,
        )

        # fromComp temperature should not change because we've only removed mass
        self.assertEqual(fromComp.temperatureInC, fromCompRefData.temp)
        # we expect the new temperature to be greater because we added mass from a
        # material with a higher temperature
        if thermalExp:
            self.assertGreater(toComp.temperatureInC, toCompRefData.temp)
        else:
            self.assertEqual(toComp.temperatureInC, toCompRefData.temp)

        # ensure the fromComp mass decreases by amountBeingRedistributed
        self.assertAlmostEqual(
            fromComp.getMass(), fromCompRefData.mass - self.amountBeingRedistributed, places=self.places
        )
        HMfrac = fromCompRefData.HMmass / fromCompRefData.mass
        self.assertAlmostEqual(
            fromComp.getHMMass(),
            fromCompRefData.HMmass - self.amountBeingRedistributed * HMfrac,
            places=self.places,
        )
        self.assertAlmostEqual(
            fromComp.p.massHmBOL,
            fromCompRefData.HMmassBOL - self.amountBeingRedistributedBOLMass,
            places=self.places,
        )
        self.assertAlmostEqual(
            fromComp.p.molesHmBOL,
            fromCompRefData.HMmolesBOL - self.amountBeingRedistributedBOLMoles,
            places=self.places,
        )


class TestMultiPinConservation(TestMultiPinConservationBase):
    def setUp(self):
        super().setUp()
        self.origTotalCMassByFlag = self.getTotalCompMassByFlag(self.a)

    @staticmethod
    def _isFluidButNotBond(c):
        """Determine if a component is a fluid, but not Bond."""
        return isinstance(c, Component) and isinstance(c.material, Fluid) and not c.hasFlags(Flags.BOND)

    def getTotalCompMassByFlag(self, a: "HexAssembly") -> dict[TypeSpec, float]:
        """Get the total mass of all components in the assembly, except Bond components.

        Notes
        -----
        The axial expansion changer does not consider the expansion or contraction of fluids and therefore their
        conservation is not guarunteed. The conservation of fluid mass is expected only if each component type on a
        block has 1) uniform expansion rates and 2) axially isothermal fluid temperatures. For multipin assemblies,
        the former is generally not met for Bond components; however since there is only one coolant and intercoolant
        component in general, the conservation of mass for these components expected if axially isothermal fluid
        temperatures are present.
        """
        totalCMassByFlags: dict[Flags, float] = collections.defaultdict(float)
        for b in a:
            for c in iterSolidComponents(b):
                totalCMassByFlags[c.p.flags] += c.getMass()
            for c in filter(self._isFluidButNotBond, b):
                totalCMassByFlags[c.p.flags] += c.getMass()

        return totalCMassByFlags

    def _iterTestFuelCompsOnBlock(self, b: "HexBlock"):
        """Iterate over components in b that exactly contain Flags.FUEL, Flags.TEST, and Flags.DEPLETABLE."""
        yield from b.iterChildrenWithFlags(Flags.FUEL | Flags.TEST | Flags.DEPLETABLE, exactMatch=True)

    def test_expandThermalBothFuel(self):
        """Perform thermal expansion on both fuel and test fuel components.

        Notes
        -----
        - Each block is scaled by an increasing temperature to simulate a variable axial temperature distribution.
        - The test fuel and fuel components are scaled by different temperatures to simulate each pin design
        existing at different temperatures.
        - The 150 deg C and 50 deg C based temperature changes are arbitrarily chosen.
        """
        for i, b in self._iterFuelBlocks():
            for c in b.iterChildrenWithFlags(Flags.FUEL):
                if c.hasFlags(Flags.TEST):
                    newTemp = c.temperatureInC + 150.0 * i
                else:
                    newTemp = c.temperatureInC + 50.0 * i
                self.axialExpChngr.expansionData.updateComponentTemp(c, newTemp)
        self.axialExpChngr.expansionData.computeThermalExpansionFactors()
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_roundTripThermalBothFuel(self):
        """Perform thermal expansion on both fuel and test fuel components and ensure that mass and total assembly
        height is recovered.

        Notes
        -----
        - Each block is scaled by an increasing temperature to simulate a variable axial temperature distribution.
        - The test fuel and fuel components are scaled by different temperatures to simulate each pin design
        existing at different temperatures.
        - The 75 deg C and 50 deg C based temperature changes are arbitrarily chosen.
        """
        tempAdjust = [50, -50]
        for temp in tempAdjust:
            for i, b in self._iterFuelBlocks():
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
        """Perform thermal expansion on the test fuel component.

        Notes
        -----
        - Each block is scaled by an increasing temperature to simulate a variable axial temperature distribution.
        - The 100 deg C based temperature changes is arbitrarily chosen.
        - An extra assertion in done in this test to ensure that isotopes uniquely found in each test are not dropped
          when moving mass between blocks.
        """
        search = lambda c: isinstance(c, Component) and c.hasFlags(
            Flags.FUEL | Flags.TEST | Flags.DEPLETABLE, exact=True
        )
        nucs = ["XE131", "I131", "NP237", "CM242"]
        for i, c in enumerate(self.a.iterChildren(deep=True, predicate=search)):
            self.assertEqual(c.getNumberDensity(nucs[i]), 0.0)
            c.setNumberDensity(nucs[i], 1e-3)

        # recalcualte the initial mass with the new isotope additions
        self.origTotalCMassByFlag = self.getTotalCompMassByFlag(self.a)

        for i, b in self._iterFuelBlocks():
            for c in self._iterTestFuelCompsOnBlock(b):
                newTemp = c.temperatureInC + 100.0 * i
                self.axialExpChngr.expansionData.updateComponentTemp(c, newTemp)
        self.axialExpChngr.expansionData.computeThermalExpansionFactors()
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

        expectedNucsPresent = [["XE131"], ["XE131", "I131"], ["I131", "NP237"], ["NP237", "CM242"]]
        for i, c in enumerate(self.a.iterChildren(deep=True, predicate=search)):
            for nuc in expectedNucsPresent[i]:
                self.assertNotEqual(c.getNumberDensity(nuc), 0.0, msg=f"{nuc} not present in {c}!")

    def test_contractThermal(self):
        """Perform thermal contraction on the test fuel component.

        Notes
        -----
        - Each block is scaled by a decreasing temperature to simulate a variable axial temperature distribution.
        - The -100 deg C based temperature changes is arbitrarily chosen.
        """
        for i, b in self._iterFuelBlocks():
            for c in self._iterTestFuelCompsOnBlock(b):
                newTemp = c.temperatureInC - 100.0 * i
                self.axialExpChngr.expansionData.updateComponentTemp(c, newTemp)
        self.axialExpChngr.expansionData.computeThermalExpansionFactors()
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_expandPrescribed(self):
        """Perform prescribed expansion on the test fuel component.

        Notes
        -----
        - The factor of 1.2 for component expansion is arbitrarily chosen. Note, if too large of a value is chosen,
        the upper block heights will go negative and the axial expansion changer will hit a RuntimeError.
        """
        cList = []
        for _i, b in self._iterFuelBlocks():
            for c in self._iterTestFuelCompsOnBlock(b):
                cList.append(c)
        pList = full(len(cList), 1.2)
        self.axialExpChngr.expansionData.setExpansionFactors(cList, pList)
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_contractPrescribed(self):
        """Perform prescribed contraction on the test fuel component.

        Notes
        -----
        - The factor of 0.9 for component contraction is arbitrarily chosen.
        """
        cList = []
        for _i, b in self._iterFuelBlocks():
            for c in self._iterTestFuelCompsOnBlock(b):
                cList.append(c)
        pList = full(len(cList), 0.9)
        self.axialExpChngr.expansionData.setExpansionFactors(cList, pList)
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_expandAndContractPrescribed(self):
        """Perform prescribed expansion and contraction on the test fuel component.

        Notes
        -----
        - Each block is scaled by a different value to simulate a variable axial expansion profile (e.g., burnup driven
        axial expansion commonly found in sodium fast reactors).
        - The factor of +/- 0.01 for component expansion/contraction is arbitrarily chosen. Note, if too large of a
        value is chosen, the upper block heights will go negative and the axial expansion changer will hit a
        RuntimeError.
        """
        cList = []
        pList = []
        for i, b in self._iterFuelBlocks():
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
        """Conservation of axial expansion is measured by ensuring the total assembly mass per component flag and total
        assembly height is the same post exapansion.
        """
        newTotalCMassByFlag = self.getTotalCompMassByFlag(self.a)
        for origMass, (cFlag, newMass) in zip(self.origTotalCMassByFlag.values(), newTotalCMassByFlag.items()):
            self.assertAlmostEqual(origMass, newMass, places=self.places, msg=f"{cFlag} are not the same!")

        self.assertAlmostEqual(self.aRef.getTotalHeight(), self.a.getTotalHeight(), places=self.places)


class TestExceptionForMultiPin(TestMultiPinConservationBase):
    def setUp(self):
        cs = Settings()
        with io.StringIO(BLOCK_DEFINITIONS + FINE_ASSEMBLY_DEF + GRID_DEFINITION) as stream:
            blueprints = Blueprints.load(stream)
            blueprints._prepConstruction(cs)
        self.a = list(blueprints.assemblies.values())[0]
        self.axialExpChngr = AxialExpansionChanger()
        self.axialExpChngr.setAssembly(self.a)

    def test_failExpansionNegativeHeight(self):
        """Purposefully fail."""
        cList = []
        for _i, b in self._iterFuelBlocks():
            for c in b.iterChildrenWithFlags(Flags.FUEL | Flags.DEPLETABLE, exactMatch=True):
                cList.append(c)
        pList = full(len(cList), 1.3)
        self.axialExpChngr.expansionData.setExpansionFactors(cList, pList)
        with self.assertRaisesRegex(ArithmeticError, expected_regex="has a negative height! This is unphysical."):
            self.axialExpChngr.axiallyExpandAssembly()
