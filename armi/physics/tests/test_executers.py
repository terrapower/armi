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
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
