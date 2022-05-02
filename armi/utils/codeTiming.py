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
Utilities related to profiling code.
"""

import time
import copy
import os


def timed(*args):
    """
    Decorate functions to measure how long they take.

    Examples
    --------
    ::

        @timed # your timer will be called the module+method name
        def mymethod(stuff):
            do stuff

        @timed('call my timer this instead')
        def mymethod2(stuff)
           do even more stuff

    """

    def time_decorator(func):
        time_decorator.__doc__ = func.__doc__
        time_decorator.__name__ = func.__name__

        def time_wrapper(*args, **kwargs):
            generated_name = "::".join(
                [
                    os.path.split(func.__code__.co_filename)[1],
                    str(func.__code__.co_firstlineno),
                    func.__code__.co_name,
                ]
            )

            MasterTimer.startTimer(label or generated_name)
            return_value = func(*args, **kwargs)
            MasterTimer.endTimer(label or generated_name)

            return return_value

        return time_wrapper

    if len(args) == 1 and callable(args[0]):
        label = None
        return time_decorator(args[0])
    elif len(args) == 1 and isinstance(args[0], str):
        label = args[0]
        return time_decorator
    else:
        raise ValueError(
            "The timed decorator has been misused. Input args were {}".format(args)
        )


def getMasterTimer():
    """Duplicate function to the MasterTimer.getMasterTimer method

    Provided for convenience and developer preference of which to use

    """
    return MasterTimer.getMasterTimer()


class MasterTimer:

    _instance = None

    def __init__(self):
        if MasterTimer._instance:
            raise RuntimeError(
                "{} is a pseudo singleton, do not attempt to make more than one.".format(
                    self.__class__.__name__
                )
            )
        MasterTimer._instance = self

        self.timers = {}

        self.start_time = time.time()
        self.end_time = None

    @staticmethod
    def getMasterTimer():
        if not MasterTimer._instance:
            MasterTimer()
        return MasterTimer._instance

    @staticmethod
    def getTimer(event_name):
        """Return a timer with no special action take

        ``with timer: ...`` friendly!

        """
        master = MasterTimer.getMasterTimer()

        if event_name in master.timers:
            timer = master.timers[event_name]
        else:
            timer = _Timer(event_name, False)
        return timer

    @staticmethod
    def startTimer(event_name):
        """Return a timer with a start call, or a newly made started timer

        ``with timer: ...`` unfriendly!

        """
        master = MasterTimer.getMasterTimer()

        if event_name in master.timers:
            timer = master.timers[event_name]
            timer.start()
        else:
            timer = _Timer(event_name, True)
        return timer

    @staticmethod
    def endTimer(event_name):
        """Return a timer with a stop call, or a newly made unstarted timer

        ``with timer: ...`` unfriendly!

        """
        master = MasterTimer.getMasterTimer()

        if event_name in master.timers:
            timer = master.timers[event_name]
            timer.stop()
        else:
            timer = _Timer(event_name, False)
        return timer

    @staticmethod
    def time():
        """System time offset by when this master timer was initialized"""
        master = MasterTimer.getMasterTimer()

        if master.end_time:
            return master.end_time - master.start_time
        else:
            return time.time() - master.start_time

    @staticmethod
    def startAll():
        """Starts all timers, won't work after a stopAll command"""
        master = MasterTimer.getMasterTimer()

        for timer in master.timers.values():
            timer.start()

    @staticmethod
    def stopAll():
        """Kills the timer run, can't easily be restarted"""
        master = MasterTimer.getMasterTimer()

        for timer in master.timers.values():
            timer.over_start = 0  # deal with what recursion may have caused
            timer.stop()

        _Timer._frozen = True  # pylint: disable=protected-access

        master.end_time = time.time()

    @staticmethod
    def getActiveTimers():
        master = MasterTimer.getMasterTimer()

        return [t for t in master.timers.values() if t.isActive]

    @staticmethod
    def report(inclusion_cutoff=0.1, total_time=False):
        r"""
        Write a string report of the timers

        Parameters
        ----------
        inclusion_cutoff : float, optional
            Will not show results that have less than this fraction of the total time.
        total_time : bool, optional
            Use either the ratio of total time or time since last report for consideration against the cutoff

        See Also
        --------
        armi.utils.codeTiming._Timer.__str__ : prints out the results for each individual line item
        """

        master = MasterTimer.getMasterTimer()

        table = [
            "{:60s} {:^20} {:^20} {:^20} {:^8} {}\t".format(
                "TIMER REPORTS",
                "SINCE LAST (s)",
                "CUMULATIVE (s)",
                "AVERAGE (s)",
                "PAUSES",
                "ACTIVE",
            )
        ]

        for timer in sorted(master.timers.values(), key=lambda x: x.time):
            if total_time:
                time_ratio = timer.time / master.time()
            else:
                time_ratio = timer.timeSinceReport / master.time()
            if time_ratio < inclusion_cutoff:
                continue
            table.append(str(timer))

        return "\n".join(table)

    @staticmethod
    def timeline(base_file_name, inclusion_cutoff=0.1, total_time=False):
        r"""Produces a timeline graphic of the timers

        Parameters
        ----------
        base_file_name : str
            whatever the leading file path should be
            this method generates the same file extension for every image to add to the base
        inclusion_cutoff : float, optional
            Will not show results that have less than this fraction of the total time.
        total_time : bool, optional
            Use either the ratio of total time or time since last report for consideration against the cutoff

        """
        import matplotlib.pyplot as plt
        import numpy as np

        # initial set up
        master = MasterTimer.getMasterTimer()
        cur_time = master.time()

        color_map = plt.cm.jet

        y_values = []  # list of heights
        y_level = 0  # height of the timelines
        names = []
        x_starts = []
        x_stops = []
        colors = []

        # plot content gather
        for timer in sorted(master.timers.values(), key=lambda x: x.name):
            if total_time:
                time_ratio = timer.time / master.time()
            else:
                time_ratio = timer.timeSinceReport / master.time()
            if time_ratio < inclusion_cutoff:
                continue

            y_level += 1
            names.append(timer.name)
            for time_pair in timer.times:
                y_values.append(y_level)
                x_starts.append(time_pair[0])
                x_stops.append(time_pair[1])
                colors.append(color_map(time_ratio))

        # plot set up
        # might not be necessary to scale the width with the height like this
        plt.figure(
            figsize=(3 + len(master.timers.values()), (3 + len(master.timers.values())))
        )
        plt.axis([0.0, cur_time, 0.0, y_level + 1])
        plt.xlabel("Time (s)")
        plt.yticks(
            np.arange(y_level + 1), [""] + names
        )  # offset needed for some reason
        _loc, labels = plt.yticks()
        for tick in labels:
            tick.set_fontsize(40)

        plt.tight_layout()

        # plot content draw
        plt.hlines(y_values, x_starts, x_stops, colors)

        def flatMerge(
            l1, l2=None
        ):  # duplicate a list flatly or merge them flatly (no tuples compared to zip)
            return [item for sublist in zip(l1, l2 or l1) for item in sublist]

        ymin = [y - 0.3 for y in y_values]
        ymax = [y + 0.3 for y in y_values]
        plt.vlines(
            flatMerge(x_starts, x_stops),
            flatMerge(ymin),
            flatMerge(ymax),
            flatMerge(colors),
        )

        # done
        filename = base_file_name + ".code-timeline.png"
        plt.savefig(filename)
        return os.path.join(os.getcwd(), filename)


