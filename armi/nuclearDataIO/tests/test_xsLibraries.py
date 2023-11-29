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
import traceback
import unittest

from six.moves import cPickle

from armi.nucDirectory import nuclideBases
from armi.nuclearDataIO import xsLibraries
from armi.nuclearDataIO.cccc import gamiso
from armi.nuclearDataIO.cccc import isotxs
from armi.nuclearDataIO.cccc import pmatrx
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
    """really a test case."""

    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    @property
    def testFileName(self):
        return os.path.join(
            THIS_DIR,
            "{}-{}.nucdata".format(self.__class__.__name__, self._testMethodName),
        )


class TestXSLibrary(unittest.TestCase, TempFileMixin):
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
        except:  # noqa: bare-except
            cls.xsLibGenerationErrorStack = traceback.format_exc()

    def test_canPickleAndUnpickleISOTXS(self):
        pikAA = cPickle.loads(cPickle.dumps(self.isotxsAA))
        self.assertTrue(xsLibraries.compare(pikAA, self.isotxsAA))

    def test_canPickleAndUnpickleGAMISO(self):
        pikAA = cPickle.loads(cPickle.dumps(self.gamisoAA))
        self.assertTrue(xsLibraries.compare(pikAA, self.gamisoAA))

    def test_canPickleAndUnpicklePMATRX(self):
        pikAA = cPickle.loads(cPickle.dumps(self.pmatrxAA))
        self.assertTrue(xsLibraries.compare(pikAA, self.pmatrxAA))

    def test_compareWorks(self):
        self.assertTrue(xsLibraries.compare(self.isotxsAA, self.isotxsAA))
        self.assertTrue(xsLibraries.compare(self.pmatrxAA, self.pmatrxAA))
        aa = isotxs.readBinary(ISOTXS_AA)
        del aa[aa.nuclideLabels[0]]
        self.assertFalse(xsLibraries.compare(aa, self.isotxsAA))

    def test_compareDifferentComponentsOfAnXSLibrary(self):
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
            dummyFileName = "ISOtopics.txt"
            with open(dummyFileName, "w") as file:
                file.write(
                    "This is a file that starts with the letters 'ISO' but will"
                    " break the regular expression search."
                )

            try:
                with mockRunLogs.BufferLog() as log:
                    lib = xsLibraries.IsotxsLibrary()
                    xsLibraries.mergeXSLibrariesInWorkingDirectory(lib)
                    self.assertIn(
                        f"{dummyFileName} in the merging of ISOXX files",
                        log.getStdout(),
                    )
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
                    print("Getting the value {}".format(attrName))
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
        # check to make sure they labels overlap... or are actually the same
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
            raise Exception("see stdout for stack trace")
        # check to make sure they labels overlap... or are actually the same
        writer.writeBinary(self.xsLib, self.testFileName)
        self.assertTrue(filecmp.cmp(refFile, self.testFileName))


class TestGetISOTXSFilesInWorkingDirectory(unittest.TestCase):
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
            "ISOTXS",
            "ISOTXS-c2",
            "dummyISOTXS",
            "ISOTXS.BCD",
            "ISOAA.BCD",
            "ISOCA-doppler",
            "ISOSA-void",
            os.path.join("file-path", "ISOCA-ISO"),
        ]
        filesInDirectory = shouldBeThere + shouldNotBeThere
        toMerge = xsLibraries.getISOTXSLibrariesToMerge("-n23", filesInDirectory)
        self.assert_contains_only(toMerge, shouldBeThere, shouldNotBeThere)

    def assert_contains_only(self, container, shouldBeThere, shouldNotBeThere):
        """
        Utility method for saying what things contain.

        This could just check the contents and the length, but the error produced when you pass shouldNotBeThere
        is much nicer.
        """
        container = set(container)
        self.assertEqual(container, set(shouldBeThere))
        self.assertEqual(set(), container & set(shouldNotBeThere))


