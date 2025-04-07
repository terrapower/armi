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
            "Test",
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
        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0)
        )

        opHot = comp.getDimension("op")
        holeODHot = comp.getDimension("holeOD")
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False),
            (self.hexArea(opHot) - nHoles * self.circArea(holeODHot)) * 2,
        )
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300)
        )

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
        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0)
        )

        loHot = comp.getDimension("lengthOuter")
        woHot = comp.getDimension("widthOuter")
        holeODHot = comp.getDimension("holeOD")
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False),
            (self.rectArea(loHot, woHot) - self.circArea(holeODHot)) * 2,
        )
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300)
        )

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
        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0)
        )

        woHot = comp.getDimension("widthOuter")
        holeODHot = comp.getDimension("holeOD")
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False),
            (self.rectArea(woHot, woHot) - self.circArea(holeODHot)) * 2,
        )
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300)
        )

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
        self.assertAlmostEqual(
            comp.getComponentArea(cold=True), comp.getComponentArea(Tc=20.0)
        )

        odHot = comp.getDimension("od")
        holeOPHot = comp.getDimension("holeOP")
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False),
            (self.circArea(odHot) - self.hexArea(holeOPHot)) * 2,
        )
        self.assertAlmostEqual(
            comp.getComponentArea(cold=False), comp.getComponentArea(Tc=300)
        )
