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

"""Tests for Cartesian reactors."""

import os
import unittest

from armi.reactor import geometry
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.tests import TESTING_ROOT


class CartesianReactorTests(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor(
            os.path.join(TESTING_ROOT, "reactors", "smallCartesian"),
            inputFileName="refTestCartesian.yaml",
        )

    def test_custom(self):
        """Test Custom material with custom density."""
        fuel = self.r.core.getFirstAssembly(Flags.MIDDLE | Flags.FUEL).getFirstBlock(Flags.FUEL)
        custom = fuel.getComponent(Flags.FUEL)
        self.assertEqual(self.r.core.geomType, geometry.GeomType.CARTESIAN)
        # from blueprints input file
        self.assertAlmostEqual(custom.getNumberDensity("U238"), 0.0134125)
