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

    def test_methodDefinitions(self):
        """Test that the timer decorators do not interupt the code being decorated."""

        @codeTiming.timed
        def someMethod(boop):
            return boop

        @codeTiming.timed("I have this name")
        def someOtherMethod(boop):
            return boop

        x = someMethod("dingdong")
        y = someOtherMethod("bingbong")

        self.assertEqual(x, "dingdong")
        self.assertEqual(y, "bingbong")

    def test_countStartsStops(self):
        """Test the start and stop counting logic."""
        # test the start() and stop() methods, and their side effects
        master = codeTiming.MasterTimer.getMasterTimer()
        timer = master.startTimer("bananananana")
        t0 = timer.stop()
        self.assertEqual(timer.overStart, 0)

        t1 = timer.start()
        self.assertGreater(t1, t0)
        self.assertEqual(timer.overStart, 0)

        t2 = timer.start()
        self.assertGreater(t2, t1)
        self.assertEqual(timer.overStart, 1)

        t3 = timer.stop()
        self.assertGreater(t3, t2)
        self.assertEqual(timer.overStart, 0)

        t4 = timer.stop()
        self.assertGreater(t4, t3)
        self.assertEqual(timer.overStart, 0)

        t5 = timer.stop()
        self.assertGreater(t5, t4)
        self.assertEqual(timer.overStart, 0)

        t6 = timer.start()
        self.assertGreater(t6, t5)
        self.assertEqual(timer.overStart, 0)

        timer2 = master.endTimer("wazzlewazllewazzzle")
        t7 = timer2.start()
        self.assertGreater(t7, t6)
        self.assertEqual(timer2.overStart, 0)

        t8 = timer2.start()
        self.assertGreater(t8, t7)
        self.assertEqual(timer2.overStart, 1)

        # use the timers as context managers
        with timer2:
            with timer:
                pass

        # There should be one start/stop each, leaving the over start count the same
        self.assertEqual(timer.overStart, 0)
        self.assertEqual(timer2.overStart, 1)

    def test_propertyAccess(self):
        """Test property access is okay."""
        master = codeTiming.MasterTimer.getMasterTimer()
        timer = master.startTimer("sometimer")

        t0 = timer.time
        self.assertGreater(t0, 0)
        ts = timer.times
        self.assertEqual(len(ts), 1)
        self.assertEqual(len(ts[0]), 2)
        self.assertGreater(ts[0][0], 0)
        self.assertGreater(ts[0][1], 0)
        tName = timer.name
        self.assertEqual(tName, "sometimer")
        tActive = timer.isActive
        self.assertTrue(tActive)

    def test_master(self):
        master = codeTiming.MasterTimer.getMasterTimer()
        _ = master.time

        master.startAll()
        actives = master.getActiveTimers()
        self.assertEqual(list(master.timers.values()), actives)

        master.stopAll()
        actives = master.getActiveTimers()
        self.assertEqual([], actives)

        with self.assertRaises(RuntimeError):
            codeTiming.MasterTimer()

    def test_messyStartsAndStops(self):
        master = codeTiming.MasterTimer.getMasterTimer()

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
        self.assertEqual(timer.numIterations, 3)

    def test_report(self):
        master = codeTiming.MasterTimer.getMasterTimer()
        name = "test_report"
        timer = master.getTimer(name)
        timer.start()
        time.sleep(0.01)
        timer.stop()

        # basic validation of the reports
        table = codeTiming.MasterTimer.report(inclusionCutoff=0.01, totalTime=True)
        self.assertIn("  AVERAGE ", table)
        self.assertIn("  CUMULATIVE ", table)
        self.assertIn("  NUM ITERS", table)
        self.assertIn("TIMER REPORTS  ", table)
        self.assertIn(name, table)

        lines = table.strip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(len(lines[1].strip().split()), 4)
