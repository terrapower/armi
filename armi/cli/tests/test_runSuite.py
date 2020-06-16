"""
Test for runsuite cli entry point
"""
import unittest

import sys
import io


class TestRunSuiteSuite(unittest.TestCase):
    def test_listCommand(self):
        """Ensure run-suite entry point is registered."""
        from armi import cli

        cli = cli.ArmiCLI()

        origout = sys.stdout
        try:
            out = io.StringIO()
            sys.stdout = out
            cli.listCommands()
        finally:
            sys.stdout = origout
        self.assertIn("run-suite", out.getvalue())


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
