# Copyright 2026 TerraPower, LLC
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

"""Unit tests for the parameter related data in the material data file schema."""

import os
import unittest

from jsonschema.exceptions import ValidationError

from armi.matProps.dataSchema.dataSchemaValidator import validateFile

THIS_DIR = os.path.dirname(__file__)
INPUTS_DIR = os.path.join(THIS_DIR, "inputs")


class TestParameter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cwd = os.getcwd()
        os.chdir(INPUTS_DIR)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.cwd)

    def test_maxDegreesCTest(self):
        """
        This YAML contains an incorrect value for "max degrees C". Only numbers are allowed, so the string "test" will
        be caught.
        """
        with self.assertRaises(ValidationError):
            validateFile("maxDegreesCTest.yaml")

    def test_minDegreeCTest(self):
        """
        This YAML contains an incorrect value for "min degrees C". Only numbers are allowed, so the string "test" will
        be caught.
        """
        with self.assertRaises(ValidationError):
            validateFile("minDegreeCTest.yaml")

    def test_missingFxnTypePW(self):
        """This YAML is missing "function type" inside the piecewise function."""
        with self.assertRaises(ValidationError):
            validateFile("missingFxnTypePW.yaml")

    def test_missingMaxDCPW(self):
        """This YAML is missing "max degrees C" inside the piecewise function."""
        with self.assertRaises(ValidationError):
            validateFile("missingMaxDCPW.yaml")

    def test_missingMinDCPW(self):
        """This YAML is missing "max degrees C" inside the piecewise function."""
        with self.assertRaises(ValidationError):
            validateFile("missingMinDCPW.yaml")

    def test_missingParamFxnType(self):
        """This YAML is missing the "function type" key."""
        with self.assertRaises(ValidationError):
            validateFile("missingParamFxnType.yaml")

    def test_missingParamMaxDC(self):
        """This YAML is missing the "max degrees C" key."""
        with self.assertRaises(ValidationError):
            validateFile("missingParamMaxDC.yaml")

    def test_missingParamMinDC(self):
        """This YAML is missing the "min degrees C" key."""
        with self.assertRaises(ValidationError):
            validateFile("missingParamMinDC.yaml")

    def test_missingRefProperty(self):
        """This YAML is missing references for a material property."""
        with self.assertRaises(ValidationError):
            validateFile("missingRefProperty.yaml")

    def test_missingTabData(self):
        """This file is missing tabulated data for a material property."""
        with self.assertRaises(ValidationError):
            validateFile("missingTabData.yaml")

    def test_missingTabDataPW(self):
        """This YAML is missing tabulated data in the piecewise function."""
        with self.assertRaises(ValidationError):
            validateFile("missingTabDataPW.yaml")

    def test_polyBadKeys(self):
        """This YAML has bad coefficient values for a polynomial function."""
        with self.assertRaises(ValidationError):
            validateFile("polyBadKeys.yaml")

    def test_polyMissingCoef(self):
        """This file is missing the "coefficients" property of the polynomial function."""
        with self.assertRaises(ValidationError):
            validateFile("polyMissingCoef.yaml")

    def test_unidentifiedFxnTest(self):
        """This YAML contains a string that is not in the enum for the "function type" string."""
        with self.assertRaises(ValidationError):
            validateFile("unidentifiedFxnTest.yaml")

    def test_loadExampleFile(self):
        """Loads the example file in the data_schema directory to make sure it loads without raising an exception."""
        validateFile("example.yaml")

        # The validateFile function will raise an error if anything goes wrong. So if it success, and returns nothing,
        # we do not have much to test. The function either raises an error or it does not.
        # This is a good test file, so no error should be raised.
        self.assertTrue(True)
