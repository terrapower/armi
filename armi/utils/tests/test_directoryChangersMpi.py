# Copyright 2024 TerraPower, LLC
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
Test the MpiDirectoryChanger.

These tests will be generally ignored by pytest if you are trying to run
them in an environment without MPI installed.

To run these tests from the command line, install MPI and mpi4py, and do:

mpiexec -n 2 python -m pytest test_parallel.py
or
mpiexec.exe -n 2 python -m pytest test_parallel.py
"""

import os
import shutil
import unittest

from armi import context, mpiActions
from armi.utils.directoryChangersMpi import MpiDirectoryChanger

# determine if this is a parallel run, and MPI is installed
MPI_EXE = None
if shutil.which("mpiexec.exe") is not None:
    MPI_EXE = "mpiexec.exe"
elif shutil.which("mpiexec") is not None:
    MPI_EXE = "mpiexec"


class RevealYourDirectory(mpiActions.MpiAction):
    def invokeHook(self):
        # make a dir with name corresponding to the rank, that way we can confirm
        # that all ranks actually executed this code
        os.mkdir(str(context.MPI_RANK))
        return True


class TestMPI(unittest.TestCase):
    def setUp(self):
        self.targetDir = "mpiDir"
        if context.MPI_RANK == 0:
            os.mkdir(self.targetDir)

    def tearDown(self):
        context.MPI_COMM.barrier()
        if context.MPI_RANK == 0:
            shutil.rmtree(self.targetDir)

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_MpiDirectoryChanger(self):
        # make sure all workers start outside the targetDir
        self.assertNotIn(self.targetDir, os.getcwd())

        # put the workers in a loop, waiting for command from the main process
        if context.MPI_RANK != 0:
            while True:
                cmd = context.MPI_COMM.bcast(None, root=0)
                print(cmd)
                if cmd == "quit":
                    break
                cmd.invoke(None, None, None)

        # from main, send commands to the workers to move into the targetDir
        # and then create folders within there
        if context.MPI_RANK == 0:
            with MpiDirectoryChanger(self.targetDir):
                RevealYourDirectory.invokeAsMaster(None, None, None)

            # make the workers exit the waiting loop
            context.MPI_COMM.bcast("quit", root=0)

        context.MPI_COMM.barrier()
        if context.MPI_RANK == 0:
            # from main, confirm that subdirectories were created by all workers
            for i in range(context.MPI_SIZE):
                self.assertTrue(os.path.isdir(os.path.join(os.getcwd(), self.targetDir, str(i))))

        # make sure all workers have moved back out from the targetDir
        self.assertNotIn(self.targetDir, os.getcwd())

        context.MPI_COMM.barrier()
