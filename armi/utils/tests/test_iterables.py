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

"""


unittests for iterables.py
"""
import time
import unittest

from armi.utils import iterables


class TestIterables(unittest.TestCase):
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

    testData = {"turtle": [float(vv) for vv in range(-2000, 2000)]}

    def test_packingAndUnpackingBinaryStrings(self):
        start = time.perf_counter()
        packed = iterables.packBinaryStrings(self.testData)
        unpacked = iterables.unpackBinaryStrings(packed["turtle"][0])
        timeDelta = time.perf_counter() - start
        self.assertEqual(self.testData["turtle"], unpacked)
        return timeDelta

    def test_packingAndUnpackingHexStrings(self):
        start = time.perf_counter()
        packed = iterables.packHexStrings(self.testData)
        unpacked = iterables.unpackHexStrings(packed["turtle"][0])
        timeDelta = time.perf_counter() - start
        self.assertEqual(self.testData["turtle"], unpacked)
        return timeDelta


if __name__ == "__main__":
    unittest.main()
