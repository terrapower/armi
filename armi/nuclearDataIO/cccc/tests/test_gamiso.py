# Copyright 2022 TerraPower, LLC
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

"""Test GAMISO reading and writing."""

import os
import unittest
from copy import deepcopy

from armi.nuclearDataIO import xsLibraries
from armi.nuclearDataIO.cccc import gamiso, isotxs
from armi.nuclearDataIO.xsNuclides import XSNuclide
from armi.utils.directoryChangers import TemporaryDirectoryChanger

THIS_DIR = os.path.dirname(__file__)
FIXTURE_DIR = os.path.join(THIS_DIR, "..", "..", "tests", "fixtures")
GAMISO_AA = os.path.join(FIXTURE_DIR, "AA.gamiso")


class TestGamiso(unittest.TestCase):
    def setUp(self):
        self.xsLib = xsLibraries.IsotxsLibrary()

    def test_compare(self):
        """Compare the input binary GAMISO file.

        .. test:: Test reading GAMISO files.
            :id: T_ARMI_NUCDATA_GAMISO0
            :tests: R_ARMI_NUCDATA_GAMISO
        """
        gamisoAA = gamiso.readBinary(GAMISO_AA)
        self.xsLib.merge(deepcopy(gamisoAA))
        self.assertTrue(gamiso.compare(self.xsLib, gamisoAA))

    def test_writeBinary(self):
        """Write a binary GAMISO file.

        .. test:: Test writing GAMISO files.
            :id: T_ARMI_NUCDATA_GAMISO1
            :tests: R_ARMI_NUCDATA_GAMISO
        """
        with TemporaryDirectoryChanger():
            data = gamiso.readBinary(GAMISO_AA)
            binData = gamiso.writeBinary(data, "gamiso.out")
            self.assertTrue(gamiso.compare(data, binData))

    def test_addDummyNuclidesToLibrary(self):
        dummyNuclides = [XSNuclide(None, "U238AA")]
        before = self.xsLib.getNuclides("")
        self.assertEqual(len(self.xsLib.xsIDs), 0)
        self.assertTrue(gamiso.addDummyNuclidesToLibrary(self.xsLib, dummyNuclides))
        self.assertEqual(len(self.xsLib.xsIDs), 1)
        self.assertEqual(list(self.xsLib.xsIDs)[0], "38")

        after = self.xsLib.getNuclides("")
        self.assertGreater(len(after), len(before))

        diff = set(after).difference(set(before))
        self.assertEqual(len(diff), 1)
        self.assertEqual(list(diff)[0].xsId, "38")

    def test_addDummyNuclidesToLibraryNumGroups(self):
        isoLib = isotxs.readBinary(os.path.join(FIXTURE_DIR, "ISOAA"))
        gamLib = gamiso.readBinary(GAMISO_AA)
        gamLib.gamisoMetadata["numGroups"] = 50
        dummyNuc = XSNuclide(isoLib, "DMP1AA")
        dummyNuc.isotxsMetadata = isoLib.getNuclides("AA")[0].isotxsMetadata
        gamiso.addDummyNuclidesToLibrary(gamLib, [dummyNuc])
        self.assertEqual(gamLib["DMP1AA"].nucLabel, "DMP1")
        self.assertEqual(gamLib["DMP1AA"].gamisoMetadata["jband"][(49, 3)], 1)
