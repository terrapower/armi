# Copyright 2021 Google, LLC
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
Tests for gridEditor.py.

By default, this would open the app in your primary display and steal control from your mouse and keyboard while the
test is running. This means that if your display is smaller than 1000 x 1000, or if you move your mouse when the test is
running, the test might fail even when things are fine.

These issues can be resolved by running the test in a virtual display. To do so, `pip install pytest-xvfb`,
and run `pytest test_gridGui.py` as usual. If you wish to change the resolution of the virtual display, you can modify
the `xvfb_width` and `xvfb_height` in `pytest.ini`.

After you have installed pytest-xvfb, you will no longer see the app displayed on your screen, which can make debugging
harder. Thus, during debugging, you may want the app to appear on your display by setting the `--no-xvfb` flag, and
have the print statements print to your console by setting the `--capture=tee-sys` flag, like this:
```
pytest --no-xvfb --capture=tee-sys test_gridGui.py
```

Note:
These tests currently require a rather specific environment:
1. wxPython needs to be installed, and
2. The test needs to run in a pure X11 environment (doesn't work in Wayland or XWayland, unfortunately).
To check if you are in an X11 environment, run this command:
```
loginctl list-sessions --no-legend | \
  cut --delimiter=' ' --field=1 | \
  xargs loginctl show-session --property=Type --value
```
If it outputs "x11", it should work (and if it outputs "wayland", it probably won't, for now).
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import asyncio
import os
import pytest
import time
import unittest
import test.support

# wxpython is an optional dependency, and without it we cant do much of anything. This
# should raise a unittest.SkipTest if it can't find wx, signalling to pytest to skip the
# rest of the module. Neat!
wx = test.support.import_module("wx")

import armi

if armi._app is None:
    armi.configure()
from armi.utils import gridEditor

_SECONDS_PER_TICK = 0.05


def _wait(num_ticks: int) -> None:
    time.sleep(num_ticks * _SECONDS_PER_TICK)


def _findPointInWindow(
    window: wx.Window, offsetFromLeft: float = 0.5, offsetFromTop: float = 0.5
) -> wx.Point:
    """Given a window, return a point in it. Defaults to the center of the window object.

    If offsets are smaller than 0 or greater than 1, this would return a point outside the window object.
    """
    rect: wx.Rect = window.GetScreenRect()
    x = rect.x + int(offsetFromLeft * rect.width)
    if x == rect.x + rect.width:
        x = rect.x + rect.width - 1
    y = rect.y + int(offsetFromTop * rect.height)
    if y == rect.y + rect.height:
        y = rect.y + rect.height - 1
    return wx.Point(x, y)


class GuiTestCase(unittest.TestCase):
    """Provides scaffolding for a GUI test.

    Without this scaffolding, the GUI's main loop would block the UIActionSimulator. Thus, the simulated actions and
    asserts must be run asynchronously within the GUI's event loop. Since the asserts are also run asynchronously,
    we need to make sure that the test does not end until all assert statements have been called, and that the test
    outputs are properly passed to the test framework. The app is also properly torn down after each test.

    This way, the user only needs to define the simulated actions and the expected behavior in order to write a UI test.
    """

    def initializeGui(self):
        """The user can override this to initialize the GUI differently.

        Note: This method is called in self.run(), before super().run. We deliberately avoid naming this 'setUp',
        because super().run internally calls self.setUp, which would be too late.
        """

        self.app = wx.App()
        self.frame = wx.Frame(
            None, wx.ID_ANY, title="Grid Blueprints UI", pos=(0, 0), size=(1000, 1000)
        )
        self.gui = gridEditor.GridBlueprintControl(self.frame)
        self.frame.Show()
        self.inputSimulator = wx.UIActionSimulator()

    def _cleanUpApp(self):
        for window in wx.GetTopLevelWindows():
            try:
                assert window.IsModal()
            except (AttributeError, AssertionError):
                window and window.Close()
            else:
                window.EndModal(0)
                self.app.ScheduleForDestruction(window)

    def _runAsync(self, result):
        super().run(result)
        self._cleanUpApp()
        self._testCompleted.set_result(None)

    def run(self, result=None):
        """Overrides unittest.TestCase.run."""
        self.initializeGui()
        loop = asyncio.get_event_loop()
        self._testCompleted = loop.create_future()
        wx.CallLater(0, self._runAsync, result)
        self.app.MainLoop()
        loop.run_until_complete(self._testCompleted)
        return result


@pytest.mark.skipif(
    not bool(os.environ.get("ARMI_GUI_TESTS", False)),
    reason="GUI tests require a rather specific environment (see above), so these tests are opt-in",
)
class Test(GuiTestCase):
    def test_setNumRings(self):
        # Set the number of rings to 1
        self.inputSimulator.MouseMove(
            _findPointInWindow(self.gui.controls.ringControl, offsetFromLeft=0.15)
        )
        _wait(num_ticks=5)
        self.inputSimulator.MouseDblClick()
        _wait(num_ticks=5)
        self.inputSimulator.KeyDown(49)  # 49 is the keycode for the "1" key
        _wait(num_ticks=1)
        self.inputSimulator.KeyUp(49)
        _wait(num_ticks=5)

        # Select (i, j) specifier
        self.inputSimulator.MouseMove(_findPointInWindow(self.gui.controls.labelMode))
        _wait(num_ticks=5)
        self.inputSimulator.MouseDown()
        _wait(num_ticks=1)
        self.inputSimulator.MouseUp()
        _wait(num_ticks=5)
        self.inputSimulator.MouseMove(
            _findPointInWindow(self.gui.controls.labelMode, offsetFromTop=1.5)
        )
        _wait(num_ticks=5)
        self.inputSimulator.MouseDown()
        _wait(num_ticks=1)
        self.inputSimulator.MouseUp()
        _wait(num_ticks=5)

        # Click the Apply button
        self.inputSimulator.MouseMove(_findPointInWindow(self.gui.controls.ringApply))
        _wait(num_ticks=5)
        self.inputSimulator.MouseDown()
        _wait(num_ticks=1)
        self.inputSimulator.MouseUp()
        _wait(num_ticks=5)

        # Assert that there is only one grid cell
        gridCellIndices = self.gui.clicker.indicesToPdcId
        self.assertEqual(1, len(gridCellIndices))

        # Assert that the grid cell contains "0, 0'
        labels = [self.gui.clicker._getLabel(idx)[0] for idx in gridCellIndices]
        self.assertEqual("0, 0", labels[0])


if __name__ == "__main__":
    unittest.main()
