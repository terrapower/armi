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
Component parameter definitions.
"""

from armi.reactor import parameters
from armi.reactor.parameters import ParamLocation
from armi.utils import units
from armi.reactor.flags import Flags  # non-standard import to avoid name conflict below


def getComponentParameterDefinitions():
    """Return the base Component parameters."""

    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("volume", units="cm^3", description="Volume of this object.")

        pb.defParam(
            "area", units="cm^2", description="Cross sectional area of this component."
        )

        pb.defParam(
            "mult",
            units=None,
            description="The multiplicity of this component, i.e. how many of them there are. ",
            default=1,
        )

        pb.defParam(
            "mergeWith",
            units=None,
            description="Label of other component to merge with",
        )

        pb.defParam(
            "type",
            units="",
            description="The name of this object as input on the blueprints",
        )

        pb.defParam(
            "temperatureInC",
            units=units.DEGC,
            description="Component temperature in {}".format(units.DEGC),
        )

        pb.defParam(
            "numberDensities",
            units="#/bn-cm",
            description="Number densities of each nuclide.",
        )

        pb.defParam(
            "percentBu",
            units="%FIMA",
            description="Burnup as a percentage of initial (heavy) metal atoms.",
            default=0.0,
        )

        pb.defParam(
            "massHmBOL",
            units="grams",
            description="Mass of heavy metal at BOL",
            default=None,
        )

        pb.defParam(
            "burnupMWdPerKg",
            units="MWd/kg",
            description="Burnup in MWd/Kg of heavy metal",
            default=0.0,
            categories=["cumulative"],
        )

        pb.defParam(
            "customIsotopicsName",
            units=None,
            description="Label of isotopics applied to this component. ",
        )

        pb.defParam(
            "modArea",
            units="Tuple referencing another component and operation",
            description="A (component, operation) tuple used to add/subtract area (in "
            "cm^2) from another components area. See c.getArea()",
        )

        pb.defParam(
            "zrFrac",
            units=None,
            description="Original Zr frac of this, used for material properties. ",
        )

        pb.defParam(
            "pinNum",
            units="N/A",
            description="Pin number of this component in some mesh. Starts at 1.",
            default=None,
        )
    return pDefs


def getCircleParameterDefinitions():
    """Return parameters for Circle."""

    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("od", units="cm", description="Outer diameter")

        pb.defParam("id", units="cm", description="Inner diameter", default=0.0)

        pb.defParam("op", units="cm", description="Outer pitch")

    return pDefs


def getHexagonParameterDefinitions():
    """Return parameters for Hexagon."""

    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("ip", units="cm", description="Inner pitch", default=0.0)

        pb.defParam("op", units="cm", description="Outer pitch")

    return pDefs


def getShieldBlockParameterDefinitions():
    """Return parameters for ShieldBlock."""

    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("holeOD", units="?", description="?")

        pb.defParam("nHoles", units="?", description="?")

    return pDefs


def getHelixParameterDefinitions():
    """Return parameters for Helix."""

    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("od", units="cm", description="Outer diameter")

        pb.defParam("id", units="cm", description="Inner diameter", default=0.0)

        pb.defParam("op", units="cm", description="Outer pitch")

        pb.defParam(
            "axialPitch",
            units="cm",
            description="Axial pitch of helix in helical shapes.",
        )

        pb.defParam("helixDiameter", units="cm", description="Diameter of helix")

    return pDefs


def getRectangleParameterDefinitions():
    """Return parameters for Rectangle."""

    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("lengthInner", units="cm", description="Inner length")

        pb.defParam("lengthOuter", units="cm", description="Outer length")

        pb.defParam("widthInner", units="cm", description="Inner width")

        pb.defParam("widthOuter", units="cm", description="Outer width")

    return pDefs


def getCubeParameterDefinitions():
    """Return parameters for Cube."""

    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("lengthInner", units="cm", description="Inner length")

        pb.defParam("lengthOuter", units="cm", description="Outer length")

        pb.defParam("widthInner", units="cm", description="Inner width")

        pb.defParam("widthOuter", units="cm", description="Outer width")

        pb.defParam("heightOuter", units="?", description="?")

        pb.defParam("heightInner", units="?", description="?")

    return pDefs


def getTriangleParameterDefinitions():
    """Return parameters for Triangle."""

    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("base", units="?", description="?")

        pb.defParam("height", units="?", description="?")

    return pDefs


def getUnshapedParameterDefinitions():
    """Return parameters for UnshapedComponent."""

    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("op", units="cm", description="Outer pitch")

        pb.defParam(
            "userDefinedVolume", units="cm^3", description="Volume of this object."
        )

    return pDefs


def getRadialSegmentParameterDefinitions():
    """Return parameters for RadialSegment."""

    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("inner_theta", units="?", description="?")

        pb.defParam("outer_theta", units="?", description="?")

        pb.defParam("inner_radius", units="?", description="?")

        pb.defParam("outer_radius", units="?", description="?")

        pb.defParam("height", units="?", description="?")

        pb.defParam("azimuthal_differential", units="?", description="?")

        pb.defParam("radius_differential", units="?", description="?")

        pb.defParam("inner_axial", units="?", description="?")

        pb.defParam("outer_axial", units="?", description="?")

    return pDefs


def getTorusParameterDefinitions():
    """Return parameters for Torus."""

    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("inner_theta", units="?", description="?")

        pb.defParam("outer_theta", units="?", description="?")

        pb.defParam("inner_radius", units="?", description="?")

        pb.defParam("outer_radius", units="?", description="?")

        pb.defParam("height", units="?", description="?")

        pb.defParam("azimuthal_differential", units="?", description="?")

        pb.defParam("radius_differential", units="?", description="?")

        pb.defParam("inner_axial", units="?", description="?")

        pb.defParam("outer_axial", units="?", description="?")

        pb.defParam("inner_minor_radius", units="?", description="?")

        pb.defParam("outer_minor_radius", units="?", description="?")

        pb.defParam("major_radius", units="?", description="?")

        pb.defParam("inner_phi", units="?", description="?")

        pb.defParam("outer_phi", units="?", description="?")

        pb.defParam("reference_volume", units="?", description="?")

    return pDefs
