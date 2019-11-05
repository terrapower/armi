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

"""Tests the geometry (loading input) file"""
import os
import unittest
import io

from armi.reactor import geometry
from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT

GEOM_INPUT = """<?xml version="1.0" ?>
<reactor geom="hex" symmetry="third core periodic">
    <assembly name="A1" pos="1"  ring="1"/>
    <assembly name="A2" pos="2"  ring="2"/>
    <assembly name="A3" pos="1"  ring="2"/>
    <assembly name="A4" pos="3"  ring="3"/>
    <assembly name="A5" pos="2"  ring="3"/>
    <assembly name="A6" pos="12" ring="3"/>
    <assembly name="A7" pos="4"  ring="3"/>
    <assembly name="A8" pos="1"  ring="3"/>
</reactor>
"""

# Sorry about the top line being a little out of alignment.
# it has to be written no further left than the line below it...
GEOM_INPUT_YAML = """reactor:
  core:
    geom: hex
    symmetry: third periodic
    lattice: |
        -     SH   SH   SH
        -  SH   SH   SH   SH
         SH   RR   RR   RR   SH
           RR   RR   RR   RR   SH
         RR   RR   RR   RR   RR   SH
           RR   OC   OC   RR   RR   SH
             OC   OC   OC   RR   RR   SH
           OC   OC   OC   OC   RR   RR
             OC   MC   OC   OC   RR   SH
               MC   MC   PC   OC   RR   SH
             MC   MC   MC   OC   OC   RR
               MC   MC   MC   OC   RR   SH
                 PC   MC   MC   OC   RR   SH
               MC   MC   MC   MC   OC   RR
                 IC   MC   MC   OC   RR   SH
                   IC   US   MC   OC   RR
                 IC   IC   MC   OC   RR   SH
                   IC   MC   MC   OC   RR
                 IC   IC   MC   PC   RR   SH
"""


class TestSystemLayoutInput(unittest.TestCase):
    def testReadHexGeomXML(self):
        geom = geometry.SystemLayoutInput()
        geom.readGeomFromFile(os.path.join(TEST_ROOT, "geom.xml"))
        self.assertEqual(geom.geomType, "hex")
        self.assertEqual(geom.assemTypeByIndices[(1, 1)], "IC")
        out = os.path.join(TEST_ROOT, "geom-output.xml")
        geom.writeGeom(out)
        os.remove(out)

    def testReadReactor(self):
        reactor = test_reactors.buildOperatorOfEmptyBlocks().r
        reactor.core.symmetry = geometry.THIRD_CORE + geometry.PERIODIC
        geom = geometry.fromReactor(reactor)
        self.assertEqual(geom.assemTypeByIndices[(2, 1)], "fuel")
        self.assertEqual(geom.geomType, "hex")

    def test_growToFullCore(self):
        geom = geometry.SystemLayoutInput()
        geom.readGeomFromStream(io.StringIO(GEOM_INPUT))
        self.assertNotIn((2, 3), geom.assemTypeByIndices)
        self.assertEqual(8, len(geom.assemTypeByIndices))
        geom.growToFullCore()
        self.assertEqual(geometry.FULL_CORE, geom.symmetry)
        self.assertIn((2, 3), geom.assemTypeByIndices)
        self.assertIn(
            geom.assemTypeByIndices[2, 3],  # perodic repeat
            geom.assemTypeByIndices[2, 1],
        )  # from input
        self.assertEqual(1 + 6 + 12, len(geom.assemTypeByIndices))

    def test_yamlIO(self):
        """Ensure we can read and write to YAML formatted streams."""
        geom = geometry.SystemLayoutInput()
        geom.readGeomFromStream(io.StringIO(GEOM_INPUT))
        fName = "testYamlIO.yaml"
        with open(fName, "w") as f:
            geom._writeYaml(f)  # pylint: disable=protected-access
        with open(fName) as f:
            geom2 = geometry.SystemLayoutInput()
            geom2._readYaml(f)  # pylint: disable=protected-access
        self.assertEqual(geom2.assemTypeByIndices[2, 2], "A2")
        os.remove(fName)

    def test_asciimap(self):
        """Ensure this can write ascii maps"""
        geom = geometry.SystemLayoutInput()
        geom.readGeomFromStream(io.StringIO(GEOM_INPUT))
        geom._writeAsciiMap()

    def test_readAsciimap(self):
        geom = geometry.SystemLayoutInput()
        geom._readYaml(io.StringIO(GEOM_INPUT_YAML))
        self.assertEqual(geom.assemTypeByIndices[(1, 1)], "IC")
        self.assertEqual(geom.assemTypeByIndices[(4, 1)], "US")
        # check top edge since it's complicated.
        self.assertEqual(geom.assemTypeByIndices[(10, 10)], "SH")
        self.assertEqual(geom.assemTypeByIndices[(11, 13)], "SH")


class TestSystemLayoutInputTRZ(unittest.TestCase):
    """
    Tests that require a full TRZ reactor.

    This loads a case that has hex-like geometry defined but the DerivedShapes have explicit areas defined
    because it can't auto-compute the area.
    """

    def testReadTRZGeomXML(self):
        geom = geometry.SystemLayoutInput()
        geom.readGeomFromFile(os.path.join(TEST_ROOT, "trz_geom.xml"))
        self.assertEqual(geom.geomType, "thetarz")
        self.assertEqual(geom.assemTypeByIndices[(0.0, 2.0, 0.0, 360.0, 1, 1)], "IC")

    def test_TRZyamlIO(self):
        geom = geometry.SystemLayoutInput()
        geom.readGeomFromFile(os.path.join(TEST_ROOT, "trz_geom.xml"))
        fName = "testTRZYamlIO.yaml"
        with open(fName, "w") as f:
            geom._writeYaml(f)  # pylint: disable=protected-access
        with open(fName) as f:
            geom2 = geometry.SystemLayoutInput()
            geom2._readYaml(f)  # pylint: disable=protected-access
        self.assertEqual(geom2.assemTypeByIndices[2.0, 3.0, 0.0, 180.0, 1, 1], "MC")
        os.remove(fName)


if __name__ == "__main__":
    #  import sys; sys.argv = ['', 'TestLoadingReactorTRZ.test_loadTRZGeom']
    unittest.main()
