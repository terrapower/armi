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

"""Test loading Theta-RZ reactor models."""

import math
import os
import unittest

from armi import settings
from armi.reactor import reactors
from armi.testing import TESTING_ROOT


class TestRZTReactorModern(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cs = settings.Settings(fName=os.path.join(TESTING_ROOT, "reactors", "godiva", "godiva.armi.unittest.yaml"))
        cls.r = reactors.loadFromCs(cs)

    def test_loadRZT_reactor(self):
        """
        The Godiva benchmark model is a HEU sphere with a radius of 8.74 cm.

        This tests loading and verifies the reactor is loaded correctly by comparing volumes against
        expected volumes for full core (including void boundary conditions) and just the fuel.
        """
        godivaRadius = 8.7407
        reactorRadius = 9
        reactorHeight = 17.5
        refReactorVolume = math.pi * reactorRadius**2 * reactorHeight / 8
        refFuelVolume = 4.0 / 3.0 * math.pi * (godivaRadius) ** 3 / 8

        reactorVolumes = []
        fuelVolumes = []
        for b in self.r.core.iterBlocks():
            reactorVolumes.append(b.getVolume())
            for c in b:
                if "godiva" in c.name:
                    fuelVolumes.append(c.getVolume())

        # verify the total reactor volume is as expected
        tolerance = 1e-3
        error = math.fabs((refReactorVolume - sum(reactorVolumes)) / refReactorVolume)
        self.assertLess(error, tolerance)

        # verify the total fuel volume is as expected
        error = math.fabs((refFuelVolume - sum(fuelVolumes)) / refFuelVolume)
        self.assertLess(error, tolerance)

    def test_loadRZT(self):
        self.assertEqual(len(self.r.core), 3)
        radMeshes = [a.p.RadMesh for a in self.r.core]
        aziMeshes = [a.p.AziMesh for a in self.r.core]
        print(f"radMeshes: {radMeshes}")
        print(f"aziMeshes: {aziMeshes}")
        self.assertTrue(all(radMesh == 2 for radMesh in radMeshes))
        self.assertTrue(all(aziMesh == 7 for aziMesh in aziMeshes))

    def test_findAllMeshPoints(self):
        """Test findAllMeshPoints()."""
        i, _, _ = self.r.core.findAllMeshPoints()
        self.assertLess(i[-1], 2 * math.pi)
