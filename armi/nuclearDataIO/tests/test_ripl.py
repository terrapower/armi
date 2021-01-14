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

"""Tests for RIPL."""

import unittest
import os
import math

import six

from armi.nuclearDataIO import ripl
from armi.nucDirectory import nuclideBases
from armi.utils.units import SECONDS_PER_HOUR

THIS_DIR = os.path.dirname(__file__)
SAMPLE_RIPL_MASS = """#
#  Z   A s fl     Mexp      Err       Mth      Emic    beta2   beta3   beta4   beta6
#                [MeV]     [MeV]     [MeV]     [MeV]
#----------------------------------------------------------------------------------------------------
   0   1 n  2     8.071     0.000
   1   1 H  2     7.289     0.000
   1   2 H  2    13.136     0.000
   1   3 H  2    14.950     0.000
   1   4 H  2    25.902     0.103
   1   5 H  2    32.892     0.100
   1   6 H  2    41.864     0.265
"""

SAMPLE_RIPL_ABUNDANCE = """#      Natural abundances
#  Z  A  El   abundance  uncert.
#               [%]       [%]
#-------------------------------
   1   1 H   99.985001  0.001000
   1   2 H    0.015000  0.001000
   2   3 He   0.000137  0.000003
   2   4 He  99.999863  0.000003
   """

# hand calculated reference data includes stable isotopes, radioactive
# isotopes, metastable isotopes and exercises metastable minimum halflife
REF_KR_DECAY_CONSTANTS = [
    ("KR69", 25.2973423562024),
    ("KR70", 13.3297534723066),
    ("KR71", 6.93147180559945),
    ("KR72", 0.0403931923403232),
    ("KR73", 0.0253900066139174),
    ("KR73M", 6478011.03327052),
    ("KR74", 0.0010045611312463),
    ("KR75", 0.00269287948935488),
    ("KR76", 1.30095191546536e-05),
    ("KR77", 0.000155274906039414),
    ("KR78", 0),
    ("KR79", 5.49680555559037e-06),
    ("KR79M", 0.0138629436111989),
    ("KR80", 0),
    ("KR81", 9.59107763331874e-14),
    ("KR81M", 0.0529119985160264),
    ("KR82", 0),
    ("KR83", 0),
    ("KR83M", math.log(2) / (1.83 * SECONDS_PER_HOUR)),
    ("KR84", 0),
    ("KR84M", 378768.951125653),
    ("KR85", 2.03806874613333e-09),
    ("KR85M", 4.29725468419061e-05),
    ("KR86", 0),
    ("KR87", 0.000151408296321526),
    ("KR88", 6.78226204070397e-05),
    ("KR89", 0.00366744539978807),
    ("KR90", 0.021446385537127),
    ("KR91", 0.0808806511738559),
    ("KR92", 0.376710424217362),
    ("KR93", 0.538994697169475),
    ("KR94", 3.26956217245257),
    ("KR95", 6.08023842596443),
    ("KR95M", 495105.128971389),
    ("KR96", 8.66433975699932),
    ("KR97", 11.1438453466229),
    ("KR98", 16.1950275831763),
    ("KR99", 17.3286795139986),
    ("KR100", 57.7622650466621),
    ("KR101", 138.629436111989),
]


class TestRipl(unittest.TestCase):
    """Test reading/processing RIPL files."""

    def test_readmass(self):
        inp = six.StringIO(SAMPLE_RIPL_MASS)
        for z, a, el, mass, _err in ripl.readFRDMMassFile(inp):
            if z == 1 and a == 1:
                self.assertAlmostEqual(mass, 1.0078250321)
                self.assertEqual(el, "H")
                break
        else:
            raise ValueError("No hydrogen found")

    def test_readAbundance(self):
        inp = six.StringIO(SAMPLE_RIPL_ABUNDANCE)
        for z, a, sym, percent, _err in ripl.readAbundanceFile(inp):
            if z == 2 and a == 4:
                self.assertAlmostEqual(percent, 99.999863)
                self.assertEqual(sym, "HE")
                break
        else:
            raise ValueError("No helium found")

    def test_discoverRiplDecayFiles(self):
        ripDecayFiles = ripl.discoverRiplDecayFiles(THIS_DIR)
        self.assertEqual(len(ripDecayFiles), 1)
        self.assertIn("z036.dat", ripDecayFiles[0])
        self.assertTrue(os.path.exists(ripDecayFiles[0]))

    def test_RiplDecayFile(self):
        testDecayConstants = ripl.getNuclideDecayConstants(
            os.path.join(THIS_DIR, "z036.dat")
        )
        kr69 = testDecayConstants[nuclideBases.byName["KR69"]]
        self.assertAlmostEqual(1.0 - kr69 / 2.53e01, 0, 3)

        for nucName, refDecayConstant in REF_KR_DECAY_CONSTANTS:
            refNb = nuclideBases.byName[nucName]
            self.assertIn(refNb, testDecayConstants)
            try:
                self.assertAlmostEqual(
                    (refDecayConstant - testDecayConstants[refNb]) / refDecayConstant,
                    0,
                    6,
                )
            except ZeroDivisionError:
                self.assertEqual(refDecayConstant, testDecayConstants[refNb])
            except AssertionError:
                errorMessage = "{} reference Halflife {} ARMI halflife {}".format(
                    nucName, refDecayConstant, testDecayConstants[refNb]
                )
                raise AssertionError(errorMessage)

        testDecayConstants = ripl.getNuclideDecayConstants(
            os.path.join(THIS_DIR, "longLivedRipleData.dat")
        )

        for nucName in ["XE134", "XE136", "EU151"]:
            nb = nuclideBases.byName[nucName]
            self.assertAlmostEqual(testDecayConstants[nb], 0, places=3)


if __name__ == "__main__":
    unittest.main()
