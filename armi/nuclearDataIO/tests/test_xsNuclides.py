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

r"""
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import unittest

from armi.nuclearDataIO import xsNuclides
from armi.nucDirectory import nuclideBases
from armi.tests import mockRunLogs
from armi import nuclearDataIO
from armi.tests import ISOAA_PATH
from armi.localization import exceptions
from armi.nuclearDataIO import xsLibraries
from armi.nuclearDataIO import isotxs


class NuclideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = isotxs.readBinary(ISOAA_PATH)

    def test_nuclide_createFromLabelFailsOnBadName(self):
        nuc = xsNuclides.XSNuclide(None, "BACONAA")
        nuc.isotxsMetadata["nuclideId"] = "BACN87"
        with self.assertRaises(exceptions.IsotxsError):
            nuc.updateBaseNuclide()

    def test_nuclide_creatingNuclidesDoesNotMessWithUnderlyingNuclideDict(self):
        nuc = nuclideBases.byName["U238"]
        self.assertFalse(hasattr(nuc, "xsId"))
        nrAA = xsNuclides.XSNuclide(None, "U238AA")
        nrAA.isotxsMetadata["nuclideId"] = nuc.mc2id
        nrAA.updateBaseNuclide()
        self.assertEqual("AA", nrAA.xsId)
        self.assertFalse(hasattr(nuc, "xsId"))

    def test_nuclide_modifyingNuclideAttributesUpdatesTheIsotxsNuclide(self):
        lib = xsLibraries.IsotxsLibrary()
        nuc = nuclideBases.byName["FE"]
        nrAA = xsNuclides.XSNuclide(lib, "FEAA")
        lib["FEAA"] = nrAA
        nrAA.isotxsMetadata["nuclideId"] = nuc.mc2id
        nrAA.updateBaseNuclide()
        self.assertEqual(len(nuc.trans), len(nrAA.trans))
        nuc.trans.append("whatever")
        self.assertEqual(len(nuc.trans), len(nrAA.trans))
        self.assertEqual("whatever", nuc.trans[-1])
        self.assertEqual("whatever", nrAA.trans[-1])
        # I've modified the underlying nuclide... need to reset.
        nuc.trans.pop()

    def test_nuclide_newLabelsDontCauseWarnings(self):
        with mockRunLogs.BufferLog() as logCapture:
            self.assertEqual("", logCapture._outputStream)
            fe = nuclideBases.byName["FE"]
            feNuc = xsNuclides.XSNuclide(None, "FEAA")
            feNuc.isotxsMetadata["nuclideId"] = fe.getMcc3Id()
            feNuc.updateBaseNuclide()
            self.assertEqual(fe, feNuc._base)
            self.assertEqual("", logCapture._outputStream)

    def test_nuclide_oldLabelsCauseWarnings(self):
        with mockRunLogs.BufferLog() as logCapture:
            self.assertEqual("", logCapture._outputStream)
            pu = nuclideBases.byName["PU239"]
            puNuc = xsNuclides.XSNuclide(None, "PLUTAA")
            puNuc.isotxsMetadata["nuclideId"] = pu.mc2id
            puNuc.updateBaseNuclide()
            self.assertEqual(pu, puNuc._base)
            length = len(logCapture._outputStream)
            self.assertGreater(length, 15)
            # now get it with a legitmate same label, length shouldn't change
            puNuc = xsNuclides.XSNuclide(None, "PLUTAB")
            puNuc.isotxsMetadata["nuclideId"] = pu.mc2id
            puNuc.updateBaseNuclide()
            self.assertEqual(pu, puNuc._base)
            self.assertEqual(length, len(logCapture._outputStream))

    def test_nuclide_nuclideBaseMethodsShouldNotFail(self):
        for nuc in self.lib.nuclides:
            self.assertIsInstance(nuc.getDatabaseName(), str)
            self.assertIsInstance(nuc.getMcc3Id(), str)

    def test_nuclide_isoaaDetails(self):
        nuc = self.lib["U235AA"]
        self.assertEqual(935.9793848991394, sum(nuc.micros.fission))
        self.assertEqual(1.0000000956962505, sum(nuc.micros.chi))
        nuc = self.lib["B10AA"]
        self.assertEqual(0.7499475518734471, sum(nuc.micros.nGamma))
        nuc = self.lib["B11AA"]
        self.assertEqual(0.0008645406924188137, sum(nuc.micros.n2n))
        self.assertEqual(0.008091875669521187, sum(nuc.micros.nGamma))

    def test_nuclide_2dXsArrangementIsCorrect(self):
        """manually compare some 2d XS data to ensure the correct coordinates"""
        u235 = self.lib["U235AA"]
        self.assertAlmostEqual(5.76494979858, u235.micros.total[0, 0])
        self.assertAlmostEqual(6.5928812027, u235.micros.total[1, 0])
        self.assertAlmostEqual(113.00479126, u235.micros.total[31, 0])
        self.assertAlmostEqual(606.100097656, u235.micros.total[32, 0])
        self.assertAlmostEqual(5.7647356987, u235.micros.total[0, 1])
        self.assertAlmostEqual(6.58178663254, u235.micros.total[1, 1])
        self.assertAlmostEqual(112.154449463, u235.micros.total[31, 1])
        self.assertAlmostEqual(606.100097656, u235.micros.total[32, 1])
        pu239 = self.lib["PU39AA"]
        self.assertAlmostEqual(5.83128976821, pu239.micros.total[0, 0])
        self.assertAlmostEqual(6.64091205597, pu239.micros.total[1, 0])
        self.assertAlmostEqual(394.632354736, pu239.micros.total[31, 0])
        self.assertAlmostEqual(973.399902343, pu239.micros.total[32, 0])
        self.assertAlmostEqual(5.83086299896, pu239.micros.total[0, 1])
        self.assertAlmostEqual(6.63103675842, pu239.micros.total[1, 1])
        self.assertAlmostEqual(383.891998291, pu239.micros.total[31, 1])
        self.assertAlmostEqual(973.399902343, pu239.micros.total[32, 1])

    def test_nuclide_scatterXsArrangementIsCorrect(self):
        """manually compare scatter XS data to ensure the correct coordinates"""
        u235 = self.lib["U235AA"]
        elasticScatter = u235.micros.elasticScatter
        n2nScatter = u235.micros.n2nScatter
        inelasticScatter = u235.micros.inelasticScatter

        self.assertAlmostEqual(0.0304658822715, elasticScatter[(2, 1)])
        self.assertAlmostEqual(0.0331721678376, inelasticScatter[(2, 0)])
        self.assertAlmostEqual(0.0310171917081, inelasticScatter[(2, 1)])
        self.assertAlmostEqual(0.0893433615565, inelasticScatter[(2, 2)])
        self.assertAlmostEqual(8.41606015456e-05, inelasticScatter[(16, 2)])
        self.assertAlmostEqual(3.23279074621e-08, inelasticScatter[(17, 2)])
        self.assertAlmostEqual(1.96078691062e-08, inelasticScatter[(18, 2)])
        self.assertAlmostEqual(1.18927703241e-08, inelasticScatter[(19, 2)])
        self.assertAlmostEqual(7.21333170972e-09, inelasticScatter[(20, 2)])
        self.assertAlmostEqual(3.66581343059e-09, inelasticScatter[(21, 2)])
        self.assertAlmostEqual(3.81337583732e-09, inelasticScatter[(22, 2)])
        self.assertAlmostEqual(1.35068589646e-09, inelasticScatter[(23, 2)])
        self.assertAlmostEqual(3.96180976914e-10, inelasticScatter[(24, 2)])
        self.assertAlmostEqual(4.85626551381e-05, n2nScatter[(1, 0)])
        self.assertAlmostEqual(4.61509245042e-07, n2nScatter[(1, 1)])
        self.assertAlmostEqual(9.67319720075e-05, n2nScatter[(2, 1)])
        self.assertAlmostEqual(3.39554608217e-05, n2nScatter[(16, 1)])
        self.assertAlmostEqual(1.12633460958e-05, n2nScatter[(17, 1)])
        self.assertAlmostEqual(6.964501722e-07, n2nScatter[(18, 1)])

        pu239 = self.lib["PU39AA"]
        elasticScatter = pu239.micros.elasticScatter
        inelasticScatter = pu239.micros.inelasticScatter
        n2nScatter = pu239.micros.n2nScatter
        self.assertAlmostEqual(1.7445316189e-05, n2nScatter[(1, 0)])
        self.assertAlmostEqual(4.12698773289e-06, n2nScatter[(17, 1)])
        self.assertAlmostEqual(6.80282767007e-07, n2nScatter[(1, 1)])
        self.assertAlmostEqual(1.56137302838e-05, n2nScatter[(16, 1)])
        self.assertAlmostEqual(9.7953477507e-07, n2nScatter[(18, 1)])
        self.assertAlmostEqual(0.000104939324956, n2nScatter[(2, 1)])
        self.assertAlmostEqual(0.0206335708499, elasticScatter[(2, 1)])
        self.assertAlmostEqual(0.000585122266784, inelasticScatter[(2, 0)])
        self.assertAlmostEqual(0.0352461636066, inelasticScatter[(2, 1)])
        self.assertAlmostEqual(0.457990020514, inelasticScatter[(2, 2)])
        self.assertAlmostEqual(1.16550609164e-07, n2nScatter[(19, 1)])
        self.assertAlmostEqual(5.22556074429e-05, inelasticScatter[(16, 2)])
        ######
        # the code below is very useful for generating the above test information
        ######
        # for key, xs in pu239Scatter.items():
        #    mk = max(key[1:])
        #    if len(key)  == 5 and 1 in key and 2 in key and (mk <= 2 or mk > 15):
        #        print ('self.assertAlmostEqual({}, pu239.micros[{}])'
        #               .format(xs, key))

    def test_getMicroXS(self):
        """Check whether getMicroXS method returns the correct cross sections for the input nuclide."""
        u235Nuc = self.lib["U235AA"]
        for i in range(self.lib.numGroups):
            ref_FissionXS = u235Nuc.micros.fission[i]
            cur_FissionXS = u235Nuc.getMicroXS("fission", i)
            self.assertAlmostEqual(ref_FissionXS, cur_FissionXS)


if __name__ == "__main__":
    unittest.main()
