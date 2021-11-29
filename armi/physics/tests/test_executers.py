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

"""This module provides tests for the generic Executers."""
import os
import unittest

from armi.physics import executers


class TestExecutionOptions(unittest.TestCase):
    def test_runningDirectoryPath(self):
        """
        Test that the running directory path is set up correctly
        based on the case title and label provided.
        """
        e = executers.ExecutionOptions(label=None)
        e.setRunDirFromCaseTitle(caseTitle="test")
        self.assertEqual(os.path.basename(e.runDir), "508bc04f-0")

        e = executers.ExecutionOptions(label="label")
        e.setRunDirFromCaseTitle(caseTitle="test")
        self.assertEqual(os.path.basename(e.runDir), "b07da087-0")

        e = executers.ExecutionOptions(label="label2")
        e.setRunDirFromCaseTitle(caseTitle="test")
        self.assertEqual(os.path.basename(e.runDir), "9c1c83cb-0")


if __name__ == "__main__":
    unittest.main()