class _Timer:
    r"""Code timer to call at various points to measure performance

    see MasterTimer.getTimer() for construction

    """

    _frozen = False  # if the master timer stops, all timers must freeze, with no thaw (how would that make sense in a run?)

    def __init__(self, name, start):
        self.name = name
        MasterTimer.getMasterTimer().timers[self.name] = self

        self._active = False
        self._times = []  # [(start, end), (start, end)...]
        self.over_start = 0  # necessary for recursion tracking
        self.reportedTotal = (
            0.0  # time elapsed since last asked to report time in __str__
        )

        if start:
            self.start()

    def __repr__(self):
        return "<{} name:'{}' pauses:{} active:{} time:{}>".format(
            self.__class__.__name__, self.name, self.pauses, self.isActive, self.time
        )

    def __str__(self):
        str_ = "{:60s} {:>20.2f} {:>20.2f} {:>20.2f} {:^8} {}".format(
            self.name[:60],
            self.timeSinceReport,
            self.time,
            self.time / (self.pauses + 1),
            self.pauses,
            self.isActive,
        )
        self.reportedTotal = (
            self.time
        )  # needs to come after str generation because it resets the timeSinceReport
        return str_

    def __enter__(self):
        self.start()

    def __exit__(self, *args, **kwargs):
        self.stop()

    @property
    def isActive(self):
        return self._active

    @property
    def pauses(
        self,
    ):  # if this number seems high remember .start() twice in a row adds a pause
        return len(self._times) - 1 if self._times else 0

    @property
    def time(self):
        """Total time value"""
        return sum([t[1] - t[0] for t in self.times])

    @property
    def timeSinceReport(self):
        """The elapsed time since this timer was asked to report itself"""
        return self.time - self.reportedTotal

    @property
    def times(self):
        """List of time start and stop pairs, if active the current time is used as the last stop"""
        if self.isActive:
            times = copy.deepcopy(self._times)
            times[-1] = (self._times[-1][0], MasterTimer.time())
            return times
        else:
            return self._times

    def _open_time_pair(self, cur_time):
        self._times.append((cur_time, None))

    def _close_time_pair(self, cur_time):
        self._times[-1] = (self._times[-1][0], cur_time)

    def start(self):
        cur_time = MasterTimer.time()

        if self._frozen:
            return

        if self.isActive:
            self.over_start += (
                1  # call was made on an active timer, we're now over-started
            )
            self._close_time_pair(cur_time)
        self._active = True
        self._open_time_pair(cur_time)

        return cur_time

    def stop(self):
        cur_time = MasterTimer.time()

        if self._frozen:
            return

        if self.over_start:  # can't end the timer as it's over-started
            self.over_start -= 1
        elif self.isActive:
            self._active = False
            self._close_time_pair(cur_time)

        return cur_time
