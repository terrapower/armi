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
"""Unit tests for Case and CaseSuite objects."""
import copy
import cProfile
import io
import logging
import os
import platform
import unittest

from armi import cases
from armi import context
from armi import getApp
from armi import interfaces
from armi import plugins
from armi import runLog
from armi import settings
from armi.physics.fuelCycle.settings import CONF_SHUFFLE_LOGIC
from armi.reactor import blueprints
from armi.reactor import systemLayoutInput
from armi.tests import ARMI_RUN_PATH
from armi.tests import mockRunLogs
from armi.tests import TEST_ROOT
from armi.utils import directoryChangers


GEOM_INPUT = """<?xml version="1.0" ?>
<reactor geom="hex" symmetry="third core periodic">
    <assembly name="A1" pos="1"  ring="1"/>
    <assembly name="A2" pos="2"  ring="2"/>
    <assembly name="A3" pos="1"  ring="2"/>
</reactor>
"""
# This gets made into a StringIO multiple times because
# it gets read multiple times.

BLUEPRINT_INPUT = """
nuclide flags:
    U: {burn: false, xs: true}
    ZR: {burn: false, xs: true}
    MN: {burn: false, xs: true}
    FE: {burn: false, xs: true}
    SI: {burn: false, xs: true}
    C: {burn: false, xs: true}
    CR: {burn: false, xs: true}
    MO: {burn: false, xs: true}
    NI: {burn: false, xs: true}
blocks:
    fuel 1: &fuel_1
        fuel: &fuel_1_fuel
            Tinput: 350.0
            Thot: 350.0
            shape: circle
            id: 0.0
            od: 0.5
            material: UZr
        clad: &fuel_1_clad
            Tinput: 350.0
            Thot: 350.0
            shape: circle
            id: 1.0
            od: 1.1
            material: SS316
    fuel 2: *fuel_1
    block 3: *fuel_1                                        # non-fuel blocks
    block 4: {<<: *fuel_1}                                  # non-fuel blocks
    block 5: {fuel: *fuel_1_fuel, clad: *fuel_1_clad}       # non-fuel blocks
assemblies: {}
"""


