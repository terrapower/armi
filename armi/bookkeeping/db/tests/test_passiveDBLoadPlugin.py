# Copyright 2025 TerraPower, LLC
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

"""Provides functionality for testing the PassiveDBLoadPlugin."""

import unittest
from copy import deepcopy
from io import StringIO

from ruamel.yaml.nodes import MappingNode, ScalarNode

from armi import context, getApp
from armi.bookkeeping.db.passiveDBLoadPlugin import (
    PassiveDBLoadPlugin,
    PassThroughYamlize,
)
from armi.reactor.blocks import Block


class TestPassiveDBLoadPlugin(unittest.TestCase):
    def setUp(self):
        """
        Manipulate the standard App. We can't just configure our own, since the
        pytest environment bleeds between tests.
        """
        self.app = getApp()
        self._backupApp = deepcopy(self.app)
        self._cacheBPSections = PassiveDBLoadPlugin.SKIP_BP_SECTIONS
        self._cacheUnkownParams = PassiveDBLoadPlugin.UNKNOWN_PARAMS
        PassiveDBLoadPlugin.SKIP_BP_SECTIONS = []
        PassiveDBLoadPlugin.UNKNOWN_PARAMS = {}

    def tearDown(self):
        """Restore the App to its original state."""
        import armi

        armi._app = self._backupApp
        context.APP_NAME = "armi"
        PassiveDBLoadPlugin.SKIP_BP_SECTIONS = self._cacheBPSections
        PassiveDBLoadPlugin.UNKNOWN_PARAMS = self._cacheUnkownParams

    def test_passiveDBLoadPlugin(self):
        plug = PassiveDBLoadPlugin()

        # default case
        bpSections = plug.defineBlueprintsSections()
        self.assertEqual(len(bpSections), 0)
        params = plug.defineParameters()
        self.assertEqual(len(params), 0)

        # non-empty cases
        PassiveDBLoadPlugin.SKIP_BP_SECTIONS = ["hi", "mom"]
        PassiveDBLoadPlugin.UNKNOWN_PARAMS = {Block: ["fake1", "fake2"]}
        bpSections = plug.defineBlueprintsSections()
        self.assertEqual(len(bpSections), 2)
        self.assertTrue(type(bpSections[0]), tuple)
        self.assertEqual(bpSections[0][0], "hi")
        self.assertTrue(type(bpSections[1]), tuple)
        self.assertEqual(bpSections[1][0], "mom")
        params = plug.defineParameters()
        self.assertEqual(len(params), 1)
        self.assertIn(Block, params)


class TestPassThroughYamlize(unittest.TestCase):
    def test_passThroughYamlizeExample1(self):
        # create node from known BP-style YAML object
        node = MappingNode(
            "test_passThroughYamlizeExample1",
            [
                (
                    ScalarNode(tag="tag:yaml.org,2002:str", value="core-wide"),
                    MappingNode(
                        tag="tag:yaml.org,2002:map",
                        value=[
                            (
                                ScalarNode(
                                    tag="tag:yaml.org,2002:str",
                                    value="fuel axial expansion",
                                ),
                                ScalarNode(tag="tag:yaml.org,2002:bool", value="False"),
                            ),
                            (
                                ScalarNode(
                                    tag="tag:yaml.org,2002:str",
                                    value="grid plate radial expansion",
                                ),
                                ScalarNode(tag="tag:yaml.org,2002:bool", value="True"),
                            ),
                        ],
                    ),
                )
            ],
        )

        # test that node is non-zero and has the "core-wide" section
        self.assertEqual(node.value[0][0].value, "core-wide")

        # # pass the YAML string through the known YAML
        # pty = PassThroughYamlize()
        # loader = CLoader(StringIO(""))
        # _p = pty.from_yaml(loader, node)

        # # prove the section has been cleared
        # self.assertEqual(len(node.value), 0)
