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
"""Test Locationlabel migration"""
import io
import unittest

from armi.settings import caseSettings
from armi.scripts.migration.m0_1_6_locationLabels import (
    ConvertAlphanumLocationSettingsToNum,
)
from armi.settings.settingsIO import SettingsWriter, SettingsReader


class TestMigration(unittest.TestCase):
    def test_locationLabelMigration(self):
        """Make a setting with an old value and make sure it migrates to expected new value."""
        cs = caseSettings.Settings()
        newSettings = {"detailAssemLocationsBOL": ["B1012"]}
        cs = cs.modified(newSettings=newSettings)

        writer = SettingsWriter(cs)
        stream = io.StringIO()
        writer.writeYaml(stream)
        stream.seek(0)

        converter = ConvertAlphanumLocationSettingsToNum(stream=stream)
        newCs = caseSettings.Settings()
        reader = SettingsReader(newCs)
        reader.readFromStream(converter.apply())
        self.assertEqual(newCs["detailAssemLocationsBOL"][0], "011-012")


if __name__ == "__main__":
    nittest.main()
