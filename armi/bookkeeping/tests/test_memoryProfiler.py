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
Tests for memoryProfiler
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import unittest

from armi.bookkeeping import memoryProfiler
from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT


class MemoryProfilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.o, cls.r = test_reactors.loadTestReactor(TEST_ROOT, {"debugMem": True})

    def setUp(self):
        self.memPro = memoryProfiler.MemoryProfiler()
        self.o.addInterface(self.memPro)

    def tearDown(self):
        self.o.removeInterface(self.memPro)

    @unittest.skip("Takes way too long in unit test suites")
    def test_fullBreakdown(self):
        results = self.memPro._printFullMemoryBreakdown(
            startsWith="armi.physics", reportSize=False
        )
        _objects, count, _size = results["Dif3dInterface"]
        self.assertGreater(count, 0)


class KlassCounterTests(unittest.TestCase):
    def get_containers(self):
        container1 = [1, 2, 3, 4, 5, 6, 7, 2.0]
        container2 = ("a", "b", container1, None)
        container3 = {
            "yo": container2,
            "yo1": container1,
            ("t1", "t2"): True,
            "yeah": [],
            "nope": {},
        }

        return container3

    def test_expandContainer(self):
        container = self.get_containers()

        counter = memoryProfiler.KlassCounter(False)
        counter.countObjects(container)

        self.assertEqual(counter.count, 24)
        self.assertEqual(counter[list].count, 2)
        self.assertEqual(counter[dict].count, 2)
        self.assertEqual(counter[tuple].count, 2)
        self.assertEqual(counter[int].count, 7)

    def test_countHandlesRecursion(self):
        container = self.get_containers()
        container1 = container["yo1"]
        container1.append(container1)

        counter = memoryProfiler.KlassCounter(False)
        counter.countObjects(container)

        # despite it now being recursive ... we get the same counts
        self.assertEqual(counter.count, 24)
        self.assertEqual(counter[list].count, 2)
        self.assertEqual(counter[dict].count, 2)
        self.assertEqual(counter[tuple].count, 2)
        self.assertEqual(counter[int].count, 7)


if __name__ == "__main__":
    # import sys;sys.argv=['','MemoryProfilerSimpleTests.test_expandContainerRecursionLimit']
    unittest.main()
