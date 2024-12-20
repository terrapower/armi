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

"""Tests for settings validation system."""
import os
import unittest

from armi import context, operators, settings
from armi.settings import settingsValidation
from armi.settings.settingsValidation import createQueryRevertBadPathToDefault
from armi.utils import directoryChangers


class TestInspector(unittest.TestCase):
    def setUp(self):
        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()
        self.init_mode = context.CURRENT_MODE
        self.cs = settings.Settings()
        self.inspector = operators.getOperatorClassFromSettings(self.cs).inspector(
            self.cs
        )
        self.inspector.queries = []  # clear out the auto-generated ones
        self.filepathYaml = os.path.join(
            os.getcwd(), self._testMethodName + "_test_setting_io.yaml"
        )

    def tearDown(self):
        context.Mode.setMode(self.init_mode)
        self.td.__exit__(None, None, None)

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

    def test_overwriteSettingsCorrectiveQuery(self):
        """
        Tests the case where a corrective query is resolved.
        Checks to make sure the settings file is overwritten with the resolved setting.

        .. test:: Settings have validation and correction tools.
            :id: T_ARMI_SETTINGS_RULES0
            :tests: R_ARMI_SETTINGS_RULES
        """
        # load settings from test settings file
        self.cs["cycleLength"] = 300.0
        self.cs.writeToYamlFile(self.filepathYaml)
        self.cs.loadFromInputFile(self.filepathYaml)
        self.assertEqual(self.cs["cycleLength"], 300.0)

        # define corrective query
        def csChange(x, y, z):
            x[y] = z

        self.inspector.addQuery(
            lambda: self.inspector.cs["cycleLength"] == 300.0,
            "Changing `cycleLength` from 300.0 to 666",
            ":D",
            lambda: csChange(self.cs, "cycleLength", 666),
        )

        # redefine prompt function in order to circumvent need for user input
        def fakePrompt(*inputs):
            return True

        nominalPromptFunction = settingsValidation.prompt
        settingsValidation.prompt = fakePrompt

        try:
            # run inspector
            self.inspector.run()

            # check to see if file was overwritten correctly
            self.cs.loadFromInputFile(self.filepathYaml)
            self.assertEqual(self.cs["cycleLength"], 666)

            # check to see if original settings were saved in "_old.yaml" file
            oldFilePath = "{}_old.yaml".format(self.filepathYaml.split(".yaml")[0])
            self.assertTrue(os.path.exists(oldFilePath) and os.path.isfile(oldFilePath))
            self.csOriginal = settings.Settings()
            self.csOriginal.loadFromInputFile(oldFilePath)
            self.assertEqual(self.csOriginal["cycleLength"], 300.0)

        finally:
            # reset prompt function to nominal
            settingsValidation.prompt = nominalPromptFunction

    def test_changeOfCS(self):
        self.inspector.addQuery(
            lambda: self.inspector.cs["runType"] == "banane",
            "babababa",
            "",
            self.inspector.NO_ACTION,
        )
        query = self.inspector.queries[0]
        self.assertFalse(query)

        newCS = settings.Settings().duplicate()
        newSettings = {"runType": "banane"}
        newCS = newCS.modified(newSettings=newSettings)

        self.inspector.cs = newCS
        self.assertTrue(query)
        self.assertIsNone(self.inspector.NO_ACTION())

    def test_nonCorrectiveQuery(self):
        self.inspector.addQuery(lambda: True, "babababa", "", self.inspector.NO_ACTION)
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
        self.assertIn("nCycles", keys)

    def test_createQueryRevertBadPathToDefault(self):
        query = createQueryRevertBadPathToDefault(self.inspector, "nTasks")
        self.assertEqual(
            str(query),
            "<Query: Setting nTasks points to a nonexistent location:\n1>",
        )

    def test_correctCyclesToZeroBurnup(self):
        self.inspector._assignCS("nCycles", 666)
        self.inspector._assignCS("burnSteps", 666)

        self.assertEqual(self.inspector.cs["nCycles"], 666)
        self.assertEqual(self.inspector.cs["burnSteps"], 666)

        self.inspector._correctCyclesToZeroBurnup()

        self.assertEqual(self.inspector.cs["nCycles"], 1)
        self.assertEqual(self.inspector.cs["burnSteps"], 0)

    def test_checkForBothSimpleAndDetailedCyclesInputs(self):
        self.inspector._assignCS(
            "cycles",
            [
                {"cumulative days": [1, 2, 3]},
                {"cycle length": 1},
                {"step days": [3, 3, 3]},
            ],
        )
        self.assertFalse(self.inspector._checkForBothSimpleAndDetailedCyclesInputs())

        self.inspector._assignCS(
            "cycles",
            [
                {"cumulative days": [1, 2, 3]},
                {"cycle length": 1},
                {"step days": [3, 3, 3]},
            ],
        )
        self.inspector._assignCS("cycleLength", 666)
        self.assertTrue(self.inspector._checkForBothSimpleAndDetailedCyclesInputs())
