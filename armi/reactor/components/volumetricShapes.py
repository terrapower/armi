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

"""3-dimensional shapes."""

import math

from armi.reactor.components import componentParameters
from armi.reactor.components import ShapedComponent


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
        """Abstract bounding circle method that should be overwritten by each shape subclass."""
        return self.getDimension("od")

    def getComponentArea(self, cold=False):
        """Compute an average area over the height"""
        from armi.reactor.blocks import Block  # avoid circular import

        block = self.getAncestor(lambda c: isinstance(c, Block))
        return self.getComponentVolume(cold) / block.getHeight()
        # raise NotImplementedError("Cannot compute area of a sphere component.")

    def getComponentVolume(self, cold=False):
        """Computes the volume of the sphere in cm^3."""
        od = self.getDimension("od", cold=cold)
        iD = self.getDimension("id", cold=cold)
        mult = self.getDimension("mult")
        vol = mult * 4.0 / 3.0 * math.pi * ((od / 2.0) ** 3 - (iD / 2.0) ** 3)
        return vol


class Cube(ShapedComponent):
    """
    More correctly, a rectangular cuboid
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
            heightOuter=heightOuter,
            heightInner=heightInner,
            mult=mult,
            modArea=modArea,
        )

    def getComponentArea(self, cold=False):
        raise NotImplementedError("Cannot compute area of a cube component.")

    def getComponentVolume(self):
        r"""
        Computes the volume of the cube in cm^3.
        """
        lengthO = self.getDimension("lengthOuter")
        widthO = self.getDimension("widthOuter")
        heightO = self.getDimension("heightOuter")
        lengthI = self.getDimension("lengthInner")
        widthI = self.getDimension("widthInner")
        heightI = self.getDimension("heightInner")
        mult = self.getDimension("mult")
        vol = mult * (lengthO * widthO * heightO - lengthI * widthI * heightI)
        return vol


class Torus(ShapedComponent):
    r"""
    A torus.

    Theta defines the extent the radial segment is rotated around the Z-axis
    phi defines the extent around the major radius (i.e. a half torus is from 0 to pi)

    Notes
    -----
    The dimensions are:

    * p0 - inner minor radius
    * p1 - outer minor radius
    * p2 - major radius
    * p3 - multiplier
    * p4 - inner theta (optional) 0 (default)
    * p5 - outer theta (optional) 2pi (default)
    * p6 - inner phi (optional) 0 (default)
    * p7 - outer phi (optional) 2pi (default)
    * p8 - height (optional) <set as outer minor radius > (default)
    * p9 - reference volume (optional)

    Image::

        Z
        |
        |
        |
        |            - ^ -
        |          /   | minor radius
        |-----------------------> major radius, R
        |          \      /
        |           - - -
        |

        Y
        ^                      -
        |                 -
        |            -    \
        |       -  \       \
        |  theta   |       |
       ZX-----------------------> major radius, X
        |
        |
        |
    """

    is3D = True

    THERMAL_EXPANSION_DIMS = {}

    pDefs = componentParameters.getTorusParameterDefinitions()

    def __init__(
        self,
        name,
        material,
        Tinput,
        Thot,
        inner_minor_radius=None,
        outer_minor_radius=None,
        major_radius=None,
        mult=1,
        inner_theta=0.0,
        outer_theta=math.pi * 2,
        inner_phi=0,
        outer_phi=math.pi * 2,
        height=None,
        reference_volume=None,
        inner_radius=None,
        outer_radius=None,
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
        height = 2 * outer_minor_radius if height is None else height
        inner_radius = (
            major_radius - outer_minor_radius if inner_radius is None else inner_radius
        )
        outer_radius = (
            major_radius + outer_minor_radius if outer_radius is None else outer_radius
        )
        self._linkAndStoreDimensions(
            components,
            inner_minor_radius=inner_minor_radius,
            outer_minor_radius=outer_minor_radius,
            major_radius=major_radius,
            mult=mult,
            inner_theta=inner_theta,
            outer_theta=outer_theta,
            inner_phi=inner_phi,
            outer_phi=outer_phi,
            height=height,
            reference_volume=reference_volume,
            inner_radius=inner_radius,
            outer_radius=outer_radius,
        )

    def getComponentArea(
        self, refVolume=None, refArea=None, refHeight=None, cold=False
    ):
        r"""Computes the volume averaged area of the torus component.

        Parameters
        ----------
        RefVolume - float
            This is the volume to use when normalizing area
        RefArea - float
            This is the area to use when normalizing area
        RefHeight - floats
            This is the height to use to estimate volume if a reference volume
            is not given

        Notes
        -----
        Since area fractions are being used as a proxy for volume fractions, this method returns the reference
        area normalized to the volume ratio of the torus within reference volume
        """

        refPhi = self.getDimension("reference_phi", cold=cold)
        height = self.getDimension("height", cold=cold)
        if refArea is None:
            # assume the footprint of the assembly is the footprint of a half torus
            if "reference_phi" in self.p and "height" in self.p:
                # reference volume and reference height defined in the component
                refArea = refPhi / height
            else:
                majorRad = self.getDimension("major_radius", cold=cold)
                outerMinorRad = self.getDimension("outer_minor_radius", cold=cold)
                outerTh = self.getDimension("outer_theta")
                innerTh = self.getDimension("inner_theta")
                refArea = (
                    math.pi
                    * (
                        (majorRad + outerMinorRad) ** 2.0
                        - (majorRad - outerMinorRad) ** 2.0
                    )
                    * (outerTh - innerTh)
                    / (2 * math.pi)
                )

        if refVolume is None:
            if refPhi:
                refVolume = refPhi
            elif refHeight is None:
                refVolume = refArea * height
            else:
                refVolume = refArea * refHeight

        return self.getVolume() * refArea / refVolume

    def getComponentVolume(self):
        """Computes the volume of the torus in cm^3.

        Notes
        -----
        The exact solution is the solution to integrating the volume:
            dV ~ (dr)*((R+cos(Ph)*r)*dTh)*(r*dPh)
        Solution from WolframAlpha:
            integrate (m*(R + cos(phi)*r)*r) dr dphi dtheta, theta=t1...t2, r=r1...r2, phi=p1...p2
        """
        r1 = self.getDimension("inner_minor_radius")
        r2 = self.getDimension("outer_minor_radius")
        R = self.getDimension("major_radius")
        mult = self.getDimension("mult")
        t1 = self.getDimension("inner_theta")
        t2 = self.getDimension("outer_theta")
        p1 = self.getDimension("inner_phi")
        p2 = self.getDimension("outer_phi")
        dTh = t2 - t1
        dPhi = p1 - p2
        dRad = r1 - r2
        totRad = r1 + r2
        dAngle = math.sin(p1) - math.sin(p2)
        vol = (
            mult
            * dTh
            * (3 * R * dPhi * dRad * totRad + 2 * (r1 ** 3 - r2 ** 3) * dAngle)
            / 6.0
        )
        return vol


class RadialSegment(ShapedComponent):

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
            inner_radius=inner_radius,
            outer_radius=outer_radius,
            height=height,
            mult=mult,
            inner_theta=inner_theta,
            outer_theta=outer_theta,
        )

    def getComponentArea(self, refVolume=None, refHeight=None, cold=False):
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
                        (
                            self.getDimension("outer_theta", cold=cold)
                            - self.getDimension("inner_theta", cold=cold)
                        )
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
        radialArea = math.pi * (outerRad ** 2 - innerRad ** 2)
        aziFraction = (outerTheta - innerTheta) / (math.pi * 2.0)
        vol = mult * radialArea * aziFraction * height
        return vol

    def getBoundingCircleOuterDiameter(self, Tc=None, cold=False):
        return self.getDimension("outer_radius", Tc, cold)


class DifferentialRadialSegment(RadialSegment):
    """
    This component class represents a volume element with thicknesses in the
    azimuthal, radial and axial directions. Furthermore it has dependent
    dimensions: (outer theta, outer radius, outer axial) that can be updated
    depending on the 'differential' in the corresponding directions

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
            self.getDimension("inner_radius")
            + self.getDimension("radius_differential"),
        )
        self.setDimension(
            "outer_axial",
            self.getDimension("inner_axial") + self.getDimension("height"),
        )
        self.setDimension(
            "outer_theta",
            self.getDimension("inner_theta")
            + self.getDimension("azimuthal_differential"),
        )

    def getComponentArea(self, refVolume=None, refHeight=None, cold=False):
        self.updateDims()
        return RadialSegment.getComponentArea(
            self, refVolume=None, refHeight=None, cold=False
        )

    def getComponentVolume(self):
        self.updateDims()
        return RadialSegment.getComponentVolume(self)
