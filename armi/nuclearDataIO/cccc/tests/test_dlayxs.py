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
Tests for DELAYXS
"""
import unittest
import copy
import os
import filecmp

import numpy

from armi.tests import mockRunLogs
from armi.nuclearDataIO.cccc import dlayxs
from armi.nucDirectory import nuclideBases
from armi.nuclearDataIO.tests import test_xsLibraries
from armi.tests import requires_fixture


class DlayxsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dlayxs3 = dlayxs.readBinary(test_xsLibraries.DLAYXS_MCC3)

    def test_decayConstants(self):
        """
        test that all emission spectrum delayEmissionSpectrum is normalized
        """
        delay = self.dlayxs3
        self.assertTrue(
            numpy.allclose(
                delay[nuclideBases.byName["PU239"]].precursorDecayConstants,
                [0.013271, 0.030881, 0.11337, 0.29249999, 0.85749, 2.72970009],
            )
        )
        self.assertTrue(
            numpy.allclose(
                delay[nuclideBases.byName["U235"]].precursorDecayConstants,
                [0.013336, 0.032739, 0.12078, 0.30278, 0.84948999, 2.85299993],
            )
        )

    def test_chi_delay(self):
        """
        test that all emission spectrum delayEmissionSpectrum is normalized
        """
        delay = self.dlayxs3
        self.assertTrue(
            numpy.allclose(
                delay[nuclideBases.byName["PU239"]].delayEmissionSpectrum[0, :],
                [
                    0.00000000e00,
                    0.00000000e00,
                    0.00000000e00,
                    0.00000000e00,
                    1.02141285e-02,
                    1.27532169e-01,
                    1.72763243e-01,
                    2.13220030e-01,
                    1.89730868e-01,
                    1.18315071e-01,
                    5.78320175e-02,
                    4.74486388e-02,
                    2.08687764e-02,
                    2.07701419e-02,
                    1.18288407e-02,
                    5.50153898e-03,
                    2.21613585e-03,
                    9.31866292e-04,
                    4.13533067e-04,
                    1.95023225e-04,
                    9.77608724e-05,
                    5.17436347e-05,
                    2.86061440e-05,
                    1.63285349e-05,
                    9.52779556e-06,
                    5.64059519e-06,
                    3.37031338e-06,
                    2.02547858e-06,
                    1.22162965e-06,
                    9.89770456e-07,
                    7.63815024e-07,
                    2.56295589e-08,
                    7.76525899e-10,
                ],
            )
        )
        self.assertTrue(
            numpy.allclose(
                delay[nuclideBases.byName["U235"]].delayEmissionSpectrum[0, :],
                [
                    0.00000000e00,
                    0.00000000e00,
                    0.00000000e00,
                    0.00000000e00,
                    9.78936628e-03,
                    1.22233696e-01,
                    1.67251721e-01,
                    2.09521025e-01,
                    1.94571003e-01,
                    1.22512169e-01,
                    5.92396967e-02,
                    4.92908023e-02,
                    2.16992926e-02,
                    2.16606706e-02,
                    1.23427501e-02,
                    5.74052986e-03,
                    2.31238361e-03,
                    9.72325157e-04,
                    4.31480817e-04,
                    2.03484073e-04,
                    1.02000522e-04,
                    5.39869325e-05,
                    2.98460363e-05,
                    1.70361527e-05,
                    9.94064794e-06,
                    5.88499188e-06,
                    3.51633594e-06,
                    2.11323231e-06,
                    1.27455564e-06,
                    1.03265086e-06,
                    7.96905908e-07,
                    2.67399081e-08,
                    8.10167378e-10,
                ],
            )
        )

    def test_chi_delaySumsTo1(self):
        for dlayData in self.dlayxs3.values():
            self.assertAlmostEqual(6.0, dlayData.delayEmissionSpectrum.sum(), 6)

    def test_NuDelay(self):
        delay = self.dlayxs3
        # this data has NOT been compared to ENDF-V, it was created before modifying the read/write of DLAYXS and
        # was used to make sure the data wasn't accidentally transposed, hence there are two nuclides with two vectors
        # being tested.
        self.assertTrue(
            numpy.allclose(
                delay[nuclideBases.byName["PU239"]].delayNeutronsPerFission[0, :],
                [
                    0.00015611,
                    0.000159,
                    0.00021092,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                    0.00023417,
                ],
            )
        )
        self.assertTrue(
            numpy.allclose(
                delay[nuclideBases.byName["PU239"]].delayNeutronsPerFission[1, :],
                [
                    0.00101669,
                    0.0010355,
                    0.0013736,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                    0.00152503,
                ],
            )
        )
        self.assertTrue(
            numpy.allclose(
                delay[nuclideBases.byName["U235"]].delayNeutronsPerFission[0, :],
                [
                    0.000315,
                    0.00032497,
                    0.00050422,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                    0.0005845,
                ],
            )
        )
        self.assertTrue(
            numpy.allclose(
                delay[nuclideBases.byName["U235"]].delayNeutronsPerFission[1, :],
                [
                    0.0016254,
                    0.00167686,
                    0.00260177,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                    0.00301602,
                ],
            )
        )

    @unittest.skip(
        "The TH232, U232, PU238 and PU242 numbers do not agree, likely because they are from ENDV/B VI.8."
    )
    def test_ENDFVII1DecayConstants(self):
        """Test ENDF/B VII.1 decay constants. Retrieved from ENDF/B VII.1"""
        self._assertDC(
            "TH227  ",
            [
                1.280000e-2,
                3.540000e-2,
                1.098000e-1,
                2.677000e-1,
                5.022000e-1,
                2.095600e0,
            ],
        )
        self._assertDC(
            "TH228  ",
            [
                1.280000e-2,
                3.500000e-2,
                1.123000e-1,
                2.760000e-1,
                4.950000e-1,
                2.045600e0,
            ],
        )
        self._assertDC(
            "TH229  ",
            [
                1.280000e-2,
                3.500000e-2,
                1.123000e-1,
                2.760000e-1,
                4.950000e-1,
                2.045600e0,
            ],
        )
        self._assertDC(
            "TH230  ",
            [
                1.280000e-2,
                3.500000e-2,
                1.123000e-1,
                2.760000e-1,
                4.950000e-1,
                2.045600e0,
            ],
        )
        self._assertDC(
            "TH232  ",
            [
                1.240000e-2,
                3.340000e-2,
                1.210000e-1,
                3.210000e-1,
                1.210000e0,
                3.290000e0,
            ],
        )
        self._assertDC(
            "TH233  ",
            [
                1.310000e-2,
                3.500000e-2,
                1.272000e-1,
                3.287000e-1,
                9.100000e-1,
                2.820300e0,
            ],
        )
        self._assertDC(
            "TH234  ",
            [
                1.310000e-2,
                3.500000e-2,
                1.127200e-1,
                3.287000e-1,
                9.100000e-1,
                2.820300e0,
            ],
        )
        self._assertDC(
            "PA231  ",
            [
                1.240000e-2,
                3.340000e-2,
                1.210000e-1,
                3.210000e-1,
                1.210000e0,
                3.290000e0,
            ],
        )
        self._assertDC(
            "PA233  ",
            [
                1.240000e-2,
                3.340000e-2,
                1.210000e-1,
                3.210000e-1,
                1.210000e0,
                3.290000e0,
            ],
        )
        self._assertDC(
            "U232   ",
            [
                1.280000e-2,
                3.500000e-2,
                1.073000e-1,
                2.557000e-1,
                6.626000e-1,
                2.025400e0,
            ],
        )
        self._assertDC(
            "U233   ",
            [
                1.291100e-2,
                3.473800e-2,
                1.192800e-1,
                2.861700e-1,
                7.877000e-1,
                2.441700e0,
            ],
        )
        self._assertDC(
            "U234   ",
            [
                1.308200e-2,
                3.368400e-2,
                1.209500e-1,
                2.951700e-1,
                8.136300e-1,
                2.572100e0,
            ],
        )
        self._assertDC(
            "U235   ",
            [
                1.333600e-2,
                3.273900e-2,
                1.207800e-1,
                3.027800e-1,
                8.494900e-1,
                2.853000e0,
            ],
        )
        self._assertDC(
            "U236   ",
            [
                1.338000e-2,
                3.215500e-2,
                1.201500e-1,
                3.112900e-1,
                8.793600e-1,
                2.840500e0,
            ],
        )
        self._assertDC(
            "U237   ",
            [
                1.376200e-2,
                3.159100e-2,
                1.210700e-1,
                3.162200e-1,
                9.073100e-1,
                3.036800e0,
            ],
        )
        self._assertDC(
            "U238   ",
            [
                1.363000e-2,
                3.133400e-2,
                1.233400e-1,
                3.237300e-1,
                9.059700e-1,
                3.048700e0,
            ],
        )
        self._assertDC(
            "U239   ",
            [
                1.249577e-2,
                3.037978e-2,
                1.068975e-1,
                3.240317e-1,
                1.334253e0,
                9.544175e0,
            ],
        )
        self._assertDC(
            "U240   ",
            [
                1.249423e-2,
                3.025520e-2,
                1.159376e-1,
                3.414764e-1,
                1.318630e0,
                9.979027e0,
            ],
        )
        self._assertDC(
            "U241   ",
            [
                1.249577e-2,
                3.037978e-2,
                1.068975e-1,
                3.240317e-1,
                1.334253e0,
                9.544175e0,
            ],
        )
        self._assertDC(
            "NP236  ",
            [
                1.360000e-2,
                3.080000e-2,
                1.189000e-1,
                3.077000e-1,
                8.988000e-1,
                2.967600e0,
            ],
        )
        self._assertDC(
            "NP236m1",
            [
                1.360000e-2,
                3.080000e-2,
                1.189000e-1,
                3.077000e-1,
                8.988000e-1,
                2.967600e0,
            ],
        )
        self._assertDC(
            "NP237  ",
            [
                1.325200e-2,
                3.160300e-2,
                1.167900e-1,
                3.006500e-1,
                8.666900e-1,
                2.760000e0,
            ],
        )
        self._assertDC(
            "NP238  ",
            [
                1.360000e-2,
                3.080000e-2,
                1.189000e-1,
                3.077000e-1,
                8.988000e-1,
                2.967600e0,
            ],
        )
        self._assertDC(
            "NP239  ",
            [
                1.330000e-2,
                3.160000e-2,
                1.211000e-1,
                2.933000e-1,
                8.841000e-1,
                2.792200e0,
            ],
        )
        self._assertDC(
            "PU236  ",
            [
                1.330000e-2,
                3.120000e-2,
                1.162000e-1,
                2.888000e-1,
                8.561000e-1,
                2.713800e0,
            ],
        )
        self._assertDC(
            "PU238  ",
            [
                1.330000e-2,
                3.120000e-2,
                1.162000e-1,
                2.888000e-1,
                8.561000e-1,
                2.713800e0,
            ],
        )
        self._assertDC(
            "PU239  ",
            [
                1.327100e-2,
                3.088100e-2,
                1.133700e-1,
                2.925000e-1,
                8.574900e-1,
                2.729700e0,
            ],
        )
        self._assertDC(
            "PU240  ",
            [
                1.332900e-2,
                3.051000e-2,
                1.151600e-1,
                2.974000e-1,
                8.476600e-1,
                2.879600e0,
            ],
        )
        self._assertDC(
            "PU241  ",
            [
                1.359900e-2,
                2.996600e-2,
                1.167300e-1,
                3.069100e-1,
                8.701000e-1,
                3.002800e0,
            ],
        )
        self._assertDC(
            "PU242  ",
            [
                1.360000e-2,
                3.020000e-2,
                1.154000e-1,
                3.042000e-1,
                8.272000e-1,
                3.137200e0,
            ],
        )
        self._assertDC(
            "PU244  ",
            [
                1.360000e-2,
                3.020000e-2,
                1.154000e-1,
                3.042000e-1,
                8.272000e-1,
                3.137200e0,
            ],
        )
        self._assertDC(
            "AM241  ",
            [
                1.333800e-2,
                3.079800e-2,
                1.130500e-1,
                2.867700e-1,
                8.653600e-1,
                2.643000e0,
            ],
        )
        self._assertDC(
            "AM242  ",
            [
                1.350000e-2,
                3.010000e-2,
                1.152000e-1,
                2.994000e-1,
                8.646000e-1,
                2.810700e0,
            ],
        )
        self._assertDC(
            "AM242m1",
            [
                1.350000e-2,
                3.010000e-2,
                1.152000e-1,
                2.994000e-1,
                8.646000e-1,
                2.810700e0,
            ],
        )
        self._assertDC(
            "AM243  ",
            [
                1.349900e-2,
                2.975900e-2,
                1.137700e-1,
                2.985900e-1,
                8.820200e-1,
                2.811100e0,
            ],
        )
        self._assertDC(
            "AM244  ",
            [
                1.290000e-2,
                3.130000e-2,
                1.350000e-1,
                3.330000e-1,
                1.360000e0,
                4.040000e0,
            ],
        )
        self._assertDC(
            "AM244m1",
            [
                1.290000e-2,
                3.130000e-2,
                1.350000e-1,
                3.330000e-1,
                1.360000e0,
                4.040000e0,
            ],
        )
        self._assertDC(
            "CM241  ",
            [
                1.290000e-2,
                3.130000e-2,
                1.350000e-1,
                3.330000e-1,
                1.360000e0,
                4.040000e0,
            ],
        )
        self._assertDC(
            "CM242  ",
            [
                1.300000e-2,
                3.120000e-2,
                1.129000e-1,
                2.783000e-1,
                8.710000e-1,
                2.196900e0,
            ],
        )
        self._assertDC(
            "CM243  ",
            [
                1.309000e-2,
                3.013000e-2,
                1.149800e-1,
                2.918900e-1,
                8.575600e-1,
                2.591700e0,
            ],
        )
        self._assertDC(
            "CM245  ",
            [
                1.340000e-2,
                3.070000e-2,
                1.130000e-1,
                3.001000e-1,
                8.340000e-1,
                2.768600e0,
            ],
        )
        self._assertDC(
            "CM248  ",
            [
                1.280000e-2,
                3.140000e-2,
                1.280000e-1,
                3.250000e-1,
                1.350000e0,
                3.700000e0,
            ],
        )
        self._assertDC(
            "CM249  ",
            [
                1.320000e-2,
                3.210000e-2,
                1.390000e-1,
                3.580000e-1,
                1.410000e0,
                4.020000e0,
            ],
        )
        self._assertDC(
            "CM250  ",
            [
                1.340000e-2,
                3.070000e-2,
                1.130000e-1,
                3.001000e-1,
                8.340000e-1,
                2.768600e0,
            ],
        )
        self._assertDC(
            "BK249  ",
            [
                1.290000e-2,
                3.130000e-2,
                1.350000e-1,
                3.330000e-1,
                1.360000e0,
                4.040000e0,
            ],
        )
        self._assertDC(
            "BK250  ",
            [
                1.290000e-2,
                3.130000e-2,
                1.350000e-1,
                3.330000e-1,
                1.360000e0,
                4.040000e0,
            ],
        )
        self._assertDC(
            "CF249  ",
            [
                1.350000e-2,
                2.940000e-2,
                1.053000e-1,
                2.930000e-1,
                8.475000e-1,
                2.469800e0,
            ],
        )
        self._assertDC(
            "CF250  ",
            [
                1.290000e-2,
                3.130000e-2,
                1.350000e-1,
                3.330000e-1,
                1.360000e0,
                4.040000e0,
            ],
        )
        self._assertDC(
            "CF251  ",
            [
                1.570000e-2,
                2.880000e-2,
                1.077000e-1,
                3.246000e-1,
                8.837000e-1,
                2.631400e0,
            ],
        )
        self._assertDC(
            "CF252  ",
            [
                1.360000e-2,
                2.910000e-2,
                1.068000e-1,
                3.024000e-1,
                8.173000e-1,
                2.615900e0,
            ],
        )
        self._assertDC(
            "CF254  ",
            [
                1.360000e-2,
                2.910000e-2,
                1.068000e-1,
                3.024000e-1,
                8.173000e-1,
                2.615900e0,
            ],
        )
        self._assertDC(
            "ES254  ",
            [
                1.940000e-2,
                2.890000e-2,
                1.048000e-1,
                3.185000e-1,
                8.332000e-1,
                2.723800e0,
            ],
        )
        self._assertDC(
            "ES254m1",
            [
                1.940000e-2,
                2.890000e-2,
                1.048000e-1,
                3.185000e-1,
                8.332000e-1,
                2.723800e0,
            ],
        )
        self._assertDC(
            "ES255  ",
            [
                1.940000e-2,
                2.890000e-2,
                1.048000e-1,
                3.185000e-1,
                8.332000e-1,
                2.723800e0,
            ],
        )
        self._assertDC(
            "FM255  ",
            [
                1.490000e-2,
                2.870000e-2,
                1.027000e-1,
                3.130000e-1,
                8.072000e-1,
                2.576800e0,
            ],
        )

    def _assertDC(self, nucName, endfProvidedData):
        # DC -> decay constants
        try:
            dlayData = self.dlayxs3[
                nuclideBases.byName[nucName.strip()]
            ].precursorDecayConstants
            self.assertTrue(numpy.allclose(dlayData, endfProvidedData, 1e-3))
        except AssertionError:
            # this is reraised because generating the message might take some time to format all the data from the arrays
            raise AssertionError(
                "{} was different,\nexpected:{}\nactual:{}".format(
                    nucName, endfProvidedData, dlayData
                )
            )
        except KeyError:
            pass

    @unittest.skip(
        "All the delayNeutronsPerFission data from mcc-v3 does not agree, this may be because they are from ENDV/B VI.8."
    )
    def test_ENDFVII1NeutronsPerFission(self):
        r"""
        Build delayed nu based on ENDF/B-VII data.

        Notes
        -----
        This data was simply retrieved from the NNDC [http://www.nndc.bnl.gov]. U-235 consists of 6 points for delayed
        nu and all others are only 4 points! Delayed group relative abundances are from G. Robert Keepin "Physics of
        Nuclear Kinetics" Table 4-7. There are comments there about why the fast fission data is standard.
        """
        total = [0.0030] * 3 + [0.0547] * 30
        self._assertNuDelay(
            "TH232",
            [
                [0.034 * i for i in total],
                [0.150 * i for i in total],
                [0.155 * i for i in total],
                [0.446 * i for i in total],
                [0.172 * i for i in total],
                [0.043 * i for i in total],
            ],
        )

        total = [0.0042] * 1 + [0.0047] * 2 + [0.0074] * 30
        self._assertNuDelay(
            "U233",
            [
                [0.086 * i for i in total],
                [0.274 * i for i in total],
                [0.227 * i for i in total],
                [0.317 * i for i in total],
                [0.073 * i for i in total],
                [0.023 * i for i in total],
            ],
        )

        total = [0.0090] * 3 + [0.0167] * 30
        self._assertNuDelay(
            "U235",
            [
                [0.038 * i for i in total],
                [0.213 * i for i in total],
                [0.188 * i for i in total],
                [0.407 * i for i in total],
                [0.128 * i for i in total],
                [0.026 * i for i in total],
            ],
        )

        total = [0.026] * 3 + [0.044] * 30
        self._assertNuDelay(
            "U238",
            [
                [0.013 * i for i in total],
                [0.137 * i for i in total],
                [0.162 * i for i in total],
                [0.388 * i for i in total],
                [0.225 * i for i in total],
                [0.075 * i for i in total],
            ],
        )

        total = [0.0043] * 3 + [0.00645] * 30
        self._assertNuDelay(
            "PU239",
            [
                [0.038 * i for i in total],
                [0.280 * i for i in total],
                [0.216 * i for i in total],
                [0.328 * i for i in total],
                [0.103 * i for i in total],
                [0.035 * i for i in total],
            ],
        )

        total = [0.00615] * 3 + [0.0090] * 30
        self._assertNuDelay(
            "PU240",
            [
                [0.028 * i for i in total],
                [0.273 * i for i in total],
                [0.192 * i for i in total],
                [0.350 * i for i in total],
                [0.128 * i for i in total],
                [0.029 * i for i in total],
            ],
        )

        # Keepin doesn't have any data on relative delayed group abundances for
        # Pu-241 and Pu-242, and it looks like A.DELAY doesn't either! Let's
        # assume that the abundances are the same as Pu-240.
        total = [0.0084] * 3 + [0.0162] * 30
        self._assertNuDelay(
            "PU241",
            [
                [0.028 * i for i in total],
                [0.273 * i for i in total],
                [0.192 * i for i in total],
                [0.350 * i for i in total],
                [0.128 * i for i in total],
                [0.029 * i for i in total],
            ],
        )

        total = [0.0115] + [0.0129] + [0.0133] + [0.0153] * 30
        self._assertNuDelay(
            "PU242",
            [
                [0.028 * i for i in total],
                [0.273 * i for i in total],
                [0.192 * i for i in total],
                [0.350 * i for i in total],
                [0.128 * i for i in total],
                [0.029 * i for i in total],
            ],
        )

    def _assertNuDelay(self, nucName, endfProvidedData):
        try:
            dlayData = self.dlayxs3[
                nuclideBases.byName[nucName.strip()]
            ].delayNeutronsPerFission
            numpyData = numpy.array(endfProvidedData)
            self.assertTrue(numpy.allclose(dlayData, numpyData, 1e-3))
        except AssertionError:
            # this is reraised because generating the message might take some time to format all the data from the arrays
            raise AssertionError(
                "{} was different,\nexpected:{}\nactual:{}".format(
                    nucName, numpyData, dlayData
                )
            )
        except KeyError:
            pass

    def test_compare(self):
        with mockRunLogs.BufferLog() as _log:
            self.assertTrue(dlayxs.compare(self.dlayxs3, copy.deepcopy(self.dlayxs3)))

    def test_writeBinary_mcc3(self):
        dlayxs.writeBinary(self.dlayxs3, "test_writeBinary_mcc3.temp")
        self.assertTrue(
            filecmp.cmp(test_xsLibraries.DLAYXS_MCC3, "test_writeBinary_mcc3.temp")
        )
        os.remove("test_writeBinary_mcc3.temp")

    def test_nuclides(self):
        nucs3 = set(
            nuclideBases.byName[name]
            for name in [
                "TH232",
                "U232",
                "U233",
                "U234",
                "U235",
                "U236",
                "U238",
                "NP237",
                "PU238",
                "PU239",
                "PU240",
                "PU241",
                "PU242",
                "AM241",
            ]
        )
        self.assertEqual(nucs3, set(self.dlayxs3.keys()))

    def test_avg(self):
        with self.assertRaises(RuntimeError):
            _avg = self.dlayxs3.generateAverageDelayedNeutronConstants()

        fracs = dict(zip(self.dlayxs3.keys(), numpy.zeros(len(self.dlayxs3))))
        u235 = nuclideBases.byName["U235"]
        fracs[u235] = 1.0
        self.dlayxs3.nuclideContributionFractions = fracs
        avg = self.dlayxs3.generateAverageDelayedNeutronConstants()
        dlayU235 = self.dlayxs3[u235]
        self.assertTrue(
            numpy.allclose(avg.delayEmissionSpectrum, dlayU235.delayEmissionSpectrum)
        )


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'DlayxsTests.test_writeBinary_mcc3']
    unittest.main(verbosity=2)
