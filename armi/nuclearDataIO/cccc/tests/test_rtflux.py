"""
Test rtflux reading and writing.
"""
import unittest
import os

from armi.nuclearDataIO.cccc import rtflux

THIS_DIR = os.path.dirname(__file__)
# This rtflux was made by DIF3D 11 in a Cartesian test case.
SIMPLE_RTFLUX = os.path.join(THIS_DIR, "fixtures", "simple_cartesian.rtflux")


class Testrtflux(unittest.TestCase):
    r"""
    Tests the rtflux class.
    """

    def test_readrtflux(self):
        """Ensure we can read a rtflux file."""
        flux = rtflux.RtfluxStream.readBinary(SIMPLE_RTFLUX)
        self.assertEqual(
            flux.groupFluxes.shape,
            (
                flux.metadata["NINTI"],
                flux.metadata["NINTJ"],
                flux.metadata["NINTK"],
                flux.metadata["NGROUP"],
            ),
        )

    def test_writertflux(self):
        """Ensure that we can write a modified rtflux file."""
        flux = rtflux.RtfluxStream.readBinary(SIMPLE_RTFLUX)
        # perturb off-diag item to check row/col ordering
        flux.groupFluxes[2, 1, 3, 5] *= 1.1
        flux.groupFluxes[1, 2, 4, 6] *= 1.2
        rtflux.RtfluxStream.writeBinary(flux, "rtflux2")
        flux2 = rtflux.RtfluxStream.readBinary("rtflux2")
        self.assertAlmostEqual(
            flux2.groupFluxes[2, 1, 3, 5], flux.groupFluxes[2, 1, 3, 5]
        )
        os.remove("rtflux2")

    def test_rwAscii(self):
        """Ensure that we can read/write in ascii format."""
        flux = rtflux.RtfluxStream.readBinary(SIMPLE_RTFLUX)
        rtflux.RtfluxStream.writeAscii(flux, "rtflux.ascii")
        flux2 = rtflux.RtfluxStream.readAscii("rtflux.ascii")
        self.assertTrue((flux2.groupFluxes == flux.groupFluxes).all())
        os.remove("rtflux.ascii")

    def test_adjoint(self):
        """Ensure adjoint reads energy groups differently."""
        real = rtflux.RtfluxStream.readBinary(SIMPLE_RTFLUX)
        adjoint = rtflux.AtfluxStream.readBinary(SIMPLE_RTFLUX)
        self.assertFalse((real.groupFluxes == adjoint.groupFluxes).all())
        g = 3
        self.assertTrue(
            (
                real.groupFluxes[:, :, :, g]
                == adjoint.groupFluxes[:, :, :, real.metadata["NGROUP"] - g - 1]
            ).all()
        )
