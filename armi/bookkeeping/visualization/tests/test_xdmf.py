# Copyright 2020 TerraPower, LLC
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

import unittest

from armi.bookkeeping.visualization import xdmf


class TestXdmf(unittest.TestCase):
    """
    Test XDMF-specific functionality.

    This is for testing XDMF functions that can reasonably be tested in a vacuum. The
    main dump methods are hard to test without resorting to checking whole files, which
    isn't particularly useful. Those tests can be found in test_vis.
    """

    def test_dedupTimes(self):
        # no duplicates
        self.assertEqual(
            xdmf.XdmfDumper._dedupTimes([1.0 * t for t in range(10)]),
            [1.0 * t for t in range(10)],
        )

        # ends in duplicates
        self.assertEqual(
            xdmf.XdmfDumper._dedupTimes([0.0, 1.0, 2.0, 2.0, 3.0, 4.0, 4.0, 4.0]),
            [0.0, 1.0, 2.0, 2.000000002, 3.0, 4.0, 4.000000004, 4.000000008],
        )

        # ends in unique
        self.assertEqual(
            xdmf.XdmfDumper._dedupTimes([0.0, 1.0, 2.0, 2.0, 3.0, 4.0, 4.0, 4.0, 5.0]),
            [0.0, 1.0, 2.0, 2.000000002, 3.0, 4.0, 4.000000004, 4.000000008, 5.0],
        )

        # all duplicates
        self.assertEqual(
            xdmf.XdmfDumper._dedupTimes([0.0] * 5),
            [0.0, 1e-09, 2e-09, 3.0000000000000004e-09, 4e-09],
        )

        # single value
        self.assertEqual(
            xdmf.XdmfDumper._dedupTimes([1.0]),
            [1.0],
        )

        # empty list
        self.assertEqual(
            xdmf.XdmfDumper._dedupTimes([]),
            [],
        )

        with self.assertRaises(AssertionError):
            # input should be sorted
            xdmf.XdmfDumper._dedupTimes([float(t) for t in reversed(range(10))])
