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

"""Really basic tests of the report Utils."""

import logging
import os
import subprocess
import sys
import unittest
from glob import glob
from unittest.mock import patch

from armi import runLog, settings
from armi.bookkeeping import report
from armi.bookkeeping.report import data, reportInterface
from armi.bookkeeping.report.reportingUtils import (
    _getSystemInfoLinux,
    _getSystemInfoMac,
    _getSystemInfoWindows,
    getNodeName,
    getSystemInfo,
    makeBlockDesignReport,
    makeCoreDesignReport,
    setNeutronBalancesReport,
    summarizePinDesign,
    summarizePowerPeaking,
    writeAssemblyMassSummary,
    writeCycleSummary,
    writeWelcomeHeaders,
)
from armi.testing import loadTestReactor
from armi.tests import mockRunLogs
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class _MockReturnResult:
    """Mocking the subprocess.run() return object."""

    def __init__(self, stdout):
        self.stdout = stdout


class TestReportingUtils(unittest.TestCase):
    def test_getSystemInfoLinux(self):
        """Test _getSystemInfoLinux() on any operating system, by mocking the system calls."""
        osInfo = '"Ubuntu 22.04.3 LTS"'
        procInfo = """processor : 0
vendor_id   : GenuineIntel
cpu family  : 6
model       : 126
model name  : Intel(R) Core(TM) i5-1035G1 CPU @ 1.00GHz
...
"""
        correctResult = """OS Info:  "Ubuntu 22.04.3 LTS"
Processor(s):
    processor : 0
    vendor_id   : GenuineIntel
    cpu family  : 6
    model       : 126
    model name  : Intel(R) Core(TM) i5-1035G1 CPU @ 1.00GHz
    ..."""

        def __mockSubprocessRun(*args, **kwargs):
            if "os-release" in args[0]:
                return _MockReturnResult(osInfo)
            else:
                return _MockReturnResult(procInfo)

        with patch.object(subprocess, "run", side_effect=__mockSubprocessRun):
            out = _getSystemInfoLinux()
            self.assertEqual(out.strip(), correctResult)

    @patch("subprocess.run")
    def test_getSystemInfoWindows(self, mockSubprocess):
        """Test _getSystemInfoWindows() on any operating system, by mocking the system call."""
        windowsResult = """OS Name:         Microsoft Windows 10 Enterprise
OS Version:      10.0.19041 N/A Build 19041
Processor(s):    1 Processor(s) Installed.
                 [01]: Intel64 Family 6 Model 142 Stepping 12 GenuineIntel ~801 Mhz"""

        mockSubprocess.return_value = _MockReturnResult(windowsResult)

        out = _getSystemInfoWindows()
        self.assertEqual(out, windowsResult)

    @patch("subprocess.run")
    def test_getSystemInfoMac(self, mockSubprocess):
        """Test _getSystemInfoMac() on any operating system, by mocking the system call."""
        macResult = b"""System Software Overview:

        System Version: macOS 12.1 (21C52)
        Kernel Version: Darwin 21.2.0
        ...
        Hardware Overview:
        Model Name: MacBook Pro
        ..."""

        mockSubprocess.return_value = _MockReturnResult(macResult)

        out = _getSystemInfoMac()
        self.assertEqual(out, macResult.decode("utf-8"))

    def test_getSystemInfo(self):
        """Basic sanity check of getSystemInfo() running in the wild.

        This test should pass if it is run on Window or mainstream Linux distros. But we expect this
        to fail if the test is run on some other OS.
        """
        if "darwin" in sys.platform:
            # too complicated to test MacOS in this method
            return

        out = getSystemInfo()
        substrings = ["OS ", "Processor(s):"]

        for sstr in substrings:
            self.assertIn(sstr, out)

        self.assertGreater(len(out), sum(len(sstr) + 5 for sstr in substrings))

    def test_getNodeName(self):
        """Test that the getNodeName() method returns a non-empty string.

        It is hard to know what string SHOULD be return here, and it would depend on how the OS is
        set up on your machine or cluster. But this simple test needs to pass as-is on Windows
        and Linux.
        """
        self.assertGreater(len(getNodeName()), 0)


