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

"""Tests functionalities of components within ARMI."""

import copy
import math
import random
import unittest

import numpy as np
from numpy.testing import assert_allclose, assert_equal

from armi.materials import air, alloy200
from armi.materials.material import Material
from armi.reactor import components, flags
from armi.reactor.blocks import Block
from armi.reactor.components import (
    Circle,
    Component,
    ComponentType,
    Cube,
    DerivedShape,
    DifferentialRadialSegment,
    FilletedHexagon,
    Helix,
    Hexagon,
    HexHoledCircle,
    HoledHexagon,
    HoledRectangle,
    HoledSquare,
    NullComponent,
    RadialSegment,
    Rectangle,
    SolidRectangle,
    Sphere,
    Square,
    Triangle,
    UnshapedComponent,
    UnshapedVolumetricComponent,
    materials,
)
from armi.testing import loadTestReactor
from armi.utils.units import getTc


class MockCompositionDependentExpander(materials.Material):
    """Dummy material that has a composition-dependent thermal expansion coefficient."""

    def linearExpansionPercent(self, Tk: float = None, Tc: float = None) -> float:
        """
        Composition-dependent linear expansion coefficient.

        Parameters
        ----------
        Tk : float, optional
            Temperature in Kelvin.
        Tc : float, optional
            Temperature in Celsius.
        """
        alpha = 1.0e-5
        beta = 1.0e-5 * self.parent.getMassFrac("C")
        refTemp = 20
        return (alpha + beta) * getTc(Tc=Tc, Tk=Tk) * (Tc - refTemp)


class TestComponentFactory(unittest.TestCase):
    def getCircleVoidDict(self):
        return dict(
            shape="circle",
            name="gap",
            Tinput=25,
            Thot=600,
            od=2.1,
            id=0.0,
            mult=7,
            material="Void",
            isotopics="",
        )

    def getCircleFuelDict(self):
        return dict(
            shape="circle",
            name="fuel",
            Tinput=25,
            Thot=600,
            od=2.1,
            id=0.0,
            mult=7,
            material="UZr",
            isotopics="",
        )

    def test_factory(self):
        """Creating and verifying void and fuel components.

        .. test:: Example void and fuel components are initialized.
            :id: T_ARMI_COMP_DEF0
            :tests: R_ARMI_COMP_DEF
        """
        voidAttrs = self.getCircleVoidDict()
        voidComp = components.factory(voidAttrs.pop("shape"), [], voidAttrs)
        fuelAttrs = self.getCircleFuelDict()
        fuelComp = components.factory(fuelAttrs.pop("shape"), [], fuelAttrs)
        self.assertIsInstance(voidComp, components.Circle)
        self.assertIsInstance(voidComp.material, materials.Void)
        self.assertIsInstance(fuelComp, components.Circle)
        self.assertIsInstance(fuelComp.material, materials.UZr)

    def test_componentInitializationAndDuplication(self):
        """Initialize and duplicate a component, veifying the parameters.

        .. test:: Verify the parameters of an initialized component.
            :id: T_ARMI_COMP_DEF1
            :tests: R_ARMI_COMP_DEF
        """
        # populate the class/signature dict, and create a basis attrs
        attrs = {
            "name": "gap",
            "Tinput": 25,
            "Thot": 600,
            "material": "Void",
            "isotopics": "",
        }

        for i, (name, klass) in enumerate(ComponentType.TYPES.items()):
            # hack together a dictionary input
            thisAttrs = {k: 1.0 for k in set(klass.INIT_SIGNATURE).difference(attrs)}
            if "oR" in thisAttrs:
                thisAttrs["oR"] /= 20.0
            if "iR" in thisAttrs:
                thisAttrs["iR"] /= 20.0
            del thisAttrs["components"]
            thisAttrs.update(attrs)
            thisAttrs["name"] = f"banana{i}"
            if "modArea" in thisAttrs:
                thisAttrs["modArea"] = None
            component = components.factory(name, [], thisAttrs)
            duped = copy.deepcopy(component)
            for key, val in component.p.items():
                if key in ["numberDensities", "nuclides"]:
                    for i in range(len(val)):
                        self.assertEqual(val[i], duped.p[key][i])
                elif key not in ["area", "volume", "serialNum"]:
                    # they get recomputed
                    self.assertEqual(
                        val,
                        duped.p[key],
                        msg=f"Key: {key}, val1: {val}, val2: {duped.p[key]}",
                    )

    def test_factoryBadShapeName(self):
        badDict = self.getCircleFuelDict()
        with self.assertRaises(ValueError):
            components.factory("turtle", [], badDict)


class TestGeneralComponents(unittest.TestCase):
    """Base test for all individual component tests."""

    componentCls = Component
    componentMaterial = "HT9"
    componentDims = {"Tinput": 25.0, "Thot": 25.0}

    def setUp(self, component=None):
        """
        Most of the time nothing will be passed as `component` and the result will be stored in
        self, but you can also pass a component object as `component`, in which case the object will
        be returned with the `parent` attribute assigned.
        """

        class _Parent:
            def getSymmetryFactor(self):
                return 1.0

            def getHeight(self):
                return 1.0

            def clearCache(self):
                pass

            def __iter__(self):
                """Act like an iterator but don't actually iterate."""
                return iter(())

            derivedMustUpdate = False

        if component is None:
            self.component = self.componentCls("TestComponent", self.componentMaterial, **self.componentDims)
            self.component.parent = _Parent()
        else:
            component.parent = _Parent()
            return component


class TestComponentNDens(TestGeneralComponents):
    """Test component number density setting."""

    componentCls = Circle
    componentDims = {"Tinput": 25.0, "Thot": 25.0, "id": 0.0, "od": 0.5}

    def test_setNumberDensity(self):
        """Test setting a single number density.

        .. test:: Users can set Component number density.
            :id: T_ARMI_COMP_NUCLIDE_FRACS0
            :tests: R_ARMI_COMP_NUCLIDE_FRACS
        """
        component = self.component
        self.assertAlmostEqual(component.getNumberDensity("C"), 0.000780, 6)
        component.setNumberDensity("C", 0.57)
        self.assertEqual(component.getNumberDensity("C"), 0.57)

    def test_setNumberDensities(self):
        """Test setting multiple number densities.

        .. test:: Users can set Component number densities.
            :id: T_ARMI_COMP_NUCLIDE_FRACS1
            :tests: R_ARMI_COMP_NUCLIDE_FRACS
        """
        component = self.component
        self.assertAlmostEqual(component.getNumberDensity("MN"), 0.000426, 6)
        component.setNumberDensities({"C": 1, "MN": 0.58})
        self.assertEqual(component.getNumberDensity("C"), 1.0)
        self.assertEqual(component.getNumberDensity("MN"), 0.58)

    def test_setNumberDensitiesWithExpansion(self):
        expansionMaterial = MockCompositionDependentExpander()
        expansionMaterial.parent = self.component
        self.component.material = expansionMaterial
        component = self.component
        initialVolume = component.getVolume()
        component.temperatureInC = 50
        self.assertAlmostEqual(component.getNumberDensity("MN"), 0.000426, 6)
        component.setNumberDensities({"C": 1, "MN": 0.58})
        newVolume = component.getVolume()
        expansionFactor = initialVolume / newVolume
        self.assertEqual(component.getNumberDensity("C"), 1.0 * expansionFactor)
        self.assertEqual(component.getNumberDensity("MN"), 0.58 * expansionFactor)

    def test_changeNDensByFactor(self):
        """Test the ability to change just the component number densities."""
        referenceDensity = self.component.getNumberDensities()
        self.component.p.detailedNDens = None
        self.component.p.pinNDens = None
        scalingFactor = random.uniform(0, 10)
        self.component.changeNDensByFactor(scalingFactor)
        for nuc, refDens in referenceDensity.items():
            actual = self.component.getNumberDensity(nuc)
            self.assertEqual(actual, refDens * scalingFactor, msg=nuc)
        self.assertIsNone(self.component.p.detailedNDens)
        self.assertIsNone(self.component.p.pinNDens)

    def test_changeNDensByFactorWithExtraParams(self):
        """Test scaling other parameters when component number density is scaled."""
        referenceDensity = self.component.getNumberDensities()
        refDetailedNDens = np.random.random(100)
        # Use copy to avoid spoiling the reference data with in-place multiplication
        self.component.p.detailedNDens = refDetailedNDens.copy()
        # Array of number densities per pin
        refPinDens = np.random.random(size=(50, 10))
        self.component.p.pinNDens = refPinDens.copy()

        scalingFactor = random.uniform(0, 10)
        self.component.changeNDensByFactor(scalingFactor)

        for nuc, refDens in referenceDensity.items():
            actual = self.component.getNumberDensity(nuc)
            self.assertEqual(actual, refDens * scalingFactor)

        assert_allclose(self.component.p.detailedNDens, refDetailedNDens * scalingFactor, rtol=1e-6)
        assert_allclose(self.component.p.pinNDens, refPinDens * scalingFactor, rtol=1e-6)