class TestArmiCase(unittest.TestCase):
    """Class to tests armi.cases.Case methods."""

    def test_summarizeDesign(self):
        """
        Ensure that the summarizeDesign method runs.

        Any assertions are bonus.
        """
        with directoryChangers.TemporaryDirectoryChanger():
            cs = settings.Settings(ARMI_RUN_PATH)
            cs = cs.modified(newSettings={"verbosity": "important"})
            case = cases.Case(cs)
            c2 = case.clone()
            c2.summarizeDesign()
            self.assertTrue(
                os.path.exists(
                    os.path.join("{}-reports".format(c2.cs.caseTitle), "index.html")
                )
            )

    def test_independentVariables(self):
        """Ensure that independentVariables added to a case move with it."""
        geom = systemLayoutInput.SystemLayoutInput()
        geom.readGeomFromStream(io.StringIO(GEOM_INPUT))
        bp = blueprints.Blueprints.load(BLUEPRINT_INPUT)
        cs = settings.Settings(ARMI_RUN_PATH)
        cs = cs.modified(newSettings={"verbosity": "important"})
        baseCase = cases.Case(cs, bp=bp, geom=geom)
        with directoryChangers.TemporaryDirectoryChanger():
            vals = {"cladThickness": 1, "control strat": "good", "enrich": 0.9}
            case = baseCase.clone()
            case._independentVariables = vals
            case.writeInputs()
            newCs = settings.Settings(fName=case.title + ".yaml")
            newCase = cases.Case(newCs)
            for name, val in vals.items():
                self.assertEqual(newCase.independentVariables[name], val)

    def test_setUpTaskDependence(self):
        case = cases.Case(settings.Settings())
        case.enabled = False
        case.setUpTaskDependence()
        case.enabled = True
        case.setUpTaskDependence()
        self.assertTrue(case.enabled)
        self.assertEqual(len(case._tasks), 0)
        self.assertEqual(len(case.dependencies), 0)

    def test_getCoverageRcFile(self):
        case = cases.Case(settings.Settings())
        covRcDir = os.path.abspath(context.PROJECT_ROOT)
        # Don't actually copy the file, just check the file paths match
        covRcFile = case._getCoverageRcFile(userCovFile="", makeCopy=False)
        if platform.system() == "Windows":
            self.assertEqual(covRcFile, os.path.join(covRcDir, "coveragerc"))
        else:
            self.assertEqual(covRcFile, os.path.join(covRcDir, ".coveragerc"))

        userFile = "UserCovRc"
        covRcFile = case._getCoverageRcFile(userCovFile=userFile, makeCopy=False)
        self.assertEqual(covRcFile, os.path.abspath(userFile))

    def test_startCoverage(self):
        with directoryChangers.TemporaryDirectoryChanger():
            cs = settings.Settings(ARMI_RUN_PATH)

            # Test the null case
            cs = cs.modified(newSettings={"coverage": False})
            case = cases.Case(cs)
            cov = case._startCoverage()
            self.assertIsNone(cov)

            # NOTE: We can't test coverage=True, because it breaks coverage on CI

    def test_endCoverage(self):
        with directoryChangers.TemporaryDirectoryChanger():
            cs = settings.Settings(ARMI_RUN_PATH)
            cs = cs.modified(newSettings={"coverage": False})
            case = cases.Case(cs)

            # NOTE: We can't test coverage=True, because it breaks coverage on CI
            outFile = "coverage_results.cov"
            prof = case._startCoverage()
            self.assertFalse(os.path.exists(outFile))
            case._endCoverage(userCovFile="", cov=prof)
            self.assertFalse(os.path.exists(outFile))

    @unittest.skipUnless(context.MPI_RANK == 0, "test only on root node")
    def test_startProfiling(self):
        with directoryChangers.TemporaryDirectoryChanger():
            cs = settings.Settings(ARMI_RUN_PATH)

            # Test the null case
            cs = cs.modified(newSettings={"profile": False})
            case = cases.Case(cs)
            prof = case._startProfiling()
            self.assertIsNone(prof)

            # Test when we start coverage correctly
            cs = cs.modified(newSettings={"profile": True})
            case = cases.Case(cs)
            prof = case._startProfiling()
            self.assertTrue(isinstance(prof, cProfile.Profile))

    @unittest.skipUnless(context.MPI_RANK == 0, "test only on root node")
    def test_endProfiling(self):
        with directoryChangers.TemporaryDirectoryChanger():
            cs = settings.Settings(ARMI_RUN_PATH)
            cs = cs.modified(newSettings={"profile": True})
            case = cases.Case(cs)

            # run the profiler
            prof = case._startProfiling()
            case._endProfiling(prof)
            self.assertTrue(isinstance(prof, cProfile.Profile))

    def test_run(self):
        with directoryChangers.TemporaryDirectoryChanger():
            cs = settings.Settings(ARMI_RUN_PATH)
            newSettings = {
                "branchVerbosity": "important",
                "coverage": False,
                "nCycles": 1,
                "profile": False,
                "trace": False,
                "verbosity": "important",
            }
            cs = cs.modified(newSettings=newSettings)
            case = cases.Case(cs)

            with mockRunLogs.BufferLog() as mock:
                # we should start with a clean slate
                self.assertEqual("", mock.getStdout())
                runLog.LOG.startLog("test_run")
                runLog.LOG.setVerbosity(logging.INFO)

                case.run()

                self.assertIn("Triggering BOL Event", mock.getStdout())
                self.assertIn("xsGroups", mock.getStdout())
                self.assertIn("Completed EveryNode - cycle 0", mock.getStdout())

    def test_clone(self):
        testTitle = "CLONE_TEST"
        # test the short write style
        with directoryChangers.TemporaryDirectoryChanger():
            cs = settings.Settings(ARMI_RUN_PATH)
            case = cases.Case(cs)
            shortCase = case.clone(
                additionalFiles=["ISOAA"],
                title=testTitle,
                modifiedSettings={"verbosity": "important"},
            )
            # Check additional files made it
            self.assertTrue(os.path.exists("ISOAA"))
            # Check title change made it
            clonedYaml = testTitle + ".yaml"
            self.assertTrue(os.path.exists(clonedYaml))
            self.assertTrue(shortCase.title, testTitle)
            # Check on some expected settings
            # Availability factor is in the original settings file but since it is a
            # default value, gets removed for the write-out
            txt = open(clonedYaml, "r").read()
            self.assertNotIn("availabilityFactor", txt)
            self.assertIn("verbosity: important", txt)

        # test the medium write style
        with directoryChangers.TemporaryDirectoryChanger():
            cs = settings.Settings(ARMI_RUN_PATH)
            case = cases.Case(cs)
            case.clone(writeStyle="medium")
            clonedYaml = "armiRun.yaml"
            self.assertTrue(os.path.exists(clonedYaml))
            # Availability factor is in the original settings file and it is a default
            # value. While "short" (default writing style) removes, "medium" should not
            txt = open(clonedYaml, "r").read()
            self.assertIn("availabilityFactor", txt)


