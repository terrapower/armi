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

"""
Tests functionalities of components within ARMI
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access,no-self-use,no-member,invalid-name
import copy
import math
import unittest

from armi.materials.material import Material
from armi.reactor import components
from armi.reactor.components import (
    Component,
    UnshapedComponent,
    NullComponent,
    Circle,
    Hexagon,
    HoledHexagon,
    HexHoledCircle,
    HoledRectangle,
    HoledSquare,
    Helix,
    Sphere,
    Cube,
    Rectangle,
    SolidRectangle,
    Square,
    Triangle,
    Torus,
    RadialSegment,
    DifferentialRadialSegment,
    DerivedShape,
    UnshapedVolumetricComponent,
    ComponentType,
)
from armi.reactor.components import materials
from armi.utils import units


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
        voidAttrs = self.getCircleVoidDict()
        voidComp = components.factory(voidAttrs.pop("shape"), [], voidAttrs)
        fuelAttrs = self.getCircleFuelDict()
        fuelComp = components.factory(fuelAttrs.pop("shape"), [], fuelAttrs)
        self.assertIsInstance(voidComp, components.Circle)
        self.assertIsInstance(voidComp.material, materials.Void)
        self.assertIsInstance(fuelComp, components.Circle)
        self.assertIsInstance(fuelComp.material, materials.UZr)

    def test_componentInitializationAndDuplication(self):
        # populate the class/signature dict, and create a basis attrs
        attrs = self.getCircleVoidDict()
        del attrs["shape"]
        del attrs["od"]
        del attrs["id"]
        del attrs["mult"]

        for i, (name, klass) in enumerate(
            ComponentType.TYPES.items()
        ):  # pylint: disable=protected-access
            # hack together a dictionary input
            thisAttrs = {k: 1.0 for k in set(klass.INIT_SIGNATURE).difference(attrs)}
            del thisAttrs["components"]
            thisAttrs.update(attrs)
            thisAttrs["name"] = "banana{}".format(i)
            if "modArea" in thisAttrs:
                thisAttrs["modArea"] = None
            component = components.factory(name, [], thisAttrs)
            duped = copy.deepcopy(component)
            for key, val in component.p.items():
                if key not in ["area", "volume", "serialNum"]:  # they get recomputed
                    self.assertEqual(
                        val,
                        duped.p[key],
                        msg="Key: {}, val1: {}, val2: {}".format(
                            key, val, duped.p[key]
                        ),
                    )

    def test_factoryBadShapeName(self):
        badDict = self.getCircleFuelDict()
        with self.assertRaises(ValueError):
            components.factory("turtle", [], badDict)

    def test_invalidCoolantComponentAssignment(self):
        invalidComponentTypes = [Component, NullComponent]
        for ComponentType in invalidComponentTypes:
            with self.assertRaises(ValueError):
                _c = ComponentType("coolant", "Sodium", 0, 0)


class TestGeneralComponents(unittest.TestCase):
    """Base test for all individual component tests."""

    componentCls = Component
    componentMaterial = "HT9"
    componentDims = {"Tinput": 25.0, "Thot": 25.0}

    def setUp(self, component=None):
        """
        Most of the time nothing will be passed as `component` and the result will
        be stored in self, but you can also pass a component object as `component`,
        in which case the object will be returned with the `parent` attribute assigned.
        """

        class _Parent:
            def getSymmetryFactor(self):
                return 1.0

            def getHeight(self):
                return 1.0

            def clearCache(self):
                pass

            def getChildren(self):
                return []

            derivedMustUpdate = False

        if component == None:
            self.component = self.componentCls(
                "TestComponent", self.componentMaterial, **self.componentDims
            )
            self.component.parent = _Parent()
        else:
            component.parent = _Parent()
            return component


class TestComponent(TestGeneralComponents):
    """Test the base component."""

    componentCls = Component

    def test_initializeComponent(self):
        expectedName = "TestComponent"
        actualName = self.component.getName()
        expectedMaterialName = "HT9"
        actualMaterialName = self.component.material.getName()
        self.assertEqual(expectedName, actualName)
        self.assertEqual(expectedMaterialName, actualMaterialName)


class TestNullComponent(TestGeneralComponents):
    componentCls = NullComponent

    def test_cmp(self):
        cur = self.component
        ref = DerivedShape("DerivedShape", "Material", 0, 0)
        self.assertLess(cur, ref)

    def test_nonzero(self):
        cur = bool(self.component)
        ref = False
        self.assertEqual(cur, ref)

    def test_getDimension(self):
        self.assertEqual(self.component.getDimension(""), 0.0)


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
            math.pi
            * self.component.getThermalExpansionFactor(self.component.temperatureInC)
            ** 2,
        )

        # show that area expansion is consistent with the density change in the material
        hotDensity = self.component.density()
        hotArea = self.component.getArea()
        thermalExpansionFactor = self.component.getThermalExpansionFactor(
            self.component.temperatureInC
        )

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
            2.0
            * self.component.getThermalExpansionFactor(self.component.temperatureInC),
        )

    def test_fromComponent(self):
        circle = components.Circle("testCircle", "HT9", 25, 500, 1.0)
        unshaped = components.UnshapedComponent.fromComponent(circle)
        self.assertEqual(circle.getComponentArea(), unshaped.getComponentArea())


class TestShapedComponent(TestGeneralComponents):
    """Abstract class for all shaped components"""

    def test_preserveMassDuringThermalExpansion(self):
        """Test that when we thermally expand any arbirtray shape, mass is conserved

        .. test:: Test that ARMI can thermally expand any arbitrary shape.
           :id: TEST_REACTOR_THERMAL_EXPANSION_0
           :links: REQ_REACTOR_THERMAL_EXPANSION
        """
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
        c = UnshapedVolumetricComponent("testComponent", "Custom", 0, 0, volume=1)
        self.assertAlmostEqual(c.getVolume(), 1, 6)
        c.clearCache()
        self.assertAlmostEqual(c.getVolume(), 1, 6)

    def test_densityConsistent(self):
        c = self.component

        # no volume defined
        if isinstance(c, (DerivedShape, UnshapedVolumetricComponent)):
            return
        elif type(c) == Component:
            return

        # basic density sanity test
        self.assertAlmostEqual(c.density(), c.getMass() / c.getVolume())

        # test 2D expanding density
        if c.temperatureInC == c.inputTemperatureInC:
            self.assertAlmostEqual(
                c.density(), c.material.pseudoDensity(Tc=c.temperatureInC), delta=0.001
            )

        if not c.is3D:
            self.assertAlmostEqual(
                c.getArea() * c.parent.getHeight() * c.density(),
                self.component.getMass(),
            )

    def test_density(self):
        """Testing the Component density gets the correct 3D material density."""

        class StrangeMaterial(Material):
            """material designed to make the test easier to understand"""

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
        self.assertGreater(
            self.component.getBoundingCircleOuterDiameter(cold=True), 0.0
        )


class TestCircle(TestShapedComponent):
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

    def test_getThermalExpansionFactorConservedMassByLinearExpansionPercent(self):
        """Test that when ARMI thermally expands a circle, mass is conserved.

        .. test:: Test that ARMI correctly thermally expands objects with circular shape.
           :id: TEST_REACTOR_THERMAL_EXPANSION_1
           :links: REQ_REACTOR_THERMAL_EXPANSION
        """
        hotTemp = 700.0
        ref = self.component.material.linearExpansionFactor(
            Tc=hotTemp, T0=self._coldTemp
        )
        cur = self.component.getThermalExpansionFactor(Tc=hotTemp)
        self.assertAlmostEqual(cur, ref)

    def test_getDimension(self):
        hotTemp = 700.0
        ref = self._od * self.component.getThermalExpansionFactor(Tc=hotTemp)
        cur = self.component.getDimension("od", Tc=hotTemp)
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a circle

        .. test:: Test that ARMI can thermally expands a circle
           :id: TEST_REACTOR_THERMAL_EXPANSION_2
           :links: REQ_REACTOR_THERMAL_EXPANSION
        """
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
        od = self.component.getDimension("od")
        idd = self.component.getDimension("id")
        mult = self.component.getDimension("mult")
        ref = math.pi * ((od / 2) ** 2 - (idd / 2) ** 2) * mult
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_componentInteractionsLinkingByDimensions(self):
        r"""Tests linking of components by dimensions."""
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
        """This shows that resolveLinkedDims cannot support names with periods in them"""
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
        r"""Tests linking of components by subtraction."""
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
            * (
                (gap.getDimension("od") / 2.0) ** 2
                - (gap.getDimension("id") / 2.0) ** 2
            )
        )
        fuelArea = (
            fuel.getDimension("mult")
            * math.pi
            * (
                (fuel.getDimension("od") / 2.0) ** 2
                - (fuel.getDimension("id") / 2.0) ** 2
            )
        )
        ref = fuelArea - gapArea
        cur = fuel.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_getNumberDensities(self):
        """Test that demonstrates that number densities can be retrieved on from component."""
        self.component.p.numberDensities = {"NA23": 1.0}
        self.assertEqual(self.component.getNumberDensity("NA23"), 1.0)

    def test_changeNumberDensities(self):
        """Test that demonstates that the number densities on a component can be modified."""
        self.component.p.numberDensities = {"NA23": 1.0}
        self.assertEqual(self.component.getNumberDensity("NA23"), 1.0)
        self.component.changeNDensByFactor(3.0)
        self.assertEqual(self.component.getNumberDensity("NA23"), 3.0)


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
        hotterDim = self.coldOuterDiameter * (
            circle1.material.linearExpansionFactor(self.tCold + 200, self.tCold)
        )
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
            circle1.p.numberDensities[isotope] / circle2.p.numberDensities[isotope],
            circle1.density() / circle2.density(),
        )

        # the colder one has more because it is the same cold outer diameter
        # but it would be taller at the same temperature
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
            thermalExpansionFactorFromColdMatTemp = math.exp(percent / 100)
            self.assertAlmostEqual(
                circle.density() * thermalExpansionFactorFromColdMatTemp,
                circle.material.pseudoDensity(Tc=circle.temperatureInC),
            )
            self.assertAlmostEqual(
                circle.density(),
                circle.material.density(Tc=circle.temperatureInC),
            )

        # brief 2D expansion with set temp to show mass is conserved
        # hot height would come from block value
        warmMass = circle1.density() * circle1.getArea() * hotHeight
        circle1.setTemperature(self.tHot)
        hotMass = circle1.density() * circle1.getArea() * hotHeight
        self.assertAlmostEqual(warmMass, hotMass)
        circle1.setTemperature(self.tWarm)

        # Change temp to circle 2 temp  to show equal to circle2
        # and then change back to show recoverable to original values
        oldArea = circle1.getArea()
        initialDens = circle1.density()

        # when block.setHeight is called (which effectively changes component height)
        # component.setNumberDensity is called (for solid isotopes) to adjust the number
        # density so that now the 2D expansion will be approximated/expanded around
        # the hot temp which is akin to these adjustments
        heightFactor = circle1.getHeightFactor(self.tHot)
        circle1.adjustDensityForHeightExpansion(self.tHot)  # apply temp at new height
        circle1.setTemperature(self.tHot)

        # now its density is same as hot component
        self.assertAlmostEqual(
            circle1.density(),
            circle2.density(),
        )

        # show that mass is conserved after expansion
        circle1NewHotHeight = hotHeight * heightFactor
        self.assertAlmostEqual(
            mass1, circle1.density() * circle1.getArea() * circle1NewHotHeight
        )

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
        Demonstrate that material is conserved at during expansion

        Notes
        -----
        - height taken as cold height and show how quantity is conserved with
          inputHeightsConsideredHot = False
        """
        coldHeight = 1.0
        circle1 = Circle("circle", mat, self.tCold, self.tWarm, self.coldOuterDiameter)
        circle2 = Circle("circle", mat, self.tCold, self.tHot, self.coldOuterDiameter)
        # same as 1 but we will make like 2
        circle1AdjustTo2 = Circle(
            "circle", mat, self.tCold, self.tWarm, self.coldOuterDiameter
        )

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
            # total mass consistent between hot and cold
            # Hot height will be taller
            hotHeight = coldHeight * circle.getThermalExpansionFactor()
            self.assertAlmostEqual(
                coldHeight
                * circle.getArea(cold=True)
                * circle.material.density(Tc=circle.inputTemperatureInC),
                hotHeight * circle.getArea() * circle.density(),
            )


class TestTriangle(TestShapedComponent):
    componentCls = Triangle
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "base": 3.0,
        "height": 2.0,
        "mult": 30,
    }

    def test_getArea(self):
        b = self.component.getDimension("base")
        h = self.component.getDimension("height")
        mult = self.component.getDimension("mult")
        ref = mult * 0.5 * b * h
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a triangle

        .. test:: Test that ARMI can thermally expands a triangle
           :id: TEST_REACTOR_THERMAL_EXPANSION_3
           :links: REQ_REACTOR_THERMAL_EXPANSION
        """
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_dimensionThermallyExpands(self):
        expandedDims = ["base", "height", "mult"]
        ref = [True, True, False]
        for i, d in enumerate(expandedDims):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])


