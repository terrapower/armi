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

"""
Tests that a case with Component Groups can load, write to DB, and then read from DB.

This test is intended to grow into a test of a TRISO fuel case as the capabilities
to support TRISO are added. It does not yet represent real TRISO.
"""
import unittest

from armi.utils import directoryChangers
from armi.tests import TEST_ROOT
from armi.reactor.flags import Flags
from armi.reactor import geometry
from armi import settings
from armi.reactor import reactors
from armi import operators
from armi.bookkeeping import db

TEST_NAME = "refTriso-settings.yaml"


class ComponentGroupReactorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directoryChanger = directoryChangers.DirectoryChanger(TEST_ROOT)
        cls.directoryChanger.open()

    @classmethod
    def tearDownClass(cls):
        cls.directoryChanger.close()

    def setUp(self):
        """
        Use the related setup in the testFuelHandlers module.
        """
        cs = settings.Settings(fName=TEST_NAME)
        self.o = operators.factory(cs)
        self.r = reactors.loadFromCs(cs)
        settings.setMasterCs(cs)
        self.o.initializeInterfaces(self.r)

    def test_particleFuel(self):
        """
        Make sure composition is blended as expected
        """
        triso = self.o.r.core[-1][0][0]
        self.assertEqual(len(list(triso.iterComponents())), 5)
        self.assertGreater(triso.getMass("U235"), 0.0)
        self.assertGreater(triso.getMass("C"), 0.0)

    def test_db(self):
        """Show that this kind of reactor configuration can write and load from DB"""
        # set some state
        assem = self.o.r.core.childrenByLocator[self.o.r.core.spatialGrid[8, 0, 0]]
        block = assem[0]
        block.p.flux = 1e15

        # write
        dbi = self.o.getInterface("database")
        dbi.initDB()
        dbi.database.writeToDB(self.o.r)

        # read
        dbo = db.databaseFactory(TEST_NAME.replace(".yaml", ".h5"), permission="r")
        with dbo:
            r = dbo.load(0, 0)

        # verify
        self.assertEqual(r.core.geomType, geometry.GeomType.HEX)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
