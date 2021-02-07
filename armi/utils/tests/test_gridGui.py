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
import asyncio
import base64
import os
import pytest
import subprocess
import time
import unittest
import test.support

# wxpython is an optional dependency, and without it we cant do much of anything. This
# should raise a unittest.SkipTest if it can't find wx, signalling to pytest to skip the
# rest of the module. Neat!
wx = test.support.import_module("wx")

import armi
from PIL import Image


if armi._app is None:
    armi.configure()
from armi.utils import gridEditor

from screeninfo import get_monitors

for m in get_monitors():
    print(str(m))
print(f"DISPLAY: {os.environ['DISPLAY']}")
loginctl = subprocess.check_output(
    ["loginctl", "list-sessions"]
)
print("loginctl list-sessions:")
for line in loginctl.decode("utf-8").split("\n"):
    print("  " + line)

loginctl_show = subprocess.check_output(
    ["loginctl", "show-session", "2"]
)
print("loginctl show-session 2:")
for line in loginctl_show.decode("utf-8").split("\n"):
    print("  " + line)
# if cut_output:
#     print(f"cut_output: {cut_output}")
#     display_server_type = (
#         subprocess.check_output(
#             ["loginctl", "show-session", "--property=Type"] + cut_output.split()
#         )
#         .decode("utf-8")
#         .strip("\n")
#     )
#     print(f"display_server_type: {display_server_type}")  # is it "x11"?
# else:
#     print("!!!!No loginctl sessions!!!!")

_SECONDS_PER_TICK = 0.05
# _TMP_DIR = "/tmp/armi"
_TMP_DIR = "/home/travis/build/terrapower/armi"


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


def wx2PIL(img: wx.Image) -> Image.Image:
    w = img.GetWidth()
    h = img.GetHeight()
    data = img.GetData()

    red_image = Image.frombuffer("L", (w, h), data[0::3])
    green_image = Image.frombuffer("L", (w, h), data[1::3])
    blue_image = Image.frombuffer("L", (w, h), data[2::3])
    raw_image = Image.merge("RGB", (red_image, green_image, blue_image))
    return raw_image.quantize(colors=16)


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
        self.imageList = []
        self.inputSimulator = wx.UIActionSimulator()

    def wait(self, num_ticks: int) -> None:
        for _ in range(num_ticks):
            time.sleep(_SECONDS_PER_TICK)
            self._takeScreenshot()

    def _takeScreenshot(self):
        bmp = wx.Bitmap(width=1200, height=1050)
        memDC = wx.MemoryDC()
        memDC.SelectObject(bmp)
        mousePos = wx.GetMouseState().GetPosition()
        memDC.Blit(0, 0, 1200, 1050, wx.ClientDC(self.frame), 0, 0)
        memDC.SetPen(wx.Pen(colour=wx.Colour(red=150, green=50, blue=50), width=5))
        memDC.DrawCircle(x=mousePos.x, y=mousePos.y, radius=7)
        memDC.SelectObject(wx.NullBitmap)
        img = bmp.ConvertToImage()
        self.imageList.append(img)

    def _addBlackScreen(self, num_frames=1):
        bmp = wx.Bitmap.FromRGBA(width=1200, height=1050)
        img = bmp.ConvertToImage()
        for _ in range(num_frames):
            self.imageList.append(img)

    def _saveAnimation(self, testcaseName):
        pilImageList = [wx2PIL(wxImage) for wxImage in self.imageList]
        gif = pilImageList[0]
        filename = os.path.join(_TMP_DIR, f"{testcaseName}.webp")
        with open(filename, mode="wb") as f:
            gif.save(
                fp=f,
                append_images=pilImageList[1:],
                save_all=True,
                duration=75,
                loop=0,
                minimize_size=True,
            )
        print("==========BASE64 BEGINS==========")
        with open(filename, mode="rb") as f:
            print(base64.standard_b64encode(f.read()).decode("ascii"))
        print("===========BASE64 ENDS===========")

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
        self.wait(num_ticks=5)
        self._addBlackScreen(num_frames=5)
        self._saveAnimation(result.originalname)
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
        # self.takeScreenshot()
        self.wait(num_ticks=1)
        self.inputSimulator.MouseMove(
            _findPointInWindow(self.gui.controls.ringControl, offsetFromLeft=0.15)
        )
        self.wait(num_ticks=5)
        # self.takeScreenshot()
        self.inputSimulator.MouseDblClick()
        self.wait(num_ticks=5)
        self.inputSimulator.KeyDown(49)  # 49 is the keycode for the "1" key
        self.wait(num_ticks=1)
        self.inputSimulator.KeyUp(49)
        self.wait(num_ticks=5)

        # Select (i, j) specifier
        # self.takeScreenshot()
        self.inputSimulator.MouseMove(_findPointInWindow(self.gui.controls.labelMode))
        self.wait(num_ticks=5)
        self.inputSimulator.MouseDown()
        self.wait(num_ticks=1)
        # self.takeScreenshot()
        self.inputSimulator.MouseUp()
        self.wait(num_ticks=5)
        self.inputSimulator.MouseMove(
            _findPointInWindow(self.gui.controls.labelMode, offsetFromTop=1.5)
        )
        self.wait(num_ticks=5)
        # self.takeScreenshot()
        self.inputSimulator.MouseDown()
        self.wait(num_ticks=1)
        self.inputSimulator.MouseUp()
        self.wait(num_ticks=5)

        # Click the Apply button
        # self.takeScreenshot()
        self.inputSimulator.MouseMove(_findPointInWindow(self.gui.controls.ringApply))
        self.wait(num_ticks=5)
        self.inputSimulator.MouseDown()
        self.wait(num_ticks=1)
        self.inputSimulator.MouseUp()
        self.wait(num_ticks=5)

        # self.takeScreenshot()
        # Assert that there is only one grid cell
        gridCellIndices = self.gui.clicker.indicesToPdcId
        self.assertEqual(1, len(gridCellIndices))

        # Assert that the grid cell contains "0, 0'
        labels = [self.gui.clicker._getLabel(idx)[0] for idx in gridCellIndices]
        self.assertEqual("0, 0", labels[0])


if __name__ == "__main__":
    unittest.main()
