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
from armi.reactor.parameters.parameterDefinitions import isNumpyArray, isNumpyF32Array
from armi.utils import units


def getComponentParameterDefinitions():
    """Return the base Component parameters."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("volume", units=f"{units.CM}^3", description="Volume of this object.")

        pb.defParam(
            "area",
            units=f"{units.CM}^2",
            description="Cross sectional area of this component.",
        )

        pb.defParam(
            "mult",
            units=units.UNITLESS,
            description="The multiplicity of this component, i.e. how many of them there are.",
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
            setter=isNumpyArray("numberDensities"),
            units=f"#/(bn*{units.CM})",
            description="Number densities of each nuclide.",
        )

        pb.defParam(
            "nuclides",
            setter=isNumpyArray("nuclides"),
            units=units.UNITLESS,
            description="Nuclide names corresponding to numberDensities array.",
        )

        pb.defParam(
            "detailedNDens",
            setter=isNumpyArray("detailedNDens"),
            units=f"atoms/(bn*{units.CM})",
            description=(
                "High-fidelity number density vector with up to thousands of nuclides. "
                "Used in high-fi depletion runs where low-fi depletion may also be occurring. "
                "This param keeps the hi-fi and low-fi depletion values from interfering."
            ),
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "pinNDens",
            setter=isNumpyF32Array("pinNDens"),
            units=f"atoms/(bn*{units.CM})",
            description="Pin-wise number densities of each nuclide.",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            categories=["depletion", parameters.Category.pinQuantities],
            default=None,
        )

        pb.defParam(
            "percentBu",
            units=f"{units.PERCENT_FIMA}",
            description="Burnup as a percentage of initial (heavy) metal atoms.",
            default=0.0,
        )

        pb.defParam(
            "pinPercentBu",
            setter=isNumpyArray("pinPercentBu"),
            units=units.PERCENT_FIMA,
            description="Pin-wise burnup as a percentage of initial (heavy) metal atoms.",
            default=None,
        )

        pb.defParam(
            "buRate",
            units=f"{units.PERCENT_FIMA}/{units.DAYS}",
            # This is very related to power, but normalized to %FIMA.
            description=(
                "Current rate of burnup accumulation. Useful for estimating times when burnup limits may be exceeded."
            ),
        )

        pb.defParam(
            "massHmBOL",
            units=units.GRAMS,
            description="Mass of heavy metal at BOL",
            default=None,
        )

        pb.defParam(
            "customIsotopicsName",
            units=units.UNITLESS,
            description="Label of isotopics applied to this component.",
        )

        pb.defParam(
            "modArea",
            units=units.UNITLESS,
            description="A (component, operation) tuple used to add/subtract area (in "
            "cm^2) from another components area. See c.getArea()",
        )

        pb.defParam(
            "zrFrac",
            units=units.UNITLESS,
            description="Original Zr frac of this, used for material properties.",
        )

        pb.defParam(
            "pinNum",
            units=units.UNITLESS,
            description="Pin number of this component in some mesh. Starts at 1.",
            default=None,
        )

        def _assignTDFrac(self, val):
            if val > 1 or val < 0:
                raise ValueError(f"Theoretical density fraction must be in range [0,1], got {val}")
            self._p_theoreticalDensityFrac = val

        pb.defParam(
            "theoreticalDensityFrac",
            description=(
                "Fractional value between zero and one, inclusive, for the theoretical density "
                "of the material stored on this component."
            ),
            units=units.UNITLESS,
            default=1,
            setter=_assignTDFrac,
        )

        pb.defParam(
            "molesHmBOL",
            units=units.MOLES,
            default=0.0,
            description="Total number of moles of heavy metal at BOL.",
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
        pb.defParam("holeOD", units=units.CM, description="Diameter of interior hole(s)")

        pb.defParam("nHoles", units=units.UNITLESS, description="Number of interior holes")

        pb.defParam(
            "holeRadFromCenter",
            units=units.CM,
            description="Distance from the center of the hexagon to the center of the holes assuming the hole centers "
            "all lie on a circle.",
            default=None,
        )

    return pDefs


def getHexHoledCircleParameterDefinitions():
    """Return parameters for HexHoledCircle."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("holeOP", units=units.CM, description="Pitch of interior hole")

    return pDefs


def getFilletedHexagonParameterDefinitions():
    """Return parameters for FilletedHexagon."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("iR", units=units.CM, description="Radius of curvature of the inner corners")
        pb.defParam("oR", units=units.CM, description="Radius of curvature of the outer corners")

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
        pb.defParam(
            "lengthInner",
            units=units.CM,
            default=0.0,
            description="Inner length dimension (if the cube is hollow).",
        )

        pb.defParam("lengthOuter", units=units.CM, description="Outermost length dimension")

        pb.defParam(
            "widthInner",
            units=units.CM,
            default=0.0,
            description="Inner width dimension (if the cube is hollow).",
        )

        pb.defParam("widthOuter", units=units.CM, description="Outermost width dimension")

        pb.defParam(
            "heightInner",
            units=units.CM,
            default=0.0,
            description="Inner height dimension (if the cube is hollow).",
        )

        pb.defParam("heightOuter", units=units.CM, description="Outermost height dimension")

    return pDefs


def getTriangleParameterDefinitions():
    """Return parameters for Triangle."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("base", units=units.CM, description="Length of the base of the triangle")

        pb.defParam("height", units=units.CM, description="Height of the triangle")

    return pDefs


def getUnshapedParameterDefinitions():
    """Return parameters for UnshapedComponent."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam("op", units=units.CM, description="Outer pitch")

        pb.defParam(
            "userDefinedVolume",
            units=f"{units.CM}^3",
            description="Volume of this object.",
        )

    return pDefs


def getRadialSegmentParameterDefinitions():
    """Return parameters for RadialSegment."""
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(location=ParamLocation.AVERAGE, saveToDB=True) as pb:
        pb.defParam(
            "inner_theta",
            units=units.RADIANS,
            description="Starting axial position, in radians.",
        )

        pb.defParam(
            "outer_theta",
            units=units.RADIANS,
            description="Ending axial position, in radians.",
        )

        pb.defParam(
            "inner_radius",
            units=units.CM,
            description="Starting radial position; this can be zero.",
        )

        pb.defParam("outer_radius", units=units.CM, description="Ending radial position.")

        pb.defParam("height", units=units.CM, description="Height of the 3D radial segment.")

        pb.defParam(
            "azimuthal_differential",
            units=units.RADIANS,
            description="Perturbation in the azimuthal dimension (see inner_theta and outer_theta).",
        )

        pb.defParam(
            "radius_differential",
            units=units.UNITLESS,
            description="Perturbation in the radial dimension (see inner_radius and outer_radius).",
        )

        pb.defParam(
            "inner_axial",
            units=units.UNITLESS,
            description="Perturbation in the axial dimension (picture outer_axial = inner_axial + height).",
        )

        pb.defParam(
            "outer_axial",
            units=units.UNITLESS,
            description="Perturbation result in the axial dimension (picture outer_axial = inner_axial + height).",
        )

    return pDefs
