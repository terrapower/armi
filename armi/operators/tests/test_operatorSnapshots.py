# Copyright 2022 TerraPower, LLC
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

"""Tests for operator snapshots"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-method-argument,import-outside-toplevel
import unittest

from armi.bookkeeping.db.databaseInterface import DatabaseInterface
from armi.operators.snapshots import OperatorSnapshots
from armi.reactor.tests import test_reactors
from armi.settings.fwSettings.databaseSettings import CONF_FORCE_DB_PARAMS


class TestOperatorSnapshots(unittest.TestCase):
    def setUp(self):
        newSettings = {}
        newSettings["db"] = True
        newSettings["runType"] = "Standard"
        newSettings["verbosity"] = "important"
        newSettings["branchVerbosity"] = "important"
        newSettings["nCycles"] = 1
        newSettings[CONF_FORCE_DB_PARAMS] = ["baseBu"]
        newSettings["dumpSnapshot"] = ["000000", "008000", "016005"]
        o1, self.r = test_reactors.loadTestReactor(customSettings=newSettings)
        self.o = OperatorSnapshots(o1.cs)
        self.o.r = self.r

        # mock a Database Interface
        self.dbi = DatabaseInterface(self.r, o1.cs)
        self.dbi.loadState = lambda c, n: None

    def test_atEOL(self):
        self.assertFalse(self.o.atEOL)

    def test_mainOperate(self):
        # Mock some unimportant tooling
        self.o.interactBOL = lambda: None
        self.o.getInterface = (
            lambda s: self.dbi if s == "database" else super().getInterface(s)
        )
        self.o.interactAllBOC = lambda c: True

        self.assertEqual(self.r.core.p.power, 0.0)
        self.o._mainOperate()
        self.assertEqual(self.r.core.p.power, 100000000.0)


if __name__ == "__main__":
    unittest.main()
