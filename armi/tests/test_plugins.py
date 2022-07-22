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
import os
import pathlib
import unittest
from typing import Optional

import yamlize

from armi import interfaces
from armi import plugins
from armi import settings
from armi.bookkeeping.tests._constants import TUTORIAL_FILES
from armi.bookkeeping.tests.test_historyTracker import runTutorialNotebook
from armi.cases import case
from armi.context import ROOT
from armi.reactor.flags import Flags
from armi.tests import ArmiTestHelper
from armi.utils.directoryChangers import TemporaryDirectoryChanger

CASE_TITLE = "anl-afci-177"
TUTORIAL_DIR = os.path.join(ROOT, "tests", "tutorials")


class TestPluginAfterLoadDB(plugins.ArmiPlugin):
    """Toy Plugin, used to test the afterLoadDB hook"""

    @staticmethod
    @plugins.HOOKIMPL
    def afterLoadDB(core, cs):
        for b in core.getBlocks(Flags.FUEL):
            b.p.power += 1.0


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
            self.assertEqual(len(result), 3)
            self.assertIsInstance(result[0], str)
            self.assertIsInstance(result[1], yamlize.Attribute)
            self.assertTrue(callable(result[2]))

    def test_exposeInterfaces(self):
        """Make sure that the exposeInterfaces hook is properly implemented"""
        if self.plugin is None:
            return

        cs = settings.getMasterCs()
        results = self.plugin.exposeInterfaces(cs)
        if results is None or not results:
            return

        # each plugin should return a list
        self.assertIsInstance(results, list)
        for result in results:
            # Make sure that all elements in the list satisfy the constraints of the
            # hookspec
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 3)

            order, interface, kwargs = result

            self.assertIsInstance(order, (int, float))
            self.assertTrue(issubclass(interface, interfaces.Interface))
            self.assertIsInstance(kwargs, dict)


class TestPluginsNeedDB(ArmiTestHelper):
    """This test class provides test plugins a realistic ARMI DB file to act upon."""

    @classmethod
    def setUpClass(cls):
        # We need to be in the TUTORIAL_DIR so that for `filesToMove` to work right.
        os.chdir(TUTORIAL_DIR)

        # Do this work in a temp dir, to avoid race conditions.
        cls.dirChanger = TemporaryDirectoryChanger(filesToMove=TUTORIAL_FILES)
        cls.dirChanger.__enter__()
        runTutorialNotebook()

    @classmethod
    def tearDownClass(cls):
        cls.dirChanger.__exit__(None, None, None)

    def setUp(self):
        cs = settings.Settings(f"{CASE_TITLE}.yaml")
        newSettings = {}
        newSettings["db"] = True
        newSettings["detailAssemLocationsBOL"] = ["001-001"]
        newSettings["loadStyle"] = "fromDB"
        newSettings["reloadDBName"] = pathlib.Path(f"{CASE_TITLE}.h5").absolute()
        newSettings["startNode"] = 1
        cs = cs.modified(newSettings=newSettings)

        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

        c = case.Case(cs)
        case2 = c.clone(title="armiRun")
        settings.setMasterCs(case2.cs)
        self.o = case2.initializeOperator()
        self.r = self.o.r

        self.o.getInterface("main").interactBOL()

    def tearDown(self):
        self.o.getInterface("database").database.close()
        self.r = None
        self.o = None
        self.td.__exit__(None, None, None)

    def test_afterLoadDB(self):
        r"""
        Test the afterLoadDB hook works

        Notes
        -----
        This test *assumes* the ``afterLoadDB()`` hook takes place at the end of
        the ``DBI.loadState()`` method. We are not here to test that plugin hooks
        work, but that this one in particular can affect the ``Reactor`` state.
        """
        # Get to the database state at the end of stack of time node 1.
        dbi = self.o.getInterface("database")
        dbi.loadState(0, 1)

        bFuels = self.r.core.getBlocks(Flags.FUEL)
        power = sum([b.p.power for b in bFuels])
        self.assertEqual(power, 0.0)

        plugin = TestPluginAfterLoadDB()
        plugin.afterLoadDB(self.r.core, self.o.cs)

        bFuels = self.r.core.getBlocks(Flags.FUEL)
        powers = [b.p.power for b in bFuels]
        self.assertEqual(sum(powers), len(powers))


if __name__ == "__main__":
    unittest.main()
