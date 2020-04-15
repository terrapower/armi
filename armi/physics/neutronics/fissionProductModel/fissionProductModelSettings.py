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


CONF_FP_MODEL = "fpModel"
CONF_MAKE_ALL_BLOCK_LFPS_INDEPENDENT = "makeAllBlockLFPsIndependent"
CONF_LFP_COMPOSITION_FILE_PATH = "lfpCompositionFilePath"


def defineSettings():
    settings = [
        setting.Setting(
            CONF_FP_MODEL,
            default="infinitelyDilute",
            label="Fission Product Model",
            description="The fission product model to use in this ARMI run",
            options=[
                "noFissionProducts",
                "infinitelyDilute",
                "2ndOrder",
                "2ndOrderWithTransmutation",
                "MO99",
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
            default="",
            label="LFP Definition File",
            description=(
                "Path to the file that contains lumped fission product composition "
                "definitions (e.g. equilibrium yields)"
            ),
        ),
    ]
    return settings
