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

"""Three-dimensional shapes."""

import math

from armi.reactor.components import ShapedComponent, componentParameters


class Sphere(ShapedComponent):
    """A spherical component."""

    is3D = True

    THERMAL_EXPANSION_DIMS = {}

    # Just usurp the Circle parameters. This may lead to issues at some point in things like the DB
    # interface, but for now, they are the same params, so why not?
    pDefs = componentParameters.getCircleParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        od=None,
        id=None,
        mult=None,
        modArea=None,
        isotopics=None,
        mergeWith=None,
        components=None,
        loadFromDb=False,
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
            loadFromDb=loadFromDb,
        )
        self._linkAndStoreDimensions(components, od=od, id=id, mult=mult, modArea=modArea)

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        """Abstract bounding circle method that should be overwritten by each shape subclass."""
        return self.getDimension("od")

    def getComponentArea(self, cold=False, Tc=None):
        """Compute an average area over the height."""
        from armi.reactor.blocks import Block  # avoid circular import

        if Tc is not None:
            raise NotImplementedError(f"Cannot calculate area at specified temperature: {Tc}")
        block = self.getAncestor(lambda c: isinstance(c, Block))
        return self.getComponentVolume(cold) / block.getHeight()

    def getComponentVolume(self, cold=False):
        """Computes the volume of the sphere in cm^3."""
        od = self.getDimension("od", cold=cold)
        iD = self.getDimension("id", cold=cold)
        mult = self.getDimension("mult")
        vol = mult * 4.0 / 3.0 * math.pi * ((od / 2.0) ** 3 - (iD / 2.0) ** 3)
        return vol


class Cube(ShapedComponent):
    """More correctly, a rectangular cuboid.

    Optionally, there may be a centric cuboid volume cut out of center of this shape.
    """

    is3D = True

    THERMAL_EXPANSION_DIMS = {}

    pDefs = componentParameters.getCubeParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        lengthOuter=None,
        lengthInner=None,
        widthOuter=None,
        widthInner=None,
        heightOuter=None,
        heightInner=None,
        mult=None,
        modArea=None,
        isotopics=None,
        mergeWith=None,
        components=None,
        loadFromDb=False,
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
            loadFromDb=loadFromDb,
        )
        self._linkAndStoreDimensions(
            components,
            lengthOuter=lengthOuter,
            lengthInner=lengthInner,
            widthOuter=widthOuter,
            widthInner=widthInner,
            heightOuter=heightOuter,
            heightInner=heightInner,
            mult=mult,
            modArea=modArea,
        )

    def getComponentArea(self, cold=False, Tc=None):
        raise NotImplementedError("Cannot compute area of a cube component.")

    def getComponentVolume(self):
        """Computes the volume of the cube in cm^3."""
        lengthO = self.getDimension("lengthOuter")
        widthO = self.getDimension("widthOuter")
        heightO = self.getDimension("heightOuter")
        lengthI = self.getDimension("lengthInner")
        widthI = self.getDimension("widthInner")
        heightI = self.getDimension("heightInner")
        mult = self.getDimension("mult")
        vol = mult * (lengthO * widthO * heightO - lengthI * widthI * heightI)
        return vol


