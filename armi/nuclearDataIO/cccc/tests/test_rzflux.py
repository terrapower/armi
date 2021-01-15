"""
Test rzflux reading and writing.
"""
import unittest
import os

from armi.nuclearDataIO.cccc import rzflux

THIS_DIR = os.path.dirname(__file__)
# This RZFLUX was made by DIF3D 11 in a Cartesian test case.
SIMPLE_RZFLUX = os.path.join(THIS_DIR, "fixtures", "simple_cartesian.rzflux")


class TestRzflux(unittest.TestCase):
    r"""
    Tests the rzflux class.
    """

    def test_readRzflux(self):
        """Ensure we can read a RZFLUX file."""
        flux = rzflux.readBinary(SIMPLE_RZFLUX)
        self.assertEqual(
            flux.groupFluxes.shape, (flux.metadata["NGROUP"], flux.metadata["NZONE"])
        )

    def test_writeRzflux(self):
        """Ensure that we can write a modified RZFLUX file."""
        flux = rzflux.readBinary(SIMPLE_RZFLUX)
        rzflux.writeBinary(flux, "RZFLUX2")
        self.assertTrue(binaryFilesEqual(SIMPLE_RZFLUX, "RZFLUX2"))
        # perturb off-diag item to check row/col ordering
        flux.groupFluxes[2, 10] *= 1.1
        flux.groupFluxes[12, 1] *= 1.2
        rzflux.writeBinary(flux, "RZFLUX3")
        flux2 = rzflux.readBinary("RZFLUX3")
        self.assertAlmostEqual(flux2.groupFluxes[12, 1], flux.groupFluxes[12, 1])
        os.remove("RZFLUX2")
        os.remove("RZFLUX3")

    def test_rwAscii(self):
        """Ensure that we can read/write in ascii format."""
        flux = rzflux.readBinary(SIMPLE_RZFLUX)
        rzflux.writeAscii(flux, "RZFLUX.ascii")
        flux2 = rzflux.readAscii("RZFLUX.ascii")
        self.assertTrue((flux2.groupFluxes == flux.groupFluxes).all())
        os.remove("RZFLUX.ascii")


def binaryFilesEqual(fn1, fn2):
    """True if two files are bytewise identical."""
    with open(fn1, "rb") as f1, open(fn2, "rb") as f2:
        for byte1, byte2 in zip(f1, f2):
            if byte1 != byte2:
                return False
    return True
