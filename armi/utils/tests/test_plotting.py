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

import matplotlib.pyplot as plt
import numpy as np

from armi import settings
from armi.nuclearDataIO.cccc import isotxs
from armi.reactor import blueprints, reactors
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.testing import TESTING_ROOT
from armi.tests import ISOAA_PATH, getEmptyHexReactor
from armi.utils import plotting
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class TestPlotting(unittest.TestCase):
    """
    Test and demonstrate some plotting capabilities of ARMI.

    Notes
    -----
    These tests don't do a great job of making sure the plot appears correctly, but they do check that the lines of code
    run, and that an image is produced, and demonstrate how they are meant to be called.
    """

    @classmethod
    def setUpClass(cls):
        cls.o, cls.r = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")

    def test_plotDepthMap(self):
        """Indirectly tests plot face map."""
        with TemporaryDirectoryChanger():
            # set some params to visualize
            for i, b in enumerate(self.o.r.core.iterBlocks()):
                b.p.percentBu = i / 100
            fName = plotting.plotBlockDepthMap(self.r.core, param="percentBu", fName="depthMapPlot.png", depthIndex=2)
            self._checkFileExists(fName)

            # catch an edge case error (no matching assemblies)
            with self.assertRaises(ValueError):
                r = getEmptyHexReactor()
                plotting.plotBlockDepthMap(r.core)

    def test_plotFaceMap(self):
        """Indirectly tests plot face map."""
        with TemporaryDirectoryChanger():
            for i, b in enumerate(self.o.r.core.iterBlocks()):
                b.p.percentBu = i / 100

            # make sure some of the plot files exist
            fName = plotting.plotFaceMap(self.r.core, param="percentBu", fName="faceMapPlot0.png", makeColorBar=True)
            self._checkFileExists(fName)

            fName = plotting.plotFaceMap(self.r.core, param="percentBu", fName="faceMapPlot1.png", vals="average")
            self._checkFileExists(fName)

            # catch an edge case error (bad val name)
            with self.assertRaises(ValueError):
                plotting.plotFaceMap(self.r.core, param="percentBu", fName="faceMapPlot2.png", vals="whoops")

            # this should not throw an error
            plotting.close()

    def test_plotAssemblyTypes(self):
        with TemporaryDirectoryChanger():
            plotPath = "coreAssemblyTypes1.png"
            plotting.plotAssemblyTypes(list(self.r.core.parent.blueprints.assemblies.values()), plotPath)
            self._checkFileExists(plotPath)

            if os.path.exists(plotPath):
                os.remove(plotPath)

            plotPath = "coreAssemblyTypes2.png"
            fig = plotting.plotAssemblyTypes(
                list(self.r.core.parent.blueprints.assemblies.values()),
                plotPath,
                yAxisLabel="y axis",
                title="title",
            )
            self.assertFalse(fig.subfigures(1, 1).subplots().has_data())
            self.assertEqual(fig.axes[0]._children[0].xy, (0.5, 0))
            self._checkFileExists(plotPath)

            for _ in range(3):
                if os.path.exists(plotPath):
                    os.remove(plotPath)

    def test_plotRadialReactorLayouts(self):
        figs = plotting.plotRadialReactorLayouts(self.r)
        self.assertEqual(len(figs), 1)
        self.assertEqual(figs[0].axes[0]._children[0].xy, (0.5, 0))

        plotPath = "coreAssemblyTypes1-rank0.png"
        for _ in range(3):
            if os.path.exists(plotPath):
                os.remove(plotPath)

    def test_plotScatterMatrix(self):
        plotPath = "test_plotScatterMatrix.png"
        lib = isotxs.readBinary(ISOAA_PATH)
        u235 = lib.getNuclide("U235", "AA")
        scatterMatrix = u235.micros.inelasticScatter
        img = plotting.plotScatterMatrix(scatterMatrix, fName=plotPath)
        self.assertGreater(len(img.axes.get_children()), 10)
        self.assertLess(len(img.axes.get_children()), 30)
        self.assertTrue(img.axes.has_data())

        for _ in range(3):
            if os.path.exists(plotPath):
                os.remove(plotPath)

    def test_plotBlocksInAssembly(self):
        _fig, ax = plt.subplots(figsize=(15, 15), dpi=300)
        xBlockLoc, yBlockHeights, yBlockAxMesh = plotting._plotBlocksInAssembly(
            ax,
            self.r.core.getFirstAssembly(Flags.FUEL),
            True,
            [],
            set(),
            0.5,
            5.6,
            True,
            hot=True,
        )
        self.assertEqual(xBlockLoc, 0.5)
        self.assertEqual(yBlockHeights[0], 25.0)
        yBlockAxMesh = list(yBlockAxMesh)[0]
        self.assertIn(10.0, yBlockAxMesh)
        self.assertIn(25.0, yBlockAxMesh)
        self.assertIn(1, yBlockAxMesh)

    def test_plotBlockFlux(self):
        with TemporaryDirectoryChanger():
            xslib = isotxs.readBinary(ISOAA_PATH)
            self.r.core.lib = xslib

            blocks = self.r.core.getBlocks()
            for b in blocks:
                b.p.mgFlux = range(33)

            plotting.plotBlockFlux(self.r.core, fName="flux.png", bList=blocks)
            self.assertTrue(os.path.exists("flux.png"))
            plotting.plotBlockFlux(self.r.core, fName="peak.png", bList=blocks, peak=True)
            self._checkFileExists("peak.png")
            plotting.plotBlockFlux(
                self.r.core,
                fName="bList2.png",
                bList=blocks,
                bList2=blocks,
            )
            self._checkFileExists("bList2.png")

    def test_plotHexBlock(self):
        with TemporaryDirectoryChanger():
            first_fuel_block = self.r.core.getFirstBlock(Flags.FUEL)
            first_fuel_block.autoCreateSpatialGrids(self.r.core.spatialGrid)
            plotting.plotBlockDiagram(first_fuel_block, "blockDiagram23.svg", True)
            self._checkFileExists("blockDiagram23.svg")

    def test_plotCartesianBlock(self):
        with TemporaryDirectoryChanger():
            cs = settings.Settings(os.path.join(TESTING_ROOT, "c5g7", "c5g7-settings.yaml"))
            blueprint = blueprints.loadFromCs(cs)
            _ = reactors.factory(cs, blueprint)
            for name, bDesign in blueprint.blockDesigns.items():
                b = bDesign.construct(cs, blueprint, 0, 1, 1, "AA", {})
                plotting.plotBlockDiagram(b, "{}.svg".format(name), True)

            self._checkFileExists("uo2.svg")
            self._checkFileExists("mox.svg")

    def _checkFileExists(self, fName):
        self.assertTrue(os.path.exists(fName))


