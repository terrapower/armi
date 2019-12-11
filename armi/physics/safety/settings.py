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

from armi.settings import setting2 as setting


CONF_BETA_COMPONENTS = "betaComponents"
CONF_DECAY_CONSTANTS = "decayConstants"


def defineSettings():
    settings = [
        setting.Setting(
            CONF_BETA_COMPONENTS,
            default=[],
            label="Beta Components",
            description="Manually set individual precursor group delayed neutron fractions",
        ),
        setting.Setting(
            CONF_DECAY_CONSTANTS,
            default=[],
            label="Decay Constants",
            description="Manually set individual precursor group delayed neutron decay constants",
        ),
    ]
    return settings
