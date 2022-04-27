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

"""Provides functionality for testing implementations of plugins"""
import unittest
from typing import Optional

import yamlize

from armi import interfaces
from armi import plugins
from armi import settings


class TestPlugin(unittest.TestCase):
    """This contains some sanity tests that can be used by implementing plugins"""

    plugin: Optional[plugins.ArmiPlugin] = None

    def test_defineBlueprintsSections(self):
        """Make sure that the defineBlueprintsSections hook is properly implemented"""
        if self.plugin is None:
            return
        if not hasattr(self.plugin, "defineBlueprintsSections"):
            return

        results = self.plugin.defineBlueprintsSections()
        if results is None:
            return

        # each plugin should return a list
        self.assertIsInstance(results, (list, type(None)))

        for result in results:
            self.assertIsInstance(result, tuple)
            self.assertTrue(len(result) == 3)
            self.assertIsInstance(result[0], str)
            self.assertIsInstance(result[1], yamlize.Attribute)
            self.assertTrue(callable(result[2]))

    def test_exposeInterfaces(self):
        """Make sure that the exposeInterfaces hook is properly implemented"""
        if self.plugin is None:
            return
        if not hasattr(self.plugin, "exposeInterfaces"):
            return

        cs = settings.getMasterCs()
        results = self.plugin.exposeInterfaces(cs)
        # each plugin should return a list
        self.assertIsInstance(results, list)
        for result in results:
            # Make sure that all elements in the list satisfy the constraints of the
            # hookspec
            self.assertIsInstance(result, tuple)
            self.assertTrue(len(result) == 3)

            order, interface, kwargs = result

            self.assertIsInstance(order, (int, float))
            self.assertTrue(issubclass(interface, interfaces.Interface))
            self.assertIsInstance(kwargs, dict)


if __name__ == "__main__":
    unittest.main()
