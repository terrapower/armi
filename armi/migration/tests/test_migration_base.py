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

from armi.migration.base import Migration, SettingsMigration
from armi.tests import TEST_ROOT


class TestMigrationBases(unittest.TestCase):
    def test_basic_validation(self):
        with self.assertRaises(RuntimeError):
            _m = Migration(None, None)

        with self.assertRaises(RuntimeError):
            _m = Migration("fake_stream", "fake_path")

        Migration("fake_stream", None)
        m = Migration(None, "fake_path")
        with self.assertRaises(ValueError):
            m._loadStreamFromPath()


class TestSettingsMigration(unittest.TestCase):
    def test_loadStreamFromPath(self):
        file_path = os.path.join(TEST_ROOT, "armiRun.yaml")
        m = SettingsMigration(None, file_path)
        m._loadStreamFromPath()
        self.assertIsNotNone(m.stream)
