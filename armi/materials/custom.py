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
Custom materials are ones that you can specify all the number densities yourself.

Useful for benchmarking when you have a particular specified material density.
Use the isotopic input described in :doc:`/user/inputs/blueprints`.

The density function gets applied from custom isotopics by
:py:meth:`armi.reactor.blueprints.isotopicOptions.CustomIsotopic.apply`.
"""
from armi.materials.material import Material


class Custom(Material):
    """
    Custom Materials have user input properties.
    """

    name = "Custom Material"
    enrichedNuclide = "U235"

    def __init__(self):
        """
        During construction, set default density to 1.0. That way,
        people can set number densities without having to set
        a density and it will work. This will generally be overwritten in practice
        by a constant user-input density.
        """
        Material.__init__(self)
        self.customDensity = 1.0

    def pseudoDensity(self, Tk=None, Tc=None):
        r"""
        The density value is set in the loading input.

        In some cases it needs to be set after full core assemblies are populated (e.g. for
        CustomLocation materials), so the missing density warning will appear no matter
        what.
        """
        return self.customDensity

    def setMassFrac(self, *args, **kwargs):
        if self.customDensity == 1.0:
            raise ValueError(
                "Cannot set mass fractions on Custom materials unless a density "
                "is defined."
            )
        Material.setMassFrac(self, *args, **kwargs)
