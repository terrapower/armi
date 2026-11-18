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

"""MPI-mocked tests for operator MPI. For actual MPI unit tests, refer to armi/tests/test_mpiFeatures.py."""

from contextlib import contextmanager
from unittest import mock
import unittest

from armi.operators import operatorMPI


class TestOperatorMpiLogConcat(unittest.TestCase):
    """Class that tests the `_concatMpiLogs()` functionality in OperatorMPI.operate()."""

    @contextmanager
    def patchedMpiContextandClose(self, rank, size, comm, events):
        """Patch MPI context and runLog.close()"""
        with (
            mock.patch.object(operatorMPI.context, "MPI_RANK", rank),
            mock.patch.object(operatorMPI.context, "MPI_SIZE", size),
            mock.patch.object(operatorMPI.context, "MPI_COMM", comm),
            mock.patch.object(operatorMPI.runLog, "close", side_effect=lambda: events.append("close")),
        ):
            yield

    def test_operatorLogConcatPrimary(self):
        """Base rank closes logs before concatenating MPI logs."""
        events = []
        comm = mock.Mock()
        comm.barrier.side_effect = lambda: events.append("barrier")

        with (
            self.patchedMpiContextandClose(rank=0, size=2, comm=comm, events=events),
            mock.patch.object(
                operatorMPI.runLog, "concatenateLogs", side_effect=lambda: events.append("concatenate")
            ) as concatenateLogs,
        ):
            operatorMPI._concatMpiLogs()

        self.assertEqual(events, ["close", "barrier", "concatenate", "barrier"])
        concatenateLogs.assert_called_once()

    def test_operatorLogConcatWorker(self):
        """Worker ranks close logs but do not concatenate them."""
        events = []
        comm = mock.Mock()
        comm.barrier.side_effect = lambda: events.append("barrier")
        with (
            self.patchedMpiContextandClose(rank=1, size=2, comm=comm, events=events),
            mock.patch.object(
                operatorMPI.runLog, "concatenateLogs", side_effect=lambda: events.append("concatenate")
            ) as concatenateLogs,
        ):
            operatorMPI._concatMpiLogs()

        self.assertEqual(events, ["close", "barrier", "barrier"])
        concatenateLogs.assert_not_called()

    def test_operatorLogConcatPrimaryFinally(self):
        """Ensure the last MPI barrier in the finally statement is reached for base rank."""
        events = []
        comm = mock.Mock()
        comm.barrier.side_effect = lambda: events.append("barrier")
        concatErr = OSError("Fake Error")
        with (
            self.patchedMpiContextandClose(rank=0, size=2, comm=comm, events=events),
            mock.patch.object(operatorMPI.runLog, "concatenateLogs", side_effect=concatErr) as concatenateLogs,
        ):
            with self.assertRaisesRegex(RuntimeError, "Failed to concatenate MPI logs") as errorContext:
                operatorMPI._concatMpiLogs()

        self.assertEqual(events, ["close", "barrier", "barrier"])
        concatenateLogs.assert_called_once()
        self.assertIs(errorContext.exception.__cause__, concatErr)

    def test_operatorLogConcatWorkerFinally(self):
        """Ensure the last MPI barrier in the finally statement is reached for worker rank."""
        events = []
        comm = mock.Mock()
        comm.barrier.side_effect = lambda: events.append("barrier")
        concatErr = OSError("Fake Error")
        with (
            self.patchedMpiContextandClose(rank=1, size=2, comm=comm, events=events),
            mock.patch.object(operatorMPI.runLog, "concatenateLogs", side_effect=concatErr) as concatenateLogs,
        ):
            operatorMPI._concatMpiLogs()

        self.assertEqual(events, ["close", "barrier", "barrier"])
        concatenateLogs.assert_not_called()