class TestRectangle(TestShapedComponent):
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
        refArea = dims["mult"] * (
            dims["lengthOuter"] * dims["widthOuter"]
            - dims["lengthInner"] * dims["widthInner"]
        )
        negativeRectangle = Rectangle("test", "Void", **dims)
        self.assertAlmostEqual(negativeRectangle.getArea(), refArea)
        with self.assertRaises(ArithmeticError):
            negativeRectangle = Rectangle("test", "UZr", **dims)
            negativeRectangle.getArea()

    def test_getBoundingCircleOuterDiameter(self):
        ref = math.sqrt(61.0)
        cur = self.component.getBoundingCircleOuterDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getCircleInnerDiameter(self):
        cur = self.component.getCircleInnerDiameter(cold=True)
        self.assertAlmostEqual(math.sqrt(25.0), cur)

    def test_getArea(self):
        outerL = self.component.getDimension("lengthOuter")
        innerL = self.component.getDimension("lengthInner")
        outerW = self.component.getDimension("widthOuter")
        innerW = self.component.getDimension("widthInner")
        mult = self.component.getDimension("mult")
        ref = mult * (outerL * outerW - innerL * innerW)
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a rectangle

        .. test:: Test that ARMI can thermally expands a rectangle
           :id: TEST_REACTOR_THERMAL_EXPANSION_4
           :links: REQ_REACTOR_THERMAL_EXPANSION
        """
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
        ref = math.sqrt(50)
        cur = self.component.getBoundingCircleOuterDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getArea(self):
        outerL = self.component.getDimension("lengthOuter")
        outerW = self.component.getDimension("widthOuter")
        mult = self.component.getDimension("mult")
        ref = mult * (outerL * outerW)
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a solid rectangle

        .. test:: Test that ARMI can thermally expands a solid rectangle
           :id: TEST_REACTOR_THERMAL_EXPANSION_5
           :links: REQ_REACTOR_THERMAL_EXPANSION
        """
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_dimensionThermallyExpands(self):
        expandedDims = ["lengthOuter", "widthOuter", "mult"]
        ref = [True, True, False]
        for i, d in enumerate(expandedDims):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])