class TestComponent(TestGeneralComponents):
    """Test the base component."""

    componentCls = Component

    def test_initializeComponentMaterial(self):
        """Creating component with single material.

        .. test:: Components are made of one material.
            :id: T_ARMI_COMP_1MAT0
            :tests: R_ARMI_COMP_1MAT
        """
        expectedName = "TestComponent"
        actualName = self.component.getName()
        expectedMaterialName = "HT9"
        actualMaterialName = self.component.material.getName()
        self.assertEqual(expectedName, actualName)
        self.assertEqual(expectedMaterialName, actualMaterialName)

    def test_solid_material(self):
        """Determine if material is solid.

        .. test:: Components have material properties.
            :id: T_ARMI_COMP_MAT
            :tests: R_ARMI_COMP_MAT
        """
        self.assertTrue(isinstance(self.component.getProperties(), Material))
        self.assertTrue(hasattr(self.component.material, "density"))
        self.assertIn("HT9", str(self.component.getProperties()))

        self.component.material = air.Air()
        self.assertFalse(self.component.containsSolidMaterial())

        self.component.material = alloy200.Alloy200()
        self.assertTrue(self.component.containsSolidMaterial())

        self.assertTrue(isinstance(self.component.getProperties(), Material))
        self.assertTrue(hasattr(self.component.material, "density"))
        self.assertIn("Alloy200", str(self.component.getProperties()))


class TestNullComponent(TestGeneralComponents):
    componentCls = NullComponent

    def test_cmp(self):
        """Test null component."""
        cur = self.component
        ref = DerivedShape("DerivedShape", "Material", 0, 0)
        self.assertLess(cur, ref)

    def test_nonzero(self):
        cur = bool(self.component)
        ref = False
        self.assertEqual(cur, ref)

    def test_getDimension(self):
        """Test getting empty component.

        .. test:: Retrieve a null dimension.
            :id: T_ARMI_COMP_DIMS0
            :tests: R_ARMI_COMP_DIMS
        """
        for temp in range(400, 901, 25):
            self.assertEqual(self.component.getDimension("", Tc=temp), 0.0)


class TestUnshapedComponent(TestGeneralComponents):
    componentCls = UnshapedComponent
    componentMaterial = "HT9"
    componentDims = {"Tinput": 25.0, "Thot": 430.0, "area": math.pi}

    def test_getComponentArea(self):
        # a case without thermal expansion
        self.assertEqual(self.component.getComponentArea(cold=True), math.pi)

        # a case with thermal expansion
        self.assertEqual(
            self.component.getComponentArea(cold=False),
            math.pi * self.component.getThermalExpansionFactor(self.component.temperatureInC) ** 2,
        )

        # Passing temperature directly
        self.assertEqual(
            self.component.getComponentArea(cold=False),
            self.component.getComponentArea(Tc=self.component.temperatureInC),
        )

        # show that area expansion is consistent with the density change in the material
        hotDensity = self.component.density()
        hotArea = self.component.getArea()
        thermalExpansionFactor = self.component.getThermalExpansionFactor(self.component.temperatureInC)

        coldComponent = self.setUp(
            UnshapedComponent(
                name="coldComponent",
                material=self.componentMaterial,
                Tinput=self.component.inputTemperatureInC,
                Thot=self.component.inputTemperatureInC,
                area=math.pi,
            )
        )
        coldDensity = coldComponent.density()
        coldArea = coldComponent.getArea()

        self.assertGreater(thermalExpansionFactor, 1)
        # thermalExpansionFactor accounts for density being 3D while area is 2D
        self.assertAlmostEqual(
            (coldDensity * coldArea),
            (thermalExpansionFactor * hotDensity * hotArea),
        )

    def test_getBoundingCircleOuterDiameter(self):
        # a case without thermal expansion
        self.assertEqual(self.component.getBoundingCircleOuterDiameter(cold=True), 2.0)

        # a case with thermal expansion
        self.assertEqual(
            self.component.getBoundingCircleOuterDiameter(cold=False),
            2.0 * self.component.getThermalExpansionFactor(self.component.temperatureInC),
        )

    def test_component_less_than(self):
        """Ensure that comparisons between components properly reference bounding circle outer diameter.

        .. test:: Order components by their outermost diameter
            :id: T_ARMI_COMP_ORDER
            :tests: R_ARMI_COMP_ORDER
        """
        componentCls = UnshapedComponent
        componentMaterial = "HT9"

        smallDims = {"Tinput": 25.0, "Thot": 430.0, "area": 0.5 * math.pi}
        sameDims = {"Tinput": 25.0, "Thot": 430.0, "area": 1.0 * math.pi}
        bigDims = {"Tinput": 25.0, "Thot": 430.0, "area": 2.0 * math.pi}

        smallComponent = componentCls("TestComponent", componentMaterial, **smallDims)
        sameComponent = componentCls("TestComponent", componentMaterial, **sameDims)
        bigComponent = componentCls("TestComponent", componentMaterial, **bigDims)

        self.assertTrue(smallComponent < self.component)
        self.assertFalse(bigComponent < self.component)
        self.assertFalse(sameComponent < self.component)

    def test_fromComponent(self):
        circle = components.Circle("testCircle", "HT9", 25, 500, 1.0)
        unshaped = components.UnshapedComponent.fromComponent(circle)
        self.assertEqual(circle.getComponentArea(), unshaped.getComponentArea())


class TestShapedComponent(TestGeneralComponents):
    """Abstract class for all shaped components."""

    def test_preserveMassDuringThermalExpansion(self):
        """Test that when we thermally expand any arbitrary shape, mass is conserved."""
        if not self.component.THERMAL_EXPANSION_DIMS:
            return
        temperatures = [25.0, 30.0, 40.0, 60.0, 80.0, 430.0]
        masses = []
        report = "Temperature, mass, volume, dLL\n"
        for ht in temperatures:
            self.component.setTemperature(ht)
            mass = self.component.getMass()
            masses.append(mass)
            report += "{:10.1f}, {:7.5e}, {:7.5e}, {:7.5e}\n".format(
                ht,
                mass,
                self.component.getVolume(),
                self.component.getThermalExpansionFactor(),
            )

        for mass in masses:
            self.assertNotAlmostEqual(mass, 0.0)
            self.assertAlmostEqual(
                masses[0],
                mass,
                msg="Masses are not preserved during thermal expansion of component {} at {} C. "
                "Original Mass: {}, Thermally Expanded Mass: {}\n{}"
                "".format(self.component, ht, masses[0], mass, report),
            )

    def test_volumeAfterClearCache(self):
        """
        Test volume after cache has been cleared.

        .. test:: Clear cache after a dimensions updated.
            :id: T_ARMI_COMP_VOL0
            :tests: R_ARMI_COMP_VOL
        """
        c = UnshapedVolumetricComponent("testComponent", "Custom", 0, 0, volume=1)
        self.assertAlmostEqual(c.getVolume(), 1, 6)
        c.clearCache()
        self.assertAlmostEqual(c.getVolume(), 1, 6)

    def test_densityConsistent(self):
        """Testing the Component matches quick hand calc."""
        c = self.component

        # no volume defined
        if isinstance(c, (DerivedShape, UnshapedVolumetricComponent)):
            return
        elif isinstance(c, Component):
            return

        # basic density sanity test
        self.assertAlmostEqual(c.density(), c.getMass() / c.getVolume())

        # test 2D expanding density
        if c.temperatureInC == c.inputTemperatureInC:
            self.assertAlmostEqual(c.density(), c.material.pseudoDensity(Tc=c.temperatureInC), delta=0.001)

        if not c.is3D:
            self.assertAlmostEqual(
                c.getArea() * c.parent.getHeight() * c.density(),
                self.component.getMass(),
            )

    def test_density(self):
        """Testing the Component density gets the correct 3D material density."""

        class StrangeMaterial(Material):
            """material designed to make the test easier to understand."""

            def pseduoDensity(self, Tk=None, Tc=None):
                return 1.0

            def density(self, Tk=None, Tc=None):
                return 3.0

        c = Sphere(
            name="strangeBall",
            material=StrangeMaterial(),
            Tinput=200,
            Thot=500,
            od=1,
            id=0,
            mult=1,
        )

        # we expect to see the 3D material density here
        self.assertEqual(c.density(), 3.0)


