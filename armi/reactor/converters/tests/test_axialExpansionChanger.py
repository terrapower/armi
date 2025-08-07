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

"""Test axialExpansionChanger."""

import collections
import copy
import os
import unittest
from statistics import mean
from typing import Callable

from attr import dataclass
from numpy import array, linspace, zeros

from armi import materials
from armi.materials import _MATERIAL_NAMESPACE_ORDER, custom
from armi.reactor.assemblies import HexAssembly, grids
from armi.reactor.blocks import HexBlock
from armi.reactor.components import Component, DerivedShape
from armi.reactor.components.basicShapes import Circle, Hexagon
from armi.reactor.converters.axialExpansionChanger import (
    AssemblyAxialLinkage,
    AxialExpansionChanger,
    ExpansionData,
    getSolidComponents,
    iterSolidComponents,
)
from armi.reactor.flags import Flags
from armi.testing import loadTestReactor
from armi.tests import TEST_ROOT
from armi.utils import units
from armi.utils.customExceptions import InputError


class AxialExpansionTestBase(unittest.TestCase):
    """Common methods and variables for unit tests."""

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

    @classmethod
    def setUpClass(cls):
        cls.origNameSpace = _MATERIAL_NAMESPACE_ORDER
        # set namespace order for materials so that fake HT9 material can be found
        materials.setMaterialNamespaceOrder(
            [
                "armi.reactor.converters.tests.test_axialExpansionChanger",
                "armi.materials",
            ]
        )

    def setUp(self):
        self.obj = AxialExpansionChanger()
        self.componentMass = collections.defaultdict(list)
        self.componentDensity = collections.defaultdict(list)
        self.totalAssemblySteelMass = []
        self.blockZtop = collections.defaultdict(list)

    @classmethod
    def tearDownClass(cls):
        # reset global namespace
        materials.setMaterialNamespaceOrder(cls.origNameSpace)

    def _getConservationMetrics(self, a):
        """Retrieves and stores various conservation metrics.

        - useful for verification and unittesting
        - Finds and stores:
            1. mass and density of target components
            2. mass of assembly steel
            3. block heights
        """
        totalSteelMass = 0.0
        for b in a:
            # store block ztop
            self.blockZtop[b].append(b.p.ztop)
            for c in iterSolidComponents(b):
                # store mass and density of component
                self.componentMass[c].append(c.getMass())
                self.componentDensity[c].append(c.material.getProperty("density", c.temperatureInK))
                # store steel mass for assembly
                if c.p.flags in self.Steel_Component_Lst:
                    totalSteelMass += c.getMass()

        self.totalAssemblySteelMass.append(totalSteelMass)


