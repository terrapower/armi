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

from armi.settings import setting, settingsValidation

CONF_ASSEM_ROTATION_STATIONARY = "assemblyRotationStationary"
CONF_ASSEMBLY_ROTATION_ALG = "assemblyRotationAlgorithm"
CONF_CIRCULAR_RING_MODE = "circularRingMode"
CONF_CIRCULAR_RING_ORDER = "circularRingOrder"
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
                "Whether or not to rotate assemblies that are not shuffled.This can only be True if 'rotation' is true."
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
            CONF_JUMP_RING_NUM,
            default=8,
            label="Jump Ring Number",
            description="The number of hex rings jumped when distributing the feed assemblies in "
            "the alternating concentric rings or checkerboard shuffle patterns (convergent / "
            "divergent shuffling).",
        ),
        setting.Setting(
            CONF_LEVELS_PER_CASCADE,
            default=14,
            label="Move per cascade",
            description="The number of moves made per cascade when performing convergent or "
            "divergent shuffle patterns.",
        ),
    ]
    return settings


def getFuelCycleSettingValidators(inspector):
    queries = []

    queries.append(
        settingsValidation.Query(
            lambda: bool(inspector.cs[CONF_SHUFFLE_LOGIC]) ^ bool(inspector.cs[CONF_FUEL_HANDLER_NAME]),
            "A value was provided for `fuelHandlerName` or `shuffleLogic`, but not "
            "the other. Either both `fuelHandlerName` and `shuffleLogic` should be "
            "defined, or neither of them.",
            "",
            inspector.NO_ACTION,
        )
    )

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
            "The specified shuffle logic file '{0}' cannot be found. Shuffling will not occur.".format(
                inspector.cs[CONF_SHUFFLE_LOGIC]
            ),
            "Clear specified file value?",
            _clearShufflingInput,
        )
    )

    return queries
