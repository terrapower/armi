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

"""Tests for basic plotting tools."""
import os
import unittest

from armi.nuclearDataIO.cccc import isotxs
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.tests import ISOAA_PATH, TEST_ROOT
from armi.utils import plotting
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class TestPlotting(unittest.TestCase):
    """
    Test and demonstrate some plotting capabilities of ARMI.

    Notes
    -----
    These tests don't do a great job of making sure the plot appears correctly,
    but they do check that the lines of code run, and that an image is produced, and
    demonstrate how they are meant to be called.
    """

    @classmethod
    def setUpClass(cls):
        cls.o, cls.r = test_reactors.loadTestReactor()

    def test_plotDepthMap(self):  # indirectly tests plot face map
        with TemporaryDirectoryChanger():
            # set some params to visualize
            for i, b in enumerate(self.o.r.core.getBlocks()):
                b.p.percentBu = i / 100
            fName = plotting.plotBlockDepthMap(
                self.r.core, param="percentBu", fName="depthMapPlot.png", depthIndex=2
            )
            self._checkExists(fName)

    def test_plotAssemblyTypes(self):
        with TemporaryDirectoryChanger():
            plotPath = "coreAssemblyTypes1.png"
            plotting.plotAssemblyTypes(self.r.core.parent.blueprints, plotPath)
            self._checkExists(plotPath)

            plotPath = "coreAssemblyTypes2.png"
            plotting.plotAssemblyTypes(
                self.r.core.parent.blueprints,
                plotPath,
                yAxisLabel="y axis",
                title="title",
            )
            self._checkExists(plotPath)

            with self.assertRaises(ValueError):
                plotting.plotAssemblyTypes(None, plotPath, None)

    def test_plotBlockFlux(self):
        with TemporaryDirectoryChanger():
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

    def test_plotHexBlock(self):
        with TemporaryDirectoryChanger():
            first_fuel_block = self.r.core.getFirstBlock(Flags.FUEL)
            first_fuel_block.autoCreateSpatialGrids()
            plotting.plotBlockDiagram(first_fuel_block, "blockDiagram23.svg", True)
            self.assertTrue(os.path.exists("blockDiagram23.svg"))

    def test_plotCartesianBlock(self):
        from armi import settings
        from armi.reactor import blueprints, reactors

        with TemporaryDirectoryChanger():
            cs = settings.Settings(
                os.path.join(TEST_ROOT, "tutorials", "c5g7-settings.yaml")
            )

            blueprint = blueprints.loadFromCs(cs)
            _ = reactors.factory(cs, blueprint)
            for name, bDesign in blueprint.blockDesigns.items():
                b = bDesign.construct(cs, blueprint, 0, 1, 1, "AA", {})
                plotting.plotBlockDiagram(b, "{}.svg".format(name), True)
            self.assertTrue(os.path.exists("uo2.svg"))
            self.assertTrue(os.path.exists("mox.svg"))

    def _checkExists(self, fName):
        self.assertTrue(os.path.exists(fName))
