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
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access

import distutils.spawn
import os
import subprocess
import unittest

import armi
from armi import settings
from armi import nuclearDataIO
from armi import mpiActions
from armi.utils import iterables
from armi.operators import OperatorMPI
from armi.nucDirectory import nuclideBases
from armi.mpiActions import DistributeStateAction

from armi.tests import ARMI_RUN_PATH, ISOAA_PATH


class DistributeStateTests(unittest.TestCase):

    # @unittest.skipIf(distutils.spawn.find_executable('mpiexec.exe') is None, "mpiexec is not in path.")
    @unittest.skip("MPI tests are not working")
    def testDistribute(self):
        """
        Calls a subprocess to spawn new tests.

        The subprocess is redirected to dev/null (windows <any-dir>\\NUL), to prevent excessive
        output. In order to debug, this test you will likely need to modify this code.
        """
        args = ["mpiexec", "-n", "2", "python", "-m", "unittest"]
        args += ["armi.tests.test_mpiActions.MpiDistributeStateTests"]
        with open(os.devnull, "w") as null:
            # check_call needed because call will just keep going in the event
            # of failures.
            subprocess.check_call(args, stdout=null, stderr=subprocess.STDOUT)


# these two must be defined up here so that they can be pickled
class BcastAction1(mpiActions.MpiAction):
    def invokeHook(self):
        nItems = 50
        results = [None] * nItems
        for objIndex in range(nItems):
            if objIndex % armi.MPI_SIZE == armi.MPI_RANK:
                results[objIndex] = objIndex

        allResults = self.gather(results)

        if allResults:
            # this is confounding!!!!
            return [allResults[ai % armi.MPI_SIZE][ai] for ai in range(nItems)]


class BcastAction2(mpiActions.MpiAction):
    def invokeHook(self):
        results = []
        for num in self.mpiIter(range(50)):
            results.append(num)

        allResults = self.gather(results)
        if allResults:
            return self.mpiFlatten(allResults)


if armi.MPI_SIZE > 1:

    class MpiDistributeStateTests(unittest.TestCase):
        def setUp(self):
            self.cs = settings.Settings(fName=ARMI_RUN_PATH)
            settings.setMasterCs(self.cs)
            self.o = OperatorMPI(self.cs)
            self.action = DistributeStateAction()
            self.action.o = self.o
            self.action.r = self.o.r

        def test_distributeSettings(self):
            """Under normal circumstances, we would not test "private" methods;
            however, distributeState is quite complicated.
            """
            self.action._distributeSettings()
            if armi.MPI_RANK == 0:
                self.assertEqual(self.cs, self.action.o.cs)
            else:
                self.assertNotEqual(self.cs, self.action.o.cs)
                original = {ss.name: ss.value for ss in self.cs.settings.values()}
                current = {
                    ss.name: ss.value for ss in self.action.o.cs.settings.values()
                }
                # remove values that are *expected to be* different...
                for key in ["stationaryBlocks", "verbosity"]:
                    # self.assertNotEqual(original.get(key, None),
                    #                    current.get(key, None))
                    if key in original:
                        del original[key]
                    if key in current:
                        del current[key]
                # for key in set(original.keys() + current.keys()):
                #     self.assertEqual(original[key],
                #                      current[key],
                #                      'Values for key `{}\' are different {} != {}'
                #                      .format(key, original[key], current[key]))
                self.assertEqual(original, current)

        def test_distributeReactor(self):
            """Under normal circumstances, we would not test "private" methods;
            however, distributeState is quite complicated.
            """
            original_reactor = self.action.r
            self.action._distributeReactor(self.cs)
            self.assertIsNone(self.action.o.r.o)
            if armi.MPI_RANK == 0:
                self.assertEqual(original_reactor, self.action.r)
            else:
                self.assertNotEqual(original_reactor, self.action.r)
            self.assertIsNone(self.action.r.core.lib)

        def test_distributeReactorWithIsotxs(self):
            """Under normal circumstances, we would not test "private" methods;
            however, distributeState is quite complicated.
            """
            original_reactor = self.action.r
            self.assertIsNone(self.action.r.core.lib)
            if armi.MPI_RANK == 0:
                original_reactor.lib = nuclearDataIO.isotxs.readBinary(ISOAA_PATH)
            self.action._distributeReactor(self.cs)
            actual = {nb.label: nb.mc2id for nb in self.o.r.core.lib.nuclides}
            if armi.MPI_RANK == 0:
                self.assertEqual(original_reactor.lib, self.action.r.core.lib)
                armi.MPI_COMM.bcast(actual)  # soon to become expected
            else:
                self.assertIsNotNone(self.action.r.core.lib)
                for nuclide in self.action.r.core.lib.nuclides:
                    self.assertEqual(
                        nuclideBases.byLabel[nuclide._base.label], nuclide._base
                    )
                expected = armi.MPI_COMM.bcast(None)
                self.assertEqual(expected, actual)

        def test_distributeInterfaces(self):
            """Under normal circumstances, we would not test "private" methods;
            however, distributeState is quite complicated.
            """
            original_interfaces = self.o.interfaces
            self.action._distributeInterfaces()
            if armi.MPI_RANK == 0:
                self.assertEqual(original_interfaces, self.o.interfaces)
            else:
                self.assertEqual(original_interfaces, self.o.interfaces)

        def test_distributeState(self):
            original_reactor = self.o.r
            original_lib = self.o.r.core.lib
            original_interfaces = self.o.interfaces
            original_bolassems = self.o.r.blueprints.assemblies.values()
            self.action.invokeHook()

            if armi.MPI_RANK == 0:
                self.assertEqual(self.cs, self.o.cs)
                self.assertEqual(original_reactor, self.o.r)
                self.assertEqual(original_interfaces, self.o.interfaces)
                self.assertEqual(
                    original_bolassems, self.o.r.blueprints.assemblies.values()
                )
                self.assertEqual(original_lib, self.o.r.core.lib)
            else:
                self.assertNotEqual(self.cs, self.o.cs)
                self.assertNotEqual(original_reactor, self.o.r)
                self.assertNotEqual(
                    original_bolassems, self.o.r.blueprints.assemblies.values()
                )
                self.assertEqual(original_interfaces, self.o.interfaces)
                self.assertEqual(original_lib, self.o.r.core.lib)

        def test_compileResults(self):

            action1 = BcastAction1()
            armi.MPI_COMM.bcast(action1)
            results1 = action1.invoke(None, None, None)

            action2 = BcastAction2()
            armi.MPI_COMM.bcast(action2)
            results2 = action2.invoke(None, None, None)
            self.assertEqual(results1, results2)


