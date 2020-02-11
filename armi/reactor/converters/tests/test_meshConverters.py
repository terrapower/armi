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

        meshConvert = meshConverters.RZThetaReactorMeshConverterByRingCompositionAxialBins(
            self._converterSettings
        )
        meshConvert.generateMesh(self.r)

        self.assertListEqual(meshConvert.radialMesh, expectedRadialMesh)
        self.assertListEqual(meshConvert.axialMesh, expectedAxialMesh)
        self.assertListEqual(meshConvert.thetaMesh, expectedThetaMesh)

    def test_meshByRingCompositionAxialCoordinatesSmallCore(self):
        expectedRadialMesh = [2, 3, 4, 4, 5, 5, 6, 6, 6, 7, 8, 8, 9, 10]
        expectedAxialMesh = [25.0, 50.0, 175.0]
        expectedThetaMesh = [2 * math.pi]

        meshConvert = meshConverters.RZThetaReactorMeshConverterByRingCompositionAxialCoordinates(
            self._converterSettings
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

        meshConvert = meshConverters.RZThetaReactorMeshConverterByRingCompositionAxialBins(
            self._converterSettingsLargerCore
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

        meshConvert = meshConverters.RZThetaReactorMeshConverterByRingCompositionAxialCoordinates(
            self._converterSettingsLargerCore
        )
        meshConvert.generateMesh(self.r)

        self.assertListEqual(meshConvert.radialMesh, expectedRadialMesh)
        self.assertListEqual(meshConvert.axialMesh, expectedAxialMesh)
        self.assertListEqual(meshConvert.thetaMesh, expectedThetaMesh)


class AxialExpandNucs(unittest.TestCase):
    def setUp(self):
        self.o, self.r = loadTestReactor(TEST_ROOT)

    def test_getAxialExpansionNuclideAdjustList(self):
        nucs = meshConverters.getAxialExpansionNuclideAdjustList(self.r)
        expected = [
            "NP238",
            "LFP35",
            "PU242",
            "LFP39",
            "ZR94",
            "LFP38",
            "CM245",
            "PU241",
            "U235",
            "CM244",
            "ZR96",
            "AM243",
            "U236",
            "NP237",
            "U238",
            "AM242",
            "PU236",
            "ZR90",
            "LFP40",
            "DUMP2",
            "DUMP1",
            "CM242",
            "LFP41",
            "PU240",
            "CM246",
            "CM243",
            "PU238",
            "ZR92",
            "CM247",
            "AM241",
            "U234",
            "PU239",
            "ZR91",
        ]
        self.assertEqual(sorted(nucs), sorted(expected))

        nucs = meshConverters.getAxialExpansionNuclideAdjustList(
            self.r, [Flags.FUEL, Flags.CLAD]
        )
        expected = [
            "U235",
            "U238",
            "ZR90",
            "ZR91",
            "ZR92",
            "ZR94",
            "ZR96",
            "NP237",
            "LFP38",
            "DUMP1",
            "PU239",
            "NP238",
            "PU236",
            "U236",
            "DUMP2",
            "PU238",
            "LFP35",
            "LFP39",
            "PU240",
            "LFP40",
            "PU241",
            "LFP41",
            "PU242",
            "AM241",
            "CM242",
            "AM242",
            "CM243",
            "U234",
            "AM243",
            "CM244",
            "CM245",
            "CM246",
            "CM247",
            "C",
            "V",
            "CR50",
            "CR52",
            "CR53",
            "CR54",
            "FE54",
            "FE56",
            "FE57",
            "FE58",
            "MO92",
            "MO94",
            "MO95",
            "MO96",
            "MO97",
            "MO98",
            "MO100",
            "NI58",
            "NI60",
            "NI61",
            "NI62",
            "NI64",
            "SI28",
            "SI29",
            "SI30",
            "MN55",
            "W182",
            "W183",
            "W184",
            "W186",
        ]
        self.assertEqual(sorted(nucs), sorted(expected))


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'TestRZReactorMeshConverter.test_meshByRingCompositionAxialBinsSmallCore']
    unittest.main()