class TestSquare(TestShapedComponent):
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
        refArea = dims["mult"] * (
            dims["widthOuter"] * dims["widthOuter"]
            - dims["widthInner"] * dims["widthInner"]
        )
        negativeRectangle = Square("test", "Void", **dims)
        self.assertAlmostEqual(negativeRectangle.getArea(), refArea)
        with self.assertRaises(ArithmeticError):
            negativeRectangle = Square("test", "UZr", **dims)
            negativeRectangle.getArea()

    def test_getBoundingCircleOuterDiameter(self):
        ref = math.sqrt(18.0)
        cur = self.component.getBoundingCircleOuterDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getCircleInnerDiameter(self):
        ref = math.sqrt(8.0)
        cur = self.component.getCircleInnerDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getArea(self):
        outerW = self.component.getDimension("widthOuter")
        innerW = self.component.getDimension("widthInner")
        mult = self.component.getDimension("mult")
        ref = mult * (outerW * outerW - innerW * innerW)
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a square

        .. test:: Test that ARMI can thermally expands a square
           :id: TEST_REACTOR_THERMAL_EXPANSION_6
           :links: REQ_REACTOR_THERMAL_EXPANSION
        """
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
        """Test that ARMI can thermally expands a cube

        .. test:: Test that ARMI can thermally expands a cube
           :id: TEST_REACTOR_THERMAL_EXPANSION_7
           :links: REQ_REACTOR_THERMAL_EXPANSION
        """
        self.assertFalse(self.component.THERMAL_EXPANSION_DIMS)


class TestHexagon(TestShapedComponent):
    componentCls = Hexagon
    componentDims = {"Tinput": 25.0, "Thot": 430.0, "op": 10.0, "ip": 5.0, "mult": 1}

    def test_getPerimeter(self):
        ip = self.component.getDimension("ip")
        mult = self.component.getDimension("mult")
        ref = 6 * (ip / math.sqrt(3)) * mult
        cur = self.component.getPerimeter()
        self.assertAlmostEqual(cur, ref)

    def test_getBoundingCircleOuterDiameter(self):
        ref = 2.0 * 10 / math.sqrt(3)
        cur = self.component.getBoundingCircleOuterDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getCircleInnerDiameter(self):
        ref = 2.0 * 5.0 / math.sqrt(3)
        cur = self.component.getCircleInnerDiameter(cold=True)
        self.assertAlmostEqual(ref, cur)

    def test_getArea(self):
        cur = self.component.getArea()
        mult = self.component.getDimension("mult")
        op = self.component.getDimension("op")
        ip = self.component.getDimension("ip")
        ref = math.sqrt(3.0) / 2.0 * (op ** 2 - ip ** 2) * mult
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a hexagon

        .. test:: Test that ARMI can thermally expands a hexagon
           :id: TEST_REACTOR_THERMAL_EXPANSION_8
           :links: REQ_REACTOR_THERMAL_EXPANSION
        """
        self.assertTrue(self.component.THERMAL_EXPANSION_DIMS)

    def test_dimensionThermallyExpands(self):
        expandedDims = ["op", "ip", "mult"]
        ref = [True, True, False]
        for i, d in enumerate(expandedDims):
            cur = d in self.component.THERMAL_EXPANSION_DIMS
            self.assertEqual(cur, ref[i])


