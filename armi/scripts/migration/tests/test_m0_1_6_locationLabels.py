"""Test Locationlabel migration"""
import unittest
import io

from armi.settings import caseSettings
from armi.scripts.migration.m0_1_6_locationLabels import (
    ConvertAlphanumLocationSettingsToNum,
)
from armi.settings.settingsIO import SettingsWriter, SettingsReader


class TestMigration(unittest.TestCase):
    def testLocationLabelMigration(self):
        """Make a setting with an old value and make sure it migrates to expected new value."""
        cs = caseSettings.Settings()
        cs["detailAssemLocationsBOL"] = ["B1012"]
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
    unittest.main()
