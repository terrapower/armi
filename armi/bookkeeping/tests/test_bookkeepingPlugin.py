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

"""Test Bookkeeping Plugin."""

import unittest

from armi import settings
from armi.bookkeeping import BookkeepingPlugin, summarizeMaterialData
from armi.reactor import blueprints, reactors
from armi.reactor.blueprints import gridBlueprint, reactorBlueprint
from armi.reactor.blueprints.tests import test_customIsotopics
from armi.tests import TEST_ROOT, mockRunLogs
from armi.tests.test_plugins import TestPlugin

CORE_BLUEPRINT = """
core:
  grid name: core
  origin:
    x: 0.0
    y: 10.1
    z: 1.1
"""
GRIDS = """
core:
    geom: hex
    symmetry: third core periodic
    grid contents:
      [0, 0]: IC
      [1, 1]: IC
    orientationBOL:
      [1, 1]: 60.0
      [3, 2]: 120.0
"""

class TestBookkeepingPlugin(TestPlugin):
    plugin = BookkeepingPlugin

class TestBookkeepingPlugin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Create a reactor core with case settings, blueprints, reactor"""
        # TODO: Just copied over old test setup b/c I assume this is a much smaller reactor than the test reactors.
        # But this may be simplifiable via test reactor.
        cs = settings.Settings()
        bp = blueprints.Blueprints.load(test_customIsotopics.TestCustomIsotopics.yamlString)
        bp.systemDesigns = reactorBlueprint.Systems.load(CORE_BLUEPRINT)
        bp.gridDesigns = gridBlueprint.Grids.load(GRIDS)
        reactor = reactors.Reactor(cs.caseTitle, bp)
        cls.core = bp.systemDesigns["core"].construct(cs, bp, reactor)

    def test_materialDataSummary(self):
        """Test that the material data summary for the core is valid as a printout to the stdout."""
        expectedMaterialData = [
            ("Custom", "ARMI"),
            ("HT9", "ARMI"),
            ("Sodium", "ARMI"),
            ("UZr", "ARMI"),
        ]
        materialData = summarizeMaterialData(self.core)
        for actual, expected in zip(materialData, expectedMaterialData):
            self.assertEqual(actual, expected)

    def test_bookkeepingOnProcessCoreLoading(self):
        """Test that the onProcessCoreLoading plugin hook operates properly."""
        with mockRunLogs.BufferLog() as mock:
            BookkeepingPlugin.onProcessCoreLoading(self.core, None, None)
            self.assertIn("Summarizing Source of Material Data for", mock.getStdout())
            self.assertIn("Material Name    Source Location", mock.getStdout())
            self.assertIn("UZr              ARMI", mock.getStdout())


