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
import unittest

from armi import runLog, settings
from armi.bookkeeping import report
from armi.bookkeeping.report import data, reportInterface
from armi.bookkeeping.report.reportingUtils import (
    makeBlockDesignReport,
    setNeutronBalancesReport,
    summarizePinDesign,
    summarizePower,
    summarizePowerPeaking,
    writeAssemblyMassSummary,
    writeCycleSummary,
    writeWelcomeHeaders,
)
from armi.reactor.tests.test_reactors import loadTestReactor
from armi.tests import mockRunLogs


class TestReport(unittest.TestCase):
    def setUp(self):
        self.test_group = data.Table(settings.Settings(), "banana")

    def test_setData(self):
        report.setData("banana_1", ["sundae", "plain"])
        report.setData("banana_2", ["sundae", "vanilla"], self.test_group)
        report.setData(
            "banana_3", ["sundae", "chocolate"], self.test_group, [report.ALL]
        )

        with self.assertRaises(AttributeError):
            report.setData(
                "banana_4", ["sundae", "strawberry"], "no_workie", [report.ALL]
            )
        with self.assertRaises(AttributeError):
            report.setData(
                "banana_5", ["sundae", "peanut_butter"], self.test_group, "no_workie"
            )

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
        o, r = loadTestReactor()

        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock.getStdout())
            runLog.LOG.startLog("test_reactorSpecificReporting")
            runLog.LOG.setVerbosity(logging.INFO)

            writeAssemblyMassSummary(r)
            self.assertIn("BOL Assembly Mass Summary", mock.getStdout())
            self.assertIn("igniter fuel", mock.getStdout())
            self.assertIn("primary control", mock.getStdout())
            self.assertIn("plenum", mock.getStdout())
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

            summarizePower(r.core)
            self.assertIn("Power in radial shield", mock.getStdout())
            self.assertIn("Power in primary control", mock.getStdout())
            self.assertIn("Power in feed fuel", mock.getStdout())
            mock.emptyStdout()

            writeCycleSummary(r.core)
            self.assertIn("Core Average", mock.getStdout())
            self.assertIn("Outlet Temp", mock.getStdout())
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
        o, r = loadTestReactor()

        # grab this file path
        randoFile = os.path.abspath(__file__)

        # pass that random file into the settings
        o.cs["crossSectionControl"]["DA"].xsFileLocation = randoFile

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
            self.assertIn(randoFile, mock.getStdout())


class TestReportInterface(unittest.TestCase):
    def test_printReports(self):
        """Testing printReports method."""
        repInt = reportInterface.ReportInterface(None, None)
        rep = repInt.printReports()

        self.assertIn("REPORTS BEGIN", rep)
        self.assertIn("REPORTS END", rep)

    def test_writeReports(self):
        """Test writing html reports."""
        repInt = reportInterface.ReportInterface(None, None)
        repInt.writeReports()

    def test_distributableReportInt(self):
        repInt = reportInterface.ReportInterface(None, None)
        self.assertEqual(repInt.distributable(), 4)

    def test_interactBOLReportInt(self):
        o, r = loadTestReactor()
        repInt = reportInterface.ReportInterface(r, o.cs)

        with mockRunLogs.BufferLog() as mock:
            repInt.interactBOL()
            self.assertIn("Writing assem layout", mock.getStdout())
            self.assertIn("BOL Assembly", mock.getStdout())
            self.assertIn("wetMass", mock.getStdout())
            self.assertIn("moveable plenum", mock.getStdout())

    def test_interactEveryNode(self):
        o, r = loadTestReactor()
        repInt = reportInterface.ReportInterface(r, o.cs)

        with mockRunLogs.BufferLog() as mock:
            repInt.interactEveryNode(0, 0)
            self.assertIn("Cycle 0", mock.getStdout())
            self.assertIn("node 0", mock.getStdout())
            self.assertIn("keff=", mock.getStdout())

    def test_interactBOC(self):
        o, r = loadTestReactor()
        repInt = reportInterface.ReportInterface(r, o.cs)

        self.assertEqual(repInt.fuelCycleSummary["bocFissile"], 0.0)
        repInt.interactBOC(1)
        self.assertAlmostEqual(repInt.fuelCycleSummary["bocFissile"], 726.30401755)

    def test_interactEOC(self):
        o, r = loadTestReactor()
        repInt = reportInterface.ReportInterface(r, o.cs)

        with mockRunLogs.BufferLog() as mock:
            repInt.interactEOC(0)
            self.assertIn("Cycle 0", mock.getStdout())
            self.assertIn("TIMER REPORTS", mock.getStdout())

    def test_interactEOL(self):
        o, r = loadTestReactor()
        repInt = reportInterface.ReportInterface(r, o.cs)

        with mockRunLogs.BufferLog() as mock:
            repInt.interactEOL()
            self.assertIn("Comprehensive Core Report", mock.getStdout())
            self.assertIn("Assembly Area Fractions", mock.getStdout())
