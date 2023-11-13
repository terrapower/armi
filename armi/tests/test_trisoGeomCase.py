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
import math

from armi.utils import directoryChangers
from armi.tests import TEST_ROOT
from armi.reactor.flags import Flags
from armi.reactor import geometry
from armi import settings
from armi.reactor import reactors
from armi import operators
from armi.bookkeeping import db
from armi.materials.uZr import UZr

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

        self.trisoBlock = self.o.r.core[-1][0]
        self.trisoComponent = self.trisoBlock[0]
        self.blockHeight = self.trisoBlock.getHeight()
        self.expectedSingleCompactVolume = (
            self.blockHeight * math.pi * 1.2446**2 / 4.0
        )
        self.blendFrac = 0.7
        self.kernel = self.trisoComponent[0]
        self.opyc = self.trisoComponent[-1]
        self.compactMult = 2.0
        self.expectedSingleCompactVolume = (
            self.blockHeight * math.pi * 1.2446**2 / 4.0
        )
        self.singleParticleVolume = 4.0 / 3.0 * math.pi * (self.opyc.p.od / 2) ** 3
        self.expectedKernelFrac = 0.010625**3 / 0.021125**3

    def test_triso_has_components(self):
        self.assertEqual(len(list(self.trisoComponent.iterComponents())), 5)
        self.assertGreater(self.trisoComponent.getMass("U235"), 0.0)
        self.assertGreater(self.trisoBlock.getMass("U235"), 0.0)

        # ensure all uranium is in the triso compact
        uraniumMass = self.trisoBlock.getMass("U")
        self.assertAlmostEqual(uraniumMass, self.trisoComponent.getMass("U"))

    def test_background_component_has_mass(self):
        """
        Make sure composition is blended as expected

        ensure the mass of the background component gets picked up
        (in this test only the triso compact component has any Graphite)
        """
        blockCMass = self.trisoBlock.getMass("C")
        compactCMass = self.trisoComponent.getMass("C")
        self.assertGreater(compactCMass, 0.0)
        self.assertGreater(blockCMass, 0.0)
        self.assertEqual(blockCMass, compactCMass)

    def test_particle_mult(self):
        """Make sure triso mult gets computed as expected"""
        # check inferred mult.
        # if the compact is supposed to be 70% triso particles by volume,
        # how many trisos should be in one of them (ignoring compact mult)?
        expectedMult = (
            self.expectedSingleCompactVolume
            * self.blendFrac
            / self.singleParticleVolume
        )
        self.assertAlmostEqual(expectedMult, self.kernel.p.mult)

    def test_particle_volume(self):

        expectedParticleVolume = self.expectedSingleCompactVolume * self.blendFrac
        actualParticleVolume = sum([c.getVolume() for c in self.trisoComponent])
        self.assertAlmostEqual(expectedParticleVolume, actualParticleVolume)

        # u vol frac within one particle
        actualKernelFrac = self.kernel.p.od**3 / self.opyc.p.od**3
        self.assertAlmostEqual(self.t guiexpectedKernelFrac, actualKernelFrac)

    def test_check_particle_mass(self):
        # mults need to cascade as well. So if you're looking at a single kernel
        # it should have a mult within that compact, but the compact can
        # also have a mult (e.g. representing number of pins) that needs
        # to be applied properly.
        uraniumMass = self.trisoBlock.getMass("U")

        rho = UZr().density(Tc=600)
        expectedUraniumMass = (
            rho
            * 0.9
            * self.expectedSingleCompactVolume
            * self.blendFrac
            * self.expectedKernelFrac
            * self.compactMult
        )
        self.assertAlmostEqual(expectedUraniumMass, uraniumMass)

        self.assertAlmostEqual(uraniumMass, self.kernel.getMass("U") * self.compactMult)

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

        dbPath = dbi.database._fullPath

        # read
        dbo = db.databaseFactory(dbPath, permission="r")
        with dbo:
            r = dbo.load(0, 0)

        # verify
        self.assertEqual(r.core.geomType, geometry.GeomType.HEX)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
