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

We hope neutronics plugins that compute flux will use ``mgFlux``, etc.,
which will enable modular construction of apps.
"""
import numpy

from armi.reactor import parameters
from armi.reactor.parameters import ParamLocation
from armi.reactor.blocks import Block
from armi.reactor.reactors import Core


def getNeutronicsParameterDefinitions():
    """Return ParameterDefinitionCollections for each appropriate ArmiObject."""
    return {Block: _getNeutronicsBlockParams(), Core: _getNeutronicsCoreParams()}


def _getNeutronicsBlockParams():
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder() as pb:

        pb.defParam(
            "axMesh",
            units="",
            description="number of neutronics axial mesh points in this block",
            default=None,
            categories=[parameters.Category.retainOnReplacement],
        )

        def mgFlux(self, value):
            self._p_mgFlux = (
                value
                if value is None or isinstance(value, numpy.ndarray)
                else numpy.array(value)
            )

        pb.defParam(
            "mgFlux",
            setter=mgFlux,
            units="n-cm/s",
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
            units="n-cm/s",
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
            units="n-cm/s",
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
            units="g-cm/s",
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
            units="cm/s",
            description="multigroup neutron velocity",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            categories=[parameters.Category.multiGroupQuantities],
            default=None,
        )

        pb.defParam(
            "extSrc",
            units="g/cm^3/s",
            description="multigroup external source",
            location=ParamLocation.AVERAGE,
            saveToDB=False,
            categories=[parameters.Category.multiGroupQuantities],
            default=None,
        )

        pb.defParam(
            "mgGammaSrc",
            units="g/cm^3/s",
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
            units="g/cm^3/s",
            description="gamma source",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            categories=[parameters.Category.gamma],
            default=0.0,
        )

        pb.defParam(
            "mgFluxSK",
            units="",
            description="multigroup volume-integrated flux stored for multiple time steps in spatial kinetics (2-D array)",
            location=ParamLocation.VOLUME_INTEGRATED,
            saveToDB=False,
            categories=[
                parameters.Category.fluxQuantities,
                parameters.Category.multiGroupQuantities,
            ],
            default=None,
        )

        # Not anointing the pin fluxes as a MG quantity, since it has an extra dimension, which
        # could lead to issues, depending on how the multiGroupQuantities category gets used
        pb.defParam(
            "pinMgFluxes",
            units="n/s/cm$^2$",
            description="""
                The block-level pin multigroup fluxes. pinMgFluxes[g][i] represents the flux in group g for pin i.  Flux
                units are the standard n/cm^2/s.  The "ARMI pin ordering" is used, which is counter-clockwise from 3
                o'clock.
            """,
            categories=[parameters.Category.pinQuantities],
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "pinMgFluxesAdj",
            units="",
            description="should be a blank 3-D array, but re-defined later (ng x nPins x nAxialSegments)",
            categories=[parameters.Category.pinQuantities],
            saveToDB=False,
            default=None,
        )

        pb.defParam(
            "pinMgFluxesGamma",
            units="g/s/cm$^2$",
            description="should be a blank 3-D array, but re-defined later (ng x nPins x nAxialSegments)",
            categories=[parameters.Category.pinQuantities, parameters.Category.gamma],
            saveToDB=False,
            default=None,
        )

        pb.defParam(
            "axialPowerProfile",
            units="",
            description="""
                For each reconstructed axial location, a tuple (z,power density) where with axial origin at the bottom
                of assembly in which the blocks are located.
            """,
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "axialPowerProfileNeutron",
            units="",
            description="",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "axialPowerProfileGamma",
            units="",
            description="",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "betad",
            units="",
            description="Delayed neutron beta",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "chi",
            units="",
            description="Energy distribution of fission neutrons",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "chid",
            units="",
            description="Energy distribution of delayed fission neutrons",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "linPow",
            units="W/m",
            description=(
                "Pin-averaged linear heat rate, which is calculated by evaluating the block power and dividing "
                "by the number of pins. If gamma transport is enabled, then this represents the combined "
                "neutron and gamma heating. If gamma transport is disabled then this represents the energy "
                "generation in the pin, where gammas are assumed to deposit their energy locally. Note that this "
                "value does not implicitly account for axial and radial peaking factors within the block. Use `linPowByPin` "
                "for obtaining the pin linear heat rate with peaking factors included."
            ),
            location=ParamLocation.AVERAGE,
            default=0.0,
            categories=[
                parameters.Category.detailedAxialExpansion,
                parameters.Category.neutronics,
            ],
        )

        def linPowByPin(self, value):
            if value is None or isinstance(value, numpy.ndarray):
                self._p_linPowByPin = value
            else:
                self._p_linPowByPin = numpy.array(value)

        pb.defParam(
            "linPowByPin",
            setter=linPowByPin,
            units="W/cm",
            description=(
                "Pin linear linear heat rate, which is calculated through flux reconstruction and "
                "accounts for axial and radial peaking factors. This differs from the `linPow` "
                "parameter, which assumes no axial and radial peaking in the block as this information "
                "is unavailable without detailed flux reconstruction. The same application of neutron and gamma "
                "heating results applies."
            ),
            location=ParamLocation.CHILDREN,
            categories=[parameters.Category.pinQuantities],
            default=None,
        )

        def linPowByPinNeutron(self, value):
            if value is None or isinstance(value, numpy.ndarray):
                self._p_linPowByPinNeutron = value
            else:
                self._p_linPowByPinNeutron = numpy.array(value)

        # gamma category because linPowByPin is only split by neutron/gamma when gamma is activated
        pb.defParam(
            "linPowByPinNeutron",
            setter=linPowByPinNeutron,
            units="W/cm",
            description="Pin linear neutron heat rate. This is the neutron heating component of `linPowByPin`",
            location=ParamLocation.CHILDREN,
            categories=[parameters.Category.pinQuantities, parameters.Category.gamma],
            default=None,
        )

        def linPowByPinGamma(self, value):
            if value is None or isinstance(value, numpy.ndarray):
                self._p_linPowByPinGamma = value
            else:
                self._p_linPowByPinGamma = numpy.array(value)

        pb.defParam(
            "linPowByPinGamma",
            setter=linPowByPinGamma,
            units="W/cm",
            description="Pin linear gamma heat rate. This is the gamma heating component of `linPowByPin`",
            location=ParamLocation.CHILDREN,
            categories=[parameters.Category.pinQuantities, parameters.Category.gamma],
            default=None,
        )

        pb.defParam(
            "reactionRates",
            units="#/s",
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
            units=None,
            description="Fraction of flux above 100keV at edges of the block",
        )

        pb.defParam(
            "pointsEdgeDpa",
            units="dpa",
            description="displacements per atom at edges of the block",
            categories=["cumulative", "detailedAxialExpansion", "depletion"],
        )

        pb.defParam(
            "pointsEdgeDpaRate",
            units="dpa/s",
            description="Current time derivative of the displacement per atoms at edges of the block",
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
            units="n/cm^2/s",
            description="Neutron flux above 100keV at hexagon block corners",
        )

        pb.defParam(
            "pointsCornerFastFluxFr",
            units=None,
            description="Fraction of flux above 100keV at corners of the block",
        )

        pb.defParam(
            "pointsCornerDpa",
            units="dpa",
            description="displacements per atom at corners of the block",
            location=ParamLocation.CORNERS,
            categories=["cumulative", "detailedAxialExpansion", "depletion"],
        )

        pb.defParam(
            "pointsCornerDpaRate",
            units="dpa/s",
            description="Current time derivative of the displacement per atoms at corners of the block",
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        categories=[parameters.Category.detailedAxialExpansion],
    ) as pb:
        # Neutronics reaction rate params that are not re-derived in mesh conversion
        pb.defParam(
            "rateBalance",
            units="1/cm^3/s",
            description="Numerical balance between particle production and destruction (should be small)",
        )

        pb.defParam(
            "rateExtSrc",
            units="1/cm^3/s",
            description="Rate of production of neutrons from an external source.",
        )

        pb.defParam(
            "rateFisAbs",
            units="1/cm^3/s",
            description="Neutron abs. rate in fissile material",
        )

        pb.defParam(
            "rateFisSrc",
            units="1/cm^3/s",
            description="Fission source rate. This is related to production rate in fissile by a factor of keff",
        )

        pb.defParam(
            "rateLeak",
            units="1/cm^3/s",
            description="Rate that neutrons leak out of this block.",
        )

        pb.defParam(
            "rateParasAbs",
            units="1/cm^3/s",
            description="Rate of parasitic absorption (absorption in non-fertile/fissionable material)",
        )

        pb.defParam(
            "rateProdNet",
            units="1/cm^3/s",
            description="Net production rate of neutrons",
        )

        pb.defParam(
            "rateScatIn",
            units="1/cm^3/s",
            description="Rate neutrons in-scatter in this block",
        )

        pb.defParam(
            "rateScatOut",
            units="1/cm^3/s",
            description="Rate that neutrons out-scatter in this block (removal - absorption)",
        )

        pb.defParam(
            "capturePowerFrac",
            units=None,
            description="Fraction of the power produced through capture in a block.",
            saveToDB="True",
        )

        pb.defParam(
            "fastFluence",
            units="#/cm^2",
            description="Fast spectrum fluence",
            categories=[
                parameters.Category.cumulative,
                parameters.Category.detailedAxialExpansion,
            ],
        )

        pb.defParam(
            "fastFluencePeak",
            units="#/cm^2",
            description="Fast spectrum fluence with a peaking factor",
            location=ParamLocation.MAX,
            categories=[
                parameters.Category.cumulative,
                parameters.Category.detailedAxialExpansion,
            ],
        )

        pb.defParam(
            "fluence", units="#/cm^2", description="Fluence", categories=["cumulative"]
        )

        pb.defParam(
            "flux",
            units="n/cm^2/s",
            description="neutron flux",
            categories=[
                parameters.Category.retainOnReplacement,
                parameters.Category.fluxQuantities,
            ],
        )

        pb.defParam(
            "fluxAdj", units="", description="Adjoint flux"  # adjoint flux is unitless
        )
        pb.defParam(
            "fluxAdjPeak",
            units="",
            description="Adjoint flux",
            location=ParamLocation.MAX,
        )

        pb.defParam(
            "pdens",
            units="W/cm$^3$",
            description="Average volumetric power density",
            categories=[parameters.Category.neutronics],
        )

        pb.defParam(
            "pdensDecay",
            units="W/cm$^3$",
            description="Decay power density from decaying radionuclides",
        )

        pb.defParam("arealPd", units="MW/m^2", description="Power divided by XY area")

        pb.defParam("fertileBonus", units=None, description="The fertile bonus")

        pb.defParam(
            "fisDens",
            units="fissions/cm^3/s",
            description="Fission density in a pin (scaled up from homogeneous)",
        )

        pb.defParam(
            "fisDensHom", units="1/cm^3/s", description="Homogenized fissile density"
        )

        pb.defParam(
            "fluxGamma",
            units="g/cm^2/s",
            description="Gamma scalar flux",
            categories=[
                parameters.Category.retainOnReplacement,
                parameters.Category.fluxQuantities,
            ],
        )

        pb.defParam(
            "fluxPeak",
            units="n/cm^2/s",
            description="Peak neutron flux calculated within the mesh",
            location=ParamLocation.MAX,
        )

        pb.defParam(
            "kInf",
            units="None",
            description="Neutron production rate in this block/neutron absorption rate in this block. Not truly kinf but a reasonable approximation of reactivity.",
        )

        pb.defParam(
            "medAbsE", units="eV", description="Median neutron absorption energy"
        )

        pb.defParam(
            "medFisE",
            units="eV",
            description="Median energy of neutron causing fission",
        )

        pb.defParam("medFlxE", units="eV", description="Median neutron flux energy")

        pb.defParam(
            "pdensGamma",
            units="W/cm^3",
            description="Average volumetric gamma power density",
            categories=[parameters.Category.gamma],
        )

        # gamma category because pdens is only split by neutron/gamma when gamma is activated
        pb.defParam(
            "pdensNeutron",
            units="W/cm^3",
            description="Average volumetric neutron power density",
            categories=[parameters.Category.gamma],
        )

        pb.defParam(
            "ppdens",
            units="W/cm^3",
            description="Peak power density",
            location=ParamLocation.MAX,
        )

        pb.defParam(
            "ppdensGamma",
            units="W/cm^3",
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
            units="1/cm^3/s",
            description="Total absorption rate in this block (fisson + capture).",
        )

        pb.defParam(
            "rateCap",
            units="1/cm^3/s",
            description="Parasitic capture rate in this block.",
        )

        pb.defParam(
            "rateProdN2n",
            units="1/cm^3/s",
            description="Production rate of neutrons from n2n reactions.",
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        categories=[parameters.Category.detailedAxialExpansion],
    ) as pb:
        pb.defParam(
            "rateFis", units="1/cm^3/s", description="Fission rate in this block."
        )

        pb.defParam(
            "rateProdFis",
            units="1/cm^3/s",
            description="Production rate of neutrons from fission reactions (nu * fission source / k-eff)",
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.VOLUME_INTEGRATED,
        categories=[parameters.Category.detailedAxialExpansion],
    ) as pb:
        pb.defParam(
            "powerGenerated",
            units=" W",
            description="Generated power. Different than b.p.power only when gamma transport is activated.",
            categories=[parameters.Category.gamma],
        )

        pb.defParam(
            "power",
            units="W",
            description="Total power",
            categories=[parameters.Category.neutronics],
        )

        pb.defParam("powerDecay", units="W", description="Total decay power")

        pb.defParam(
            "powerGamma",
            units="W",
            description="Total gamma power",
            categories=[parameters.Category.gamma],
        )

        # gamma category because power is only split by neutron/gamma when gamma is activated
        pb.defParam(
            "powerNeutron",
            units="W",
            description="Total neutron power",
            categories=[parameters.Category.gamma],
        )

    with pDefs.createBuilder(default=0.0) as pb:
        pb.defParam(
            "detailedDpaThisCycle",
            units="dpa",
            location=ParamLocation.AVERAGE,
            description="Displacement per atom accumulated during this cycle. This accumulates over a cycle and resets to zero at BOC.",
            categories=[
                parameters.Category.cumulativeOverCycle,
                parameters.Category.detailedAxialExpansion,
            ],
        )

        pb.defParam(
            "detailedDpaPeakRate",
            units="DPA/s",
            description="Peak DPA rate based on detailedDpaPeak",
            location=ParamLocation.MAX,
            categories=[parameters.Category.cumulative, parameters.Category.neutronics],
        )

        pb.defParam(
            "dpaPeakFromFluence",
            units="dpa",
            description="DPA approximation based on a fluence conversion factor set in the dpaPerFluence setting",
            location=ParamLocation.MAX,
            categories=[
                parameters.Category.cumulative,
                parameters.Category.detailedAxialExpansion,
            ],
        )

        pb.defParam(
            "enrichmentBOL",
            units="mass fraction",
            description="Enrichment during fabrication",
        )

        pb.defParam(
            "fastFlux",
            units="1/cm^2/s",
            description="Neutron flux above 100keV",
            location=ParamLocation.AVERAGE,
            categories=["detailedAxialExpansion"],
        )

        pb.defParam(
            "fastFluxFr",
            units="",
            description="Fraction of flux above 100keV",
            location=ParamLocation.AVERAGE,
            categories=["detailedAxialExpansion"],
        )

        pb.defParam(
            "pdensGenerated",
            units="W/cm^3",
            description="Volume-averaged generated power density. Different than b.p.pdens only when gamma transport is activated.",
            location=ParamLocation.AVERAGE,
            categories=[parameters.Category.gamma],
        )

    return pDefs


def _getNeutronicsCoreParams():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder(categories=[parameters.Category.neutronics]) as pb:
        pb.defParam(
            "eigenvalues",
            units=None,
            description="All available lambda-eigenvalues of reactor.",
            default=None,  # will be a list though, can't set default to mutable type.
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "kInf",
            units=None,
            description="k-infinity",
            default=0.0,
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "refKeff",
            units=None,
            description="Reference unperturbed keff",
            default=0.0,
            location=ParamLocation.AVERAGE,
        )

    return pDefs
