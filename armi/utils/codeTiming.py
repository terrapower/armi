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
"""Utilities related to profiling code."""
import copy
import functools
import os
import time


def timed(*args):
    """
    Decorate functions to measure how long they take.

    Examples
    --------
    Here are some examples of using this method::

        @timed # your timer will be called the module+method name
        def mymethod(stuff):
            do stuff

        @timed('call my timer this instead')
        def mymethod2(stuff)
           do even more stuff
    """

    def time_decorator(func):
        @functools.wraps(func)
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
            f"The timed decorator has been misused. Input args were {args}"
        )


class MasterTimer:
    """A code timing interface, this class is designed to be a singleton."""

    _instance = None

    def __init__(self):
        if MasterTimer._instance is not None:
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
        """Primary method that users need get access to the MasterTimer singleton."""
        if MasterTimer._instance is None:
            MasterTimer()

        return MasterTimer._instance

    @staticmethod
    def getTimer(eventName):
        """Return a timer with no special action take.

        ``with timer: ...`` friendly!
        """
        master = MasterTimer.getMasterTimer()

        if eventName in master.timers:
            timer = master.timers[eventName]
        else:
            timer = _Timer(eventName, False)
            master.timers[eventName] = timer
        return timer

    @staticmethod
    def startTimer(eventName):
        """Return a timer with a start call, or a newly made started timer.

        ``with timer: ...`` unfriendly!
        """
        master = MasterTimer.getMasterTimer()

        if eventName in master.timers:
            timer = master.timers[eventName]
            timer.start()
        else:
            timer = _Timer(eventName, True)
            master.timers[eventName] = timer
        return timer

    @staticmethod
    def endTimer(eventName):
        """Return a timer with a stop call, or a newly made unstarted timer.

        ``with timer: ...`` unfriendly!
        """
        master = MasterTimer.getMasterTimer()

        if eventName in master.timers:
            timer = master.timers[eventName]
            timer.stop()
        else:
            timer = _Timer(eventName, False)
            master.timers[eventName] = timer
        return timer

    @staticmethod
    def time():
        """System time offset by when this master timer was initialized."""
        master = MasterTimer.getMasterTimer()

        if master.end_time:
            return master.end_time - master.start_time
        else:
            return time.time() - master.start_time

    @staticmethod
    def startAll():
        """Starts all timers, won't work after a stopAll command."""
        master = MasterTimer.getMasterTimer()

        for timer in master.timers.values():
            timer.start()

    @staticmethod
    def stopAll():
        """Kills the timer run, can't easily be restarted."""
        master = MasterTimer.getMasterTimer()

        for timer in master.timers.values():
            timer.overStart = 0  # deal with what recursion may have caused
            timer.stop()

        _Timer._frozen = True

        master.end_time = time.time()

    @staticmethod
    def getActiveTimers():
        """Get all the timers for processes that are still active."""
        master = MasterTimer.getMasterTimer()

        return [t for t in master.timers.values() if t.isActive]

    def __str__(self):
        t = self.time()
        return "{:55s} {:>14.2f} {:>14.2f} {:11}".format("TOTAL TIME", t, t, 1)

    @staticmethod
    def report(inclusionCutoff=0.1, totalTime=False):
        """
        Write a string report of the timers.

        This report prints a table that looks something like this:

        TIMER REPORTS                                           CUMULATIVE (s)    AVERAGE (s)   NUM ITERS
        thing1                                                            0.01           0.01           1
        thing2                                                            0.01           0.01           1
        TOTAL TIME                                                        0.02           0.02           1

        Parameters
        ----------
        inclusionCutoff : float, optional
            Will not show results that have less than this fraction of the total time.
        totalTime : bool, optional
            Use the ratio of total time or time since last report to compare against the cutoff.

        See Also
        --------
        armi.utils.codeTiming._Timer.__str__ : prints out the results for each individual line item

        Returns
        -------
        str : Plain-text table report on the timers.
        """
        master = MasterTimer.getMasterTimer()

        table = [
            "{:55s} {:^15} {:^15} {:9}".format(
                "TIMER REPORTS",
                "CUMULATIVE (s)",
                "AVERAGE (s)",
                "NUM ITERS".rjust(9, " "),
            )
        ]

        for timer in sorted(master.timers.values(), key=lambda x: x.time):
            if totalTime:
                timeRatio = timer.time / master.time()
            else:
                timeRatio = timer.timeSinceReport / master.time()

            if timeRatio < inclusionCutoff:
                continue
            table.append(str(timer))

        # add the total time as the last row
        table.append(str(master))
        return "\n".join(table)

    @staticmethod
    def timeline(baseFileName, inclusionCutoff=0.1, totalTime=False):
        """Produces a timeline graphic of the timers.

        Parameters
        ----------
        baseFileName : str
            Whatever the leading file path should be.
            This method generates the same file extension for every image to add to the base.
        inclusionCutoff : float, optional
            Will not show results that have less than this fraction of the total time.
        totalTime : bool, optional
            Use the ratio of total time or time since last report to compare against the cutoff.

        Returns
        -------
        str : Path to the saved plot file.
        """
        import matplotlib.pyplot as plt
        import numpy as np

        # initial set up
        master = MasterTimer.getMasterTimer()
        curTime = master.time()

        color_map = plt.cm.jet

        colors = []
        names = []
        xStarts = []
        xStops = []
        yLevel = 0  # height of the timelines
        yValues = []  # list of heights

        # plot content gather
        for timer in sorted(master.timers.values(), key=lambda x: x.name):
            if totalTime:
                timeRatio = timer.time / master.time()
            else:
                timeRatio = timer.timeSinceReport / master.time()
            if timeRatio < inclusionCutoff:
                continue

            yLevel += 1
            names.append(timer.name)
            for timePair in timer.times:
                colors.append(color_map(timeRatio))
                xStarts.append(timePair[0])
                xStops.append(timePair[1])
                yValues.append(yLevel)

        # plot set up: might not be necessary to scale the width with the height like this
        plt.figure(
            figsize=(3 + len(master.timers.values()), (3 + len(master.timers.values())))
        )
        plt.axis([0.0, curTime, 0.0, yLevel + 1])
        plt.xlabel("Time (s)")
        plt.yticks(np.arange(yLevel + 1), [""] + names)
        _loc, labels = plt.yticks()
        for tick in labels:
            tick.set_fontsize(40)

        plt.tight_layout()

        # plot content draw
        plt.hlines(yValues, xStarts, xStops, colors)

        def flatMerge(l1, l2=None):
            # duplicate a list flatly or merge them flatly (no tuples compared to zip)
            return [item for sublist in zip(l1, l2 or l1) for item in sublist]

        ymin = [y - 0.3 for y in yValues]
        ymax = [y + 0.3 for y in yValues]
        plt.vlines(
            flatMerge(xStarts, xStops),
            flatMerge(ymin),
            flatMerge(ymax),
            flatMerge(colors),
        )

        # save and close
        filename = f"{baseFileName}.code-timeline.png"
        plt.savefig(filename)
        plt.close()
        return os.path.join(os.getcwd(), filename)


