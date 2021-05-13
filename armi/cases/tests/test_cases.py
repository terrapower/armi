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
Unit tests for Case and CaseSuite objects
"""
import unittest
import os
import io
import platform

from armi import cases
from armi import settings
from armi.utils import directoryChangers
from armi.tests import ARMI_RUN_PATH
from armi.tests import TEST_ROOT
from armi.reactor import blueprints, systemLayoutInput


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
    """Class to tests armi.cases.Case methods"""

    def test_summarizeDesign(self):
        """
        Ensure that the summarizeDesign method runs.

        Any assertions are bonus.
        """
        with directoryChangers.TemporaryDirectoryChanger():  # ensure we are not in IN_USE_TEST_ROOT
            cs = settings.Settings(ARMI_RUN_PATH)
            cs["verbosity"] = "important"
            case = cases.Case(cs)
            c2 = case.clone()
            c2.summarizeDesign(True, True)
            self.assertTrue(os.path.exists("Core Design Report.html"))

    def test_independentVariables(self):
        """Ensure that independentVariables added to a case move with it."""
        geom = systemLayoutInput.SystemLayoutInput()
        geom.readGeomFromStream(io.StringIO(GEOM_INPUT))
        bp = blueprints.Blueprints.load(BLUEPRINT_INPUT)
        cs = settings.Settings(ARMI_RUN_PATH)
        cs["verbosity"] = "important"
        baseCase = cases.Case(cs, bp=bp, geom=geom)
        with directoryChangers.TemporaryDirectoryChanger():  # ensure we are not in IN_USE_TEST_ROOT
            vals = {"cladThickness": 1, "control strat": "good", "enrich": 0.9}
            case = baseCase.clone()
            case._independentVariables = vals  # pylint: disable=protected-access
            case.writeInputs()
            newCs = settings.Settings(fName=case.title + ".yaml")
            newCase = cases.Case(newCs)
            for name, val in vals.items():
                self.assertEqual(newCase.independentVariables[name], val)


class TestCaseSuiteDependencies(unittest.TestCase):
    """CaseSuite tests"""

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
            self.c2.cs["loadStyle"] = "fromDB"
            self.c2.cs["reloadDBName"] = dbPath
            # note that case.dependencies is a property and
            # will actually reflect these changes
            self.assertEqual(
                isIn,
                self.c1 in self.c2.dependencies,
                "where p1: {} p2: {} dbPath: {}".format(p1, p2, dbPath),
            )

    def test_dependencyFromDBName(self):
        self.c2.cs[
            "reloadDBName"
        ] = "c1.h5"  # no effect -> need to specify loadStyle, 'fromDB'
        self.assertEqual(0, len(self.c2.dependencies))
        self.c2.cs["loadStyle"] = "fromDB"
        self.assertIn(self.c1, self.c2.dependencies)

        # the .h5 extension is optional
        self.c2.cs["reloadDBName"] = "c1"
        self.assertIn(self.c1, self.c2.dependencies)

    def test_dependencyFromExplictRepeatShuffles(self):
        self.assertEqual(0, len(self.c2.dependencies))
        self.c2.cs["explicitRepeatShuffles"] = "c1-SHUFFLES.txt"
        self.assertIn(self.c1, self.c2.dependencies)


class TestExtraInputWriting(unittest.TestCase):
    """Make sure extra inputs from interfaces are written."""

    def test_writeInput(self):
        fName = os.path.join(TEST_ROOT, "armiRun.yaml")
        cs = settings.Settings(fName)
        baseCase = cases.Case(cs)
        with directoryChangers.TemporaryDirectoryChanger():
            case = baseCase.clone()
            case.writeInputs()
            self.assertTrue(os.path.exists(cs["shuffleLogic"]))


if __name__ == "__main__":
    # import sys; sys.argv = ['', 'TestArmiCase.test_independentVariables']
    unittest.main()
