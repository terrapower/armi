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

from armi.reactor.components import ShapedComponent
from armi.reactor.components import componentParameters
from armi.reactor.components import basicShapes


class HoledHexagon(basicShapes.Hexagon):
    """Hexagon with n uniform circular holes hollowed out of it."""

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
        self._linkAndStoreDimensions(
            components, op=op, holeOD=holeOD, nHoles=nHoles, mult=mult, modArea=modArea
        )

    def getComponentArea(self, cold=False):
        r"""Computes the area for the hexagon with n number of circular holes in cm^2."""
        op = self.getDimension("op", cold=cold)
        holeOD = self.getDimension("holeOD", cold=cold)
        nHoles = self.getDimension("nHoles", cold=cold)
        mult = self.getDimension("mult")
        hexArea = math.sqrt(3.0) / 2.0 * (op**2)
        circularArea = nHoles * math.pi * ((holeOD / 2.0) ** 2)
        area = mult * (hexArea - circularArea)
        return area

    def getCircleInnerDiameter(self, Tc=None, cold=False):
        """
        For the special case of only one single hole, returns the
        diameter of that hole.

        For any other case, returns 0.0 because an "circle inner diameter" becomes
        undefined.
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
        self._linkAndStoreDimensions(
            components, od=od, holeOP=holeOP, mult=mult, modArea=modArea
        )

    def getComponentArea(self, cold=False):
        r"""Computes the area for the circle with one hexagonal hole."""
        od = self.getDimension("od", cold=cold)
        holeOP = self.getDimension("holeOP", cold=cold)
        mult = self.getDimension("mult")
        hexArea = math.sqrt(3.0) / 2.0 * (holeOP**2)
        circularArea = math.pi * ((od / 2.0) ** 2)
        area = mult * (circularArea - hexArea)
        return area

    def getCircleInnerDiameter(self, Tc=None, cold=False):
        """Returns the diameter of the hole equal to the hexagon outer pitch."""
        return self.getDimension("holeOP", Tc, cold)


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

    def getComponentArea(self, cold=False):
        r"""Computes the area (in cm^2) for the the rectangle with one hole in it."""
        length = self.getDimension("lengthOuter", cold=cold)
        width = self.getDimension("widthOuter", cold=cold)
        rectangleArea = length * width
        holeOD = self.getDimension("holeOD", cold=cold)
        circularArea = math.pi * ((holeOD / 2.0) ** 2)
        mult = self.getDimension("mult")
        area = mult * (rectangleArea - circularArea)
        return area

    def getCircleInnerDiameter(self, Tc=None, cold=False):
        """Returns the ``holeOD``."""
        return self.getDimension("holeOD", Tc, cold)


class HoledSquare(basicShapes.Square):
    """Square with one circular hole in it."""

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
        self._linkAndStoreDimensions(
            components, widthOuter=widthOuter, holeOD=holeOD, mult=mult, modArea=modArea
        )

    def getComponentArea(self, cold=False):
        r"""Computes the area (in cm^2) for the the square with one hole in it."""
        width = self.getDimension("widthOuter", cold=cold)
        rectangleArea = width**2
        holeOD = self.getDimension("holeOD", cold=cold)
        circularArea = math.pi * ((holeOD / 2.0) ** 2)
        mult = self.getDimension("mult")
        area = mult * (rectangleArea - circularArea)
        return area

    def getCircleInnerDiameter(self, Tc=None, cold=False):
        """Returns the ``holeOD``."""
        return self.getDimension("holeOD", Tc, cold)


class Helix(ShapedComponent):
    """A spiral wire component used to model a pin wire-wrap.

    Notes
    -----
    http://mathworld.wolfram.com/Helix.html
    In a single rotation with an axial climb of P, the length of the helix will be a factor of
    2*pi*sqrt(r^2+c^2)/2*pi*c longer than vertical length L. P = 2*pi*c.

    - od: outer diameter of the helix wire
    - id: inner diameter of the helix wire (if non-zero, helix wire is annular.)
    - axialPitch: vertical distance between wraps. Is also the axial distance required to complete
                  a full 2*pi rotation.
    - helixDiameter: The helix diameter is the distance from the center of the
                     wire-wrap on one side to the center of the wire-wrap on the opposite side
                     (can be visualized if the axial pitch is 0.0 - creates a circle).
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
        return self.getDimension("helixDiameter", Tc, cold=cold) + self.getDimension(
            "od", Tc, cold
        )

    def getCircleInnerDiameter(self, Tc=None, cold=False):
        """The diameter of a circle which is encompassed by the interior of the wire-wrap.

        - should be equal to the outer diameter of the pin in which the wire is wrapped around
        """
        return self.getDimension("helixDiameter", Tc, cold=cold) - self.getDimension(
            "od", Tc, cold
        )

    def getComponentArea(self, cold=False):
        """Computes the area for the helix in cm^2."""
        ap = self.getDimension("axialPitch", cold=cold)
        hd = self.getDimension("helixDiameter", cold=cold)
        id = self.getDimension("id", cold=cold)
        od = self.getDimension("od", cold=cold)
        mult = self.getDimension("mult")
        c = ap / (2.0 * math.pi)
        helixFactor = math.sqrt((hd / 2.0) ** 2 + c**2) / c
        area = mult * math.pi * ((od / 2.0) ** 2 - (id / 2.0) ** 2) * helixFactor
        return area
