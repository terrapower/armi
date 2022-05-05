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
"""
Test the monkeyPatcher module.

The file written by the setUp method test suite can also give users a jumpstart 
on how to write an effective patch file.
"""

import unittest
import os
import io
import contextlib
import numpy as np

from armi.utils.monkeyPatcher import Patcher


class TestMonkeyPatcher(unittest.TestCase):
    def setUp(self):
        self.tf = open(r".\tempPatcherFile.py", "w")
        self.tf.write(
            """
def preOpPatch(upper_globals, upper_locals):
    print("foo")
    return

def postOpPatch(upper_globals, upper_locals):
    import types

    def testStaticMethod():
        return "spam"

    def testMethod(self):
        return self.__name__

    upper_locals["operator"].testStaticMethod = testStaticMethod
    upper_locals["operator"].testAttribute = "eggs"
    upper_locals["operator"].testMethod = types.MethodType(testMethod, upper_locals["operator"])
    upper_globals["np"].pi = 3  # Comply with Indiana bill #246
    upper_globals["np"].testStaticMethod = testStaticMethod
    upper_globals["np"].testMethod = types.MethodType(testMethod, upper_globals["np"])
    return

def postInterfacePatch(upper_globals, upper_locals):
    class NewClass():
        testAttribute = "eggs"
        
        def __init__(self):
            return

        def simpleMethod(self):
            return 2

    upper_globals["TestNewClass"] = NewClass
    return

def postRestartLoadPatch(upper_globals, upper_locals):
    return
"""
        )
        self.tf.close()
        self.tempPatchFileName = r".\tempPatcherFile.py"
        self.tf = open(self.tempPatchFileName)
        dummyCS = {"patchFilePath": self.tempPatchFileName}
        self.patcher = Patcher(dummyCS)
        return

    def tearDown(self):
        self.tf.close()
        os.remove(self.tempPatchFileName)
        return

    def test_SimplePrint(self):
        """
        This test covers very simple operations that do not modify objects in
        the upper level scopes, like printing.
        """
        capturedOut = io.StringIO()
        with contextlib.redirect_stdout(capturedOut):
            self.patcher.applyPreOpPatch(globals(), locals())
            self.assertEqual(capturedOut.getvalue(), "foo\n")
        return

    def test_MethodInjection(self):
        """
        This test injects methods and attributes into preexisting classes.
        """
        from armi.operators import operator

        self.patcher.applyPostOpPatch(globals(), locals())
        # test local scope
        self.assertEqual(operator.testAttribute, "eggs")
        self.assertEqual(operator.testStaticMethod(), "spam")
        self.assertEqual(operator.testMethod(), "armi.operators.operator")

        # Test global scope
        self.assertEqual(np.pi, 3)
        self.assertEqual(np.testStaticMethod(), "spam")
        self.assertEqual(np.testMethod(), "numpy")

        return

    def test_ClassInjection(self):
        """
        Test that a new class can be injected
        """
        self.patcher.applyPostInterfacePatch(globals(), locals())
        testClass = TestNewClass()
        self.assertEqual(testClass.testAttribute, "eggs")
        self.assertEqual(testClass.simpleMethod(), 2)
        return

    def test_Empty(self):
        """
        Test that the empty case returns with None
        """
        self.assertEqual(
            self.patcher.applyPostRestartLoadPatch(globals(), locals()), None
        )

    def test_NoInputFile(self):
        """
        Test if an error is raised when the target file does not exist.
        """
        self.assertRaises(
            IOError,
            Patcher,
            {"patchFilePath": "./thisFileDoesNotExistasdffdsa123321.nope"},
        )
        return

    def test_NoInputPath(self):
        """
        Test that the patcher returns when no input file is specified
        """
        patcher = Patcher({"patchFilePath": ""})
        self.assertEqual(patcher.applyPreOpPatch(), None)
        self.assertEqual(patcher.applyPostOpPatch(), None)
        self.assertEqual(patcher.applyPostInterfacePatch(), None)
        self.assertEqual(patcher.applyPostRestartLoadPatch(), None)
        return

    def test_RaisesErrors(self):
        """
        Test that errors from the patchfile are raised properly
        """
        patchFileWithErrors = """
def preOpPatch(upper_globals, upper_locals):
    # foo not defined
    foo == "bar"
    return

def postOpPatch(upper_globals, upper_locals):
    # foo not defined
    foo == "bar"
    return

def postInterfacePatch(upper_globals, upper_locals):
    # foo not defined
    foo == "bar"
    return

def postRestartLoadPatch(upper_globals, upper_locals):
    # foo not defined
    foo == "bar"
    return
"""
        with open("./tempPatchFileWithErrors.py", "w") as f:
            f.write(patchFileWithErrors)
        patcher = Patcher({"patchFilePath": "./tempPatchFileWithErrors.py"})
        self.assertRaises(NameError, patcher.applyPreOpPatch, globals(), locals())
        self.assertRaises(NameError, patcher.applyPostOpPatch, globals(), locals())
        self.assertRaises(
            NameError, patcher.applyPostInterfacePatch, globals(), locals()
        )
        self.assertRaises(
            NameError, patcher.applyPostRestartLoadPatch, globals(), locals()
        )
        os.remove("./tempPatchFileWithErrors.py")


if __name__ == "__main__":
    unittest.main()
