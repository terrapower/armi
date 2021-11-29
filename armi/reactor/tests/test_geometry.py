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
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import os
import unittest
import io

from armi.reactor import geometry
from armi.reactor.systemLayoutInput import SystemLayoutInput
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


class TestGeomType(unittest.TestCase):
    def testFromStr(self):
        # note the bonkers case and extra whitespace to exercise the canonicalization
        self.assertEqual(geometry.GeomType.fromStr("HeX"), geometry.GeomType.HEX)
        self.assertEqual(
            geometry.GeomType.fromStr("cARTESIAN"), geometry.GeomType.CARTESIAN
        )
        self.assertEqual(geometry.GeomType.fromStr(" thetaRZ"), geometry.GeomType.RZT)
        self.assertEqual(geometry.GeomType.fromStr("rZ  "), geometry.GeomType.RZ)

        with self.assertRaises(ValueError):
            geometry.GeomType.fromStr("what even is this?")

    def testLabel(self):
        gt = geometry.GeomType.fromStr("hex")
        self.assertEqual(gt.label, "Hexagonal")
        gt = geometry.GeomType.fromStr("cartesian")
        self.assertEqual(gt.label, "Cartesian")
        gt = geometry.GeomType.fromStr("rz")
        self.assertEqual(gt.label, "R-Z")
        gt = geometry.GeomType.fromStr("thetarz")
        self.assertEqual(gt.label, "R-Z-Theta")

    def testStr(self):
        for geom in {geometry.HEX, geometry.CARTESIAN, geometry.RZ, geometry.RZT}:
            self.assertEqual(str(geometry.GeomType.fromStr(geom)), geom)


class TestSymmetryType(unittest.TestCase):
    def testFromStr(self):
        # note the bonkers case and extra whitespace to exercise the canonicalization
        self.assertEqual(
            geometry.SymmetryType.fromStr("thiRd periodic ").domain,
            geometry.DomainType.THIRD_CORE,
        )
        st = geometry.SymmetryType.fromStr("sixteenth reflective")
        self.assertEqual(st.boundary, geometry.BoundaryType.REFLECTIVE)
        self.assertEqual(str(st), "sixteenth reflective")

        with self.assertRaises(ValueError):
            geometry.SymmetryType.fromStr("what even is this?")

    def testFromAny(self):
        st = geometry.SymmetryType.fromAny("eighth reflective through center assembly")
        self.assertTrue(st.isThroughCenterAssembly)
        self.assertEqual(st.domain, geometry.DomainType.EIGHTH_CORE)
        self.assertEqual(st.boundary, geometry.BoundaryType.REFLECTIVE)

        st = geometry.SymmetryType(
            geometry.DomainType.EIGHTH_CORE, geometry.BoundaryType.REFLECTIVE, True
        )
        self.assertTrue(st.isThroughCenterAssembly)
        self.assertEqual(st.domain, geometry.DomainType.EIGHTH_CORE)
        self.assertEqual(st.boundary, geometry.BoundaryType.REFLECTIVE)

        newST = geometry.SymmetryType.fromAny(st)
        self.assertTrue(newST.isThroughCenterAssembly)
        self.assertEqual(newST.domain, geometry.DomainType.EIGHTH_CORE)
        self.assertEqual(newST.boundary, geometry.BoundaryType.REFLECTIVE)

    def testBaseConstructor(self):
        self.assertEqual(
            geometry.SymmetryType(
                geometry.DomainType.SIXTEENTH_CORE, geometry.BoundaryType.REFLECTIVE
            ).domain,
            geometry.DomainType.SIXTEENTH_CORE,
        )
        self.assertEqual(
            str(
                geometry.SymmetryType(
                    geometry.DomainType.FULL_CORE, geometry.BoundaryType.NO_SYMMETRY
                ).boundary
            ),
            "",
        )

    def testLabel(self):
        st = geometry.SymmetryType(
            geometry.DomainType.FULL_CORE, geometry.BoundaryType.NO_SYMMETRY
        )
        self.assertEqual(st.domain.label, "Full")
        self.assertEqual(st.boundary.label, "No Symmetry")
        st = geometry.SymmetryType(
            geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC
        )
        self.assertEqual(st.domain.label, "Third")
        self.assertEqual(st.boundary.label, "Periodic")
        st = geometry.SymmetryType(
            geometry.DomainType.QUARTER_CORE, geometry.BoundaryType.REFLECTIVE
        )
        self.assertEqual(st.domain.label, "Quarter")
        self.assertEqual(st.boundary.label, "Reflective")
        st = geometry.SymmetryType(
            geometry.DomainType.EIGHTH_CORE, geometry.BoundaryType.REFLECTIVE
        )
        self.assertEqual(st.domain.label, "Eighth")
        st = geometry.SymmetryType(
            geometry.DomainType.SIXTEENTH_CORE, geometry.BoundaryType.REFLECTIVE
        )
        self.assertEqual(st.domain.label, "Sixteenth")

    def testSymmetryFactor(self):
        st = geometry.SymmetryType(
            geometry.DomainType.FULL_CORE, geometry.BoundaryType.NO_SYMMETRY
        )
        self.assertEqual(st.symmetryFactor(), 1.0)
        st = geometry.SymmetryType(
            geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC
        )
        self.assertEqual(st.symmetryFactor(), 3.0)
        st = geometry.SymmetryType(
            geometry.DomainType.QUARTER_CORE, geometry.BoundaryType.REFLECTIVE
        )
        self.assertEqual(st.symmetryFactor(), 4.0)
        st = geometry.SymmetryType(
            geometry.DomainType.EIGHTH_CORE, geometry.BoundaryType.REFLECTIVE
        )
        self.assertEqual(st.symmetryFactor(), 8.0)
        st = geometry.SymmetryType(
            geometry.DomainType.SIXTEENTH_CORE, geometry.BoundaryType.REFLECTIVE
        )
        self.assertEqual(st.symmetryFactor(), 16.0)

    def test_checkValidGeomSymmetryCombo(self):
        geomHex = geometry.GeomType.HEX
        geomCart = geometry.GeomType.CARTESIAN
        geomRZT = geometry.GeomType.RZT
        geomRZ = geometry.GeomType.RZ
        fullCore = geometry.SymmetryType(
            geometry.DomainType.FULL_CORE, geometry.BoundaryType.NO_SYMMETRY
        )
        thirdPeriodic = geometry.SymmetryType(
            geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC
        )
        quarterCartesian = geometry.SymmetryType(
            geometry.DomainType.QUARTER_CORE, geometry.BoundaryType.REFLECTIVE
        )

        self.assertTrue(geometry.checkValidGeomSymmetryCombo(geomHex, thirdPeriodic))
        self.assertTrue(geometry.checkValidGeomSymmetryCombo(geomHex, fullCore))
        self.assertTrue(
            geometry.checkValidGeomSymmetryCombo(geomCart, quarterCartesian)
        )
        self.assertTrue(geometry.checkValidGeomSymmetryCombo(geomRZT, quarterCartesian))
        self.assertTrue(geometry.checkValidGeomSymmetryCombo(geomRZ, fullCore))

        with self.assertRaises(ValueError):
            _ = geometry.SymmetryType(
                geometry.DomainType.THIRD_CORE,
                geometry.BoundaryType.REFLECTIVE,
                False,
            )
        with self.assertRaises(ValueError):
            geometry.checkValidGeomSymmetryCombo(geomHex, quarterCartesian)

        with self.assertRaises(ValueError):
            geometry.checkValidGeomSymmetryCombo(geomCart, thirdPeriodic)


