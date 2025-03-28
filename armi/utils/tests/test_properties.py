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
"""Tests of the properties class."""
import unittest

from armi.utils import properties


class ImmutableClass:
    myNum = properties.createImmutableProperty(
        "myNum", "You must invoke the initialize() method", "My random number"
    )

    def initialize(self, val):
        properties.unlockImmutableProperties(self)
        try:
            self.myNum = val
        finally:
            properties.lockImmutableProperties(self)


class ImmutablePropertyTests(unittest.TestCase):
    def test_retreivingUnassignedValueRaisesError(self):
        ic = ImmutableClass()
        with self.assertRaises(properties.ImmutablePropertyError):
            print(ic.myNum)

    def test_cannotAssignValueToImmutableProperty(self):
        ic = ImmutableClass()
        ic.myNum = 4.0
        with self.assertRaises(properties.ImmutablePropertyError):
            ic.myNum = 2.2
        self.assertEqual(ic.myNum, 4.0)

    def test_unlockDoesntPermitReassignmentOfAnImmutProp(self):
        ic = ImmutableClass()
        ic.myNum = 7.7
        with self.assertRaises(properties.ImmutablePropertyError):
            ic.initialize(3.4)
        self.assertEqual(ic.myNum, 7.7)
