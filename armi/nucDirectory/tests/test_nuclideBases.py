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

"""
Tests for nuclideBases.
"""
import unittest
import random
import re

from armi.nucDirectory import nuclideBases
from armi.nucDirectory import elements

from armi.nucDirectory.tests import NUCDIRECTORY_TESTS_DEFAULT_DIR_PATH


class TestNuclide(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nucDirectoryTestsPath = NUCDIRECTORY_TESTS_DEFAULT_DIR_PATH

    def test_nucBases_fromNameBadNameRaisesException(self):
        with self.assertRaises(KeyError):
            nuclideBases.byName["WTF"]

    def test_nucBase_AllAbundancesAddToOne(self):
        for zz in range(1, 102):
            clides = nuclideBases.isotopes(zz)
            # We only process nuclides with measured masses. Some are purely theoretical, mostly over z=100
            self.assertTrue(
                len(clides) > 0, msg="z={} unexpectedly has no nuclides".format(zz)
            )
            total = sum([nn.abundance for nn in clides if nn.a > 0])
            self.assertAlmostEqual(
                any([nn.abundance > 0 for nn in clides]),
                total,
                delta=1e-4,
                msg="Abundance ({}) not 1.0 for nuclideBases:\n  {}"
                "".format(total, "\n  ".join(repr(nn) for nn in clides)),
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
            "LFP00",  # this is an on-the-fly fission product
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

    def test_element_getNatrualIsotpicsOnlyRetrievesAbundaceGt0(self):
        # so this test LOOKS like it is in the wrong file,
        # but being here eliminates a dependency for test_elements,
        # which will make test_elements run faster (particularly when run by itself)
        for ee in elements.byZ.values():
            if not ee.isNaturallyOccurring():
                continue
            for nuc in ee.getNaturalIsotopics():
                self.assertGreater(nuc.abundance, 0.0)
                self.assertGreater(nuc.a, 0)

    def test_element_getNaturalIsotopicsAddsToOne(self):
        # so this test LOOKS like it is in the wrong file,
        # but being here eliminates a dependency for test_elements,
        # which will make test_elements run faster (particularly when run by itself)
        count = 0
        for ee in elements.byZ.values():
            if not ee.isNaturallyOccurring():
                continue
            if any(ee.getNaturalIsotopics()):
                count += 1
                self.assertAlmostEqual(
                    1.0,
                    sum([ee.abundance for ee in ee.getNaturalIsotopics()]),
                    delta=1e-4,
                )
        self.assertGreater(
            count, 10, "Not enough natural isotopes, something went wrong"
        )

    def test_LumpNuclideBase_getNatrualIsotopicsDoesNotFail(self):
        for nuc in nuclideBases.where(
            lambda nn: isinstance(nn, nuclideBases.LumpNuclideBase) and nn.z == 0
        ):
            self.assertEqual(0, len(list(nuc.getNaturalIsotopics())), nuc)

    def test_NaturalNuclideBase_getNatrualIsotpics(self):
        for nuc in nuclideBases.where(
            lambda nn: isinstance(nn, nuclideBases.NaturalNuclideBase)
        ):
            numNaturals = len(list(nuc.getNaturalIsotopics()))
            self.assertGreaterEqual(
                len(nuc.element.nuclideBases) - 1, numNaturals
            )  # , nuc)

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

    def test_NaturalNuclide_atomicWeightIsAverageOfNaturallyOccuringIsotopes(self):
        for natNuk in nuclideBases.where(
            lambda nn: isinstance(nn, nuclideBases.NaturalNuclideBase)
        ):
            atomicMass = 0.0
            for natIso in natNuk.getNaturalIsotopics():
                atomicMass += natIso.abundance * natIso.weight
            self.assertEqual(
                atomicMass,
                natNuk.weight,
                "{} weight is {}, expected {}".format(
                    natNuk, natNuk.weight, atomicMass
                ),
            )

    def test_nucBases_labelAndNameCollsionsAreForSameNuclide(self):
        count = 0
        for nuc in nuclideBases.where(lambda nn: nn.name == nn.label):
            count += 1
            self.assertEqual(nuc, nuclideBases.byName[nuc.name])
            self.assertEqual(nuc, nuclideBases.byDBName[nuc.getDatabaseName()])
            self.assertEqual(nuc, nuclideBases.byLabel[nuc.label])
        self.assertGreater(count, 10)

    def test_nucBases_imposeBurnChainDecayBulkStatistics(self):
        """
        Test must be updated manually when burn chain is modified.
        """
        decayers = list(nuclideBases.where(lambda nn: len(nn.decays) > 0))
        self.assertTrue(decayers)
        for nuc in decayers:
            # print nuc
            # for tt in nuc.decays: print '  ', tt
            # TODO: BUG 102
            if nuc.name in [
                "U238",
                "PU240",
                "PU242",
                "CM242",
                "CM244",
                "CM246",
                "CF250",
            ]:
                continue
            self.assertAlmostEqual(1.0, sum(dd.branch for dd in nuc.decays))

    def test_nucBases_imposeBurnChainTransmutationBulkStatistics(self):
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
        actual = {
            nn.name: nn.nuSF for nn in nuclideBases.where(lambda nn: nn.nuSF > 0.0)
        }
        expected = {
            "CM248": 3.1610,
            "BK249": 3.4000,
            "CF249": 3.4000,
            "CF250": 3.5200,
            "CF252": 3.7676,
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
        am242m = nuclideBases.byName["AM242"]
        self.assertEqual(am242m, nuclideBases.byName["AM242M"])
        self.assertEqual("nAm242", am242m.getDatabaseName())
        self.assertEqual(am242m, nuclideBases.byDBName["nAm242"])
        self.assertAlmostEqual(am242m.weight, 242.05954949)

        am242g = nuclideBases.byName["AM242G"]
        self.assertEqual(am242g, nuclideBases.byName["AM242G"])
        self.assertEqual("nAm242g", am242g.getDatabaseName())
        self.assertEqual(am242g, nuclideBases.byDBName["nAm242g"])

    def test_nucBases_isHeavyMetal(self):
        for nb in nuclideBases.where(lambda nn: nn.z <= 89):
            self.assertFalse(nb.isHeavyMetal())
        for nb in nuclideBases.where(lambda nn: nn.z > 89):
            self.assertTrue(nb.isHeavyMetal())

    def test_getEndfMatNum(self):
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


class test_getAAAZZZSId(unittest.TestCase):
    def test_AAAZZZSNameGenerator(self):

        referenceNucNames = [
            ("C", "120060"),
            ("U235", "2350920"),
            ("AM242M", "2420951"),
            ("LFP35", None),
            ("DUMP1", None),
        ]

        for nucName, refAaazzzs in referenceNucNames:
            nb = nuclideBases.byName[nucName]
            if refAaazzzs:
                self.assertEqual(refAaazzzs, nb.getAAAZZZSId())


def readEndfMatNumIndex(path):
    """
    read mat nums from known endf reference
    """

    endfReferenceFile = open(path)
    endfMatNumbers = {}

    for line in endfReferenceFile:
        if not re.search(r"^\s+\d+\)", line):
            continue
        data = line.split()
        _rowNum, matNum, nuclide = data[:3]
        _zNum, element, aNum = nuclide.split("-")
        armiNuclideName = element + aNum
        endfMatNumbers[armiNuclideName] = matNum

    return endfMatNumbers


if __name__ == "__main__":
    #     import sys;sys.argv = ['', 'TestNuclide.test_nucBases_factoryIsFast']
    unittest.main()
