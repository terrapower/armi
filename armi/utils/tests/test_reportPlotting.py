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

import numpy as np

from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT
from armi.utils.directoryChangers import TemporaryDirectoryChanger
from armi.utils.reportPlotting import (
    _getPhysicalVals,
    createPlotMetaData,
    keffVsTime,
    movesVsCycle,
    plotAxialProfile,
    plotCoreOverviewRadar,
    valueVsTime,
)


class TestRadar(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor(
            TEST_ROOT, inputFileName="smallestTestReactor/armiRunSmallest.yaml"
        )
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    def test_radar(self):
        """Test execution of radar plot. Note this has no asserts and is therefore a smoke test."""
        r2 = copy.deepcopy(self.r)
        plotCoreOverviewRadar([self.r, r2], ["Label1", "Label2"])
        self.assertTrue(os.path.exists("reactor_comparison.png"))

    def test_getPhysicalVals(self):
        dims, labels, vals = _getPhysicalVals(self.r)
        self.assertEqual(dims, "Dimensions")

        self.assertEqual(labels[0], "Cold fuel height")
        self.assertEqual(labels[1], "Fuel assems")
        self.assertEqual(labels[2], "Assem weight")
        self.assertEqual(labels[3], "Core radius")
        self.assertEqual(labels[4], "Core aspect ratio")
        self.assertEqual(labels[5], "Fissile mass")
        self.assertEqual(len(labels), 6)

        self.assertEqual(vals[0], 25.0)
        self.assertEqual(vals[1], 1)
        self.assertAlmostEqual(vals[2], 52474.8927038, delta=1e-5)
        self.assertEqual(vals[3], 16.8)
        self.assertAlmostEqual(vals[5], 4290.60340961, delta=1e-5)
        self.assertEqual(len(vals), 6)

        # this test will use getInputHeight() instead of getHeight()
        radius = self.r.core.getCoreRadius()
        avgHeight = 0
        fuelA = self.r.core.getAssemblies(Flags.FUEL)
        for a in fuelA:
            for b in a.getBlocks(Flags.FUEL):
                avgHeight += b.getInputHeight()
        avgHeight /= len(fuelA)
        coreAspectRatio = (2 * radius) / avgHeight
        self.assertEqual(vals[4], coreAspectRatio)

    def test_createPlotMetaData(self):
        title = "test_createPlotMetaData"
        xLabel = "xLabel"
        yLabel = "yLabel"
        xTicks = [1, 2]
        yTicks = [3, 4]
        labels = ["a", "b"]
        meta = createPlotMetaData(title, xLabel, yLabel, xTicks, yTicks, labels)

        self.assertEqual(len(meta), 6)
        self.assertEqual(meta["title"], title)
        self.assertEqual(meta["xlabel"], xLabel)
        self.assertEqual(meta["ylabel"], yLabel)

    def test_plotAxialProfile(self):
        vals = list(range(1, 10, 2))
        fName = "test_plotAxialProfile"

        xLabel = "xLabel"
        yLabel = "yLabel"
        xTicks = [1, 2]
        yTicks = [3, 4]
        labels = ["a", "b"]
        meta = createPlotMetaData(fName, xLabel, yLabel, xTicks, yTicks, labels)

        plotAxialProfile(vals, np.ones((5, 2)), fName, meta, nPlot=2)
        self.assertTrue(os.path.exists(fName + ".png"))

    def test_keffVsTime(self):
        t = list(range(12))
        ext = "png"

        # plot with no keff function
        keffVsTime(self.r.name, t, t, keffUnc=[], extension=ext)
        self.assertTrue(os.path.exists("R-armiRunSmallest.keff.png"))
        self.assertGreater(os.path.getsize("R-armiRunSmallest.keff.png"), 0)

        # plot with a keff function
        keffVsTime(self.r.name, t, t, t, extension=ext)
        self.assertTrue(os.path.exists("R-armiRunSmallest.keff.png"))
        self.assertGreater(os.path.getsize("R-armiRunSmallest.keff.png"), 0)

    def test_valueVsTime(self):
        t = list(range(12))
        ext = "png"
        valueVsTime(self.r.name, t, t, "val", "yaxis", "title", extension=ext)
        self.assertTrue(os.path.exists("R-armiRunSmallest.val.png"))
        self.assertGreater(os.path.getsize("R-armiRunSmallest.val.png"), 0)

    def test_movesVsCycle(self):
        name = "movesVsCycle"
        scalars = {
            "cycle": [1, 2, 3, 4],
            "maxBuF": [6, 7, 8, 9],
            "maxBuI": [6, 7, 8, 9],
            "maxDPA": [6, 7, 8, 9],
            "numMoves": [2, 2, 2, 2],
            "time": [1, 2, 3, 4],
        }
        figName = name + ".moves.png"
        movesVsCycle(name, scalars, "png")
        self.assertTrue(os.path.exists(figName))
        self.assertGreater(os.path.getsize(figName), 0)
