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
"""Tests of the runLog tooling with MPI."""

import logging
import unittest
from logging import handlers

from armi import context, runLog


class TestRunLoggerMPI(unittest.TestCase):
    @unittest.skipIf(context.MPI_SIZE <= 1, "Parallel test only")
    def test_handlerType(self):
        if context.MPI_RANK == 0:
            self.rl = runLog.RunLogger("ARMI|things_and_stuff|0")
        else:
            self.rl = runLog.RunLogger("ARMI|things_and_stuff|1")

        # check the handler type
        if context.Platform == context.Platform.WINDOWS:
            if context.MPI_RANK == 0:
                self.assertTrue(isinstance(self.rl.handlers[0], logging.StreamHandler))
            else:
                self.assertTrue(isinstance(self.rl.handlers[0], logging.FileHandler))
        else:
            if context.MPI_RANK == 0:
                self.assertTrue(isinstance(self.rl.handlers[0], logging.StreamHandler))
            else:
                self.assertTrue(isinstance(self.rl.handlers[0], handlers.WatchedFileHandler))