class TestDerivedShape(TestShapedComponent):
    componentCls = DerivedShape
    componentMaterial = "Sodium"
    componentDims = {"Tinput": 25.0, "Thot": 400.0, "area": 1.0}

    def test_getBoundingCircleOuterDiameter(self):
        self.assertGreater(self.component.getBoundingCircleOuterDiameter(cold=True), 0.0)

    def test_computeVolume(self):
        """Test the computeVolume method on a number of components in a block.

        .. test:: Compute the volume of a DerivedShape inside solid shapes.
            :id: T_ARMI_COMP_FLUID
            :tests: R_ARMI_COMP_FLUID
        """
        from armi.reactor.tests.test_blocks import buildSimpleFuelBlock

        # Calculate the total volume of the block
        b = buildSimpleFuelBlock()
        totalVolume = b.getVolume()

        # calculate the total volume by adding up all the components
        c = b.getComponent(flags.Flags.COOLANT)
        totalByParts = 0
        for co in b.getComponents():
            totalByParts += co.computeVolume()

        self.assertAlmostEqual(totalByParts, totalVolume)

        # test the computeVolume method on the one DerivedShape in this block
        self.assertAlmostEqual(c.computeVolume(), 1386.5232044586771)


class TestDerivedShapeGetArea(unittest.TestCase):
    def test_getAreaColdTrue(self):
        """Prove that the DerivedShape.getArea() works at cold=True."""
        # load one-block test reactor
        _o, r = loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        b = r.core[0][0]

        # ensure there is a DerivedShape in this Block
        shapes = set([type(c) for c in b])
        self.assertIn(Circle, shapes)
        self.assertIn(DerivedShape, shapes)
        self.assertIn(Helix, shapes)
        self.assertIn(Hexagon, shapes)

        # prove that getArea works on the block level
        self.assertAlmostEqual(b.getArea(cold=True), b.getArea(cold=False), delta=1e-10)

        # prove that getArea preserves the sum of all the areas, even if there is a DerivedShape
        totalAreaCold = sum([c.getArea(cold=True) for c in b])
        totalAreaHot = sum([c.getArea(cold=False) for c in b])
        self.assertAlmostEqual(totalAreaCold, totalAreaHot, delta=1e-10)

    def test_getAreaTemp(self):
        """Prove that the DerivedShape.getArea() works for an arbitrary temperature."""
        # load one-block test reactor
        _o, r = loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        b = r.core[0][0]
        b.clearCache()

        # ensure there is a DerivedShape in this Block
        shapes = set([type(c) for c in b])
        self.assertIn(Circle, shapes)
        self.assertIn(DerivedShape, shapes)
        self.assertIn(Helix, shapes)
        self.assertIn(Hexagon, shapes)

        blockArea = b.getMaxArea()
        compArea = sum([c.getArea(Tc=300) for c in b if not isinstance(c, DerivedShape)])

        comp = [c for c in b if isinstance(c, DerivedShape)][0]

        self.assertAlmostEqual(blockArea - compArea, comp.getComponentArea(Tc=300))


class TestComponentSort(unittest.TestCase):
    def setUp(self):
        self.components = []
        pinComp = components.Circle("pin", "UZr", Tinput=273.0, Thot=273.0, od=0.08, mult=169.0)
        gapComp = components.Circle("gap", "Sodium", Tinput=273.0, Thot=273.0, id=0.08, od=0.08, mult=169.0)
        ductComp = components.Hexagon("duct", "HT9", Tinput=273.0, Thot=273.0, op=2.6, ip=2.0, mult=1.0)
        cladComp = components.Circle("clad", "HT9", Tinput=273.0, Thot=273.0, id=0.08, od=0.1, mult=169.0)
        wireComp = components.Helix(
            "wire",
            "HT9",
            Tinput=273.0,
            Thot=273.0,
            axialPitch=10.0,
            helixDiameter=0.11,
            od=0.01,
            mult=169.0,
        )
        self.components = [
            wireComp,
            cladComp,
            ductComp,
            pinComp,
            gapComp,
        ]

    def test_sorting(self):
        """Test that components are sorted as expected."""
        sortedComps = sorted(self.components)
        currentMaxOd = 0.0
        for c in sortedComps:
            self.assertGreaterEqual(c.getBoundingCircleOuterDiameter(cold=True), currentMaxOd)
            currentMaxOd = c.getBoundingCircleOuterDiameter(cold=True)
        self.assertEqual(sortedComps[1].name, "gap")
        self.assertEqual(sortedComps[2].name, "clad")


