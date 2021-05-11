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
            categories=[parameters.Category.multiGroupQuantities],
            default=None,
        )

        pb.defParam(
            "gammaSrc",
            units="g/cm^3/s",
            description="gamma source",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=None,
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
                o'clock.  See TP1-1.9.31-RPT-0010 for more details.
            """,
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "pinMgFluxesAdj",
            units="",
            description="should be a blank 3-D array, but re-defined later (ng x nPins x nAxialSegments)",
            saveToDB=False,
            default=None,
        )

        pb.defParam(
            "pinMgFluxesGamma",
            units="g/s/cm$^2$",
            description="should be a blank 3-D array, but re-defined later (ng x nPins x nAxialSegments)",
            saveToDB=False,
            default=None,
        )

        pb.defParam(
            "pinPowers",
            units="W/cm",
            description="""
                The block-level pin linear power densities. pinPowers[i] represents the average linear power density of
                pin i.  Power units are Watts/cm (Watts produced per cm of pin length).  The "ARMI pin ordering" is
                used, which is counter-clockwise from 3 o'clock.  See TP1-1.9.31-RPT-0010 for more details.
            """,
            saveToDB=True,
            default=None,
        )

        def pinPowersNeutron(self, value):
            self._p_pinPowersNeutron = (
                value
                if value is None or isinstance(value, numpy.ndarray)
                else numpy.array(value)
            )

        pb.defParam(
            "pinPowersNeutron",
            setter=pinPowersNeutron,
            units="W/cm",
            description="""
                The block-level pin linear power densities from neutron-induced
                interactions. pinPowersNeutron[i] represents the average linear power density of pin i
                (from neutron heating). Power units are Watts/cm (Watts produced per cm of pin length).
            """,
            saveToDB=True,
            default=None,
        )

        def pinPowersGamma(self, value):
            self._p_pinPowersGamma = (
                value
                if value is None or isinstance(value, numpy.ndarray)
                else numpy.array(value)
            )

        pb.defParam(
            "pinPowersGamma",
            setter=pinPowersGamma,
            units="W/cm",
            description="""
                The block-level pin linear power densities from gamma heating.
                pinPowersGamma[i] represents the average linear power density of pin i (from gamma
                heating). Power units are Watts/cm (Watts produced per cm of pin length).",
            """,
            saveToDB=True,
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
            "axialMgFluxReconCoeff",
            units="",
            description="""
                The coefficients in the axial multigroup flux profile polynomial for this block.  The flux profile is
                usually A*z^4 + B*z^3 + C*z^2 + D*z + E, and so this variable will be the 5 x ng list, so
                axialMgFluxReconCoeff[g][i] is the ith coefficient for flux group g.  Also, this flux profile is
                normalized (for each group) so that its average is always 1.0 in each block.  One must multiply the
                coefficients of each group by the block-average group flux to obtain the axial group flux profile.
            """,
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "axialMgFluxProfileAdj",
            units="",
            description="",
            location=ParamLocation.AVERAGE,
            saveToDB=False,
            default=None,
        )

        pb.defParam(
            "axialMgFluxProfileNeutron",
            units="",
            description="",
            location=ParamLocation.AVERAGE,
            saveToDB=False,
            default=None,
        )

        pb.defParam(
            "axialMgFluxProfileNeutronAdj",
            units="",
            description="",
            location=ParamLocation.AVERAGE,
            saveToDB=False,
            default=None,
        )

        pb.defParam(
            "axialMgFluxProfileGamma",
            units="",
            description="",
            location=ParamLocation.AVERAGE,
            saveToDB=False,
            default=None,
        )

        pb.defParam(
            "radialMgFluxProfile",
            units="",
            description="",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "radialMgFluxProfileAdj",
            units="",
            description="",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "radialMgFluxProfileNeutron",
            units="",
            description="",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "radialMgFluxProfileNeutronAdj",
            units="",
            description="",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=None,
        )

        pb.defParam(
            "radialMgFluxProfileGamma",
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
            description="Pin-averaged linear heat generation rate",
            location=ParamLocation.AVERAGE,
            default=0.0,
            categories=[parameters.Category.detailedAxialExpansion],
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
            description="Pin linear power",
            location=ParamLocation.CHILDREN,
            default=None,
        )

        def linPowByPinNeutron(self, value):
            if value is None or isinstance(value, numpy.ndarray):
                self._p_linPowByPinNeutron = value
            else:
                self._p_linPowByPinNeutron = numpy.array(value)

        pb.defParam(
            "linPowByPinNeutron",
            setter=linPowByPinNeutron,
            units="W/cm",
            description="Pin linear neutron power",
            location=ParamLocation.CHILDREN,
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
            description="Pin linear gamma power",
            location=ParamLocation.CHILDREN,
            default=None,
        )

        pb.defParam(
            "reactionRates",
            units="Reactions/sec",
            description='List of reaction rates in specified by setting "reactionsToDB"',
            location=ParamLocation.VOLUME_INTEGRATED,
            default=None,
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
            categories=["cumulative"],
        )

        pb.defParam(
            "fastFluencePeak",
            units="#/cm^2",
            description="Fast spectrum fluence with a peaking factor",
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
        )

        pb.defParam(
            "pdens", units="W/cm$^3$", description="Average volumetric power density"
        )

        pb.defParam(
            "pdensDecay",
            units="W/cm$^3$",
            description="Decay power density from decaying radionuclides",
        )

        pb.defParam("arealPd", units="MW/m^2", description="Power divided by XY area")

        pb.defParam(
            "arealPdGamma", units="MW/m^2", description="Areal gamma power density"
        )

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
            "fluxDeltaFromRef",
            units="None",
            description="Relative difference between the current flux and the directly-computed perturbed flux.",
        )

        pb.defParam(
            "fluxDirect",
            units="n/cm^2/s",
            description="Flux is computed with a direct method",
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
        )

        pb.defParam(
            "fluxPertDeltaFromDirect",
            units="None",
            description="Relative difference between the perturbed flux and the directly-computed perturbed flux",
        )

        pb.defParam(
            "fluxPertDeltaFromDirectfluxRefWeighted", units="None", description=""
        )

        pb.defParam(
            "fluxPerturbed", units="1/cm^2/s", description="Flux is computed by MEPT"
        )

        pb.defParam("fluxRef", units="1/cm^2/s", description="Reference flux")

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
        )

        pb.defParam(
            "pdensNeutron",
            units="W/cm^3",
            description="Average volumetric neutron power density",
        )

        pb.defParam("ppdens", units="W/cm^3", description="Peak power density")

        pb.defParam("ppdensGamma", units="W/cm^3", description="Peak gamma density")

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
            "rateFis", units="1/cm^3/s", description="Fission rate in this block."
        )

        pb.defParam(
            "rateProdFis",
            units="1/cm^3/s",
            description="Production rate of neutrons from fission reactions (nu * fission source / k-eff)",
        )

        pb.defParam(
            "rateProdN2n",
            units="1/cm^3/s",
            description="Production rate of neutrons from n2n reactions.",
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
        )

        pb.defParam("power", units="W", description="Total power")

        pb.defParam("powerDecay", units="W", description="Total decay power")

        pb.defParam("powerGamma", units="W", description="Total gamma power")

        pb.defParam("powerNeutron", units="W", description="Total neutron power")

    with pDefs.createBuilder(default=0.0) as pb:
        pb.defParam(
            "detailedDpaNewCycle",
            units="dpa",
            description="The total DPA accumulated in all burn steps of one cycle",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "detailedDpaPeakNewCycle",
            units="dpa",
            description="The total peak DPA accumulated in all burn steps of one cycle",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "detailedDpaThisCycle",
            units="dpa",
            location=ParamLocation.AVERAGE,
            description="Displacement per atom accumulated during this cycle. This accumulates over a cycle and resets to zero at BOC.",
            categories=["cumulative over cycle", "detailedAxialExpansion"],
        )

        pb.defParam(
            "detailedDpaPeakRate",
            units="DPA/s",
            description="Peak DPA rate based on detailedDpaPeak",
            location=ParamLocation.AVERAGE,
        )

        pb.defParam(
            "dpaPeakFromFluence",
            units="dpa",
            description="DPA approximation based on a fluence conversion factor set in the dpaPerFluence setting",
            location=ParamLocation.AVERAGE,
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
        )

        pb.defParam(
            "fastFluxFr",
            units="",
            description="Fraction of flux above 100keV",
            location=ParamLocation.AVERAGE,
            categories=["detailedAxialExpansion"],
        )

        # This quantity should eventually be part of category 'detailedAxialExpansion'
        # to be "remapped" (converter currently do not support arrays)
        pb.defParam(
            "cornerFastFlux",
            units="n/cm^2/s",
            description="Neutron flux above 100keV at hexagon block corners",
            location=ParamLocation.CORNERS,
            saveToDB=False,
        )

        # This quantity should eventually be part of category 'detailedAxialExpansion'
        # to be "remapped" (converter currently do not support arrays)
        pb.defParam(
            "pointsFastFluxFr",
            units=None,
            description="Fraction of flux above 100keV at points within the block",
            location=ParamLocation.CHILDREN,
            saveToDB=False,
        )

        # This quantity should eventually be part of category 'detailedAxialExpansion'
        # to be "remapped" (converter currently do not support arrays)
        pb.defParam(
            "pointsDpa",
            units="dpa",
            description="displacements per atom at points within the block",
            location=ParamLocation.CHILDREN,
            categories=["cumulative"],
            saveToDB=False,
            default=0.0,
        )

        # This quantity should eventually be part of category 'detailedAxialExpansion'
        # to be "remapped" (converter currently do not support arrays)
        pb.defParam(
            "pointsDpaRate",
            units="dpa/s",
            description="Current time derivative of the displacement per atoms at points within the block",
            location=ParamLocation.CHILDREN,
            saveToDB=False,
        )

        pb.defParam(
            "pdensGenerated",
            units="W/cm^3",
            description="Volume-averaged generated power density. Different than b.p.pdens only when gamma transport is activated.",
            location=ParamLocation.AVERAGE,
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
            "axialMesh",
            units="cm",
            description="Global axial mesh from bottom to top used in structured-mesh neutronics simulations.",
            default=None,
            location=ParamLocation.TOP,
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