class RadialSegment(ShapedComponent):
    r"""A RadialSegement represents a volume element with thicknesses in the
    azimuthal, radial and axial directions.

    This a 3D projection of a 2D shape that is an angular slice of a ring or circle.

    The 2D shape is like the one below, with an inner and outer position for the
    theta and the radius:

    Image::

        Y
        ^                      -
        |                 -
        |            -XXXX\
        |       -  \XXXXXXX\
        |  theta   |XXXXXXX|
        |-----------------------> radius, X
        |
        |
    """

    is3D = True

    THERMAL_EXPANSION_DIMS = {}

    pDefs = componentParameters.getRadialSegmentParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        inner_radius=None,
        outer_radius=None,
        height=None,
        mult=None,
        inner_theta=0,
        outer_theta=math.pi * 2,
        isotopics=None,
        mergeWith=None,
        components=None,
        loadFromDb=False,
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
            loadFromDb=loadFromDb,
        )
        self._linkAndStoreDimensions(
            components,
            inner_radius=inner_radius,
            outer_radius=outer_radius,
            height=height,
            mult=mult,
            inner_theta=inner_theta,
            outer_theta=outer_theta,
        )

    def getComponentArea(self, refVolume=None, refHeight=None, cold=False, Tc=None):
        if Tc is not None:
            raise NotImplementedError(f"Cannot calculate area at specified temperature: {Tc}")
        if refHeight:
            return (
                (self.getDimension("height", cold=cold) / refHeight)
                * self.getDimension("mult")
                * (
                    math.pi
                    * (
                        self.getDimension("outer_radius", cold=cold) ** 2
                        - self.getDimension("inner_radius", cold=cold) ** 2
                    )
                    * (
                        (self.getDimension("outer_theta", cold=cold) - self.getDimension("inner_theta", cold=cold))
                        / (math.pi * 2.0)
                    )
                )
            )
        if refVolume:
            return (self.getComponentVolume() / refVolume) / self.getDimension("height")
        else:
            return self.getComponentVolume() / self.getDimension("height")

    def getComponentVolume(self):
        mult = self.getDimension("mult")
        outerRad = self.getDimension("outer_radius")
        innerRad = self.getDimension("inner_radius")
        outerTheta = self.getDimension("outer_theta")
        innerTheta = self.getDimension("inner_theta")
        height = self.getDimension("height")
        radialArea = math.pi * (outerRad**2 - innerRad**2)
        aziFraction = (outerTheta - innerTheta) / (math.pi * 2.0)
        vol = mult * radialArea * aziFraction * height
        return vol

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        return 2.0 * self.getDimension("outer_radius", Tc, cold)

    def getCircleInnerDiameter(self, Tc=None, cold=False):
        return 2.0 * self.getDimension("inner_radius", Tc, cold)


class DifferentialRadialSegment(RadialSegment):
    """
    This component class represents a volume element with thicknesses in the
    azimuthal, radial and axial directions. Furthermore it has dependent
    dimensions: (outer theta, outer radius, outer axial) that can be updated
    depending on the 'differential' in the corresponding directions.

    This component class is super useful for defining ThRZ reactors and
    perturbing its dimensions using the optimization modules

    See Also
    --------
    geometry purturbation:
    armi.physics.optimize.OptimizationInterface.modifyCase (ThRZReflectorThickness,ThRZActiveHeight,ThRZActiveRadius)

    mesh updating:
    armi.reactor.reactors.Reactor.importGeom
    """

    is3D = True

    THERMAL_EXPANSION_DIMS = {}

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        inner_radius=None,
        radius_differential=None,
        inner_axial=None,
        height=None,
        inner_theta=0,
        azimuthal_differential=2 * math.pi,
        mult=1,
        isotopics=None,
        mergeWith=None,
        components=None,
        loadFromDb=False,
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
            loadFromDb=loadFromDb,
        )
        self._linkAndStoreDimensions(
            components,
            inner_radius=inner_radius,
            radius_differential=radius_differential,
            inner_axial=inner_axial,
            height=height,
            inner_theta=inner_theta,
            azimuthal_differential=azimuthal_differential,
            mult=mult,
        )
        self.updateDims()

    def updateDims(self, key="", val=None):
        """
        Update the dimensions of differential radial segment component.

        Notes
        -----
        Can be used to update any dimension on the component, but outer_radius, outer_axial, and outer_theta are
        always updated.

        See Also
        --------
        armi.reactor.blocks.Block.updateComponentDims
        """
        self.setDimension(key, val)
        self.setDimension(
            "outer_radius",
            self.getDimension("inner_radius") + self.getDimension("radius_differential"),
        )
        self.setDimension(
            "outer_axial",
            self.getDimension("inner_axial") + self.getDimension("height"),
        )
        self.setDimension(
            "outer_theta",
            self.getDimension("inner_theta") + self.getDimension("azimuthal_differential"),
        )

    def getComponentArea(self, refVolume=None, refHeight=None, cold=False, Tc=None):
        if Tc is not None:
            raise NotImplementedError(f"Cannot calculate area at specified temperature: {Tc}")
        self.updateDims()
        return RadialSegment.getComponentArea(self, refVolume=None, refHeight=None, cold=False)

    def getComponentVolume(self):
        self.updateDims()
        return RadialSegment.getComponentVolume(self)
