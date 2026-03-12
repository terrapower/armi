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

from armi.materials.material import Fluid, FuelMaterial, Material, SimpleSolid

# handle pathing to materials files
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_RESOURCES_DIR = os.path.join(_THIS_DIR, "..", "resources", "materials")


class Be9(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Be9.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 1.85


# TODO: Find a better reference for the density of this material, and use that instead of "refDens".
class Graphite(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Graphite.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 1.8888


# TODO: Find a better reference for the density of this material, and use that instead of "refDens".
class HastelloyN(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "HastelloyN.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 8.86


class HT9(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "HT9.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 7.778


# TODO: Find a better reference for the density of this material, and use that instead of "refDens".
class Inconel625(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Inconel625.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 8.44


# TODO: Find a better reference for the density of this material, and use that instead of "refDens".
class Inconel800(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Inconel800.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 7.94


# TODO: Find a better reference for the density of this material, and use that instead of "refDens".
class InconelX750(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "InconelX750.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 8.28


class Lithium(Fluid):
    enrichedNuclide = "LI6"
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Lithium.yaml")


# TODO: Find a better reference for the density of this material, and use that instead of "refDens".
class MgO(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "MgO.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 3.58


# TODO: Find a better reference for the density of this material, and use that instead of "refDens".
class Sc2O3(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Sc2O3.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 3.86


class Thorium(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Thorium.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 11.68


class ThoriumOxide(FuelMaterial, SimpleSolid):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "ThoriumOxide.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 10.0

    def density(self, Tk=None, Tc=None):
        return Material.density(self, Tk, Tc) * self.getTD()


class ThO2(ThoriumOxide):
    """Just another name for ThoriumOxide."""

    pass


class ThU(FuelMaterial):
    enrichedNuclide = "U233"
    YAML_PATH = os.path.join(_RESOURCES_DIR, "ThU.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 11.68


class Uranium(FuelMaterial):
    enrichedNuclide = "U235"
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Uranium.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 19.07

    def pseudoDensity(self, Tk: float = None, Tc: float = None) -> float:
        """2D-expanded density in g/cc."""
        return super().pseudoDensity(Tk=Tk, Tc=Tc) * self.getTD()


class UraniumOxide(FuelMaterial):
    enrichedNuclide = "U235"
    YAML_PATH = os.path.join(_RESOURCES_DIR, "UraniumOxide.yaml")


class UO2(UraniumOxide):
    """Just another name for UraniumOxide."""

    def __init__(self):
        UraniumOxide.__init__(self)
        self._name = "UraniumOxide"


# TODO: Find a better reference for the density of this material, and use that instead of "refDens".
class Y2O3(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Y2O3.yaml")

    def __init__(self):
        Material.__init__(self)
        self.refDens = 5.03


class Zr(Material):
    YAML_PATH = os.path.join(_RESOURCES_DIR, "Zr.yaml")

    def __init__(self):
        Material.__init__(self)
        # AAA Materials Handbook 45803
        self.refDens = 6.569997702553134
        # TODO: https://en.wikipedia.org/wiki/Zirconium
        #       density of metal: 6.505 g/cm, of liquid: 5.8 g/cm3
