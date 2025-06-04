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

import os
import subprocess
import unittest

from armi.physics import executers
from armi.reactor import geometry
from armi.utils import directoryChangers


class MockParams:
    def __init__(self):
        self.cycle = 1
        self.timeNode = 2


class MockCore:
    def __init__(self):
        # just pick a random geomType
        self.geomType = geometry.GeomType.CARTESIAN
        self.symmetry = "full"
        self.p = MockParams()


class MockReactor:
    def __init__(self):
        self.core = MockCore()
        self.o = None
        self.p = MockParams()


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
        """Verify that the executer can select to not copy back output."""
        self.executer.options.inputFile = "test.inp"
        self.executer.options.outputFile = "test.out"
        self.executer.options.copyOutput = False
        inputs, outputs = self.executer._collectInputsAndOutputs()
        self.assertEqual("test.inp", inputs[0], "Input file was not successfully identified.")
        self.assertTrue(outputs == [], "Outputs were returned erroneously!")

        self.executer.options.copyOutput = True
        inputs, outputs = self.executer._collectInputsAndOutputs()
        self.assertEqual("test.inp", inputs[0], "Input file was not successfully identified.")
        self.assertEqual("test.out", outputs[0], "Output file was not successfully identified.")

    def test_updateRunDir(self):
        """
        Verify that runDir is updated when TemporaryDirectoryChanger is used and
        not updated when ForcedCreationDirectoryChanger is used.
        """
        self.assertEqual(self.executer.dcType, directoryChangers.TemporaryDirectoryChanger)
        self.executer._updateRunDir("updatedRunDir")
        self.assertEqual(self.executer.options.runDir, "updatedRunDir")

        # change directoryChanger type, runDir not updated
        self.executer.options.runDir = "runDir"
        self.executer.dcType = directoryChangers.ForcedCreationDirectoryChanger
        self.executer._updateRunDir("notThisString")
        self.assertEqual(self.executer.options.runDir, "runDir")

    def test_runExternalExecutable(self):
        """Run an external executable with an Executer.

        .. test:: Run an external executable with an Executer.
            :id: T_ARMI_EX
            :tests: R_ARMI_EX
        """
        filePath = "test_runExternalExecutable.py"
        outFile = "tmp.txt"
        label = "printExtraStuff"

        class MockExecutionOptions(executers.ExecutionOptions):
            pass

        class MockExecuter(executers.Executer):
            def run(self, args):
                if self.options.label == label:
                    subprocess.run(["python", filePath, "extra stuff"])
                else:
                    subprocess.run(["python", filePath, args])

        with directoryChangers.TemporaryDirectoryChanger():
            # build a mock external program (a little Python script)
            self.__makeALittleTestProgram(filePath, outFile)

            # make sure the output file doesn't exist yet
            self.assertFalse(os.path.exists(outFile))

            # set up an executer for our little test program
            opts = MockExecutionOptions()
            exe = MockExecuter(opts, None)
            exe.run("")

            # make sure the output file exists now
            self.assertTrue(os.path.exists(outFile))

            # run the executer with options
            testString = "some options"
            exe.run(testString)

            # make sure the output file exists now
            self.assertTrue(os.path.exists(outFile))
            newTxt = open(outFile, "r").read()
            self.assertIn(testString, newTxt)

            # now prove the options object can affect the execution
            exe.options.label = label
            exe.run("")
            newerTxt = open(outFile, "r").read()
            self.assertIn("extra stuff", newerTxt)

    @staticmethod
    def __makeALittleTestProgram(filePath, outFile):
        """Helper method to write a tiny Python script.

        We need "an external program" for testing.
        """
        txt = f"""import sys

def main():
    with open("{outFile}", "w") as f:
        f.write(str(sys.argv))

if __name__ == "__main__":
    main()
"""
        with open(filePath, "w") as f:
            f.write(txt)
