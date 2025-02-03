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

"""Unit tests for the neutronics plugin."""
import io
import unittest

from ruamel.yaml import YAML

from armi import getPluginManagerOrFail, settings, tests
from armi.physics import neutronics
from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.physics.neutronics.settings import (
    CONF_BOUNDARIES,
    CONF_DPA_XS_SET,
    CONF_GEN_XS,
    CONF_GLOBAL_FLUX_ACTIVE,
    CONF_GRID_PLATE_DPA_XS_SET,
    CONF_GROUP_STRUCTURE,
    CONF_INNERS_,
    CONF_LATTICE_PHYSICS_FREQUENCY,
    CONF_NEUTRONICS_KERNEL,
    CONF_OUTERS_,
    getNeutronicsSettingValidators,
)
from armi.settings import caseSettings, settingsValidation
from armi.settings.fwSettings.globalSettings import CONF_RUN_TYPE
from armi.tests import TEST_ROOT
from armi.tests.test_plugins import TestPlugin
from armi.utils import directoryChangers

XS_EXAMPLE = """AA:
    geometry: 0D
    criticalBuckling: true
    blockRepresentation: Median
BA:
    geometry: 1D slab
    blockRepresentation: Median
"""


class TestNeutronicsPlugin(TestPlugin):
    plugin = neutronics.NeutronicsPlugin

    def setUp(self):
        self.td = directoryChangers.TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    def test_customSettingObjectIO(self):
        """Check specialized settings can build objects as values and write."""
        cs = caseSettings.Settings()
        yaml = YAML()
        inp = yaml.load(io.StringIO(XS_EXAMPLE))
        cs[CONF_CROSS_SECTION] = inp
        self.assertEqual(cs[CONF_CROSS_SECTION]["AA"].geometry, "0D")
        fname = "test_setting_obj_io_.yaml"
        cs.writeToYamlFile(fname)
        outText = open(fname, "r").read()
        self.assertIn("geometry: 0D", outText)

    def test_customSettingRoundTrip(self):
        """Check specialized settings can go back and forth."""
        cs = caseSettings.Settings()
        yaml = YAML()
        inp = yaml.load(io.StringIO(XS_EXAMPLE))
        cs[CONF_CROSS_SECTION] = inp
        cs[CONF_CROSS_SECTION] = cs[CONF_CROSS_SECTION]
        fname = "test_setting_obj_io_round.yaml"
        cs.writeToYamlFile(fname)
        outText = open(fname, "r").read()
        self.assertIn("geometry: 0D", outText)
        self.assertIn("geometry: 1D", outText)

    def test_neutronicsSettingsLoaded(self):
        """Check that various special neutronics-specifics settings are loaded."""
        cs = caseSettings.Settings()

        self.assertIn(CONF_INNERS_, cs)
        self.assertIn(CONF_OUTERS_, cs)
        self.assertIn(CONF_NEUTRONICS_KERNEL, cs)


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

    @staticmethod
    def __getModifiedSettings(customSettings):
        cs = settings.Settings()

        newSettings = {}
        for key, val in customSettings.items():
            newSettings[key] = val

        return cs.modified(newSettings=newSettings)

    def test_kineticsParameterAssignment(self):
        """Test that the delayed neutron fraction and precursor decay constants are applied from settings."""
        r = tests.getEmptyHexReactor()
        self.assertIsNone(r.core.p.beta)
        self.assertIsNone(r.core.p.betaComponents)
        self.assertIsNone(r.core.p.betaDecayConstants)

        # Test that the group-wise beta and decay constants are assigned
        # together given that they are the same length.
        r = tests.getEmptyHexReactor()
        cs = self.__getModifiedSettings(
            customSettings={
                "beta": [0.0] * 6,
                "decayConstants": [1.0] * 6,
            }
        )
        dbLoad = False
        getPluginManagerOrFail().hook.onProcessCoreLoading(
            core=r.core, cs=cs, dbLoad=dbLoad
        )
        r.core.setOptionsFromCs(cs)
        self.assertEqual(r.core.p.beta, sum(cs["beta"]))
        self.assertListEqual(list(r.core.p.betaComponents), cs["beta"])
        self.assertListEqual(list(r.core.p.betaDecayConstants), cs["decayConstants"])

        # Test the assignment of total beta as a float
        r = tests.getEmptyHexReactor()
        cs = self.__getModifiedSettings(
            customSettings={"beta": 0.00670},
        )
        getPluginManagerOrFail().hook.onProcessCoreLoading(
            core=r.core, cs=cs, dbLoad=dbLoad
        )
        self.assertEqual(r.core.p.beta, cs["beta"])
        self.assertIsNone(r.core.p.betaComponents)
        self.assertIsNone(r.core.p.betaDecayConstants)

        # Test that nothing is assigned if the beta is specified as a list
        # without a corresponding decay constants list.
        r = tests.getEmptyHexReactor()
        cs = self.__getModifiedSettings(
            customSettings={
                "beta": [0.0] * 6,
            },
        )
        getPluginManagerOrFail().hook.onProcessCoreLoading(
            core=r.core, cs=cs, dbLoad=dbLoad
        )
        self.assertIsNone(r.core.p.beta)
        self.assertIsNone(r.core.p.betaComponents)
        self.assertIsNone(r.core.p.betaDecayConstants)

        # Test that 1 group beta components and decay constants can be assigned.
        # Since beta is a list, ensure that it's assigned to the `betaComponents`
        # parameter.
        r = tests.getEmptyHexReactor()
        cs = self.__getModifiedSettings(
            customSettings={"beta": [0.0], "decayConstants": [1.0]},
        )
        getPluginManagerOrFail().hook.onProcessCoreLoading(
            core=r.core, cs=cs, dbLoad=dbLoad
        )
        self.assertEqual(r.core.p.beta, sum(cs["beta"]))
        self.assertListEqual(list(r.core.p.betaComponents), cs["beta"])
        self.assertListEqual(list(r.core.p.betaDecayConstants), cs["decayConstants"])

        # Test that decay constants are not assigned without a corresponding
        # group-wise beta input.
        r = tests.getEmptyHexReactor()
        cs = self.__getModifiedSettings(
            customSettings={"decayConstants": [1.0] * 6},
        )
        getPluginManagerOrFail().hook.onProcessCoreLoading(
            core=r.core, cs=cs, dbLoad=dbLoad
        )
        self.assertIsNone(r.core.p.beta)
        self.assertIsNone(r.core.p.betaComponents)
        self.assertIsNone(r.core.p.betaDecayConstants)

        # Test that decay constants are not assigned without a corresponding
        # group-wise beta input. This also demonstrates that the total beta
        # is still assigned.
        r = tests.getEmptyHexReactor()
        cs = self.__getModifiedSettings(
            customSettings={"decayConstants": [1.0] * 6, "beta": 0.0},
        )
        getPluginManagerOrFail().hook.onProcessCoreLoading(
            core=r.core, cs=cs, dbLoad=dbLoad
        )
        self.assertEqual(r.core.p.beta, cs["beta"])
        self.assertIsNone(r.core.p.betaComponents)
        self.assertIsNone(r.core.p.betaDecayConstants)

        # Test the demonstrates that None values are acceptable
        # and that nothing is assigned.
        r = tests.getEmptyHexReactor()
        cs = self.__getModifiedSettings(
            customSettings={"decayConstants": None, "beta": None},
        )
        getPluginManagerOrFail().hook.onProcessCoreLoading(
            core=r.core, cs=cs, dbLoad=dbLoad
        )
        self.assertEqual(r.core.p.beta, cs["beta"])
        self.assertIsNone(r.core.p.betaComponents)
        self.assertIsNone(r.core.p.betaDecayConstants)

        # Test that an error is raised if the decay constants
        # and group-wise beta are inconsistent sizes
        with self.assertRaises(ValueError):
            r = tests.getEmptyHexReactor()
            cs = self.__getModifiedSettings(
                customSettings={"decayConstants": [1.0] * 6, "beta": [0.0]},
            )
            getPluginManagerOrFail().hook.onProcessCoreLoading(
                core=r.core, cs=cs, dbLoad=dbLoad
            )

        # Test that an error is raised if the decay constants
        # and group-wise beta are inconsistent sizes
        with self.assertRaises(ValueError):
            r = tests.getEmptyHexReactor()
            cs = self.__getModifiedSettings(
                customSettings={"decayConstants": [1.0] * 6, "beta": [0.0] * 5},
            )
            getPluginManagerOrFail().hook.onProcessCoreLoading(
                core=r.core, cs=cs, dbLoad=dbLoad
            )

    @staticmethod
    def __autoCorrectAllQueries(settingsValidator):
        """Force-Correct (resolve() to "YES") all queries in a Settings Validator."""
        for query in settingsValidator:
            try:
                query.correction()
            except FileNotFoundError:
                # to make testing easier, let's ignore settings that require input files
                pass

    def test_neutronicsSettingsValidators(self):
        # grab the neutronics validators
        cs = settings.Settings()
        inspector = settingsValidation.Inspector(cs)
        sv = getNeutronicsSettingValidators(inspector)
        self.assertEqual(len(sv), 8)

        # Test the Query: boundaries are now "Extrapolated", not "Generalized"
        cs = cs.modified(newSettings={CONF_BOUNDARIES: "Generalized"})
        inspector = settingsValidation.Inspector(cs)
        sv = getNeutronicsSettingValidators(inspector)

        self.__autoCorrectAllQueries(sv)
        self.assertEqual(inspector.cs[CONF_BOUNDARIES], "Extrapolated")

        # Test the Query: genXS are no longer True/False
        cs = cs.modified(newSettings={CONF_GEN_XS: "True"})
        inspector = settingsValidation.Inspector(cs)
        sv = getNeutronicsSettingValidators(inspector)

        self.__autoCorrectAllQueries(sv)
        self.assertEqual(inspector.cs[CONF_GEN_XS], "Neutron")

        cs = cs.modified(newSettings={CONF_GEN_XS: "False"})
        inspector = settingsValidation.Inspector(cs)
        sv = getNeutronicsSettingValidators(inspector)

        self.__autoCorrectAllQueries(sv)
        self.assertEqual(inspector.cs[CONF_GEN_XS], "")

        # Test the Query: CONF_GLOBAL_FLUX_ACTIVE are no longer True/False
        cs = cs.modified(newSettings={CONF_GLOBAL_FLUX_ACTIVE: "True"})
        inspector = settingsValidation.Inspector(cs)
        sv = getNeutronicsSettingValidators(inspector)

        self.__autoCorrectAllQueries(sv)
        self.assertEqual(inspector.cs[CONF_GLOBAL_FLUX_ACTIVE], "Neutron")

        cs = cs.modified(newSettings={CONF_GLOBAL_FLUX_ACTIVE: "False"})
        inspector = settingsValidation.Inspector(cs)
        sv = getNeutronicsSettingValidators(inspector)

        self.__autoCorrectAllQueries(sv)
        self.assertEqual(inspector.cs[CONF_GLOBAL_FLUX_ACTIVE], "")

        # Test the Query: try to migrate the Group Structure name
        cs = cs.modified(newSettings={CONF_GROUP_STRUCTURE: "armi45"})
        inspector = settingsValidation.Inspector(cs)
        sv = getNeutronicsSettingValidators(inspector)

        self.__autoCorrectAllQueries(sv)
        self.assertEqual(inspector.cs[CONF_GROUP_STRUCTURE], "ARMI45")

        cs = cs.modified(newSettings={CONF_GROUP_STRUCTURE: "bad_value"})
        inspector = settingsValidation.Inspector(cs)
        sv = getNeutronicsSettingValidators(inspector)

        self.__autoCorrectAllQueries(sv)
        self.assertEqual(inspector.cs[CONF_GROUP_STRUCTURE], "ANL33")

        # Test the Query: migrating some common shortened names for dpa XS sets
        cs = cs.modified(newSettings={CONF_DPA_XS_SET: "dpaHT9_33"})
        inspector = settingsValidation.Inspector(cs)
        sv = getNeutronicsSettingValidators(inspector)

        self.__autoCorrectAllQueries(sv)
        self.assertEqual(inspector.cs[CONF_DPA_XS_SET], "dpaHT9_ANL33_TwrBol")

        cs = cs.modified(newSettings={CONF_GRID_PLATE_DPA_XS_SET: "dpa_SS316"})
        inspector = settingsValidation.Inspector(cs)
        sv = getNeutronicsSettingValidators(inspector)

        self.__autoCorrectAllQueries(sv)
        self.assertEqual(
            inspector.cs[CONF_GRID_PLATE_DPA_XS_SET], "dpaSS316_ANL33_TwrBol"
        )

        cs = cs.modified(
            newSettings={
                CONF_RUN_TYPE: "Snapshots",
                CONF_LATTICE_PHYSICS_FREQUENCY: "BOC",
            }
        )
        inspector = settingsValidation.Inspector(cs)
        sv = getNeutronicsSettingValidators(inspector)

        self.__autoCorrectAllQueries(sv)
        self.assertEqual(
            inspector.cs[CONF_LATTICE_PHYSICS_FREQUENCY], "firstCoupledIteration"
        )