class TestPatches(unittest.TestCase):
    """Test the ability to correctly make patches."""

    def test_makeAssemPatches(self):
        # this one is flats-up with many assemblies in the core
        _, rHexFlatsUp = test_reactors.loadTestReactor()

        nAssems = len(rHexFlatsUp.core)
        self.assertGreater(nAssems, 1)
        patches = plotting._makeAssemPatches(rHexFlatsUp.core)
        self.assertEqual(len(patches), nAssems)

        # find the patch corresponding to the center assembly
        for patch in patches:
            if np.allclose(patch.xy, (0, 0)):
                break

        vertices = patch.get_verts()
        # there should be 1 more than the number of points in the shape
        self.assertEqual(len(vertices), 7)
        # for flats-up, the first vertex should have a y position of ~zero
        self.assertAlmostEqual(vertices[0][1], 0)

        # this one is corners-up, with only a single assembly
        _, rHexCornersUp = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")

        nAssems = len(rHexCornersUp.core)
        self.assertEqual(nAssems, 1)
        patches = plotting._makeAssemPatches(rHexCornersUp.core)
        self.assertEqual(len(patches), 1)

        vertices = patches[0].get_verts()
        self.assertEqual(len(vertices), 7)
        # for corners-up, the first vertex should have an x position of ~zero
        self.assertAlmostEqual(vertices[0][0], 0)

        # this one is cartestian, with many assemblies in the core
        _, rCartesian = test_reactors.loadTestReactor(inputFileName="refTestCartesian.yaml")

        nAssems = len(rCartesian.core)
        self.assertGreater(nAssems, 1)
        patches = plotting._makeAssemPatches(rCartesian.core)
        self.assertEqual(nAssems, len(patches))

        # Just pick a given patch and ensure that it is square-like. Orientation is not important here.
        vertices = patches[0].get_verts()
        self.assertEqual(len(vertices), 5)
