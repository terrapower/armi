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
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
