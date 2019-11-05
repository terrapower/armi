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

"""
import unittest

from armi.utils import directoryChangers
from armi.tests import TEST_ROOT
from armi.reactor.flags import Flags
import armi.reactor.tests.test_reactors
from armi.reactor import geometry


class CartesianReactorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # prepare the input files. This is important so the unit tests run from wherever
        # they need to run from.
        cls.directoryChanger = directoryChangers.DirectoryChanger(TEST_ROOT)
        cls.directoryChanger.open()

    @classmethod
    def tearDownClass(cls):
        cls.directoryChanger.close()

    def setUp(self):
        """
        Use the related setup in the testFuelHandlers module.
        """
        self.o, self.r = armi.reactor.tests.test_reactors.loadTestReactor(
            self.directoryChanger.destination, inputFileName="refTestCartesian.yaml"
        )

    def test_custom(self):
        """Test Custom material with custom density."""
        fuel = self.r.core.getFirstAssembly(Flags.MIDDLE | Flags.FUEL).getFirstBlock(
            Flags.FUEL
        )
        custom = fuel.getComponent(Flags.FUEL)
        self.assertEqual(self.r.core.geomType, geometry.CARTESIAN)
        self.assertAlmostEqual(
            custom.getNumberDensity("U238"), 0.0134125
        )  # from blueprints input file


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
