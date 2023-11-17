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
"""Settings for generic fuel cycle code."""
import re
import os

from armi.settings import setting
from armi.operators import settingsValidation

CONF_ASSEM_ROTATION_STATIONARY = "assemblyRotationStationary"
CONF_ASSEMBLY_ROTATION_ALG = "assemblyRotationAlgorithm"
CONF_CIRCULAR_RING_MODE = "circularRingMode"
CONF_CIRCULAR_RING_ORDER = "circularRingOrder"
CONF_CUSTOM_FUEL_MANAGEMENT_INDEX = "customFuelManagementIndex"
CONF_FUEL_HANDLER_NAME = "fuelHandlerName"
CONF_JUMP_RING_NUM = "jumpRingNum"
CONF_LEVELS_PER_CASCADE = "levelsPerCascade"
CONF_PLOT_SHUFFLE_ARROWS = "plotShuffleArrows"
CONF_RUN_LATTICE_BEFORE_SHUFFLING = "runLatticePhysicsBeforeShuffling"
CONF_SHUFFLE_LOGIC = "shuffleLogic"


def getFuelCycleSettings():
    """Define settings for fuel cycle."""
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
        ),
        setting.Setting(
            CONF_FUEL_HANDLER_NAME,
            default="",
            label="Fuel Handler Name",
            description="The name of the FuelHandler class in the shuffle logic module to activate",
        ),
        setting.Setting(
            CONF_PLOT_SHUFFLE_ARROWS,
            default=False,
            description="Make plots with arrows showing each move.",
            label="Plot shuffle arrows",
        ),
        setting.Setting(
            CONF_JUMP_RING_NUM, default=8, label="Jump Ring Number", description="None"
        ),
        setting.Setting(
            CONF_LEVELS_PER_CASCADE,
            default=14,
            label="Move per cascade",
            description="None",
        ),
    ]
    return settings


def getFuelCycleSettingValidators(inspector):
    queries = []

    queries.append(
        settingsValidation.Query(
            lambda: bool(inspector.cs[CONF_SHUFFLE_LOGIC])
            ^ bool(inspector.cs[CONF_FUEL_HANDLER_NAME]),
            "A value was provided for `fuelHandlerName` or `shuffleLogic`, but not "
            "the other. Either both `fuelHandlerName` and `shuffleLogic` should be "
            "defined, or neither of them.",
            "",
            inspector.NO_ACTION,
        )
    )

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
        with open(inspector._csRelativePath(inspector.cs[CONF_SHUFFLE_LOGIC])) as src:
            src = src.read()
            matches = []
            for pattern, _sub in regex_solutions:
                matches += re.findall(pattern, src)
            return matches

    def _applyRegexSolutions():
        srcFile = inspector._csRelativePath(inspector.cs[CONF_SHUFFLE_LOGIC])
        destFile = os.path.splitext(srcFile)[0] + "migrated.py"
        with open(srcFile) as src, open(destFile, "w") as dest:
            srcContent = src.read()  # get the buffer content
            regexContent = srcContent  # keep the before and after changes separate

            for pattern, sub in regex_solutions:
                regexContent = re.sub(pattern, sub, regexContent)

            if regexContent != srcContent:
                dest.write("from armi import runLog\n")
            dest.write(regexContent)

        inspector.cs = inspector.cs.modified(newSettings={CONF_SHUFFLE_LOGIC: destFile})

    queries.append(
        settingsValidation.Query(
            lambda: " " in inspector.cs[CONF_SHUFFLE_LOGIC],
            "Spaces are not allowed in shuffleLogic file location. You have specified {0}. "
            "Shuffling will not occur.".format(inspector.cs[CONF_SHUFFLE_LOGIC]),
            "",
            inspector.NO_ACTION,
        )
    )

    def _clearShufflingInput():
        inspector._assignCS(CONF_SHUFFLE_LOGIC, "")
        inspector._assignCS(CONF_FUEL_HANDLER_NAME, "")

    queries.append(
        settingsValidation.Query(
            lambda: inspector.cs[CONF_SHUFFLE_LOGIC]
            and not inspector._csRelativePathExists(inspector.cs[CONF_SHUFFLE_LOGIC]),
            "The specified shuffle logic file '{0}' cannot be found. "
            "Shuffling will not occur.".format(inspector.cs[CONF_SHUFFLE_LOGIC]),
            "Clear specified file value?",
            _clearShufflingInput,
        )
    )

    queries.append(
        settingsValidation.Query(
            lambda: inspector.cs[CONF_SHUFFLE_LOGIC]
            and inspector._csRelativePathExists(inspector.cs[CONF_SHUFFLE_LOGIC])
            and _locateRegexOccurences(),
            "The shuffle logic file {} uses deprecated code."
            " It will not work unless you permit some automated changes to occur."
            " The logic file will be backed up to the current directory under a timestamped name"
            "".format(inspector.cs[CONF_SHUFFLE_LOGIC]),
            "Proceed?",
            _applyRegexSolutions,
        )
    )
    return queries
