# Copyright 2023 TerraPower, LLC
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
import unittest
from armi.reactor.components import UnshapedComponent
from armi.reactor.components.basicShapes import Circle, Hexagon, Rectangle
from armi.reactor.components.complexShapes import Helix
from armi.reactor.converters.axialExpansion.assemblyAxialLinkage import (
    AssemblyAxialLinkage,
)
class TestDetermineLinked(unittest.TestCase):
    """Test assemblyAxialLinkage.py::AssemblyAxialLinkage::_determineLinked for anticipated configrations

    This is the primary method used to determined if two components are linked axial linkage between components.
    """

    def setUp(self):
        """Contains common dimensions for all component class types."""
        self.common = ("test", "HT9", 25.0, 25.0)  # name, material, Tinput, Thot

    def runTest(
        self,
        componentsToTest: dict,
        assertionBool: bool,
        name: str,
        commonArgs: tuple = None,
    ):
        """Runs various linkage tests.

        Parameters
        ----------
        componentsToTest : dict
            keys --> component class type; values --> dimensions specific to key
        assertionBool : boolean
            expected truth value for test
        name : str
            the name of the test
        commonArgs : tuple, optional
            arguments common to all Component class types

        Notes
        -----
        - components "typeA" and "typeB" are assumed to be vertically stacked
        - two assertions: 1) comparing "typeB" component to "typeA"; 2) comparing "typeA" component to "typeB"
        - the different assertions are particularly useful for comparing two annuli
        - to add Component class types to a test:
            Add dictionary entry with following:
              {Component Class Type: [{<settings for component 1>}, {<settings for component 2>}]
        """
        if commonArgs is None:
            common = self.common
        else:
            common = commonArgs
        for method, dims in componentsToTest.items():
            typeA = method(*common, **dims[0])
            typeB = method(*common, **dims[1])
            if assertionBool:
                self.assertTrue(
                    AssemblyAxialLinkage._determineLinked(typeA, typeB),
                    msg="Test {0:s} failed for component type {1:s}!".format(
                        name, str(method)
                    ),
                )
                self.assertTrue(
                    AssemblyAxialLinkage._determineLinked(typeB, typeA),
                    msg="Test {0:s} failed for component type {1:s}!".format(
                        name, str(method)
                    ),
                )
            else:
                self.assertFalse(
                    AssemblyAxialLinkage._determineLinked(typeA, typeB),
                    msg="Test {0:s} failed for component type {1:s}!".format(
                        name, str(method)
                    ),
                )
                self.assertFalse(
                    AssemblyAxialLinkage._determineLinked(typeB, typeA),
                    msg="Test {0:s} failed for component type {1:s}!".format(
                        name, str(method)
                    ),
                )

    def test_overlappingSolidPins(self):
        componentTypesToTest = {
            Circle: [{"od": 0.5, "id": 0.0}, {"od": 1.0, "id": 0.0}],
            Hexagon: [{"op": 0.5, "ip": 0.0}, {"op": 1.0, "ip": 0.0}],
            Rectangle: [
                {
                    "lengthOuter": 0.5,
                    "lengthInner": 0.0,
                    "widthOuter": 0.5,
                    "widthInner": 0.0,
                },
                {
                    "lengthOuter": 1.0,
                    "lengthInner": 0.0,
                    "widthOuter": 1.0,
                    "widthInner": 0.0,
                },
            ],
            Helix: [
                {"od": 0.5, "axialPitch": 1.0, "helixDiameter": 1.0},
                {"od": 1.0, "axialPitch": 1.0, "helixDiameter": 1.0},
            ],
        }
        self.runTest(componentTypesToTest, True, "test_overlappingSolidPins")

    def test_differentMultNotOverlapping(self):
        componentTypesToTest = {
            Circle: [{"od": 0.5, "mult": 10}, {"od": 0.5, "mult": 20}],
            Hexagon: [{"op": 0.5, "mult": 10}, {"op": 1.0, "mult": 20}],
            Rectangle: [
                {"lengthOuter": 1.0, "widthOuter": 1.0, "mult": 10},
                {"lengthOuter": 1.0, "widthOuter": 1.0, "mult": 20},
            ],
            Helix: [
                {"od": 0.5, "axialPitch": 1.0, "helixDiameter": 1.0, "mult": 10},
                {"od": 1.0, "axialPitch": 1.0, "helixDiameter": 1.0, "mult": 20},
            ],
        }
        self.runTest(componentTypesToTest, False, "test_differentMultNotOverlapping")

    def test_solidPinNotOverlappingAnnulus(self):
        componentTypesToTest = {
            Circle: [{"od": 0.5, "id": 0.0}, {"od": 1.0, "id": 0.6}],
        }
        self.runTest(componentTypesToTest, False, "test_solidPinNotOverlappingAnnulus")

    def test_solidPinOverlappingWithAnnulus(self):
        componentTypesToTest = {
            Circle: [{"od": 0.7, "id": 0.0}, {"od": 1.0, "id": 0.6}],
        }
        self.runTest(componentTypesToTest, True, "test_solidPinOverlappingWithAnnulus")

    def test_annularPinNotOverlappingWithAnnulus(self):
        componentTypesToTest = {
            Circle: [{"od": 0.6, "id": 0.3}, {"od": 1.0, "id": 0.6}],
        }
        self.runTest(
            componentTypesToTest, False, "test_annularPinNotOverlappingWithAnnulus"
        )

    def test_annularPinOverlappingWithAnnuls(self):
        componentTypesToTest = {
            Circle: [{"od": 0.7, "id": 0.3}, {"od": 1.0, "id": 0.6}],
        }
        self.runTest(componentTypesToTest, True, "test_annularPinOverlappingWithAnnuls")

    def test_thinAnnularPinOverlappingWithThickAnnulus(self):
        componentTypesToTest = {
            Circle: [{"od": 0.7, "id": 0.3}, {"od": 0.6, "id": 0.5}],
        }
        self.runTest(
            componentTypesToTest, True, "test_thinAnnularPinOverlappingWithThickAnnulus"
        )

    def test_AnnularHexOverlappingThickAnnularHex(self):
        componentTypesToTest = {
            Hexagon: [{"op": 1.0, "ip": 0.8}, {"op": 1.2, "ip": 0.8}]
        }
        self.runTest(
            componentTypesToTest, True, "test_AnnularHexOverlappingThickAnnularHex"
        )

    def test_liquids(self):
        componentTypesToTest = {
            Circle: [{"od": 1.0, "id": 0.0}, {"od": 1.0, "id": 0.0}],
            Hexagon: [{"op": 1.0, "ip": 0.0}, {"op": 1.0, "ip": 0.0}],
        }
        liquid = ("test", "Sodium", 425.0, 425.0)  # name, material, Tinput, Thot
        self.runTest(componentTypesToTest, False, "test_liquids", commonArgs=liquid)

    def test_unshapedComponentAndCircle(self):
        comp1 = Circle(*self.common, od=1.0, id=0.0)
        comp2 = UnshapedComponent(*self.common, area=1.0)
        self.assertFalse(AssemblyAxialLinkage._determineLinked(comp1, comp2))
