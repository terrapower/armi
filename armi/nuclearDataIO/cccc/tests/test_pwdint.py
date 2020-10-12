"""
Test PWDINT reading and writing.
"""
import unittest
import os

from armi.nuclearDataIO.cccc import pwdint

THIS_DIR = os.path.dirname(__file__)
SIMPLE_PWDINT = os.path.join(THIS_DIR, "fixtures", "simple_cartesian.pwdint")


class TestGeodst(unittest.TestCase):
    r"""
    Tests the PWDINT class.

    This reads from a PWDINT file that was created using DIF3D 11 on a small
    test hex reactor in 1/3 geometry.
    """

    def test_readGeodst(self):
        """Ensure we can read a PWDINT file."""
        pwr = pwdint.readBinary(SIMPLE_PWDINT)
        self.assertGreater(pwr.powerDensity.min(), 0.0)

    def test_writeGeodst(self):
        """Ensure that we can write a modified PWDINT."""
        pwr = pwdint.readBinary(SIMPLE_PWDINT)
        pwdint.writeBinary(pwr, "PWDINT2")
        pwr2 = pwdint.readBinary("PWDINT2")
        self.assertTrue((pwr2.powerDensity == pwr.powerDensity).all())
        os.remove("PWDINT2")
