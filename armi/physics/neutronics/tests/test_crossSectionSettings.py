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
from armi.settings import caseSettings
from armi.physics.neutronics.crossSectionSettings import XSModelingOptions
from armi.physics.neutronics.crossSectionSettings import XSSettings
from armi.physics.neutronics.crossSectionSettings import XSSettingDef
from armi.physics.neutronics.crossSectionSettings import SINGLE_XS_SCHEMA
from armi.physics.neutronics.tests.test_neutronicsPlugin import XS_EXAMPLE
from armi.physics.neutronics.const import CONF_CROSS_SECTION


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
            geometry="1D cylinder",
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
        da = XSModelingOptions("DA", geometry="1D cylinder", meshSubdivisionsPerCm=1.0)
        xsModel["DA"] = da
        xsModel.setDefaults(settings.Settings())
        self.assertEqual(xsModel["DA"].mergeIntoClad, ["gap"])
        self.assertEqual(xsModel["DA"].meshSubdivisionsPerCm, 1.0)

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
        xs.setValue(inp)
        self.assertEqual(xs.value["BA"].geometry, "1D slab")
        outBuf = io.StringIO()
        output = xs.dump()
        yaml.dump(output, outBuf)
        outBuf.seek(0)
        inp2 = yaml.load(outBuf)
        self.assertEqual(inp.keys(), inp2.keys())

    def test_caseSettings(self):
        """
        Test the setting of the cross section setting using the case settings object.

        Notes
        -----
        The purpose of this test is to ensure that the cross sections sections can
        be removed from an existing case settings object once they have been set.
        """

        def _setInitialXSSettings():
            cs = caseSettings.Settings()
            cs[CONF_CROSS_SECTION] = XSSettings()
            cs[CONF_CROSS_SECTION]["AA"] = XSModelingOptions("AA")
            cs[CONF_CROSS_SECTION]["BA"] = XSModelingOptions("BA")
            self.assertIn("AA", cs[CONF_CROSS_SECTION].keys())
            self.assertIn("BA", cs[CONF_CROSS_SECTION].keys())
            self.assertNotIn("CA", cs[CONF_CROSS_SECTION].keys())
            self.assertNotIn("DA", cs[CONF_CROSS_SECTION].keys())
            return cs

        # Test that the cross section setting can be completely cleared
        # using a None value, by setting the value to an empty dictionary,
        # or by setting the individual keys to None or empty dictionaries.
        cs = _setInitialXSSettings()
        cs[CONF_CROSS_SECTION] = None
        self.assertDictEqual(cs[CONF_CROSS_SECTION], {})

        cs = _setInitialXSSettings()
        cs[CONF_CROSS_SECTION] = {"AA": {}, "BA": {}}
        self.assertDictEqual(cs[CONF_CROSS_SECTION], {})

        cs = _setInitialXSSettings()
        cs[CONF_CROSS_SECTION] = {"AA": None, "BA": {}}
        self.assertDictEqual(cs[CONF_CROSS_SECTION], {})

        # Test that a new XS setting can be added to an existing
        # caseSetting using the ``XSModelingOptions`` or using
        # a dictionary.
        cs = _setInitialXSSettings()
        cs[CONF_CROSS_SECTION].update(
            {"CA": XSModelingOptions("CA"), "DA": {"geometry": "0D"}}
        )
        self.assertIn("AA", cs[CONF_CROSS_SECTION].keys())
        self.assertIn("BA", cs[CONF_CROSS_SECTION].keys())
        self.assertIn("CA", cs[CONF_CROSS_SECTION].keys())
        self.assertIn("DA", cs[CONF_CROSS_SECTION].keys())

        # Clear out the settings by setting the value to a None.
        # This will be interpreted as a empty dictionary.
        cs[CONF_CROSS_SECTION] = None
        self.assertDictEqual(cs[CONF_CROSS_SECTION], {})

    def test_csBlockRepresentation(self):
        """
        Test that the XS block representation is applied globally,
        but only to XS modeling options where the blockRepresentation
        has not already been assigned.
        """
        cs = caseSettings.Settings()
        cs["xsBlockRepresentation"] = "FluxWeightedAverage"
        cs[CONF_CROSS_SECTION] = XSSettings()
        cs[CONF_CROSS_SECTION]["AA"] = XSModelingOptions("AA", geometry="0D")
        cs[CONF_CROSS_SECTION]["BA"] = XSModelingOptions(
            "BA", geometry="0D", blockRepresentation="Average"
        )

        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].blockRepresentation, None)
        self.assertEqual(cs[CONF_CROSS_SECTION]["BA"].blockRepresentation, "Average")

        cs[CONF_CROSS_SECTION].setDefaults(cs)

        self.assertEqual(
            cs[CONF_CROSS_SECTION]["AA"].blockRepresentation, "FluxWeightedAverage"
        )
        self.assertEqual(cs[CONF_CROSS_SECTION]["BA"].blockRepresentation, "Average")

    def test_csBlockRepresentationFileLocation(self):
        """
        Test that default blockRepresentation is applied correctly to a
        XSModelingOption that has the ``fileLocation`` attribute defined.
        """
        cs = caseSettings.Settings()
        cs["xsBlockRepresentation"] = "FluxWeightedAverage"
        cs[CONF_CROSS_SECTION] = XSSettings()
        cs[CONF_CROSS_SECTION]["AA"] = XSModelingOptions("AA", fileLocation=[])

        # Check FluxWeightedAverage
        cs[CONF_CROSS_SECTION].setDefaults(cs)
        self.assertEqual(
            cs[CONF_CROSS_SECTION]["AA"].blockRepresentation, "FluxWeightedAverage"
        )

        # Check Average
        cs["xsBlockRepresentation"] = "Average"
        cs[CONF_CROSS_SECTION]["AA"] = XSModelingOptions("AA", fileLocation=[])
        cs[CONF_CROSS_SECTION].setDefaults(cs)
        self.assertEqual(
            cs[CONF_CROSS_SECTION]["AA"].blockRepresentation, "Average"
        )

        # Check Median
        cs["xsBlockRepresentation"] = "Average"
        cs[CONF_CROSS_SECTION]["AA"] = XSModelingOptions(
            "AA", fileLocation=[], blockRepresentation="Median"
        )
        cs[CONF_CROSS_SECTION].setDefaults(cs)
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].blockRepresentation, "Median")


if __name__ == "__main__":
    # sys.argv = ["", "TestCrossSectionSettings.test_badCrossSections"]
    unittest.main()
