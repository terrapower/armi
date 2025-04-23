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
from collections import defaultdict

from armi.nuclearDataIO import isotxs
from armi.nuclearDataIO.xsCollections import XSCollection
from armi.physics.neutronics.macroXSGenerationInterface import (
    MacroXSGenerationInterface,
)
from armi.settings import Settings
from armi.testing import loadTestReactor
from armi.tests import ISOAA_PATH


class TestMacroXSGenerationInterface(unittest.TestCase):
    def test_macroXSGenerationInterfaceBasics(self):
        """Test the macroscopic XS generating interfaces.

        .. test:: Build macroscopic cross sections for all blocks in the reactor.
            :id: T_ARMI_MACRO_XS
            :tests: R_ARMI_MACRO_XS
        """
        cs = Settings()
        _o, r = loadTestReactor(
            inputFileName="smallestTestReactor/armiRunSmallest.yaml"
        )

        # Before: verify there are no macro XS on each block
        for b in r.core.iterBlocks():
            self.assertIsNone(b.macros)

        # create the macro XS interface
        i = MacroXSGenerationInterface(r, cs)
        self.assertEqual(i.minimumNuclideDensity, 1e-15)
        self.assertEqual(i.name, "macroXsGen")

        # Mock up a nuclide library
        mockLib = isotxs.readBinary(ISOAA_PATH)
        mockLib.__dict__["_nuclides"] = defaultdict(
            lambda: mockLib.__dict__["_nuclides"]["CAA"], mockLib.__dict__["_nuclides"]
        )

        # This is the meat of it: build the macro XS
        self.assertIsNone(i.macrosLastBuiltAt)
        i.buildMacros(mockLib, buildScatterMatrix=False)
        self.assertEqual(i.macrosLastBuiltAt, 0)

        # After: verify there are macro XS on each block
        for b in r.core.iterBlocks():
            self.assertIsNotNone(b.macros)
            self.assertTrue(isinstance(b.macros, XSCollection))
