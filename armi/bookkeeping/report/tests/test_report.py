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

"""Really basic tests of the report Utils"""
import logging
import unittest

from armi import runLog, settings
from armi.bookkeeping import report
from armi.bookkeeping.report import data, reportInterface
from armi.bookkeeping.report.reportingUtils import (
    writeAssemblyMassSummary,
    makeBlockDesignReport,
    setNeutronBalancesReport,
    summarizePinDesign,
    summarizePowerPeaking,
    summarizePower,
)
from armi.reactor.tests.test_reactors import loadTestReactor
from armi.tests import mockRunLogs


class TestReport(unittest.TestCase):
    def setUp(self):
        self.test_group = data.Table(settings.getMasterCs(), "banana")

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

    def test_printReports(self):
        """testing testing

        :ref:`REQ86d884bb-6133-4078-8804-5a334c935338`
        """
        repInt = reportInterface.ReportInterface(None, None)
        rep = repInt.printReports()

        self.assertIn("REPORTS BEGIN", rep)
        self.assertIn("REPORTS END", rep)

    def test_writeReports(self):
        """Test writing html reports."""
        repInt = reportInterface.ReportInterface(None, None)
        repInt.writeReports()

    def test_reactorSpecificReporting(self):
        """Test a number of reporting utils that require reactor/core information"""
        o, r = loadTestReactor()

        with mockRunLogs.BufferLog() as mock:
            # we should start with a clean slate
            self.assertEqual("", mock._outputStream)
            runLog.LOG.startLog("test_reactorSpecificReporting")
            runLog.LOG.setVerbosity(logging.INFO)

            writeAssemblyMassSummary(r)
            self.assertIn("BOL Assembly Mass Summary", mock._outputStream)
            self.assertIn("igniter fuel", mock._outputStream)
            self.assertIn("primary control", mock._outputStream)
            self.assertIn("plenum", mock._outputStream)
            mock._outputStream = ""

            setNeutronBalancesReport(r.core)
            self.assertIn("No rate information", mock._outputStream)
            mock._outputStream = ""

            summarizePinDesign(r.core)
            self.assertIn("Assembly Design Summary", mock._outputStream)
            self.assertIn("Design & component information", mock._outputStream)
            self.assertIn("Multiplicity", mock._outputStream)
            mock._outputStream = ""

            summarizePower(r.core)
            self.assertIn("Power in radial shield", mock._outputStream)
            self.assertIn("Power in primary control", mock._outputStream)
            self.assertIn("Power in feed fuel", mock._outputStream)
            mock._outputStream = ""

            # this report won't do much for the test reactor - improve test reactor
            makeBlockDesignReport(r)
            self.assertTrue(len(mock._outputStream) == 0)
            mock._outputStream = ""

            # this report won't do much for the test reactor - improve test reactor
            summarizePowerPeaking(r.core)
            self.assertTrue(len(mock._outputStream) == 0)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
