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
from armi.operators.settingsValidation import createQueryRevertBadPathToDefault


class TestInspector(unittest.TestCase):
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

        self.assertEqual(str(query), "<Query: beepbopboopbeep>")

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
        newSettings = {"runType": "banane"}
        newCS = newCS.modified(newSettings=newSettings)

        self.inspector.cs = newCS
        self.assertTrue(query)
        self.assertIsNone(self.inspector.NO_ACTION())

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

    def test_assignCS(self):
        keys = sorted(self.inspector.cs.keys())
        self.assertIn("HCFcoretype", keys)

        self.assertEqual(self.inspector.cs["HCFcoretype"], "TWRC")
        self.inspector._assignCS(
            "HCFcoretype", "FAKE"
        )  # pylint: disable=protected-access
        self.assertEqual(self.inspector.cs["HCFcoretype"], "FAKE")

    def test_createQueryRevertBadPathToDefault(self):
        query = createQueryRevertBadPathToDefault(self.inspector, "numProcessors")
        self.assertEqual(
            str(query),
            "<Query: Setting numProcessors points to a nonexistent location:\n1>",
        )

    def test_correctCyclesToZeroBurnup(self):
        self.inspector._assignCS("nCycles", 666)
        self.inspector._assignCS("burnSteps", 666)

        self.assertEqual(self.inspector.cs["nCycles"], 666)
        self.assertEqual(self.inspector.cs["burnSteps"], 666)

        self.inspector._correctCyclesToZeroBurnup()

        self.assertEqual(self.inspector.cs["nCycles"], 1)
        self.assertEqual(self.inspector.cs["burnSteps"], 0)


if __name__ == "__main__":
    unittest.main()
