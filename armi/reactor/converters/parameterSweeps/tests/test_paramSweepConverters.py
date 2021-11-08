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
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import math
import os
import unittest

from armi import runLog
from armi import settings
from armi.reactor import blocks
from armi.reactor import geometry
from armi.reactor import grids
from armi.tests import TEST_ROOT
from armi.reactor.converters.parameterSweeps.generalParameterSweepConverters import (
    NeutronicConvergenceModifier,
    ParameterSweepConverter,
)
from armi.reactor.tests.test_reactors import loadTestReactor
from armi.reactor.flags import Flags


THIS_DIR = os.path.dirname(__file__)


class TestParamSweepConverters(unittest.TestCase):
    def setUp(self):
        self.o, self.r = loadTestReactor(TEST_ROOT)
        self.cs = settings.getMasterCs()

    def test_paramSweepConverter(self):
        """basic test of the param sweep converter"""
        con = ParameterSweepConverter(self.cs, "FakeParam")
        self.assertEqual(con._parameter, "FakeParam")

        con.convert(self.r)
        self.assertEqual(con._sourceReactor, self.r)

    def test_neutronicConvergenceModifier(self):
        """super basic test of the Neutronic Convergence Modifier"""
        custom = NeutronicConvergenceModifier(self.cs, 1000)
        self.assertEqual(custom._parameter, 1000)

        custom.convert(self.r)
        self.assertAlmostEqual(custom._cs["epsFSPoint"], 1, delta=1e-3)
