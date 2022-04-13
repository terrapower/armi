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

"""Tests for the App class."""

import copy
import unittest

import armi
from armi import plugins
from armi.__main__ import main


class TestPlugin1(plugins.ArmiPlugin):
    """This should be fine on its own"""

    @staticmethod
    @plugins.HOOKIMPL
    def defineParameterRenames():
        return {"oldType": "type"}


class TestPlugin2(plugins.ArmiPlugin):
    """This should lead to an error if it coexists with Plugin1."""

    @staticmethod
    @plugins.HOOKIMPL
    def defineParameterRenames():
        return {"oldType": "type"}


class TestPlugin3(plugins.ArmiPlugin):
    """This should lead to errors, since it collides with the framework `type` param."""

    @staticmethod
    @plugins.HOOKIMPL
    def defineParameterRenames():
        return {"type": "newType"}


class TestPlugin4(plugins.ArmiPlugin):
    """This should be fine on its own, and safe to merge with TestPlugin1. And would
    make for a pretty good rename IRL.
    """

    @staticmethod
    @plugins.HOOKIMPL
    def defineParameterRenames():
        return {"arealPD": "arealPowerDensity"}


class TestApps(unittest.TestCase):
    """Test the base apps.App interfaces."""

    def setUp(self):
        """Manipulate the standard App. We can't just configure our own, since the
        pytest environment bleeds between tests :("""
        self._backupApp = copy.deepcopy(armi._app)

    def tearDown(self):
        """Restore the App to its original state"""
        armi._app = self._backupApp
        armi.context.APP_NAME = "armi"

    def test_getParamRenames(self):
        app = armi.getApp()
        app.pluginManager.register(TestPlugin1)
        app.pluginManager.register(TestPlugin4)
        app._paramRenames = None  # need to implement better cache invalidation rules

        renames = app.getParamRenames()
        self.assertIn("oldType", renames)
        self.assertEqual(renames["oldType"], "type")

        self.assertIn("arealPD", renames)
        self.assertEqual(renames["arealPD"], "arealPowerDensity")

        app.pluginManager.register(TestPlugin2)
        app._paramRenames = None  # need to implement better cache invalidation rules
        with self.assertRaisesRegex(
            plugins.PluginError,
            ".*parameter renames are already defined by another plugin.*",
        ):
            app.getParamRenames()
        app.pluginManager.unregister(TestPlugin2)

        app.pluginManager.register(TestPlugin3)
        with self.assertRaisesRegex(
            plugins.PluginError, ".*currently-defined parameters.*"
        ):
            app.getParamRenames()

    def test_version(self):
        app = armi.getApp()
        ver = app.version
        self.assertEqual(ver, armi.meta.__version__)

    def test_getSettings(self):
        app = armi.getApp()
        settings = app.getSettings()

        self.assertGreater(len(settings), 100)
        self.assertEqual(settings["numProcessors"].value, 1)
        self.assertEqual(settings["nCycles"].value, 1)

    def test_splashText(self):
        app = armi.getApp()
        splash = app.splashText
        self.assertIn("========", splash)
        self.assertIn("Advanced", splash)
        self.assertIn("version", splash)
        self.assertIn(armi.meta.__version__, splash)

    def test_splashTextDifferentApp(self):
        app = armi.getApp()
        name = "DifferentApp"
        app.name = name
        armi._app = app
        armi.context.APP_NAME = name

        splash = app.splashText
        self.assertIn("========", splash)
        self.assertIn("Advanced", splash)
        self.assertIn("version", splash)
        self.assertIn(armi.meta.__version__, splash)
        self.assertIn("DifferentApp", splash)


class TestArmi(unittest.TestCase):
    """Tests for functions in the ARMI __init__ module."""

    def test_getDefaultPlugMan(self):
        from armi import cli

        pm = armi.getDefaultPluginManager()
        pm2 = armi.getDefaultPluginManager()

        self.assertTrue(pm is not pm2)
        self.assertIn(cli.EntryPointsPlugin, pm.get_plugins())

    def test_overConfigured(self):
        with self.assertRaises(RuntimeError):
            armi.configure()

    def test_main(self):
        with self.assertRaises(SystemExit):
            main()
