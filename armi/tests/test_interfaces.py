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

"""Tests the Interface."""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import unittest
import os

from armi import interfaces
from armi import settings
from armi.tests import TEST_ROOT
from armi.utils import textProcessors


class DummyInterface(interfaces.Interface):
    name = "Dummy"
    function = "dummyAction"


class TestCodeInterface(unittest.TestCase):
    """Test Code interface."""

    def setUp(self):
        self.cs = settings.Settings()

    def test_isRequestedDetailPoint(self):
        """Tests notification of detail points."""
        newSettings = {"dumpSnapshot": ["000001", "995190"]}
        cs = self.cs.modified(newSettings=newSettings)

        i = DummyInterface(None, cs)

        self.assertEqual(i.isRequestedDetailPoint(0, 1), True)
        self.assertEqual(i.isRequestedDetailPoint(995, 190), True)
        self.assertEqual(i.isRequestedDetailPoint(5, 10), False)

    def test_enabled(self):
        """Test turning interfaces on and off."""
        i = DummyInterface(None, self.cs)

        self.assertEqual(i.enabled(), True)
        i.enabled(False)
        self.assertEqual(i.enabled(), False)
        i.enabled(True)
        self.assertEqual(i.enabled(), True)


class TestTextProcessor(unittest.TestCase):
    """Test Text processor."""

    def setUp(self):
        self.tp = textProcessors.TextProcessor(os.path.join(TEST_ROOT, "geom.xml"))

    def test_fsearch(self):
        """Test fsearch in re mode."""
        line = self.tp.fsearch("xml")
        self.assertIn("version", line)
        self.assertEqual(self.tp.fsearch("xml"), "")

    def test_fsearch_text(self):
        """Test fsearch in text mode."""
        line = self.tp.fsearch("xml", textFlag=True)
        self.assertIn("version", line)
        self.assertEqual(self.tp.fsearch("xml"), "")


class TestTightCoupler(unittest.TestCase):
    """Test the tight coupler class."""

    def setUp(self):
        cs = settings.Settings()
        cs["tightCoupling"] = True
        cs["tightCouplingSettings"] = {
            "dummyAction": {"parameter": "nothing", "convergence": 1.0e-5}
        }
        self.interface = DummyInterface(None, cs)

    def test_couplerActive(self):
        self.assertIsNotNone(self.interface.coupler)

    def test_storePreviousIterationValue(self):
        self.interface.coupler.storePreviousIterationValue(1.0)
        self.assertEqual(self.interface.coupler._previousIterationValue, 1.0)

    def test_storePreviousIterationValueException(self):
        with self.assertRaises(TypeError) as cm:
            self.interface.coupler.storePreviousIterationValue({5.0})
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_isConvergedValueError(self):
        with self.assertRaises(ValueError) as cm:
            self.interface.coupler.isConverged(1.0)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_isConverged(self):
        """Ensure TightCoupler.isConverged() works with float, 1D list, and ragged 2D list.

        Notes
        -----
        2D lists can end up being ragged as assemblies can have different number of blocks.
        Ragged lists are easier to manage with lists as opposed to numpy.arrays,
        namely, their dimension is preserved.
        """
        previousValues = {
            "float": 1.0,
            "list1D": [1.0, 2.0],
            "list2D": [[1, 2, 3], [1, 2]],
        }
        updatedValues = {
            "float": 5.0,
            "list1D": [5.0, 6.0],
            "list2D": [[5, 6, 7], [5, 6]],
        }
        for previous, current in zip(previousValues.values(), updatedValues.values()):
            self.interface.coupler.storePreviousIterationValue(previous)
            self.assertFalse(self.interface.coupler.isConverged(current))

    def test_isConvergedRuntimeError(self):
        """Test to ensure 3D arrays do not work."""
        previous = [[[1, 2, 3]], [[1, 2, 3]], [[1, 2, 3]]]
        updatedValues = [[[5, 6, 7]], [[5, 6, 7]], [[5, 6, 7]]]
        self.interface.coupler.storePreviousIterationValue(previous)
        with self.assertRaises(RuntimeError) as cm:
            self.interface.coupler.isConverged(updatedValues)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_getListDimension(self):
        a = [1, 2, 3]
        self.assertEqual(interfaces.TightCoupler.getListDimension(a), 1)
        a = [[1, 2, 3]]
        self.assertEqual(interfaces.TightCoupler.getListDimension(a), 2)
        a = [[[1, 2, 3]]]
        self.assertEqual(interfaces.TightCoupler.getListDimension(a), 3)


if __name__ == "__main__":
    unittest.main()
