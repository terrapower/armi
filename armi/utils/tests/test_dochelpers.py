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
"""Tests for documentation helpers"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import unittest

from armi.reactor import reactors
from armi.reactor import reactorParameters
from armi.utils.dochelpers import (
    create_figure,
    create_table,
    generateParamTable,
    generatePluginSettingsTable,
)


class TestDocHelpers(unittest.TestCase):
    """Tests for the utility dochelpers functions."""

    def test_paramTable(self):

        table = generateParamTable(
            reactors.Core,
            reactorParameters.defineCoreParameters(),
        )
        self.assertIn("keff", table)
        self.assertNotIn("notAParameter", table)

    def test_settingsTable(self):
        from armi.settings.fwSettings import globalSettings

        table = generatePluginSettingsTable(
            globalSettings.defineSettings(),
            "Framework",
        )
        self.assertIn("numProcessors", table)
        self.assertNotIn("notASetting", table)

    def test_createFigure(self):
        rst = create_figure(
            "/path/to/thing.png",
            caption="caption1",
            align="right",
            alt="test1",
            width=300,
        )

        self.assertEqual(len(rst), 6)
        self.assertIn("thing.png", rst[0])
        self.assertIn("right", rst[1])
        self.assertIn("test1", rst[2])
        self.assertIn("width", rst[3])
        self.assertIn("caption1", rst[5])

    def test_createTable(self):
        rst = "some\nthing"
        table = create_table(
            rst, caption="awesomeTable", align="left", widths=[200, 300], width=250
        )

        self.assertEqual(len(table), 100)
        self.assertIn("awesomeTable", table)
        self.assertIn("width: 250", table)
        self.assertIn("widths: [200, 300]", table)
        self.assertIn("thing", table)


if __name__ == "__main__":
    unittest.main()
