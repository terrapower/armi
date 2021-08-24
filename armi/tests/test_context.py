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

import os
import shutil
import unittest

from armi import context

# CONSTANTS FOR TESTING
TEST_DIR1 = "test_createLogDir"


class TestContext(unittest.TestCase):
    def tearDown(self):
        # clean up any existing test directories
        testDirs = [TEST_DIR1]
        for testDir in testDirs:
            if os.path.exists(testDir):
                shutil.rmtree(testDir, ignore_errors=True)

    def test_createLogDir(self):
        """Test the createLogDir() method"""
        logDir = TEST_DIR1
        self.assertFalse(os.path.exists(logDir))
        context.createLogDir(0, logDir)
        self.assertTrue(os.path.exists(logDir))


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
