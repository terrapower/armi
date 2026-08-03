# Copyright 2026 TerraPower, LLC
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

"""Unit tests on the mass redistribution class.

These are limited in scope. More extensive testing is done in test_axialExpansionChanger_MultiPin.py
"""

from unittest import TestCase

import numpy as np

from armi.reactor.components import Circle
from armi.reactor.converters.axialExpansionChanger.redistributeMass import RedistributeMass


class BlockLike:
    """Stand in for a component's parent."""

    def __init__(self, height: float):
        self.height = height

    def getHeight(self):
        """Produce the block height."""
        return self.height

    @staticmethod
    def getSymmetryFactor():
        return 1


class TestMassRedistribution(TestCase):
    def setUp(self):
        self.fromComp = Circle("fuel", "UZr", Tinput=500, Thot=500, od=1.0, mult=3)
        self.fromComp.parent = BlockLike(7.3)
        self.toComp = Circle("fuel", "UZr", Tinput=500, Thot=500, od=1.0, mult=3)
        # Arbitrary post-expansion height of the component prior to the truncation / extension
        self.toComp.height = 3.74
        self.toComp.parent = BlockLike(self.toComp.height)

        # Height of fromComp to be shifted to toComp
        self.dz = 0.6
        self.distributor = RedistributeMass(
            fromComp=self.fromComp, toComp=self.toComp, deltaZTop=self.dz, assemName=self._testMethodName, initOnly=True
        )

    def test_noUpdateMisMatchedPinNDens(self):
        """Pin number density is only updated if both components have `pinNDens` populated."""
        # neither have pin ndens => no update
        self.toComp.p.pinNDens = None
        self.fromComp.p.pinNDens = None
        self.assertFalse(self.distributor._adjustPinNDens())
        # generate random sample pNDens data
        rng = np.random.default_rng()
        pinDensShape = (7, 3)  # arbitrary
        sampleData = rng.uniform(low=0, high=1e-2, size=pinDensShape).astype(np.float32)

    # only fromComp has pin ndens => no update
        self.fromComp.p.pinNDens = sampleData
        self.assertFalse(self.distributor._adjustPinNDens())

    # only toComp has pin ndens => no update
        self.fromComp.p.pinNDens = None
        self.toComp.p.pinNDens = sampleData
        self.assertFalse(self.distributor._adjustPinNDens())

    def test_updatedPinNDens(self):
        """Test the ability to shift pin ndens between components."""
        rng = np.random.default_rng()
        pinDensShape = (11, 5)  # arbitrary
        self.fromComp.p.pinNDens = rng.uniform(low=0, high=1e-2, size=pinDensShape).astype(np.float32)
        self.toComp.p.pinNDens = rng.uniform(low=0, high=1e-2, size=pinDensShape).astype(np.float32)

        initialFromPinDens = self.fromComp.p.pinNDens.copy()
        initialToPinDens = self.toComp.p.pinNDens.copy()
        toVol = self.toComp.height * self.toComp.getArea()
        fromVol = self.dz * self.fromComp.getArea()
        expected = (initialToPinDens * toVol + initialFromPinDens * fromVol) / (fromVol + toVol)

        self.assertTrue(self.distributor._adjustPinNDens())
        # no change in from comp
        np.testing.assert_allclose(self.fromComp.p.pinNDens, initialFromPinDens)
        np.testing.assert_allclose(self.toComp.p.pinNDens, expected, rtol=1e-5)

    def test_updatedDetailedNDens(self):
        """Test the ability to shift detailed ndens between components."""
        rng = np.random.default_rng()
        nDetailedNucs = 123  # arbitrary
        self.fromComp.p.detailedNDens = rng.uniform(low=0, high=1e-2, size=nDetailedNucs)
        self.toComp.p.detailedNDens = rng.uniform(low=0, high=1e-2, size=nDetailedNucs)

        initialFromDetailedDens = self.fromComp.p.detailedNDens.copy()
        initialToDetailedDens = self.toComp.p.detailedNDens.copy()
        toVol = self.toComp.height * self.toComp.getArea()
        fromVol = self.dz * self.fromComp.getArea()
        expected = (initialToDetailedDens * toVol + initialFromDetailedDens * fromVol) / (fromVol + toVol)

        self.assertTrue(self.distributor._adjustDetailedNDens())
        # no change in from comp
        np.testing.assert_allclose(self.fromComp.p.detailedNDens, initialFromDetailedDens)
        np.testing.assert_allclose(self.toComp.p.detailedNDens, expected, rtol=1e-5)

    def test_volumes(self):
        """Test the volume properties.

        Even relatively simple functionality deserves low-level unit testing.
        """
        self.assertAlmostEqual(
            self.distributor.fromCompVolume,
            self.fromComp.getArea() * self.dz,
        )
        self.assertAlmostEqual(
            self.distributor.toCompVolume,
            self.toComp.getArea() * self.toComp.height,
        )
        self.assertAlmostEqual(
            self.distributor.newVolume, self.distributor.toCompVolume + self.distributor.fromCompVolume
        )
