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
"""macroXSGenerationInterface tests."""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import unittest

from armi.physics.neutronics.macroXSGenerationInterface import (
    MacroXSGenerationInterface,
)
from armi.reactor.tests.test_reactors import loadTestReactor
from armi.settings import Settings


class TestMacroXSGenerationInterface(unittest.TestCase):
    def test_macroXSGenerationInterface(self):
        cs = Settings()
        _o, r = loadTestReactor()
        i = MacroXSGenerationInterface(r, cs)

        self.assertIsNone(i.macrosLastBuiltAt)
        self.assertEqual(i.minimumNuclideDensity, 1e-15)
        self.assertEqual(i.name, "macroXsGen")


if __name__ == "__main__":
    unittest.main()
