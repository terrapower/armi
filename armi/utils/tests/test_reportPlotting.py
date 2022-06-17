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
"""Test plotting"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-acces
import copy
import os
import unittest

import numpy as np

from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT
from armi.utils.reportPlotting import (
    createPlotMetaData,
    keffVsTime,
    plotAxialProfile,
    plotCoreOverviewRadar,
)


class TestRadar(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor(TEST_ROOT)

    def test_radar(self):
        """Test execution of radar plot. Note this has no asserts and is therefore a smoke test."""
        self.r.core.p.doppler = 0.5
        self.r.core.p.voidWorth = 0.5
        r2 = copy.deepcopy(self.r)
        r2.core.p.voidWorth = 1.0
        r2.core.p.doppler = 1.0
        plotCoreOverviewRadar([self.r, r2], ["Label1", "Label2"])
        os.remove("reactor_comparison.png")

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
        os.remove(fName + ".png")

    def test_keffVsTime(self):
        t = list(range(75))
        ext = "png"
        keffVsTime(self.r, t, t, keffUnc=[], extension=ext)
        self.assertTrue(os.path.exists("R-armiRun.keff.png"))
        os.remove("R-armiRun.keff.png")


if __name__ == "__main__":
    unittest.main()
