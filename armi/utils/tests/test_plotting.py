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

from armi.nuclearDataIO.cccc import isotxs
from armi.utils import plotting
from armi.reactor.tests import test_reactors
from armi.tests import ISOAA_PATH


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

    def test_plotBlockFlux(self):
        try:
            xslib = isotxs.readBinary(ISOAA_PATH)
            self.r.core.lib = xslib

            blockList = self.r.core.getBlocks()
            for _, b in enumerate(blockList):
                b.p.mgFlux = range(33)

            plotting.plotBlockFlux(self.r.core, fName="flux.png", bList=blockList)
            self.assertTrue(os.path.exists("flux.png"))
            plotting.plotBlockFlux(
                self.r.core, fName="peak.png", bList=blockList, peak=True
            )
            self.assertTrue(os.path.exists("peak.png"))
            plotting.plotBlockFlux(
                self.r.core,
                fName="bList2.png",
                bList=blockList,
                bList2=blockList,
            )
            self.assertTrue(os.path.exists("bList2.png"))
            # can't test adjoint at the moment, testBlock doesn't like to .getMgFlux(adjoint=True)
        finally:
            os.remove("flux.txt")  # secondarily created during the call.
            os.remove("flux.png")  # created during the call.
            os.remove("peak.txt")  # csecondarily reated during the call.
            os.remove("peak.png")  # created during the call.
            os.remove("bList2.txt")  # secondarily created during the call.
            os.remove("bList2.png")  # created during the call.

    def _checkExists(self, fName):
        self.assertTrue(os.path.exists(fName))
        if self.removeFiles:
            os.remove(fName)


if __name__ == "__main__":
    unittest.main()