class TestCaseSuiteDependencies(unittest.TestCase):
    """CaseSuite tests."""

    def setUp(self):
        self.suite = cases.CaseSuite(settings.Settings())

        geom = systemLayoutInput.SystemLayoutInput()
        geom.readGeomFromStream(io.StringIO(GEOM_INPUT))
        bp = blueprints.Blueprints.load(BLUEPRINT_INPUT)

        self.c1 = cases.Case(cs=settings.Settings(), geom=geom, bp=bp)
        self.c1.cs.path = "c1.yaml"
        self.suite.add(self.c1)

        self.c2 = cases.Case(cs=settings.Settings(), geom=geom, bp=bp)
        self.c2.cs.path = "c2.yaml"
        self.suite.add(self.c2)

    def test_clone(self):
        """If you pass an invalid path, the clone can't happen, but it won't do any damage either."""
        with self.assertRaises(RuntimeError):
            _clone = self.suite.clone("test_clone")

    def test_dependenciesWithObscurePaths(self):
        """
        Test directory dependence.

        .. tip:: This should be updated to use the Python pathlib
            so the tests can work in both Linux and Windows identically.
        """
        checks = [
            ("c1.yaml", "c2.yaml", "c1.h5", True),
            (r"\\case\1\c1.yaml", r"\\case\2\c2.yaml", "c1.h5", False),
            # below doesn't work due to some windows path obscurities
            (r"\\case\1\c1.yaml", r"\\case\2\c2.yaml", r"..\1\c1.h5", False),
        ]
        if platform.system() == "Windows":
            # windows-specific case insensitivity
            checks.extend(
                [
                    ("c1.yaml", "c2.yaml", "C1.H5", True),
                    (
                        r"\\cas\es\1\c1.yaml",
                        r"\\cas\es\2\c2.yaml",
                        r"..\..\1\c1.h5",
                        True,
                    ),
                    (
                        r"c1.yaml",
                        r"c2.yaml",
                        r".\c1.h5",
                        True,
                    ),  # py bug in 3.6.4 and 3.7.1 fails here
                    (
                        r"\\cas\es\1\c1.yaml",
                        r"\\cas\es\2\c2.yaml",
                        r"../..\1\c1.h5",
                        True,
                    ),
                    (
                        r"\\cas\es\1\c1.yaml",
                        r"\\cas\es\2\c2.yaml",
                        r"../../1\c1.h5",
                        True,
                    ),
                    (
                        r"\\cas\es\1\c1.yaml",
                        r"\\cas\es\2\c2.yaml",
                        r"..\../1\c1.h5",
                        True,
                    ),
                    (
                        r"\\cas\es\1\c1.yaml",
                        r"\\cas\es\2\c2.yaml",
                        r"\\cas\es\1\c1.h5",
                        True,
                    ),
                    # below False because getcwd() != \\case\es\2
                    (
                        r"..\..\1\c1.yaml",
                        r"\\cas\es\2\c2.yaml",
                        r"\\cas\es\1\c1.h5",
                        False,
                    ),
                    (
                        r"\\cas\es\1\c1.yaml",
                        r"\\cas\es\2\c2.yaml",
                        r"..\..\2\c1.h5",
                        False,
                    ),
                ]
            )

        for p1, p2, dbPath, isIn in checks:
            self.c1.cs.path = p1
            self.c2.cs.path = p2

            newSettings = {}
            newSettings["loadStyle"] = "fromDB"
            newSettings["reloadDBName"] = dbPath
            self.c2.cs = self.c2.cs.modified(newSettings=newSettings)

            # note that case.dependencies is a property and
            # will actually reflect these changes
            self.assertEqual(
                isIn,
                self.c1 in self.c2.dependencies,
                "where p1: {} p2: {} dbPath: {}".format(p1, p2, dbPath),
            )

    def test_dependencyFromDBName(self):
        # no effect -> need to specify loadStyle, 'fromDB'
        newSettings = {"reloadDBName": "c1.h5"}
        self.c2.cs = self.c2.cs.modified(newSettings=newSettings)
        self.assertEqual(0, len(self.c2.dependencies))

        newSettings = {"loadStyle": "fromDB"}
        self.c2.cs = self.c2.cs.modified(newSettings=newSettings)
        self.assertIn(self.c1, self.c2.dependencies)

        # the .h5 extension is optional
        newSettings = {"reloadDBName": "c1"}
        self.c2.cs = self.c2.cs.modified(newSettings=newSettings)
        self.assertIn(self.c1, self.c2.dependencies)

    def test_dependencyFromExplictRepeatShuffles(self):
        self.assertEqual(0, len(self.c2.dependencies))
        newSettings = {"explicitRepeatShuffles": "c1-SHUFFLES.txt"}
        self.c2.cs = self.c2.cs.modified(newSettings=newSettings)
        self.assertIn(self.c1, self.c2.dependencies)

    def test_explicitDependency(self):
        self.c1.addExplicitDependency(self.c2)

        self.assertIn(self.c2, self.c1.dependencies)

    def test_titleSetterGetter(self):
        self.assertEqual(self.c1.title, "c1")
        self.c1.title = "new_bob"
        self.assertEqual(self.c1.title, "new_bob")

    def test_buildCommand(self):
        cmd = self.c1.buildCommand()
        self.assertEqual(cmd, 'python -u  -m armi run "c1.yaml"')


