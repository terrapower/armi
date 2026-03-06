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

"""Unit tests for the composition and material type data in the material data file schema."""

import os
import unittest

from jsonschema.exceptions import ValidationError

from armi.matProps.dataSchema.dataSchemaValidator import validateDir, validateFile

THIS_DIR = os.path.dirname(__file__)
INPUTS_DIR = os.path.join(THIS_DIR, "inputs")


class TestMaterialType(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cwd = os.getcwd()
        os.chdir(INPUTS_DIR)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.cwd)

    def test_materialTypeFail(self):
        """This contains an incorrect material type, not included in the enum in the 'material type' schema."""
        with self.assertRaises(ValidationError):
            validateFile("materialTypeFail.yaml")


class TestValidateDir(unittest.TestCase):
    def test_validateDir(self):
        # The validation will complain that these file formats are "TESTS" and not "1.0".
        with self.assertRaises(ValidationError):
            validateDir(os.path.join(THIS_DIR, "..", "..", "tests", "testDir1"))


class TestComposition(unittest.TestCase):
    """Class for testing the composition related data in the material data file schema."""

    @classmethod
    def setUpClass(cls):
        cls.cwd = os.getcwd()
        os.chdir(INPUTS_DIR)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.cwd)

    def test_compositionBalanceTest(self):
        """
        This YAML contains the key "Fe:"" with the incorrect string "test" that will be caught because it is not the
        only allowed string "balance".
        """
        with self.assertRaises(ValidationError):
            validateFile("compositionBalanceTest.yaml")

    def test_compositionKeyFail(self):
        """This YAML has an incorrect key, test, that does not follow the regexes in the schema."""
        with self.assertRaises(ValidationError):
            validateFile("compositionKeyFail.yaml")

    def test_compositionLimitTestMax(self):
        """This YAML has a value out of range in the "C" key of composition. The value purposely goes over 100."""
        with self.assertRaises(ValidationError):
            validateFile("compositionLimitTestMax.yaml")

    def test_compositionLimitTestMin(self):
        """This YAML has a value out of range in the "C" key of composition. The value purposely goes under 0."""
        with self.assertRaises(ValidationError):
            validateFile("compositionLimitTestMin.yaml")

    def test_referenceTypeTest(self):
        """This YAML contains an incorrect type for the "ref" key in references."""
        with self.assertRaises(ValidationError):
            validateFile("referenceTypeTest.yaml")

    def test_referenceTypeTest2(self):
        """This YAML contains an incorrect type for the "refType" key in references."""
        with self.assertRaises(ValidationError):
            validateFile("referenceTypeTest2.yaml")
