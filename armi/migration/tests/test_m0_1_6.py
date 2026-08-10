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
"""Test Locationlabel migration."""

import io
import unittest

from armi.migration.m0_1_3 import RemoveCentersFromBlueprints, UpdateElementalNuclides
from armi.migration.m0_1_6 import ConvertAlphanumLocationSettingsToNum
from armi.migration.m0_7_0 import UpdateAmericium242
from armi.settings import caseSettings
from armi.settings.settingsIO import SettingsReader, SettingsWriter


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

    def test_noMigrationIfVersion(self):
        """
        Ensure that no migration happens if the version of the DB is newer than the migration 'toVersion'.

        This test checks the specific case of `ConvertAlphanumLocationSettingsToNum`, which should only be applied until
        v0.1.7.
        """
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
        reader.readFromStream(converter.apply(version="0.6.4"))
        self.assertEqual(newCs["detailAssemLocationsBOL"][0], "B1012")

    def test_removeCentersFromBlueprints(self):
        # RemoveCentersFromBlueprints
        pass

    def test_updateElementalNuclides(self):
        # UpdateElementalNuclides
        pass

    def test_updateAmericium242(self):
        # mock up a partial blueprint
        bpText = """
nulide flags:
  CM244: {burn: false, xs: true, expandTo: []}
  CM242: {burn: false, xs: true, expandTo: []}
  AM242: {burn: false, xs: true, expandTo: []}
  CM245: {burn: false, xs: true, expandTo: []}
  CM243: {burn: false, xs: true, expandTo: []}
"""
        # run the UpdateAmericium242 migration
        stream = io.StringIO(bpText)
        converter = UpdateAmericium242(stream=stream)
        newStream = converter.apply(version="0.7.0")
        outText = newStream.read()

        print(outText)

        # validate migration
        self.assertIn("AM242M:", outText)
        self.assertNotIn("AM242:", outText)
        self.assertIn("CM244:", outText)
        self.assertIn("CM243:", outText)
        
