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
"""Who tests the testers?."""

from armi.testing import symmetryTesting


class SymmetryTestFixtureTester(symmetryTesting.BasicArmiSymmetryTestHelper):
    """Run the basic symmetry test helper with some input known to raise errors."""

    def setUp(self):
        self.pluginBlockParams = ["zbottom", "massHmBOL"]
        self.pluginSymmetricBlockParams = ["massHmBOL"]
        return super().setUp()

    def test_errorWhenExpandedButNotRequested(self):
        if (
            len(self.pluginSymmetricCoreParams + self.pluginSymmetricAssemblyParams + self.pluginSymmetricBlockParams)
            > 0
        ):
            with self.assertRaises(AssertionError) as err:
                self.symTester.runSymmetryFactorTests()
                self.assertIn(f"The value of {self.pluginSymmetricBlockParams} on the", err.msg)

    def test_errorWhenRequestedButNotExpanded(self):
        with self.assertRaises(AssertionError) as err:
            targetParam = self.pluginBlockParams[0]
            self.symTester.runSymmetryFactorTests(blockParams=targetParam)
            self.assertIn(f"The after-to-before expansion ratio of parameter '{targetParam}'", err.msg)