class _Timer:
    """Code timer to call at various points to measure performance.

    See Also
    --------
    MasterTimer.getTimer() for construction
    """

    # If the master timer stops, all timers must freeze with no thaw.
    _frozen = False

    def __init__(self, name, start):
        self.name = name
        self._active = False
        self._times = []  # [(start, end), (start, end)...]
        self.overStart = 0  # necessary for recursion tracking
        self.reportedTotal = (
            0.0  # time elapsed since last asked to report time in __str__
        )

        if start:
            self.start()

    def __repr__(self):
        return "<{} name:'{}' num iterations:{} time:{}>".format(
            self.__class__.__name__, self.name, self.numIterations, self.time
        )

    def __str__(self):
        s = "{:55s} {:>14.2f} {:>14.2f} {:11}".format(
            self.name[:55],
            self.time,
            self.time / (self.numIterations + 1),
            self.numIterations + 1,
        )
        # needs to come after str generation because it resets the timeSinceReport
        self.reportedTotal = self.time
        return s

    def __enter__(self):
        self.start()

    def __exit__(self, *args, **kwargs):
        self.stop()

    @property
    def isActive(self):
        """Return True if the code for this timer still running."""
        return self._active

    @property
    def numIterations(self):
        """If this number seems high, remember .start() twice in a row adds an iteration to numIterations."""
        return len(self._times) - 1 if self._times else 0

    @property
    def time(self):
        """Total time value."""
        return sum([t[1] - t[0] for t in self.times])

    @property
    def timeSinceReport(self):
        """The elapsed time since this timer was asked to report itself."""
        return self.time - self.reportedTotal

    @property
    def times(self):
        """List of time start / stop pairs, if active the current time is used as the last stop."""
        if self.isActive:
            times = copy.deepcopy(self._times)
            times[-1] = (self._times[-1][0], MasterTimer.time())
            return times
        else:
            return self._times

    def _openTimePair(self, curTime):
        self._times.append((curTime, None))

    def _closeTimePair(self, curTime):
        self._times[-1] = (self._times[-1][0], curTime)

    def start(self):
        """Start this Timer.

        Returns
        -------
        float : Time stamp for the current time / start time.
        """
        curTime = MasterTimer.time()

        if self._frozen:
            return curTime
        elif self.isActive:
            # call was made on an active timer, we're now over-started
            self.overStart += 1
            self._closeTimePair(curTime)

        self._active = True
        self._openTimePair(curTime)

        return curTime

    def stop(self):
        """Stop this Timer.

        Returns
        -------
        float : Time stamp for the current time / stop time.
        """
        curTime = MasterTimer.time()

        if self._frozen:
            return curTime

        if self.overStart:
            # can't end the timer as it's over-started
            self.overStart -= 1
        elif self.isActive:
            self._active = False
            self._closeTimePair(curTime)

        return curTime
