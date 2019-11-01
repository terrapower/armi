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

"""

"""
import unittest

from armi import settings
from armi.bookkeeping import report
from armi.bookkeeping.report import data


class TestReport(unittest.TestCase):
    def setUp(self):
        self.test_group = data.Table(settings.getMasterCs(), "banana")

    def tearDown(self):
        pass

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
        from armi.bookkeeping.report import reportInterface

        repInt = reportInterface.ReportInterface(None, None)
        repInt.printReports()

    def test_writeReports(self):
        """Test writing html reports."""
        from armi.bookkeeping.report import reportInterface

        repInt = reportInterface.ReportInterface(None, None)
        repInt.writeReports()


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