class TestHoledHexagon(TestShapedComponent):
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
        op = self.component.getDimension("op")
        odHole = self.component.getDimension("holeOD")
        nHoles = self.component.getDimension("nHoles")
        mult = self.component.getDimension("mult")
        hexarea = math.sqrt(3.0) / 2.0 * (op ** 2)
        holeArea = nHoles * math.pi * ((odHole / 2.0) ** 2)
        ref = mult * (hexarea - holeArea)
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a holed hexagon

        .. test:: Test that ARMI can thermally expands a holed hexagon
           :id: TEST_REACTOR_THERMAL_EXPANSION_9
           :links: REQ_REACTOR_THERMAL_EXPANSION
        """
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
        od = self.component.getDimension("od")
        holeOP = self.component.getDimension("holeOP")
        mult = self.component.getDimension("mult")
        hexarea = math.sqrt(3.0) / 2.0 * (holeOP ** 2)
        holeArea = math.pi * ((od / 2.0) ** 2)
        ref = mult * (holeArea - hexarea)
        cur = self.component.getArea()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        """Test that ARMI can thermally expands a holed hexagon

        .. test:: Test that ARMI can thermally expands a holed hexagon
           :id: TEST_REACTOR_THERMAL_EXPANSION_10
           :links: REQ_REACTOR_THERMAL_EXPANSION
        """
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
        ref = (self.length ** 2 + self.width ** 2) ** 0.5
        cur = self.component.getBoundingCircleOuterDiameter()
        self.assertAlmostEqual(ref, cur)

    def test_getCircleInnerDiameter(self):
        ref = self.componentDims["holeOD"]
        cur = self.component.getCircleInnerDiameter(cold=True)
        self.assertEqual(ref, cur)

    def test_getArea(self):
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
        cur = self.component.getArea()
        axialPitch = self.component.getDimension("axialPitch")
        helixDiameter = self.component.getDimension("helixDiameter")
        innerDiameter = self.component.getDimension("id")
        outerDiameter = self.component.getDimension("od")
        mult = self.component.getDimension("mult")
        c = axialPitch / (2.0 * math.pi)
        helixFactor = math.sqrt((helixDiameter / 2.0) ** 2 + c ** 2) / c
        ref = (
            mult
            * math.pi
            * (outerDiameter ** 2 / 4.0 - innerDiameter ** 2 / 4.0)
            * helixFactor
        )
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
        """testing the Helix class performs as expected with various inputs"""
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
        od = self.component.getDimension("od")
        idd = self.component.getDimension("id")
        mult = self.component.getDimension("mult")
        ref = mult * 4.0 / 3.0 * math.pi * ((od / 2.0) ** 3 - (idd / 2.0) ** 3)
        cur = self.component.getVolume()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        self.assertFalse(self.component.THERMAL_EXPANSION_DIMS)


class TestTorus(TestShapedComponent):
    componentCls = Torus
    componentDims = {
        "Tinput": 25.0,
        "Thot": 430.0,
        "inner_minor_radius": 28.73,
        "outer_minor_radius": 30,
        "major_radius": 140,
    }

    def test_thermallyExpands(self):
        self.assertFalse(self.component.THERMAL_EXPANSION_DIMS)

    def test_getVolume(self):
        expectedVolume = 2.0 * 103060.323859
        self.assertAlmostEqual(self.component.getVolume() / expectedVolume, 1.0)


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
        radialArea = math.pi * (outerRad ** 2 - innerRad ** 2)
        aziFraction = (outerTheta - innerTheta) / (math.pi * 2.0)
        ref = mult * radialArea * aziFraction * height
        cur = self.component.getVolume()
        self.assertAlmostEqual(cur, ref)

    def test_thermallyExpands(self):
        self.assertFalse(self.component.THERMAL_EXPANSION_DIMS)

    def test_getBoundingCircleOuterDiameter(self):
        self.assertEqual(
            self.component.getBoundingCircleOuterDiameter(cold=True), 170.0
        )


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
        radialArea = math.pi * (outerRad ** 2 - innerRad ** 2)
        aziFraction = (outerTheta - innerTheta) / (math.pi * 2.0)
        ref = mult * radialArea * aziFraction * height
        cur = self.component.getVolume()
        self.assertAlmostEqual(cur, ref)

    def test_updateDims(self):
        self.assertEqual(self.component.getDimension("inner_radius"), 110)
        self.assertEqual(self.component.getDimension("radius_differential"), 60)
        self.component.updateDims()
        self.assertEqual(self.component.getDimension("outer_radius"), 170)
        self.assertEqual(self.component.getDimension("outer_axial"), 220)
        self.assertEqual(self.component.getDimension("outer_theta"), 2 * math.pi)

    def test_thermallyExpands(self):
        self.assertFalse(self.component.THERMAL_EXPANSION_DIMS)

    def test_getBoundingCircleOuterDiameter(self):
        self.assertEqual(self.component.getBoundingCircleOuterDiameter(cold=True), 170)


class TestMaterialAdjustments(unittest.TestCase):
    """Tests to make sure enrichment and mass fractions can be adjusted properly."""

    def setUp(self):
        dims = {"Tinput": 25.0, "Thot": 600.0, "od": 10.0, "id": 5.0, "mult": 1.0}
        self.fuel = Circle("fuel", "UZr", **dims)

        class fakeBlock:
            def getHeight(self):  # unit height
                return 1.0

            def getSymmetryFactor(self):
                return 1.0

        self.fuel.parent = fakeBlock()

    def test_setMassFrac(self):
        """Make sure we can set a mass fraction properly."""
        target35 = 0.2
        self.fuel.setMassFrac("U235", target35)
        self.assertAlmostEqual(self.fuel.getMassFrac("U235"), target35)

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

        self.fuel.adjustMassFrac(
            nuclideToAdjust="U235", elementToHoldConstant="ZR", val=u235Frac
        )
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
        self.assertAlmostEqual(
            self.fuel.getMassFrac("U235") + self.fuel.getMassFrac("U238"), 1.0
        )

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


if __name__ == "__main__":
    # import sys; sys.argv = ['', 'TestMaterialAdjustments.test_adjustMassFrac_U235']
    unittest.main()
