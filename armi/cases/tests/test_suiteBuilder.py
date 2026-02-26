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

"""Unit tests for the SuiteBuilder."""

import os
import unittest

from armi import cases, settings
from armi.cases.inputModifiers.inputModifiers import InputModifier
from armi.cases.suiteBuilder import FullFactorialSuiteBuilder, SeparateEffectsSuiteBuilder

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
AFCI_PATH = os.path.join(THIS_DIR, "..", "..", "testing", "reactors", "anl-afci-177", "anl-afci-177.yaml")


class SettingModifier(InputModifier):
    def __init__(self, settingName, value):
        self.settingName = settingName
        self.value = value

    def __call__(self, cs, bp):
        cs = cs.modified(newSettings={self.settingName: self.value})
        return cs, bp


class TestFullFactorialSuiteBuilder(unittest.TestCase):
    """Class to test FullFactorialSuiteBuilder."""

    def test_buildSuite(self):
        """Initialize a full factorial suite of cases.

        .. test:: A generic mechanism to allow users to modify user inputs in cases.
            :id: T_ARMI_CASE_MOD1
            :tests: R_ARMI_CASE_MOD
        """
        cs = settings.Settings(AFCI_PATH)
        case = cases.Case(cs)
        builder = FullFactorialSuiteBuilder(case)
        builder.addDegreeOfFreedom(SettingModifier("settingName1", value) for value in (1, 2))
        builder.addDegreeOfFreedom(SettingModifier("settingName2", value) for value in (3, 4, 5))

        self.assertEqual(builder.modifierSets[0][0].value, 1)
        self.assertEqual(builder.modifierSets[0][1].value, 3)

        self.assertEqual(builder.modifierSets[1][0].value, 2)
        self.assertEqual(builder.modifierSets[1][1].value, 3)

        self.assertEqual(builder.modifierSets[2][0].value, 1)
        self.assertEqual(builder.modifierSets[2][1].value, 4)

        self.assertEqual(builder.modifierSets[3][0].value, 2)
        self.assertEqual(builder.modifierSets[3][1].value, 4)

        self.assertEqual(builder.modifierSets[4][0].value, 1)
        self.assertEqual(builder.modifierSets[4][1].value, 5)

        self.assertEqual(builder.modifierSets[5][0].value, 2)
        self.assertEqual(builder.modifierSets[5][1].value, 5)

        self.assertEqual(len(builder.modifierSets), 6)


class TestSeparateEffectsBuilder(unittest.TestCase):
    """Class to test separate effects builder."""

    def test_buildSuite(self):
        """Initialize a full factorial suite of cases.

        .. test:: A generic mechanism to allow users to modify user inputs in cases.
            :id: T_ARMI_CASE_MOD2
            :tests: R_ARMI_CASE_MOD
        """
        cs = settings.Settings(AFCI_PATH)
        case = cases.Case(cs)
        builder = SeparateEffectsSuiteBuilder(case)
        builder.addDegreeOfFreedom(SettingModifier("settingName1", value) for value in (1, 2))
        builder.addDegreeOfFreedom(SettingModifier("settingName2", value) for value in (3, 4, 5))

        self.assertEqual(builder.modifierSets[0][0].value, 1)
        self.assertEqual(builder.modifierSets[0][0].settingName, "settingName1")

        self.assertEqual(builder.modifierSets[1][0].value, 2)
        self.assertEqual(builder.modifierSets[1][0].settingName, "settingName1")

        self.assertEqual(builder.modifierSets[2][0].value, 3)
        self.assertEqual(builder.modifierSets[2][0].settingName, "settingName2")

        self.assertEqual(builder.modifierSets[3][0].value, 4)
        self.assertEqual(builder.modifierSets[3][0].settingName, "settingName2")

        self.assertEqual(builder.modifierSets[4][0].value, 5)
        self.assertEqual(builder.modifierSets[4][0].settingName, "settingName2")

        self.assertEqual(len(builder.modifierSets), 5)
