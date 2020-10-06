"""
Test rzflux reading and writing.
"""
import unittest
import os

from armi.nuclearDataIO import rzflux

THIS_DIR = os.path.dirname(__file__)
# This RZFLUX was made by DIF3D 11 in a Cartesian test case.
SIMPLE_RZFLUX = os.path.join(THIS_DIR, "fixtures", "RZFLUX")


class TestRzflux(unittest.TestCase):
    r"""
    Tests the rzflux class.
    """

    def test_readRzflux(self):
        """Ensure we can read a file."""
        flux = rzflux.readBinary(SIMPLE_RZFLUX)
        self.assertEqual(
            flux.groupFluxes.shape, (flux.metadata["NGROUP"], flux.metadata["NZONE"])
        )

    def test_writeRzflux(self):
        """Ensure that we can write a modified GEODST."""
        flux = rzflux.readBinary(SIMPLE_RZFLUX)
        flux.groupFluxes[0, 0] *= 1.1
        rzflux.writeBinary(flux, "RZFLUX2")
        flux2 = rzflux.readBinary("RZFLUX2")
        self.assertAlmostEqual(flux2.groupFluxes[0, 0], flux.groupFluxes[0, 0])
        os.remove("RZFLUX2")