class TestExtraInputWriting(unittest.TestCase):
    """Make sure extra inputs from interfaces are written."""

    def test_writeInput(self):
        fName = os.path.join(TEST_ROOT, "armiRun.yaml")
        cs = settings.Settings(fName)
        baseCase = cases.Case(cs)
        with directoryChangers.TemporaryDirectoryChanger():
            case = baseCase.clone()
            case.writeInputs()
            self.assertTrue(os.path.exists(cs[CONF_SHUFFLE_LOGIC]))
            # Availability factor is in the original settings file but since it is a
            # default value, gets removed for the write-out
            txt = open("armiRun.yaml", "r").read()
            self.assertNotIn("availabilityFactor", txt)
            self.assertIn("armiRun-blueprints.yaml", txt)

        with directoryChangers.TemporaryDirectoryChanger():
            case = baseCase.clone(writeStyle="medium")
            case.writeInputs(writeStyle="medium")
            # Availability factor is in the original settings file and it is a default
            # value. While "short" (default writing style) removes, "medium" should not
            txt = open("armiRun.yaml", "r").read()
            self.assertIn("availabilityFactor", txt)


class MultiFilesInterfaces(interfaces.Interface):
    """
    A little test interface that adds a setting that we need to test copyInterfaceInputs
    with multiple files.
    """

    name = "MultiFilesInterfaces"

    @staticmethod
    def specifyInputs(cs):
        settingName = "multipleFilesSetting"
        return {settingName: cs[settingName]}


class TestPluginWithDuplicateSetting(plugins.ArmiPlugin):
    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        """Define a duplicate setting."""
        return [
            settings.setting.Setting(
                "power",
                default=123,
                label="power",
                description="duplicate power",
            )
        ]


