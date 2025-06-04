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

"""Settings related to Thermal Hydraulics."""

from armi.settings import setting

CONF_DO_TH = "doTH"
CONF_TH_KERNEL = "thKernel"


def defineSettings():
    """Define generic thermal/hydraulic settings."""
    settings = [
        setting.Setting(
            CONF_DO_TH,
            default=False,
            label="Run Thermal Hydraulics",
            description=(
                f"Activate thermal hydraulics calculations using the physics module defined in `{CONF_TH_KERNEL}`"
            ),
        ),
        setting.Setting(
            CONF_TH_KERNEL,
            default="",
            label="Thermal Hydraulics Kernel",
            description="Name of primary T/H solver in this run",
        ),
    ]
    return settings


def defineValidators(inspector):
    return []