class TestCircle(TestShapedComponent):
    """Test circle shaped component."""

    componentCls = Circle
    _id = 5.0
    _od = 10
    _coldTemp = 25.0
    componentDims = {
        "Tinput": _coldTemp,
        "Thot": 25.0,
        "od": _od,
        "id": _id,
        "mult": 1.5,
    }

    def test_getThermExpansFactorConsMassLinExpanPerc(self):
        """Test that when ARMI thermally expands a circle, mass is conserved.

        .. test:: Calculate thermal expansion.
            :id: T_ARMI_COMP_EXPANSION0
            :tests: R_ARMI_COMP_EXPANSION
        """
        hotTemp = 700.0
        dLL = self.component.material.linearExpansionFactor(Tc=hotTemp, T0=self._coldTemp)
        ref = 1.0 + dLL
        cur = self.component.getThermalExpansionFactor(Tc=hotTemp)
        self.assertAlmostEqual(cur, ref)

    def test_getDimension(self):
        """Test getting component dimension at specific temperature.

        .. test:: Retrieve a dimension at a temperature.
            :id: T_ARMI_COMP_DIMS1
            :tests: R_ARMI_COMP_DIMS

        .. test:: Calculate thermal expansion.
            :id: T_ARMI_COMP_EXPANSION1
            :tests: R_ARMI_COMP_EXPANSION
        """
        for hotTemp in range(600, 901, 25):
            ref = self._od * self.component.getThermalExpansionFactor(Tc=hotTemp)
            cur = self.component.getDimension("od", Tc=hotTemp)
            self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a circle."""
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_getBoundingCircleOuterDiameter(self):
        ref = self._od
        cur = self.component.getBoundingCircleOuterDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getCircleInnerDiameter(self):
        cur = self.component.getCircleInnerDiameter(cold=True)
        self.assertAlmostEqual(self._id, cur)

    def test_dimensionThermallyExpands(self):
        expandedDims = ["od", "id", "mult"]
        ref = [True, True, False]
        for i, d in enumerate(expandedDims):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])

    def test_getArea(self):
        """Calculate area of circle.

        .. test:: Calculate area of circle.
            :id: T_ARMI_COMP_VOL1
            :tests: R_ARMI_COMP_VOL
        """
        # show we can calculate the area once
        od = self.component.getDimension("od")
        idd = self.component.getDimension("id")
        mult = self.component.getDimension("mult")
        ref = math.pi * ((od / 2) ** 2 - (idd / 2) ** 2) * mult
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

        # show we can clear the cache, change the temp, and correctly re-calc the area
        for newTemp in range(500, 690, 19):
            self.component.clearCache()

            # re-calc area
            self.component.temperatureInC = newTemp
            od = self.component.getDimension("od", Tc=newTemp)
            idd = self.component.getDimension("id", Tc=newTemp)
            ref = math.pi * ((od / 2) ** 2 - (idd / 2) ** 2) * mult
            cur = self.component.getArea()
            self.assertAlmostEqual(cur, ref)

    def test_componentInteractionsLinkingByDimensions(self):
        """Tests linking of Components by dimensions.

        The component ``gap``, representing the fuel-clad gap filled with Void, is defined with
        dimensions that depend on the fuel outer diameter and clad inner diameter. The
        :py:meth:`~armi.reactor.components.component.Component.resolveLinkedDims` method links the
        gap dimensions appropriately when the Component is constructed, and the test shows the area
        of the gap is calculated correctly based on the thermally-expanded dimensions of the fuel
        and clad Components.

        .. test:: Show the dimensions of a liquid Component can be defined to depend on the solid
            Components that bound it.
            :id: T_ARMI_COMP_FLUID1
            :tests: R_ARMI_COMP_FLUID
        """
        nPins = 217
        fuelDims = {"Tinput": 25.0, "Thot": 430.0, "od": 0.9, "id": 0.0, "mult": nPins}
        cladDims = {"Tinput": 25.0, "Thot": 430.0, "od": 1.1, "id": 1.0, "mult": nPins}
        fuel = Circle("fuel", "UZr", **fuelDims)
        clad = Circle("clad", "HT9", **cladDims)
        gapDims = {
            "Tinput": 25.0,
            "Thot": 430.0,
            "od": "clad.id",
            "id": "fuel.od",
            "mult": nPins,
        }
        gapDims["components"] = {"clad": clad, "fuel": fuel}
        gap = Circle("gap", "Void", **gapDims)
        mult = gap.getDimension("mult")
        od = gap.getDimension("od")
        idd = gap.getDimension("id")
        ref = mult * math.pi * ((od / 2.0) ** 2 - (idd / 2.0) ** 2)
        cur = gap.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_badComponentName(self):
        """This shows that resolveLinkedDims cannot support names with periods in them."""
        nPins = 12
        fuelDims = {"Tinput": 25.0, "Thot": 430.0, "od": 0.9, "id": 0.0, "mult": nPins}
        cladDims = {"Tinput": 25.0, "Thot": 430.0, "od": 1.1, "id": 1.0, "mult": nPins}
        fuel = Circle("fuel", "UZr", **fuelDims)
        clad = Circle("clad_4.2.3", "HT9", **cladDims)
        gapDims = {
            "Tinput": 25.0,
            "Thot": 430.0,
            "od": "clad_4.2.3.id",
            "id": "fuel.od",
            "mult": nPins,
        }
        gapDims["components"] = {"clad_4.2.3": clad, "fuel": fuel}
        with self.assertRaises(ValueError):
            _gap = Circle("gap", "Void", **gapDims)

    def test_componentInteractionsLinkingBySubtraction(self):
        """Tests linking of components by subtraction."""
        nPins = 217
        gapDims = {"Tinput": 25.0, "Thot": 430.0, "od": 1.0, "id": 0.9, "mult": nPins}
        gap = Circle("gap", "Void", **gapDims)
        fuelDims = {
            "Tinput": 25.0,
            "Thot": 430.0,
            "od": 0.9,
            "id": 0.0,
            "mult": nPins,
            "modArea": "gap.sub",
        }
        fuel = Circle("fuel", "UZr", components={"gap": gap}, **fuelDims)
        gapArea = (
            gap.getDimension("mult")
            * math.pi
            * ((gap.getDimension("od") / 2.0) ** 2 - (gap.getDimension("id") / 2.0) ** 2)
        )
        fuelArea = (
            fuel.getDimension("mult")
            * math.pi
            * ((fuel.getDimension("od") / 2.0) ** 2 - (fuel.getDimension("id") / 2.0) ** 2)
        )
        ref = fuelArea - gapArea
        cur = fuel.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_getNumberDensities(self):
        """Test that demonstrates that number densities can be retrieved on from component."""
        self.component.p.numberDensities = np.ones(1, dtype=np.float64)
        self.component.p.nuclides = np.array(["NA23"], dtype="S6")
        self.assertEqual(self.component.getNumberDensity("NA23"), 1.0)

    def test_changeNumberDensities(self):
        """Test that demonstrates that the number densities on a component can be modified."""
        self.component.p.numberDensities = np.ones(1, dtype=np.float64)
        self.component.p.nuclides = np.array(["NA23"], dtype="S6")
        self.component.p.detailedNDens = [1.0]
        self.component.p.pinNDens = [1.0]
        self.assertEqual(self.component.getNumberDensity("NA23"), 1.0)
        self.component.changeNDensByFactor(3.0)
        self.assertEqual(self.component.getNumberDensity("NA23"), 3.0)
        self.assertEqual(self.component.p.detailedNDens[0], 3.0)
        self.assertEqual(self.component.p.pinNDens[0], 3.0)

    def test_fuelMass(self):
        nominalMass = self.component.getMass()
        self.component.p.flags = flags.Flags.FUEL
        self.assertEqual(self.component.getFuelMass(), nominalMass)
        self.component.p.flags = flags.Flags.MODERATOR
        self.assertEqual(self.component.getFuelMass(), 0.0)

    def test_theoreticalDensitySetter(self):
        """Ensure only fraction theoretical densities are supported."""
        self.assertEqual(self.component.p.theoreticalDensityFrac, 1)
        with self.assertRaises(ValueError):
            self.component.p.theoreticalDensityFrac = 2.0
        self.assertEqual(self.component.p.theoreticalDensityFrac, 1)
        self.component.p.theoreticalDensityFrac = 0.2
        self.assertEqual(self.component.p.theoreticalDensityFrac, 0.2)
        with self.assertRaises(ValueError):
            self.component.p.theoreticalDensityFrac = -1.0
        self.assertEqual(self.component.p.theoreticalDensityFrac, 0.2)
        self.component.p.theoreticalDensityFrac = 1.0
        self.assertEqual(self.component.p.theoreticalDensityFrac, 1)
        self.component.p.theoreticalDensityFrac = 0.0
        self.assertEqual(self.component.p.theoreticalDensityFrac, 0)


class TestComponentExpansion(unittest.TestCase):
    tCold = 20
    tWarm = 50
    tHot = 500
    coldOuterDiameter = 1.0

    def test_HT9Expansion(self):
        self.runExpansionTests(mat="HT9", isotope="FE")

    def test_UZrExpansion(self):
        self.runExpansionTests(mat="UZr", isotope="U235")

    def test_B4CExpansion(self):
        self.runExpansionTests(mat="B4C", isotope="B10")

    def runExpansionTests(self, mat: str, isotope: str):
        self.componentMassIndependentOfInputTemp(mat)
        self.expansionConservationHotHeightDefined(mat, isotope)
        self.expansionConservationColdHeightDefined(mat)

    def componentMassIndependentOfInputTemp(self, mat: str):
        circle1 = Circle("circle", mat, self.tCold, self.tHot, self.coldOuterDiameter)
        # pick the input dimension to get the same hot component
        hotterDim = self.coldOuterDiameter * (1 + circle1.material.linearExpansionFactor(self.tCold + 200, self.tCold))
        circle2 = Circle("circle", mat, self.tCold + 200, self.tHot, hotterDim)
        self.assertAlmostEqual(circle1.getDimension("od"), circle2.getDimension("od"))
        self.assertAlmostEqual(circle1.getArea(), circle2.getArea())
        self.assertAlmostEqual(circle1.density(), circle2.density())

    def expansionConservationHotHeightDefined(self, mat: str, isotope: str):
        """
        Demonstrate tutorial for how to expand and relationships conserved at during expansion.

        Notes
        -----
        - height taken as hot height and show how quantity is conserved with
          inputHeightsConsideredHot = True (the default)
        """
        hotHeight = 1.0

        circle1 = Circle("circle", mat, self.tCold, self.tWarm, self.coldOuterDiameter)
        circle2 = Circle("circle", mat, self.tCold, self.tHot, self.coldOuterDiameter)

        # mass density is proportional to Fe number density and derived from
        # all the number densities and atomic masses
        self.assertAlmostEqual(
            circle1.getNumberDensity(isotope) / circle2.getNumberDensity(isotope),
            circle1.density() / circle2.density(),
        )

        # the colder one has more because it is the same cold outer diameter but it would be taller
        # at the same temperature
        mass1 = circle1.density() * circle1.getArea() * hotHeight
        mass2 = circle2.density() * circle2.getArea() * hotHeight
        self.assertGreater(mass1, mass2)

        # they are off by factor of thermal exp
        self.assertAlmostEqual(
            mass1 * circle1.getThermalExpansionFactor(),
            mass2 * circle2.getThermalExpansionFactor(),
        )

        # material.pseudoDensity is the 2D density of a material
        # material.density is true density and not equal in this case
        for circle in [circle1, circle2]:
            # 2D density is not equal after application of coldMatAxialExpansionFactor
            # which happens during construction
            self.assertNotAlmostEqual(
                circle.density(),
                circle.material.pseudoDensity(Tc=circle.temperatureInC),
            )
            # 2D density is off by the material thermal exp factor
            percent = circle.material.linearExpansionPercent(Tc=circle.temperatureInC)
            thermalExpansionFactorFromColdMatTemp = 1 + percent / 100
            self.assertAlmostEqual(
                circle.density() * thermalExpansionFactorFromColdMatTemp,
                circle.material.pseudoDensity(Tc=circle.temperatureInC),
            )
            self.assertAlmostEqual(
                circle.density(),
                circle.material.density(Tc=circle.temperatureInC),
            )

        # brief 2D expansion with set temp to show mass is conserved hot height would come from
        # block value
        warmMass = circle1.density() * circle1.getArea() * hotHeight
        circle1.setTemperature(self.tHot)
        hotMass = circle1.density() * circle1.getArea() * hotHeight
        self.assertAlmostEqual(warmMass, hotMass)
        circle1.setTemperature(self.tWarm)

        # Change temp to circle 2 temp  to show equal to circle2 and then change back to show
        # recoverable to original values
        oldArea = circle1.getArea()
        initialDens = circle1.density()

        # when block.setHeight is called (which effectively changes component height)
        # component.setNumberDensity is called (for solid isotopes) to adjust the number density so
        # that now the 2D expansion will be approximated/expanded around the hot temp which is akin
        # to these adjustments
        heightFactor = circle1.getHeightFactor(self.tHot)
        circle1.adjustDensityForHeightExpansion(self.tHot)  # apply temp at new height
        circle1.setTemperature(self.tHot)

        # now its density is same as hot component
        self.assertAlmostEqual(circle1.density(), circle2.density())

        # show that mass is conserved after expansion
        circle1NewHotHeight = hotHeight * heightFactor
        self.assertAlmostEqual(mass1, circle1.density() * circle1.getArea() * circle1NewHotHeight)

        self.assertAlmostEqual(
            circle1.density(),
            circle1.material.density(Tc=circle1.temperatureInC),
        )
        # change back to old temp
        circle1.adjustDensityForHeightExpansion(self.tWarm)
        circle1.setTemperature(self.tWarm)

        # check for consistency
        self.assertAlmostEqual(initialDens, circle1.density())
        self.assertAlmostEqual(oldArea, circle1.getArea())
        self.assertAlmostEqual(mass1, circle1.density() * circle1.getArea() * hotHeight)

    def expansionConservationColdHeightDefined(self, mat: str):
        """
        Demonstrate that material is conserved at during expansion.

        Notes
        -----
        - height taken as cold height and show how quantity is conserved with
          inputHeightsConsideredHot = False
        """
        coldHeight = 1.0
        circle1 = Circle("circle", mat, self.tCold, self.tWarm, self.coldOuterDiameter)
        circle2 = Circle("circle", mat, self.tCold, self.tHot, self.coldOuterDiameter)
        # same as 1 but we will make like 2
        circle1AdjustTo2 = Circle("circle", mat, self.tCold, self.tWarm, self.coldOuterDiameter)

        # make it hot like 2
        circle1AdjustTo2.adjustDensityForHeightExpansion(self.tHot)
        circle1AdjustTo2.setTemperature(self.tHot)
        # check that its like 2
        self.assertAlmostEqual(circle2.density(), circle1AdjustTo2.density())
        self.assertAlmostEqual(circle2.getArea(), circle1AdjustTo2.getArea())

        for circle in [circle1, circle2, circle1AdjustTo2]:
            self.assertAlmostEqual(
                circle.density(),
                circle.material.density(Tc=circle.temperatureInC),
            )
            # total mass consistent between hot and cold. Hot height will be taller
            hotHeight = coldHeight * circle.getThermalExpansionFactor()
            self.assertAlmostEqual(
                coldHeight * circle.getArea(cold=True) * circle.material.density(Tc=circle.inputTemperatureInC),
                hotHeight * circle.getArea() * circle.density(),
            )


class TestTriangle(TestShapedComponent):
    """Test triangle shaped component."""

    componentCls = Triangle
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "base": 3.0,
        "height": 2.0,
        "mult": 30,
    }

    def test_getArea(self):
        """Calculate area of triangle.

        .. test:: Calculate area of triangle.
            :id: T_ARMI_COMP_VOL2
            :tests: R_ARMI_COMP_VOL

        .. test:: Triangle shaped component
            :id: T_ARMI_COMP_SHAPES1
            :tests: R_ARMI_COMP_SHAPES
        """
        b = self.component.getDimension("base")
        h = self.component.getDimension("height")
        mult = self.component.getDimension("mult")
        ref = mult * 0.5 * b * h
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a triangle."""
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_dimensionThermallyExpands(self):
        expandedDims = ["base", "height", "mult"]
        ref = [True, True, False]
        for i, d in enumerate(expandedDims):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])


