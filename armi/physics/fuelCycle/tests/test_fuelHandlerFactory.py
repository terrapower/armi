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

"""Tests for :mod:`armi.physics.fuelCycle.fuelHandlerFactory`."""

import unittest
from pathlib import Path

from armi.physics.fuelCycle import fuelHandlerFactory
from armi.physics.fuelCycle.settings import CONF_FUEL_HANDLER_NAME, CONF_SHUFFLE_LOGIC


class _DummySettings(dict):
    """Minimal stand-in for :class:`armi.settings.Settings`."""


class _DummyOperator:
    """Operator stub that only exposes the settings object."""

    def __init__(self, settings):
        self.cs = settings


class FuelHandlerFactoryTests(unittest.TestCase):
    """Exercise the custom module import logic."""

    def setUp(self):
        self.inputDirectory = Path(__file__).resolve().parents[3]
        self.settings = _DummySettings()
        self.settings.inputDirectory = str(self.inputDirectory)
        self.operator = _DummyOperator(self.settings)

    def test_filePath(self):
        """Custom handlers can still be loaded from explicit file paths."""
        modulePath = Path(__file__).resolve().with_name("_customFuelHandlerModule.py")
        self.settings.update(
            {
                CONF_FUEL_HANDLER_NAME: "FileFuelHandler",
                CONF_SHUFFLE_LOGIC: str(modulePath),
            }
        )

        handler = fuelHandlerFactory.fuelHandlerFactory(self.operator)

        self.assertEqual(handler.__class__.__name__, "FileFuelHandler")

    def test_modulePath(self):
        """Module-style paths are imported using :mod:`importlib`."""
        moduleName = "armi.physics.fuelCycle.tests._customFuelHandlerModule"
        self.settings.update(
            {
                CONF_FUEL_HANDLER_NAME: "ModuleFuelHandler",
                CONF_SHUFFLE_LOGIC: moduleName,
            }
        )

        handler = fuelHandlerFactory.fuelHandlerFactory(self.operator)

        from armi.physics.fuelCycle.tests import _customFuelHandlerModule

        self.assertIsInstance(handler, _customFuelHandlerModule.ModuleFuelHandler)


if __name__ == "__main__":
    unittest.main()
