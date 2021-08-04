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

"""Test reports."""
import os
from typing import OrderedDict
import unittest

from armi.tests import TEST_ROOT
from armi.reactor.tests import test_reactors
from armi.bookkeeping import newReports
from armi.utils import directoryChangers


class TestReportContentCreation(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor(TEST_ROOT)

    def testTimeSeries(self):
        """Test execution of TimeSeries object."""
        with directoryChangers.TemporaryDirectoryChanger():
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

    def testTableCreation(self):
        import htmltree

        header = ["item", "value"]
        table = newReports.Table("Assembly Table", "table of assemblies", header)

        for assem in self.r.core.getAssemblies():
            table.addRow([assem.p.type, assem.p.powerDecay])

        result = table.render(0)
        self.assertTrue(isinstance(result, htmltree.HtmlElement))

    def testReportContents(self):
        import collections
        import armi
        import armi.bookkeeping.newReports
        from armi.cli.reportsEntryPoint import ReportStage

        reportTest = newReports.ReportContent("Test")

        armi.getPluginManagerOrFail().hook.getReportContents(
            r=self.r,
            cs=self.o.cs,
            report=reportTest,
            stage=ReportStage.Begin,
            blueprint=self.r.blueprints,
        )

        self.assertTrue(isinstance(reportTest.sections, collections.OrderedDict))
        self.assertTrue("Comprehensive Report" in reportTest.sections)
        self.assertTrue("Neutronics" in reportTest.sections)


if __name__ == "__main__":
    unittest.main()
