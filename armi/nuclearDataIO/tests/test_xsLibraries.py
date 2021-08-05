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

"""Tests for xsLibraries.IsotxsLibrary"""
import copy
import filecmp
import os
import shutil
import subprocess
import traceback
import unittest

from six.moves import cPickle

from armi import settings
from armi.tests import mockRunLogs
from armi.localization import exceptions
from armi.nucDirectory import nuclideBases
from armi.nuclearDataIO.cccc import isotxs
from armi.nuclearDataIO.cccc import pmatrx
from armi.nuclearDataIO.cccc import gamiso
from armi.nuclearDataIO import xsLibraries
from armi.utils import directoryChangers
from armi.utils import properties
from armi.utils import outputCache

THIS_DIR = os.path.dirname(__file__)
RUN_DIR = os.path.join(THIS_DIR, "library-file-generation")
FIXTURE_DIR = os.path.join(THIS_DIR, "fixtures")
# CCCC fixtures are less fancy than these merging ones.
FIXTURE_DIR_CCCC = os.path.join(os.path.dirname(isotxs.__file__), "tests", "fixtures")

ISOTXS_AA = os.path.join(FIXTURE_DIR, "mc2v3-AA.isotxs")
ISOTXS_AB = os.path.join(FIXTURE_DIR, "mc2v3-AB.isotxs")
ISOTXS_AA_AB = os.path.join(FIXTURE_DIR, "combined-AA-AB.isotxs")
ISOTXS_LUMPED = os.path.join(FIXTURE_DIR, "combined-and-lumped-AA-AB.isotxs")

PMATRX_AA = os.path.join(FIXTURE_DIR, "mc2v3-AA.pmatrx")
PMATRX_AB = os.path.join(FIXTURE_DIR, "mc2v3-AB.pmatrx")
PMATRX_AA_AB = os.path.join(FIXTURE_DIR, "combined-AA-AB.pmatrx")
PMATRX_LUMPED = os.path.join(FIXTURE_DIR, "combined-and-lumped-AA-AB.pmatrx")

GAMISO_AA = os.path.join(FIXTURE_DIR, "mc2v3-AA.gamiso")
GAMISO_AB = os.path.join(FIXTURE_DIR, "mc2v3-AB.gamiso")
GAMISO_AA_AB = os.path.join(FIXTURE_DIR, "combined-AA-AB.gamiso")
GAMISO_LUMPED = os.path.join(FIXTURE_DIR, "combined-and-lumped-AA-AB.gamiso")

DLAYXS_MCC3 = os.path.join(FIXTURE_DIR_CCCC, "mc2v3.dlayxs")
UFG_FLUX_EDIT = os.path.join(FIXTURE_DIR, "mc2v3-AA.flux_ufg")


def copyInputForPmatrxAndGamsio(inpPath):
    with open(inpPath, "r") as inp, open(
        inpPath.replace(".inp", ".pmatrx.inp"), "w"
    ) as pmatrxInp, open(inpPath.replace(".inp", ".gamiso.inp"), "w") as gamisoInp:
        for line in inp:
            pmatrxInp.write(line.replace("isotxs", "pmatrx"))
            gamisoInp.write(line.replace(".isotxs", ".gamiso"))


def createTestXSLibraryFiles(cachePath):
    r"""This method is used to generate 5 ISOTXS files used during testing.

    Notes
    -----
    It runs a batch file pointing to the MC**2-v3 executable with MC**2-v3 inputs within the repository,
    instead of placing the larger binary ISOTXS files within the repository.

    Also, the _CREATE_ERROR module attribute is used to track whether we have already tried to generate
    ISOTXS files. Basically, this method can (and should) be called in the setUp/setUpClass of any test
    that uses the generated ISOTXS files. Therefore, it is possible that for some reason the ISOTXS
    generation fails, and it would not be worth the time to continually try to recreate the ISOTXS files
    for each test that uses them, instead just raise the error that occurred the first time.
    """
    cs = settings.Settings()
    cs["outputCacheLocation"] = cachePath
    mc2v3 = cs.settings["mc2v3.path"].default
    with directoryChangers.DirectoryChanger(RUN_DIR):
        # the two lines below basically copy the inputs to be used for PMATRX and GAMISO generation.
        # Since they are inputs to secondary calculations, the inputs need to be created before any
        # other output is generated. Do not move the two lines below to, for exmaple just before they
        # are used, otherwise the input to the GAMISO calculation would be younger than the output
        # DLAYXS, which would cause this the @fixture to determine that targets are out of date.
        # The result would be that the targets will never be up to date, which defeats the purpose ;-).
        # IMPORTANT!! these two lines cannot move!
        copyInputForPmatrxAndGamsio("combine-AA-AB.inp")
        copyInputForPmatrxAndGamsio("combine-and-lump-AA-AB.inp")
        # IMPORTANT!! these two lines cannot move!
        ############################################################
        ##                                                        ##
        ##                   GENERATE DLAYXS                      ##
        ##                                                        ##
        ############################################################
        outputCache.cacheCall(
            cs["outputCacheLocation"], mc2v3, ["mc2v3-dlayxs.inp"], ["DLAYXS"]
        )
        shutil.move("DLAYXS", DLAYXS_MCC3)

        ############################################################
        ##                                                        ##
        ##                   GENERATE ISOTXS                      ##
        ##                                                        ##
        ############################################################
        outputCache.cacheCall(
            cs["outputCacheLocation"],
            mc2v3,
            ["mc2v3-AA.inp"],
            ["ISOTXS.merged", "GAMISO.merged", "PMATRX.merged", "output.flux_ufg"],
        )
        shutil.move("ISOTXS.merged", ISOTXS_AA)
        shutil.move("GAMISO.merged", GAMISO_AA)
        shutil.move("PMATRX.merged", PMATRX_AA)
        shutil.move("output.flux_ufg", UFG_FLUX_EDIT)

        outputCache.cacheCall(
            cs["outputCacheLocation"],
            mc2v3,
            ["mc2v3-AB.inp"],
            ["ISOTXS.merged", "GAMISO.merged", "PMATRX.merged"],
        )
        shutil.move("ISOTXS.merged", ISOTXS_AB)
        shutil.move("GAMISO.merged", GAMISO_AB)
        shutil.move("PMATRX.merged", PMATRX_AB)

        # ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        # ::                                                      ::
        # ::                     COMBINE                          ::
        # ::                                                      ::
        # ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

        outputCache.cacheCall(
            cs["outputCacheLocation"], mc2v3, ["combine-AA-AB.inp"], ["ISOTXS.merged"]
        )
        shutil.move("ISOTXS.merged", ISOTXS_AA_AB)

        outputCache.cacheCall(
            cs["outputCacheLocation"],
            mc2v3,
            ["combine-AA-AB.pmatrx.inp"],
            ["PMATRX.merged"],
        )
        shutil.move("PMATRX.merged", PMATRX_AA_AB)

        outputCache.cacheCall(
            cs["outputCacheLocation"],
            mc2v3,
            ["combine-AA-AB.gamiso.inp"],
            ["ISOTXS.merged"],
        )
        shutil.move("ISOTXS.merged", GAMISO_AA_AB)

        # ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
        # ::                                                      ::
        # ::                COMBINE AND LUMP                      ::
        # ::                                                      ::
        # ::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

        subprocess.call([mc2v3, "combine-and-lump-AA-AB.inp"])
        shutil.move("ISOTXS.merged", ISOTXS_LUMPED)

        subprocess.call([mc2v3, "combine-and-lump-AA-AB.pmatrx.inp"])
        shutil.move("PMATRX.merged", PMATRX_LUMPED)

        subprocess.call([mc2v3, "combine-and-lump-AA-AB.gamiso.inp"])
        shutil.move("ISOTXS.merged", GAMISO_LUMPED)


