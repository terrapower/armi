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
from armi.physics.neutronics.crossSectionSettings import xsSettingsValidator
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
        cs = settings.Settings()
        xs = XSSettings()
        xa = XSModelingOptions("XA", fileLocation=["ISOXA"])
        xs["XA"] = xa
        self.assertEqual(["ISOXA"], xa.fileLocation)
        self.assertNotIn("XB", xs)
        xs.setDefaults(
            cs["xsBlockRepresentation"], cs["disableBlockTypeExclusionInXsGeneration"]
        )
        # Check that the file location of 'XB' still points to the same file location as 'XA'.
        self.assertEqual(xa, xs["XB"])

    def test_homogeneousXsDefaultSettingAssignment(self):
        """
        Make sure the object can whip up an unspecified xsID by default.

        This is used when user hasn't specified anything.
        """
        cs = settings.Settings()
        xsModel = XSSettings()
        xsModel.setDefaults(
            cs["xsBlockRepresentation"], cs["disableBlockTypeExclusionInXsGeneration"]
        )
        self.assertNotIn("YA", xsModel)
        self.assertEqual(xsModel["YA"].geometry, "0D")
        self.assertEqual(xsModel["YA"].criticalBuckling, True)

    def test_setDefaultSettingsByLowestBuGroupHomogeneous(self):
        # Initialize some micro suffix in the cross sections
        cs = settings.Settings()
        xs = XSSettings()
        jd = XSModelingOptions("JD", geometry="0D", criticalBuckling=False)
        xs["JD"] = jd
        xs.setDefaults(
            cs["xsBlockRepresentation"], cs["disableBlockTypeExclusionInXsGeneration"]
        )

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
        cs = settings.Settings()
        xsModel = XSSettings()
        rq = XSModelingOptions(
            "RQ",
            geometry="1D cylinder",
            blockRepresentation="Average",
            meshSubdivisionsPerCm=1.0,
        )
        xsModel["RQ"] = rq
        xsModel.setDefaults(
            cs["xsBlockRepresentation"], cs["disableBlockTypeExclusionInXsGeneration"]
        )

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
        cs = settings.Settings()
        xsModel = XSSettings()
        da = XSModelingOptions("DA", geometry="1D cylinder", meshSubdivisionsPerCm=1.0)
        xsModel["DA"] = da
        xsModel.setDefaults(
            cs["xsBlockRepresentation"], cs["disableBlockTypeExclusionInXsGeneration"]
        )
        self.assertEqual(xsModel["DA"].mergeIntoClad, ["gap"])
        self.assertEqual(xsModel["DA"].meshSubdivisionsPerCm, 1.0)

    def test_badCrossSections(self):
        with self.assertRaises(TypeError):
            # This will fail because it is not the required
            # Dict[str: Dict] structure
            xsSettingsValidator({"geometry": "4D"})

        with self.assertRaises(vol.error.MultipleInvalid):
            # This will fail because it has an invalid type for ``driverID``
            xsSettingsValidator({"AA": {"driverId": 0.0}})

        with self.assertRaises(vol.error.MultipleInvalid):
            # This will fail because it has an invalid value for
            # the ``blockRepresentation``
            xsSettingsValidator({"AA": {"blockRepresentation": "Invalid"}})

        with self.assertRaises(vol.error.MultipleInvalid):
            # This will fail because the ``xsID`` is not one or two
            # characters
            xsSettingsValidator({"AAA": {"blockRepresentation": "Average"}})