class TestRectangle(TestShapedComponent):
    """Test rectangle shaped component."""

    componentCls = Rectangle
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "lengthOuter": 6.0,
        "lengthInner": 4.0,
        "widthOuter": 5.0,
        "widthInner": 3.0,
        "mult": 2,
    }

    def test_negativeArea(self):
        dims = {
            "Tinput": 25.0,
            "Thot": 430.0,
            "lengthOuter": 1.0,
            "lengthInner": 2.0,
            "widthOuter": 5.0,
            "widthInner": 6.0,
            "mult": 2,
        }
        refArea = dims["mult"] * (dims["lengthOuter"] * dims["widthOuter"] - dims["lengthInner"] * dims["widthInner"])
        negativeRectangle = Rectangle("test", "Void", **dims)
        self.assertAlmostEqual(negativeRectangle.getArea(), refArea)
        with self.assertRaises(ArithmeticError):
            negativeRectangle = Rectangle("test", "UZr", **dims)
            negativeRectangle.getArea()

    def test_getBoundingCircleOuterDiameter(self):
        """Get outer diameter bounding circle.

        .. test:: Rectangle shaped component
            :id: T_ARMI_COMP_SHAPES2
            :tests: R_ARMI_COMP_SHAPES
        """
        ref = math.sqrt(61.0)
        cur = self.component.getBoundingCircleOuterDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

        # verify the area of the rectangle is correct
        ref = self.componentDims["lengthOuter"] * self.componentDims["widthOuter"]
        ref -= self.componentDims["lengthInner"] * self.componentDims["widthInner"]
        ref *= self.componentDims["mult"]
        cur = self.component.getArea(cold=True)
        self.assertAlmostEqual(cur, ref)

    def test_getCircleInnerDiameter(self):
        cur = self.component.getCircleInnerDiameter(cold=True)
        self.assertAlmostEqual(math.sqrt(25.0), cur)

    def test_getArea(self):
        """Calculate area of rectangle.

        .. test:: Calculate area of rectangle.
            :id: T_ARMI_COMP_VOL3
            :tests: R_ARMI_COMP_VOL
        """
        outerL = self.component.getDimension("lengthOuter")
        innerL = self.component.getDimension("lengthInner")
        outerW = self.component.getDimension("widthOuter")
        innerW = self.component.getDimension("widthInner")
        mult = self.component.getDimension("mult")
        ref = mult * (outerL * outerW - innerL * innerW)
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a rectangle."""
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_dimensionThermallyExpands(self):
        expandedDims = [
            "lengthInner",
            "lengthOuter",
            "widthInner",
            "widthOuter",
            "mult",
        ]
        ref = [True, True, True, True, False]
        for i, d in enumerate(expandedDims):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])


class TestSolidRectangle(TestShapedComponent):
    componentCls = SolidRectangle
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "lengthOuter": 5.0,
        "widthOuter": 5.0,
        "mult": 1,
    }

    def test_getBoundingCircleOuterDiameter(self):
        """Test get bounding circle of the outer diameter."""
        ref = math.sqrt(50)
        cur = self.component.getBoundingCircleOuterDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getArea(self):
        """Calculate area of solid rectangle.

        .. test:: Calculate area of solid rectangle.
            :id: T_ARMI_COMP_VOL4
            :tests: R_ARMI_COMP_VOL
        """
        outerL = self.component.getDimension("lengthOuter")
        outerW = self.component.getDimension("widthOuter")
        mult = self.component.getDimension("mult")
        ref = mult * (outerL * outerW)
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a solid rectangle."""
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_dimensionThermallyExpands(self):
        expandedDims = ["lengthOuter", "widthOuter", "mult"]
        ref = [True, True, False]
        for i, d in enumerate(expandedDims):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])


