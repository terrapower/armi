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

"""Components represented by complex shapes, and typically less widely used."""

import math

from armi.reactor.components import ShapedComponent, basicShapes, componentParameters


class HoledHexagon(basicShapes.Hexagon):
    """Hexagon with n uniform circular holes hollowed out of it.

    .. impl:: Holed hexagon shaped Component
        :id: I_ARMI_COMP_SHAPES5
        :implements: R_ARMI_COMP_SHAPES

        This class provides an implementation for a holed hexagonal Component. This includes setting
        key parameters such as its material, temperature, and dimensions. It also provides the
        capability to retrieve the diameter of the inner hole via the ``getCircleInnerDiameter``
        method.
    """

    THERMAL_EXPANSION_DIMS = {"op", "holeOD"}

    pDefs = componentParameters.getHoledHexagonParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        op,
        holeOD,
        nHoles,
        mult=1.0,
        modArea=None,
        isotopics=None,
        mergeWith=None,
        components=None,
    ):
        ShapedComponent.__init__(
            self,
            name,
            material,
            Tinput,
            Thot,
            isotopics=isotopics,
            mergeWith=mergeWith,
            components=components,
        )
        self._linkAndStoreDimensions(components, op=op, holeOD=holeOD, nHoles=nHoles, mult=mult, modArea=modArea)

    def getComponentArea(self, cold=False, Tc=None):
        """Computes the area for the hexagon with n number of circular holes in cm^2."""
        op = self.getDimension("op", cold=cold, Tc=Tc)
        holeOD = self.getDimension("holeOD", cold=cold, Tc=Tc)
        nHoles = self.getDimension("nHoles", cold=cold, Tc=Tc)
        mult = self.getDimension("mult")
        hexArea = math.sqrt(3.0) / 2.0 * (op**2)
        circularArea = nHoles * math.pi * ((holeOD / 2.0) ** 2)
        area = mult * (hexArea - circularArea)
        return area

    def getCircleInnerDiameter(self, Tc=None, cold=False):
        """
        For the special case of only one single hole, returns the diameter of that hole.

        For any other case, returns 0.0 because an "circle inner diameter" becomes undefined.
        """
        if self.getDimension("nHoles") == 1:
            return self.getDimension("holeOD", Tc, cold)
        else:
            return 0.0


class HexHoledCircle(basicShapes.Circle):
    """Circle with a single uniform hexagonal hole hollowed out of it."""

    THERMAL_EXPANSION_DIMS = {"od", "holeOP"}

    pDefs = componentParameters.getHexHoledCircleParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        od,
        holeOP,
        mult=1.0,
        modArea=None,
        isotopics=None,
        mergeWith=None,
        components=None,
    ):
        ShapedComponent.__init__(
            self,
            name,
            material,
            Tinput,
            Thot,
            isotopics=isotopics,
            mergeWith=mergeWith,
            components=components,
        )
        self._linkAndStoreDimensions(components, od=od, holeOP=holeOP, mult=mult, modArea=modArea)

    def getComponentArea(self, cold=False, Tc=None):
        r"""Computes the area for the circle with one hexagonal hole."""
        od = self.getDimension("od", cold=cold, Tc=Tc)
        holeOP = self.getDimension("holeOP", cold=cold, Tc=Tc)
        mult = self.getDimension("mult")
        hexArea = math.sqrt(3.0) / 2.0 * (holeOP**2)
        circularArea = math.pi * ((od / 2.0) ** 2)
        area = mult * (circularArea - hexArea)
        return area

    def getCircleInnerDiameter(self, Tc=None, cold=False):
        """Returns the diameter of the hole equal to the hexagon outer pitch."""
        return self.getDimension("holeOP", Tc, cold)


