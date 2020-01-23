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
    return pDefs


def _getNeutronicsCoreParams():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder(categories=["neutronics"]) as pb:
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
