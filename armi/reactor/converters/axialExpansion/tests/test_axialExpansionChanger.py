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

"""Test axialExpansionChanger."""
import os
import unittest
from statistics import mean

from armi.materials import custom
from armi.reactor.assemblies import HexAssembly, grids
from armi.reactor.blocks import HexBlock
from armi.reactor.converters.axialExpansion import getSolidComponents
from armi.reactor.converters.axialExpansion.axialExpansionChanger import (
    AxialExpansionChanger,
)
from armi.reactor.converters.axialExpansion.tests import AxialExpansionTestBase
from armi.reactor.converters.axialExpansion.tests.buildAxialExpAssembly import (
    buildTestAssembly,
    buildTestBlock,
    buildDummySodium,
)
from armi.reactor.flags import Flags
from armi.reactor.tests.test_reactors import loadTestReactor, reduceTestReactorRings
from armi.tests import TEST_ROOT
from numpy import array, linspace, zeros


class Temperature:
    """Create and store temperature grid/field for verification testing."""

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


class TestAxialExpansionHeight(AxialExpansionTestBase):
    """Verify that test assembly is expanded correctly."""

    def setUp(self):
        AxialExpansionTestBase.setUp(self)
        self.a = buildTestAssembly(materialName="FakeMat")

        self.temp = Temperature(
            self.a.getTotalHeight(), numTempGridPts=11, tempSteps=10
        )

        # get the right/expected answer
        self._generateComponentWiseExpectedHeight()

        # do the axial expansion
        for idt in range(self.temp.tempSteps):
            self.obj.performThermalAxialExpansion(
                self.a, self.temp.tempGrid, self.temp.tempField[idt, :], setFuel=True
            )
            self._getConservationMetrics(self.a)

    def tearDown(self):
        AxialExpansionTestBase.tearDown(self)

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
        """Calculate the expected height, external of AssemblyAxialExpansion()."""
        assem = buildTestAssembly(materialName="FakeMat")
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


