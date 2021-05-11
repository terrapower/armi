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
import os

from ruamel.yaml import YAML
import voluptuous as vol

from armi.tests.test_plugins import TestPlugin
from armi.physics import neutronics
from armi.settings import caseSettings
from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.utils import directoryChangers
from armi import tests
from armi.tests import TEST_ROOT
from armi import settings
import armi

XS_EXAMPLE = """AA:
    geometry: 0D
    criticalBuckling: true
    blockRepresentation: Median
BA:
    geometry: 1D slab
    blockRepresentation: Median
"""


class Test_NeutronicsPlugin(TestPlugin):
    plugin = neutronics.NeutronicsPlugin

    def test_customSettingObjectIO(self):
        """Check specialized settings can build objects as values and write."""
        cs = caseSettings.Settings()
        yaml = YAML()
        inp = yaml.load(io.StringIO(XS_EXAMPLE))
        cs[CONF_CROSS_SECTION] = inp
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].geometry, "0D")
        fname = "test_setting_obj_io_.yaml"
        cs.writeToYamlFile(fname)
        os.remove(fname)

    def test_customSettingRoundTrip(self):
        """Check specialized settings can go back and forth."""
        cs = caseSettings.Settings()
        yaml = YAML()
        inp = yaml.load(io.StringIO(XS_EXAMPLE))
        cs[CONF_CROSS_SECTION] = inp
        cs[CONF_CROSS_SECTION] = cs[CONF_CROSS_SECTION]
        fname = "test_setting_obj_io_round.yaml"
        cs.writeToYamlFile(fname)
        os.remove(fname)


class NeutronicsReactorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # prepare the input files. This is important so the unit tests run from wherever
        # they need to run from.
        cls.directoryChanger = directoryChangers.DirectoryChanger(TEST_ROOT)
        cls.directoryChanger.open()

    @classmethod
    def tearDownClass(cls):
        cls.directoryChanger.close()

    def test_kineticsParameterAssignment(self):
        """Test that the delayed neutron fraction and precursor decay constants are applied from settings."""

        def _getModifiedSettings(customSettings):
            cs = settings.Settings()
            for key, val in customSettings.items():
                cs[key] = val
            return cs

        r = tests.getEmptyHexReactor()
        self.assertIsNone(r.core.p.beta)
        self.assertIsNone(r.core.p.betaComponents)
        self.assertIsNone(r.core.p.betaDecayConstants)

        # Test that the group-wise beta and decay constants are assigned
        # together given that they are the same length.
        r = tests.getEmptyHexReactor()
        cs = _getModifiedSettings(
            customSettings={
                "beta": [0.0] * 6,
                "decayConstants": [0.0] * 6,
            }
        )
        armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=r.core, cs=cs)
        r.core.setOptionsFromCs(cs)
        self.assertEqual(r.core.p.beta, sum(cs["beta"]))
        self.assertListEqual(list(r.core.p.betaComponents), cs["beta"])
        self.assertListEqual(list(r.core.p.betaDecayConstants), cs["decayConstants"])

        # Test the assignment of total beta as a float
        r = tests.getEmptyHexReactor()
        cs = _getModifiedSettings(
            customSettings={"beta": 0.00670},
        )
        armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=r.core, cs=cs)
        self.assertEqual(r.core.p.beta, cs["beta"])
        self.assertIsNone(r.core.p.betaComponents)
        self.assertIsNone(r.core.p.betaDecayConstants)

        # Test that nothing is assigned if the beta is specified as a list
        # without a corresponding decay constants list.
        r = tests.getEmptyHexReactor()
        cs = _getModifiedSettings(
            customSettings={
                "beta": [0.0] * 6,
            },
        )
        armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=r.core, cs=cs)
        self.assertIsNone(r.core.p.beta)
        self.assertIsNone(r.core.p.betaComponents)
        self.assertIsNone(r.core.p.betaDecayConstants)

        # Test that 1 group beta components and decay constants can be assigned.
        # Since beta is a list, ensure that it's assigned to the `betaComponents`
        # parameter.
        r = tests.getEmptyHexReactor()
        cs = _getModifiedSettings(
            customSettings={"beta": [0.0], "decayConstants": [0.0]},
        )
        armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=r.core, cs=cs)
        self.assertEqual(r.core.p.beta, sum(cs["beta"]))
        self.assertListEqual(list(r.core.p.betaComponents), cs["beta"])
        self.assertListEqual(list(r.core.p.betaDecayConstants), cs["decayConstants"])

        # Test that decay constants are not assigned without a corresponding
        # group-wise beta input.
        r = tests.getEmptyHexReactor()
        cs = _getModifiedSettings(
            customSettings={"decayConstants": [0.0] * 6},
        )
        armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=r.core, cs=cs)
        self.assertIsNone(r.core.p.beta)
        self.assertIsNone(r.core.p.betaComponents)
        self.assertIsNone(r.core.p.betaDecayConstants)

        # Test that decay constants are not assigned without a corresponding
        # group-wise beta input. This also demonstrates that the total beta
        # is still assigned.
        r = tests.getEmptyHexReactor()
        cs = _getModifiedSettings(
            customSettings={"decayConstants": [0.0] * 6, "beta": 0.0},
        )
        armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=r.core, cs=cs)
        self.assertEqual(r.core.p.beta, cs["beta"])
        self.assertIsNone(r.core.p.betaComponents)
        self.assertIsNone(r.core.p.betaDecayConstants)

        # Test the demonstrates that None values are acceptable
        # and that nothing is assigned.
        r = tests.getEmptyHexReactor()
        cs = _getModifiedSettings(
            customSettings={"decayConstants": None, "beta": None},
        )
        armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=r.core, cs=cs)
        self.assertEqual(r.core.p.beta, cs["beta"])
        self.assertIsNone(r.core.p.betaComponents)
        self.assertIsNone(r.core.p.betaDecayConstants)

        # Test that an error is raised if the decay constants
        # and group-wise beta are inconsistent sizes
        with self.assertRaises(ValueError):
            r = tests.getEmptyHexReactor()
            cs = _getModifiedSettings(
                customSettings={"decayConstants": [0.0] * 6, "beta": [0.0]},
            )
            armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=r.core, cs=cs)

        # Test that an error is raised if the decay constants
        # and group-wise beta are inconsistent sizes
        with self.assertRaises(ValueError):
            r = tests.getEmptyHexReactor()
            cs = _getModifiedSettings(
                customSettings={"decayConstants": [0.0] * 6, "beta": [0.0] * 5},
            )
            armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=r.core, cs=cs)

        # The following tests check the voluptuous schema definition. This
        # ensures that anything except NoneType, [float], float are not valid
        # inputs.
        with self.assertRaises(vol.AnyInvalid):
            r = tests.getEmptyHexReactor()
            cs = _getModifiedSettings(
                customSettings={"decayConstants": [1]},
            )
            armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=r.core, cs=cs)

        with self.assertRaises(vol.AnyInvalid):
            r = tests.getEmptyHexReactor()
            cs = _getModifiedSettings(
                customSettings={"beta": [1]},
            )
            armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=r.core, cs=cs)

        with self.assertRaises(vol.AnyInvalid):
            r = tests.getEmptyHexReactor()
            cs = _getModifiedSettings(
                customSettings={"beta": 1},
            )
            armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=r.core, cs=cs)

        with self.assertRaises(vol.AnyInvalid):
            r = tests.getEmptyHexReactor()
            cs = _getModifiedSettings(
                customSettings={"beta": (1, 2, 3)},
            )
            armi.getPluginManagerOrFail().hook.onProcessCoreLoading(core=r.core, cs=cs)


if __name__ == "__main__":
    unittest.main()
