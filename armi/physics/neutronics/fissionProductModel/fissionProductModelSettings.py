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

from armi.settings import setting
from armi.physics.neutronics import fissionProductModel

CONF_FP_MODEL = "fpModel"
CONF_MAKE_ALL_BLOCK_LFPS_INDEPENDENT = "makeAllBlockLFPsIndependent"
CONF_LFP_COMPOSITION_FILE_PATH = "lfpCompositionFilePath"
CONF_FISSION_PRODUCT_LIBRARY_NAME = "fpModelLibrary"


def defineSettings():
    settings = [
        setting.Setting(
            CONF_FP_MODEL,
            default="infinitelyDilute",
            label="Fission Product Model",
            description="",
            options=[
                "noFissionProducts",
                "infinitelyDilute",
                "MO99",
                "explicitFissionProducts",
            ],
        ),
        setting.Setting(
            CONF_FISSION_PRODUCT_LIBRARY_NAME,
            default="MC2-3",
            label="Fission Product Library",
            description=(
                f"This setting is used when the `{CONF_FP_MODEL}` setting "
                f"is set to `explicitFissionProducts` and is used to configure "
                f"all the nuclides that should be modeled within the core. "
                f"Setting this is equivalent to adding all nuclides in the "
                f"selected code library (i.e., MC2-3) within the blueprints "
                f"`nuclideFlags` to be [xs:true, burn:false]. This option acts "
                f"as a short-cut so that analysts do not need to change their "
                f"inputs when modifying the fission product treatment for calculations."
            ),
            options=[
                "MC2-3",
            ],
        ),
        setting.Setting(
            CONF_MAKE_ALL_BLOCK_LFPS_INDEPENDENT,
            default=False,
            label="Use Independent LFPs",
            description="Flag to make all blocks have independent lumped fission products",
        ),
        setting.Setting(
            CONF_LFP_COMPOSITION_FILE_PATH,
            default=fissionProductModel.REFERENCE_LUMPED_FISSION_PRODUCT_FILE,
            label="LFP Definition File",
            description=(
                "Path to the file that contains lumped fission product composition "
                "definitions (e.g. equilibrium yields)"
            ),
        ),
    ]
    return settings
