# Copyright 2026 TerraPower, LLC
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
"""Tests of the runLog tooling with MPI."""

import logging
import os
import shutil
import tempfile
import unittest
from logging import handlers
from unittest.mock import patch

from armi import context, runLog


class TestRunLoggerMPI(unittest.TestCase):
    @unittest.skipIf(context.MPI_SIZE <= 1, "Parallel test only")
    def test_handlerType(self):
        if context.MPI_RANK == 0:
            self.rl = runLog.RunLogger("ARMI|things_and_stuff|0")
        else:
            self.rl = runLog.RunLogger("ARMI|things_and_stuff|1")

        # check the handler type
        if context.MPI_RANK == 0:
            self.assertEqual(type(self.rl.handlers[0]), logging.StreamHandler)
        elif context.PLATFORM == context.Platform.WINDOWS:
            self.assertEqual(type(self.rl.handlers[0]), logging.FileHandler)
        else:
            self.assertEqual(type(self.rl.handlers[0]), handlers.WatchedFileHandler)


class TestRunLogMpiLogConcat(unittest.TestCase):
    @unittest.skipIf(context.MPI_SIZE <= 1, "Parallel test only")
    def test_mpiLogConcat(self):
        """Checks that the concatenation of MPI log files performs as expected.

        There are three try/excepts, which is more than one might expect in here. This is necessary so that the test
        doesn't hang at any stage if that stage happens to fail for some reason. The first two need to call an
        ``allgather`` to check that no errors happen on any rank before the subsequent step. The first one catches any
        logger-related "setup" failures and the second one catches any concatenation-related failures. The third try/
        except runs on rank 0 but then broadcasts any failures to the worker ranks so the test failures are aligned.
        """
        rank = context.MPI_RANK
        comm = context.MPI_COMM

        # Couldn't figure out how to get this MPI test to play nice with TemporaryDirectoryChanger, so we will use
        # tempfile instead and broadcast it
        tmpDir = comm.bcast(tempfile.mkdtemp(prefix="concat-test-", dir=os.getcwd()) if rank == 0 else None, root=0)
        caseTitle = comm.bcast("concat-test" if rank == 0 else None, root=0)
        logDir = os.path.join(tmpDir, "logs")
        try:
            with (
                patch.dict(os.environ, {"ARMI_TEMP_ROOT_PATH": tmpDir}),
                patch.object(runLog.RunLogger, "LOG_DIR", logDir),
            ):
                # "Setup" try/except to tee up the runLog
                setupErr = None
                try:
                    runLog.createLogDir(logDir)
                    runLog.LOG.startLog(caseTitle)
                    runLog.setVerbosity("info")
                    runLog.info(f"Hi hello from rank {rank}")
                except Exception as error:
                    setupErr = f"rank {rank}: {type(error).__name__}: {error}"
                setupErrs = [error for error in comm.allgather(setupErr) if error is not None]
                self.assertFalse(setupErrs, msg=setupErr)

                # Try/except to perform actual log concatenation
                concatErr = None
                try:
                    runLog.closeAndConcatenateMpiLogs()
                except Exception as error:
                    concatErr = f"rank {rank}: {type(error).__name__}: {error}"
                concatErrs = [error for error in comm.allgather(concatErr) if error is not None]
                self.assertFalse(concatErrs, msg=concatErr)

                # Last try/except to read in the concatenated logs on rank 0 only
                testErr = None
                if rank == 0:
                    try:
                        with open(os.path.join(logDir, f"{caseTitle}-mpi.log")) as l:
                            log = l.read()
                        # Rank 1 log should be in the concatenated file, and rank 0 should not be
                        self.assertIn("Hi hello from rank 1", log)
                        self.assertNotIn("Hi hello from rank 0", log)
                    except Exception as error:
                        testErr = f"{type(error).__name__}: {error}"
                # Ensure every test process reports rank 0's error.
                testErr = comm.bcast(testErr, root=0)
                self.assertIsNone(testErr, msg=testErr)
        finally:
            comm.barrier()
            if rank == 0:
                shutil.rmtree(tmpDir)
            comm.barrier()
