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
Tests some capabilities of the fuel handling machine.

This test is high enough level that it requires input files to be present. The ones to use
are called armiRun.yaml which is located in armi.tests
"""
import copy
import os
import unittest

import armi.physics.fuelCycle.fuelHandlers as fuelHandlers
from armi.reactor import assemblies
from armi.reactor import blocks
from armi.reactor import components
import armi.reactor.tests.test_reactors as testReactor
from armi.tests import TEST_ROOT
from armi.utils import directoryChangers
from armi.reactor import grids
from armi.reactor.flags import Flags
from armi.tests import ArmiTestHelper
from armi.settings import caseSettings
from armi.physics import fuelCycle


class TestFuelHandler(ArmiTestHelper):
    @classmethod
    def setUpClass(cls):
        # prepare the input files. This is important so the unit tests run from wherever
        # they need to run from.
        cls.directoryChanger = directoryChangers.DirectoryChanger(
            TEST_ROOT, dumpOnException=False
        )
        cls.directoryChanger.open()

    @classmethod
    def tearDownClass(cls):
        cls.directoryChanger.close()

    def setUp(self):
        r"""
        Build a dummy reactor without using input files. There are some igniters and feeds
        but none of these have any number densities.
        """

        self.o, self.r = testReactor.loadTestReactor(self.directoryChanger.destination)
        self.nfeed = len(self.r.core.getAssemblies(Flags.FEED))
        self.nigniter = len(self.r.core.getAssemblies(Flags.IGNITER))
        self.nSfp = len(self.r.core.sfp)

        # generate a reactor with assemblies
        # generate components with materials
        nPins = 271

        fuelDims = {"Tinput": 273.0, "Thot": 273.0, "od": 1.0, "id": 0.0, "mult": nPins}
        fuel = components.Circle("fuel", "UZr", **fuelDims)

        cladDims = {"Tinput": 273.0, "Thot": 273.0, "od": 1.1, "id": 1.0, "mult": nPins}
        clad = components.Circle("clad", "HT9", **cladDims)

        interDims = {
            "Tinput": 273.0,
            "Thot": 273.0,
            "op": 16.8,
            "ip": 16.0,
            "mult": 1.0,
        }
        interSodium = components.Hexagon("interCoolant", "Sodium", **interDims)

        # generate a block
        self.block = blocks.HexBlock("TestHexBlock", self.o.cs)
        self.block.setType("fuel")
        self.block.setHeight(10.0)
        self.block.addComponent(fuel)
        self.block.addComponent(clad)
        self.block.addComponent(interSodium)

        # generate an assembly
        self.assembly = assemblies.HexAssembly("TestAssemblyType")
        self.assembly.spatialGrid = grids.axialUnitGrid(1)
        for _ in range(1):
            self.assembly.add(copy.deepcopy(self.block))

        # copy the assembly to make a list of assemblies and have a reference assembly
        self.aList = []
        for _ in range(6):
            self.aList.append(copy.deepcopy(self.assembly))

        self.refAssembly = copy.deepcopy(self.assembly)
        self.directoryChanger.open()

    def tearDown(self):
        # clean up the test
        self.block = None
        self.assembly = None
        self.aList = None
        self.refAssembly = None
        self.r = None
        self.o = None

        self.directoryChanger.close()

    def test_FindHighBu(self):
        a = self.r.core.whichAssemblyIsIn(5, 4)
        # set burnup way over 1.0, which is otherwise the highest bu in the core
        a[0].p.percentBu = 10

        fh = fuelHandlers.FuelHandler(self.o)
        a1 = fh.findAssembly(
            param="percentBu", compareTo=100, blockLevelMax=True, typeSpec=None
        )
        self.assertEqual(
            a,
            a1,
            "The high burnup assembly {0} is not the expected one {1}".format(a, a1),
        )

    def test_Width(self):
        """Tests the width capability of findAssembly."""

        fh = fuelHandlers.FuelHandler(self.o)
        # instantiate reactor power. more power in more outer rings
        for ring, power in zip(range(1, 8), range(10, 80, 10)):
            aList = self.r.core.whichAssemblyIsIn(ring)
            for a in aList:
                for b in a:
                    b.p.power = power

        paramName = "power"
        # 1 ring outer and inner from ring 3
        a = fh.findAssembly(
            targetRing=3,
            width=(1, 0),
            param=paramName,
            blockLevelMax=True,
            compareTo=100,
        )
        ring = a.spatialLocator.getRingPos()[0]
        self.assertEqual(
            ring,
            4,
            "The highest power ring returned is {0}. It should be {1}".format(ring, 4),
        )
        a = fh.findAssembly(
            targetRing=3, width=(1, 0), param=paramName, blockLevelMax=True, compareTo=0
        )
        ring = a.spatialLocator.getRingPos()[0]
        self.assertEqual(
            ring,
            2,
            "The lowest power ring returned is {0}. It should be {1}".format(ring, 2),
        )

        # 2 rings outer from ring 3
        a = fh.findAssembly(
            targetRing=3,
            width=(2, 1),
            param=paramName,
            blockLevelMax=True,
            compareTo=100,
        )
        ring = a.spatialLocator.getRingPos()[0]
        self.assertEqual(
            ring,
            5,
            "The highest power ring returned is {0}. It should be {1}".format(ring, 5),
        )
        a = fh.findAssembly(
            targetRing=3, width=(2, 1), param=paramName, blockLevelMax=True, compareTo=0
        )
        ring = a.spatialLocator.getRingPos()[0]
        self.assertEqual(
            ring,
            3,
            "The lowest power ring returned is {0}. It should be {1}".format(ring, 3),
        )

        # 2 rings inner from ring 3
        a = fh.findAssembly(
            targetRing=3,
            width=(2, -1),
            param=paramName,
            blockLevelMax=True,
            compareTo=100,
        )
        ring = a.spatialLocator.getRingPos()[0]
        self.assertEqual(
            ring,
            3,
            "The highest power ring returned is {0}. It should be {1}".format(ring, 3),
        )
        a = fh.findAssembly(
            targetRing=3,
            width=(2, -1),
            param=paramName,
            blockLevelMax=True,
            compareTo=0,
        )
        ring = a.spatialLocator.getRingPos()[0]
        self.assertEqual(
            ring,
            1,
            "The lowest power ring returned is {0}. It should be {1}".format(ring, 1),
        )

    def test_FindMany(self):
        r"""
        Tests the findMany and type aspects of the fuel handler
        """

        fh = fuelHandlers.FuelHandler(self.o)

        igniters = fh.findAssembly(typeSpec=Flags.IGNITER | Flags.FUEL, findMany=True)
        feeds = fh.findAssembly(typeSpec=Flags.FEED | Flags.FUEL, findMany=True)
        fewFeeds = fh.findAssembly(
            typeSpec=Flags.FEED | Flags.FUEL, findMany=True, maxNumAssems=4
        )

        self.assertEqual(
            len(igniters),
            self.nigniter,
            "Found {0} igniters. Should have found {1}".format(
                len(igniters), self.nigniter
            ),
        )
        self.assertEqual(
            len(feeds),
            self.nfeed,
            "Found {0} feeds. Should have found {1}".format(len(igniters), self.nfeed),
        )
        self.assertEqual(
            len(fewFeeds),
            4,
            "Reduced findMany returned {0} assemblies instead of {1}"
            "".format(len(fewFeeds), 4),
        )

    def test_findInSFP(self):
        r"""
        Tests ability to pull from the spent fuel pool.
        """
        fh = fuelHandlers.FuelHandler(self.o)
        spent = fh.findAssembly(
            findMany=True,
            findFromSfp=True,
            param="percentBu",
            compareTo=100,
            blockLevelMax=True,
        )
        self.assertEqual(
            len(spent),
            self.nSfp,
            "Found {0} assems in SFP. Should have found {1}".format(
                len(spent), self.nSfp
            ),
        )
        burnups = [a.getMaxParam("percentBu") for a in spent]
        bu = spent[0].getMaxParam("percentBu")
        self.assertEqual(
            bu,
            max(burnups),
            "First assembly does not have the "
            "highest burnup ({0}). It has ({1})".format(max(burnups), bu),
        )

    def runShuffling(self, fh):
        """Shuffle fuel and write out a SHUFFLES.txt file."""
        fh.attachReactor(self.o, self.r)
        # so we don't overwrite the version-controlled armiRun-SHUFFLES.txt
        self.o.cs.caseTitle = "armiRun2"
        fh.interactBOL()

        for cycle in range(3):
            self.r.p.cycle = cycle
            fh.cycle = cycle
            fh.manageFuel(cycle)
            for a in self.r.core.sfp.getChildren():
                self.assertEqual(a.getLocation(), "SFP")
        fh.interactEOL()

    def test_buildEqRingScheduleHelper(self):

        fh = fuelHandlers.FuelHandler(self.o)

        ringList1 = [1, 5]
        buildRing1 = fh.buildEqRingScheduleHelper(ringList1)
        self.assertEqual(buildRing1, [1, 2, 3, 4, 5])

        ringList2 = [1, 5, 9, 6]
        buildRing2 = fh.buildEqRingScheduleHelper(ringList2)
        self.assertEqual(buildRing2, [1, 2, 3, 4, 5, 9, 8, 7, 6])

        ringList3 = [9, 5, 3, 4, 1, 2]
        buildRing3 = fh.buildEqRingScheduleHelper(ringList3)
        self.assertEqual(buildRing3, [9, 8, 7, 6, 5, 3, 4, 1, 2])

        ringList4 = [2, 5, 1, 1]
        buildRing1 = fh.buildEqRingScheduleHelper(ringList4)
        self.assertEqual(buildRing1, [2, 3, 4, 5, 1])

    def test_repeatShuffles(self):
        r"""
        Builds a dummy core. Does some shuffles. Repeats the shuffles. Checks that it was a perfect repeat.

        Checks some other things in the meantime

        See Also
        --------
        runShuffling : creates the shuffling file to be read in.
        """

        # check labels before shuffling:
        for a in self.r.core.sfp.getChildren():
            self.assertEqual(a.getLocation(), "SFP")

        # do some shuffles.
        fh = self.r.o.getInterface("fuelHandler")
        self.runShuffling(fh)  # changes caseTitle

        # make sure the generated shuffles file matches the tracked one.
        # This will need to be updated if/when more assemblies are added to the test reactor
        # but must be done carefully. Do not blindly rebaseline this file.
        self.compareFilesLineByLine("armiRun-SHUFFLES.txt", "armiRun2-SHUFFLES.txt")

        # store locations of each assembly
        firstPassResults = {}
        for a in self.r.core.getAssemblies():
            firstPassResults[a.getLocation()] = a.getName()
            self.assertNotIn(a.getLocation(), ["SFP", "LoadQueue", "ExCore"])

        # reset core to BOL state
        # reset assembly counter to get the same assem nums.
        self.setUp()
        self.o.cs["plotShuffleArrows"] = True
        # now repeat shuffles
        self.o.cs[
            "explicitRepeatShuffles"
        ] = "armiRun-SHUFFLES.txt"  # signals repeat shuffles

        fh = self.r.o.getInterface("fuelHandler")

        self.runShuffling(fh)

        # make sure the shuffle was repeated perfectly.
        for a in self.r.core.getAssemblies():
            self.assertEqual(a.getName(), firstPassResults[a.getLocation()])
        for a in self.r.core.sfp.getChildren():
            self.assertEqual(a.getLocation(), "SFP")

        if os.path.exists("armiRun2-SHUFFLES.txt"):
            # sometimes pytest runs two of these at once.
            os.remove("armiRun2-SHUFFLES.txt")

        restartFileName = "armiRun2.restart.dat"
        if os.path.exists(restartFileName):
            os.remove(restartFileName)
        for i in range(3):
            fname = f"armiRun2.shuffles_{i}.png"
            if os.path.exists(fname):
                os.remove(fname)

    def test_readMoves(self):
        """
        Depends on the shuffleLogic created by repeatShuffles

        See Also
        --------
        runShuffling : creates the shuffling file to be read in.
        """
        numblocks = len(self.r.core.getFirstAssembly())
        fh = fuelHandlers.FuelHandler(self.o)
        moves = fh.readMoves("armiRun-SHUFFLES.txt")
        self.assertEqual(len(moves), 3)
        firstMove = moves[1][0]
        self.assertEqual(firstMove[0], "A2001")
        self.assertEqual(firstMove[1], "SFP")
        self.assertEqual(len(firstMove[2]), numblocks)
        self.assertEqual(firstMove[3], "igniter fuel")
        self.assertEqual(firstMove[4], None)

        # check the move that came back out of the SFP
        sfpMove = moves[2][-2]
        self.assertEqual(sfpMove[0], "SFP")
        self.assertEqual(sfpMove[1], "A5003")
        self.assertEqual(sfpMove[4], "A0089")  # name of assem in SFP

    def test_processMoveList(self):
        fh = fuelHandlers.FuelHandler(self.o)
        moves = fh.readMoves("armiRun-SHUFFLES.txt")
        (
            loadChains,
            loopChains,
            enriches,
            loadChargeTypes,
            loadNames,
            alreadyDone,
        ) = fh.processMoveList(moves[2])
        self.assertIn("A0089", loadNames)
        self.assertIn(None, loadNames)
        self.assertNotIn("SFP", loadChains)
        self.assertNotIn("LoadQueue", loadChains)
        self.assertFalse(loopChains)


class TestFuelPlugin(unittest.TestCase):
    """Tests that make sure the plugin is being discovered well."""

    def test_settingsAreDiscovered(self):
        cs = caseSettings.Settings()
        nm = fuelCycle.CONF_CIRCULAR_RING_ORDER
        self.assertEqual(cs[nm], "angle")

        setting = cs.settings[nm]
        self.assertIn("distance", setting.options)


if __name__ == "__main__":
    # import sys; sys.argv = ['', 'TestFuelHandler.test_repeatShuffles']
    unittest.main()
