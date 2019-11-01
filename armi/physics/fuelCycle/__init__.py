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
The fuel cycle package analyzes the various elements of nuclear fuel cycles from mining to disposal.

Fuel cycle code can include things like:

* In- and ex-core fuel management
* Fuel chemistry
* Fuel processing
* Fuel fabrication
* Fuel mass flow scenarios
* And so on

There is one included fuel cycle plugin: The Fuel Handler.

The fuel handler plugin moves fuel around in a reactor.
"""
import os
import re

import voluptuous as vol

from armi import runLog
from armi import interfaces
from armi import plugins
from armi import operators
from armi.utils import directoryChangers
from armi.operators import RunTypes
from armi.settings import setting2 as setting
from armi.operators import settingsValidation

from armi.physics.fuelCycle import fuelHandlers


ORDER = interfaces.STACK_ORDER.FUEL_MANAGEMENT

CONF_ASSEMBLY_ROTATION_ALG = "assemblyRotationAlgorithm"
CONF_ASSEM_ROTATION_STATIONARY = "assemblyRotationStationary"
CONF_CIRCULAR_RING_MODE = "circularRingMode"
CONF_CIRCULAR_RING_ORDER = "circularRingOrder"
CONF_CUSTOM_FUEL_MANAGEMENT_INDEX = "customFuelManagementIndex"
CONF_RUN_LATTICE_BEFORE_SHUFFLING = "runLatticePhysicsBeforeShuffling"
CONF_SHUFFLE_LOGIC = "shuffleLogic"
CONF_PLOT_SHUFFLE_ARROWS = "plotShuffleArrows"


class FuelHandlerPlugin(plugins.ArmiPlugin):
    """The build-in ARMI fuel management plugin."""

    @staticmethod
    @plugins.HOOKIMPL
    def exposeInterfaces(cs):
        """
        Implementation of the exposeInterfaces plugin hookspec

        Notes
        -----
        The interface may import user input modules to customize the actual
        fuel management.
        """

        fuelHandlerNeedsToBeActive = cs["fuelHandlerName"] or (
            cs["eqDirect"] and cs["runType"].lower() == RunTypes.STANDARD.lower()
        )
        if not fuelHandlerNeedsToBeActive or "MCNP" in cs["neutronicsKernel"]:
            return []
        else:

            enabled = cs["runType"] != operators.RunTypes.SNAPSHOTS
            return [
                interfaces.InterfaceInfo(
                    ORDER, fuelHandlers.FuelHandlerInterface, {"enabled": enabled}
                )
            ]

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        settings = [
            setting.Setting(
                CONF_ASSEMBLY_ROTATION_ALG,
                default="",
                label="Assembly Rotation Algorithm",
                description="The algorithm to use to rotate the detail assemblies while shuffling",
                options=["", "buReducingAssemblyRotation", "simpleAssemblyRotation"],
                enforcedOptions=True,
            ),
            setting.Setting(
                CONF_ASSEM_ROTATION_STATIONARY,
                default=False,
                label="Rotate stationary assems",
                description=(
                    "Whether or not to rotate assemblies that are not shuffled."
                    "This can only be True if 'rotation' is true."
                ),
            ),
            setting.Setting(
                CONF_CIRCULAR_RING_MODE,
                default=False,
                description="Toggle between circular ring definitions to hexagonal ring definitions",
                label="Use Circular Rings",
            ),
            setting.Setting(
                CONF_CIRCULAR_RING_ORDER,
                default="angle",
                description="Order by which locations are sorted in circular rings for equilibrium shuffling",
                label="Eq. circular sort type",
                options=["angle", "distance", "distanceSmart"],
            ),
            setting.Setting(
                CONF_CUSTOM_FUEL_MANAGEMENT_INDEX,
                default=0,
                description=(
                    "An index that determines which of various options is used in management. "
                    "Useful for optimization sweeps. "
                ),
                label="Custom Shuffling Index",
            ),
            setting.Setting(
                CONF_RUN_LATTICE_BEFORE_SHUFFLING,
                default=False,
                description=(
                    "Forces the Generation of Cross Sections Prior to Shuffling the Fuel Assemblies. "
                    "Note: This is recommended when performing equilibrium shuffling branching searches."
                ),
                label="Generate XS Prior to Fuel Shuffling",
            ),
            setting.Setting(
                CONF_SHUFFLE_LOGIC,
                default="",
                label="Shuffle Logic",
                description=(
                    "Python script written to handle the fuel shuffling for this case.  "
                    "This is user-defined per run as a dynamic input."
                ),
                # schema here could check if file exists, but this is a bit constraining in testing.
                # For example, some tests have relative paths for this but aren't running in
                # the right directory, and IsFile doesn't seem to work well with relative paths.
                # This is left here as an FYI about how we could check existence of files if we get
                # around these problem.
                #                 schema=vol.All(
                #                     vol.IsFile(),  # pylint: disable=no-value-for-parameter
                #                     msg="Shuffle logic input must be an existing file",
                #                 ),
            ),
            setting.Setting(
                CONF_PLOT_SHUFFLE_ARROWS,
                default=False,
                description="Make plots with arrows showing each move.",
                label="Plot shuffle arrows",
            ),
        ]

        return settings

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettingsValidators(inspector):
        """
        Implementation of settings inspections for fuel cycle settings.
        """
        queries = []
        # Check for code fixes for input code on the fuel shuffling outside the version control of ARMI
        # These are basically auto-migrations for untracked code using
        # the ARMI API. (This may make sense at a higher level)
        regex_solutions = [
            (
                r"(#{0,20}?)[^\s#]*output\s*?\((.*?)(,\s*[1-3]{1}\s*)\)",
                r"\1runLog.important(\2)",
            ),
            (
                r"(#{0,20}?)[^\s#]*output\s*?\((.*?)(,\s*[4-5]{1,2}\s*)\)",
                r"\1runLog.info(\2)",
            ),
            (
                r"(#{0,20}?)[^\s#]*output\s*?\((.*?)(,\s*[6-8]{1,2}\s*)\)",
                r"\1runLog.extra(\2)",
            ),
            (
                r"(#{0,20}?)[^\s#]*output\s*?\((.*?)(,\s*\d{1,2}\s*)\)",
                r"\1runLog.debug(\2)",
            ),
            (r"(#{0,20}?)[^\s#]*output\s*?\((.*?)\)", r"\1runLog.important(\2)"),
            (r"output = self.cs.output", r""),
            (r"cs\.getSetting\(\s*([^\)]+)\s*\)", r"cs[\1]"),
            (r"cs\.setSetting\(\s*([^\)]+)\s*,\s*([^\)]+)\s*\)", r"cs[\1] = \2"),
            (
                r"import\s*armi\.components\s*as\s*components",
                r"from armi.reactor import components",
            ),
            (r"\[['\"]caseTitle['\"]\]", r".caseTitle"),
            (
                r"self.r.core.bolAssems\['(.*?)'\]",
                r"self.r.blueprints.assemblies['\1']",
            ),
            (r"copyAssembly", r"duplicate"),
        ]

        def _locateRegexOccurences():
            with open(inspector._csRelativePath(inspector.cs["shuffleLogic"])) as src:
                src = src.read()
                matches = []
                for pattern, _sub in regex_solutions:
                    matches += re.findall(pattern, src)
                return matches

        def _applyRegexSolutions():
            srcFile = inspector._csRelativePath(inspector.cs["shuffleLogic"])
            destFile = os.path.splitext(srcFile)[0] + "migrated.py"
            with open(srcFile) as src, open(destFile, "w") as dest:
                srcContent = src.read()  # get the buffer content
                regexContent = srcContent  # keep the before and after changes separate

                for pattern, sub in regex_solutions:
                    regexContent = re.sub(pattern, sub, regexContent)

                if regexContent != srcContent:
                    dest.write("from armi import runLog\n")
                dest.write(regexContent)
            inspector.cs["shuffleLogic"] = destFile

        queries.append(
            settingsValidation.Query(
                lambda: " " in inspector.cs["shuffleLogic"],
                "Spaces are not allowed in shuffleLogic file location. You have specified {0}. "
                "Shuffling will not occur.".format(inspector.cs["shuffleLogic"]),
                "",
                inspector.NO_ACTION,
            )
        )

        def _clearShufflingInput():
            inspector._assignCS("shuffleLogic", "")
            inspector._assignCS("fuelHandlerName", "")

        queries.append(
            settingsValidation.Query(
                lambda: inspector.cs["shuffleLogic"]
                and not inspector._csRelativePathExists(inspector.cs["shuffleLogic"]),
                "The specified shuffle logic file '{0}' cannot be found. "
                "Shuffling will not occur.".format(inspector.cs["shuffleLogic"]),
                "Clear specified file value?",
                _clearShufflingInput,
            )
        )

        queries.append(
            settingsValidation.Query(
                lambda: inspector.cs["shuffleLogic"]
                and inspector._csRelativePathExists(inspector.cs["shuffleLogic"])
                and _locateRegexOccurences(),
                "The shuffle logic file {} uses deprecated code."
                " It will not work unless you permit some automated changes to occur."
                " The logic file will be backed up to the current directory under a timestamped name"
                "".format(inspector.cs["shuffleLogic"]),
                "Proceed?",
                _applyRegexSolutions,
            )
        )

        return queries
