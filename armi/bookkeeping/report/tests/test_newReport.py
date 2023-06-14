# Copyright 2020 TerraPower, LLC
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

"""Test new reports."""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import collections
import os
import unittest

import htmltree

from armi import getPluginManagerOrFail
from armi.bookkeeping.report import newReports
from armi.bookkeeping.report import data
from armi.physics.neutronics.reports import neutronicsPlotting
from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT
from armi.tests import mockRunLogs
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class TestReportContentCreation(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor(TEST_ROOT)
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    def test_timeSeries(self):
        """Test execution of TimeSeries object."""
        times = [0.1, 0.3, 0.5, 0.7, 0.9, 1.1, 1.3]
        data1 = [7, 4, 3, 2, 1, 5, 7]
        data2 = [1, 2, 3, 4, 5, 5, 7]
        # Labels are predetermined at creation...
        series = newReports.TimeSeries(
            "Example Plot",
            "ReactorName",
            ["data1", "data2"],
            "height (cm)",
            "plotexample.png",
            "This is the Caption",
        )

        for val in range(len(times)):
            series.add("data1", times[val], data1[val])
            series.add("data2", times[val], data2[val])

        series.plot()
        self.assertTrue(os.path.exists("ReactorName.plotexample.png"))

    def test_tableCreation(self):
        header = ["item", "value"]
        table = newReports.Table("Assembly Table", "table of assemblies", header)

        for assem in self.r.core.getAssemblies():
            table.addRow([assem.p.type, assem.p.powerDecay])

        result = table.render(0)
        self.assertTrue(isinstance(result, htmltree.HtmlElement))

    def test_reportContents(self):
        reportTest = newReports.ReportContent("Test")

        getPluginManagerOrFail().hook.getReportContents(
            r=self.r,
            cs=self.o.cs,
            report=reportTest,
            stage=newReports.ReportStage.Begin,
            blueprint=self.r.blueprints,
        )

        self.assertTrue(isinstance(reportTest.sections, collections.OrderedDict))
        self.assertIn("Comprehensive Report", reportTest.sections)
        self.assertIn("Design", reportTest.sections)
        self.assertIn("Neutronics", reportTest.sections)
        self.assertTrue(isinstance(reportTest.tableOfContents(), htmltree.HtmlElement))

    def test_reportContentsEnd(self):
        reportTest = newReports.ReportContent("Test")

        getPluginManagerOrFail().hook.getReportContents(
            r=self.r,
            cs=self.o.cs,
            report=reportTest,
            stage=newReports.ReportStage.End,
            blueprint=self.r.blueprints,
        )

        self.assertTrue(isinstance(reportTest.sections, collections.OrderedDict))
        self.assertNotIn("Comprehensive Report", reportTest.sections)
        self.assertIn("Design", reportTest.sections)
        self.assertIn("Neutronics", reportTest.sections)
        self.assertTrue(isinstance(reportTest.tableOfContents(), htmltree.HtmlElement))

    def test_neutronicsPlotFunctions(self):
        reportTest = newReports.ReportContent("Test")

        neutronicsPlotting(self.r, reportTest, self.o.cs)
        self.assertIn("Neutronics", reportTest.sections)
        self.assertTrue(
            isinstance(reportTest["Neutronics"]["Keff-Plot"], newReports.TimeSeries)
        )

    def test_writeReports(self):
        reportTest = newReports.ReportContent("Test")
        table = newReports.Table("Example")
        table.addRow(["example", 1])
        table.addRow(["example", 2])

        reportTest["TableTest"]["Table Example"] = table

        reportTest.writeReports()
        # Want to check that two <tr> exists...
        times = 0
        with open("index.html") as f:
            for line in f:
                if "<tr>" in line:
                    times = times + 1
        self.assertEqual(times, 2)

    def test_reportBasics(self):
        env = data.Report("Environment", "ARMI Env Info")

        s = str(env)
        self.assertIn("Environment", s)
        self.assertIn("Env Info", s)

        gro = env._groupRenderOrder
        self.assertEqual(len(gro), 0)

        self.assertIsNone(env["Environment"])

    def test_reportLogs(self):
        env = data.Report("Environment", "ARMI Env Info")

        with mockRunLogs.BufferLog() as mock:
            self.assertEqual("", mock.getStdout())
            _ = env["badStuff"]
            self.assertIn("Cannot locate group", mock.getStdout())

            mock.emptyStdout()
            self.assertEqual("", mock.getStdout())
            env.writeHTML()
            self.assertIn("Writing HTML document", mock.getStdout())
            self.assertIn("[info] HTML document", mock.getStdout())
