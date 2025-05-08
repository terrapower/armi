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

"""
Provides the ability to ignore parameters sections of blueprint files.

This plugin can allow you to more easily open a database, because you can ignore sections of the
blueprint files, and ignore any parameters as you want.

This was designed to allow loading an ARMI database without the application that created it.
"""
import yamlize

from armi import plugins
from armi.reactor import parameters
from armi.reactor.parameters import ParamLocation
from armi.utils import units


class PassThroughYamlize(yamlize.Object):
    """Just a helper for PassiveDBLoadPlugin, to allow for ignore unknown blueprints sections."""

    @classmethod
    def from_yaml(cls, loader, node, round_trip_data=None):
        node.value = []
        return yamlize.Object.from_yaml.__func__(
            PassThroughYamlize, loader, node, round_trip_data
        )


class PassiveDBLoadPlugin(plugins.ArmiPlugin):
    """Provides the ability to passively load a reactor data model from an ARMI DB even if there are
    unknown parameters and blueprint sections.

    This plugin allows you two define two things:

    1. Sections of blueprint files to ignore entirely.
    2. A collection of unknown parameters that will be loaded without units or underlying metadata.

    To use this plugin, you need to set two class variables before instantiating the ARMI App:

    1. Set ``SKIP_BP_SECTIONS`` to a list of BP section names (strings).
    2. Set ``UNKNOWN_PARAMS`` to a mapping from param class to name: ``{Core: ["a", "b", "c"]}``

    Notes
    -----
    Obviously, if you are loading huge numbers of unknown parameters and ignoring whole sections of
    blueprints, you are losing information. There is no way to use this plugin and still claim full
    fidelity of your understanding of the reactor. ARMI does not support any such claims.
    """

    SKIP_BP_SECTIONS = []
    UNKNOWN_PARAMS = {}

    @staticmethod
    @plugins.HOOKIMPL
    def defineBlueprintsSections():
        """Ignore a pre-determined set of blueprint sections."""
        skips = []
        for skippedBp in PassiveDBLoadPlugin.SKIP_BP_SECTIONS:
            skips.append(
                (
                    skippedBp.replace(" ", ""),
                    yamlize.Attribute(
                        key=skippedBp, type=PassThroughYamlize, default=None
                    ),
                    PassThroughYamlize,
                )
            )

        return skips

    @staticmethod
    @plugins.HOOKIMPL
    def defineParameters():
        """Define parameters for the plugin."""
        # build all the parameters we are missing in default ARMI
        params = {}
        for dataClass, paramNames in PassiveDBLoadPlugin.UNKNOWN_PARAMS.items():
            if len(paramNames):
                params[dataClass] = PassiveDBLoadPlugin.buildParamColl(paramNames)

        return params

    @staticmethod
    def buildParamColl(names):
        """Try replacing any missing parameters with unitless nonsense."""
        # build a collection of defaulted parameters to passively ignore
        desc = "This is just a placeholder Parameter; it's meaning is unknown."
        pDefs = parameters.ParameterDefinitionCollection()
        with pDefs.createBuilder(location=ParamLocation.AVERAGE) as pb:
            for param in names:
                pb.defParam(
                    param, units=units.UNITLESS, description=desc, saveToDB=False
                )

        return pDefs
