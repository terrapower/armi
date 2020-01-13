# Copyright 2020 TerraPower, LLC
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

"""
Tests for functions in textProcessors.py
"""
import os
import pathlib
import unittest

import ruamel
from ruamel import yaml

from armi.utils import textProcessors
from armi.utils import pathTools

THIS_DIR = pathTools.armiAbsDirFromName(__name__)
RES_DIR = os.path.join(THIS_DIR, "resources")


class YamlIncludeTest(unittest.TestCase):
    def testIncludeCtor(self):
        with open(os.path.join(RES_DIR, "root.yaml")) as f:
            resolved = textProcessors.resolveMarkupInclusions(
                f, root=pathlib.Path(RES_DIR)
            )

        # Make sure that there aren't any !include tags left in the converted stream
        anyIncludes = False
        for l in resolved:
            if "!include" in l:
                anyIncludes = True
        self.assertFalse(anyIncludes)

        # Re-parse the resolved stream, make sure that we included the stuff that we
        # want
        resolved.seek(0)
        data = ruamel.yaml.YAML().load(resolved)
        self.assertEqual(data["billy"]["children"][1]["full_name"], "Jennifer Person")
        self.assertEqual(
            data["billy"]["children"][1]["children"][0]["full_name"], "Elizabeth Person"
        )

        # Check that we preserved other round-trip data
        resolved.seek(0)
        commentFound = False
        anchorFound = False
        for l in resolved:
            if l.strip() == "# some comment in includeA":
                commentFound = True
            if "*bobby" in l:
                anchorFound = True

        self.assertTrue(commentFound)
        self.assertTrue(anchorFound)

    def testFindIncludes(self):
        includes = textProcessors.findYamlInclusions(pathlib.Path(RES_DIR) / "root.yaml")
        for i, _mark in includes:
            self.assertTrue(i.exists())

        self.assertEqual(len(includes), 2)


if __name__ == "__main__":
    unittest.main()
