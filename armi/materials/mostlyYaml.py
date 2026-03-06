# Copyright 2026 TerraPower, LLC
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
A collection of materials that are mostly purely defined in matProps YAML files.

This file exists to wrap pure matProps YAML files so they become full-fledged versions of ``armi.materials.Material``.
The wrappers below are designed so new matProps material objects can be created on the fly, as needed.
"""

import os

from armi.materials.material import Material

# handle pathing to materials files
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_RESOURCES_DIR = os.path.join(_THIS_DIR, "..", "resources", "materials")


class Cu(Material):
    """Copper metal."""

    YAML_PATH = os.path.join(_RESOURCES_DIR, "Cu.yaml")

    def setDefaultMassFracs(self):
        self.setMassFrac("CU63", 0.6915)
        self.setMassFrac("CU65", 0.3085)


class Inconel600(Material):
    """Inconel600 - nickle chromium alloy."""

    YAML_PATH = os.path.join(_RESOURCES_DIR, "Inconel600.yaml")

    def setDefaultMassFracs(self):
        self.refDens = 8.47  # g/cc

        # TODO: Is it possible to support nuclides like this? That would really help.
        self.setMassFrac("NI", 0.7541)
        self.setMassFrac("CR", 0.1550)
        self.setMassFrac("FE", 0.0800)
        self.setMassFrac("C", 0.0008)
        self.setMassFrac("MN55", 0.0050)
        self.setMassFrac("S", 0.0001)
        self.setMassFrac("SI", 0.0025)
        self.setMassFrac("CU", 0.0025)
