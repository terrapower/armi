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
Components represented by basic shapes.

Many reactor components can be described in 2D by circles, hexagons, rectangles, etc. These
are defined in this subpackage.
"""

import math

from armi.reactor.components import ShapedComponent
from armi.reactor.components import componentParameters


class Circle(ShapedComponent):
    """A Circle."""

    is3D = False

    THERMAL_EXPANSION_DIMS = {"od", "id"}

    pDefs = componentParameters.getCircleParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        od,
        id=0.0,
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
            components, od=od, id=id, mult=mult, modArea=modArea
        )

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        return max(self.getDimension("id", Tc, cold), self.getDimension("od", Tc, cold))

    def getComponentArea(self, cold=False):
        """Computes the area for the circle component in cm^2."""
        idiam = self.getDimension("id", cold=cold)
        od = self.getDimension("od", cold=cold)
        mult = self.getDimension("mult", cold=cold)
        area = math.pi * (od ** 2 - idiam ** 2) / 4.0
        area *= mult
        return area

    def isEncapsulatedBy(self, other):
        """Return True if this ring lies completely inside the argument component"""
        otherID, otherOD = other.getDimension("id"), other.getDimension("od")
        myID, myOD = self.getDimension("id"), self.getDimension("od")
        return otherID <= myID < otherOD and otherID < myOD <= otherOD


class Hexagon(ShapedComponent):
    """A Hexagon."""

    is3D = False

    THERMAL_EXPANSION_DIMS = {"ip", "op"}

    pDefs = componentParameters.getHexagonParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        op,
        ip=0.0,
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
            components, op=op, ip=ip, mult=mult, modArea=modArea
        )

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        sideLength = self.getDimension("op", Tc, cold) / math.sqrt(3)
        return 2.0 * sideLength

    def getComponentArea(self, cold=False):
        """
        Computes the area for the hexagon component in cm^2.

        Notes
        -----
        http://www3.wolframalpha.com/input/?i=hexagon
        """
        op = self.getDimension("op", cold=cold)
        ip = self.getDimension("ip", cold=cold)
        mult = self.getDimension("mult")
        area = math.sqrt(3.0) / 2.0 * (op ** 2 - ip ** 2)
        area *= mult
        return area

    def getPerimeter(self, Tc=None):
        """Computes the perimeter of the hexagon component in cm."""
        ip = self.getDimension("ip", Tc)
        mult = self.getDimension("mult", Tc)
        perimeter = 6 * (ip / math.sqrt(3)) * mult
        return perimeter

    def getPitchData(self):
        """
        Return the pitch data that should be used to determine block pitch.

        Notes
        -----
        This pitch data should only be used if this is the pitch defining component in
        a block. The block is responsible for determining which component in it is the
        pitch defining component.
        """
        return self.getDimension("op")


class Rectangle(ShapedComponent):
    """A rectangle component."""

    is3D = False

    THERMAL_EXPANSION_DIMS = {"lengthInner", "lengthOuter", "widthInner", "widthOuter"}

    pDefs = componentParameters.getRectangleParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        lengthOuter=None,
        lengthInner=0.0,
        widthOuter=None,
        widthInner=0.0,
        mult=None,
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
            lengthInner=lengthInner,
            widthOuter=widthOuter,
            widthInner=widthInner,
            mult=mult,
            modArea=modArea,
        )

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        lengthO = self.getDimension("lengthOuter", Tc, cold=cold)
        widthO = self.getDimension("widthOuter", Tc, cold=cold)
        return math.sqrt(widthO ** 2 + lengthO ** 2)

    def getComponentArea(self, cold=False):
        """Computes the area of the rectangle in cm^2."""
        lengthO = self.getDimension("lengthOuter", cold=cold)
        widthO = self.getDimension("widthOuter", cold=cold)
        lengthI = self.getDimension("lengthInner", cold=cold)
        widthI = self.getDimension("widthInner", cold=cold)
        mult = self.getDimension("mult")
        area = mult * (lengthO * widthO - lengthI * widthI)
        return area

    def isLatticeComponent(self):
        """Return true if the component is a `lattice component` containing void material and zero area."""
        return self.containsVoidMaterial() and self.getArea() == 0.0

    def getPitchData(self):
        """
        Return the pitch data that should be used to determine block pitch.

        Notes
        -----
        For rectangular components there are two pitches, one for each dimension.
        This pitch data should only be used if this is the pitch defining component in
        a block. The block is responsible for determining which component in it is the
        pitch defining component.
        """
        return (self.getDimension("lengthOuter"), self.getDimension("widthOuter"))


class SolidRectangle(Rectangle):
    """Solid rectangle component."""

    is3D = False

    THERMAL_EXPANSION_DIMS = {"lengthOuter", "widthOuter"}

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        lengthOuter=None,
        widthOuter=None,
        mult=None,
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
            mult=mult,
            modArea=modArea,
        )

        # these need to be set so that we don't try to write NoDefaults to the database.
        # Ultimately, it makes more sense to have the non-Solid Rectangle inherit from
        # this (and probably be called a HollowRectangle or RectangularShell or
        # whatever), since a solid rectangle is more generic of the two. Then the
        # Parameter definitions for the hollow rectangle could inherit from the ones,
        # adding the inner dimensions so that we wouln't need to do this here.
        self.p.lengthInner = 0
        self.p.widthInner = 0

    def getComponentArea(self, cold=False):
        """Computes the area of the solid rectangle in cm^2."""
        lengthO = self.getDimension("lengthOuter", cold=cold)
        widthO = self.getDimension("widthOuter", cold=cold)
        mult = self.getDimension("mult")
        area = mult * (lengthO * widthO)
        return area


class Square(Rectangle):
    """Square component that can be solid or hollow."""

    is3D = False

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        widthOuter=None,
        widthInner=0.0,
        mult=None,
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
            lengthOuter=widthOuter,
            widthOuter=widthOuter,
            widthInner=widthInner,
            lengthInner=widthInner,
            mult=mult,
            modArea=modArea,
        )

    def getComponentArea(self, cold=False):
        """Computes the area of the square in cm^2."""
        widthO = self.getDimension("widthOuter", cold=cold)
        widthI = self.getDimension("widthInner", cold=cold)
        mult = self.getDimension("mult")
        area = mult * (widthO * widthO - widthI * widthI)
        return area

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        widthO = self.getDimension("widthOuter", Tc, cold=cold)
        return math.sqrt(widthO ** 2 + widthO ** 2)

    def getPitchData(self):
        """
        Return the pitch data that should be used to determine block pitch.

        Notes
        -----
        For rectangular components there are two pitches, one for each dimension.
        This pitch data should only be used if this is the pitch defining component in
        a block. The block is responsible for determining which component in it is the
        pitch defining component.
        """
        # both dimensions are the same for a square.
        return (self.getDimension("widthOuter"), self.getDimension("widthOuter"))


class Triangle(ShapedComponent):
    """
    Triangle with defined base and height.

    Notes
    -----
    The exact angles of the triangle are undefined. The exact side lenths and angles
    are not critical to calculation of component area, so area can still be calculated.
    """

    is3D = False

    THERMAL_EXPANSION_DIMS = {"base", "height"}

    pDefs = componentParameters.getTriangleParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        base=None,
        height=None,
        mult=None,
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
            components, base=base, height=height, mult=mult, modArea=modArea
        )

    def getComponentArea(self, cold=False):
        """Computes the area of the triangle in cm^2."""
        base = self.getDimension("base", cold=cold)
        height = self.getDimension("height", cold=cold)
        mult = self.getDimension("mult")
        area = mult * base * height / 2.0
        return area
