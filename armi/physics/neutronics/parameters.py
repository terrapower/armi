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
Parameter definitions for the Neutronics Plugin.

We hope neutronics plugins that compute flux will use ``mgFlux``, etc., which will enable modular
construction of apps.
"""

from armi.reactor import parameters
from armi.reactor.blocks import Block
from armi.reactor.parameters import ParamLocation
from armi.reactor.parameters.parameterDefinitions import isNumpyArray
from armi.reactor.reactors import Core
from armi.utils import units


def getNeutronicsParameterDefinitions():
    """Return ParameterDefinitionCollections for each appropriate ArmiObject."""
    return {Block: _getNeutronicsBlockParams(), Core: _getNeutronicsCoreParams()}


def _getNeutronicsBlockParams():
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder() as pb:
        pb.defParam(
            "axMesh",
            units=units.UNITLESS,
            description="number of neutronics axial mesh points in this block",
            default=None,
            categories=[parameters.Category.retainOnReplacement],
        )

        pb.defParam(
            "mgFlux",
            setter=isNumpyArray("mgFlux"),
            units=f"n*{units.CM}/{units.SECONDS}",
            description="multigroup volume-integrated flux",
            location=ParamLocation.VOLUME_INTEGRATED,
            saveToDB=True,
            categories=[
                parameters.Category.fluxQuantities,
                parameters.Category.multiGroupQuantities,
            ],
            default=None,
        )

        pb.defParam(
            "adjMgFlux",
            units=f"n*{units.CM}/{units.SECONDS}",
            description="multigroup adjoint neutron flux",
            location=ParamLocation.VOLUME_INTEGRATED,
            saveToDB=True,
            categories=[
                parameters.Category.fluxQuantities,
                parameters.Category.multiGroupQuantities,
            ],
            default=None,
        )

        pb.defParam(
            "lastMgFlux",
            units=f"n*{units.CM}/{units.SECONDS}",
            description="multigroup volume-integrated flux used for averaging the latest and previous depletion step",
            location=ParamLocation.VOLUME_INTEGRATED,
            saveToDB=False,
            categories=[
                parameters.Category.fluxQuantities,
                parameters.Category.multiGroupQuantities,
            ],
            default=None,
        )

        pb.defParam(
            "mgFluxGamma",
            units=f"#*{units.CM}/{units.SECONDS}",
            description="multigroup gamma flux",
            location=ParamLocation.VOLUME_INTEGRATED,
            saveToDB=True,
            categories=[
                parameters.Category.fluxQuantities,
                parameters.Category.multiGroupQuantities,
                parameters.Category.gamma,
            ],
            default=None,
        )

        pb.defParam(
            "mgNeutronVelocity",
            units=f"{units.CM}/{units.SECONDS}",
            description="multigroup neutron velocity",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            categories=[parameters.Category.multiGroupQuantities],
            default=None,
        )

        pb.defParam(
            "extSrc",
            units=f"#/{units.CM}^3/{units.SECONDS}",
            description="multigroup external source",
            location=ParamLocation.AVERAGE,
            saveToDB=False,
            categories=[parameters.Category.multiGroupQuantities],
            default=None,
        )

        pb.defParam(
            "mgGammaSrc",
            units=f"#/{units.CM}^3/{units.SECONDS}",
            description="multigroup gamma source",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            categories=[
                parameters.Category.multiGroupQuantities,
                parameters.Category.gamma,
            ],
            default=None,
        )

        pb.defParam(
            "gammaSrc",
            units=f"#/{units.CM}^3/{units.SECONDS}",
            description="gamma source",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            categories=[parameters.Category.gamma],
            default=0.0,
        )

        # Not anointing the pin fluxes as a MG quantity, since it has an extra dimension, which
        # could lead to issues, depending on how the multiGroupQuantities category gets used
        pb.defParam(
            "pinMgFluxes",
            units=f"n/{units.CM}^2/{units.SECONDS}",
            description="""
            The block-level pin multigroup fluxes. pinMgFluxes[i, g] represents the flux in group g
            for pin i. Flux units are the standard n/cm^2/s. The "ARMI pin ordering" is used, which
            is counter-clockwise from 3 o'clock.
            """,
            categories=[parameters.Category.pinQuantities],
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "pinMgFluxesAdj",
            units=units.UNITLESS,
            description="should be a blank 3-D array, but re-defined later (nPins x ng x nAxialSegments)",
            categories=[parameters.Category.pinQuantities],
            saveToDB=False,
            default=None,
        )

        pb.defParam(
            "pinMgFluxesGamma",
            units=f"#/{units.CM}^2/{units.SECONDS}",
            description="should be a blank 3-D array, but re-defined later (nPins x ng x nAxialSegments)",
            categories=[parameters.Category.pinQuantities, parameters.Category.gamma],
            saveToDB=False,
            default=None,
        )

        pb.defParam(
            "chi",
            units=units.UNITLESS,
            description="Energy distribution of fission neutrons",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "linPow",
            units=f"{units.WATTS}/{units.METERS}",
            description=(
                "Pin-averaged linear heat rate, which is calculated by evaluating the block power "
                "and dividing by the number of pins. If gamma transport is enabled, then this "
                "represents the combined neutron and gamma heating. If gamma transport is disabled "
                "then this represents the energy generation in the pin, where gammas are assumed to "
                "deposit their energy locally. Note that this value does not implicitly account "
                "for axial and radial peaking factors within the block. Use `linPowByPin` for "
                "obtaining the pin linear heat rate with peaking factors included."
            ),
            location=ParamLocation.AVERAGE,
            default=0.0,
            categories=[
                parameters.Category.detailedAxialExpansion,
                parameters.Category.neutronics,
            ],
        )

        pb.defParam(
            "linPowByPin",
            setter=isNumpyArray("linPowByPin"),
            units=f"{units.WATTS}/{units.CM}",
            description=(
                "Pin linear linear heat rate, which is calculated through flux reconstruction and "
                "accounts for axial and radial peaking factors. This differs from the `linPow` "
                "parameter, which assumes no axial and radial peaking in the block as this "
                "information is unavailable without detailed flux reconstruction. The same "
                "application of neutron and gamma heating results applies."
            ),
            location=ParamLocation.CHILDREN,
            categories=[parameters.Category.pinQuantities],
            default=None,
        )

        # gamma category because linPowByPin is only split by neutron/gamma when gamma is activated
        pb.defParam(
            "linPowByPinNeutron",
            setter=isNumpyArray("linPowByPinNeutron"),
            units=f"{units.WATTS}/{units.CM}",
            description="Pin linear neutron heat rate. This is the neutron heating component of `linPowByPin`",
            location=ParamLocation.CHILDREN,
            categories=[parameters.Category.pinQuantities, parameters.Category.gamma],
            default=None,
        )

        pb.defParam(
            "linPowByPinGamma",
            setter=isNumpyArray("linPowByPinGamma"),
            units=f"{units.WATTS}/{units.CM}",
            description="Pin linear gamma heat rate. This is the gamma heating component of `linPowByPin`",
            location=ParamLocation.CHILDREN,
            categories=[parameters.Category.pinQuantities, parameters.Category.gamma],
            default=None,
        )

        pb.defParam(
            "reactionRates",
            units=f"#/{units.SECONDS}",
            description='List of reaction rates in specified by setting "reactionsToDB"',
            location=ParamLocation.VOLUME_INTEGRATED,
            categories=[parameters.Category.fluxQuantities],
            default=None,
        )

    with pDefs.createBuilder(
        saveToDB=True,
        default=None,
        location=ParamLocation.EDGES,
        categories=[parameters.Category.detailedAxialExpansion, "depletion"],
    ) as pb:
        pb.defParam(
            "pointsEdgeFastFluxFr",
            units=units.UNITLESS,
            description="Fraction of flux above 100keV at edges of the block",
        )

        pb.defParam(
            "pointsEdgeDpa",
            setter=isNumpyArray("pointsEdgeDpa"),
            units=units.DPA,
            description="displacements per atom at edges of the block",
            location=ParamLocation.EDGES | ParamLocation.BOTTOM,
            categories=["cumulative", "detailedAxialExpansion", "depletion"],
        )

        pb.defParam(
            "pointsEdgeDpaRate",
            setter=isNumpyArray("pointsEdgeDpaRate"),
            units=f"{units.DPA}/{units.SECONDS}",
            description="Current time derivative of the displacement per atoms at edges of the block",
            location=ParamLocation.EDGES | ParamLocation.BOTTOM,
        )

    with pDefs.createBuilder(
        saveToDB=True,
        default=None,
        location=ParamLocation.CORNERS,
        categories=[
            parameters.Category.detailedAxialExpansion,
            parameters.Category.depletion,
        ],
    ) as pb:
        pb.defParam(
            "cornerFastFlux",
            units=f"n/{units.CM}^2/{units.SECONDS}",
            description="Neutron flux above 100keV at hexagon block corners",
        )

        pb.defParam(
            "pointsCornerFastFluxFr",
            units=units.UNITLESS,
            description="Fraction of flux above 100keV at corners of the block",
        )

        pb.defParam(
            "pointsCornerDpa",
            setter=isNumpyArray("pointsCornerDpa"),
            units=units.DPA,
            description="displacements per atom at corners of the block",
            location=ParamLocation.CORNERS | ParamLocation.BOTTOM,
            categories=["cumulative", "detailedAxialExpansion", "depletion"],
        )

        pb.defParam(
            "pointsCornerDpaRate",
            setter=isNumpyArray("pointsCornerDpaRate"),
            units=f"{units.DPA}/{units.SECONDS}",
            description="Current time derivative of the displacement per atoms at corners of the block",
            location=ParamLocation.CORNERS | ParamLocation.BOTTOM,
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        categories=[parameters.Category.detailedAxialExpansion],
    ) as pb:
        # Neutronics reaction rate params that are not re-derived in mesh conversion
        pb.defParam(
            "rateBalance",
            units=f"1/{units.CM}^3/{units.SECONDS}",
            description="Numerical balance between particle production and destruction (should be small)",
        )

        pb.defParam(
            "rateProdNet",
            units=f"1/{units.CM}^3/{units.SECONDS}",
            description="The total neutron production including (n,2n) source and fission source.",
        )

        pb.defParam(
            "capturePowerFrac",
            units=units.UNITLESS,
            description="Fraction of the power produced through capture in a block.",
            saveToDB="True",
        )

        pb.defParam(
            "fluence",
            units=f"#/{units.CM}^2",
            description="Fluence",
            categories=["cumulative"],
        )

        pb.defParam(
            "flux",
            units=f"n/{units.CM}^2/{units.SECONDS}",
            description="neutron flux",
            categories=[
                parameters.Category.retainOnReplacement,
                parameters.Category.fluxQuantities,
            ],
        )

        pb.defParam("fluxAdj", units=units.UNITLESS, description="Adjoint flux")
        pb.defParam(
            "fluxAdjPeak",
            units=units.UNITLESS,
            description="Adjoint flux",
            location=ParamLocation.MAX,
        )

        pb.defParam(
            "pdens",
            units=f"{units.WATTS}/{units.CM}^3",
            description="Average volumetric power density",
            categories=[parameters.Category.neutronics],
        )

        pb.defParam(
            "pdensDecay",
            units=f"{units.WATTS}/{units.CM}^3",
            description="Decay power density from decaying radionuclides",
        )

        pb.defParam(
            "arealPd",
            units=f"{units.MW}/{units.METERS}^2",
            description="Power divided by XY area",
        )

        pb.defParam(
            "fisDens",
            units=f"fissions/{units.CM}^3/{units.SECONDS}",
            description="Fission density in a pin (scaled up from homogeneous)",
        )

        pb.defParam(
            "fisDensHom",
            units=f"1/{units.CM}^3/{units.SECONDS}",
            description="Homogenized fissile density",
        )

        pb.defParam(
            "fluxGamma",
            units=f"#/{units.CM}^2/{units.SECONDS}",
            description="Gamma scalar flux",
            categories=[
                parameters.Category.retainOnReplacement,
                parameters.Category.fluxQuantities,
            ],
        )

        pb.defParam(
            "fluxPeak",
            units=f"n/{units.CM}^2/{units.SECONDS}",
            description="Peak neutron flux calculated within the mesh",
            location=ParamLocation.MAX,
        )

        pb.defParam(
            "kInf",
            units=units.UNITLESS,
            description=(
                "Neutron production rate in this block/neutron absorption rate in this "
                "block. Not truly kinf but a reasonable approximation of reactivity."
            ),
        )

        pb.defParam("medAbsE", units=units.EV, description="Median neutron absorption energy")

        pb.defParam(
            "medFisE",
            units=units.EV,
            description="Median energy of neutron causing fission",
        )

        pb.defParam("medFlxE", units=units.EV, description="Median neutron flux energy")

        pb.defParam(
            "pdensGamma",
            units=f"{units.WATTS}/{units.CM}^3",
            description="Average volumetric gamma power density",
            categories=[parameters.Category.gamma],
        )

        # gamma category because pdens is only split by neutron/gamma when gamma is activated
        pb.defParam(
            "pdensNeutron",
            units=f"{units.WATTS}/{units.CM}^3",
            description="Average volumetric neutron power density",
            categories=[parameters.Category.gamma],
        )

        pb.defParam(
            "ppdens",
            units=f"{units.WATTS}/{units.CM}^3",
            description="Peak power density",
            location=ParamLocation.MAX,
        )

        pb.defParam(
            "ppdensGamma",
            units=f"{units.WATTS}/{units.CM}^3",
            description="Peak gamma density",
            categories=[parameters.Category.gamma],
            location=ParamLocation.MAX,
        )

    # rx rate params that are derived during mesh conversion.
    # We'd like all things that can be derived from flux and XS to be
    # in this category to minimize numerical diffusion but it is a WIP.
    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
    ) as pb:
        pb.defParam(
            "rateAbs",
            units=f"1/{units.CM}^3/{units.SECONDS}",
            description="Total absorption rate in this block (fisson + capture).",
        )

        pb.defParam(
            "rateCap",
            units=f"1/{units.CM}^3/{units.SECONDS}",
            description="Parasitic capture rate in this block.",
        )

        pb.defParam(
            "rateProdN2n",
            units=f"1/{units.CM}^3/{units.SECONDS}",
            description="Production rate of neutrons from n2n reactions.",
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        categories=[parameters.Category.detailedAxialExpansion],
    ) as pb:
        pb.defParam(
            "rateFis",
            units=f"1/{units.CM}^3/{units.SECONDS}",
            description="Fission rate in this block.",
        )

        pb.defParam(
            "rateProdFis",
            units=f"1/{units.CM}^3/{units.SECONDS}",
            description="Production rate of neutrons from fission reactions (nu * fission source / k-eff)",
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.VOLUME_INTEGRATED,
        categories=[parameters.Category.detailedAxialExpansion],
    ) as pb:
        pb.defParam(
            "powerGenerated",
            units=units.WATTS,
            description="Generated power. Different than b.p.power only when gamma transport is activated.",
            categories=[parameters.Category.gamma],
        )

        pb.defParam(
            "power",
            units=units.WATTS,
            description="Total power",
            categories=[parameters.Category.neutronics],
        )

        pb.defParam(
            "powerGamma",
            units=units.WATTS,
            description="Total gamma power",
            categories=[parameters.Category.gamma],
        )

        # gamma category because power is only split by neutron/gamma when gamma is activated
        pb.defParam(
            "powerNeutron",
            units=units.WATTS,
            description="Total neutron power",
            categories=[parameters.Category.gamma],
        )

    with pDefs.createBuilder(default=0.0) as pb:
        pb.defParam(
            "detailedDpaThisCycle",
            units=units.DPA,
            location=ParamLocation.AVERAGE,
            description=(
                "Displacement per atom accumulated during this cycle. This accumulates "
                "over a cycle and resets to zero at BOC."
            ),
            categories=[
                parameters.Category.cumulativeOverCycle,
                parameters.Category.detailedAxialExpansion,
            ],
        )

        pb.defParam(
            "detailedDpaPeakRate",
            units=f"{units.DPA}/{units.SECONDS}",
            description="Peak DPA rate based on detailedDpaPeak",
            location=ParamLocation.MAX,
            categories=[parameters.Category.cumulative, parameters.Category.neutronics],
        )

        pb.defParam(
            "enrichmentBOL",
            units=units.UNITLESS,
            description="Enrichment during fabrication (mass fraction)",
        )

        pb.defParam(
            "fastFlux",
            units=f"1/{units.CM}^2/{units.SECONDS}",
            description="Neutron flux above 100keV",
            location=ParamLocation.AVERAGE,
            categories=["detailedAxialExpansion"],
        )

        pb.defParam(
            "fastFluxFr",
            units=units.UNITLESS,
            description="Fraction of flux above 100keV",
            location=ParamLocation.AVERAGE,
            categories=["detailedAxialExpansion"],
        )

        pb.defParam(
            "pdensGenerated",
            units=f"{units.WATTS}/{units.CM}^3",
            description=(
                "Volume-averaged generated power density. Different than b.p.pdens only "
                "when gamma transport is activated."
            ),
            location=ParamLocation.AVERAGE,
            categories=[parameters.Category.gamma],
        )

    return pDefs


def _getNeutronicsCoreParams():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder(categories=[parameters.Category.neutronics]) as pb:
        pb.defParam(
            "eigenvalues",
            units=units.UNITLESS,
            description="All available lambda-eigenvalues of reactor.",
            default=None,  # will be a list though, can't set default to mutable type.
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "kInf",
            units=units.UNITLESS,
            description="k-infinity",
            default=0.0,
            location=ParamLocation.AVERAGE,
        )

    return pDefs
