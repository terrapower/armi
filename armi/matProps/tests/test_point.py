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

"""Program that runs all of the tests for the Point class."""

import unittest

from armi.matProps.point import Point


class TestPoint(unittest.TestCase):
    """Unit tests for the mat_props Point class."""

    def test_string(self):
        """Test string representation of Point."""
        p = Point(1, 2, 3)
        self.assertEqual(str(p), "<Point 1, 23>")
