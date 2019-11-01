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

import unittest

from armi.bookkeeping import snapshotInterface
from armi import settings


class TestSnapshotInterface(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.cs = settings.Settings()

    def setUp(self):
        self.cs.revertToDefaults()
        self.si = snapshotInterface.SnapshotInterface(None, self.cs)

    def test_activeateDefaultSnapshots_30cycles2BurnSteps(self):
        self.assertEqual([], self.cs["dumpSnapshot"])
        self.cs["nCycles"] = 30
        self.cs["burnSteps"] = 2
        self.si.activateDefaultSnapshots()
        self.assertEqual(["000000", "014000", "029002"], self.cs["dumpSnapshot"])

    def test_activeateDefaultSnapshots_17cycles5BurnSteps(self):
        self.assertEqual([], self.cs["dumpSnapshot"])
        self.cs["nCycles"] = 17
        self.cs["burnSteps"] = 5
        self.si.activateDefaultSnapshots()
        self.assertEqual(["000000", "008000", "016005"], self.cs["dumpSnapshot"])


if __name__ == "__main__":
    unittest.main()
