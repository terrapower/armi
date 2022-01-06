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
"""Test that the code examples in the docs are valid"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access

import os
import unittest
import doctest

from armi import DOC


class TestDocs(unittest.TestCase):
    @unittest.skip("Doc code examples need some love before this is going to work.")
    def test_docsHaveWorkingCodeExamples(self):
        for root, _dirs, files in os.walk(DOC):
            for f in files:
                fullpath = os.path.join(root, f)

                base, xtn = os.path.splitext(fullpath)
                if xtn != ".rst" or ".armidocs" in base:
                    # skip non rst and auto-generated rst
                    continue

                try:
                    doctest.testfile(fullpath)
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
