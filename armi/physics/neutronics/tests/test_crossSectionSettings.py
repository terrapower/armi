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
"""XS Settings tests."""

import io
import unittest

import voluptuous as vol
from ruamel.yaml import YAML

from armi import settings
from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.physics.neutronics.crossSectionSettings import (
    CONF_BLOCK_REPRESENTATION,
    CONF_GEOM,
    XSModelingOptions,
    XSSettingDef,
    XSSettings,
    xsSettingsValidator,
)
from armi.physics.neutronics.settings import (
    CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION,
    CONF_XS_BLOCK_REPRESENTATION,
)
from armi.physics.neutronics.tests.test_neutronicsPlugin import XS_EXAMPLE
from armi.settings import caseSettings


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
        self.assertEqual("Median", xsModel.blockRepresentation)
        self.assertFalse(xsModel.fluxIsPregenerated)
        self.assertFalse(xsModel.xsIsPregenerated)
        self.assertTrue(xsModel.criticalBuckling)

    def test_pregeneratedCrossSections(self):
        cs = settings.Settings()
        xs = XSSettings()
        xa = XSModelingOptions("XA", xsFileLocation=["ISOXA"])
        xs["XA"] = xa
        self.assertEqual(["ISOXA"], xa.xsFileLocation)
        self.assertNotIn("XB", xs)
        xs.setDefaults(
            cs[CONF_XS_BLOCK_REPRESENTATION],
            cs[CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION],
        )
        # Check that the file location of 'XB' still points to the same file location as 'XA'.
        self.assertEqual(xa, xs["XB"])
        self.assertFalse(xa.fluxIsPregenerated)
        self.assertTrue(xa.xsIsPregenerated)
        self.assertFalse(xa.criticalBuckling)

    def test_pregeneratedFluxInputs(self):
        xsModel = XSModelingOptions(
            xsID="AA",
            fluxFileLocation="ISOAA",
            geometry="0D",
            criticalBuckling=True,
            blockRepresentation="Median",
        )
        self.assertEqual("AA", xsModel.xsID)
        self.assertEqual("0D", xsModel.geometry)
        self.assertEqual("ISOAA", xsModel.fluxFileLocation)
        self.assertTrue(xsModel.fluxIsPregenerated)
        self.assertTrue(xsModel.criticalBuckling)
        self.assertEqual("Median", xsModel.blockRepresentation)

    def test_prioritization(self):
        xsModel = XSModelingOptions(
            xsID="AA",
            geometry="0D",
            criticalBuckling=True,
            xsPriority=2,
            xsExecuteExclusive=True,
        )
        self.assertEqual("AA", xsModel.xsID)
        self.assertEqual(True, xsModel.xsExecuteExclusive)
        self.assertEqual(2, xsModel.xsPriority)

        xsModel = XSModelingOptions(
            xsID="AA",
            geometry="0D",
            criticalBuckling=True,
        )
        # defaults work
        xsModel.setDefaults("Average", False)
        self.assertEqual(False, xsModel.xsExecuteExclusive)
        self.assertEqual(5, xsModel.xsPriority)

    def test_homogeneousXsDefaultSettingAssignment(self):
        """
        Make sure the object can whip up an unspecified xsID by default.

        This is used when user hasn't specified anything.
        """
        cs = settings.Settings()
        xsModel = XSSettings()
        xsModel.setDefaults(
            cs[CONF_XS_BLOCK_REPRESENTATION],
            cs[CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION],
        )
        self.assertNotIn("YA", xsModel)
        self.assertEqual(xsModel["YA"].geometry, "0D")
        self.assertEqual(xsModel["YA"].criticalBuckling, True)
        self.assertEqual(xsModel["YA"].ductHeterogeneous, False)
        self.assertEqual(xsModel["YA"].traceIsotopeThreshold, 0.0)

    def test_setDefSettingsByLowestEnvGroupHomog(self):
        # Initialize some micro suffix in the cross sections
        cs = settings.Settings()
        xs = XSSettings()
        jd = XSModelingOptions("JD", geometry="0D", criticalBuckling=False)
        xs["JD"] = jd
        xs.setDefaults(
            cs[CONF_XS_BLOCK_REPRESENTATION],
            cs[CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION],
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

    def test_setDefSettingsByLowestEnvGroup1D(self):
        # Initialize some micro suffix in the cross sections
        cs = settings.Settings()
        xsModel = XSSettings()
        rq = XSModelingOptions(
            "RQ",
            geometry="1D cylinder",
            blockRepresentation="ComponentAverage1DCylinder",
            meshSubdivisionsPerCm=1.0,
        )
        xsModel["RQ"] = rq
        xsModel.setDefaults(
            cs[CONF_XS_BLOCK_REPRESENTATION],
            cs[CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION],
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
        da = XSModelingOptions(
            "DA",
            geometry="1D cylinder",
            meshSubdivisionsPerCm=1.0,
            ductHeterogeneous=True,
            traceIsotopeThreshold=1.0e-5,
        )
        xsModel["DA"] = da
        xsModel.setDefaults(
            cs[CONF_XS_BLOCK_REPRESENTATION],
            cs[CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION],
        )
        self.assertEqual(xsModel["DA"].mergeIntoClad, ["gap"])
        self.assertEqual(xsModel["DA"].meshSubdivisionsPerCm, 1.0)
        self.assertEqual(xsModel["DA"].ductHeterogeneous, True)
        self.assertEqual(xsModel["DA"].traceIsotopeThreshold, 1.0e-5)
        self.assertEqual(xsModel["DA"].mergeIntoFuel, [])

    def test_badCrossSections(self):
        with self.assertRaises(TypeError):
            # This will fail because it is not the required
            # Dict[str: Dict] structure
            xsSettingsValidator({CONF_GEOM: "4D"})

        with self.assertRaises(vol.error.MultipleInvalid):
            # This will fail because it has an invalid type for ``driverID``
            xsSettingsValidator({"AA": {"driverId": 0.0}})

        with self.assertRaises(vol.error.MultipleInvalid):
            # This will fail because it has an invalid value for
            # the ``blockRepresentation``
            xsSettingsValidator({"AA": {CONF_BLOCK_REPRESENTATION: "Invalid"}})

        with self.assertRaises(vol.error.MultipleInvalid):
            # This will fail because the ``xsID`` is not one or two
            # characters
            xsSettingsValidator({"AAA": {CONF_BLOCK_REPRESENTATION: "Average"}})


class TestXSSettings(unittest.TestCase):
    def test_yamlIO(self):
        """Ensure we can read/write this custom setting object to yaml."""
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
        cs[CONF_CROSS_SECTION].update({"CA": XSModelingOptions("CA", geometry="0D"), "DA": {CONF_GEOM: "0D"}})
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
            blockRepresentation=cs[CONF_XS_BLOCK_REPRESENTATION],
            validBlockTypes=cs[CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION],
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
        cs[CONF_XS_BLOCK_REPRESENTATION] = "FluxWeightedAverage"
        cs[CONF_CROSS_SECTION] = XSSettings()
        cs[CONF_CROSS_SECTION]["AA"] = XSModelingOptions("AA", geometry="0D")
        cs[CONF_CROSS_SECTION]["BA"] = XSModelingOptions("BA", geometry="0D", blockRepresentation="Average")

        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].blockRepresentation, None)
        self.assertEqual(cs[CONF_CROSS_SECTION]["BA"].blockRepresentation, "Average")

        cs[CONF_CROSS_SECTION].setDefaults(
            cs[CONF_XS_BLOCK_REPRESENTATION],
            cs[CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION],
        )

        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].blockRepresentation, "FluxWeightedAverage")
        self.assertEqual(cs[CONF_CROSS_SECTION]["BA"].blockRepresentation, "Average")

    def test_csBlockRepresentationFileLocation(self):
        """
        Test that default blockRepresentation is applied correctly to a
        XSModelingOption that has the ``xsFileLocation`` attribute defined.
        """
        cs = caseSettings.Settings()
        cs[CONF_XS_BLOCK_REPRESENTATION] = "FluxWeightedAverage"
        cs[CONF_CROSS_SECTION] = XSSettings()
        cs[CONF_CROSS_SECTION]["AA"] = XSModelingOptions("AA", xsFileLocation=[])

        # Check FluxWeightedAverage
        cs[CONF_CROSS_SECTION].setDefaults(
            cs[CONF_XS_BLOCK_REPRESENTATION],
            cs[CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION],
        )
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].blockRepresentation, "FluxWeightedAverage")

        # Check Average
        cs[CONF_XS_BLOCK_REPRESENTATION] = "Average"
        cs[CONF_CROSS_SECTION]["AA"] = XSModelingOptions("AA", xsFileLocation=[])
        cs[CONF_CROSS_SECTION].setDefaults(
            cs[CONF_XS_BLOCK_REPRESENTATION],
            cs[CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION],
        )
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].blockRepresentation, "Average")

        # Check Median
        cs[CONF_XS_BLOCK_REPRESENTATION] = "Average"
        cs[CONF_CROSS_SECTION]["AA"] = XSModelingOptions("AA", xsFileLocation=[], blockRepresentation="Median")
        cs[CONF_CROSS_SECTION].setDefaults(
            cs[CONF_XS_BLOCK_REPRESENTATION],
            cs[CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION],
        )
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].blockRepresentation, "Median")

    def test_xsSettingsSetDefault(self):
        """Test the configuration options of the ``setDefaults`` method."""
        cs = caseSettings.Settings()
        cs[CONF_XS_BLOCK_REPRESENTATION] = "FluxWeightedAverage"
        cs[CONF_CROSS_SECTION].setDefaults(blockRepresentation=cs[CONF_XS_BLOCK_REPRESENTATION], validBlockTypes=None)
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].validBlockTypes, None)

        cs[CONF_CROSS_SECTION].setDefaults(blockRepresentation=cs[CONF_XS_BLOCK_REPRESENTATION], validBlockTypes=True)
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].validBlockTypes, None)

        cs[CONF_CROSS_SECTION].setDefaults(blockRepresentation=cs[CONF_XS_BLOCK_REPRESENTATION], validBlockTypes=False)
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].validBlockTypes, ["fuel"])

        cs[CONF_CROSS_SECTION].setDefaults(
            blockRepresentation=cs[CONF_XS_BLOCK_REPRESENTATION],
            validBlockTypes=["control", "fuel", "plenum"],
        )
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].validBlockTypes, ["control", "fuel", "plenum"])