class TestSquare(TestShapedComponent):
    """Test square shaped component."""

    componentCls = Square
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "widthOuter": 3.0,
        "widthInner": 2.0,
        "mult": 1,
    }

    def test_negativeArea(self):
        dims = {
            "Tinput": 25.0,
            "Thot": 430.0,
            "widthOuter": 1.0,
            "widthInner": 5.0,
            "mult": 1,
        }
        refArea = dims["mult"] * (dims["widthOuter"] * dims["widthOuter"] - dims["widthInner"] * dims["widthInner"])
        negativeRectangle = Square("test", "Void", **dims)
        self.assertAlmostEqual(negativeRectangle.getArea(), refArea)
        with self.assertRaises(ArithmeticError):
            negativeRectangle = Square("test", "UZr", **dims)
            negativeRectangle.getArea()

    def test_getBoundingCircleOuterDiameter(self):
        """Get bounding circle outer diameter.

        .. test:: Square shaped component
            :id: T_ARMI_COMP_SHAPES3
            :tests: R_ARMI_COMP_SHAPES
        """
        ref = math.sqrt(18.0)
        cur = self.component.getBoundingCircleOuterDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

        # verify the area of the circle is correct
        ref = self.componentDims["widthOuter"] ** 2 - self.componentDims["widthInner"] ** 2
        cur = self.component.getComponentArea(cold=True)
        self.assertAlmostEqual(cur, ref)

    def test_getCircleInnerDiameter(self):
        ref = math.sqrt(8.0)
        cur = self.component.getCircleInnerDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getArea(self):
        """Calculate area of square.

        .. test:: Calculate area of square.
            :id: T_ARMI_COMP_VOL5
            :tests: R_ARMI_COMP_VOL
        """
        outerW = self.component.getDimension("widthOuter")
        innerW = self.component.getDimension("widthInner")
        mult = self.component.getDimension("mult")
        ref = mult * (outerW * outerW - innerW * innerW)
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a square."""
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_dimensionThermallyExpands(self):
        expandedDims = ["widthOuter", "widthInner", "mult"]
        ref = [True, True, False]
        for i, d in enumerate(expandedDims):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])


class TestCube(TestShapedComponent):
    componentCls = Cube
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "lengthOuter": 5.0,
        "lengthInner": 4.0,
        "widthOuter": 5.0,
        "widthInner": 3.0,
        "heightOuter": 20.0,
        "heightInner": 10.0,
        "mult": 2,
    }

    def test_negativeVolume(self):
        dims = {
            "Tinput": 25.0,
            "Thot": 430.0,
            "lengthOuter": 5.0,
            "lengthInner": 20.0,
            "widthOuter": 5.0,
            "widthInner": 30.0,
            "heightOuter": 20.0,
            "heightInner": 30.0,
            "mult": 2,
        }
        refVolume = dims["mult"] * (
            dims["lengthOuter"] * dims["widthOuter"] * dims["heightOuter"]
            - dims["lengthInner"] * dims["widthInner"] * dims["heightInner"]
        )
        negativeCube = Cube("test", "Void", **dims)
        self.assertAlmostEqual(negativeCube.getVolume(), refVolume)
        with self.assertRaises(ArithmeticError):
            negativeCube = Cube("test", "UZr", **dims)
            negativeCube.getVolume()

    def test_getVolume(self):
        """Calculate area of cube.

        .. test:: Calculate area of cube.
            :id: T_ARMI_COMP_VOL6
            :tests: R_ARMI_COMP_VOL
        """
        lengthO = self.component.getDimension("lengthOuter")
        widthO = self.component.getDimension("widthOuter")
        heightO = self.component.getDimension("heightOuter")
        lengthI = self.component.getDimension("lengthInner")
        widthI = self.component.getDimension("widthInner")
        heightI = self.component.getDimension("heightInner")
        mult = self.component.getDimension("mult")
        ref = mult * (lengthO * widthO * heightO - lengthI * widthI * heightI)
        cur = self.component.getVolume()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a cube."""
        self.assertFalse(self.component.THERMAL_EXPANSION_DIMS)


class TestHexagon(TestShapedComponent):
    """Test hexagon shaped component."""

    componentCls = Hexagon
    componentDims = {"Tinput": 25.0, "Thot": 430.0, "op": 10.0, "ip": 5.0, "mult": 1}

    def test_getBoundingCircleOuterDiameter(self):
        ref = 2.0 * 10 / math.sqrt(3)
        cur = self.component.getBoundingCircleOuterDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getCircleInnerDiameter(self):
        ref = 2.0 * 5.0 / math.sqrt(3)
        cur = self.component.getCircleInnerDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getArea(self):
        """Calculate area of hexagon.

        .. test:: Calculate area of hexagon.
            :id: T_ARMI_COMP_VOL7
            :tests: R_ARMI_COMP_VOL
        """
        cur = self.component.getArea()
        mult = self.component.getDimension("mult")
        op = self.component.getDimension("op")
        ip = self.component.getDimension("ip")
        ref = math.sqrt(3.0) / 2.0 * (op**2 - ip**2) * mult
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a hexagon."""
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_dimensionThermallyExpands(self):
        expandedDims = ["op", "ip", "mult"]
        ref = [True, True, False]
        for i, d in enumerate(expandedDims):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])


class TestFilletedHexagon(TestShapedComponent):
    """Test FilletedHexagon shaped component."""

    componentCls = FilletedHexagon
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "op": 10.0,
        "ip": 5.0,
        "mult": 1,
        "oR": 0.2,
        "iR": 0.1,
    }

    def test_getBoundingCircleOuterDiameter(self):
        ref = 2.0 * 10 / math.sqrt(3)
        cur = self.component.getBoundingCircleOuterDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getCircleInnerDiameter(self):
        ref = 2.0 * 5.0 / math.sqrt(3)
        cur = self.component.getCircleInnerDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getComponentArea(self):
        cur = self.component.getComponentArea()
        op = self.component.getDimension("op")
        ip = self.component.getDimension("ip")
        oR = self.component.getDimension("oR")
        iR = self.component.getDimension("iR")
        mult = self.component.getDimension("mult")

        ref = mult * (FilletedHexagon._area(op, oR) - FilletedHexagon._area(ip, iR))
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a Hexagon."""
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_dimensionThermallyExpands(self):
        expandedDims = ["op", "ip", "iR", "oR", "mult"]
        ref = [True, True, True, True, False]
        for i, d in enumerate(expandedDims):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])

    def test_filletedMatchesNormal(self):
        """Prove that if the radius of curvature is 0.0, FilletedHexagon is just a hexagon."""
        for ip in np.arange(0.1, 1, 0.1):
            for op in np.arange(1.1, 5, 0.4):
                componentDims = {
                    "Tinput": 25.0,
                    "Thot": 430.0,
                    "op": op,
                    "ip": ip,
                    "mult": 1.0,
                }
                f = FilletedHexagon("xyz", "HT9", **componentDims)
                h = Hexagon("xyz", "HT9", **componentDims)

                self.assertAlmostEqual(f.getComponentArea(), h.getComponentArea(), delta=1e-7)
                self.assertGreaterEqual(h.getArea(), f.getArea() - 1e-7)

    def test_filletedBecomesACircle(self):
        """Prove that as the radius of curvature becomes D/2, the shape becomes a circle."""
        for op in np.arange(1.0, 5.0, 0.5):
            componentDims = {
                "Tinput": 425.0,
                "Thot": 425.0,
                "op": op,
                "ip": 0.0,
                "oR": op / 2.0,
                "iR": 0.0,
                "mult": 1.0,
            }
            f = FilletedHexagon("circleHex", "HT9", **componentDims)
            self.assertAlmostEqual(f.getComponentArea(), math.pi * (op / 2.0) ** 2, delta=1e-7)


class TestHoledHexagon(TestShapedComponent):
    """Test holed hexagon shaped component."""

    componentCls = HoledHexagon
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "op": 16.5,
        "holeOD": 3.6,
        "nHoles": 7,
        "mult": 1.0,
    }

    def test_getBoundingCircleOuterDiameter(self):
        ref = 2.0 * 16.5 / math.sqrt(3)
        cur = self.component.getBoundingCircleOuterDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getCircleInnerDiameter(self):
        ref = 0  # there are multiple holes, so the function should return 0
        cur = self.component.getCircleInnerDiameter(cold=True)
        self.assertEqual(ref, cur)

        # make and test another one with just 1 hole
        simpleHoledHexagon = HoledHexagon(
            "hex",
            "Void",
            self.componentDims["Tinput"],
            self.componentDims["Thot"],
            self.componentDims["op"],
            self.componentDims["holeOD"],
            nHoles=1,
        )
        self.assertEqual(
            self.componentDims["holeOD"],
            simpleHoledHexagon.getCircleInnerDiameter(cold=True),
        )

    def test_getArea(self):
        """Calculate area of holed hexagon.

        .. test:: Calculate area of holed hexagon.
            :id: T_ARMI_COMP_VOL8
            :tests: R_ARMI_COMP_VOL
        """
        op = self.component.getDimension("op")
        odHole = self.component.getDimension("holeOD")
        nHoles = self.component.getDimension("nHoles")
        mult = self.component.getDimension("mult")
        hexarea = math.sqrt(3.0) / 2.0 * (op**2)
        holeArea = nHoles * math.pi * ((odHole / 2.0) ** 2)
        ref = mult * (hexarea - holeArea)
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a holed hexagon."""
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_dimensionThermallyExpands(self):
        expandedDims = ["op", "holeOD", "mult"]
        ref = [True, True, False]
        for i, d in enumerate(expandedDims):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])


class TestHexHoledCircle(TestShapedComponent):
    componentCls = HexHoledCircle
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "od": 16.5,
        "holeOP": 3.6,
        "mult": 1.0,
    }

    def test_getCircleInnerDiameter(self):
        simpleHexHoledCircle = HexHoledCircle(
            "Circle",
            "Void",
            self.componentDims["Tinput"],
            self.componentDims["Thot"],
            self.componentDims["od"],
            self.componentDims["holeOP"],
        )
        self.assertEqual(
            self.componentDims["holeOP"],
            simpleHexHoledCircle.getCircleInnerDiameter(cold=True),
        )

    def test_getArea(self):
        """Calculate area of hex holed circle.

        .. test:: Calculate area of hex holed circle.
            :id: T_ARMI_COMP_VOL9
            :tests: R_ARMI_COMP_VOL
        """
        od = self.component.getDimension("od")
        holeOP = self.component.getDimension("holeOP")
        mult = self.component.getDimension("mult")
        hexarea = math.sqrt(3.0) / 2.0 * (holeOP**2)
        holeArea = math.pi * ((od / 2.0) ** 2)
        ref = mult * (holeArea - hexarea)
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a holed hexagon."""
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_dimensionThermallyExpands(self):
        expandedDims = ["od", "holeOP", "mult"]
        ref = [True, True, False]
        for i, d in enumerate(expandedDims):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])