class TestSystemLayoutInput(unittest.TestCase):
    def testReadHexGeomXML(self):
        geom = SystemLayoutInput()
        geom.readGeomFromFile(os.path.join(TEST_ROOT, "geom.xml"))
        self.assertEqual(str(geom.geomType), geometry.HEX)
        self.assertEqual(geom.assemTypeByIndices[(1, 1)], "IC")
        out = os.path.join(TEST_ROOT, "geom-output.xml")
        geom.writeGeom(out)
        os.remove(out)

    def testReadReactor(self):
        reactor = test_reactors.buildOperatorOfEmptyHexBlocks().r
        reactor.core.symmetry = geometry.SymmetryType(
            geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC
        )
        geom = SystemLayoutInput.fromReactor(reactor)
        self.assertEqual(geom.assemTypeByIndices[(2, 1)], "fuel")
        self.assertEqual(str(geom.geomType), geometry.HEX)

    def test_growToFullCore(self):
        geom = SystemLayoutInput()
        geom.readGeomFromStream(io.StringIO(GEOM_INPUT))
        self.assertNotIn((2, 3), geom.assemTypeByIndices)
        self.assertEqual(8, len(geom.assemTypeByIndices))
        geom.growToFullCore()
        self.assertEqual(geometry.FULL_CORE, str(geom.symmetry.domain))
        self.assertIn((2, 3), geom.assemTypeByIndices)
        self.assertIn(
            geom.assemTypeByIndices[2, 3],  # perodic repeat
            geom.assemTypeByIndices[2, 1],
        )  # from input
        self.assertEqual(1 + 6 + 12, len(geom.assemTypeByIndices))

    def test_yamlIO(self):
        """Ensure we can read and write to YAML formatted streams."""
        geom = SystemLayoutInput()
        geom.readGeomFromStream(io.StringIO(GEOM_INPUT))
        fName = "testYamlIO.yaml"
        with open(fName, "w") as f:
            geom._writeYaml(f)  # pylint: disable=protected-access
        with open(fName) as f:
            geom2 = SystemLayoutInput()
            geom2._readYaml(f)  # pylint: disable=protected-access
        self.assertEqual(geom2.assemTypeByIndices[2, 2], "A2")
        os.remove(fName)

    def test_asciimap(self):  # pylint: disable=no-self-use
        """Ensure this can write ascii maps"""
        geom = SystemLayoutInput()
        geom.readGeomFromStream(io.StringIO(GEOM_INPUT))
        geom._writeAsciiMap()

    def test_readAsciimap(self):
        geom = SystemLayoutInput()
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
        geom = SystemLayoutInput()
        geom.readGeomFromFile(os.path.join(TEST_ROOT, "trz_geom.xml"))
        self.assertEqual(str(geom.geomType), geometry.RZT)
        self.assertEqual(geom.assemTypeByIndices[(0.0, 2.0, 0.0, 360.0, 1, 1)], "IC")

    def test_TRZyamlIO(self):
        geom = SystemLayoutInput()
        geom.readGeomFromFile(os.path.join(TEST_ROOT, "trz_geom.xml"))
        fName = "testTRZYamlIO.yaml"
        with open(fName, "w") as f:
            geom._writeYaml(f)  # pylint: disable=protected-access
        with open(fName) as f:
            geom2 = SystemLayoutInput()
            geom2._readYaml(f)  # pylint: disable=protected-access
        self.assertEqual(geom2.assemTypeByIndices[2.0, 3.0, 0.0, 180.0, 1, 1], "MC")
        os.remove(fName)


if __name__ == "__main__":
    #  import sys; sys.argv = ['', 'TestLoadingReactorTRZ.test_loadTRZGeom']
    unittest.main()