class Temperature:
    """Create and store temperature grid/field."""

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
        """Generate temperature field and grid.

        - all temperatures are in C
        - temperature field : temperature readings (e.g., from T/H calculation)
        - temperature grid : physical locations in which temperature is measured
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


class TestMultiPinConservation(AxialExpansionTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _oCold, rCold = loadTestReactor(
            os.path.join(TEST_ROOT, "detailedAxialExpansion"),
            customSettings={"inputHeightsConsideredHot": True},
        )
        cls.aRef = list(filter(lambda a: a.getType() == "multi pin fuel", rCold.blueprints.assemblies.values()))[0]

    def setUp(self):
        self.a = copy.deepcopy(self.aRef)
        self.origBHeight, self.origCMassesByBlock, self.origTotalCMassByFlag = self.getMassesForTest(self.a)
        self.axialExpChngr = AxialExpansionChanger()
        self.axialExpChngr.setAssembly(self.a)

    @staticmethod
    def getMassesForTest(a: HexAssembly):
        @dataclass
        class StoreMass:
            cFlags: str
            mass: float

        blockHeights: dict[HexBlock, float] = {}
        compMassByBlock: dict[HexBlock, StoreMass] = collections.defaultdict(list)
        totalCMassByFlags: dict[Flags, float] = collections.defaultdict(float)
        for b in a:
            # collect mass and height information
            blockHeights[b] = b.getHeight()
            for c in iterSolidComponents(b):
                totalCMassByFlags[c.p.flags] += c.getMass()
                compMassByBlock[b].append(StoreMass(c.p.flags, c.getMass()))

        return blockHeights, compMassByBlock, totalCMassByFlags

    def test_expandAndContractThermal(self):
        """
        change fuel and test fuel isothermal pass
        change fuel non-isothermal and test fuel isothermal pass
        change test fuel non-isothermal fail
        """
        for i, b in enumerate(filter(lambda b: b.hasFlags(Flags.FUEL), self.a), start=1):
            for c in filter(lambda c: c.hasFlags(Flags.FUEL), b):
                if c.hasFlags(Flags.TEST):
                    newTemp = c.temperatureInC + 150.0 * i
                else:
                    newTemp = c.temperatureInC + 50.0 * i
                self.axialExpChngr.expansionData.updateComponentTemp(c, newTemp)
        self.axialExpChngr.expansionData.computeThermalExpansionFactors()
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_expandThermal(self):
        """
        Change fuel: isothermal and non-isothermal pass
        Change test fuel: isothermal pass, non-isothermal fail
        """
        for i, b in enumerate(filter(lambda b: b.hasFlags(Flags.FUEL), self.a), start=1):
            for c in filter(lambda c: c.hasFlags(Flags.FUEL) and c.hasFlags(Flags.TEST), b):
                newTemp = c.temperatureInC + 100.0 * i
                self.axialExpChngr.expansionData.updateComponentTemp(c, newTemp)
        self.axialExpChngr.expansionData.computeThermalExpansionFactors()
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_contractThermal(self):
        """
        Change fuel: isothermal and non-isothermal pass
        Change test fuel: isothermal pass, non-isothermal fail
        """
        for i, b in enumerate(filter(lambda b: b.hasFlags(Flags.FUEL), self.a), start=1):
            for c in filter(lambda c: c.hasFlags(Flags.FUEL) and not c.hasFlags(Flags.TEST), b):
                newTemp = c.temperatureInC - 100.0 * i
                self.axialExpChngr.expansionData.updateComponentTemp(c, newTemp)
        self.axialExpChngr.expansionData.computeThermalExpansionFactors()
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_expandPrescribed(self):
        cList = []
        for b in filter(lambda b: b.hasFlags(Flags.FUEL), self.a):
            for c in filter(lambda c: c.hasFlags(Flags.FUEL) and c.hasFlags(Flags.TEST), b):
                cList.append(c)
        pList = zeros(len(cList)) + 1.2
        self.axialExpChngr.expansionData.setExpansionFactors(cList, pList)
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_contractPrescribed(self):
        cList = []
        for b in filter(lambda b: b.hasFlags(Flags.FUEL), self.a):
            for c in filter(lambda c: c.hasFlags(Flags.FUEL) and not c.hasFlags(Flags.TEST), b):
                cList.append(c)
        pList = zeros(len(cList)) + 0.9
        self.axialExpChngr.expansionData.setExpansionFactors(cList, pList)
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def test_expandAndContractPrescribed(self):
        cList = []
        pList = []
        for b in filter(lambda b: b.hasFlags(Flags.FUEL), self.a):
            for c in filter(lambda c: c.hasFlags(Flags.FUEL), b):
                if c.hasFlags(Flags.TEST):
                    pList.append(1.2)
                else:
                    pList.append(1.1)
                cList.append(c)
        self.axialExpChngr.expansionData.setExpansionFactors(cList, pList)
        self.axialExpChngr.axiallyExpandAssembly()
        self.checkConservation()

    def checkConservation(self):
        _newBHeight, _newCMassesByBlock, newTotalCMassByFlag = self.getMassesForTest(self.a)

        for block in _newCMassesByBlock.keys():
            print(f"\n{block.name}")
            for new, old in zip(_newCMassesByBlock[block], self.origCMassesByBlock[block]):
                print(new.cFlags, new.mass - old.mass)

        cFlags = list(newTotalCMassByFlag.keys())
        for i, (origMass, newMass) in enumerate(zip(self.origTotalCMassByFlag.values(), newTotalCMassByFlag.values())):
            print(cFlags[i], newMass - origMass)

        for i, (origMass, newMass) in enumerate(zip(self.origTotalCMassByFlag.values(), newTotalCMassByFlag.values())):
            self.assertAlmostEqual(origMass, newMass, places=10, msg=f"{cFlags[i]} are not the same!")

class TestAxialExpansionHeight(AxialExpansionTestBase):
    """Verify that test assembly is expanded correctly."""

    def setUp(self):
        super().setUp()
        self.a = buildTestAssemblyWithFakeMaterial(name="FakeMat")

        self.temp = Temperature(self.a.getTotalHeight(), numTempGridPts=11, tempSteps=10)

        # get the right/expected answer
        self._generateComponentWiseExpectedHeight()

        # do the axial expansion
        for idt in range(self.temp.tempSteps):
            self.obj.performThermalAxialExpansion(self.a, self.temp.tempGrid, self.temp.tempField[idt, :], setFuel=True)
            self._getConservationMetrics(self.a)

    def test_AssemblyAxialExpansionHeight(self):
        """Test the axial expansion gives correct heights for component-based expansion."""
        for idt in range(self.temp.tempSteps):
            for ib, b in enumerate(self.a):
                self.assertAlmostEqual(
                    self.trueZtop[ib, idt],
                    self.blockZtop[b][idt],
                    places=7,
                    msg=f"Block height is not correct. {b}; Temp Step = {idt}",
                )

    def _generateComponentWiseExpectedHeight(self):
        """Calculate the expected height, external of AssemblyAxialExpansion."""
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
                    dll = (0.02 * aveBlockTemp[ib, idt] - 0.02 * aveBlockTemp[ib, idt - 1]) / (
                        100.0 + 0.02 * aveBlockTemp[ib, idt - 1]
                    )
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


class TestConservation(AxialExpansionTestBase):
    """Verify that conservation is maintained in assembly-level axial expansion."""

    def setUp(self):
        super().setUp()
        self.a = buildTestAssemblyWithFakeMaterial(name="FakeMat")

    def expandAssemForMassConservationTest(self):
        """Do the thermal expansion and store conservation metrics of interest."""
        # create a semi-realistic/physical variable temperature grid over the assembly
        temp = Temperature(self.a.getTotalHeight(), numTempGridPts=11, tempSteps=10)
        for idt in range(temp.tempSteps):
            self.obj.performThermalAxialExpansion(
                self.a,
                temp.tempGrid,
                temp.tempField[idt, :],
            )
            self._getConservationMetrics(self.a)

    def test_thermExpansContractConserv_simple(self):
        """Thermally expand and then contract to ensure original state is recovered.

        .. test:: Thermally expand and then contract to ensure original assembly is recovered.
            :id: T_ARMI_AXIAL_EXP_THERM0
            :tests: R_ARMI_AXIAL_EXP_THERM

        Notes
        -----
        Temperature field is always isothermal and initially at 25 C.
        """
        isothermalTempList = [100.0, 350.0, 250.0, 25.0]
        a = buildTestAssemblyWithFakeMaterial(name="HT9")
        origMesh = a.getAxialMesh()[:-1]
        origMasses, origNDens = self._getComponentMassAndNDens(a)
        origDetailedNDens = self._setComponentDetailedNDens(a, origNDens)
        axialExpChngr = AxialExpansionChanger(detailedAxialExpansion=True)

        tempGrid = linspace(0.0, a.getHeight())
        for temp in isothermalTempList:
            # compute expected change in number densities
            c = a[0][0]
            radialGrowthFrac = c.material.getThermalExpansionDensityReduction(
                prevTempInC=c.temperatureInC, newTempInC=temp
            )
            axialGrowthFrac = c.getThermalExpansionFactor(T0=c.temperatureInC, Tc=temp)
            totGrowthFrac = axialGrowthFrac / radialGrowthFrac
            # Set new isothermal temp and expand
            tempField = array([temp] * len(tempGrid))
            oldMasses, oldNDens = self._getComponentMassAndNDens(a)
            oldDetailedNDens = self._getComponentDetailedNDens(a)
            axialExpChngr.performThermalAxialExpansion(a, tempGrid, tempField)
            newMasses, newNDens = self._getComponentMassAndNDens(a)
            newDetailedNDens = self._getComponentDetailedNDens(a)
            self._checkMass(oldMasses, newMasses)
            self._checkNDens(oldNDens, newNDens, totGrowthFrac)
            self._checkDetailedNDens(oldDetailedNDens, newDetailedNDens, totGrowthFrac)

        # make sure that the assembly returned to the original state
        for orig, new in zip(origMesh, a.getAxialMesh()):
            self.assertAlmostEqual(orig, new, places=12)
        self._checkMass(origMasses, newMasses)
        self._checkNDens(origNDens, newNDens, 1.0)
        self._checkDetailedNDens(origDetailedNDens, newDetailedNDens, 1.0)

    def test_thermExpansContractionConserv_complex(self):
        """Thermally expand and then contract to ensure original state is recovered.

        Notes
        -----
        Assemblies with liners are not supported and not considered for conservation testing.
        """
        _oCold, rCold = loadTestReactor(
            os.path.join(TEST_ROOT, "detailedAxialExpansion"),
            customSettings={"inputHeightsConsideredHot": False},
        )
        assems = list(rCold.blueprints.assemblies.values())
        for a in assems:
            if a.hasFlags([Flags.MIDDLE, Flags.ANNULAR]):
                # assemblies with the above flags have liners and conservation of such assemblies is
                # not currently supported
                continue
            self.complexConservationTest(a)

    def complexConservationTest(self, a: HexAssembly):
        origMesh = a.getAxialMesh()[:-1]
        origMasses, origNDens = self._getComponentMassAndNDens(a)
        axialExpChngr = AxialExpansionChanger(detailedAxialExpansion=True)
        axialExpChngr.setAssembly(a)
        tempAdjust = [50.0, 50.0, -50.0, -50.0]
        for temp in tempAdjust:
            # adjust component temperatures by temp
            for b in a:
                for c in iterSolidComponents(b):
                    axialExpChngr.expansionData.updateComponentTemp(c, c.temperatureInC + temp)
            # get U235/B10 and FE56 mass pre-expansion
            prevFE56Mass = a.getMass("FE56")
            if a.hasFlags([Flags.FUEL, Flags.CONTROL]):
                prevMass = a.getMass("U235" if a.hasFlags(Flags.FUEL) else "B10")
            # compute thermal expansion coeffs and expand
            axialExpChngr.expansionData.computeThermalExpansionFactors()
            axialExpChngr.axiallyExpandAssembly()
            # ensure that total U235/B10 and FE56 mass is conserved post-expansion
            newFE56Mass = a.getMass("FE56")
            self.assertAlmostEqual(newFE56Mass / prevFE56Mass, 1.0, places=14, msg=f"{a}")
            if a.hasFlags([Flags.FUEL, Flags.CONTROL]):
                newMass = a.getMass("U235" if a.hasFlags(Flags.FUEL) else "B10")
                self.assertAlmostEqual(newMass / prevMass, 1.0, places=14, msg=f"{a}")

        newMasses, newNDens = self._getComponentMassAndNDens(a)
        # make sure that the assembly returned to the original state
        for orig, new in zip(origMesh, a.getAxialMesh()):
            self.assertAlmostEqual(orig, new, places=12, msg=f"{a}")
        self._checkMass(origMasses, newMasses)
        self._checkNDens(origNDens, newNDens, 1.0)

    def test_prescribedExpansionContractionConservation(self):
        """Expand all components and then contract back to original state.

        .. test:: Expand all components and then contract back to original state.
            :id: T_ARMI_AXIAL_EXP_PRESC0
            :tests: R_ARMI_AXIAL_EXP_PRESC

        Notes
        -----
        - uniform expansion over all components within the assembly
        - 10 total expansion steps: 5 at +1.01 L1/L0, and 5 at -(1.01^-1) L1/L0
        """
        a = buildTestAssemblyWithFakeMaterial(name="FakeMat")
        axExpChngr = AxialExpansionChanger()
        origMesh = a.getAxialMesh()
        origMasses, origNDens = self._getComponentMassAndNDens(a)
        componentLst = [c for b in a for c in iterSolidComponents(b)]
        expansionGrowthFrac = 1.01
        contractionGrowthFrac = 1.0 / expansionGrowthFrac
        for i in range(0, 10):
            if i < 5:
                growthFrac = expansionGrowthFrac
                fracLst = growthFrac + zeros(len(componentLst))
            else:
                growthFrac = contractionGrowthFrac
                fracLst = growthFrac + zeros(len(componentLst))
            oldMasses, oldNDens = self._getComponentMassAndNDens(a)
            # do the expansion
            axExpChngr.performPrescribedAxialExpansion(a, componentLst, fracLst, setFuel=True)
            newMasses, newNDens = self._getComponentMassAndNDens(a)
            self._checkMass(oldMasses, newMasses)
            self._checkNDens(oldNDens, newNDens, growthFrac)

        # make sure that the assembly returned to the original state
        for orig, new in zip(origMesh, a.getAxialMesh()):
            self.assertAlmostEqual(orig, new, places=13)
        self._checkMass(origMasses, newMasses)
        self._checkNDens(origNDens, newNDens, 1.0)

    def _checkMass(self, prevMass, newMass):
        for prev, new in zip(prevMass.values(), newMass.values()):
            # scaling helps check the assertion closer to machine precision
            ave = (new + prev) / 2.0
            prevScaled = prev / ave
            newScaled = new / ave
            self.assertAlmostEqual(prevScaled, newScaled, places=14)

    def _checkNDens(self, prevNDen, newNDens, ratio):
        for prevComp, newComp in zip(prevNDen.values(), newNDens.values()):
            for prev, new in zip(prevComp.values(), newComp.values()):
                if prev:
                    self.assertAlmostEqual(prev / new, ratio, msg=f"{prev} / {new}")

    def _checkDetailedNDens(self, prevDetailedNDen, newDetailedNDens, ratio):
        """Check whether the detailedNDens of two input dictionaries containing the detailedNDens
        arrays for all components of an assembly are conserved.
        """
        for prevComp, newComp in zip(prevDetailedNDen.values(), newDetailedNDens.values()):
            for prev, new in zip(prevComp, newComp):
                if prev:
                    self.assertAlmostEqual(prev / new, ratio, msg=f"{prev} / {new}")

    @staticmethod
    def _getComponentMassAndNDens(a):
        masses = {}
        nDens = {}
        for b in a:
            for c in iterSolidComponents(b):
                masses[c] = c.getMass()
                nDens[c] = c.getNumberDensities()
        return masses, nDens

    @staticmethod
    def _setComponentDetailedNDens(a, nDens):
        """Returns a dictionary that contains detailedNDens for all components in an assembly object
        input which are set to the corresponding component number densities from a number density
        dictionary input.
        """
        detailedNDens = {}
        for b in a:
            for c in getSolidComponents(b):
                c.p.detailedNDens = copy.deepcopy([val for val in nDens[c].values()])
                detailedNDens[c] = c.p.detailedNDens
        return detailedNDens

    @staticmethod
    def _getComponentDetailedNDens(a):
        """Returns a dictionary containing all solid components and their corresponding
        detailedNDens from an assembly object input.
        """
        detailedNDens = {}
        for b in a:
            for c in getSolidComponents(b):
                detailedNDens[c] = copy.deepcopy(c.p.detailedNDens)
        return detailedNDens

    def test_targetComponentMassConservation(self):
        """Tests mass conservation for target components."""
        self.expandAssemForMassConservationTest()
        for cName, masses in self.componentMass.items():
            for i in range(1, len(masses)):
                self.assertAlmostEqual(masses[i], masses[i - 1], msg=f"{cName} mass not right")

        for cName, density in self.componentDensity.items():
            for i in range(1, len(density)):
                self.assertLess(density[i], density[i - 1], msg=f"{cName} density not right.")

        for i in range(1, len(self.totalAssemblySteelMass)):
            self.assertAlmostEqual(
                self.totalAssemblySteelMass[i],
                self.totalAssemblySteelMass[i - 1],
                msg="Total assembly steel mass is not conserved.",
            )

    def test_noMovementACLP(self):
        """Ensures the above core load pad (ACLP) does not move during fuel-only expansion.

        .. test:: Ensure the ACLP does not move during fuel-only expansion.
            :id: T_ARMI_AXIAL_EXP_PRESC1
            :tests: R_ARMI_AXIAL_EXP_PRESC

        .. test:: Ensure the component volumes are correctly updated during prescribed expansion.
            :id: T_ARMI_AXIAL_EXP_PRESC2
            :tests: R_ARMI_AXIAL_EXP_PRESC
        """
        # build test assembly with ACLP
        assembly = HexAssembly("testAssemblyType")
        assembly.spatialGrid = grids.AxialGrid.fromNCells(numCells=1)
        assembly.spatialGrid.armiObject = assembly
        assembly.add(_buildTestBlock("shield", "FakeMat", 25.0, 10.0))
        assembly.add(_buildTestBlock("fuel", "FakeMat", 25.0, 10.0))
        assembly.add(_buildTestBlock("fuel", "FakeMat", 25.0, 10.0))
        assembly.add(_buildTestBlock("plenum", "FakeMat", 25.0, 10.0))
        assembly.add(_buildTestBlock("aclp", "FakeMat", 25.0, 10.0))  # "aclp plenum" also works
        assembly.add(_buildTestBlock("plenum", "FakeMat", 25.0, 10.0))
        assembly.add(_buildDummySodium(25.0, 10.0))
        assembly.calculateZCoords()
        assembly.reestablishBlockOrder()

        # get zCoords for aclp
        aclp = assembly.getChildrenWithFlags(Flags.ACLP)[0]
        aclpZTop = aclp.p.ztop
        aclpZBottom = aclp.p.zbottom

        # get total assembly fluid mass pre-expansion
        preExpAssemFluidMass = self._getTotalAssemblyFluidMass(assembly)

        # expand fuel
        # get fuel components
        cList = [c for b in assembly for c in b if c.hasFlags(Flags.FUEL)]
        # 1.01 L1/L0 growth of fuel components
        pList = zeros(len(cList)) + 1.01
        chngr = AxialExpansionChanger()
        chngr.performPrescribedAxialExpansion(assembly, cList, pList, setFuel=True)

        # get total assembly fluid mass post-expansion
        postExpAssemFluidMass = self._getTotalAssemblyFluidMass(assembly)

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

        # verify that the component volumes are correctly updated
        for b in assembly:
            for c in b:
                self.assertAlmostEqual(
                    c.getArea() * b.getHeight(),
                    c.getVolume(),
                    places=12,
                )
        # verify that the total assembly fluid mass is preserved through expansion
        self.assertAlmostEqual(preExpAssemFluidMass, postExpAssemFluidMass, places=11)

    @staticmethod
    def _getTotalAssemblyFluidMass(assembly) -> float:
        totalAssemblyFluidMass = 0.0
        for b in assembly:
            for c in b:
                if isinstance(c.material, materials.material.Fluid):
                    totalAssemblyFluidMass += c.getMass()
        return totalAssemblyFluidMass

    def test_reset(self):
        self.obj.setAssembly(self.a)
        self.obj.reset()
        self.assertIsNone(self.obj.linked)
        self.assertIsNone(self.obj.expansionData)

    def test_computeThermalExpansionFactors(self):
        """Ensure expansion factors are as expected."""
        self.obj.setAssembly(self.a)
        stdThermExpFactor = {}
        newTemp = 500.0
        # apply new temp to the pin and clad components of each block
        for b in self.a:
            for c in b[0:2]:
                stdThermExpFactor[c] = c.getThermalExpansionFactor()
                self.obj.expansionData.updateComponentTemp(c, newTemp)

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
                        1.0,
                        msg=f"Block {b}, Component {c}, thermExpCoeff not right.\n",
                    )


class TestManageCoreMesh(unittest.TestCase):
    """Verify that manage core mesh unifies the mesh for detailedAxialExpansion: False."""

    def setUp(self):
        self.axialExpChngr = AxialExpansionChanger()
        _o, self.r = loadTestReactor(os.path.join(TEST_ROOT, "detailedAxialExpansion"))

        self.oldAxialMesh = self.r.core.p.axialMesh
        self.componentLst = []
        for b in self.r.core.refAssem:
            if b.hasFlags([Flags.FUEL, Flags.PLENUM]):
                self.componentLst.extend(getSolidComponents(b))
        # expand refAssem by 1.01 L1/L0
        expansionGrowthFracs = 1.01 + zeros(len(self.componentLst))
        (
            self.origDetailedNDens,
            self.origVolumes,
        ) = self._getComponentDetailedNDensAndVol(self.componentLst)
        self.axialExpChngr.performPrescribedAxialExpansion(
            self.r.core.refAssem, self.componentLst, expansionGrowthFracs, setFuel=True
        )

    def test_manageCoreMesh(self):
        self.axialExpChngr.manageCoreMesh(self.r)
        newAxialMesh = self.r.core.p.axialMesh
        # all solid components in fuel + plenum block expand so the first three points are not expected to change
        for old, new in zip(self.oldAxialMesh[3:-1], newAxialMesh[3:-1]):
            self.assertLess(old, new)

    def test_componentConservation(self):
        self.axialExpChngr.manageCoreMesh(self.r)
        newDetailedNDens, newVolumes = self._getComponentDetailedNDensAndVol(self.componentLst)
        for c in newVolumes.keys():
            self._checkMass(
                self.origDetailedNDens[c],
                self.origVolumes[c],
                newDetailedNDens[c],
                newVolumes[c],
                c,
            )

    def _getComponentDetailedNDensAndVol(self, componentLst):
        """Returns a tuple containing dictionaries of detailedNDens and volumes of all components
        from a component list input.
        """
        detailedNDens = {}
        volumes = {}
        for c in componentLst:
            c.p.detailedNDens = [val for val in c.getNumberDensities().values()]
            detailedNDens[c] = copy.deepcopy(c.p.detailedNDens)
            volumes[c] = c.getVolume()
        return (detailedNDens, volumes)

    def _checkMass(self, origDetailedNDens, origVolume, newDetailedNDens, newVolume, c):
        for prevMass, newMass in zip(origDetailedNDens * origVolume, newDetailedNDens * newVolume):
            if c.parent.hasFlags(Flags.FUEL):
                self.assertAlmostEqual(prevMass, newMass, delta=1e-12, msg=f"{c}, {c.parent}")
            else:
                # should not conserve mass here as it is structural material above active fuel
                self.assertAlmostEqual(newMass / prevMass, 1.00, msg=f"{c}, {c.parent}")


class TestExceptions(AxialExpansionTestBase):
    """Verify exceptions are caught."""

    def setUp(self):
        super().setUp()
        self.a = buildTestAssemblyWithFakeMaterial(name="FakeMatException")
        self.obj.setAssembly(self.a)

    def test_isTopDummyBlockPresent(self):
        # build test assembly without dummy
        assembly = HexAssembly("testAssemblyType")
        assembly.spatialGrid = grids.AxialGrid.fromNCells(numCells=1)
        assembly.spatialGrid.armiObject = assembly
        assembly.add(_buildTestBlock("shield", "FakeMat", 25.0, 10.0))
        assembly.calculateZCoords()
        assembly.reestablishBlockOrder()
        # create instance of expansion changer
        obj = AxialExpansionChanger(detailedAxialExpansion=True)
        with self.assertRaisesRegex(
            RuntimeError,
            "Cannot run detailedAxialExpansion without a dummy block at the top of the assembly!",
        ):
            obj.setAssembly(assembly)

    def test_setExpansionFactors(self):
        cList = self.a.getFirstBlock().getChildren()
        with self.assertRaisesRegex(
            RuntimeError,
            "Number of components and expansion fractions must be the same!",
        ):
            self.obj.expansionData.setExpansionFactors(cList, range(len(cList) + 1))

        with self.assertRaisesRegex(
            RuntimeError,
            "L1/L0, is not physical. Expansion fractions should be greater than 0.0.",
        ):
            self.obj.expansionData.setExpansionFactors(cList, zeros(len(cList)))

        with self.assertRaisesRegex(
            RuntimeError,
            "L1/L0, is not physical. Expansion fractions should be greater than 0.0.",
        ):
            self.obj.expansionData.setExpansionFactors(cList, zeros(len(cList)) - 10.0)

    def test_updateCompTempsBy1DTempFieldValError(self):
        tempGrid = [5.0, 15.0, 35.0]
        tempField = linspace(25.0, 310.0, 3)
        with self.assertRaisesRegex(ValueError, "has no temperature points within it!"):
            self.obj.expansionData.updateComponentTempsBy1DTempField(tempGrid, tempField)

    def test_updateCompTempsBy1DTempFieldError(self):
        tempGrid = [5.0, 15.0, 35.0]
        tempField = linspace(25.0, 310.0, 10)
        with self.assertRaisesRegex(RuntimeError, "tempGrid and tempField must have the same length."):
            self.obj.expansionData.updateComponentTempsBy1DTempField(tempGrid, tempField)

    def test_AssemblyAxialExpansionException(self):
        """Test that negative height exception is caught."""
        # manually set axial exp target component for code coverage
        self.a[0].p.axialExpTargetComponent = self.a[0][0].name
        temp = Temperature(self.a.getTotalHeight(), numTempGridPts=11, tempSteps=10)
        with self.assertRaisesRegex(ArithmeticError, "has a negative height!"):
            for idt in range(temp.tempSteps):
                self.obj.expansionData.updateComponentTempsBy1DTempField(temp.tempGrid, temp.tempField[idt, :])
                self.obj.expansionData.computeThermalExpansionFactors()
                self.obj.axiallyExpandAssembly()

    def test_isFuelLocked(self):
        """Ensures that the RuntimeError statement in ExpansionData::_isFuelLocked is raised
        appropriately.

        Notes
        -----
        This is implemented by creating a fuel block that contains no fuel component and passing it
        to ExpansionData::_isFuelLocked.
        """
        expdata = ExpansionData(HexAssembly("testAssemblyType"), setFuel=True, expandFromTinputToThot=False)
        bNoFuel = HexBlock("fuel", height=10.0)
        shieldDims = {
            "Tinput": 25.0,
            "Thot": 25.0,
            "od": 0.76,
            "id": 0.00,
            "mult": 127.0,
        }
        shield = Circle("shield", "FakeMat", **shieldDims)
        bNoFuel.add(shield)
        with self.assertRaisesRegex(RuntimeError, f"No fuel component within {bNoFuel}!"):
            expdata._isFuelLocked(bNoFuel)


class TestDetermineTargetComponent(AxialExpansionTestBase):
    """Verify determineTargetComponent method is properly updating _componentDeterminesBlockHeight."""

    def setUp(self):
        super().setUp()
        self.expData = ExpansionData([], setFuel=True, expandFromTinputToThot=True)
        coolDims = {"Tinput": 25.0, "Thot": 25.0}
        self.coolant = DerivedShape("coolant", "Sodium", **coolDims)

    def test_getTargetComponent(self):
        b = HexBlock("fuel", height=10.0)
        fuelDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.76, "id": 0.00, "mult": 127.0}
        cladDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.80, "id": 0.77, "mult": 127.0}
        fuel = Circle("fuel", "FakeMat", **fuelDims)
        clad = Circle("clad", "FakeMat", **cladDims)
        b.add(fuel)
        b.add(clad)
        b.add(self.coolant)
        self.expData.setTargetComponent(b, True)
        self.assertEqual(fuel, self.expData.getTargetComponent(b))

    def test_getTargetComponent_NoneFound(self):
        b = HexBlock("fuel", height=10.0)
        with self.assertRaisesRegex(RuntimeError, f"No target component found for {b} in"):
            self.expData.getTargetComponent(b)

    def test_determineTargetComponent(self):
        """Provides coverage for searching TARGET_FLAGS_IN_PREFERRED_ORDER."""
        b = HexBlock("fuel", height=10.0)
        fuelDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.76, "id": 0.00, "mult": 127.0}
        cladDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.80, "id": 0.77, "mult": 127.0}
        fuel = Circle("fuel", "FakeMat", **fuelDims)
        clad = Circle("clad", "FakeMat", **cladDims)
        b.add(fuel)
        b.add(clad)
        b.add(self.coolant)
        self._checkTarget(b, fuel)

    def _checkTarget(self, b: HexBlock, expected: Component):
        """Call determineTargetMethod and compare what we get with expected."""
        # Value unset initially
        self.assertFalse(b.p.axialExpTargetComponent)
        target = self.expData.determineTargetComponent(b)
        self.assertIs(target, expected)
        self.assertTrue(
            self.expData.isTargetComponent(target),
            msg=f"determineTargetComponent failed to recognize intended component: {expected}",
        )
        self.assertEqual(
            b.p.axialExpTargetComponent,
            expected.name,
            msg=f"determineTargetComponent failed to recognize intended component: {expected}",
        )

    def test_determineTargetCompBlockWithMultiFlags(self):
        """Provides coverage for searching TARGET_FLAGS_IN_PREFERRED_ORDER with multiple flags."""
        # build a block that has two flags as well as a component matching each
        b = HexBlock("fuel poison", height=10.0)
        fuelDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.9, "id": 0.5, "mult": 200.0}
        poisonDims = {"Tinput": 25.0, "Thot": 25.0, "od": 0.5, "id": 0.0, "mult": 10.0}
        fuel = Circle("fuel", "FakeMat", **fuelDims)
        poison = Circle("poison", "FakeMat", **poisonDims)
        b.add(fuel)
        b.add(poison)
        b.add(self.coolant)
        self._checkTarget(b, fuel)

    def test_specifyTargetComp_NotFound(self):
        """Ensure RuntimeError gets raised when no target component is found."""
        b = HexBlock("fuel", height=10.0)
        b.add(self.coolant)
        b.setType("fuel")
        with self.assertRaisesRegex(RuntimeError, "No target component found!"):
            self.expData.determineTargetComponent(b)
        with self.assertRaisesRegex(RuntimeError, "No target component found!"):
            self.expData.determineTargetComponent(b, Flags.FUEL)

    def test_specifyTargetComp_singleSolid(self):
        """Ensures that specifyTargetComponent is smart enough to set the only solid as the target component."""
        b = HexBlock("plenum", height=10.0)
        ductDims = {"Tinput": 25.0, "Thot": 25.0, "op": 17, "ip": 0.0, "mult": 1.0}
        duct = Hexagon("duct", "FakeMat", **ductDims)
        b.add(duct)
        b.add(self.coolant)
        b.getVolumeFractions()
        b.setType("plenum")
        self._checkTarget(b, duct)

    def test_specifyTargetComp_MultiFound(self):
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
        fuel = Circle("fuel", "FakeMat", **fuelDims)
        fuelAnnular = Circle("fuel annular", "FakeMat", **fuelAnnularDims)
        b.add(fuel)
        b.add(fuelAnnular)
        b.add(self.coolant)
        b.setType("FuelBlock")
        with self.assertRaisesRegex(
            RuntimeError,
            "Cannot have more than one component within a block that has the target flag!",
        ):
            self.expData.determineTargetComponent(b, flagOfInterest=Flags.FUEL)

    def test_manuallySetTargetComponent(self):
        """
        Ensures that target components can be manually set (is done in practice via blueprints).

        .. test:: Allow user-specified target axial expansion components on a given block.
            :id: T_ARMI_MANUAL_TARG_COMP
            :tests: R_ARMI_MANUAL_TARG_COMP
        """
        b = HexBlock("dummy", height=10.0)
        ductDims = {"Tinput": 25.0, "Thot": 25.0, "op": 17, "ip": 0.0, "mult": 1.0}
        duct = Hexagon("duct", "FakeMat", **ductDims)
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
        self.expData._componentDeterminesBlockHeight[b.getComponentByName(b.p.axialExpTargetComponent)] = True
        self.assertTrue(self.expData.isTargetComponent(duct))


class TestGetSolidComponents(unittest.TestCase):
    """Verify that getSolidComponents returns just solid components."""

    def test_getSolidComponents(self):
        """Show that getSolidComponents produces a list of solids, and is consistent with iterSolidComponents."""
        a = buildTestAssemblyWithFakeMaterial(name="HT9")
        for b in a:
            solids = getSolidComponents(b)
            ids = set(map(id, solids))
            for c in iterSolidComponents(b):
                self.assertNotEqual(c.material.name, "Sodium")
                self.assertIn(id(c), ids, msg=f"Found non-solid {c}")
                ids.remove(id(c))
            self.assertFalse(
                ids,
                msg="Inconsistency between getSolidComponents and iterSolidComponents",
            )

    def test_checkForBlocksWithoutSolids(self):
        a = buildTestAssemblyWithFakeMaterial(name="Sodium")
        changer = AxialExpansionChanger()
        changer.linked = AssemblyAxialLinkage(a)
        with self.assertRaisesRegex(
            InputError,
            expected_regex="is constructed improperly for use with the axial expansion changer",
        ):
            changer._checkForBlocksWithoutSolids()


class TestInputHeightsConsideredHot(unittest.TestCase):
    """Verify thermal expansion for process loading of core."""

    def setUp(self):
        """This test uses a different armiRun.yaml than the default."""
        o, r = loadTestReactor(
            os.path.join(TEST_ROOT, "detailedAxialExpansion"),
            customSettings={"inputHeightsConsideredHot": True},
        )

        self.stdAssems = list(r.core)

        oCold, rCold = loadTestReactor(
            os.path.join(TEST_ROOT, "detailedAxialExpansion"),
            customSettings={"inputHeightsConsideredHot": False},
        )

        self.testAssems = list(rCold.core)

    def test_coldAssemblyExpansion(self):
        """Block heights are cold and should be expanded.

        .. test:: Preserve the total height of a compatible ARMI assembly.
            :id: T_ARMI_ASSEM_HEIGHT_PRES
            :tests: R_ARMI_ASSEM_HEIGHT_PRES

        .. test:: Axial expansion can be prescribed in blueprints for core construction.
            :id: T_ARMI_INP_COLD_HEIGHT
            :tests: R_ARMI_INP_COLD_HEIGHT

        Notes
        -----
        For R_ARMI_INP_COLD_HEIGHT, the action of axial expansion occurs in setUp() during core
        construction, specifically in
        :py:meth:`constructAssem <armi.reactor.blueprints.Blueprints.constructAssem>`

        Two assertions here:
            1. total assembly height should be preserved (through use of top dummy block)
            2. in armi.tests.detailedAxialExpansion.refSmallReactorBase.yaml, Thot > Tinput
               resulting in a non-zero DeltaT. Each block in the expanded case should therefore be a
               different height than that of the standard case.
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
                if any(isinstance(c.material, custom.Custom) for c in bStd):
                    checkColdBlockHeight(bStd, bExp, self.assertAlmostEqual, "the same")
                else:
                    checkColdBlockHeight(bStd, bExp, self.assertNotEqual, "different")
                    if bStd.hasFlags(Flags.FUEL):
                        self.checkColdHeightBlockMass(bStd, bExp, "U235")
                    elif bStd.hasFlags(Flags.CONTROL):
                        self.checkColdHeightBlockMass(bStd, bExp, "B10")
                    for cExp in iterSolidComponents(bExp):
                        if cExp.zbottom == bExp.p.zbottom and cExp.ztop == bExp.p.ztop:
                            matDens = cExp.material.density(Tc=cExp.temperatureInC)
                            compDens = cExp.density()
                            msg = (
                                f"{cExp} {cExp.material} in {bExp} in {aExp} was not at correct density. \n"
                                + f"expansion = {bExp.p.height / bStd.p.height} \n"
                                + f"density = {matDens}, component density = {compDens} \n"
                            )
                            self.assertAlmostEqual(
                                matDens,
                                compDens,
                                places=12,
                                msg=msg,
                            )

    def checkColdHeightBlockMass(self, bStd: HexBlock, bExp: HexBlock, nuclide: str):
        """Checks that nuclide masses for blocks with input cold heights and
        "inputHeightsConsideredHot": True are underpredicted.

        Notes
        -----
        If blueprints have cold blocks heights with "inputHeightsConsideredHot": True in the inputs,
        then the nuclide densities are thermally expanded but the block height is not. This
        ultimately results in nuclide masses being underpredicted relative to the case where both
        nuclide densities and block heights are thermally expanded.
        """
        self.assertGreater(bExp.getMass(nuclide), bStd.getMass(nuclide))


