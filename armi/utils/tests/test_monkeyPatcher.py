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
"""

from pathlib import Path
import unittest
import tempfile
import os
import io
import contextlib
import sys

# from armi.utils import outputCache

from armi.utils.monkeyPatcher import Patcher

THIS_DIR = Path(__file__).parent
testPatchPath = THIS_DIR / "resources/customPatchTest.py"


class TestMonkeyPatcher(unittest.TestCase):
    def setUp(self):
        # self.tf = tempfile.NamedTemporaryFile(dir=".")
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
    print(4)
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

    def test_simplePrint(self):
        capturedOut = io.StringIO()
        with contextlib.redirect_stdout(capturedOut):
            self.patcher.applyPreOpPatch(globals(), locals())
            self.assertEqual(capturedOut.getvalue(), "foo\n")
        return

    def test_MethodInjection(self):
        from armi.operators import operator

        self.patcher.applyPostOpPatch(globals(), locals())
        self.assertEqual(operator.testAttribute, "eggs")
        self.assertEqual(operator.testStaticMethod(), "spam")
        self.assertEqual(operator.testMethod(), "armi.operators.operator")

        return

    def test_ClassInjection(self):
        self.patcher.applyPostInterfacePatch(globals(), locals())
        testClass = TestNewClass()
        self.assertEqual(testClass.testAttribute, "eggs")
        self.assertEqual(testClass.simpleMethod(), 2)
        return

    def test_MethodSOMETHING(self):
        from armi.operators import operator

        self.patcher.applyPostRestartLoadPatch(globals(), locals())


if __name__ == "__main__":
    unittest.main()
