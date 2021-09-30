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
Unit tests for the SuiteBuilder
"""
import unittest
from armi.cases.inputModifiers.inputModifiers import SamplingInputModifier
from armi import cases, settings
from armi.cases.suiteBuilder import LatinHyperCubeSuiteBuilder


cs = settings.Settings("armi/cases/tests/anl-afci-177.yaml")
case = cases.Case(cs)


class LatinHyperCubeModifier(SamplingInputModifier):
    def __init__(self, name, paramType: str, bounds: list, independentVariable=None):
        super().__init__(name, paramType, bounds, independentVariable=independentVariable)
        self.value = None
        
    def __call__(self, cs, blueprints, geom):
        cs[self.name] = self.value


class TestLatinHyperCubeSuiteBuilder(unittest.TestCase):
    """Class to test LatinHyperCubeSuiteBuilder."""

    def testInitialize(self):
        builder = LatinHyperCubeSuiteBuilder(case, size=20)
        assert builder.modifierSets == []

    def test_buildSuite(self):
        builder = LatinHyperCubeSuiteBuilder(case, size=20)
        powerMod = LatinHyperCubeModifier("power", "continuous", [0, 1e6])
        availabilityMod = LatinHyperCubeModifier(
            "availabilityFactor", "discrete", [0.0, 0.2, 0.4, 0.6, 0.8]
        )
        builder.addDegreeOfFreedom([powerMod, availabilityMod])
        builder.buildSuite()
        assert len(builder.modifierSets) == 20
        for mod in builder.modifierSets:
            assert 0 < mod[0].value < 1e6
            assert mod[1].value in [0.0, 0.2, 0.4, 0.6, 0.8]


if __name__ == "__main__":
    unittest.main()
