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
"""
Modifies inputs related to neutronics controls.

Notes
-----
This may make more sense in the neutronics physics plugin.
"""

from armi.cases.inputModifiers import inputModifiers
from armi.physics.neutronics.settings import (
    CONF_EPS_EIG,
    CONF_EPS_FSAVG,
    CONF_EPS_FSPOINT,
)


class NeutronicConvergenceModifier(inputModifiers.InputModifier):
    """
    Adjust the neutronics convergence parameters ``CONF_EPS_EIG``, ``CONF_EPS_FSAVG``, and
    ``CONF_EPS_FSPOINT``.

    The supplied value is used for ``CONF_EPS_EIG``. ``CONF_EPS_FSAVG`` and ``CONF_EPS_FSPOINT`` are
    set to 100 times the supplied value.

    This can be used to perform sensitivity studies on convergence criteria.
    """

    def __init__(self, value):
        inputModifiers.InputModifier.__init__(self, {self.__class__.__name__: value})
        self.value = value
        if value > 1e-2 or value <= 0.0:
            raise ValueError(
                f"Neutronic convergence modifier value must be greater than 0 and less than 1e-2 (got {value})"
            )

    def __call__(self, cs, bp):
        newSettings = {}
        newSettings[CONF_EPS_FSAVG] = self.value * 100
        newSettings[CONF_EPS_FSPOINT] = self.value * 100
        newSettings[CONF_EPS_EIG] = self.value
        cs = cs.modified(newSettings=newSettings)

        return cs, bp


class NeutronicMeshsSizeModifier(inputModifiers.InputModifier):
    """
    Adjust the neutronics mesh in all assemblies by a multiplication factor.

    This can be useful when switching between nodal and finite difference approximations, or when
    doing mesh convergence sensitivity studies.

    Attributes
    ----------
    multFactor : int
        Factor to multiply the number of axial mesh points per block by.
    """

    def __init__(self, multFactor):
        inputModifiers.InputModifier.__init__(self, {self.__class__.__name__: multFactor})
        if not isinstance(multFactor, int):
            raise TypeError("multFactor must be an integer, but got {}".format(multFactor))
        self.multFactor = multFactor

    def __call__(self, cs, bp):
        for assemDesign in bp.assemDesigns:
            assemDesign.axialMeshPoints = [ax * self.multFactor for ax in assemDesign.axialMeshPoints]

        return cs, bp
