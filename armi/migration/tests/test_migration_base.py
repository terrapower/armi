# Copyright 2023 TerraPower, LLC
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
"""Test base migration classes."""

import os
import unittest

from armi.migration.base import DatabaseMigration, Migration, SettingsMigration
from armi.testing import TESTING_ROOT


class MockMigration1(Migration):
    """Migration defined for unit tests only."""

    @property
    def fromVersion(self):
        return "0.2.3"

    @property
    def toVersion(self):
        return "0.6.4"

    def _applyToStream(self):
        pass


class MockSettingsMigration1(SettingsMigration):
    """SettingsMigration defined for unit tests only."""

    @property
    def fromVersion(self):
        return "0.1.2"

    @property
    def toVersion(self):
        return "0.3.4"

    def _applyToStream(self):
        pass


class BrokenDatabaseMigration1(DatabaseMigration):
    """For testing purposes only, fromVersion and toVersion are invalid."""

    @property
    def fromVersion(self):
        return "0.7.0"

    @property
    def toVersion(self):
        return "0.6.4"

    def _applyToStream(self):
        pass


class TestMigrationBases(unittest.TestCase):
    def test_basicValidation(self):
        with self.assertRaises(RuntimeError):
            _m = MockMigration1(None, None)

        with self.assertRaises(RuntimeError):
            _m = MockMigration1("fake_stream", "fake_path")

        MockMigration1("fake_stream", None)
        m = MockMigration1(None, "fake_path")
        with self.assertRaises(ValueError):
            m._loadStreamFromPath()

        with self.assertRaises(ValueError):
            _m = BrokenDatabaseMigration1(None, "fake_path")


class TestSettingsMigration(unittest.TestCase):
    def test_loadStreamFromPath(self):
        file_path = os.path.join(TESTING_ROOT, "reactors", "sodiumHexReactor", "armiRun.yaml")
        m = MockSettingsMigration1(None, file_path)
        m._loadStreamFromPath()
        self.assertIsNotNone(m.stream)
