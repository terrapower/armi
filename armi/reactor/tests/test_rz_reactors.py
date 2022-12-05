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

"""
Test loading Theta-RZ reactor models.
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import math
import os
import unittest

from armi import settings
from armi.tests import TEST_ROOT
from armi.reactor import reactors


class Test_RZT_Reactor(unittest.TestCase):
    """Tests for RZT reactors."""

    @classmethod
    def setUpClass(cls):
        cs = settings.Settings(fName=os.path.join(TEST_ROOT, "ThRZSettings.yaml"))
        cls.r = reactors.loadFromCs(cs)

    def test_loadRZT(self):
        self.assertEqual(len(self.r.core), 14)
        radMeshes = [a.p.RadMesh for a in self.r.core]
        aziMeshes = [a.p.AziMesh for a in self.r.core]
        self.assertTrue(all(radMesh == 6 for radMesh in radMeshes))
        self.assertTrue(all(aziMesh == 8 for aziMesh in aziMeshes))

    def test_findAllMeshPoints(self):
        i, _, _ = self.r.core.findAllMeshPoints()
        self.assertLess(i[-1], 2 * math.pi)


class Test_RZT_Reactor_modern(unittest.TestCase):
    def test_loadRZT_reactor(self):
        """
        The Godiva benchmark model is a Sphere of UZr with a diameter of 30cm

        This unit tests loading and verifies the reactor is loaded correctly by
        comparing volumes against expected volumes for full core (including
        void boundary conditions) and just the fuel
        """
        cs = settings.Settings(
            fName=os.path.join(TEST_ROOT, "Godiva.armi.criticality.yaml")
        )
        r = reactors.loadFromCs(cs)

        diameter_cm = 30
        height_cm = diameter_cm

        ref_reactor_volume = math.pi / 4.0 * diameter_cm ** 2 * height_cm / 8
        ref_fuel_volume = 4.0 / 3.0 * math.pi * (diameter_cm / 2) ** 3 / 8

        reactor_volumes = []
        fuel_volumes = []
        for b in r.core.getBlocks():
            reactor_volumes.append(b.getVolume())
            for c in b:
                if "Godiva" in c.name:
                    fuel_volumes.append(c.getVolume())
        """
        verify the total reactor volume is as expected
        """
        tolerance = 1e-3
        error = math.fabs(
            (ref_reactor_volume - sum(reactor_volumes)) / ref_reactor_volume
        )
        self.assertLess(error, tolerance)

        """
        verify the total fuel volume is as expected
        """
        error = math.fabs((ref_fuel_volume - sum(fuel_volumes)) / ref_fuel_volume)
        self.assertLess(error, tolerance)


if __name__ == "__main__":
    unittest.main()