class FilletedHexagon(basicShapes.Hexagon):
    """
    A hexagon with a hexagonal hole cut out of the center of it, where the corners of both the
    outer and inner hexagons are rounded, with independent radii of curvature.

    By default, the inner hole has a diameter of zero, making this a solid object with no hole.
    """

    THERMAL_EXPANSION_DIMS = {"iR", "oR", "ip", "op"}

    pDefs = componentParameters.getFilletedHexagonParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        op,
        ip=0.0,
        iR=0.0,
        oR=0.0,
        mult=1.0,
        modArea=None,
        isotopics=None,
        mergeWith=None,
        components=None,
    ):
        ShapedComponent.__init__(
            self,
            name,
            material,
            Tinput,
            Thot,
            isotopics=isotopics,
            mergeWith=mergeWith,
            components=components,
        )
        self._linkAndStoreDimensions(components, op=op, ip=ip, iR=iR, oR=oR, mult=mult, modArea=modArea)

    @staticmethod
    def _area(D, r):
        """Helper function, to calculate the area of a hexagon with rounded corners."""
        if D <= 0.0:
            return 0.0

        area = 1.0 - (1.0 - (math.pi / (2.0 * math.sqrt(3)))) * (2 * r / D) ** 2
        area *= (math.sqrt(3.0) / 2.0) * D**2
        return area

    def getComponentArea(self, cold=False, Tc=None):
        """Computes the area for the rounded hexagon component in cm^2."""
        op = self.getDimension("op", cold=cold, Tc=Tc)
        ip = self.getDimension("ip", cold=cold, Tc=Tc)
        oR = self.getDimension("oR", cold=cold, Tc=Tc)
        iR = self.getDimension("iR", cold=cold, Tc=Tc)
        mult = self.getDimension("mult")

        area = self._area(op, oR) - self._area(ip, iR)
        area *= mult
        return area


class HoledRectangle(basicShapes.Rectangle):
    """Rectangle with one circular hole in it."""

    THERMAL_EXPANSION_DIMS = {"lengthOuter", "widthOuter", "holeOD"}

    pDefs = componentParameters.getHoledRectangleParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        holeOD,
        lengthOuter=None,
        widthOuter=None,
        mult=1.0,
        modArea=None,
        isotopics=None,
        mergeWith=None,
        components=None,
    ):
        ShapedComponent.__init__(
            self,
            name,
            material,
            Tinput,
            Thot,
            isotopics=isotopics,
            mergeWith=mergeWith,
            components=components,
        )
        self._linkAndStoreDimensions(
            components,
            lengthOuter=lengthOuter,
            widthOuter=widthOuter,
            holeOD=holeOD,
            mult=mult,
            modArea=modArea,
        )

    def getComponentArea(self, cold=False, Tc=None):
        """Computes the area (in cm^2) for the the rectangle with one hole in it."""
        length = self.getDimension("lengthOuter", cold=cold, Tc=Tc)
        width = self.getDimension("widthOuter", cold=cold, Tc=Tc)
        rectangleArea = length * width
        holeOD = self.getDimension("holeOD", cold=cold, Tc=Tc)
        circularArea = math.pi * ((holeOD / 2.0) ** 2)
        mult = self.getDimension("mult")
        area = mult * (rectangleArea - circularArea)
        return area

    def getCircleInnerDiameter(self, Tc=None, cold=False):
        """Returns the ``holeOD``."""
        return self.getDimension("holeOD", Tc, cold)


class HoledSquare(basicShapes.Square):
    """Square with one circular hole in it.

    .. impl:: Holed square shaped Component
        :id: I_ARMI_COMP_SHAPES6
        :implements: R_ARMI_COMP_SHAPES

        This class provides an implementation for a holed square Component. This includes setting
        key parameters such as its material, temperature, and dimensions. It also includes methods
        to retrieve geometric dimension information unique to holed squares via the
        ``getComponentArea`` and ``getCircleInnerDiameter`` methods.
    """

    THERMAL_EXPANSION_DIMS = {"widthOuter", "holeOD"}

    pDefs = componentParameters.getHoledRectangleParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        holeOD,
        widthOuter=None,
        mult=1.0,
        modArea=None,
        isotopics=None,
        mergeWith=None,
        components=None,
    ):
        ShapedComponent.__init__(
            self,
            name,
            material,
            Tinput,
            Thot,
            isotopics=isotopics,
            mergeWith=mergeWith,
            components=components,
        )
        self._linkAndStoreDimensions(components, widthOuter=widthOuter, holeOD=holeOD, mult=mult, modArea=modArea)

    def getComponentArea(self, cold=False, Tc=None):
        """Computes the area (in cm^2) for the the square with one hole in it."""
        width = self.getDimension("widthOuter", cold=cold, Tc=Tc)
        rectangleArea = width**2
        holeOD = self.getDimension("holeOD", cold=cold, Tc=Tc)
        circularArea = math.pi * ((holeOD / 2.0) ** 2)
        mult = self.getDimension("mult")
        area = mult * (rectangleArea - circularArea)
        return area

    def getCircleInnerDiameter(self, Tc=None, cold=False):
        """Returns the ``holeOD``."""
        return self.getDimension("holeOD", Tc, cold)


