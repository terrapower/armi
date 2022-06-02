# Copyright 2022 TerraPower, LLC
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

"""Tests for the UserPlugin class."""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import copy
import unittest

from armi import context
from armi import getApp
from armi import plugins
from armi import utils


class UserPluginFlags(plugins.UserPlugin):
    """Simple UserPlugin that defines a single, new flag."""

    def defineFlags():
        return {"FANCY": utils.flags.auto()}


class TestUserPlugins(unittest.TestCase):
    def setUp(self):
        """
        Manipulate the standard App. We can't just configure our own, since the
        pytest environment bleeds between tests.
        """
        self._backupApp = copy.deepcopy(getApp())

    def tearDown(self):
        """Restore the App to its original state"""
        import armi

        armi._app = self._backupApp
        context.APP_NAME = "armi"

    def test_userPluginsFlags(self):
        # a basic test of the method
        app = getApp()
        self.assertEqual(app.pluginManager.counter, 8)
        app.pluginManager.register(UserPluginFlags)
        self.assertEqual(app.pluginManager.counter, 9)