class Test_XSSettings(unittest.TestCase):
    def test_yamlIO(self):
        """Ensure we can read/write this custom setting object to yaml"""
        yaml = YAML()
        inp = yaml.load(io.StringIO(XS_EXAMPLE))
        xs = XSSettingDef("TestSetting")
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
            cs[CONF_CROSS_SECTION]["AA"] = XSModelingOptions("AA", geometry="0D")
            cs[CONF_CROSS_SECTION]["BA"] = XSModelingOptions("BA", geometry="0D")
            self.assertIn("AA", cs[CONF_CROSS_SECTION])
            self.assertIn("BA", cs[CONF_CROSS_SECTION])
            self.assertNotIn("CA", cs[CONF_CROSS_SECTION])
            self.assertNotIn("DA", cs[CONF_CROSS_SECTION])
            return cs

        cs = _setInitialXSSettings()
        cs[CONF_CROSS_SECTION] = {"AA": {}, "BA": {}}
        self.assertDictEqual(cs[CONF_CROSS_SECTION], {})
        self.assertTrue(isinstance(cs[CONF_CROSS_SECTION], XSSettings))

        # Produce an error if the setting is set to
        # a None value
        cs = _setInitialXSSettings()
        with self.assertRaises(TypeError):
            cs[CONF_CROSS_SECTION] = None

        cs = _setInitialXSSettings()
        cs[CONF_CROSS_SECTION] = {"AA": None, "BA": {}}
        self.assertDictEqual(cs[CONF_CROSS_SECTION], {})

        # Test that a new XS setting can be added to an existing
        # caseSetting using the ``XSModelingOptions`` or using
        # a dictionary.
        cs = _setInitialXSSettings()
        cs[CONF_CROSS_SECTION].update(
            {"CA": XSModelingOptions("CA", geometry="0D"), "DA": {"geometry": "0D"}}
        )
        self.assertIn("AA", cs[CONF_CROSS_SECTION])
        self.assertIn("BA", cs[CONF_CROSS_SECTION])
        self.assertIn("CA", cs[CONF_CROSS_SECTION])
        self.assertIn("DA", cs[CONF_CROSS_SECTION])

        # Clear out the settings by setting the value to a None.
        # This will be interpreted as a empty dictionary.
        cs[CONF_CROSS_SECTION] = {}
        self.assertDictEqual(cs[CONF_CROSS_SECTION], {})
        self.assertTrue(isinstance(cs[CONF_CROSS_SECTION], XSSettings))

        # This will fail because the ``setDefaults`` method on the
        # ``XSSettings`` has not yet been called.
        with self.assertRaises(ValueError):
            cs[CONF_CROSS_SECTION]["AA"]

        cs[CONF_CROSS_SECTION].setDefaults(
            blockRepresentation=cs["xsBlockRepresentation"],
            validBlockTypes=cs["disableBlockTypeExclusionInXsGeneration"],
        )

        cs[CONF_CROSS_SECTION]["AA"]
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].geometry, "0D")

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

        cs[CONF_CROSS_SECTION].setDefaults(
            cs["xsBlockRepresentation"], cs["disableBlockTypeExclusionInXsGeneration"]
        )

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
        cs[CONF_CROSS_SECTION].setDefaults(
            cs["xsBlockRepresentation"], cs["disableBlockTypeExclusionInXsGeneration"]
        )
        self.assertEqual(
            cs[CONF_CROSS_SECTION]["AA"].blockRepresentation, "FluxWeightedAverage"
        )

        # Check Average
        cs["xsBlockRepresentation"] = "Average"
        cs[CONF_CROSS_SECTION]["AA"] = XSModelingOptions("AA", fileLocation=[])
        cs[CONF_CROSS_SECTION].setDefaults(
            cs["xsBlockRepresentation"], cs["disableBlockTypeExclusionInXsGeneration"]
        )
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].blockRepresentation, "Average")

        # Check Median
        cs["xsBlockRepresentation"] = "Average"
        cs[CONF_CROSS_SECTION]["AA"] = XSModelingOptions(
            "AA", fileLocation=[], blockRepresentation="Median"
        )
        cs[CONF_CROSS_SECTION].setDefaults(
            cs["xsBlockRepresentation"], cs["disableBlockTypeExclusionInXsGeneration"]
        )
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].blockRepresentation, "Median")

    def test_xsSettingsSetDefault(self):
        """Test the configuration options of the ``setDefaults`` method."""
        cs = caseSettings.Settings()
        cs["xsBlockRepresentation"] = "FluxWeightedAverage"
        cs[CONF_CROSS_SECTION].setDefaults(
            blockRepresentation=cs["xsBlockRepresentation"], validBlockTypes=None
        )
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].validBlockTypes, None)

        cs[CONF_CROSS_SECTION].setDefaults(
            blockRepresentation=cs["xsBlockRepresentation"], validBlockTypes=True
        )
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].validBlockTypes, None)

        cs[CONF_CROSS_SECTION].setDefaults(
            blockRepresentation=cs["xsBlockRepresentation"], validBlockTypes=False
        )
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].validBlockTypes, ["fuel"])

        cs[CONF_CROSS_SECTION].setDefaults(
            blockRepresentation=cs["xsBlockRepresentation"],
            validBlockTypes=["control", "fuel", "plenum"],
        )
        self.assertEqual(
            cs[CONF_CROSS_SECTION]["AA"].validBlockTypes, ["control", "fuel", "plenum"]
        )


if __name__ == "__main__":
    # sys.argv = ["", "TestCrossSectionSettings.test_badCrossSections"]
    unittest.main()
