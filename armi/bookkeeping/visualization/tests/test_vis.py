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

"""Test report visualization."""

import unittest

import numpy as np
from pyevtk.vtk import VtkTetra

from armi import settings
from armi.bookkeeping.db import Database
from armi.bookkeeping.visualization import utils, vtk, xdmf
from armi.reactor import blocks, components
from armi.reactor.tests import test_reactors
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class TestVtkMesh(unittest.TestCase):
    """Test the VtkMesh utility class."""

    def test_testVtkMesh(self):
        mesh = utils.VtkMesh.empty()

        self.assertEqual(mesh.vertices.size, 0)
        self.assertEqual(mesh.vertices.shape, (0, 3))
        self.assertEqual(mesh.connectivity.size, 0)
        self.assertEqual(mesh.offsets.size, 0)
        self.assertEqual(mesh.cellTypes.size, 0)

        verts = np.array([[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.25, 0.25, 0.5]])
        conn = np.array([0, 1, 2, 3])
        offsets = np.array([4])
        cellTypes = np.array([VtkTetra.tid])
        newMesh = utils.VtkMesh(verts, conn, offsets, cellTypes)

        mesh.append(newMesh)
        mesh.append(newMesh)

        self.assertEqual(mesh.vertices.size, 3 * 8)
        self.assertEqual(mesh.offsets.size, 2)
        self.assertEqual(mesh.connectivity.size, 8)
        self.assertEqual(mesh.cellTypes.size, 2)

        self.assertEqual(mesh.offsets[-1], 8)
        self.assertEqual(mesh.connectivity[-1], 7)


class TestVisDump(unittest.TestCase):
    """Test dumping a whole reactor and some specific block types."""

    @classmethod
    def setUpClass(cls):
        caseSetting = settings.Settings()
        _, cls.r = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")

        cls.hexBlock = next(cls.r.core.iterBlocks())

        cls.cartesianBlock = blocks.CartesianBlock("TestCartesianBlock", caseSetting)
        cartesianComponent = components.HoledSquare(
            "duct",
            "UZr",
            Tinput=273.0,
            Thot=273.0,
            holeOD=68.0,
            widthOuter=12.5,
            mult=1.0,
        )
        cls.cartesianBlock.add(cartesianComponent)
        cls.cartesianBlock.add(components.Circle("clad", "HT9", Tinput=273.0, Thot=273.0, od=68.0, mult=169.0))

    def test_dumpReactorVtk(self):
        # This does a lot, and is hard to verify. at least make sure it doesn't crash
        with TemporaryDirectoryChanger(dumpOnException=False):
            dumper = vtk.VtkDumper("testVtk", inputName=None)
            with dumper:
                dumper.dumpState(self.r)

    def test_dumpReactorXdmf(self):
        # This does a lot, and is hard to verify. at least make sure it doesn't crash
        with TemporaryDirectoryChanger(dumpOnException=False):
            db = Database("testDatabase.h5", "w")
            with db:
                db.writeToDB(self.r)
            dumper = xdmf.XdmfDumper("testVtk", inputName="testDatabase.h5")
            with dumper:
                dumper.dumpState(self.r)

    def test_hexMesh(self):
        mesh = utils.createBlockMesh(self.hexBlock)

        self.assertEqual(mesh.vertices.size, 12 * 3)
        self.assertEqual(mesh.cellTypes[0], 16)

    def test_cartesianMesh(self):
        mesh = utils.createBlockMesh(self.cartesianBlock)

        self.assertEqual(mesh.vertices.size, 8 * 3)
        self.assertEqual(mesh.cellTypes[0], 12)
