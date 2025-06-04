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

"""Unittests for iterables.py."""

import unittest

import numpy as np

from armi.utils import iterables

# CONSTANTS
_TEST_DATA = {"turtle": [float(vv) for vv in range(-2000, 2000)]}


class TestIterables(unittest.TestCase):
    """Testing our custom Iterables."""

    def test_flatten(self):
        self.assertEqual(
            iterables.flatten([[1, 2, 3], [4, 5, 6], [7, 8], [9, 10]]),
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        )
        self.assertEqual(
            iterables.flatten([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10]]),
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        )

    def test_chunk(self):
        self.assertEqual(
            list(iterables.chunk([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 4)),
            [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10]],
        )

    def test_split(self):
        data = list(range(50))
        chu = iterables.split(data, 10)
        self.assertEqual(len(chu), 10)
        unchu = iterables.flatten(chu)
        self.assertEqual(data, unchu)

        chu = iterables.split(data, 1)
        self.assertEqual(len(chu), 1)
        unchu = iterables.flatten(chu)
        self.assertEqual(data, unchu)

        chu = iterables.split(data, 60, padWith=[None])
        self.assertEqual(len(chu), 60)
        unchu = iterables.flatten(chu)
        self.assertEqual(len(unchu), 60)

        chu = iterables.split(data, 60, padWith=[None])
        self.assertEqual(len(chu), 60)

        data = [0]
        chu = iterables.split(data, 1)
        unchu = iterables.flatten(chu)
        self.assertEqual(unchu, data)

    def test_packingAndUnpackingBinaryStrings(self):
        packed = iterables.packBinaryStrings(_TEST_DATA)
        unpacked = iterables.unpackBinaryStrings(packed["turtle"][0])
        self.assertEqual(_TEST_DATA["turtle"], unpacked)

    def test_packingAndUnpackingHexStrings(self):
        packed = iterables.packHexStrings(_TEST_DATA)
        unpacked = iterables.unpackHexStrings(packed["turtle"][0])
        self.assertEqual(_TEST_DATA["turtle"], unpacked)

    def test_sequenceInit(self):
        # init an empty sequence
        s = iterables.Sequence()
        for item in s:
            self.assertTrue(False, "This shouldn't happen.")

        # init a sequence with another sequence
        example = [1, 2, 3]
        s2 = iterables.Sequence(example)
        s3 = iterables.Sequence(s2)

        i = 0
        for item in s3:
            i += 1

        self.assertEqual(i, len(example))

    def test_sequence(self):
        # sequentially using methods in the usual way
        s = iterables.Sequence(range(1000000))
        s.drop(lambda i: i % 2 == 0)
        s.select(lambda i: i < 20)
        s.transform(lambda i: i * 10)
        result = tuple(s)
        self.assertEqual(result, (10, 30, 50, 70, 90, 110, 130, 150, 170, 190))

        # stringing together the methods in a more modern Python way
        s = iterables.Sequence(range(1000000))
        result = tuple(s.drop(lambda i: i % 2 == 0).select(lambda i: i < 20).transform(lambda i: i * 10))
        self.assertEqual(result, (10, 30, 50, 70, 90, 110, 130, 150, 170, 190))

        # call tuple() after a couple methods
        s = iterables.Sequence(range(1000000))
        s.drop(lambda i: i % 2 == 0)
        s.select(lambda i: i < 20)
        result = tuple(s)
        self.assertEqual(result, (1, 3, 5, 7, 9, 11, 13, 15, 17, 19))

        # you can't just call tuple() a second time, there is no data left
        s.transform(lambda i: i * 10)
        result = tuple(s)
        self.assertEqual(result, ())

    def test_copySequence(self):
        s = iterables.Sequence(range(4, 8))
        sCopy = s.copy()

        vals = [item for item in sCopy]
        self.assertEqual(vals[0], 4)
        self.assertEqual(vals[-1], 7)
        self.assertEqual(len(vals), 4)

    def test_extendSequence(self):
        s = iterables.Sequence(range(3))
        ex = range(3, 8)
        s.extend(ex)

        vals = [item for item in s]
        self.assertEqual(vals[0], 0)
        self.assertEqual(vals[-1], 7)
        self.assertEqual(len(vals), 8)

    def test_appendSequence(self):
        s = iterables.Sequence(range(3))
        s.extend([999])

        vals = [item for item in s]
        self.assertEqual(vals[0], 0)
        self.assertEqual(vals[-1], 999)
        self.assertEqual(len(vals), 4)

    def test_addingSequences(self):
        s1 = iterables.Sequence(range(3))
        s2 = iterables.Sequence(range(3, 6))

        s3 = s1 + s2

        vals = [item for item in s3]
        self.assertEqual(vals[0], 0)
        self.assertEqual(vals[-1], 5)
        self.assertEqual(len(vals), 6)

        s1 += s2

        vals = [item for item in s1]
        self.assertEqual(vals[0], 0)
        self.assertEqual(vals[-1], 5)
        self.assertEqual(len(vals), 6)

    def test_listPivot(self):
        data = list(range(10))
        loc = 4
        actual = iterables.pivot(data, loc)
        self.assertEqual(actual, data[loc:] + data[:loc])

    def test_arrayPivot(self):
        data = np.arange(10)
        loc = -7
        actual = iterables.pivot(data, loc)
        expected = np.array(iterables.pivot(data.tolist(), loc))
        self.assertTrue((actual == expected).all(), msg=f"{actual=} != {expected=}")
        # Catch a silent failure case where pivot doesn't change the iterable
        self.assertTrue(
            (actual != data).all(),
            msg=f"Pre-pivot {data=} should not equal post-pivot {actual=}",
        )
