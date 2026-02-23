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
"""Tests for xsLibraries.IsotxsLibrary."""

import copy
import filecmp
import os
import pickle
import traceback
import unittest
from time import sleep

import numpy as np

from armi.nucDirectory.nuclideBases import NuclideBases
from armi.nuclearDataIO import xsLibraries
from armi.nuclearDataIO.cccc import gamiso, isotxs, pmatrx
from armi.tests import mockRunLogs
from armi.utils import properties
from armi.utils.directoryChangers import TemporaryDirectoryChanger

THIS_DIR = os.path.dirname(__file__)
RUN_DIR = os.path.join(THIS_DIR, "library-file-generation")
FIXTURE_DIR = os.path.join(THIS_DIR, "fixtures")
# CCCC fixtures are less fancy than these merging ones.
FIXTURE_DIR_CCCC = os.path.join(os.path.dirname(isotxs.__file__), "tests", "fixtures")

ISOTXS_AA = os.path.join(FIXTURE_DIR, "ISOAA")
ISOTXS_AB = os.path.join(FIXTURE_DIR, "ISOAB")
ISOTXS_AA_AB = os.path.join(FIXTURE_DIR, "combined-AA-AB.isotxs")
ISOTXS_LUMPED = os.path.join(FIXTURE_DIR, "combined-and-lumped-AA-AB.isotxs")

PMATRX_AA = os.path.join(FIXTURE_DIR, "AA.pmatrx")
PMATRX_AB = os.path.join(FIXTURE_DIR, "AB.pmatrx")
PMATRX_AA_AB = os.path.join(FIXTURE_DIR, "combined-AA-AB.pmatrx")
PMATRX_LUMPED = os.path.join(FIXTURE_DIR, "combined-and-lumped-AA-AB.pmatrx")

GAMISO_AA = os.path.join(FIXTURE_DIR, "AA.gamiso")
GAMISO_AB = os.path.join(FIXTURE_DIR, "AB.gamiso")
GAMISO_AA_AB = os.path.join(FIXTURE_DIR, "combined-AA-AB.gamiso")
GAMISO_LUMPED = os.path.join(FIXTURE_DIR, "combined-and-lumped-AA-AB.gamiso")

DLAYXS_MCC3 = os.path.join(FIXTURE_DIR_CCCC, "mc2v3.dlayxs")
UFG_FLUX_EDIT = os.path.join(FIXTURE_DIR, "mc2v3-AA.flux_ufg")


class TempFileMixin:
    """Not a test; just helpful test tooling."""

    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    @property
    def testFileName(self):
        return os.path.join(self.td.destination, f"{self.__class__.__name__}-{self._testMethodName}.nucdata")


