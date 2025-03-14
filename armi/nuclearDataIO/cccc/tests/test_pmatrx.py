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
"""Tests the workings of the library wrappers."""

import filecmp
import unittest

from armi import nuclearDataIO
from armi.nuclearDataIO.cccc import pmatrx
from armi.nuclearDataIO.tests import test_xsLibraries
from armi.utils import properties
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class TestPmatrxNuclides(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # load a library that is in the ARMI tree. This should
        # be a small library with LFPs, Actinides, structure, and coolant
        cls.libAA = pmatrx.readBinary(test_xsLibraries.PMATRX_AA)
        cls.libAB = pmatrx.readBinary(test_xsLibraries.PMATRX_AB)

    def _nuclideGeneralHelper(self, u235):
        self.assertEqual(0, len(u235.pmatrxMetadata["activationXS"]))
        self.assertEqual(0, len(u235.pmatrxMetadata["activationMT"]))
        self.assertEqual(0, len(u235.pmatrxMetadata["activationMTU"]))
        self.assertEqual(33, len(u235.neutronHeating))
        self.assertEqual(33, len(u235.neutronDamage))
        self.assertEqual(21, len(u235.gammaHeating))
        # if there are more scattering orders, should add tests for them as well...
        self.assertEqual(1, u235.pmatrxMetadata["maxScatteringOrder"])
        self.assertEqual((21, 33), u235.isotropicProduction.shape)

    def test_pmatrxNuclideDataAA(self):
        self._nuclideGeneralHelper(self.libAA["U235AA"])

    def test_pmatrxNuclideDataAB(self):
        self._nuclideGeneralHelper(self.libAB["U235AB"])

    def test_nuclideDataIsDifferent(self):
        aa = self.libAA["U235AA"]
        ab = self.libAB["U235AB"]
        self.assertFalse((aa.isotropicProduction == ab.isotropicProduction).all())

    def test_getPMATRXFileName(self):
        self.assertEqual(nuclearDataIO.getExpectedPMATRXFileName(cycle=0), "cycle0.pmatrx")
        self.assertEqual(nuclearDataIO.getExpectedPMATRXFileName(cycle=1), "cycle1.pmatrx")
        self.assertEqual(nuclearDataIO.getExpectedPMATRXFileName(cycle=23), "cycle23.pmatrx")
        self.assertEqual(nuclearDataIO.getExpectedPMATRXFileName(xsID="AA"), "AA.pmatrx")
        self.assertEqual(
            nuclearDataIO.getExpectedPMATRXFileName(xsID="AA", suffix="test"),
            "AA-test.pmatrx",
        )
        self.assertEqual(nuclearDataIO.getExpectedPMATRXFileName(), "PMATRX")
        with self.assertRaises(ValueError):
            # Error when over specified
            nuclearDataIO.getExpectedPMATRXFileName(cycle=10, xsID="AA")


class TestPmatrx(unittest.TestCase):
    """Tests the Pmatrx gamma production matrix."""

    @classmethod
    def setUpClass(cls):
        # load a library that is in the ARMI tree. This should
        # be a small library with LFPs, Actinides, structure, and coolant
        cls.lib = pmatrx.readBinary(test_xsLibraries.PMATRX_AA)

    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    def test_pmatrxGammaEnergies(self):
        energies = [
            20000000.0,
            10000000.0,
            8000000.0,
            7000000.0,
            6000000.0,
            5000000.0,
            4000000.0,
            3000000.0,
            2500000.0,
            2000000.0,
            1500000.0,
            1000000.0,
            700000.0,
            450000.0,
            300000.0,
            150000.0,
            100000.0,
            74999.8984375,
            45000.0,
            30000.0,
            20000.0,
        ]
        self.assertTrue((energies == self.lib.gammaEnergyUpperBounds).all())

    def test_pmatrxNeutronEnergies(self):
        energies = [
            14190675.0,
            10000000.0,
            6065306.5,
            3678794.75,
            2231302.0,
            1353353.125,
            820850.0,
            497870.625,
            301973.75,
            183156.34375,
            111089.875,
            67379.390625,
            40867.66796875,
            24787.498046875,
            15034.3779296875,
            9118.810546875,
            5530.8388671875,
            3354.624267578125,
            2034.6827392578125,
            1234.097412109375,
            748.5178833007812,
            453.9991149902344,
            275.36444091796875,
            167.01695251464844,
            101.30089569091797,
            61.44210433959961,
            37.26651382446289,
            22.6032772064209,
            13.709582328796387,
            8.31528091430664,
            3.9278604984283447,
            0.5315780639648438,
            0.41745778918266296,
        ]
        self.assertTrue((energies == self.lib.neutronEnergyUpperBounds).all())

    def test_pmatrxNuclideNames(self):
        names = [
            "U235AA",
            "U238AA",
            "PU39AA",
            "FE54AA",
            "FE56AA",
            "FE57AA",
            "FE58AA",
            "NA23AA",
            "ZR90AA",
            "ZR91AA",
            "ZR92AA",
            "ZR93AA",
            "ZR94AA",
            "ZR95AA",
            "ZR96AA",
            "XE28AA",
            "XE29AA",
            "XE30AA",
            "XE31AA",
            "XE32AA",
            "XE33AA",
            "XE34AA",
            "XE35AA",
            "XE36AA",
            "FP40AA",
        ]
        self.assertEqual(names, self.lib.nuclideLabels)

    def test_pmatrxDoesntHaveDoseConversionFactors(self):
        with self.assertRaises(properties.ImmutablePropertyError):
            _bacon = self.lib.neutronDoseConversionFactors
        with self.assertRaises(properties.ImmutablePropertyError):
            _turkey = self.lib.gammaDoseConversionFactors
        # bravo!


class TestProductionMatrix_FromWritten(TestPmatrx):
    """
    Tests related to reading a PMATRX that was written by ARMI.

    Note that this runs all the tests from TestPmatrx.
    """

    def test_writtenIsIdenticalToOriginal(self):
        """Make sure our writer produces something identical to the original.

        .. test:: Test reading and writing PMATRIX files.
            :id: T_ARMI_NUCDATA_PMATRX
            :tests: R_ARMI_NUCDATA_PMATRX
        """
        origLib = pmatrx.readBinary(test_xsLibraries.PMATRX_AA)

        fname = self._testMethodName + "temp-aa.pmatrx"
        pmatrx.writeBinary(origLib, fname)
        _lib = pmatrx.readBinary(fname)

        self.assertTrue(filecmp.cmp(test_xsLibraries.PMATRX_AA, fname))


class TestProductionMatrix_FromWrittenAscii(TestPmatrx):
    """
    Tests that show you can read and write pmatrx files from ascii libraries.

    Notes
    -----
    This runs all the tests from TestPmatrx.
    """

    @classmethod
    def setUpClass(cls):
        cls.origLib = pmatrx.readBinary(test_xsLibraries.PMATRX_AA)

    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

        self.fname = self._testMethodName + "temp-aa.pmatrx.ascii"
        lib = pmatrx.readBinary(test_xsLibraries.PMATRX_AA)
        pmatrx.writeAscii(lib, self.fname)
        self.lib = pmatrx.readAscii(self.fname)

    def tearDown(self):
        self.td.__exit__(None, None, None)
