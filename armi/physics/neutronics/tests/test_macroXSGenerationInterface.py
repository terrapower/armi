# Copyright 2021 TerraPower, LLC
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
"""MacroXSGenerationInterface tests."""
import unittest
from unittest.mock import patch

from armi.physics.neutronics.macroXSGenerationInterface import (
    MacroXSGenerationInterface,
)
from armi.reactor.tests.test_reactors import loadTestReactor
from armi.settings import Settings

from armi.nucDirectory import nuclideBases


class TestMacroXSGenerationInterface(unittest.TestCase):
    @patch("armi.physics.neutronics.macroXSGenerationInterface.MacroXSGenerator.invoke")
    def test_macroXSGenerationInterfaceBasics(self, invokeHook):
        """Test the macroscopic XS generating interfaces.

        .. test::Build macroscopic cross sections for all blocks in the reactor.
            :id: T_ARMI_MACRO_XS
            :tests: R_ARMI_MACRO_XS
        """
        cs = Settings()
        _o, r = loadTestReactor()
        i = MacroXSGenerationInterface(r, cs)

        self.assertIsNone(i.macrosLastBuiltAt)
        self.assertEqual(i.minimumNuclideDensity, 1e-15)
        self.assertEqual(i.name, "macroXsGen")

        class MockLib:
            numGroups = 1
            numGroupsGamma = 1

            def getNuclide(self, nucName, suffix):
                try:
                    return nuclideBases.byName.get(nucName, None)
                except AttributeError:
                    return None

        i.buildMacros(MockLib(), buildScatterMatrix=False)
