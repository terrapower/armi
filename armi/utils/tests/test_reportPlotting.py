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
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import copy
import os
import unittest

import numpy as np

from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT
from armi.utils.directoryChangers import TemporaryDirectoryChanger
from armi.utils.reportPlotting import (
    buVsTime,
    createPlotMetaData,
    keffVsTime,
    movesVsCycle,
    plotAxialProfile,
    plotCoreOverviewRadar,
    valueVsTime,
    xsHistoryVsTime,
)


class TestRadar(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor(TEST_ROOT)
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    def test_radar(self):
        """Test execution of radar plot. Note this has no asserts and is therefore a smoke test."""
        self.r.core.p.doppler = 0.5
        self.r.core.p.voidWorth = 0.5
        r2 = copy.deepcopy(self.r)
        r2.core.p.voidWorth = 1.0
        r2.core.p.doppler = 1.0
        plotCoreOverviewRadar([self.r, r2], ["Label1", "Label2"])

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
        self.assertTrue(os.path.exists("R-armiRun.keff.png"))
        self.assertGreater(os.path.getsize("R-armiRun.keff.png"), 0)

        # plot with a keff function
        keffVsTime(self.r.name, t, t, t, extension=ext)
        self.assertTrue(os.path.exists("R-armiRun.keff.png"))
        self.assertGreater(os.path.getsize("R-armiRun.keff.png"), 0)

    def test_valueVsTime(self):
        t = list(range(12))
        ext = "png"
        valueVsTime(self.r.name, t, t, "val", "yaxis", "title", extension=ext)
        self.assertTrue(os.path.exists("R-armiRun.val.png"))
        self.assertGreater(os.path.getsize("R-armiRun.val.png"), 0)

    def test_buVsTime(self):
        name = "buvstime"
        scalars = {
            "time": [1, 2, 3, 4],
            "maxBuI": [6, 7, 8, 9],
            "maxBuF": [6, 7, 8, 9],
            "maxDPA": [6, 7, 8, 9],
        }
        figName = name + ".bu.png"
        buVsTime(name, scalars, "png")
        self.assertTrue(os.path.exists(figName))
        self.assertGreater(os.path.getsize(figName), 0)

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

    def test_xsHistoryVsTime(self):
        name = "xsHistoryVsTime"

        class HistTester:
            def __init__(self):
                self.xsHistory = {
                    1: [[0, 1], [0, 2], [0, 3]],
                    2: [[0, 5], [0, 6], [0, 7]],
                }

        history = HistTester()
        figName = name + ".bugroups.png"
        xsHistoryVsTime(name, history, [], "png")
        self.assertTrue(os.path.exists(figName))
        self.assertGreater(os.path.getsize(figName), 0)


if __name__ == "__main__":
    unittest.main()
