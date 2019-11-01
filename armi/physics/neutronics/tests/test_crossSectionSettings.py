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

import unittest
import io

from ruamel.yaml import YAML
import voluptuous as vol

from armi import settings
from armi.physics.neutronics.crossSectionSettings import XSModelingOptions
from armi.physics.neutronics.crossSectionSettings import XSSettings
from armi.physics.neutronics.crossSectionSettings import XSSettingDef
from armi.physics.neutronics.crossSectionSettings import SINGLE_XS_SCHEMA
from armi.physics.neutronics.tests.test_neutronicsPlugin import XS_EXAMPLE


class TestCrossSectionSettings(unittest.TestCase):
    def test_crossSections(self):
        xsModel = XSModelingOptions(
            xsID="AA",
            geometry="0D",
            criticalBuckling=True,
            blockRepresentation="Median",
        )
        self.assertEqual("AA", xsModel.xsID)
        self.assertEqual("0D", xsModel.geometry)
        self.assertEqual(True, xsModel.criticalBuckling)
        self.assertEqual("Median", xsModel.blockRepresentation)

    def test_pregeneratedCrossSections(self):
        xs = XSSettings()
        xa = XSModelingOptions("XA", fileLocation=["ISOXA"])
        xs["XA"] = xa
        self.assertEqual(["ISOXA"], xa.fileLocation)
        self.assertNotIn("XB", xs)
        xs.setDefaults(settings.Settings())
        # Check that the file location of 'XB' still points to the same file location as 'XA'.
        self.assertEqual(xa, xs["XB"])

    def test_homogeneousXsDefaultSettingAssignment(self):
        """
        Make sure the object can whip up an unspecified xsID by default.

        This is used when user hasn't specified anything.
        """
        xsModel = XSSettings()
        xsModel.setDefaults(settings.Settings())
        self.assertNotIn("YA", xsModel)
        self.assertEqual(xsModel["YA"].geometry, "0D")
        self.assertEqual(xsModel["YA"].criticalBuckling, True)

    def test_setDefaultSettingsByLowestBuGroupHomogeneous(self):
        # Initialize some micro suffix in the cross sections
        xs = XSSettings()
        jd = XSModelingOptions("JD", geometry="0D", criticalBuckling=False)
        xs["JD"] = jd
        xs.setDefaults(settings.Settings())

        self.assertIn("JD", xs)

        # Check that new micro suffix `JF` with higher burn-up group gets assigned the same settings as `JD`
        self.assertNotIn("JF", xs)
        self.assertEqual(xs["JD"], xs["JF"])
        self.assertNotIn("JF", xs)

        # Check that new micro suffix `JG` with higher burn-up group gets assigned the same settings as `JD`
        self.assertNotIn("JG", xs)
        self.assertEqual(xs["JG"], xs["JD"])

        # Check that new micro suffix `JB` with lower burn-up group does NOT get assigned the same settings as `JD`
        self.assertNotIn("JB", xs)
        self.assertNotEqual(xs["JD"], xs["JB"])

    def test_setDefaultSettingsByLowestBuGroupOneDimensional(self):
        # Initialize some micro suffix in the cross sections
        xsModel = XSSettings()
        rq = XSModelingOptions(
            "RQ",
            geometry="1D slab",
            blockRepresentation="Average",
            meshSubdivisionsPerCm=1.0,
        )
        xsModel["RQ"] = rq
        xsModel.setDefaults(settings.Settings())

        # Check that new micro suffix `RY` with higher burn-up group gets assigned the same settings as `RQ`
        self.assertNotIn("RY", xsModel)
        self.assertEqual(xsModel["RY"], xsModel["RQ"])

        # Check that new micro suffix `RZ` with higher burn-up group gets assigned the same settings as `RQ`
        self.assertNotIn("RZ", xsModel)
        self.assertEqual(xsModel["RZ"], xsModel["RQ"])

        # Check that new micro suffix `RA` with lower burn-up group does NOT get assigned the same settings as `RQ`
        self.assertNotIn("RA", xsModel)
        self.assertNotEqual(xsModel["RA"], xsModel["RQ"])

    def test_optionalKey(self):
        """Test that optional key shows up with default value."""
        xsModel = XSSettings()
        da = XSModelingOptions("DA", geometry="1D slab", meshSubdivisionsPerCm=1.0)
        xsModel["DA"] = da
        xsModel.setDefaults(settings.Settings())
        self.assertEqual(xsModel["DA"].mergeIntoClad, [])
        self.assertEqual(xsModel["DA"].criticalBuckling, False)

    def test_badCrossSections(self):
        with self.assertRaises(vol.error.MultipleInvalid):
            SINGLE_XS_SCHEMA({"xsID": "HI", "geometry": "4D"})

        with self.assertRaises(vol.error.MultipleInvalid):
            SINGLE_XS_SCHEMA({"xsID": "HI", "driverId": 0.0})

        with self.assertRaises(vol.error.MultipleInvalid):
            SINGLE_XS_SCHEMA({"xsID": "HI", "blockRepresentation": "Invalid"})


class Test_XSSettings(unittest.TestCase):
    def test_yamlIO(self):
        """Ensure we can read/write this custom setting object to yaml"""
        yaml = YAML()
        inp = yaml.load(io.StringIO(XS_EXAMPLE))
        xs = XSSettingDef("TestSetting", XSSettings())
        xs._load(inp)  # pylint: disable=protected-access
        self.assertEqual(xs.value["BA"].geometry, "1D slab")
        outBuf = io.StringIO()
        output = xs.dump()
        yaml.dump(output, outBuf)
        outBuf.seek(0)
        inp2 = yaml.load(outBuf)
        self.assertEqual(inp.keys(), inp2.keys())


if __name__ == "__main__":
    # sys.argv = ["", "TestCrossSectionSettings.test_badCrossSections"]
    unittest.main()
