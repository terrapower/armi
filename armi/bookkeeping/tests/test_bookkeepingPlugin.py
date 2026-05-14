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

from armi.bookkeeping import BookkeepingPlugin, summarizeMaterialData
from armi.testing import loadTestReactor
from armi.tests import mockRunLogs
from armi.tests.test_plugins import TestPlugin


class TestBookkeepingPlugin(TestPlugin):
    plugin = BookkeepingPlugin


class TestBookkeepingPluginHooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.r = loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")

    def test_materialDataSummary(self):
        """Test that the material data summary for the core is valid as a printout to the stdout."""
        expectedMaterialData = [
            ("HT9", "ARMI"),
            ("Sodium", "ARMI"),
            ("UZr", "ARMI"),
        ]
        materialData = summarizeMaterialData(self.r.core)
        for actual, expected in zip(materialData, expectedMaterialData):
            self.assertEqual(actual, expected)

    def test_bookkeepingOnProcessCoreLoading(self):
        """Test that the onProcessCoreLoading plugin hook operates properly."""
        with mockRunLogs.BufferLog() as mock:
            BookkeepingPlugin.onProcessCoreLoading(self.r.core, None, None)
            self.assertIn("Summarizing Source of Material Data for", mock.getStdout())
            self.assertIn("Material Name    Source Location", mock.getStdout())
            self.assertIn("UZr              ARMI", mock.getStdout())