class TestPluginForCopyInterfacesMultipleFiles(plugins.ArmiPlugin):
    @staticmethod
    @plugins.HOOKIMPL
    def defineSettings():
        """Define settings for the plugin."""
        return [
            settings.setting.Setting(
                "multipleFilesSetting",
                default=[],
                label="multiple files",
                description="testing stuff",
            )
        ]

    @staticmethod
    @plugins.HOOKIMPL
    def exposeInterfaces(cs):
        """A plugin is mostly just a vehicle to add Interfaces to an Application."""
        return [
            interfaces.InterfaceInfo(
                interfaces.STACK_ORDER.PREPROCESSING,
                MultiFilesInterfaces,
                {"enabled": True},
            )
        ]


class TestCopyInterfaceInputs(unittest.TestCase):
    """Ensure file path is found and updated properly."""

    def setUp(self):
        """
        Manipulate the standard App. We can't just configure our own, since the
        pytest environment bleeds between tests.
        """
        self._backupApp = copy.deepcopy(getApp())

    def tearDown(self):
        """Restore the App to its original state."""
        import armi

        armi._app = self._backupApp
        context.APP_NAME = "armi"

    def test_copyInputsHelper(self):
        """Test the helper function for copyInterfaceInputs."""
        testSetting = CONF_SHUFFLE_LOGIC
        cs = settings.Settings(ARMI_RUN_PATH)
        shuffleFile = cs[testSetting]

        # test it passes
        sourceFullPath = os.path.join(TEST_ROOT, shuffleFile)
        # ensure we are not in TEST_ROOT
        with directoryChangers.TemporaryDirectoryChanger() as newDir:
            destFilePath = cases.case._copyInputsHelper(
                testSetting,
                sourcePath=sourceFullPath,
                destPath=newDir.destination,
                origFile=shuffleFile,
            )
            newFilePath = os.path.join(newDir.destination, shuffleFile)
            self.assertTrue(os.path.exists(newFilePath))
            self.assertEqual(destFilePath, os.path.basename(newFilePath))

        # test with bad file path, should return original file
        # ensure we are not in TEST_ROOT
        with directoryChangers.TemporaryDirectoryChanger() as newDir:
            destFilePath = cases.case._copyInputsHelper(
                testSetting,
                sourcePath=sourceFullPath,
                destPath="fakeDest",
                origFile=shuffleFile,
            )
            self.assertFalse(os.path.exists(destFilePath))
            self.assertEqual(destFilePath, shuffleFile)

    def test_copyInterfaceInputs_singleFile(self):
        testSetting = CONF_SHUFFLE_LOGIC
        cs = settings.Settings(ARMI_RUN_PATH)
        shuffleFile = cs[testSetting]

        # ensure we are not in TEST_ROOT
        with directoryChangers.TemporaryDirectoryChanger() as newDir:
            newSettings = cases.case.copyInterfaceInputs(
                cs, destination=newDir.destination
            )
            newFilePath = os.path.join(newDir.destination, shuffleFile)
            self.assertTrue(os.path.exists(newFilePath))
            self.assertEqual(newSettings[testSetting], os.path.basename(newFilePath))

    def test_copyInterfaceInputs_nonFilePath(self):
        testSetting = CONF_SHUFFLE_LOGIC
        cs = settings.Settings(ARMI_RUN_PATH)
        fakeShuffle = "fakeFile.py"
        cs = cs.modified(newSettings={testSetting: fakeShuffle})

        # ensure we are not in TEST_ROOT
        with directoryChangers.TemporaryDirectoryChanger() as newDir:
            newSettings = cases.case.copyInterfaceInputs(
                cs, destination=newDir.destination
            )
            self.assertFalse(os.path.exists(newSettings[testSetting]))
            self.assertEqual(newSettings[testSetting], fakeShuffle)

    def test_failOnDuplicateSetting(self):
        """
        That that if a plugin attempts to add a duplicate setting, it raises an error.

        .. test:: Plugins cannot register duplicate settings.
            :id: T_ARMI_SETTINGS_UNIQUE
            :tests: R_ARMI_SETTINGS_UNIQUE
        """
        # register the new Plugin
        app = getApp()
        app.pluginManager.register(TestPluginWithDupicateSetting)

        with self.assertRaises(ValueError):
            cs = settings.Settings(ARMI_RUN_PATH)

    def test_copyInterfaceInputs_multipleFiles(self):
        # register the new Plugin
        app = getApp()
        app.pluginManager.register(TestPluginForCopyInterfacesMultipleFiles)

        pluginPath = (
            "armi.cases.tests.test_cases.TestPluginForCopyInterfacesMultipleFiles"
        )
        settingFiles = ["COMPXS.ascii", "ISOAA"]
        testName = "test_copyInterfaceInputs_multipleFiles"
        testSetting = "multipleFilesSetting"

        cs = settings.Settings(ARMI_RUN_PATH)
        cs = cs.modified(
            caseTitle=testName,
            newSettings={testName: [pluginPath]},
        )
        cs = cs.modified(newSettings={testSetting: settingFiles})

        # ensure we are not in TEST_ROOT
        with directoryChangers.TemporaryDirectoryChanger() as newDir:
            newSettings = cases.case.copyInterfaceInputs(
                cs, destination=newDir.destination
            )
            newFilePaths = [os.path.join(newDir.destination, f) for f in settingFiles]
            for newFilePath in newFilePaths:
                self.assertTrue(os.path.exists(newFilePath))
            self.assertEqual(newSettings[testSetting], settingFiles)

    def test_copyInterfaceInputs_wildcardFile(self):
        testSetting = CONF_SHUFFLE_LOGIC
        cs = settings.Settings(ARMI_RUN_PATH)
        # Use something that isn't the shuffle logic file in the case settings
        wcFile = "ISO*"
        cs = cs.modified(newSettings={testSetting: wcFile})

        # ensure we are not in TEST_ROOT
        with directoryChangers.TemporaryDirectoryChanger() as newDir:
            newSettings = cases.case.copyInterfaceInputs(
                cs, destination=newDir.destination
            )
            newFilePath = [os.path.join(newDir.destination, "ISOAA")]
            self.assertTrue(os.path.exists(newFilePath[0]))
            self.assertEqual(
                newSettings[testSetting], [os.path.basename(newFilePath[0])]
            )

        # Check on a file that doesn't exist (so globFilePaths len is 0)
        wcFile = "fakeFile*"
        cs = cs.modified(newSettings={testSetting: wcFile})
        with directoryChangers.TemporaryDirectoryChanger() as newDir:
            newSettings = cases.case.copyInterfaceInputs(
                cs, destination=newDir.destination
            )
            self.assertFalse(os.path.exists(newSettings[testSetting][0]))
            self.assertEqual(newSettings[testSetting], [wcFile])

    def test_copyInterfaceInputs_relPath(self):
        testSetting = CONF_SHUFFLE_LOGIC
        cs = settings.Settings(ARMI_RUN_PATH)
        shuffleFile = cs[testSetting]
        relFile = "../tests/" + shuffleFile
        cs = cs.modified(newSettings={testSetting: relFile})

        # ensure we are not in TEST_ROOT
        with directoryChangers.TemporaryDirectoryChanger() as newDir:
            newSettings = cases.case.copyInterfaceInputs(
                cs, destination=newDir.destination
            )
            newFilePath = os.path.join(newDir.destination, shuffleFile)
            self.assertTrue(os.path.exists(newFilePath))
            self.assertEqual(newSettings[testSetting], os.path.basename(newFilePath))

    def test_copyInterfaceInputs_absPath(self):
        testSetting = CONF_SHUFFLE_LOGIC
        cs = settings.Settings(ARMI_RUN_PATH)
        shuffleFile = cs[testSetting]
        absFile = os.path.dirname(os.path.abspath(ARMI_RUN_PATH))
        absFile = str(os.path.join(absFile, os.path.basename(shuffleFile)))
        cs = cs.modified(newSettings={testSetting: absFile})

        with directoryChangers.TemporaryDirectoryChanger() as newDir:
            newSettings = cases.case.copyInterfaceInputs(
                cs, destination=newDir.destination
            )
            # file exists
            self.assertTrue(os.path.exists(newSettings[testSetting]))
            # but not copied to this dir
            self.assertFalse(os.path.exists(os.path.basename(newSettings[testSetting])))
            self.assertEqual(str(newSettings[testSetting]), absFile)
