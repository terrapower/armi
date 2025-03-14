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

"""Module for general core parameter sweeps."""

from armi.physics.neutronics.settings import (
    CONF_EPS_EIG,
    CONF_EPS_FSAVG,
    CONF_EPS_FSPOINT,
)
from armi.reactor.converters.geometryConverters import GeometryConverter


class ParameterSweepConverter(GeometryConverter):
    """Abstract parameter sweep converter object."""

    PRIORITY = None

    def __init__(self, cs, parameter):
        GeometryConverter.__init__(self, cs)
        self._parameter = parameter

    def convert(self, r=None):
        self._sourceReactor = r


class SettingsModifier(ParameterSweepConverter):
    """Modifies basic setting parameters."""

    def __init__(self, cs, settingToModify, parameter):
        ParameterSweepConverter.__init__(self, cs, parameter)
        self.modifier = settingToModify

    def convert(self, r=None):
        ParameterSweepConverter.convert(self, r)
        sType = self._cs.getSetting(self.modifier).underlyingType
        if sType is not type(None):
            # NOTE: this won't work with "new-style" settings related to the plugin system.
            # Using the type of the setting._default may be more appropriate if there are issues.
            self._cs = self._cs.modified(newSettings={self.modifier: sType(self._parameter)})


class NeutronicConvergenceModifier(ParameterSweepConverter):
    """Adjusts the neutronics convergence parameters."""

    def convert(self, r=None):
        ParameterSweepConverter.convert(self, r)
        fs = 1.0e-12 + self._parameter * 1.0e-3

        newSettings = {}
        newSettings[CONF_EPS_FSAVG] = fs
        newSettings[CONF_EPS_FSPOINT] = fs
        newSettings[CONF_EPS_EIG] = 1.0e-14 + self._parameter * 1.0e-4

        self._cs = self._cs.modified(newSettings=newSettings)
