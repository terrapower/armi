"""
Test GEODST reading and writing.
"""
import unittest
import os

from numpy.testing import assert_equal

from armi.nuclearDataIO.cccc import geodst

THIS_DIR = os.path.dirname(__file__)
SIMPLE_GEODST = os.path.join(THIS_DIR, "fixtures", "simple_hexz.geodst")


class TestGeodst(unittest.TestCase):
    r"""
    Tests the GEODST class.

    This reads from a GEODST file that was created using DIF3D 11 on a small
    test hex reactor in 1/3 geometry.
    """

    def test_readGeodst(self):
        """Ensure we can read a GEODST file."""
        geo = geodst.readBinary(SIMPLE_GEODST)
        self.assertEqual(geo.metadata["IGOM"], 18)
        self.assertAlmostEqual(geo.xmesh[1], 16.79, places=5)  # hex pitch
        self.assertAlmostEqual(geo.zmesh[-1], 448.0, places=5)  # top of reactor in cm
        self.assertEqual(geo.coarseMeshRegions.shape, (10, 10, len(geo.zmesh) - 1))
        self.assertEqual(geo.coarseMeshRegions.min(), 0)
        self.assertEqual(geo.coarseMeshRegions.max(), geo.metadata["NREG"])

    def test_writeGeodst(self):
        """Ensure that we can write a modified GEODST."""
        geo = geodst.readBinary(SIMPLE_GEODST)
        geo.zmesh[-1] *= 2
        geodst.writeBinary(geo, "GEODST2")
        geo2 = geodst.readBinary("GEODST2")
        self.assertAlmostEqual(geo2.zmesh[-1], 448.0 * 2, places=5)
        assert_equal(geo.kintervals, geo2.kintervals)
        os.remove("GEODST2")
