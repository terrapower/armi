# Copyright 2024 TerraPower, LLC
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

"""TODO: JOHN."""
import yamlize

from armi import plugins
from armi.reactor import parameters
from armi.reactor.parameters import ParamLocation
from armi.utils import units


class PassThroughYamlize(yamlize.Object):
    """Just a helper for PassiveDBLoadPlugin, to allow for ignore unknown blueprints sections."""

    @classmethod
    def from_yaml(cls, loader, node, round_trip_data=None):
        return yamlize.Object.from_yaml.__func__(
            PassThroughYamlize, loader, node, round_trip_data
        )


class PassiveDBLoadPlugin(plugins.ArmiPlugin):

    SKIP_BP_SECTIONS = []
    SKIP_PARAMS = {}

    @staticmethod
    @plugins.HOOKIMPL
    def defineBlueprintsSections():
        """Ignore a pre-determined set of blueprint sections."""
        for skippedBp in PassiveDBLoadPlugin.SKIP_BP_SECTIONS:
            skips = [
                (
                    skippedBp.replace(" ", ""),
                    yamlize.Attribute(
                        key=skippedBp, type=PassThroughYamlize, default=None
                    ),
                    PassThroughYamlize,
                )
            ]

        return skips

    @staticmethod
    @plugins.HOOKIMPL
    def defineParameters():
        """Define parameters for the plugin."""
        # build all the parameters we are missing in default ARMI
        params = {}
        for dataClass, paramNames in PassiveDBLoadPlugin.SKIP_PARAMS.items():
            if len(paramNames):
                params[dataClass] = PassiveDBLoadPlugin.buildParamColl(paramNames)

        return params

    @staticmethod
    def buildParamColl(names):
        """Try replacing any missing parameters with unitless nonsense."""
        # handle the special cases
        for nomen in ["flags", "serialNum"]:
            if nomen in names:
                names.remove(nomen)

        # build a collection of defaulted parameters to passively ignore
        desc = "This is just a silly placeholder Parameter. It's meaning is unknown."
        pDefs = parameters.ParameterDefinitionCollection()
        with pDefs.createBuilder(location=ParamLocation.AVERAGE) as pb:
            for param in names:
                pb.defParam(param, units=units.UNITLESS, description=desc)

        return pDefs