def checkColdBlockHeight(bStd: HexBlock, bExp: HexBlock, assertType: Callable, strForAssertion: str):
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


def buildTestAssemblyWithFakeMaterial(name: str, hot: bool = False):
    """Create test assembly consisting of list of fake material.

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
    assembly.spatialGrid = grids.AxialGrid.fromNCells(numCells=1)
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
    """Fake material used to verify armi.reactor.converters.axialExpansionChanger.

    Notes
    -----
    - specifically used in TestAxialExpansionHeight to verify axialExpansionChanger produces
      expected heights from hand calculation
    - also used to verify mass and height conservation resulting from even amounts of expansion and
      contraction. See TestConservation.
    """

    name = "FakeMat"

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """A fake linear expansion percent."""
        Tc = units.getTc(Tc, Tk)
        return 0.02 * Tc


class FakeMatException(materials.ht9.HT9):
    """Fake material used to verify TestExceptions.

    Notes
    -----
    - the only difference between this and `class Fake(HT9)` above is that the thermal expansion
      factor is higher to ensure that a negative block height is caught in
      TestExceptions:test_AssemblyAxialExpansionException.
    """

    name = "FakeMatException"

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """A fake linear expansion percent."""
        Tc = units.getTc(Tc, Tk)
        return 0.08 * Tc