class TestHoledRectangle(TestShapedComponent):
    """Tests HoledRectangle, and provides much support for HoledSquare test."""

    componentCls = HoledRectangle
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "lengthOuter": 16.0,
        "widthOuter": 10.0,
        "holeOD": 3.6,
        "mult": 1.0,
    }

    dimsToTestExpansion = ["lengthOuter", "widthOuter", "holeOD", "mult"]

    def setUp(self):
        TestShapedComponent.setUp(self)
        self.setClassDims()

    def setClassDims(self):
        # This enables subclassing testing for square
        self.length = self.component.getDimension("lengthOuter")
        self.width = self.component.getDimension("widthOuter")

    def test_getBoundingCircleOuterDiameter(self):
        # hypotenuse
        ref = (self.length**2 + self.width**2) ** 0.5
        cur = self.component.getBoundingCircleOuterDiameter()
        self.assertAlmostEqual(ref, cur)

    def test_getCircleInnerDiameter(self):
        ref = self.componentDims["holeOD"]
        cur = self.component.getCircleInnerDiameter(cold=True)
        self.assertEqual(ref, cur)

    def test_getArea(self):
        """Calculate area of holed rectangle.

        .. test:: Calculate area of holed rectangle.
            :id: T_ARMI_COMP_VOL10
            :tests: R_ARMI_COMP_VOL
        """
        rectArea = self.length * self.width
        odHole = self.component.getDimension("holeOD")
        mult = self.component.getDimension("mult")
        holeArea = math.pi * ((odHole / 2.0) ** 2)
        ref = mult * (rectArea - holeArea)
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_dimensionThermallyExpands(self):
        ref = [True] * len(self.dimsToTestExpansion)
        ref[-1] = False  # mult shouldn't expand
        for i, d in enumerate(self.dimsToTestExpansion):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])


class TestHoledSquare(TestHoledRectangle):
    """Test holed square shaped component."""

    componentCls = HoledSquare

    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "widthOuter": 16.0,
        "holeOD": 3.6,
        "mult": 1.0,
    }

    dimsToTestExpansion = ["widthOuter", "holeOD", "mult"]

    def setClassDims(self):
        # This enables subclassing testing for square
        self.width = self.length = self.component.getDimension("widthOuter")

    def test_thermallyExpands(self):
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_getCircleInnerDiameter(self):
        ref = self.componentDims["holeOD"]
        cur = self.component.getCircleInnerDiameter(cold=True)
        self.assertEqual(ref, cur)


class TestHelix(TestShapedComponent):
    """Test helix shaped component."""

    componentCls = Helix
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "od": 0.25,
        "axialPitch": 1.0,
        "mult": 1.5,
        "helixDiameter": 2.0,
        "id": 0.1,
    }

    def test_getBoundingCircleOuterDiameter(self):
        ref = 2.0 + 0.25
        cur = self.component.getBoundingCircleOuterDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getCircleInnerDiameter(self):
        ref = 2.0 - 0.25
        cur = self.component.getCircleInnerDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getArea(self):
        """Calculate area of helix.

        .. test:: Calculate area of helix.
            :id: T_ARMI_COMP_VOL11
            :tests: R_ARMI_COMP_VOL
        """
        cur = self.component.getArea()
        axialPitch = self.component.getDimension("axialPitch")
        helixDiameter = self.component.getDimension("helixDiameter")
        innerDiameter = self.component.getDimension("id")
        outerDiameter = self.component.getDimension("od")
        mult = self.component.getDimension("mult")
        c = axialPitch / (2.0 * math.pi)
        helixFactor = math.sqrt((helixDiameter / 2.0) ** 2 + c**2) / c
        ref = mult * math.pi * (outerDiameter**2 / 4.0 - innerDiameter**2 / 4.0) * helixFactor
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_dimensionThermallyExpands(self):
        expandedDims = ["od", "id", "axialPitch", "helixDiameter", "mult"]
        ref = [True, True, True, True, False]
        for i, d in enumerate(expandedDims):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])

    def test_validParameters(self):
        """Testing the Helix class performs as expected with various inputs."""
        # stupid/simple inputs
        h = Helix("thing", "Cu", 0, 0, 1, 1, 1)
        self.assertEqual(h.getDimension("axialPitch"), 1)

        # standard case / inputs ordered well
        h = Helix(
            "what",
            "Cu",
            Tinput=25.0,
            Thot=425.0,
            id=0.1,
            od=0.35,
            mult=1.0,
            axialPitch=1.123,
            helixDiameter=1.5,
        )
        self.assertTrue(1.123 < h.getDimension("axialPitch") < 1.15)

        # inputs ordered crazy
        h = Helix(
            material="Cu",
            id=0.1,
            mult=1.0,
            Tinput=25.0,
            Thot=425.0,
            axialPitch=1.123,
            name="stuff",
            od=0.35,
            helixDiameter=1.5,
        )
        self.assertTrue(1.123 < h.getDimension("axialPitch") < 1.15)

        # missing helixDiameter input
        with self.assertRaises(TypeError):
            h = Helix(
                name="helix",
                material="Cu",
                Tinput=25.0,
                Thot=425.0,
                id=0.1,
                od=0.35,
                mult=1.0,
                axialPitch=1.123,
            )


class TestSphere(TestShapedComponent):
    componentCls = Sphere
    componentDims = {"Tinput": 25.0, "Thot": 430.0, "od": 1.0, "id": 0.0, "mult": 3}

    def test_getVolume(self):
        """Calculate area of sphere.

        .. test:: Calculate volume of sphere.
            :id: T_ARMI_COMP_VOL12
            :tests: R_ARMI_COMP_VOL
        """
        od = self.component.getDimension("od")
        idd = self.component.getDimension("id")
        mult = self.component.getDimension("mult")
        ref = mult * 4.0 / 3.0 * math.pi * ((od / 2.0) ** 3 - (idd / 2.0) ** 3)
        cur = self.component.getVolume()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        self.assertFalse(self.component.THERMAL_EXPANSION_DIMS)


class TestRadialSegment(TestShapedComponent):
    componentCls = RadialSegment
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "inner_radius": 110,
        "outer_radius": 170,
        "height": 160,
        "mult": 1,
    }

    def test_getVolume(self):
        mult = self.component.getDimension("mult")
        outerRad = self.component.getDimension("outer_radius")
        innerRad = self.component.getDimension("inner_radius")
        outerTheta = self.component.getDimension("outer_theta")
        innerTheta = self.component.getDimension("inner_theta")
        height = self.component.getDimension("height")
        radialArea = math.pi * (outerRad**2 - innerRad**2)
        aziFraction = (outerTheta - innerTheta) / (math.pi * 2.0)
        ref = mult * radialArea * aziFraction * height
        cur = self.component.getVolume()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        self.assertFalse(self.component.THERMAL_EXPANSION_DIMS)

    def test_getBoundingCircleOuterDiameter(self):
        self.assertEqual(self.component.getBoundingCircleOuterDiameter(cold=True), 340.0)


class TestDifferentialRadialSegment(TestShapedComponent):
    componentCls = DifferentialRadialSegment
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "inner_radius": 110,
        "radius_differential": 60,
        "inner_axial": 60,
        "height": 160,
    }

    def test_getVolume(self):
        mult = self.component.getDimension("mult")
        outerRad = self.component.getDimension("outer_radius")
        innerRad = self.component.getDimension("inner_radius")
        outerTheta = self.component.getDimension("outer_theta")
        innerTheta = self.component.getDimension("inner_theta")
        height = self.component.getDimension("height")
        radialArea = math.pi * (outerRad**2 - innerRad**2)
        aziFraction = (outerTheta - innerTheta) / (math.pi * 2.0)
        ref = mult * radialArea * aziFraction * height
        cur = self.component.getVolume()
        self.assertAlmostEqual(cur, ref)

    def test_updateDims(self):
        """
        Test Update dimensions.

        .. test:: Dimensions can be updated.
            :id: T_ARMI_COMP_VOL13
            :tests: R_ARMI_COMP_VOL
        """
        self.assertEqual(self.component.getDimension("inner_radius"), 110)
        self.assertEqual(self.component.getDimension("radius_differential"), 60)
        self.component.updateDims()
        self.assertEqual(self.component.getDimension("outer_radius"), 170)
        self.assertEqual(self.component.getDimension("outer_axial"), 220)
        self.assertEqual(self.component.getDimension("outer_theta"), 2 * math.pi)

    def test_thermallyExpands(self):
        self.assertFalse(self.component.THERMAL_EXPANSION_DIMS)

    def test_getBoundingCircleOuterDiameter(self):
        self.assertEqual(self.component.getBoundingCircleOuterDiameter(cold=True), 340)


