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

"""Unit tests for code timing."""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import time
import unittest

from armi.utils import codeTiming


class CodeTimingTest(unittest.TestCase):
    def setUp(self):
        codeTiming._Timer._frozen = False
        codeTiming.MasterTimer._instance = None

    def tearDown(self):
        codeTiming._Timer._frozen = False
        codeTiming.MasterTimer._instance = None

    def test_method_definitions(self):
        @codeTiming.timed
        def some_method(boop):
            return boop

        @codeTiming.timed("I have this name")
        def some_other_method(boop):
            return boop

        x = some_method("dingdong")
        y = some_other_method("bingbong")

        self.assertEqual(x, "dingdong")
        self.assertEqual(y, "bingbong")

    def test_alternate_usages(self):
        master = codeTiming.getMasterTimer()
        timer = master.startTimer("bananananana")
        timer.stop()
        timer.start()
        timer.start()
        timer.stop()
        timer.stop()
        timer.stop()
        timer.start()

        timer2 = master.endTimer("wazzlewazllewazzzle")
        timer2.start()
        timer2.start()

        with timer2:
            with timer:
                pass

    def test_property_access(self):
        # test property access is okay
        master = codeTiming.getMasterTimer()
        timer = master.startTimer("sometimer")

        _ = timer.times
        _ = timer.time
        _ = timer.name
        _ = timer.isActive

    def test_master(self):
        master = codeTiming.getMasterTimer()
        _ = master.time

        master.startAll()
        actives = master.getActiveTimers()
        self.assertEqual(list(master.timers.values()), actives)

        master.stopAll()
        actives = master.getActiveTimers()
        self.assertEqual([], actives)

        with self.assertRaises(RuntimeError):
            codeTiming.MasterTimer()

    def test_messy_starts_and_stops(self):
        master = codeTiming.getMasterTimer()

        name = "sometimerthatihaventmadeyet"
        larger_time_start = master.time()
        time.sleep(0.01)
        timer = master.getTimer(name)
        time.sleep(0.01)
        lesser_time_start = master.time()

        timer.start()  # 1st time pair
        timer.start()  # 2nd time pair
        timer.start()  # 3rd time pair
        timer.stop()
        self.assertIn(name, str(timer))
        self.assertTrue(timer.isActive)

        timer.stop()
        timer.stop()
        self.assertFalse(timer.isActive)

        timer.stop()
        timer.stop()
        timer.start()  # 4th time pair
        self.assertTrue(timer.isActive)

        lesser_time_end = master.time()
        time.sleep(0.01)
        timer.stop()
        self.assertIn(name, str(timer))
        self.assertEqual(len(timer.times), 4)
        time.sleep(0.01)
        larger_time_end = master.time()

        # even with all the starts and stops the total time needs to be between these two values.
        self.assertGreater(timer.time, lesser_time_end - lesser_time_start)
        self.assertLess(timer.time, larger_time_end - larger_time_start)
        self.assertEqual(timer.pauses, 3)

        # test report
        table = codeTiming.MasterTimer.report(inclusion_cutoff=0.01, total_time=True)
        self.assertIn("TIMER REPORTS", table)
        self.assertIn(name, table)
        self.assertIn("CUMULATIVE", table)
        self.assertIn("ACTIVE", table)


if __name__ == "__main__":
    unittest.main()
