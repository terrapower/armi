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

"""
Tests for functions in util.plotting.py
"""
import os
import unittest

from armi.utils import plotting
from armi.reactor.tests import test_reactors


class TestPlotting(unittest.TestCase):
    """
    Test and demonstrate some plotting capabilities of ARMI.

    Notes
    -----
    These tests don't do a great job of making sure the plot appears correctly,
    but they do check that the lines of code run, and that an image is produced, and
    demonstrate how they are meant to be called.
    """

    # Change to False when you want to inspect the plots. Change back please.
    removeFiles = True

    @classmethod
    def setUpClass(cls):
        cls.o, cls.r = test_reactors.loadTestReactor()

    def test_plotDepthMap(self):  # indirectly tests plot face map
        # set some params to visualize
        for i, b in enumerate(self.o.r.core.getBlocks()):
            b.p.percentBu = i / 100
        fName = plotting.plotBlockDepthMap(
            self.r.core, param="percentBu", fName="depthMapPlot.png", depthIndex=2
        )
        self._checkExists(fName)

    def test_plotAssemblyTypes(self):
        plotting.plotAssemblyTypes(
            self.r.core.parent.blueprints, "coreAssemblyTypes1.png"
        )
        self._checkExists("coreAssemblyTypes1.png")

    def _checkExists(self, fName):
        self.assertTrue(os.path.exists(fName))
        if self.removeFiles:
            os.remove(fName)


if __name__ == "__main__":
    unittest.main()
