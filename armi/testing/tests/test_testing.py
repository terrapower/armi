# Copyright 2025 TerraPower, LLC
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

"""Unit tests for testing fixtures."""

import unittest

from armi.testing.symmetryTests import SymmetryFactorTester


class BasicArmiSymmetryTestHelper(unittest.TestCase):
    pluginCoreParams = []
    pluginAssemblyParams = []
    pluginBlockParams = []
    pluginSymmetricCoreParams = []
    pluginSymmetricAssemblyParams = []
    pluginSymmetricBlockParams = []

    def setUp(self):
        self.defaultSymmetricBlockParams = [
            "powerGenerated",
            "power",
            "powerGamma",
            "powerNeutron",
            "molesHmNow",
            "molesHmBOL",
            "massHmBOL",
            "initialB10ComponentVol",
            "kgFis",
            "kgHM",
        ]
        self.symmetricBlockParams = self.defaultSymmetricBlockParams + self.pluginSymmetricBlockParams
        self.symTester = SymmetryFactorTester(
            self,
            pluginCoreParams=self.pluginCoreParams,
            pluginAssemblyParams=self.pluginAssemblyParams,
            pluginBlockParams=self.pluginBlockParams,
        )

    def test_defaultSymmetry(self):
        self.symTester.runSymmetryFactorTests(blockParams=self.symmetricBlockParams)

    def test_errorWhenNotDefined(self):
        with self.assertRaises(AssertionError) as em:
            self.symTester.runSymmetryFactorTests()
            self.assertIn("but is not specified in the parameters expected to change", em.msg)

    def test_errorWhenRequestedButNotExpanded(self):
        with self.assertRaises(AssertionError) as em:
            blockParams = self.defaultSymmetricBlockParams + ["nHMAtBOL"]
            self.symTester.runSymmetryFactorTests(blockParams=blockParams)
            self.assertIn("The after-to-before expansion ratio of parameter", em.msg)
