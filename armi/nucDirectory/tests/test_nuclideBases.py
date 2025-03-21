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

"""Tests for nuclideBases."""
import math
import os
import random
import unittest

from ruamel.yaml import YAML

from armi.context import RES
from armi.nucDirectory import nuclideBases
from armi.nucDirectory.tests import NUCDIRECTORY_TESTS_DEFAULT_DIR_PATH
from armi.utils.units import AVOGADROS_NUMBER, CURIE_PER_BECQUEREL, SECONDS_PER_HOUR


class TestNuclide(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nucDirectoryTestsPath = NUCDIRECTORY_TESTS_DEFAULT_DIR_PATH
        nuclideBases.destroyGlobalNuclides()
        nuclideBases.factory()
        # Ensure that the burn chain data is initialized before running these tests.
        nuclideBases.burnChainImposed = False
        with open(os.path.join(RES, "burn-chain.yaml"), "r") as burnChainStream:
            nuclideBases.imposeBurnChain(burnChainStream)

    def test_nucBases_fromNameBadNameRaisesException(self):
        with self.assertRaises(KeyError):
            nuclideBases.byName["Cat"]

    def test_nucBase_AllAbundancesAddToOne(self):
        for zz in range(1, 102):
            nuclides = nuclideBases.isotopes(zz)
            # We only process nuclides with measured masses. Some are purely theoretical, mostly over z=100
            self.assertTrue(
                len(nuclides) > 0, msg="z={} unexpectedly has no nuclides".format(zz)
            )
            total = sum([nn.abundance for nn in nuclides if nn.a > 0])
            self.assertAlmostEqual(
                any([nn.abundance > 0 for nn in nuclides]),
                total,
                delta=1e-4,
                msg="Abundance ({}) not 1.0 for nuclideBases:\n  {}"
                "".format(total, "\n  ".join(repr(nn) for nn in nuclides)),
            )

    def test_nucBases_AllLabelsAreUnique(self):
        labels = []
        for nn in nuclideBases.instances:
            self.assertTrue(
                nn.label not in labels, "Label already exists: {}".format(nn.label)
            )
            labels.append(nn.label)

    def test_nucBases_NegativeZRaisesException(self):
        for _ in range(0, 5):
            with self.assertRaises(Exception):
                nuclideBases.isotopes(random.randint(-1000, -1))

    def test_nucBases_Z295RaisesException(self):
        with self.assertRaises(Exception):
            nuclideBases.isotopes(295)

    def test_nucBases_Mc2Elementals(self):
        notElemental = [
            "LFP35",
            "LFP38",
            "LFP39",
            "LFP40",
            "LFP41",
            "DUMMY",
            "DUMP1",
            "DUMP2",
            "LREGN",
        ]
        for lump in nuclideBases.where(
            lambda nn: isinstance(nn, nuclideBases.LumpNuclideBase)
        ):
            if lump.name in notElemental:
                self.assertIsInstance(lump, nuclideBases.LumpNuclideBase)
            else:
                self.assertIsInstance(lump, nuclideBases.NaturalNuclideBase)

    def test_LumpNucBaseGetNatIsotopDoesNotFail(self):
        for nuc in nuclideBases.where(
            lambda nn: isinstance(nn, nuclideBases.LumpNuclideBase) and nn.z == 0
        ):
            self.assertEqual(0, len(list(nuc.getNaturalIsotopics())), nuc)

    def test_NaturalNuclideBase_getNatrualIsotpics(self):
        for nuc in nuclideBases.where(
            lambda nn: isinstance(nn, nuclideBases.NaturalNuclideBase)
        ):
            numNaturals = len(list(nuc.getNaturalIsotopics()))
            self.assertGreaterEqual(len(nuc.element.nuclides) - 1, numNaturals)

    def test_nucBases_singleFailsWithMultipleMatches(self):
        with self.assertRaises(Exception):
            nuclideBases.single(lambda nuc: nuc.z == 92)

    def test_nucBases_singleFailsWithNoMatches(self):
        with self.assertRaises(Exception):
            nuclideBases.single(lambda nuc: nuc.z == 1000)

    def test_nucBases_singleIsPrettySpecific(self):
        u235 = nuclideBases.single(lambda nuc: nuc.name == "U235")
        self.assertEqual(235, u235.a)
        self.assertEqual(92, u235.z)

    def test_natNucStomicWgtIsAvgOfNatIsotopes(self):
        for natNuk in nuclideBases.where(
            lambda nn: isinstance(nn, nuclideBases.NaturalNuclideBase)
        ):
            atomicMass = 0.0
            for natIso in natNuk.getNaturalIsotopics():
                atomicMass += natIso.abundance * natIso.weight
            self.assertAlmostEqual(atomicMass, natNuk.weight, delta=0.000001)

    def test_nucBasesLabelAndNameCollsAreForSameNuc(self):
        """The name and labels for correct for nuclides.

        .. test:: Validate the name, label, and DB name are accessible for nuclides.
            :id: T_ARMI_ND_ISOTOPES0
            :tests: R_ARMI_ND_ISOTOPES
        """
        count = 0
        for nuc in nuclideBases.where(lambda nn: nn.name == nn.label):
            count += 1
            self.assertEqual(nuc, nuclideBases.byName[nuc.name])
            self.assertEqual(nuc, nuclideBases.byDBName[nuc.getDatabaseName()])
            self.assertEqual(nuc, nuclideBases.byLabel[nuc.label])
        self.assertGreater(count, 10)

    def test_nucBases_imposeBurnChainDecayBulkStats(self):
        """Test must be updated manually when burn chain is modified."""
        decayers = list(nuclideBases.where(lambda nn: len(nn.decays) > 0))
        self.assertTrue(decayers)
        for nuc in decayers:
            if nuc.name in [
                "U238",
                "PU240",
                "PU242",
                "CM242",
                "CM244",
                "CM246",
                "CF250",
                "CF252",
            ]:
                continue
            self.assertAlmostEqual(1.0, sum(dd.branch for dd in nuc.decays))

    def test_nucBasesImposeBurnChainTransmBulkStats(self):
        """
        Make sure all branches are equal to 1 for every transmutation type.

        Exception: We allow 3e-4 threshold to account for ternary fissions,
        which are usually < 2e-4 per fission.
        """
        trasmuters = nuclideBases.where(lambda nn: len(nn.trans) > 0)
        self.assertTrue(trasmuters)
        for nuc in trasmuters:
            expected = len(set(tt.type for tt in nuc.trans))
            self.assertTrue(all(0.0 <= tt.branch <= 1.0 for tt in nuc.trans))
            actual = sum(tt.branch for tt in nuc.trans)
            self.assertAlmostEqual(
                expected,
                actual,
                msg="{0} has {1} transmutation but the branches add up to {2}"
                "".format(nuc, expected, actual),
                delta=3e-4,
            )  # ternary fission

    def test_nucBases_imposeBurn_nuSF(self):
        """Test the nuclide data from file (specifically neutrons / sponaneous fission).

        .. test:: Test that nuclide data was read from file instead of code.
            :id: T_ARMI_ND_DATA0
            :tests: R_ARMI_ND_DATA
        """
        actual = {
            nn.name: nn.nuSF for nn in nuclideBases.where(lambda nn: nn.nuSF > 0.0)
        }
        expected = {
            "CM248": 3.1610,
            "BK249": 3.4000,
            "CF249": 3.4000,
            "CF250": 3.5200,
            "CF252": 3.7676,
            "U232": 1.710000,
            "U234": 1.8000,
            "U235": 1.8700,
            "U236": 1.900,
            "U238": 2.000,
            "PU236": 2.1200,
            "PU238": 2.2100,
            "PU239": 2.3200,
            "PU240": 2.1510,
            "PU242": 2.1410,
            "CM242": 2.5280,
            "CM243": 0.0000,
            "CM244": 2.6875,
            "CM245": 0.0000,
            "CM246": 2.9480,
            "TH230": 1.390000,
            "TH232": 1.5,
            "NP237": 2.05,
            "PA231": 1.710000,
            "PU241": 2.25,
            "PU244": 2.290000,
            "U233": 1.76,
            "AM241": 2.5,
            "AM242M": 2.56,
            "AM243": 2.61,
            "ES253": 4.700000,
        }
        for key, val in actual.items():
            self.assertEqual(val, expected[key])

    def test_nucBases_databaseNamesStartWith_n(self):
        for nb in nuclideBases.instances:
            self.assertEqual("n", nb.getDatabaseName()[0])

    def test_nucBases_AllDatabaseNamesAreUnique(self):
        self.assertEqual(
            len(nuclideBases.instances),
            len(set(nb.getDatabaseName() for nb in nuclideBases.instances)),
        )

    def test_nucBases_Am242m(self):
        """Test the correct am242g and am242m abbreviations are supported.

        .. test:: Specifically test for Am242 and Am242g because it is a special case.
            :id: T_ARMI_ND_ISOTOPES1
            :tests: R_ARMI_ND_ISOTOPES
        """
        am242m = nuclideBases.byName["AM242"]
        self.assertEqual(am242m, nuclideBases.byName["AM242M"])
        self.assertEqual("nAm242m", am242m.getDatabaseName())
        self.assertEqual(am242m, nuclideBases.byDBName["nAm242"])
        self.assertAlmostEqual(am242m.weight, 242.059601666)

        am242g = nuclideBases.byName["AM242G"]
        self.assertEqual(am242g, nuclideBases.byName["AM242G"])
        self.assertEqual("nAm242g", am242g.getDatabaseName())
        self.assertEqual(am242g, nuclideBases.byDBName["nAm242g"])

    def test_nucBases_isHeavyMetal(self):
        for nb in nuclideBases.where(lambda nn: nn.z <= 89):
            self.assertFalse(nb.isHeavyMetal())
        for nb in nuclideBases.where(lambda nn: nn.z > 89):
            if isinstance(
                nb, (nuclideBases.DummyNuclideBase, nuclideBases.LumpNuclideBase)
            ):
                self.assertFalse(nb.isHeavyMetal())
            else:
                self.assertTrue(nb.isHeavyMetal())

    def test_getDecay(self):
        nb = list(nuclideBases.where(lambda nn: nn.z == 89))[0]
        # This test is a bit boring, because the test nuclide library is a bit boring.
        self.assertIsNone(nb.getDecay("sf"))

    def test_getEndfMatNum(self):
        """Test get nuclides by name.

        .. test:: Test get nuclides by name.
            :id: T_ARMI_ND_ISOTOPES2
            :tests: R_ARMI_ND_ISOTOPES
        """
        self.assertEqual(nuclideBases.byName["U235"].getEndfMatNum(), "9228")
        self.assertEqual(nuclideBases.byName["U238"].getEndfMatNum(), "9237")
        self.assertEqual(nuclideBases.byName["PU239"].getEndfMatNum(), "9437")
        self.assertEqual(nuclideBases.byName["TC99"].getEndfMatNum(), "4325")
        self.assertEqual(nuclideBases.byName["AM242"].getEndfMatNum(), "9547")  # meta 1
        self.assertEqual(nuclideBases.byName["CF252"].getEndfMatNum(), "9861")
        self.assertEqual(nuclideBases.byName["NP237"].getEndfMatNum(), "9346")
        self.assertEqual(nuclideBases.byName["PM151"].getEndfMatNum(), "6161")
        self.assertEqual(nuclideBases.byName["PA231"].getEndfMatNum(), "9131")

    def test_NonMc2Nuclide(self):
        """Make sure nuclides that aren't in MC2 still get nuclide bases."""
        nuc = nuclideBases.byName["YB154"]
        self.assertEqual(nuc.a, 154)

    def test_kryptonDecayConstants(self):
        """Tests that the nuclides data contains the expected decay constants."""
        # hand calculated reference data includes stable isotopes, radioactive
        # isotopes, metastable isotopes and exercises metastable minimum halflife
        REF_KR_DECAY_CONSTANTS = [
            ("KR69", 24.755256448569472),
            ("KR70", 17.3286795139986),
            ("KR71", 6.93147180559945),
            ("KR72", 0.04053492283976288),
            ("KR73", 0.0253900066139174),
            ("KR74", 0.0010045611312463),
            ("KR75", 0.00251140282811574),
            ("KR76", 0.0000130095191546536),
            ("KR77", 0.000162139691359051),
            ("KR78", 0),
            ("KR79", 5.49488822742219e-06),
            ("KR79M", 0.0138629436111989),
            ("KR80", 0),
            ("KR81", 9.591693391393433e-14),
            ("KR81M", 0.0529119985160263),
            ("KR82", 0),
            ("KR83", 0),
            ("KR83M", math.log(2) / (1.83 * SECONDS_PER_HOUR)),
            ("KR84", 0),
            ("KR85", 2.0453466678736843e-09),
            ("KR85M", 4.29725468419061e-05),
            ("KR86", 0),
            ("KR87", 0.000151408296321526),
            ("KR88", 0.0000681560649518136),
            ("KR89", 0.00366744539978807),
            ("KR90", 0.021446385537127),
            ("KR91", 0.0808806511738559),
            ("KR92", 0.376710424217362),
            ("KR93", 0.538994697169475),
            ("KR94", 3.26956217245257),
            ("KR95", 6.08023842596443),
            ("KR96", 8.66433975699932),
            ("KR97", 11.0023361993642),
            ("KR98", 16.1197018734871),
            ("KR99", 53.3190138892265),
            ("KR100", 99.0210257942778),
            ("KR101", 1091570.36308652),
        ]

        for nucName, refDecayConstant in REF_KR_DECAY_CONSTANTS:
            refNb = nuclideBases.byName[nucName]
            decayConstantNb = math.log(2) / refNb.halflife
            try:
                self.assertAlmostEqual(
                    (refDecayConstant - decayConstantNb) / refDecayConstant,
                    0,
                    6,
                )
            except ZeroDivisionError:
                self.assertEqual(refDecayConstant, decayConstantNb)
            except AssertionError:
                errorMessage = (
                    "{} reference decay constant {} ARMI decay constant {}".format(
                        nucName, refDecayConstant, decayConstantNb
                    )
                )
                raise AssertionError(errorMessage)

        for nucName in ["XE134", "XE136", "EU151"]:
            nb = nuclideBases.byName[nucName]
            decayConstantNb = math.log(2) / nb.halflife
            self.assertAlmostEqual(decayConstantNb, 0, places=3)

    def test_curieDefinitionWithRa226(self):
        """
        Tests that the decay constant of Ra-226 is close to 1 Ci.

        Notes
        -----
        The original definition of 1 Ci was based on the half-life of Ra-226
        for 1 gram. The latest evaluations show that 1 gram is defined as
        0.988 Ci.
        """
        ra226 = nuclideBases.byName["RA226"]
        decayConstantRa226 = math.log(2) / ra226.halflife
        weight = ra226.weight
        mass = 1  # gram
        activity = mass * AVOGADROS_NUMBER / weight * decayConstantRa226  # 1 gram
        activity = activity * CURIE_PER_BECQUEREL
        self.assertAlmostEqual(activity, 0.9885593, places=6)

    def test_loadMcc2Data(self):
        """Tests consistency with the `mcc-nuclides.yaml` input and the ENDF/B-V.2 nuclides in the data model.

        .. test:: Test that MCC v2 ENDF/B-V.2 IDs can be queried by nuclides.
            :id: T_ARMI_ND_ISOTOPES3
            :tests: R_ARMI_ND_ISOTOPES
        """
        with open(os.path.join(RES, "mcc-nuclides.yaml")) as f:
            yaml = YAML(typ="rt")
            data = yaml.load(f)
            expectedNuclides = set(
                [nuc for nuc in data.keys() if data[nuc]["ENDF/B-V.2"] is not None]
            )

        for nuc, nb in nuclideBases.byMcc2Id.items():
            self.assertIn(nb.name, expectedNuclides)
            self.assertEqual(nb.getMcc2Id(), nb.mcc2id)
            self.assertEqual(nb.getMcc2Id(), nuc)

        self.assertEqual(len(nuclideBases.byMcc2Id), len(expectedNuclides))

    def test_loadMcc3EndfVII0Data(self):
        """Tests consistency with the `mcc-nuclides.yaml` input and the ENDF/B-VII.0 nuclides in the data model.

        .. test:: Test that MCC v3 ENDF/B-VII.0 IDs can be queried by nuclides.
            :id: T_ARMI_ND_ISOTOPES4
            :tests: R_ARMI_ND_ISOTOPES

        .. test:: Test the MCC ENDF/B-VII.0 nuclide data that was read from file instead of code.
            :id: T_ARMI_ND_DATA1
            :tests: R_ARMI_ND_DATA
        """
        with open(os.path.join(RES, "mcc-nuclides.yaml")) as f:
            yaml = YAML(typ="rt")
            data = yaml.load(f)
            expectedNuclides = set(
                [nuc for nuc in data.keys() if data[nuc]["ENDF/B-VII.0"] is not None]
            )

        for nuc, nb in nuclideBases.byMcc3IdEndfbVII0.items():
            self.assertIn(nb.name, expectedNuclides)
            self.assertEqual(nb.getMcc3IdEndfbVII0(), nb.mcc3idEndfbVII0)
            self.assertEqual(nb.getMcc3IdEndfbVII0(), nuc)

        # Subtract 1 nuclide due to DUMP2.
        self.assertEqual(len(nuclideBases.byMcc3IdEndfbVII0), len(expectedNuclides) - 1)

    def test_loadMcc3EndfVII1Data(self):
        """Tests consistency with the `mcc-nuclides.yaml` input and the ENDF/B-VII.1 nuclides in the data model.

        .. test:: Test that MCC v3 ENDF/B-VII.1 IDs can be queried by nuclides.
            :id: T_ARMI_ND_ISOTOPES6
            :tests: R_ARMI_ND_ISOTOPES

        .. test:: Test the MCC ENDF/B-VII.1 nuclide data that was read from file instead of code.
            :id: T_ARMI_ND_DATA2
            :tests: R_ARMI_ND_DATA
        """
        with open(os.path.join(RES, "mcc-nuclides.yaml")) as f:
            yaml = YAML(typ="rt")
            data = yaml.load(f)
            expectedNuclides = set(
                [nuc for nuc in data.keys() if data[nuc]["ENDF/B-VII.1"] is not None]
            )

        for nuc, nb in nuclideBases.byMcc3IdEndfbVII1.items():
            self.assertIn(nb.name, expectedNuclides)
            self.assertEqual(nb.getMcc3IdEndfbVII1(), nb.mcc3idEndfbVII1)
            self.assertEqual(nb.getMcc3IdEndfbVII1(), nuc)
            self.assertEqual(nb.getMcc3Id(), nb.mcc3idEndfbVII1)
            self.assertEqual(nb.getMcc3Id(), nuc)

        # Subtract 1 nuclide due to DUMP2.
        self.assertEqual(len(nuclideBases.byMcc3IdEndfbVII1), len(expectedNuclides) - 1)


class TestAAAZZZSId(unittest.TestCase):
    def test_AAAZZZSNameGenerator(self):
        """Test that AAAZZS ID name generator.

        .. test:: Query the AAAZZS IDs can be retrieved for nuclides.
            :id: T_ARMI_ND_ISOTOPES5
            :tests: R_ARMI_ND_ISOTOPES
        """
        referenceNucNames = [
            ("C12", "120060"),
            ("U235", "2350920"),
            ("AM242M", "2420951"),
        ]

        for nucName, refAaazzzs in referenceNucNames:
            nb = nuclideBases.byName[nucName]
            if refAaazzzs:
                self.assertEqual(refAaazzzs, nb.getAAAZZZSId())