class TestConservation(AxialExpansionTestBase):
    """Verify that conservation is maintained in assembly-level axial expansion."""

    def setUp(self):
        AxialExpansionTestBase.setUp(self)
        self.a = buildTestAssembly(materialName="FakeMat")

    def tearDown(self):
        AxialExpansionTestBase.tearDown(self)

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

    def test_ThermalExpansionContractionConservation_Simple(self):
        r"""Thermally expand and then contract to ensure original state is recovered.

        Notes
        -----
        Temperature field is always isothermal and initially at 25 C.
        """
        isothermalTempList = [100.0, 350.0, 250.0, 25.0]
        a = buildTestAssembly(materialName="HT9")
        origMesh = a.getAxialMesh()[:-1]
        origMasses, origNDens = self._getComponentMassAndNDens(a)
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
            axialExpChngr.performThermalAxialExpansion(a, tempGrid, tempField)
            newMasses, newNDens = self._getComponentMassAndNDens(a)
            self._checkMass(oldMasses, newMasses)
            self._checkNDens(oldNDens, newNDens, totGrowthFrac)

        # make sure that the assembly returned to the original state
        for orig, new in zip(origMesh, a.getAxialMesh()):
            self.assertAlmostEqual(orig, new, places=12)
        self._checkMass(origMasses, newMasses)
        self._checkNDens(origNDens, newNDens, 1.0)

    def test_ThermalExpansionContractionConservation_Complex(self):
        r"""Thermally expand and then contract to ensure original state is recovered.

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
            if a.hasFlags([Flags.MIDDLE, Flags.ANNULAR, Flags.TEST]):
                # assemblies with the above flags have liners and conservation
                # of such assemblies is not currently supported
                continue
            self.complexConservationTest(a)

    def complexConservationTest(self, a):
        origMesh = a.getAxialMesh()[:-1]
        origMasses, origNDens = self._getComponentMassAndNDens(a)
        axialExpChngr = AxialExpansionChanger(detailedAxialExpansion=True)
        axialExpChngr.setAssembly(a)
        tempAdjust = [50.0, 50.0, -50.0, -50.0]
        for temp in tempAdjust:
            # adjust component temperatures by temp
            for b in a:
                for c in getSolidComponents(b):
                    axialExpChngr.expansionData.updateComponentTemp(
                        c, c.temperatureInC + temp
                    )
            # get U235/B10 and FE56 mass pre-expansion
            prevFE56Mass = a.getMass("FE56")
            prevMass = self._getMass(a)
            # compute thermal expansion coeffs and expand
            axialExpChngr.expansionData.computeThermalExpansionFactors()
            axialExpChngr.axiallyExpandAssembly()
            # ensure that total U235/B10 and FE56 mass is conserved post-expansion
            newFE56Mass = a.getMass("FE56")
            newMass = self._getMass(a)
            self.assertAlmostEqual(
                newFE56Mass / prevFE56Mass, 1.0, places=14, msg=f"{a}"
            )
            if newMass:
                self.assertAlmostEqual(newMass / prevMass, 1.0, places=14, msg=f"{a}")

        newMasses, newNDens = self._getComponentMassAndNDens(a)
        # make sure that the assembly returned to the original state
        for orig, new in zip(origMesh, a.getAxialMesh()):
            self.assertAlmostEqual(orig, new, places=12, msg=f"{a}")
        self._checkMass(origMasses, newMasses)
        self._checkNDens(origNDens, newNDens, 1.0)

    @staticmethod
    def _getMass(a):
        """Get the mass of an assembly. The conservation of HT9 pins in shield assems
        are accounted for in FE56 conservation checks.
        """
        newMass = None
        if a.hasFlags(Flags.FUEL):
            newMass = a.getMass("U235")
        elif a.hasFlags(Flags.CONTROL):
            newMass = a.getMass("B10")
        return newMass

    def test_PrescribedExpansionContractionConservation(self):
        """Expand all components and then contract back to original state.

        Notes
        -----
        - uniform expansion over all components within the assembly
        - 10 total expansion steps: 5 at +1.01 L1/L0, and 5 at -(1.01^-1) L1/L0
        """
        a = buildTestAssembly(materialName="FakeMat")
        axExpChngr = AxialExpansionChanger()
        origMesh = a.getAxialMesh()
        origMasses, origNDens = self._getComponentMassAndNDens(a)
        componentLst = [c for b in a for c in getSolidComponents(b)]
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
            axExpChngr.performPrescribedAxialExpansion(
                a, componentLst, fracLst, setFuel=True
            )
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

    @staticmethod
    def _getComponentMassAndNDens(a):
        masses = {}
        nDens = {}
        for b in a:
            for c in getSolidComponents(b):
                masses[c] = c.getMass()
                nDens[c] = c.getNumberDensities()
        return masses, nDens

    def test_TargetComponentMassConservation(self):
        """Tests mass conservation for target components."""
        self.expandAssemForMassConservationTest()
        for cName, masses in self.componentMass.items():
            for i in range(1, len(masses)):
                self.assertAlmostEqual(
                    masses[i], masses[i - 1], msg=f"{cName} mass not right"
                )

        for cName, density in self.componentDensity.items():
            for i in range(1, len(density)):
                self.assertLess(
                    density[i], density[i - 1], msg=f"{cName} density not right."
                )

        for i in range(1, len(self.totalAssemblySteelMass)):
            self.assertAlmostEqual(
                self.totalAssemblySteelMass[i],
                self.totalAssemblySteelMass[i - 1],
                msg="Total assembly steel mass is not conserved.",
            )

    def test_NoMovementACLP(self):
        """Ensures that above core load pad (ACLP) does not move during fuel-only expansion."""
        # build test assembly with ACLP
        assembly = HexAssembly("testAssemblyType")
        assembly.spatialGrid = grids.axialUnitGrid(numCells=1)
        assembly.spatialGrid.armiObject = assembly
        assembly.add(buildTestBlock("shield", "FakeMat", 25.0, 10.0))
        assembly.add(buildTestBlock("fuel", "FakeMat", 25.0, 10.0))
        assembly.add(buildTestBlock("fuel", "FakeMat", 25.0, 10.0))
        assembly.add(buildTestBlock("plenum", "FakeMat", 25.0, 10.0))
        assembly.add(
            buildTestBlock("aclp", "FakeMat", 25.0, 10.0)
        )  # "aclp plenum" also works
        assembly.add(buildTestBlock("plenum", "FakeMat", 25.0, 10.0))
        assembly.add(buildDummySodium(25.0, 10.0))
        assembly.calculateZCoords()
        assembly.reestablishBlockOrder()

        # get zCoords for aclp
        aclp = assembly.getChildrenWithFlags(Flags.ACLP)[0]
        aclpZTop = aclp.p.ztop
        aclpZBottom = aclp.p.zbottom

        # expand fuel
        # get fuel components
        cList = [c for b in assembly for c in b if c.hasFlags(Flags.FUEL)]
        # 1.01 L1/L0 growth of fuel components
        pList = zeros(len(cList)) + 1.01
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
        o, self.r = loadTestReactor(TEST_ROOT)
        reduceTestReactorRings(self.r, o.cs, 3)

        self.oldAxialMesh = self.r.core.p.axialMesh
        # expand refAssem by 1.01 L1/L0
        componentLst = [c for b in self.r.core.refAssem for c in b]
        expansionGrowthFracs = 1.01 + zeros(len(componentLst))
        self.axialExpChngr.performPrescribedAxialExpansion(
            self.r.core.refAssem, componentLst, expansionGrowthFracs, setFuel=True
        )

    def test_manageCoreMesh(self):
        self.axialExpChngr.manageCoreMesh(self.r)
        newAxialMesh = self.r.core.p.axialMesh
        # skip first and last entries as they do not change
        for old, new in zip(self.oldAxialMesh[1:-1], newAxialMesh[1:-1]):
            self.assertLess(old, new)


class TestExceptions(AxialExpansionTestBase):
    """Verify exceptions are caught."""

    def setUp(self):
        AxialExpansionTestBase.setUp(self)
        self.a = buildTestAssembly(materialName="FakeMatException")
        self.obj.setAssembly(self.a)

    def tearDown(self):
        AxialExpansionTestBase.tearDown(self)

    def test_isTopDummyBlockPresent(self):
        # build test assembly without dummy
        assembly = HexAssembly("testAssemblyType")
        assembly.spatialGrid = grids.axialUnitGrid(numCells=1)
        assembly.spatialGrid.armiObject = assembly
        assembly.add(buildTestBlock("shield", "FakeMat", 25.0, 10.0))
        assembly.calculateZCoords()
        assembly.reestablishBlockOrder()
        # create instance of expansion changer
        obj = AxialExpansionChanger(detailedAxialExpansion=True)
        with self.assertRaises(RuntimeError) as cm:
            obj.setAssembly(assembly)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_AssemblyAxialExpansionException(self):
        """Test that negative height exception is caught."""
        # manually set axial exp target component for code coverage
        self.a[0].p.axialExpTargetComponent = self.a[0][0].name
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


class TestGetSolidComponents(unittest.TestCase):
    """Verify that getSolidComponents returns just solid components."""

    def setUp(self):
        self.a = buildTestAssembly(materialName="HT9")

    def test_getSolidComponents(self):
        for b in self.a:
            for c in getSolidComponents(b):
                self.assertNotEqual(c.material.name, "Sodium")


class TestInputHeightsConsideredHot(unittest.TestCase):
    """Verify thermal expansion for process loading of core."""

    def setUp(self):
        """This test uses a different armiRun.yaml than the default."""
        o, r = loadTestReactor(
            os.path.join(TEST_ROOT, "detailedAxialExpansion"),
            customSettings={"inputHeightsConsideredHot": True},
        )
        reduceTestReactorRings(r, o.cs, 5)

        self.stdAssems = [a for a in r.core.getAssemblies()]

        oCold, rCold = loadTestReactor(
            os.path.join(TEST_ROOT, "detailedAxialExpansion"),
            customSettings={"inputHeightsConsideredHot": False},
        )
        reduceTestReactorRings(rCold, oCold.cs, 5)

        self.testAssems = [a for a in rCold.core.getAssemblies()]

    def test_coldAssemblyExpansion(self):
        """Block heights are cold and should be expanded.

        Notes
        -----
        Two assertions here:
            1. total assembly height should be preserved (through use of top dummy block)
            2. in armi.tests.detailedAxialExpansion.refSmallReactorBase.yaml,
               Thot > Tinput resulting in a non-zero DeltaT. Each block in the
               expanded case should therefore be a different height than that of the standard case.
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
                if hasCustomMaterial:
                    checkColdBlockHeight(bStd, bExp, self.assertAlmostEqual, "the same")
                else:
                    checkColdBlockHeight(bStd, bExp, self.assertNotEqual, "different")
                if bStd.hasFlags(Flags.FUEL):
                    self.checkColdHeightBlockMass(bStd, bExp, Flags.FUEL, "U235")
                elif bStd.hasFlags(Flags.CONTROL):
                    self.checkColdHeightBlockMass(bStd, bExp, Flags.CONTROL, "B10")

                if not aStd.hasFlags(Flags.TEST) and not hasCustomMaterial:
                    for cExp in getSolidComponents(bExp):
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

    def checkColdHeightBlockMass(
        self, bStd: HexBlock, bExp: HexBlock, flagType: Flags, nuclide: str
    ):
        """Checks that nuclide masses for blocks with input cold heights and "inputHeightsConsideredHot": True are underpredicted.

        Notes
        -----
        If blueprints have cold blocks heights with "inputHeightsConsideredHot": True in the inputs, then
        the nuclide densities are thermally expanded but the block height is not. This ultimately results in
        nuclide masses being underpredicted relative to the case where both nuclide densities and block heights
        are thermally expanded.
        """
        # custom materials don't expand
        if not isinstance(bStd.getComponent(flagType).material, custom.Custom):
            self.assertGreater(bExp.getMass(nuclide), bStd.getMass(nuclide))


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
