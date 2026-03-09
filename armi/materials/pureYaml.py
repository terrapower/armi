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
A collection of materials that are defined in pure matProps YAML files.

This file exists to wrap pure matProps YAML files so they become full-fledged versions of ``armi.materials.Material``.
The wrappers below are designed so new matProps material objects can be created on the fly, as needed.
"""

import os

from armi.materials.material import Fluid, Material, SimpleSolid

# handle pathing to materials files
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_RESOURCES_DIR = os.path.join(_THIS_DIR, "..", "resources", "materials")


class Air(Fluid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Air.yaml")


class Alloy200(SimpleSolid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Alloy200.yaml")


class Californium(SimpleSolid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Californium.yaml")


class CaH2(SimpleSolid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "CaH2.yaml")


class Concrete(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Concrete.yaml")


class Cu(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Cu.yaml")


class Hafnium(SimpleSolid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Hafnium.yaml")


class Inconel600(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Inconel600.yaml")


class Lead(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Lead.yaml")


class LeadBismuth(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "LeadBismuth.yaml")


class Magnesium(Fluid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Magnesium.yaml")


class Molybdenum(SimpleSolid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Molybdenum.yaml")


class NaCl(SimpleSolid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "NaCl.yaml")


class NZ(SimpleSolid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "NZ.yaml")


class Sodium(Fluid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Sodium.yaml")


class Tantalum(SimpleSolid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Tantalum.yaml")


class TZM(SimpleSolid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "TZM.yaml")


class Void(Fluid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Void.yaml")


class ZnO(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "ZnO.yaml")
