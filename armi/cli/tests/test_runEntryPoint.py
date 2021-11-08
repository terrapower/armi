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
Test for run cli entry point
"""
import unittest

import sys

from armi.__main__ import main


class TestRun(unittest.TestCase):
    def test_runCommand(self):
        """Ensure main entry point with no args completes."""
        with self.assertRaises(SystemExit) as excinfo:
            sys.argv = [""]  # have to override the pytest args
            main()
        self.assertEqual(excinfo.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
