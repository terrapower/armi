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

import unittest

from armi import nuclearDataIO
from armi.nucDirectory import nuclideBases
from armi.nuclearDataIO import xsLibraries
from armi.nuclearDataIO.cccc import isotxs
from armi.tests import ISOAA_PATH
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class TestIsotxs(unittest.TestCase):
    """Tests the ISOTXS class."""

    @classmethod
    def setUpClass(cls):
        # load a library that is in the ARMI tree. This should
        # be a small library with LFPs, Actinides, structure, and coolant
        cls.lib = isotxs.readBinary(ISOAA_PATH)

    def test_writeBinary(self):
        """Test reading in an ISOTXS file, and then writing it back out again.

        Now, the library here can't guarantee the output will be the same as the
        input. But we can guarantee the  written file is still valid, by reading
        it again.

        .. test:: Write ISOTSX binary files.
            :id: T_ARMI_NUCDATA_ISOTXS0
            :tests: R_ARMI_NUCDATA_ISOTXS
        """
        with TemporaryDirectoryChanger():
            origLib = isotxs.readBinary(ISOAA_PATH)

            fname = self._testMethodName + "temp-aa.isotxs"
            isotxs.writeBinary(origLib, fname)
            lib = isotxs.readBinary(fname)

            # validate the written file is still valid
            nucs = lib.nuclides
            self.assertTrue(nucs)
            self.assertIn("AA", lib.xsIDs)
            nuc = lib["U235AA"]
            self.assertIsNotNone(nuc)
            with self.assertRaises(KeyError):
                lib.getNuclide("nonexistent", "zz")

    def test_isotxsGeneralData(self):
        nucs = self.lib.nuclides
        self.assertTrue(nucs)
        self.assertIn("AA", self.lib.xsIDs)
        nuc = self.lib["U235AA"]
        self.assertIsNotNone(nuc)
        with self.assertRaises(KeyError):
            self.lib.getNuclide("nonexistent", "zz")

    def test_isotxsDetailedData(self):
        self.assertEqual(50, len(self.lib.nuclides))
        groups = self.lib.neutronEnergyUpperBounds
        self.assertEqual(33, len(groups))
        self.assertEqual(14072911.0, max(groups))
        self.assertEqual(0.4139941930770874, min(groups))
        # file-wide chi
        self.assertEqual(33, len(self.lib.isotxsMetadata["chi"]))
        self.assertEqual(1.0000016745038094, sum(self.lib.isotxsMetadata["chi"]))

    def test_getScatteringWeights(self):
        self.assertEqual(1650, len(self.lib.getScatterWeights()))
        refVector = [
            0.0,
            0.9924760291647134,
            0.007523970835286507,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]
        for v1, v2 in zip(refVector, self.lib.getScatterWeights()["U235AA", 1].todense().T.tolist()[0]):
            self.assertAlmostEqual(v1, v2)

    def test_getNuclide(self):
        self.assertEqual(nuclideBases.byName["U235"], self.lib.getNuclide("U235", "AA")._base)
        self.assertEqual(nuclideBases.byName["PU239"], self.lib.getNuclide("PU239", "AA")._base)

    def test_n2nIsReactionBased(self):
        """
        ARMI assumes ISOTXS n2n reactions are all reaction-based. Test this.

        The alternative is production based.
        Previous studies show that MC**2-2 is reaction based.
        """
        nuc = self.lib.getNuclide("U235", "AA")
        fromMatrix = nuc.micros.n2nScatter.sum(axis=0).getA1()  # convert to ndarray
        for base, matrix in zip(fromMatrix, nuc.micros.n2n):
            self.assertAlmostEqual(base, matrix)

    def test_getScatterWeights(self):
        scatWeights = self.lib.getScatterWeights()
        vals = scatWeights["U235AA", 4]
        self.assertAlmostEqual(sum(vals), 1.0)

    def test_getISOTXSFileName(self):
        self.assertEqual(nuclearDataIO.getExpectedISOTXSFileName(cycle=0), "ISOTXS-c0")
        self.assertEqual(nuclearDataIO.getExpectedISOTXSFileName(cycle=1), "ISOTXS-c1")
        self.assertEqual(nuclearDataIO.getExpectedISOTXSFileName(cycle=0, node=1), "ISOTXS-c0n1")
        self.assertEqual(nuclearDataIO.getExpectedISOTXSFileName(cycle=23), "ISOTXS-c23")
        self.assertEqual(nuclearDataIO.getExpectedISOTXSFileName(xsID="AA"), "ISOAA")
        self.assertEqual(
            nuclearDataIO.getExpectedISOTXSFileName(xsID="AA", suffix="test"),
            "ISOAA-test",
        )
        self.assertEqual(nuclearDataIO.getExpectedISOTXSFileName(), "ISOTXS")
        with self.assertRaises(ValueError):
            # Error when over specified
            nuclearDataIO.getExpectedISOTXSFileName(cycle=10, xsID="AA")

    def test_getGAMISOFileName(self):
        self.assertEqual(nuclearDataIO.getExpectedGAMISOFileName(cycle=0), "cycle0.gamiso")
        self.assertEqual(nuclearDataIO.getExpectedGAMISOFileName(cycle=1), "cycle1.gamiso")
        self.assertEqual(
            nuclearDataIO.getExpectedGAMISOFileName(cycle=1, node=3),
            "cycle1node3.gamiso",
        )
        self.assertEqual(nuclearDataIO.getExpectedGAMISOFileName(cycle=23), "cycle23.gamiso")
        self.assertEqual(nuclearDataIO.getExpectedGAMISOFileName(xsID="AA"), "AA.gamiso")
        self.assertEqual(
            nuclearDataIO.getExpectedGAMISOFileName(xsID="AA", suffix="test"),
            "AA-test.gamiso",
        )
        self.assertEqual(nuclearDataIO.getExpectedGAMISOFileName(), "GAMISO")
        with self.assertRaises(ValueError):
            # Error when over specified
            nuclearDataIO.getExpectedGAMISOFileName(cycle=10, xsID="AA")


class Isotxs_merge_Tests(unittest.TestCase):
    def test_mergeMccV2FilesRemovesTheFileWideChi(self):
        """Test merging ISOTXS files.

        .. test:: Read ISOTXS files.
            :id: T_ARMI_NUCDATA_ISOTXS1
            :tests: R_ARMI_NUCDATA_ISOTXS
        """
        isoaa = isotxs.readBinary(ISOAA_PATH)
        self.assertAlmostEqual(1.0, sum(isoaa.isotxsMetadata["chi"]), 5)
        self.assertAlmostEqual(1, isoaa.isotxsMetadata["fileWideChiFlag"])
        someIsotxs = xsLibraries.IsotxsLibrary()
        # semi-copy...
        someIsotxs.merge(isoaa)
        self.assertAlmostEqual(1.0, sum(someIsotxs.isotxsMetadata["chi"]), 5)
        self.assertEqual(1, someIsotxs.isotxsMetadata["fileWideChiFlag"])
        # OK, now I need to delete all the nuclides, so we can merge again.
        for key in someIsotxs.nuclideLabels:
            del someIsotxs[key]
        someIsotxs.merge(isotxs.readBinary(ISOAA_PATH))
        self.assertEqual(None, someIsotxs.isotxsMetadata["chi"])