class TempFileMixin:  # really a test case...
    @property
    def testFileName(self):
        return os.path.join(
            THIS_DIR,
            "{}-{}.nucdata".format(self.__class__.__name__, self._testMethodName),
        )

    def tearDown(self):
        try:
            os.remove(self.testFileName)
        except OSError:
            pass


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
        except:
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
                with self.assertRaises(exceptions.IsotxsError):
                    xsLibraries.mergeXSLibrariesInWorkingDirectory(lib, "ISOTXS", "")
                self.assertTrue(dummyFileName in log.getStdoutValue())
        finally:
            os.remove(dummyFileName)

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


class Test_GetISOTXSFilesInWorkingDirectory(unittest.TestCase):
    def test_getISOTXSFilesWithoutLibrarySuffix(self):
        shouldBeThere = ["ISOAA", "ISOBA"]
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
        shouldBeThere = ["ISOAA-n23", "ISOAAF-n23", "ISOBA-n23", "ISOCA", "ISODA"]
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
        ]
        filesInDirectory = shouldBeThere + shouldNotBeThere
        toMerge = xsLibraries.getISOTXSLibrariesToMerge("-n23", filesInDirectory)
        self.assert_contains_only(toMerge, shouldBeThere, shouldNotBeThere)

    def assert_contains_only(self, container, shouldBeThere, shouldNotBeThere):
        """
        Utility method for saying what things contain

        This could just check the contents and the length, but the error produced when you pass shouldNotBeThere
        is much nicer.
        """
        container = set(container)
        self.assertEqual(container, set(shouldBeThere))
        self.assertEqual(set(), container & set(shouldNotBeThere))


# LOOK OUT, THIS GETS DELETED LATER ON SO IT DOESN'T RUN... IT IS AN ABSTRACT CLASS!!
# LOOK OUT, THIS GETS DELETED LATER ON SO IT DOESN'T RUN... IT IS AN ABSTRACT CLASS!!
# LOOK OUT, THIS GETS DELETED LATER ON SO IT DOESN'T RUN... IT IS AN ABSTRACT CLASS!!
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
        with self.assertRaises(exceptions.XSLibraryError):
            self.libAA.merge(self.libCombined)
        with self.assertRaises(exceptions.XSLibraryError):
            self.libAA.merge(self.libAA)
        with self.assertRaises(exceptions.XSLibraryError):
            self.libAA.merge(self.libCombined)
        with self.assertRaises(exceptions.XSLibraryError):
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
            nucLabel = nuclideBases.byMccId[nucId].label
            del emptyXSLib[nucLabel + "AA"]
            del emptyXSLib[nucLabel + "AB"]
        self.assertEqual(
            set(self.libLumped.nuclideLabels), set(emptyXSLib.nuclideLabels)
        )
        self.getWriteFunc()(emptyXSLib, self.testFileName)
        self.assertTrue(filecmp.cmp(self.getLibLumpedPath(), self.testFileName))


class Pmatrx_merge_Tests(TestXSlibraryMerging):
    def getErrorType(self):
        return exceptions.IsotxsError

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
        return exceptions.PmatrxError

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
        return exceptions.GamisoError

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


# Remove the abstract class, so that it does not run (all tests would fail)
del TestXSlibraryMerging

if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Gamiso_merge_Tests.test_mergeTwoXSLibFiles']
    unittest.main()
