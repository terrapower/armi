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

"""Tests the Interface"""

import unittest
import os

import armi.interfaces as interfaces
from armi.utils import textProcessors
import armi.settings as settings
from armi.tests import TEST_ROOT


class DummyInterface(interfaces.Interface):
    name = "Dummy"


class TestCodeInterface(unittest.TestCase):
    """Test Code interface."""

    def test_isRequestedDetailPoint(self):
        r"""
        Tests notification of detail points.
        """
        cs = settings.Settings()
        cs["dumpSnapshot"] = ["000001", "995190"]
        i = DummyInterface(None, cs)

        self.assertEqual(i.isRequestedDetailPoint(0, 1), True)
        self.assertEqual(i.isRequestedDetailPoint(995, 190), True)
        self.assertEqual(i.isRequestedDetailPoint(5, 10), False)

    def test_enabled(self):
        """Test turning interfaces on and off."""
        i = DummyInterface(None, None)

        self.assertEqual(i.enabled(), True)
        i.enabled(False)
        self.assertEqual(i.enabled(), False)
        i.enabled(True)
        self.assertEqual(i.enabled(), True)


class TestTextProcessor(unittest.TestCase):
    """Test Text processor."""

    def setUp(self):
        self.tp = textProcessors.TextProcessor(os.path.join(TEST_ROOT, "geom.xml"))

    def test_fsearch(self):
        """Test fsearch in re mode."""
        line = self.tp.fsearch("xml")
        self.assertIn("version", line)
        self.assertEqual(self.tp.fsearch("xml"), "")

    def test_fsearch_text(self):
        """Test fsearch in text mode."""
        line = self.tp.fsearch("xml", textFlag=True)
        self.assertIn("version", line)
        self.assertEqual(self.tp.fsearch("xml"), "")


if __name__ == "__main__":
    unittest.main()