class TestReport(unittest.TestCase):
    def setUp(self):
        self.test_group = data.Table(settings.Settings(), "banana")

    def test_setData(self):
        report.setData("banana_1", ["sundae", "plain"])
        report.setData("banana_2", ["sundae", "vanilla"], self.test_group)
        report.setData("banana_3", ["sundae", "chocolate"], self.test_group, [report.ALL])

        with self.assertRaises(AttributeError):
            report.setData("banana_4", ["sundae", "strawberry"], "no_workie", [report.ALL])
        with self.assertRaises(AttributeError):
            report.setData("banana_5", ["sundae", "peanut_butter"], self.test_group, "no_workie")

        ungroup_instance = report.ALL[report.UNGROUPED]
        self.assertEqual(ungroup_instance["banana_1"], ["sundae", "plain"])

        filled_instance = report.ALL[self.test_group]
        self.assertEqual(filled_instance["banana_2"], ["sundae", "vanilla"])
        self.assertEqual(filled_instance["banana_3"], ["sundae", "chocolate"])

    def test_getData(self):
        # test the null case
        self.assertIsNone(self.test_group["fake"])

        # insert some data
        self.test_group["banana_1"] = ["sundae", "plain"]

        # validate we can pull that data back out again
        data = self.test_group["banana_1"]
        self.assertEqual(len(data), 2)
        self.assertIn("sundae", data)
        self.assertIn("plain", data)

    def test_reactorSpecificReporting(self):
        """Test a number of reporting utils that require reactor/core information."""
        o, r = loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")

        # make sure makeCoreDesignReport() doesn't fail, though it won't generate an output here
        makeCoreDesignReport(r.core, o.cs)
        self.assertEqual(len(glob("*.html")), 0)

        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock.getStdout())
            runLog.LOG.startLog("test_reactorSpecificReporting")
            runLog.LOG.setVerbosity(logging.INFO)

            writeAssemblyMassSummary(r)
            self.assertIn("BOL Assembly Mass Summary", mock.getStdout())
            self.assertIn("igniter fuel", mock.getStdout())
            mock.emptyStdout()

            setNeutronBalancesReport(r.core)
            self.assertIn("No rate information", mock.getStdout())
            mock.emptyStdout()

            r.core.getFirstBlock().p.rateCap = 1.0
            r.core.getFirstBlock().p.rateProdFis = 1.02
            r.core.getFirstBlock().p.rateFis = 1.01
            r.core.getFirstBlock().p.rateAbs = 1.0
            setNeutronBalancesReport(r.core)
            self.assertIn("Fission", mock.getStdout())
            self.assertIn("Capture", mock.getStdout())
            self.assertIn("Absorption", mock.getStdout())
            self.assertIn("Leakage", mock.getStdout())
            mock.emptyStdout()

            summarizePinDesign(r.core)
            self.assertIn("Assembly Design Summary", mock.getStdout())
            self.assertIn("Design & component information", mock.getStdout())
            self.assertIn("Multiplicity", mock.getStdout())
            mock.emptyStdout()

            writeCycleSummary(r.core)
            self.assertIn("Core Average", mock.getStdout())
            self.assertIn("End of Cycle", mock.getStdout())
            mock.emptyStdout()

            # this report won't do much for the test reactor - improve test reactor
            makeBlockDesignReport(r)
            self.assertEqual(len(mock.getStdout()), 0)
            mock.emptyStdout()

            # this report won't do much for the test reactor - improve test reactor
            summarizePowerPeaking(r.core)
            self.assertEqual(len(mock.getStdout()), 0)

    def test_writeWelcomeHeaders(self):
        o, r = loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")

        # grab this file path
        randoFile = os.path.abspath(__file__)

        # pass that random file into the settings
        o.cs["crossSectionControl"]["DA"].xsFileLocation = randoFile
        o.cs["crossSectionControl"]["DA"].fluxFileLocation = randoFile

        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock.getStdout())
            runLog.LOG.startLog("test_writeWelcomeHeaders")
            runLog.LOG.setVerbosity(logging.INFO)

            writeWelcomeHeaders(o, o.cs)

            # assert our random file (and a lot of other stuff) is in the welcome
            self.assertIn("Case Info", mock.getStdout())
            self.assertIn("Input File Info", mock.getStdout())
            self.assertIn("crossSectionControl-DA", mock.getStdout())
            self.assertIn("Python Executable", mock.getStdout())
            self.assertIn(randoFile, mock.getStdout())


class TestReportInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = TemporaryDirectoryChanger()
        cls.td.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.td.__exit__(None, None, None)

    def test_printReports(self):
        """Testing printReports method."""
        repInt = reportInterface.ReportInterface(None, None)
        rep = repInt.printReports()

        self.assertIn("REPORTS BEGIN", rep)
        self.assertIn("REPORTS END", rep)

    def test_distributableReportInt(self):
        repInt = reportInterface.ReportInterface(None, None)
        self.assertEqual(repInt.distributable(), 4)

    def test_interactBOLReportInt(self):
        o, r = loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        repInt = reportInterface.ReportInterface(r, o.cs)

        with mockRunLogs.BufferLog() as mock:
            repInt.interactBOL()
            self.assertIn("Writing assem layout", mock.getStdout())
            self.assertIn("BOL Assembly", mock.getStdout())
            self.assertIn("wetMass", mock.getStdout())

    def test_interactEveryNode(self):
        o, r = loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        repInt = reportInterface.ReportInterface(r, o.cs)

        with mockRunLogs.BufferLog() as mock:
            repInt.interactEveryNode(0, 0)
            self.assertIn("Cycle 0", mock.getStdout())
            self.assertIn("node 0", mock.getStdout())
            self.assertIn("keff=", mock.getStdout())

    def test_interactBOC(self):
        o, r = loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        repInt = reportInterface.ReportInterface(r, o.cs)

        self.assertEqual(repInt.fuelCycleSummary["bocFissile"], 0.0)
        repInt.interactBOC(1)
        self.assertAlmostEqual(repInt.fuelCycleSummary["bocFissile"], 4.290603409612653)

    def test_interactEOC(self):
        o, r = loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        repInt = reportInterface.ReportInterface(r, o.cs)

        with mockRunLogs.BufferLog() as mock:
            repInt.interactEOC(0)
            self.assertIn("Cycle 0", mock.getStdout())
            self.assertIn("TIMER REPORTS", mock.getStdout())

    def test_interactEOL(self):
        o, r = loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        repInt = reportInterface.ReportInterface(r, o.cs)

        with mockRunLogs.BufferLog() as mock:
            repInt.interactEOL()
            self.assertIn("Comprehensive Core Report", mock.getStdout())
            self.assertIn("Assembly Area Fractions", mock.getStdout())
