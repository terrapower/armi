# Copyright 2026 TerraPower, LLC
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

"""Test the Reference."""

import unittest

from matProps.reference import Reference


class TestReference(unittest.TestCase):
    """Unit tests for Reference."""

    def test_str(self):
        ref = Reference()
        ref._ref = "REF123"
        ref._type = "TYPE321"

        self.assertEqual(str(ref), "REF123 (TYPE321)")

    def test_getRef(self):
        ref = Reference()
        ref._ref = "REF234"

        self.assertEqual(ref.getRef(), "REF234")

    def test_getType(self):
        ref = Reference()
        ref._type = "TYPE789"

        self.assertEqual(ref.getType(), "TYPE789")

    def test_factory(self):
        node = {"ref": "REF234", "type": "TYPE789"}
        ref = Reference._factory(node)
        self.assertEqual(str(ref), "REF234 (TYPE789)")
        self.assertEqual(ref.getRef(), "REF234")
        self.assertEqual(ref.getType(), "TYPE789")
