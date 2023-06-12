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

"""This module provides tests for the generic Executers."""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import os
import unittest

from armi.reactor import geometry
from armi.utils import directoryChangers
from armi.physics import executers

# pylint: disable=abstract-method
class MockReactorParams:
    def __init__(self):
        self.cycle = 1
        self.timeNode = 2


class MockCoreParams:
    pass


class MockCore:
    def __init__(self):
        # just pick a random geomType
        self.geomType = geometry.GeomType.CARTESIAN
        self.symmetry = "full"
        self.p = MockCoreParams()


class MockReactor:
    def __init__(self):
        self.core = MockCore()
        self.o = None
        self.p = MockReactorParams()


class TestExecutionOptions(unittest.TestCase):
    def test_runningDirectoryPath(self):
        """
        Test that the running directory path is set up correctly
        based on the case title and label provided.
        """
        e = executers.ExecutionOptions(label=None)
        e.setRunDirFromCaseTitle(caseTitle="test")
        self.assertEqual(os.path.basename(e.runDir), "508bc04f-0")

        e = executers.ExecutionOptions(label="label")
        e.setRunDirFromCaseTitle(caseTitle="test")
        self.assertEqual(os.path.basename(e.runDir), "b07da087-0")

        e = executers.ExecutionOptions(label="label2")
        e.setRunDirFromCaseTitle(caseTitle="test")
        self.assertEqual(os.path.basename(e.runDir), "9c1c83cb-0")


class TestExecuters(unittest.TestCase):
    def setUp(self):
        e = executers.ExecutionOptions(label=None)
        self.executer = executers.DefaultExecuter(e, MockReactor())

    def test_collectInputsAndOutputs(self):
        """
        Verify that the executer can select to not copy back output.
        """
        self.executer.options.inputFile = "test.inp"
        self.executer.options.outputFile = "test.out"
        self.executer.options.copyOutput = False
        inputs, outputs = self.executer._collectInputsAndOutputs()
        self.assertEqual(
            "test.inp", inputs[0], "Input file was not successfully identified."
        )
        self.assertTrue(outputs == [], "Outputs were returned erroneously!")

        self.executer.options.copyOutput = True
        inputs, outputs = self.executer._collectInputsAndOutputs()
        self.assertEqual(
            "test.inp", inputs[0], "Input file was not successfully identified."
        )
        self.assertEqual(
            "test.out", outputs[0], "Output file was not successfully identified."
        )

    def test_updateRunDir(self):
        """
        Verify that runDir is updated when TemporaryDirectoryChanger is used and
        not updated when ForcedCreationDirectoryChanger is used.
        """

        self.assertEqual(
            self.executer.dcType, directoryChangers.TemporaryDirectoryChanger
        )
        self.executer._updateRunDir("updatedRunDir")
        self.assertEqual(self.executer.options.runDir, "updatedRunDir")

        # change directoryChanger type, runDir not updated
        self.executer.options.runDir = "runDir"
        self.executer.dcType = directoryChangers.ForcedCreationDirectoryChanger
        self.executer._updateRunDir("notThisString")
        self.assertEqual(self.executer.options.runDir, "runDir")


if __name__ == "__main__":
    unittest.main()
