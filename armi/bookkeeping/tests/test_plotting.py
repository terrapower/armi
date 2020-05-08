# Copyright 2020 TerraPower, LLC
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

"""Test plotting."""
import copy
import os
import unittest

from armi.tests import TEST_ROOT
from armi.reactor.tests import test_reactors
from armi.bookkeeping.plotting import plotCoreOverviewRadar


class TestRadar(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor(TEST_ROOT)

    def testRadar(self):
        """Test execution of radar plot. Note this has no asserts and is therefore a smoke test."""

        self.r.core.p.doppler = 0.5
        self.r.core.p.voidWorth = 0.5
        r2 = copy.deepcopy(self.r)
        r2.core.p.voidWorth = 1.0
        r2.core.p.doppler = 1.0
        plotCoreOverviewRadar([self.r, r2], ["Label1", "Label2"])
        os.remove("reactor_comparison.png")


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
