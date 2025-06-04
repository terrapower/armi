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

"""Serial tests for the Context module."""

import unittest

from armi import context


class TestContextSerial(unittest.TestCase):
    """Serial tests for the Context module."""

    @unittest.skipIf(context.MPI_SIZE > 1, "Serial test only")
    def test_rank(self):
        self.assertEqual(context.MPI_RANK, 0)
        self.assertEqual(context.MPI_SIZE, 1)

    @unittest.skipIf(context.MPI_SIZE > 1, "Serial test only")
    def test_nonNoneData(self):
        self.assertGreater(len(context.APP_DATA), 0)
        self.assertGreater(len(context.DOC), 0)
        self.assertGreater(len(context.getFastPath()), 0)
        self.assertGreater(len(context.PROJECT_ROOT), 0)
        self.assertGreater(len(context.RES), 0)
        self.assertGreater(len(context.ROOT), 0)
        self.assertGreater(len(context.USER), 0)
