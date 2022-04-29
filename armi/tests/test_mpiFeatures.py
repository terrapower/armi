# Copyright 2021 TerraPower, LLC
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
Tests for featurest that need MPI, and thus require special testing.
These tests will be generally ignored by pytest if you are trying to run
them in an environment without MPI installed.

To run these tests from the commandline, install MPI, mpi4py, and do:

mpiexec -n 2 python -m pytest armi/tests/test_mpiFeatures.py
or
mpiexec.exe -n 2 python -m pytest armi/tests/test_mpiFeatures.py
"""
# pylint: disable=abstract-method,no-self-use,unused-argument
from distutils.spawn import find_executable
import os
import subprocess
import unittest

import pytest

from armi import context
from armi import mpiActions
from armi import settings
from armi.interfaces import Interface
from armi.mpiActions import DistributeStateAction
from armi.operators import OperatorMPI
from armi.reactor import blueprints
from armi.reactor import reactors
from armi.reactor.parameters import parameterDefinitions
from armi.reactor.tests import test_reactors
from armi.tests import ARMI_RUN_PATH, TEST_ROOT

# determine if this is a parallel run, and MPI is installed
MPI_EXE = None
if find_executable("mpiexec.exe") is not None:
    MPI_EXE = "mpiexec.exe"
elif find_executable("mpiexec") is not None:
    MPI_EXE = "mpiexec"


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
        context.MPI_COMM.bcast("fail", root=0)

    def workerOperate(self, cmd):
        if cmd == "fail":
            self.fail()
            return True
        return False


class MpiOperatorTests(unittest.TestCase):
    """Testing the MPI parallelization operator"""

    def setUp(self):
        self.old_op, self.r = test_reactors.loadTestReactor(TEST_ROOT)
        self.o = OperatorMPI(cs=self.old_op.cs)
        self.o.r = self.r

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_basicOperatorMPI(self):
        self.o.operate()

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_masterException(self):
        self.o.removeAllInterfaces()
        failer = FailingInterface1(self.o.r, self.o.cs)
        self.o.addInterface(failer)

        if context.MPI_RANK == 0:
            self.assertRaises(RuntimeError, self.o.operate)
        else:
            self.o.operate()

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_masterCritical(self):
        self.o.removeAllInterfaces()
        failer = FailingInterface2(self.o.r, self.o.cs)
        self.o.addInterface(failer)

        if context.MPI_RANK == 0:
            self.assertRaises(Exception, self.o.operate)
        else:
            self.o.operate()


# these two must be defined up here so that they can be pickled
class BcastAction1(mpiActions.MpiAction):
    def invokeHook(self):
        nItems = 50
        results = [None] * nItems
        for objIndex in range(nItems):
            if objIndex % context.MPI_SIZE == context.MPI_RANK:
                results[objIndex] = objIndex

        allResults = self.gather(results)

        if allResults:
            # this is confounding!!!!
            return [allResults[ai % context.MPI_SIZE][ai] for ai in range(nItems)]


class BcastAction2(mpiActions.MpiAction):
    def invokeHook(self):
        results = []
        for num in self.mpiIter(range(50)):
            results.append(num)

        allResults = self.gather(results)
        if allResults:
            return self.mpiFlatten(allResults)


class MpiDistributeStateTests(unittest.TestCase):
    def setUp(self):
        self.cs = settings.Settings(fName=ARMI_RUN_PATH)
        bp = blueprints.loadFromCs(self.cs)

        settings.setMasterCs(self.cs)
        self.o = OperatorMPI(self.cs)
        self.o.r = reactors.factory(self.cs, bp)
        self.action = DistributeStateAction()
        self.action.o = self.o
        self.action.r = self.o.r

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_distributeSettings(self):
        """Under normal circumstances, we would not test "private" methods;
        however, distributeState is quite complicated.
        """
        self.action._distributeSettings()
        if context.MPI_RANK == 0:
            self.assertEqual(self.cs, self.action.o.cs)
        else:
            self.assertNotEqual(self.cs, self.action.o.cs)
            original = {ss.name: ss.value for ss in self.cs.values()}
            current = {ss.name: ss.value for ss in self.action.o.cs.values()}
            # remove values that are *expected to be* different...
            # crossSectionControl is removed because unittest is being mean about
            # comparing dicts...
            for key in ["stationaryBlocks", "verbosity", "crossSectionControl"]:
                if key in original:
                    del original[key]
                if key in current:
                    del current[key]

            for key in original.keys():
                self.assertEqual(original[key], current[key])

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_distributeReactor(self):
        """Under normal circumstances, we would not test "private" methods;
        however, distributeState is quite complicated.
        """
        original_reactor = self.action.r
        self.action._distributeReactor(self.cs)
        if context.MPI_RANK == 0:
            self.assertEqual(original_reactor, self.action.r)
        else:
            self.assertNotEqual(original_reactor, self.action.r)
        self.assertIsNone(self.action.r.core.lib)

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_distributeInterfaces(self):
        """Under normal circumstances, we would not test "private" methods;
        however, distributeState is quite complicated.
        """
        original_interfaces = self.o.interfaces
        self.action._distributeInterfaces()
        if context.MPI_RANK == 0:
            self.assertEqual(original_interfaces, self.o.interfaces)
        else:
            self.assertEqual(original_interfaces, self.o.interfaces)

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_distributeState(self):
        original_reactor = self.o.r
        original_lib = self.o.r.core.lib
        original_interfaces = self.o.interfaces
        original_bolassems = self.o.r.blueprints.assemblies
        self.action.invokeHook()

        if context.MPI_RANK == 0:
            self.assertEqual(self.cs, self.o.cs)
            self.assertEqual(original_reactor, self.o.r)
            self.assertEqual(original_interfaces, self.o.interfaces)
            self.assertDictEqual(original_bolassems, self.o.r.blueprints.assemblies)
            self.assertEqual(original_lib, self.o.r.core.lib)
        else:
            self.assertNotEqual(self.cs, self.o.cs)
            self.assertNotEqual(original_reactor, self.o.r)
            self.assertNotEqual(original_bolassems, self.o.r.blueprints.assemblies)
            self.assertEqual(original_interfaces, self.o.interfaces)
            self.assertEqual(original_lib, self.o.r.core.lib)

        for pDef in parameterDefinitions.ALL_DEFINITIONS:
            self.assertFalse(
                pDef.assigned & parameterDefinitions.SINCE_LAST_DISTRIBUTE_STATE
            )

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_compileResults(self):
        action1 = BcastAction1()
        context.MPI_COMM.bcast(action1)
        results1 = action1.invoke(None, None, None)

        action2 = BcastAction2()
        context.MPI_COMM.bcast(action2)
        results2 = action2.invoke(None, None, None)
        self.assertEqual(results1, results2)


if __name__ == "__main__":
    # these tests must be run from the command line using MPI:
    #
    # mpiexec -n 2 python -m pytest armi/tests/test_mpiFeatures.py
    # or
    # mpiexec.exe -n 2 python -m pytest armi/tests/test_mpiFeatures.py
    pass
