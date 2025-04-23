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

"""Unit testing file for basic shapes."""
import math
import unittest

from armi.materials import resolveMaterialClassByName
from armi.reactor.components.basicShapes import (
    Circle,
    Hexagon,
    Rectangle,
    SolidRectangle,
    Square,
    Triangle,
)


class TestBasicShapes(unittest.TestCase):
    """Class for testing basic shapes."""

    @classmethod
    def setUpClass(cls):
        cls.material = resolveMaterialClassByName("HT9")()

    def test_circleArea(self):
        od = 2.0
        id = 1.5
        comp = Circle(
            "Test", material=self.material, Tinput=20, Thot=300, od=od, id=id, mult=2
        )

        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), math.pi * (od**2 / 4 - id**2 / 4) * 2
        )
        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0)
        )

        odHot = comp.getDimension("od")
        idHot = comp.getDimension("id")
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False),
            math.pi * (odHot**2 / 4 - idHot**2 / 4) * 2,
        )
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300)
        )

    def test_hexagonArea(self):
        op = 2.0
        ip = 1.5
        comp = Hexagon(
            "Test", material=self.material, Tinput=20, Thot=300, op=op, ip=ip, mult=2
        )

        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), math.sqrt(3.0) * (op**2 - ip**2)
        )
        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0)
        )

        opHot = comp.getDimension("op")
        ipHot = comp.getDimension("ip")
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False),
            math.sqrt(3.0) * (opHot**2 - ipHot**2),
        )
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300)
        )

    def test_rectangleArea(self):
        lo = 2.0
        li = 1.5
        wo = 2.5
        wi = 1.25
        comp = Rectangle(
            "Test",
            material=self.material,
            Tinput=20,
            Thot=300,
            lengthOuter=lo,
            lengthInner=li,
            widthOuter=wo,
            widthInner=wi,
            mult=2,
        )

        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), 2 * (lo * wo - li * wi)
        )
        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0)
        )

        loHot = comp.getDimension("lengthOuter")
        liHot = comp.getDimension("lengthInner")
        woHot = comp.getDimension("widthOuter")
        wiHot = comp.getDimension("widthInner")
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False), 2 * (loHot * woHot - liHot * wiHot)
        )
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300)
        )

    def test_solidRectangleArea(self):
        lo = 2.0
        wo = 2.5
        comp = SolidRectangle(
            "Test",
            material=self.material,
            Tinput=20,
            Thot=300,
            lengthOuter=lo,
            widthOuter=wo,
            mult=2,
        )

        self.assertAlmostEqual(comp.getComponentArea(cold=True), 2 * lo * wo)
        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0)
        )

        loHot = comp.getDimension("lengthOuter")
        woHot = comp.getDimension("widthOuter")
        self.assertAlmostEqual(comp.getComponentArea(cold=False), 2 * loHot * woHot)
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300)
        )

    def test_squareArea(self):
        wo = 2.5
        wi = 1.25
        comp = Square(
            "Test",
            material=self.material,
            Tinput=20,
            Thot=300,
            widthOuter=wo,
            widthInner=wi,
            mult=2,
        )

        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), 2 * (wo**2 - wi**2)
        )
        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0)
        )

        woHot = comp.getDimension("widthOuter")
        wiHot = comp.getDimension("widthInner")
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False), 2 * (woHot**2 - wiHot**2)
        )
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300)
        )

    def test_triangleArea(self):
        base = 2.5
        height = 1.25
        comp = Triangle(
            "Test",
            material=self.material,
            Tinput=20,
            Thot=300,
            base=base,
            height=height,
            mult=2,
        )

        self.assertAlmostEqual(comp.getComponentArea(cold=True), base * height)
        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0)
        )

        baseHot = comp.getDimension("base")
        heightHot = comp.getDimension("height")
        self.assertAlmostEqual(comp.getComponentArea(cold=False), baseHot * heightHot)
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300)
        )
