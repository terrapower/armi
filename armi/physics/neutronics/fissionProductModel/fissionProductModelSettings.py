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

"""Settings related to the fission product model."""

from armi.physics.neutronics import fissionProductModel
from armi.settings import setting

CONF_FP_MODEL = "fpModel"
CONF_MAKE_ALL_BLOCK_LFPS_INDEPENDENT = "makeAllBlockLFPsIndependent"
CONF_LFP_COMPOSITION_FILE_PATH = "lfpCompositionFilePath"
CONF_FISSION_PRODUCT_LIBRARY_NAME = "fpModelLibrary"


def defineSettings():
    """Define settings for the plugin."""
    settings = [
        setting.Setting(
            CONF_FP_MODEL,
            default="infinitelyDilute",
            label="Fission Product Model",
            description=(
                "This setting is used to determine how fission products are treated in an "
                "analysis. By choosing `noFissionProducts`, no fission products will be added. By "
                "selecting, `infinitelyDilute`, lumped fission products will be initialized to a "
                "very small number on the blocks/components that require them. By choosing `MO99`, "
                "the fission products will be represented only by Mo-99. This is a simplistic "
                "assumption that is commonly used by fast reactor analyses in scoping calculations "
                "and is not necessarily a great assumption for depletion evaluations. Finally, by "
                "choosing `explicitFissionProducts` the fission products will be added explicitly "
                "to the blocks/components that are depletable. This is useful for detailed tracking "
                "of fission products."
            ),
            options=[
                "noFissionProducts",
                "infinitelyDilute",
                "MO99",
                "explicitFissionProducts",
            ],
        ),
        setting.Setting(
            CONF_FISSION_PRODUCT_LIBRARY_NAME,
            default="",
            label="Fission Product Library",
            description=(
                f"This setting should be used when `{CONF_FP_MODEL}` is set to "
                "`explicitFissionProducts`. It is used in conjunction with any nuclideFlags "
                "defined in the blueprints to configure all the nuclides that are modeled within "
                "the core. Selecting any library option will add all nuclides from the selected "
                "library to the model so that analysts do not need to change their inputs when "
                "modifying the fission product treatment for calculations."
            ),
            options=[
                "",
                "MC2-3",
            ],
        ),
        setting.Setting(
            CONF_MAKE_ALL_BLOCK_LFPS_INDEPENDENT,
            default=False,
            label="Use Independent LFPs",
            description=(
                "Flag to make all blocks have independent lumped fission products. Note that this "
                "is forced to be True when the `explicitFissionProducts` modeling option is "
                "selected or an interface named `mcnp` is on registered on the operator stack."
            ),
        ),
        setting.Setting(
            CONF_LFP_COMPOSITION_FILE_PATH,
            default=fissionProductModel.REFERENCE_LUMPED_FISSION_PRODUCT_FILE,
            label="LFP Definition File",
            description=(
                "Path to the file that contains lumped fission product composition definitions "
                "(e.g. equilibrium yields). This is unused when the `explicitFissionProducts` or "
                "`MO99` modeling options are selected."
            ),
        ),
    ]
    return settings


def getFissionProductModelSettingValidators(inspector):
    """The standard helper method, to provide validators to the fission product model."""
    # Import the Query class here to avoid circular imports.
    from armi.settings.settingsValidation import Query

    queries = []

    queries.append(
        Query(
            lambda: inspector.cs[CONF_FP_MODEL] != "explicitFissionProducts"
            and not bool(inspector.cs["initializeBurnChain"]),
            (
                "The burn chain is not being initialized and the fission product model is not set "
                "to `explicitFissionProducts`. This will likely fail."
            ),
            f"Would you like to set the `{CONF_FP_MODEL}` to `explicitFissionProducts`?",
            lambda: inspector._assignCS(CONF_FP_MODEL, "explicitFissionProducts"),
        )
    )

    queries.append(
        Query(
            lambda: inspector.cs[CONF_FP_MODEL] != "explicitFissionProducts"
            and inspector.cs[CONF_FISSION_PRODUCT_LIBRARY_NAME] != "",
            (
                "The explicit fission product model is disabled and the fission product model "
                "library is set. This will have no impact on the results, but it is best to "
                f"disable the `{CONF_FISSION_PRODUCT_LIBRARY_NAME}` option."
            ),
            "Would you like to do this?",
            lambda: inspector._assignCS(CONF_FISSION_PRODUCT_LIBRARY_NAME, ""),
        )
    )

    queries.append(
        Query(
            lambda: inspector.cs[CONF_FP_MODEL] == "explicitFissionProducts"
            and bool(inspector.cs["initializeBurnChain"]),
            (
                "The explicit fission product model is enabled, but initializing the burn chain is "
                "also enabled. This will likely fail."
            ),
            "Would you like to disable the burn chain initialization?",
            lambda: inspector._assignCS("initializeBurnChain", False),
        )
    )

    queries.append(
        Query(
            lambda: inspector.cs[CONF_FP_MODEL] == "explicitFissionProducts"
            and inspector.cs[CONF_FISSION_PRODUCT_LIBRARY_NAME] == "",
            (
                "The explicit fission product model is enabled and the fission product model "
                "library is disabled. May result in no fission product nuclides being added to the "
                "case, unless these have manually added in `nuclideFlags`."
            ),
            (
                f"Would you like to set the `{CONF_FISSION_PRODUCT_LIBRARY_NAME}` option to be "
                "equal to the default implementation of MC2-3?."
            ),
            lambda: inspector._assignCS(CONF_FISSION_PRODUCT_LIBRARY_NAME, "MC2-3"),
        )
    )

    return queries
