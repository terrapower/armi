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

"""Component parameter definitions."""
from armi.reactor import parameters
from armi.reactor.parameters import ParamLocation
from armi.utils import units


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
            units=units.UNITLESS,
            description="The multiplicity of this component, i.e. how many of them there are. ",
            default=1,
        )

        pb.defParam(
            "mergeWith",
            units=units.UNITLESS,
            description="Label of other component to merge with",
        )

        pb.defParam(
            "type",
            units=units.UNITLESS,
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
            "buRate",
            units="%FIMA/day",
            # This is very related to power, but normalized to %FIMA.
            description=(
                "Current rate of burnup accumulation. Useful for estimating times when "
                "burnup limits may be exceeded."
            ),
        )

        pb.defParam(
            "massHmBOL",
            units=units.GRAMS,
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
            units=units.UNITLESS,
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
            units=units.UNITLESS,
            description="Original Zr frac of this, used for material properties. ",
        )

        pb.defParam(
            "pinNum",
            units=units.UNITLESS,
            description="Pin number of this component in some mesh. Starts at 1.",
            default=None,
        )
    return pDefs


def getCircleParameterDefinitions():
    """Return parameters for Circle."""
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("od", units=units.CM, description="Outer diameter")

        pb.defParam("id", units=units.CM, description="Inner diameter", default=0.0)

        pb.defParam("op", units=units.CM, description="Outer pitch")

    return pDefs


def getHexagonParameterDefinitions():
    """Return parameters for Hexagon."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("ip", units=units.CM, description="Inner pitch", default=0.0)

        pb.defParam("op", units=units.CM, description="Outer pitch")

    return pDefs


def getHoledHexagonParameterDefinitions():
    """Return parameters for HoledHexagon."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam(
            "holeOD", units=units.CM, description="Diameter of interior hole(s)"
        )

        pb.defParam(
            "nHoles", units=units.UNITLESS, description="Number of interior holes"
        )

    return pDefs


def getHexHoledCircleParameterDefinitions():
    """Return parameters for HexHoledCircle."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("holeOP", units=units.CM, description="Pitch of interior hole")

    return pDefs


def getHoledRectangleParameterDefinitions():
    """Return parameters for HoledRectangle."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("holeOD", units=units.CM, description="Diameter of interior hole")

    return pDefs


def getHelixParameterDefinitions():
    """Return parameters for Helix."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("od", units=units.CM, description="Outer diameter")

        pb.defParam("id", units=units.CM, description="Inner diameter", default=0.0)

        pb.defParam("op", units=units.CM, description="Outer pitch")

        pb.defParam(
            "axialPitch",
            units=units.CM,
            description="Axial pitch of helix in helical shapes.",
        )

        pb.defParam("helixDiameter", units=units.CM, description="Diameter of helix")

    return pDefs


def getRectangleParameterDefinitions():
    """Return parameters for Rectangle."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("lengthInner", units=units.CM, description="Inner length")

        pb.defParam("lengthOuter", units=units.CM, description="Outer length")

        pb.defParam("widthInner", units=units.CM, description="Inner width")

        pb.defParam("widthOuter", units=units.CM, description="Outer width")

    return pDefs


def getCubeParameterDefinitions():
    """Return parameters for Cube."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("lengthInner", units=units.CM, description="Inner length")

        pb.defParam("lengthOuter", units=units.CM, description="Outer length")

        pb.defParam("widthInner", units=units.CM, description="Inner width")

        pb.defParam("widthOuter", units=units.CM, description="Outer width")

        pb.defParam("heightOuter", units=units.UNITLESS, description="?")

        pb.defParam("heightInner", units=units.UNITLESS, description="?")

    return pDefs


def getTriangleParameterDefinitions():
    """Return parameters for Triangle."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("base", units=units.UNITLESS, description="?")

        pb.defParam("height", units=units.UNITLESS, description="?")

    return pDefs


def getUnshapedParameterDefinitions():
    """Return parameters for UnshapedComponent."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("op", units=units.CM, description="Outer pitch")

        pb.defParam(
            "userDefinedVolume", units="cm^3", description="Volume of this object."
        )

    return pDefs


def getRadialSegmentParameterDefinitions():
    """Return parameters for RadialSegment."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("inner_theta", units=units.UNITLESS, description="?")

        pb.defParam("outer_theta", units=units.UNITLESS, description="?")

        pb.defParam("inner_radius", units=units.UNITLESS, description="?")

        pb.defParam("outer_radius", units=units.UNITLESS, description="?")

        pb.defParam("height", units=units.UNITLESS, description="?")

        pb.defParam("azimuthal_differential", units=units.UNITLESS, description="?")

        pb.defParam("radius_differential", units=units.UNITLESS, description="?")

        pb.defParam("inner_axial", units=units.UNITLESS, description="?")

        pb.defParam("outer_axial", units=units.UNITLESS, description="?")

    return pDefs


def getTorusParameterDefinitions():
    """Return parameters for Torus."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("inner_theta", units=units.UNITLESS, description="?")

        pb.defParam("outer_theta", units=units.UNITLESS, description="?")

        pb.defParam("inner_radius", units=units.UNITLESS, description="?")

        pb.defParam("outer_radius", units=units.UNITLESS, description="?")

        pb.defParam("height", units=units.UNITLESS, description="?")

        pb.defParam("azimuthal_differential", units=units.UNITLESS, description="?")

        pb.defParam("radius_differential", units=units.UNITLESS, description="?")

        pb.defParam("inner_axial", units=units.UNITLESS, description="?")

        pb.defParam("outer_axial", units=units.UNITLESS, description="?")

        pb.defParam("inner_minor_radius", units=units.UNITLESS, description="?")

        pb.defParam("outer_minor_radius", units=units.UNITLESS, description="?")

        pb.defParam("major_radius", units=units.UNITLESS, description="?")

        pb.defParam("inner_phi", units=units.UNITLESS, description="?")

        pb.defParam("outer_phi", units=units.UNITLESS, description="?")

        pb.defParam("reference_volume", units=units.UNITLESS, description="?")

    return pDefs