class Helix(ShapedComponent):
    """A spiral wire component used to model a pin wire-wrap.

    .. impl:: Helix shaped Component
        :id: I_ARMI_COMP_SHAPES7
        :implements: R_ARMI_COMP_SHAPES

        This class provides the implementation for a helical Component. This includes setting key
        parameters such as its material, temperature, and dimensions. It also includes the
        ``getComponentArea`` method to retrieve the area of a helix. Helixes can be used for wire
        wrapping around fuel pins in fast reactor designs.

    Notes
    -----
    http://mathworld.wolfram.com/Helix.html
    In a single rotation with an axial climb of P, the length of the helix will be a factor of
    2*pi*sqrt(r^2+c^2)/2*pi*c longer than vertical length L. P = 2*pi*c.

    - od: outer diameter of the helix wire
    - id: inner diameter of the helix wire (if non-zero, helix wire is annular.)
    - axialPitch: vertical distance between wraps. Is also the axial distance required to complete a
                  full 2*pi rotation.
    - helixDiameter: The helix diameter is the distance from the center of the wire-wrap on one side
                     to the center of the wire-wrap on the opposite side (can be visualized if the
                     axial pitch is 0.0 - creates a circle).
    """

    is3D = False

    THERMAL_EXPANSION_DIMS = {"od", "id", "axialPitch", "helixDiameter"}

    pDefs = componentParameters.getHelixParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        od,
        axialPitch,
        helixDiameter,
        mult=1.0,
        id=0.0,
        modArea=None,
        isotopics=None,
        mergeWith=None,
        components=None,
    ):
        ShapedComponent.__init__(
            self,
            name,
            material,
            Tinput,
            Thot,
            isotopics=isotopics,
            mergeWith=mergeWith,
            components=components,
        )
        self._linkAndStoreDimensions(
            components,
            od=od,
            axialPitch=axialPitch,
            mult=mult,
            helixDiameter=helixDiameter,
            id=id,
            modArea=modArea,
        )

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        """The diameter of a circle which is encompassed by the exterior of the wire-wrap."""
        return self.getDimension("helixDiameter", Tc, cold=cold) + self.getDimension("od", Tc, cold)

    def getCircleInnerDiameter(self, Tc=None, cold=False):
        """The diameter of a circle which is encompassed by the interior of the wire-wrap.

        This should be equal to the outer diameter of the pin in which the wire is wrapped around.
        """
        return self.getDimension("helixDiameter", Tc, cold=cold) - self.getDimension("od", Tc, cold)

    def getComponentArea(self, cold=False, Tc=None):
        """Computes the area for the helix in cm^2."""
        ap = self.getDimension("axialPitch", cold=cold, Tc=Tc)
        hd = self.getDimension("helixDiameter", cold=cold, Tc=Tc)
        id = self.getDimension("id", cold=cold, Tc=Tc)
        od = self.getDimension("od", cold=cold, Tc=Tc)
        mult = self.getDimension("mult")
        c = ap / (2.0 * math.pi)
        helixFactor = math.sqrt((hd / 2.0) ** 2 + c**2) / c
        area = mult * math.pi * ((od / 2.0) ** 2 - (id / 2.0) ** 2) * helixFactor
        return area
