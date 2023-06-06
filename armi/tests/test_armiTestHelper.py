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

"""Tests to demonstrate the test helper is functional."""
import os
import unittest

from armi.tests import ArmiTestHelper

THIS_DIR = os.path.dirname(__file__)


class TestArmiTestHelper(ArmiTestHelper):
    def setUp(self):
        self.goodFilePath = os.path.join(THIS_DIR, "goodFile" + self._testMethodName)
        self.badFilePath = os.path.join(THIS_DIR, "badFile" + self._testMethodName)
        self.BLOCK_TEXT = (
            "TerraPower aims to develop a sustainable and economic nuclear energy technology using:\n"
            "Next-generation safe, affordable, clean and secure technologies\n"
            "Advanced materials for more durable metallic fuels\n"
            "World-class leadership for dynamic reactor engineering and innovation\n"
            "Supercomputing for reliable and comprehensive modeling\n"
        )
        self.BAD_TEXT = self.BLOCK_TEXT.replace("class", "NEGATIVE")
        for path, text in zip(
            [self.goodFilePath, self.badFilePath], (self.BLOCK_TEXT, self.BAD_TEXT)
        ):
            with open(path, "w") as fileObj:
                fileObj.write(text)

    def tearDown(self):
        for path in [self.goodFilePath, self.badFilePath]:
            if os.path.exists(path):
                os.remove(path)

    def test_compareFilesSucess(self):
        self.compareFilesLineByLine(self.goodFilePath, self.goodFilePath)

    def test_compareFilesFail(self):
        self.assertRaises(
            AssertionError,
            self.compareFilesLineByLine,
            self.goodFilePath,
            self.badFilePath,
        )

    def test_compareFilesSucceedFalseNegative(self):
        self.compareFilesLineByLine(
            self.goodFilePath, self.badFilePath, falseNegList=["NEGATIVE"]
        )


if __name__ == "_main__":
    unittest.main()
