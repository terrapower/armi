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
from armi.reactor.components.complexShapes import (
    HexHoledCircle,
    HoledHexagon,
    HoledRectangle,
    HoledSquare,
)


class TestComplexShapes(unittest.TestCase):
    """Class for testing complex shapes."""

    @classmethod
    def setUpClass(cls):
        cls.material = resolveMaterialClassByName("HT9")()

    @staticmethod
    def circArea(d):
        return math.pi * (d / 2) ** 2

    @staticmethod
    def hexArea(op):
        return math.sqrt(3.0) / 2.0 * op**2

    @staticmethod
    def rectArea(l, w):
        return l * w

    def test_holedHexagon(self):
        op = 2.0
        holeOD = 0.5
        nHoles = 2
        comp = HoledHexagon(
            "TestHoledHexagon",
            material=self.material,
            Tinput=20,
            Thot=300,
            op=op,
            holeOD=holeOD,
            nHoles=nHoles,
            mult=2,
        )

        self.assertAlmostEqual(
            comp.getComponentArea(cold=True),
            (self.hexArea(op) - nHoles * self.circArea(holeOD)) * 2,
        )
        self.assertAlmostEqual(comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0))

        opHot = comp.getDimension("op")
        holeODHot = comp.getDimension("holeOD")
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False),
            (self.hexArea(opHot) - nHoles * self.circArea(holeODHot)) * 2,
        )
        self.assertAlmostEqual(comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300))

        # Test that holeRadFromCenter does not change the area.
        comp2 = HoledHexagon(
            "TestHoledHexagonHoleRadFromCenter",
            material=self.material,
            Tinput=20,
            Thot=300,
            op=op,
            holeOD=holeOD,
            nHoles=nHoles,
            holeRadFromCenter=(op + holeOD) / 2,
            mult=2,
        )
        self.assertAlmostEqual(comp.getComponentArea(cold=True), comp2.getComponentArea(cold=True))
        self.assertAlmostEqual(comp.getComponentArea(cold=False), comp2.getComponentArea(cold=False))

        compHoleRadFromCenter = HoledHexagon(
            "TestHoledHexagon33",
            material=self.material,
            Tinput=20,
            Thot=300,
            op=op,
            holeOD=holeOD,
            nHoles=nHoles,
            holeRadFromCenter=0.5,
            mult=2,
        )
        self.assertEqual(compHoleRadFromCenter.getDimension("holeRadFromCenter", cold=True, Tc=500), 0.5)
        self.assertGreater(compHoleRadFromCenter.getDimension("holeRadFromCenter", cold=False, Tc=500), 0.5)

    def test_holedRectangle(self):
        lo = 2.0
        wo = 3.0
        holeOD = 0.5
        comp = HoledRectangle(
            "Test",
            material=self.material,
            Tinput=20,
            Thot=300,
            lengthOuter=lo,
            widthOuter=wo,
            holeOD=holeOD,
            mult=2,
        )

        self.assertAlmostEqual(
            comp.getComponentArea(cold=True),
            (self.rectArea(lo, wo) - self.circArea(holeOD)) * 2,
        )
        self.assertAlmostEqual(comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0))

        loHot = comp.getDimension("lengthOuter")
        woHot = comp.getDimension("widthOuter")
        holeODHot = comp.getDimension("holeOD")
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False),
            (self.rectArea(loHot, woHot) - self.circArea(holeODHot)) * 2,
        )
        self.assertAlmostEqual(comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300))

    def test_holedSquare(self):
        wo = 3.0
        holeOD = 0.5
        comp = HoledSquare(
            "Test",
            material=self.material,
            Tinput=20,
            Thot=300,
            widthOuter=wo,
            holeOD=holeOD,
            mult=2,
        )

        self.assertAlmostEqual(
            comp.getComponentArea(cold=True),
            (self.rectArea(wo, wo) - self.circArea(holeOD)) * 2,
        )
        self.assertAlmostEqual(comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0))

        woHot = comp.getDimension("widthOuter")
        holeODHot = comp.getDimension("holeOD")
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False),
            (self.rectArea(woHot, woHot) - self.circArea(holeODHot)) * 2,
        )
        self.assertAlmostEqual(comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300))

    def test_hexHoledCircle(self):
        od = 3.0
        holeOP = 0.5
        comp = HexHoledCircle(
            "Test",
            material=self.material,
            Tinput=20,
            Thot=300,
            od=od,
            holeOP=holeOP,
            mult=2,
        )

        self.assertAlmostEqual(
            comp.getComponentArea(cold=True),
            (self.circArea(od) - self.hexArea(holeOP)) * 2,
        )
        self.assertAlmostEqual(comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0))

        odHot = comp.getDimension("od")
        holeOPHot = comp.getDimension("holeOP")
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False),
            (self.circArea(odHot) - self.hexArea(holeOPHot)) * 2,
        )
        self.assertAlmostEqual(comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300))