class TestXSLibrary(TempFileMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.isotxsAA = isotxs.readBinary(ISOTXS_AA)
        cls.gamisoAA = gamiso.readBinary(GAMISO_AA)
        cls.pmatrxAA = pmatrx.readBinary(PMATRX_AA)
        cls.xsLib = xsLibraries.IsotxsLibrary()
        cls.xsLibGenerationErrorStack = None
        try:
            cls.xsLib.merge(copy.deepcopy(cls.isotxsAA))
            cls.xsLib.merge(copy.deepcopy(cls.gamisoAA))
            cls.xsLib.merge(copy.deepcopy(cls.pmatrxAA))
        except Exception:
            cls.xsLibGenerationErrorStack = traceback.format_exc()

    def test_canPickleAndUnpickleISOTXS(self):
        pikAA = pickle.loads(pickle.dumps(self.isotxsAA))
        self.assertTrue(xsLibraries.compare(pikAA, self.isotxsAA))

    def test_canPickleAndUnpickleGAMISO(self):
        pikAA = pickle.loads(pickle.dumps(self.gamisoAA))
        self.assertTrue(xsLibraries.compare(pikAA, self.gamisoAA))

    def test_canPickleAndUnpicklePMATRX(self):
        pikAA = pickle.loads(pickle.dumps(self.pmatrxAA))
        self.assertTrue(xsLibraries.compare(pikAA, self.pmatrxAA))

    def test_compareWorks(self):
        self.assertTrue(xsLibraries.compare(self.isotxsAA, self.isotxsAA))
        self.assertTrue(xsLibraries.compare(self.pmatrxAA, self.pmatrxAA))
        aa = isotxs.readBinary(ISOTXS_AA)
        del aa[aa.nuclideLabels[0]]
        self.assertFalse(xsLibraries.compare(aa, self.isotxsAA))

    def test_compareComponentsOfXSLibrary(self):
        """Compare different components of a XS library."""
        self.assertTrue(xsLibraries.compare(self.isotxsAA, self.isotxsAA))
        self.assertTrue(xsLibraries.compare(self.pmatrxAA, self.pmatrxAA))
        aa = isotxs.readBinary(ISOTXS_AA)
        del aa[aa.nuclideLabels[0]]
        self.assertFalse(xsLibraries.compare(aa, self.isotxsAA))

    def test_mergeFailsWithNonIsotxsFiles(self):
        dummyFileName = "ISOSOMEFILE"
        with open(dummyFileName, "w") as someFile:
            someFile.write("hi")

        try:
            with mockRunLogs.BufferLog() as log:
                lib = xsLibraries.IsotxsLibrary()
                with self.assertRaises(OSError):
                    xsLibraries.mergeXSLibrariesInWorkingDirectory(lib, "ISOTXS", "")
                self.assertIn(dummyFileName, log.getStdout())
        finally:
            os.remove(dummyFileName)

        with TemporaryDirectoryChanger():
            dummyFileName = "ISO[]"
            with open(dummyFileName, "w") as file:
                file.write(
                    "This is a file that starts with the letters 'ISO' but will break the regular expression search."
                )

            try:
                with mockRunLogs.BufferLog() as log:
                    lib = xsLibraries.IsotxsLibrary()
                    xsLibraries.mergeXSLibrariesInWorkingDirectory(lib)
                    self.assertIn(f"{dummyFileName} in the merging of ISOXX files", log.getStdout())
            finally:
                pass

    def _xsLibraryAttributeHelper(
        self,
        lib,
        neutronEnergyLength,
        neutronVelLength,
        gammaEnergyLength,
        neutronDoseLength,
        gammaDoseLength,
    ):
        for attrName, listLength in [
            ("neutronEnergyUpperBounds", neutronEnergyLength),
            ("neutronVelocity", neutronVelLength),
            ("gammaEnergyUpperBounds", gammaEnergyLength),
            ("neutronDoseConversionFactors", neutronDoseLength),
            ("gammaDoseConversionFactors", gammaDoseLength),
        ]:
            if listLength > 0:
                self.assertEqual(listLength, len(getattr(lib, attrName)))
            else:
                with self.assertRaises(properties.ImmutablePropertyError):
                    print(f"Getting the value {attrName}")
                    print(getattr(lib, attrName))

    def test_isotxsLibraryAttributes(self):
        self._xsLibraryAttributeHelper(
            self.isotxsAA,
            neutronEnergyLength=33,
            neutronVelLength=33,
            gammaEnergyLength=0,
            neutronDoseLength=0,
            gammaDoseLength=0,
        )

    def test_gamisoLibraryAttributes(self):
        self._xsLibraryAttributeHelper(
            self.gamisoAA,
            neutronEnergyLength=0,
            neutronVelLength=0,
            gammaEnergyLength=21,
            neutronDoseLength=0,
            gammaDoseLength=0,
        )

    def test_pmatrxLibraryAttributes(self):
        self._xsLibraryAttributeHelper(
            self.pmatrxAA,
            neutronEnergyLength=33,
            neutronVelLength=0,
            gammaEnergyLength=21,
            neutronDoseLength=0,
            gammaDoseLength=0,
        )

    def test_mergeXSLibrariesWithDifferentDataWorks(self):
        if self.xsLibGenerationErrorStack is not None:
            print(self.xsLibGenerationErrorStack)
            raise Exception("see stdout for stack trace")
        # check to make sure they labels overlap, or are actually the same
        labels = set(self.xsLib.nuclideLabels)
        self.assertEqual(labels, set(self.isotxsAA.nuclideLabels))
        self.assertEqual(labels, set(self.gamisoAA.nuclideLabels))
        self.assertEqual(labels, set(self.pmatrxAA.nuclideLabels))
        # the whole thing is different from the sum of its components
        self.assertFalse(xsLibraries.compare(self.xsLib, self.isotxsAA))
        self.assertFalse(xsLibraries.compare(self.xsLib, self.gamisoAA))
        self.assertFalse(xsLibraries.compare(self.xsLib, self.pmatrxAA))
        # individual components are the same
        self.assertTrue(isotxs.compare(self.xsLib, self.isotxsAA))
        self.assertTrue(gamiso.compare(self.xsLib, self.gamisoAA))
        self.assertTrue(pmatrx.compare(self.xsLib, self.pmatrxAA))

    def test_canWriteIsotxsFromCombinedXSLibrary(self):
        self._canWritefromCombined(isotxs, ISOTXS_AA)

    def test_canWriteGamisoFromCombinedXSLibrary(self):
        self._canWritefromCombined(gamiso, GAMISO_AA)

    def test_canWritePmatrxFromCombinedXSLibrary(self):
        self._canWritefromCombined(pmatrx, PMATRX_AA)

    def _canWritefromCombined(self, writer, refFile):
        if self.xsLibGenerationErrorStack is not None:
            print(self.xsLibGenerationErrorStack)
            raise Exception("See stdout for stack trace")
        # check to make sure they labels overlap... or are actually the same
        writer.writeBinary(self.xsLib, self.testFileName)
        self.assertTrue(filecmp.cmp(refFile, self.testFileName))


class TestGetISOTXSFilesWorkDir(unittest.TestCase):
    def test_getISOTXSFilesWithoutLibrarySuffix(self):
        shouldBeThere = ["ISOAA", "ISOBA", os.path.join("file-path", "ISOCA")]
        shouldNotBeThere = [
            "ISOBA-n2",
            "ISOTXS",
            "ISOTXS-c2",
            "dummyISOTXS",
            "ISOTXS.BCD",
            "ISOAA.BCD",
        ]
        filesInDirectory = shouldBeThere + shouldNotBeThere
        toMerge = xsLibraries.getISOTXSLibrariesToMerge("", filesInDirectory)
        self.assert_contains_only(toMerge, shouldBeThere, shouldNotBeThere)

    def test_getISOTXSFilesWithLibrarySuffix(self):
        shouldBeThere = [
            "ISOAA-n23",
            "ISOAAF-n23",
            "ISOBA-n23",
            "ISODA",
            os.path.join("file-path", "ISOCA-n23"),
        ]
        shouldNotBeThere = [
            "ISOAA",
            "ISOAA-n24",
            "ISOBA-ISO",
            "ISOBA-n2",
            "ISOBA",
            "ISOTXS",
            "ISOTXS-c2",
            "dummyISOTXS",
            "ISOTXS.BCD",
            "ISOAA.BCD",
            "ISOCA-doppler",
            "ISOSA-void",
            os.path.join("file-path", "ISOCA"),
        ]
        filesInDirectory = shouldBeThere + shouldNotBeThere
        toMerge = xsLibraries.getISOTXSLibrariesToMerge("-n23", filesInDirectory)
        self.assert_contains_only(toMerge, shouldBeThere, shouldNotBeThere)

    def assert_contains_only(self, container, shouldBeThere, shouldNotBeThere):
        """
        Utility method for saying what things contain.

        This could just check the contents and length, but the error produced from shouldNotBeThere is much nicer.
        """
        container = set(container)
        self.assertEqual(container, set(shouldBeThere))
        self.assertEqual(set(), container & set(shouldNotBeThere))


class AbstractTestXSlibraryMerging(TempFileMixin):
    """
    A shared class that defines tests that should be true for all IsotxsLibrary merging.

    Notes
    -----
    This is a base class; it is not run directly.
    """

    def _readFileAttempts(self, path):
        """Run the file read a few times, because sometimes GitHub CI is flaky with these tests."""
        maxAttempts = 5
        for a in range(maxAttempts):
            try:
                return self.getReadFunc()(path)
            except OSError as e:
                if a >= (maxAttempts - 1):
                    raise e
                sleep(1)

    def setUp(self):
        TempFileMixin.setUp(self)
        # Load a library in the ARMI tree. This should be a small library with LFPs, Actinides, structure, and coolant.
        self.libAA = self._readFileAttempts(self.getLibAAPath())
        self.libAB = self._readFileAttempts(self.getLibABPath())
        self.libCombined = self._readFileAttempts(self.getLibAA_ABPath())
        self.libLumped = self._readFileAttempts(self.getLibLumpedPath())
        self.nuclideBases = NuclideBases()

    def getErrorType(self):
        raise NotImplementedError()

    def getReadFunc(self):
        raise NotImplementedError()

    def getWriteFunc(self):
        raise NotImplementedError()

    def getLibAAPath(self):
        raise NotImplementedError()

    def getLibABPath(self):
        raise NotImplementedError()

    def getLibAA_ABPath(self):
        raise NotImplementedError()

    def getLibLumpedPath(self):
        raise NotImplementedError()

    def test_mergeXSLibSameNucNames(self):
        """Cannot merge XS libraries with the same nuclide names."""
        with self.assertRaises(AttributeError):
            self.libAA.merge(self.libCombined)

        with self.assertRaises(AttributeError):
            self.libAA.merge(self.libAA)

        with self.assertRaises(AttributeError):
            self.libAA.merge(self.libCombined)

        with self.assertRaises(AttributeError):
            self.libCombined.merge(self.libAA)

    def test_mergeXSLibxDiffGroupStructure(self):
        """Cannot merge XS libraries with different group structure."""
        dummyXsLib = xsLibraries.IsotxsLibrary()
        dummyXsLib.neutronEnergyUpperBounds = np.array([1, 2, 3])
        dummyXsLib.gammaEnergyUpperBounds = np.array([1, 2, 3])
        with self.assertRaises(properties.ImmutablePropertyError):
            dummyXsLib.merge(self.libCombined)

    def test_mergeEmptyXSLibWithClones(self):
        """Merge empty XS libraries with clones of others."""
        emptyXSLib = xsLibraries.IsotxsLibrary()
        emptyXSLib.merge(self.libAA)
        self.libAA = None
        self.getWriteFunc()(emptyXSLib, self.testFileName)
        sleep(1)
        self.assertTrue(os.path.exists(self.testFileName))
        self.assertGreater(os.path.getsize(self.testFileName), 0)
        self.assertTrue(filecmp.cmp(self.getLibAAPath(), self.testFileName))

    def test_mergeTwoXSLibFiles(self):
        emptyXSLib = xsLibraries.IsotxsLibrary()
        emptyXSLib.merge(self.libAA)
        self.libAA = None
        emptyXSLib.merge(self.libAB)
        self.libAB = None
        self.assertEqual(set(self.libCombined.nuclideLabels), set(emptyXSLib.nuclideLabels))
        self.assertTrue(xsLibraries.compare(emptyXSLib, self.libCombined))
        self.getWriteFunc()(emptyXSLib, self.testFileName)
        sleep(1)
        self.assertTrue(os.path.exists(self.testFileName))
        self.assertGreater(os.path.getsize(self.testFileName), 0)
        self.assertTrue(filecmp.cmp(self.getLibAA_ABPath(), self.testFileName))


class TestPmatrxMerge(AbstractTestXSlibraryMerging, unittest.TestCase):
    def getErrorType(self):
        raise OSError

    def getReadFunc(self):
        return pmatrx.readBinary

    def getWriteFunc(self):
        return pmatrx.writeBinary

    def getLibAAPath(self):
        return PMATRX_AA

    def getLibABPath(self):
        return PMATRX_AB

    def getLibAA_ABPath(self):
        return PMATRX_AA_AB

    def getLibLumpedPath(self):
        return PMATRX_LUMPED

    def test_cannotMergeXSLibsWithDiffGammaGroups(self):
        """Test that we cannot merge XS Libs with different Gamma Group Structures."""
        dummyXsLib = xsLibraries.IsotxsLibrary()
        dummyXsLib.gammaEnergyUpperBounds = np.array([1, 2, 3])
        with self.assertRaises(properties.ImmutablePropertyError):
            dummyXsLib.merge(self.libCombined)


class TestIsotxsMerge(AbstractTestXSlibraryMerging, unittest.TestCase):
    def getErrorType(self):
        raise OSError

    def getReadFunc(self):
        return isotxs.readBinary

    def getWriteFunc(self):
        return isotxs.writeBinary

    def getLibAAPath(self):
        return ISOTXS_AA

    def getLibABPath(self):
        return ISOTXS_AB

    def getLibAA_ABPath(self):
        return ISOTXS_AA_AB

    def getLibLumpedPath(self):
        return ISOTXS_LUMPED

    def test_canRemoveIsotopes(self):
        emptyXSLib = xsLibraries.IsotxsLibrary()
        emptyXSLib.merge(self.libAA)
        self.libAA = None
        emptyXSLib.merge(self.libAB)
        self.libAB = None
        for nucId in [
            "ZR93_7",
            "ZR95_7",
            "XE1287",
            "XE1297",
            "XE1307",
            "XE1317",
            "XE1327",
            "XE1337",
            "XE1347",
            "XE1357",
            "XE1367",
        ]:
            nucLabel = self.nuclideBases.byMcc3Id[nucId].label
            del emptyXSLib[nucLabel + "AA"]
            del emptyXSLib[nucLabel + "AB"]
        self.assertEqual(set(self.libLumped.nuclideLabels), set(emptyXSLib.nuclideLabels))
        self.getWriteFunc()(emptyXSLib, self.testFileName)
        self.assertTrue(filecmp.cmp(self.getLibLumpedPath(), self.testFileName))


class TestGamisoMerge(AbstractTestXSlibraryMerging, unittest.TestCase):
    def getErrorType(self):
        raise OSError

    def getReadFunc(self):
        return gamiso.readBinary

    def getWriteFunc(self):
        return gamiso.writeBinary

    def getLibAAPath(self):
        return GAMISO_AA

    def getLibABPath(self):
        return GAMISO_AB

    def getLibAA_ABPath(self):
        return GAMISO_AA_AB

    def getLibLumpedPath(self):
        return GAMISO_LUMPED

    def test_canRemoveIsotopes(self):
        emptyXSLib = xsLibraries.IsotxsLibrary()
        emptyXSLib.merge(self.libAA)
        self.libAA = None
        emptyXSLib.merge(self.libAB)
        self.libAB = None
        for nucId in [
            "ZR93_7",
            "ZR95_7",
            "XE1287",
            "XE1297",
            "XE1307",
            "XE1317",
            "XE1327",
            "XE1337",
            "XE1347",
            "XE1357",
            "XE1367",
        ]:
            nucLabel = self.nuclideBases.byMcc3Id[nucId].label
            del emptyXSLib[nucLabel + "AA"]
            del emptyXSLib[nucLabel + "AB"]

        self.assertEqual(set(self.libLumped.nuclideLabels), set(emptyXSLib.nuclideLabels))
        self.getWriteFunc()(emptyXSLib, self.testFileName)
        self.assertTrue(filecmp.cmp(self.getLibLumpedPath(), self.testFileName))


class TestCombinedMerge(unittest.TestCase):
    def setUp(self):
        # Load a library in the ARMI tree. This should be a small library with LFPs, Actinides, structure, and coolant.
        self.isotxsAA = isotxs.readBinary(ISOTXS_AA)
        self.gamisoAA = gamiso.readBinary(GAMISO_AA)
        self.pmatrxAA = pmatrx.readBinary(PMATRX_AA)
        self.isotxsAB = isotxs.readBinary(ISOTXS_AB)
        self.gamisoAB = gamiso.readBinary(GAMISO_AB)
        self.pmatrxAB = pmatrx.readBinary(PMATRX_AB)
        self.libCombined = isotxs.readBinary(ISOTXS_AA_AB)

    def test_mergeAllXSLibFiles(self):
        lib = xsLibraries.IsotxsLibrary()
        xsLibraries.mergeXSLibrariesInWorkingDirectory(
            lib, xsLibrarySuffix="", mergeGammaLibs=True, alternateDirectory=FIXTURE_DIR
        )
        self.assertEqual(set(lib.nuclideLabels), set(self.libCombined.nuclideLabels))