class TestMaterialAdjustments(unittest.TestCase):
    """Tests to make sure enrichment and mass fractions can be adjusted properly."""

    def setUp(self):
        dims = {"Tinput": 25.0, "Thot": 600.0, "od": 10.0, "id": 5.0, "mult": 1.0}
        self.fuel = Circle("fuel", "UZr", **dims)

        class FakeBlock:
            def getHeight(self):
                return 1.0

            def getSymmetryFactor(self):
                return 1.0

        self.fuel.parent = FakeBlock()

    def test_setMassFrac(self):
        """Make sure we can set a mass fraction properly."""
        target35 = 0.2
        self.fuel.setMassFrac("U235", target35)
        self.assertAlmostEqual(self.fuel.getMassFrac("U235"), target35)

    def test_setMassFracOnComponentMaterial(self):
        """Checks for valid and invalid mass fraction assignments on a component's material."""
        # Negative value is not acceptable.
        with self.assertRaises(ValueError):
            self.fuel.material.setMassFrac("U235", -0.1)

        # Greater than 1.0 value is not acceptable.
        with self.assertRaises(ValueError):
            self.fuel.material.setMassFrac("U235", 1.1)

        # String is not acceptable.
        with self.assertRaises(TypeError):
            self.fuel.material.setMassFrac("U235", "")

        # `NoneType` is not acceptable.
        with self.assertRaises(TypeError):
            self.fuel.material.setMassFrac("U235", None)

        # Zero is acceptable
        self.fuel.material.setMassFrac("U235", 0.0)
        self.assertAlmostEqual(self.fuel.material.getMassFrac("U235"), 0.0)

        # One is acceptable
        self.fuel.material.setMassFrac("U235", 1.0)
        self.assertAlmostEqual(self.fuel.material.getMassFrac("U235"), 1.0)

    def test_adjustMassFrac_invalid(self):
        with self.assertRaises(ValueError):
            self.fuel.adjustMassFrac(nuclideToAdjust="ZR", val=-0.23)

        with self.assertRaises(ValueError):
            self.fuel.adjustMassFrac(nuclideToAdjust="ZR", val=1.12)

        alwaysFalse = lambda a: False
        self.fuel.parent = None
        self.assertIsNone(self.fuel.getAncestorAndDistance(alwaysFalse))

    def test_adjustMassFrac_U235(self):
        zrMass = self.fuel.getMass("ZR")
        uMass = self.fuel.getMass("U")
        zrFrac = zrMass / (uMass + zrMass)

        enrichmentFrac = 0.3
        u235Frac = enrichmentFrac * uMass / (uMass + zrMass)
        u238Frac = (1.0 - enrichmentFrac) * uMass / (uMass + zrMass)

        self.fuel.adjustMassFrac(nuclideToAdjust="U235", elementToHoldConstant="ZR", val=u235Frac)
        self.assertAlmostEqual(self.fuel.getMassFrac("U235"), u235Frac)
        self.assertAlmostEqual(self.fuel.getMassFrac("U238"), u238Frac)
        self.assertAlmostEqual(self.fuel.getMassFrac("ZR"), zrFrac)

    def test_adjustMassFrac_U(self):
        self.fuel.adjustMassFrac(elementToAdjust="U", val=0.7)
        uFrac = self.fuel.getMassFrac("U")
        u235Enrichment = 0.1
        u238Frac = (1.0 - u235Enrichment) * uFrac
        u235Frac = u235Enrichment * uFrac

        self.assertAlmostEqual(self.fuel.getMassFrac("U235"), u235Frac)
        self.assertAlmostEqual(self.fuel.getMassFrac("U238"), u238Frac)
        self.assertAlmostEqual(self.fuel.getMassFrac("ZR"), 0.30)

    def test_adjustMassFrac_clear_ZR(self):
        self.fuel.adjustMassFrac(nuclideToAdjust="ZR", val=0.0)
        self.assertAlmostEqual(self.fuel.getMassFrac("ZR"), 0.0)
        self.assertAlmostEqual(self.fuel.getNumberDensity("ZR"), 0.0)
        self.assertAlmostEqual(self.fuel.getMassFrac("U235") + self.fuel.getMassFrac("U238"), 1.0)

    def test_adjustMassFrac_set_ZR(self):
        u235Enrichment = 0.1
        zrFrac = 0.1
        uFrac = 1.0 - zrFrac
        u238Frac = (1.0 - u235Enrichment) * uFrac
        u235Frac = u235Enrichment * uFrac

        self.fuel.adjustMassFrac(nuclideToAdjust="ZR", val=zrFrac)
        self.assertAlmostEqual(self.fuel.getMassFrac("U235"), u235Frac)
        self.assertAlmostEqual(self.fuel.getMassFrac("U238"), u238Frac)
        self.assertAlmostEqual(self.fuel.getMassFrac("ZR"), zrFrac)

    def test_adjustMassFrac_leave_same(self):
        zrFrac = 0.1
        u238Enrichment = 0.9
        uFrac = 1.0 - zrFrac
        u238Frac = uFrac * u238Enrichment

        self.fuel.adjustMassFrac(nuclideToAdjust="ZR", val=zrFrac)
        self.assertAlmostEqual(self.fuel.getMassFrac("U238"), u238Frac)
        self.assertAlmostEqual(self.fuel.getMassFrac("ZR"), zrFrac)

    def test_adjustMassEnrichment(self):
        self.fuel.adjustMassEnrichment(0.2)
        self.assertAlmostEqual(self.fuel.getMassFrac("U235"), 0.18)
        self.assertAlmostEqual(self.fuel.getMassFrac("U238"), 0.72)
        self.assertAlmostEqual(self.fuel.getMassFrac("ZR"), 0.1)

    def test_getEnrichment(self):
        self.fuel.adjustMassEnrichment(0.3)
        self.assertAlmostEqual(self.fuel.getEnrichment(), 0.3)

    def test_finalizeLoadDBAdjustsTD(self):
        """Ensure component is fully loaded through finalize methods."""
        tdFrac = 0.54321
        comp = self.fuel
        comp.p.theoreticalDensityFrac = tdFrac
        comp.finalizeLoadingFromDB()
        self.assertEqual(comp.material.getTD(), tdFrac)


class TestPinQuantities(unittest.TestCase):
    """Test methods that involve retrieval of pin quantities."""

    def setUp(self):
        self.r = loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")[1]

    def test_getPinMgFluxes(self):
        """Test proper retrieval of pin multigroup flux for fuel component."""
        # Get a fuel block and its fuel component from the core
        fuelBlock: Block = self.r.core.getFirstBlock(flags.Flags.FUEL)
        fuelComponent: Component = fuelBlock.getComponent(flags.Flags.FUEL)
        numPins = int(fuelComponent.p.mult)
        self.assertEqual(numPins, 169)

        # Set pin fluxes at block level
        fuelBlock.initializePinLocations()
        pinMgFluxes = np.random.rand(numPins, 33)
        pinMgFluxesAdj = np.random.rand(numPins, 33)
        pinMgFluxesGamma = np.random.rand(numPins, 33)
        fuelBlock.setPinMgFluxes(pinMgFluxes)
        fuelBlock.setPinMgFluxes(pinMgFluxesAdj, adjoint=True)
        fuelBlock.setPinMgFluxes(pinMgFluxesGamma, gamma=True)

        # Retrieve from component to ensure they match
        simPinMgFluxes = fuelComponent.getPinMgFluxes()
        simPinMgFluxesAdj = fuelComponent.getPinMgFluxes(adjoint=True)
        simPinMgFluxesGamma = fuelComponent.getPinMgFluxes(gamma=True)
        assert_equal(pinMgFluxes, simPinMgFluxes)
        assert_equal(pinMgFluxesAdj, simPinMgFluxesAdj)
        assert_equal(pinMgFluxesGamma, simPinMgFluxesGamma)

        # Check assertion for adjoint gamma flux
        with self.assertRaisesRegex(ValueError, "Adjoint gamma flux is currently unsupported."):
            fuelComponent.getPinMgFluxes(adjoint=True, gamma=True)

        # Check assertion for not-found parameter
        fuelBlock.p.pinMgFluxes = None
        with self.assertRaisesRegex(
            ValueError,
            f"Failure getting pinMgFluxes from {fuelComponent} via parent {fuelBlock}",
        ):
            fuelComponent.getPinMgFluxes()
