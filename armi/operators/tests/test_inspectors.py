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

"""
Tests for settings validation system.
"""
import unittest

from armi import settings
from armi import operators


class Test(unittest.TestCase):
    """Test case"""

    def setUp(self):
        self.cs = settings.Settings()
        self.inspector = operators.getOperatorClassFromSettings(self.cs).inspector(
            self.cs
        )
        self.inspector.queries = []  # clear out the auto-generated ones

    def tearDown(self):
        pass

    def test_query(self):
        buh = {1: 2, 3: 4}

        def defdef(x, y, z):
            x[y] = z

        self.inspector.addQuery(
            lambda: buh[1] == 2,
            "beepbopboopbeep",
            "bonkbonk",
            lambda: defdef(buh, 1, 10),
        )
        query = self.inspector.queries[0]
        if query:
            query.correction()
        self.assertEqual(buh[1], 10)
        self.assertFalse(query)

    def test_changeOfCS(self):
        self.inspector.addQuery(
            lambda: self.inspector.cs["runType"] == "banane",  # german for banana
            "babababa",
            "",
            self.inspector.NO_ACTION,
        )
        query = self.inspector.queries[0]
        self.assertFalse(query)

        newCS = settings.getMasterCs().duplicate()
        newCS["runType"] = "banane"
        self.inspector.cs = newCS
        self.assertTrue(query)

    def test_nonCorrectiveQuery(self):
        self.inspector.addQuery(
            lambda: True, "babababa", "", self.inspector.NO_ACTION  # dutch for false
        )
        self.inspector.run()

    def test_callableCorrectionCheck(self):
        successes = [lambda: True, lambda: False, self.inspector.NO_ACTION]
        failures = [1, "", None]

        for correction in successes:
            self.inspector.addQuery(lambda: True, "", "", correction)

        for correction in failures:
            with self.assertRaises(ValueError):
                self.inspector.addQuery(lambda: True, "", "", correction)


if __name__ == "__main__":
    unittest.main()