@unittest.skipUnless(armi.MPI_RANK == 0, "test only on root node")
class MpiIterTests(unittest.TestCase):
    def setUp(self):
        """save MPI size on entry"""
        self._mpiSize = armi.MPI_SIZE
        self.action = mpiActions.MpiAction()

    def tearDown(self):
        """restore MPI rank and size on exit"""
        armi.MPI_SIZE = self._mpiSize
        armi.MPI_RANK = 0

    def test_mpiIter(self):
        allObjs = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        distObjs = [[0, 1, 2], [3, 4, 5], [6, 7], [8, 9], [10, 11]]
        # or distObjs = iterables.split(allObjs, 5)

        armi.MPI_SIZE = 5
        for rank in range(armi.MPI_SIZE):
            armi.MPI_RANK = rank
            myObjs = list(self.action.mpiIter(allObjs))
            self.assertEqual(myObjs, distObjs[rank])

    def _distributeObjects(self, allObjs, numProcs):
        armi.MPI_SIZE = numProcs
        objs = []
        for armi.MPI_RANK in range(armi.MPI_SIZE):
            objs.append(list(self.action.mpiIter(allObjs)))
        return objs

    def test_perfectBalancing(self):
        """Test load balancing when numProcs divides numObjects

        In this case, all processes should get the same number of objects.
        """
        numObjs, numProcs = 25, 5
        allObjs = list(range(numObjs))
        objs = self._distributeObjects(allObjs, numProcs)
        counts = [len(o) for o in objs]
        imbalance = max(counts) - min(counts)

        # ensure we haven't missed any objects
        self.assertEqual(iterables.flatten(objs), allObjs)

        # check imbalance
        self.assertEqual(imbalance, 0)

    def test_excessProcesses(self):
        """Test load balancing when numProcs exceeds numObjects

        In this case, some processes should receive a single object and the
        rest should receive no objects
        """
        numObjs, numProcs = 5, 25
        allObjs = list(range(numObjs))
        objs = self._distributeObjects(allObjs, numProcs)
        counts = [len(o) for o in objs]
        imbalance = max(counts) - min(counts)

        # ensure we haven't missed any objects
        self.assertEqual(iterables.flatten(objs), allObjs)

        # check imbalance
        self.assertLessEqual(imbalance, 1)

    def test_typicalBalancing(self):
        """Test load balancing for typical case (numProcs < numObjs)

        In this case, the total imbalance should be 1 (except for the perfectly
        balanced case).
        """
        numObjs, numProcs = 25, 6
        allObjs = list(range(numObjs))
        objs = self._distributeObjects(allObjs, numProcs)

        # typical case (more objects than processes)
        counts = [len(o) for o in objs]
        imbalance = max(counts) - min(counts)
        self.assertLessEqual(imbalance, 1)
        self.assertEqual(iterables.flatten(objs), allObjs)


if __name__ == "__main__":
    # args = ["mpiexec", "-n", "2", "python", "-m", "unittest"]
    # args += ["armi.tests.test_mpiActions.MpiDistributeStateTests.test_compileResults"]
    # subprocess.call(args)
    unittest.main()
