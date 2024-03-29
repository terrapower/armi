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
Void material.

Use this to fill empty spaces while maintaining proper volume fractions.
"""
from armi.materials import material


class Void(material.Fluid):
    """A Void material is a bookkeeping material with zero density.

    .. impl:: Define a void material with zero density.
        :id: I_ARMI_MAT_VOID
        :implements: R_ARMI_MAT_VOID

        To help with expansion, it is sometimes useful to put a small section of void
        material into the reactor model. This is not meant to represent a true void,
        that would cause negative pressure in a system, but just as a bookkeeping tool.
        Sometimes this helps users define the geometry of an expanding and conctracting
        reactor. It is called a "void" because it has zero density at all temperatures.
    """

    def pseudoDensity(self, Tk: float = None, Tc: float = None) -> float:
        return 0.0

    def density(self, Tk: float = None, Tc: float = None) -> float:
        return 0.0
