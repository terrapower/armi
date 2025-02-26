# Copyright 2023 TerraPower, LLC
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
"""Tests of the MPI portion of the Parameters class."""

import shutil
import unittest

from armi import context
from armi.reactor import composites, parameters

# determine if this is a parallel run, and MPI is installed
MPI_EXE = None
if shutil.which("mpiexec.exe") is not None:
    MPI_EXE = "mpiexec.exe"
elif shutil.which("mpiexec") is not None:
    MPI_EXE = "mpiexec"


class MockSyncPC(parameters.ParameterCollection):
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(default=0.0, location=parameters.ParamLocation.AVERAGE) as pb:
        pb.defParam("param1", "units", "p1 description", categories=["cat1"])
        pb.defParam("param2", "units", "p2 description", categories=["cat2"])
        pb.defParam("param3", "units", "p3 description", categories=["cat3"])


def makeComp(name):
    """Helper method for MPI sync tests: mock up a Composite with a minimal param collections."""
    c = composites.Composite(name)
    c.p = MockSyncPC()
    return c


class SynchronizationTests(unittest.TestCase):
    """Some tests that must be run with mpirun instead of the standard unittest system."""

    def setUp(self):
        self.r = makeComp("reactor")
        self.r.core = makeComp("core")
        self.r.add(self.r.core)
        for ai in range(context.MPI_SIZE * 3):
            a = makeComp("assembly{}".format(ai))
            self.r.core.add(a)
            for bi in range(3):
                a.add(makeComp("block{}-{}".format(ai, bi)))

        self.comps = [self.r.core] + self.r.core.getChildren(deep=True)

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_noConflicts(self):
        """Make sure sync works across processes.

        .. test:: Synchronize a reactor's state across processes.
            :id: T_ARMI_CMP_MPI0
            :tests: R_ARMI_CMP_MPI
        """
        _syncCount = self.r.syncMpiState()

        for ci, comp in enumerate(self.comps):
            if ci % context.MPI_SIZE == context.MPI_RANK:
                comp.p.param1 = (context.MPI_RANK + 1) * 30.0
            else:
                self.assertNotEqual((context.MPI_RANK + 1) * 30.0, comp.p.param1)

        syncCount = self.r.syncMpiState()
        self.assertEqual(len(self.comps), syncCount)

        for ci, comp in enumerate(self.comps):
            self.assertEqual((ci % context.MPI_SIZE + 1) * 30.0, comp.p.param1)

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_withConflicts(self):
        """Test conflicts arise correctly if we force a conflict.

        .. test:: Raise errors when there are conflicts across processes.
            :id: T_ARMI_CMP_MPI1
            :tests: R_ARMI_CMP_MPI
        """
        self.r.core.p.param1 = (context.MPI_RANK + 1) * 99.0
        with self.assertRaises(ValueError):
            self.r.syncMpiState()

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_withConflictsButSameValue(self):
        """Test that conflicts are ignored if the values are the same.

        .. test:: Don't raise errors when multiple processes make the same changes.
            :id: T_ARMI_CMP_MPI2
            :tests: R_ARMI_CMP_MPI
        """
        self.r.core.p.param1 = (context.MPI_SIZE + 1) * 99.0
        self.r.syncMpiState()
        self.assertEqual((context.MPI_SIZE + 1) * 99.0, self.r.core.p.param1)

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_conflictsMaintainWithStateRetainer(self):
        """Test that the state retainer fails correctly when it should."""
        with self.r.retainState(parameters.inCategory("cat2")):
            for _, comp in enumerate(self.comps):
                comp.p.param2 = 99 * context.MPI_RANK

        with self.assertRaises(ValueError):
            self.r.syncMpiState()
