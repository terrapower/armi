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

"""Module to test parameter sweep converters."""

import os
import unittest

from armi.physics.neutronics.settings import CONF_EPS_FSPOINT
from armi.reactor.converters.parameterSweeps.generalParameterSweepConverters import (
    NeutronicConvergenceModifier,
    ParameterSweepConverter,
    SettingsModifier,
)
from armi.testing import loadTestReactor
from armi.tests import TEST_ROOT

THIS_DIR = os.path.dirname(__file__)


class TestParamSweepConverters(unittest.TestCase):
    def setUp(self):
        self.o, self.r = loadTestReactor(TEST_ROOT, inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        self.cs = self.o.cs

    def test_paramSweepConverter(self):
        """Basic test of the param sweep converter."""
        con = ParameterSweepConverter(self.cs, "FakeParam")
        self.assertEqual(con._parameter, "FakeParam")

        con.convert(self.r)
        self.assertEqual(con._sourceReactor, self.r)

    def test_neutronicConvergenceModifier(self):
        """Super basic test of the Neutronic Convergence Modifier."""
        custom = NeutronicConvergenceModifier(self.cs, 1000)
        self.assertEqual(custom._parameter, 1000)

        custom.convert(self.r)
        self.assertAlmostEqual(custom._cs[CONF_EPS_FSPOINT], 1, delta=1e-3)

    def test_settingsModifier(self):
        """Super basic test of the Settings Modifier."""
        con = SettingsModifier(self.cs, "comment", "FakeParam")
        self.assertEqual(con._parameter, "FakeParam")

        con.convert(self.r)
        self.assertEqual(con._sourceReactor, self.r)

        # NOTE: Settings objects are not modified, but we point to new objects
        self.assertIn("Simple test input", self.cs["comment"])
        self.assertEqual(con._cs["comment"], "FakeParam")
