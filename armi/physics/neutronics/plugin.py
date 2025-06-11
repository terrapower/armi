# Copyright 2025 TerraPower, LLC
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
A boilerplate entry for a neutronics physics plugin.

The ARMI Framework comes with a neutronics plugin that introduces two independent interfaces:

:py:mod:`~armi.physics.neutronics.fissionProductModel`
    Handles fission product modeling

:py:mod:`~armi.physics.neutronics.crossSectionGroupManager`
    Handles the management of different cross section "groups"
"""

import numpy as np

from armi import plugins, runLog
from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.utils import tabulate


class NeutronicsPlugin(plugins.ArmiPlugin):
    """The built-in neutronics plugin with a few capabilities and a lot of state parameter definitions."""

    @staticmethod
    @plugins.HOOKIMPL
    def exposeInterfaces(cs):
        """Collect and expose all of the interfaces that live under the built-in neutronics package."""
        from armi.physics.neutronics import crossSectionGroupManager
        from armi.physics.neutronics.fissionProductModel import fissionProductModel

        interfaceInfo = []
        for mod in (crossSectionGroupManager, fissionProductModel):
            interfaceInfo += plugins.collectInterfaceDescriptions(mod, cs)

        return interfaceInfo

    @staticmethod
    @plugins.HOOKIMPL
    def defineParameters():
        """Define parameters for the plugin."""
        from armi.physics.neutronics import parameters as neutronicsParameters

        return neutronicsParameters.getNeutronicsParameterDefinitions()

    @staticmethod
    @plugins.HOOKIMPL
    def defineParameterRenames():
        return {"buGroup": "envGroup", "buGroupNum": "envGroupNum"}

    @staticmethod
    @plugins.HOOKIMPL
    def defineEntryPoints():
        """Define entry points for the plugin."""
        from armi.physics.neutronics import diffIsotxs

        entryPoints = [diffIsotxs.CompareIsotxsLibraries]

        return entryPoints

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        """Define settings for the plugin."""
        from armi.physics.neutronics import crossSectionSettings
        from armi.physics.neutronics import settings as neutronicsSettings
        from armi.physics.neutronics.fissionProductModel import (
            fissionProductModelSettings,
        )

        settings = [
            crossSectionSettings.XSSettingDef(
                CONF_CROSS_SECTION,
            )
        ]
        settings += neutronicsSettings.defineSettings()
        settings += fissionProductModelSettings.defineSettings()

        return settings

    @staticmethod
    @plugins.HOOKIMPL
    def defineSettingsValidators(inspector):
        """Implementation of settings inspections for neutronics settings."""
        from armi.physics.neutronics.fissionProductModel.fissionProductModelSettings import (
            getFissionProductModelSettingValidators,
        )
        from armi.physics.neutronics.settings import getNeutronicsSettingValidators

        settingsValidators = getNeutronicsSettingValidators(inspector)
        settingsValidators.extend(getFissionProductModelSettingValidators(inspector))
        return settingsValidators

    @staticmethod
    @plugins.HOOKIMPL
    def onProcessCoreLoading(core, cs, dbLoad):
        """Called whenever a Core object is newly built."""
        applyEffectiveDelayedNeutronFractionToCore(core, cs)

    @staticmethod
    @plugins.HOOKIMPL
    def getReportContents(r, cs, report, stage, blueprint):
        """Generates the Report Content for the Neutronics Report."""
        from armi.physics.neutronics import reports

        return reports.insertNeutronicsReport(r, cs, report, stage)


def applyEffectiveDelayedNeutronFractionToCore(core, cs):
    """Process the settings for the delayed neutron fraction and precursor decay constants."""
    # Verify and set the core beta parameters based on the user-supplied settings
    beta = cs["beta"]
    decayConstants = cs["decayConstants"]

    # If beta is interpreted as a float, then assign it to the total delayed neutron fraction
    # parameter. Otherwise, setup the group-wise delayed neutron fractions and precursor decay
    # constants.
    reportTableData = []
    if isinstance(beta, float):
        core.p.beta = beta
        reportTableData.append(("Total Delayed Neutron Fraction", core.p.beta))

    elif isinstance(beta, list) and isinstance(decayConstants, list):
        if len(beta) != len(decayConstants):
            raise ValueError(
                f"The values for `beta` ({beta}) and `decayConstants` ({decayConstants}) are not consistent lengths."
            )

        core.p.beta = sum(beta)
        core.p.betaComponents = np.array(beta)
        core.p.betaDecayConstants = np.array(decayConstants)

        reportTableData.append(("Total Delayed Neutron Fraction", core.p.beta))
        for i, betaComponent in enumerate(core.p.betaComponents):
            reportTableData.append((f"Group {i} Delayed Neutron Fractions", betaComponent))
        for i, decayConstant in enumerate(core.p.betaDecayConstants):
            reportTableData.append(("Group {i} Precursor Decay Constants", decayConstant))

    # Report to the user the values were not applied.
    if not reportTableData and (beta is not None or decayConstants is not None):
        runLog.warning(
            f"Delayed neutron fraction(s) - {beta} and decay constants - {decayConstants} have not been applied."
        )
    else:
        runLog.extra(
            tabulate.tabulate(
                data=reportTableData,
                headers=["Component", "Value"],
                tableFmt="armi",
            )
        )
