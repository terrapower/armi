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

import unittest
import math

from armi.reactor.tests.test_reactors import loadTestReactor
from armi.reactor.flags import Flags
from armi.reactor.converters import meshConverters, geometryConverters
from armi.tests import TEST_ROOT


class TestRZReactorMeshConverter(unittest.TestCase):
    """
    Loads a hex reactor and converts its mesh to RZTheta coordinates
    """

    def setUp(self):
        self.o, self.r = loadTestReactor(TEST_ROOT)
        self._converterSettings = {
            "uniformThetaMesh": True,
            "thetaBins": 1,
            "thetaMesh": [2 * math.pi],
            "axialMesh": [25.0, 50.0, 174.0],
            "axialSegsPerBin": 1,
        }

    def test_meshByRingCompositionAxialBinsSmallCore(self):
        expectedRadialMesh = [2, 3, 4, 4, 5, 5, 6, 6, 6, 7, 8, 8, 9, 10]
        expectedAxialMesh = [25.0, 50.0, 75.0, 100.0, 175.0]
        expectedThetaMesh = [2 * math.pi]

        meshConvert = (
            meshConverters.RZThetaReactorMeshConverterByRingCompositionAxialBins(
                self._converterSettings
            )
        )
        meshConvert.generateMesh(self.r)

        self.assertListEqual(meshConvert.radialMesh, expectedRadialMesh)
        self.assertListEqual(meshConvert.axialMesh, expectedAxialMesh)
        self.assertListEqual(meshConvert.thetaMesh, expectedThetaMesh)

    def test_meshByRingCompositionAxialCoordinatesSmallCore(self):
        expectedRadialMesh = [2, 3, 4, 4, 5, 5, 6, 6, 6, 7, 8, 8, 9, 10]
        expectedAxialMesh = [25.0, 50.0, 175.0]
        expectedThetaMesh = [2 * math.pi]

        meshConvert = (
            meshConverters.RZThetaReactorMeshConverterByRingCompositionAxialCoordinates(
                self._converterSettings
            )
        )
        meshConvert.generateMesh(self.r)

        self.assertListEqual(meshConvert.radialMesh, expectedRadialMesh)
        self.assertListEqual(meshConvert.axialMesh, expectedAxialMesh)
        self.assertListEqual(meshConvert.thetaMesh, expectedThetaMesh)

    def _growReactor(self):
        modifier = geometryConverters.FuelAssemNumModifier(self.o.cs)
        modifier.numFuelAssems = 1
        modifier.ringsToAdd = 9 * ["igniter fuel"] + 1 * ["radial shield"]
        modifier.convert(self.r)
        self._converterSettingsLargerCore = {
            "uniformThetaMesh": True,
            "thetaBins": 1,
            "thetaMesh": [2 * math.pi],
            "axialMesh": [25.0, 30.0, 60.0, 90.0, 105.2151, 152.0, 174.0],
            "axialSegsPerBin": 2,
        }

    def test_meshByRingCompositionAxialBinsLargeCore(self):
        self._growReactor()
        expectedRadialMesh = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 12, 13]
        expectedAxialMesh = [50.0, 100.0, 175.0]
        expectedThetaMesh = [2 * math.pi]

        meshConvert = (
            meshConverters.RZThetaReactorMeshConverterByRingCompositionAxialBins(
                self._converterSettingsLargerCore
            )
        )
        meshConvert.generateMesh(self.r)

        self.assertListEqual(meshConvert.radialMesh, expectedRadialMesh)
        self.assertListEqual(meshConvert.axialMesh, expectedAxialMesh)
        self.assertListEqual(meshConvert.thetaMesh, expectedThetaMesh)

    def test_meshByRingCompositionAxialCoordinatesLargeCore(self):
        self._growReactor()
        expectedRadialMesh = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 12, 13]
        expectedAxialMesh = [25.0, 30.0, 60.0, 90.0, 105.2151, 152.0, 175.0]
        expectedThetaMesh = [2 * math.pi]

        meshConvert = (
            meshConverters.RZThetaReactorMeshConverterByRingCompositionAxialCoordinates(
                self._converterSettingsLargerCore
            )
        )
        meshConvert.generateMesh(self.r)

        self.assertListEqual(meshConvert.radialMesh, expectedRadialMesh)
        self.assertListEqual(meshConvert.axialMesh, expectedAxialMesh)
        self.assertListEqual(meshConvert.thetaMesh, expectedThetaMesh)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'TestRZReactorMeshConverter.test_meshByRingCompositionAxialBinsSmallCore']
    unittest.main()
