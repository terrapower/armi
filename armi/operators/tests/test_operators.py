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
Tests for operators
"""
# pylint: disable=abstract-method,no-self-use,unused-argument

import os
import unittest
import subprocess

import pytest

import armi
from armi import settings
from armi.operators import OperatorMPI
from armi.tests import ARMI_RUN_PATH
from armi.interfaces import Interface
from armi.reactor.tests import test_reactors


class FailingInterface1(Interface):
    """utility classes to make sure the logging system fails properly"""

    name = "failer"

    def interactEveryNode(self, cycle, node):
        raise RuntimeError("Failing interface failure")


class FailingInterface2(Interface):
    """utility class to make sure the logging system fails properly"""

    name = "failer"

    def interactEveryNode(self, cycle, node):
        raise RuntimeError("Failing interface critical failure")


class FailingInterface3(Interface):
    """fails on worker operate"""

    name = "failer"

    def fail(self):
        raise RuntimeError("Failing interface critical worker failure")

    def interactEveryNode(self, c, n):  # pylint:disable=unused-argument
        armi.MPI_COMM.bcast("fail", root=0)

    def workerOperate(self, cmd):
        if cmd == "fail":
            self.fail()
            return True
        return False


class InterfaceA(Interface):
    function = "A"
    name = "First"


class InterfaceB(InterfaceA):
    """Dummy Interface that extends A"""

    function = "A"
    name = "Second"


class InterfaceC(Interface):
    function = "A"
    name = "Third"


class OperatorTests(unittest.TestCase):
    def test_addInterfaceSubclassCollision(self):

        self.cs = settings.Settings()
        o, r = test_reactors.loadTestReactor()

        interfaceA = InterfaceA(r, self.cs)

        interfaceB = InterfaceB(r, self.cs)
        o.addInterface(interfaceA)

        # 1) Adds B and gets rid of A
        o.addInterface(interfaceB)
        self.assertEqual(o.getInterface("Second"), interfaceB)
        self.assertEqual(o.getInterface("First"), None)

        # 2) Now we have B which is a subclass of A,
        #    we want to not add A (but also not have an error)

        o.addInterface(interfaceA)
        self.assertEqual(o.getInterface("Second"), interfaceB)
        self.assertEqual(o.getInterface("First"), None)

        # 3) Also if another class not a subclass has the same function,
        #    raise an error
        interfaceC = InterfaceC(r, self.cs)

        self.assertRaises(RuntimeError, o.addInterface, interfaceC)

        # 4) Check adding a different function Interface

        interfaceC.function = "C"

        o.addInterface(interfaceC)
        self.assertEqual(o.getInterface("Second"), interfaceB)
        self.assertEqual(o.getInterface("Third"), interfaceC)


class OperatorMPITests(unittest.TestCase):
    """Testing the MPI parallelization operation"""

    # @unittest.skipIf(distutils.spawn.find_executable('mpiexec.exe') is None, "mpiexec is not in path.")
    @unittest.skip("MPI tests are not working")
    def testMpiOperator(self):  # pylint: disable=abstract-method,no-self-use
        """
        Calls a subprocess to spawn new tests.

        The subprocess is redirected to dev/null (windows <any-dir>\\NUL), to prevent excessive
        output. In order to debug, this test you will likely need to modify this code.
        """
        cmds = ["mpiexec", "-n", "2", "python", "-m", "unittest"]
        cmds += ["armi.tests.test_operators.MpiOperatorTests"]
        with open(os.devnull, "w") as null:
            # check_call needed because call will just keep going in the event
            # of failures.
            subprocess.check_call(cmds, stdout=null, stderr=subprocess.STDOUT)


if armi.MPI_SIZE > 1:

    class MpiOperatorTests(unittest.TestCase):
        """Testing the MPI parallelization operation"""

        def setUp(self):
            self.cs = settings.Settings(fName=ARMI_RUN_PATH)
            settings.setMasterCs(self.cs)
            self.o = OperatorMPI(cs=self.cs)

        def test_masterException(self):
            self.o.removeAllInterfaces()
            failer = FailingInterface1(self.o.r, self.o.cs)
            self.o.addInterface(failer)
            if armi.MPI_RANK == 0:
                self.assertRaises(RuntimeError, self.o.operate)
            else:
                self.o.operate()

        def test_masterCritical(self):
            self.o.removeAllInterfaces()
            failer = FailingInterface2(self.o.r, self.o.cs)
            self.o.addInterface(failer)
            if armi.MPI_RANK == 0:
                self.assertRaises(Exception, self.o.operate)
            else:
                self.o.operate()

        def test_workerException(self):
            self.o.removeAllInterfaces()
            failer = FailingInterface3(self.o.r, self.o.cs)
            self.o.addInterface(failer)
            if armi.MPI_RANK != 0:
                self.assertRaises(RuntimeError, self.o.operate)
            else:
                self.o.operate()


if __name__ == "__main__":
    # args = ["mpiexec", "-n", "2", "python", "-m", "unittest"]
    # args += ["armi.tests.test_operators.OperatorTests"]
    # subprocess.call(args)
    pytest.main()