# NOTE: This is just a base class, so it isn't run directly.
class TestXSlibraryMerging(unittest.TestCase, TempFileMixin):
    """A shared class that defines tests that should be true for all IsotxsLibrary merging."""

    @classmethod
    def setUpClass(cls):
        cls.libAA = None
        cls.libAB = None
        cls.libCombined = None
        cls.libLumped = None

    @classmethod
    def tearDownClass(cls):
        cls.libAA = None
        cls.libAB = None
        cls.libCombined = None
        cls.libLumped = None
        del cls.libAA
        del cls.libAB
        del cls.libCombined
        del cls.libLumped

    def setUp(self):
        # load a library that is in the ARMI tree. This should
        # be a small library with LFPs, Actinides, structure, and coolant
        for attrName, path in [
            ("libAA", self.getLibAAPath),
            ("libAB", self.getLibABPath),
            ("libCombined", self.getLibAA_ABPath),
            ("libLumped", self.getLibLumpedPath),
        ]:
            if getattr(self.__class__, attrName) is None:
                setattr(self.__class__, attrName, self.getReadFunc()(path()))

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

    def test_cannotMergeXSLibWithSameNuclideNames(self):
        with self.assertRaises(AttributeError):
            self.libAA.merge(self.libCombined)
        with self.assertRaises(AttributeError):
            self.libAA.merge(self.libAA)
        with self.assertRaises(AttributeError):
            self.libAA.merge(self.libCombined)
        with self.assertRaises(AttributeError):
            self.libCombined.merge(self.libAA)

    def test_cannotMergeXSLibxWithDifferentGroupStructure(self):
        dummyXsLib = xsLibraries.IsotxsLibrary()
        dummyXsLib.neutronEnergyUpperBounds = [1, 2, 3]
        dummyXsLib.gammaEnergyUpperBounds = [1, 2, 3]
        with self.assertRaises(properties.ImmutablePropertyError):
            dummyXsLib.merge(self.libCombined)

    def test_mergeEmptyXSLibWithOtherEssentiallyClonesTheOther(self):
        emptyXSLib = xsLibraries.IsotxsLibrary()
        emptyXSLib.merge(self.libAA)
        self.__class__.libAA = None
        self.getWriteFunc()(emptyXSLib, self.testFileName)
        self.assertTrue(filecmp.cmp(self.getLibAAPath(), self.testFileName))

    def test_mergeTwoXSLibFiles(self):
        emptyXSLib = xsLibraries.IsotxsLibrary()
        emptyXSLib.merge(self.libAA)
        self.__class__.libAA = None
        emptyXSLib.merge(self.libAB)
        self.__class__.libAB = None
        self.assertEqual(
            set(self.libCombined.nuclideLabels), set(emptyXSLib.nuclideLabels)
        )
        self.assertTrue(xsLibraries.compare(emptyXSLib, self.libCombined))
        self.getWriteFunc()(emptyXSLib, self.testFileName)
        self.assertTrue(filecmp.cmp(self.getLibAA_ABPath(), self.testFileName))

    def test_canRemoveIsotopes(self):
        emptyXSLib = xsLibraries.IsotxsLibrary()
        emptyXSLib.merge(self.libAA)
        self.__class__.libAA = None
        emptyXSLib.merge(self.libAB)
        self.__class__.libAB = None
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
            nucLabel = nuclideBases.byMcc3Id[nucId].label
            del emptyXSLib[nucLabel + "AA"]
            del emptyXSLib[nucLabel + "AB"]
        self.assertEqual(
            set(self.libLumped.nuclideLabels), set(emptyXSLib.nuclideLabels)
        )
        self.getWriteFunc()(emptyXSLib, self.testFileName)
        self.assertTrue(filecmp.cmp(self.getLibLumpedPath(), self.testFileName))


class Pmatrx_merge_Tests(TestXSlibraryMerging):
    def getErrorType(self):
        return OSError

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

    @unittest.skip("Do not have data for comparing merged and purged PMATRX")
    def test_canRemoveIsotopes(self):
        # this test does not work for PMATRX, MC**2-v3 does not currently
        pass

    def test_cannotMergeXSLibsWithDifferentGammaGroupStructures(self):
        dummyXsLib = xsLibraries.IsotxsLibrary()
        dummyXsLib.gammaEnergyUpperBounds = [1, 2, 3]
        with self.assertRaises(properties.ImmutablePropertyError):
            dummyXsLib.merge(self.libCombined)


class Isotxs_merge_Tests(TestXSlibraryMerging):
    def getErrorType(self):
        return OSError

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


class Gamiso_merge_Tests(TestXSlibraryMerging):
    def getErrorType(self):
        return OSError

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


class Combined_merge_Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.isotxsAA = None
        cls.isotxsAB = None
        cls.gamisoAA = None
        cls.gamisoAB = None
        cls.pmatrxAA = None
        cls.pmatrxAB = None
        cls.libCombined = None

    @classmethod
    def tearDownClass(cls):
        cls.isotxsAA = None
        cls.isotxsAB = None
        cls.gamisoAA = None
        cls.gamisoAB = None
        cls.pmatrxAA = None
        cls.pmatrxAB = None
        cls.libCombined = None
        del cls.isotxsAA
        del cls.isotxsAB
        del cls.gamisoAA
        del cls.gamisoAB
        del cls.pmatrxAA
        del cls.pmatrxAB
        del cls.libCombined

    def setUp(self):
        # load a library that is in the ARMI tree. This should
        # be a small library with LFPs, Actinides, structure, and coolant
        for attrName, path, readFunc in [
            ("isotxsAA", ISOTXS_AA, isotxs.readBinary),
            ("gamisoAA", GAMISO_AA, gamiso.readBinary),
            ("pmatrxAA", PMATRX_AA, pmatrx.readBinary),
            ("isotxsAB", ISOTXS_AB, isotxs.readBinary),
            ("gamisoAB", GAMISO_AB, gamiso.readBinary),
            ("pmatrxAB", PMATRX_AB, pmatrx.readBinary),
            ("libCombined", ISOTXS_AA_AB, isotxs.readBinary),
        ]:
            if getattr(self.__class__, attrName) is None:
                setattr(self.__class__, attrName, readFunc(path))

    def test_mergeAllXSLibFiles(self):
        lib = xsLibraries.IsotxsLibrary()
        xsLibraries.mergeXSLibrariesInWorkingDirectory(
            lib, xsLibrarySuffix="", mergeGammaLibs=True, alternateDirectory=FIXTURE_DIR
        )
        self.assertEqual(set(lib.nuclideLabels), set(self.libCombined.nuclideLabels))


# Remove the abstract class, so that it does not run (all tests would fail)
del TestXSlibraryMerging
