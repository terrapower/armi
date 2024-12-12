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

"""Settings related to the report generation."""

import voluptuous as vol

from armi.settings import setting

CONF_GEN_REPORTS = "genReports"
CONF_ASSEM_POW_SUMMARY = "assemPowSummary"
CONF_SUMMARIZE_ASSEM_DESIGN = "summarizeAssemDesign"
CONF_TIMELINE_INCLUSION_CUTOFF = "timelineInclusionCutoff"


def defineSettings():
    """Define settings for the interface."""
    settings = [
        setting.Setting(
            CONF_GEN_REPORTS,
            default=True,
            label="Enable Reports",
            description="Employ the use of the reporting utility for ARMI, generating "
            "HTML and ASCII summaries of the run",
            oldNames=[("summarizer", None)],
        ),
        setting.Setting(
            CONF_ASSEM_POW_SUMMARY,
            default=False,
            label="Summarize Assembly Power",
            description="Print a summary of how much power is in each assembly "
            "type at every timenode",
        ),
        setting.Setting(
            CONF_SUMMARIZE_ASSEM_DESIGN,
            default=True,
            label="Summarize Assembly Design",
            description="Print a summary of the assembly design details at BOL",
        ),
        setting.Setting(
            CONF_TIMELINE_INCLUSION_CUTOFF,
            default=0.03,
            label="Timer Cutoff",
            description="Timers who are not active for this percent of the run will "
            "not be presented in the timeline graphic",
            schema=vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        ),
    ]
    return settings
