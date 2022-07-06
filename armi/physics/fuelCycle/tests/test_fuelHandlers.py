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
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import collections
import copy
import os
import unittest

import numpy as np

from armi.physics.fuelCycle import fuelHandlers, settings
from armi.reactor import assemblies, blocks, components, grids
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.settings import caseSettings
from armi.tests import ArmiTestHelper, TEST_ROOT
from armi.utils import directoryChangers


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
        self.o, self.r = test_reactors.loadTestReactor(
            self.directoryChanger.destination,
            customSettings={"nCycles": 3, "trackAssems": True},
        )

        blockList = self.r.core.getBlocks()
        for bi, b in enumerate(blockList):
            b.p.flux = 5e10
            if b.isFuel():
                b.p.percentBu = 30.0 * bi / len(blockList)
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
        self.block = blocks.HexBlock("TestHexBlock")
        self.block.setType("fuel")
        self.block.setHeight(10.0)
        self.block.add(fuel)
        self.block.add(clad)
        self.block.add(interSodium)

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

    def test_findHighBu(self):
        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(5, 4)
        a = self.r.core.childrenByLocator[loc]
        # set burnup way over 1.0, which is otherwise the highest bu in the core
        a[0].p.percentBu = 50

        fh = fuelHandlers.FuelHandler(self.o)
        a1 = fh.findAssembly(
            param="percentBu", compareTo=100, blockLevelMax=True, typeSpec=None
        )
        self.assertIs(a, a1)

    def test_width(self):
        """Tests the width capability of findAssembly."""
        fh = fuelHandlers.FuelHandler(self.o)
        assemsByRing = collections.defaultdict(list)
        for a in self.r.core.getAssemblies():
            assemsByRing[a.spatialLocator.getRingPos()[0]].append(a)

        # instantiate reactor power. more power in more outer rings
        for ring, power in zip(range(1, 8), range(10, 80, 10)):
            aList = assemsByRing[ring]
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

    def test_findMany(self):
        """Tests the findMany and type aspects of the fuel handler"""
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
        """Tests ability to pull from the spent fuel pool"""
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

    def test_findByCoords(self):
        fh = fuelHandlers.FuelHandler(self.o)
        assem = fh.findAssembly(coords=(0, 0))
        self.assertIs(assem, self.o.r.core[0])

    def test_findWithMinMax(self):
        """Test the complex min/max comparators."""
        fh = fuelHandlers.FuelHandler(self.o)
        assem = fh.findAssembly(
            param="percentBu",
            compareTo=100,
            blockLevelMax=True,
            minParam="percentBu",
            minVal=("percentBu", 0.1),
            maxParam="percentBu",
            maxVal=20.0,
        )
        # the burnup should be the maximum bu within
        # up to a burnup of 20%, which by the simple
        # dummy data layout should be the 2/3rd block in the blocklist
        bs = self.r.core.getBlocks(Flags.FUEL)
        lastB = None
        for b in bs:
            if b.p.percentBu > 20:
                break
            lastB = b
        expected = lastB.parent
        self.assertIs(assem, expected)

        # test the impossible: an block with burnup less than
        # 110% of its own burnup
        assem = fh.findAssembly(
            param="percentBu",
            compareTo=100,
            blockLevelMax=True,
            minParam="percentBu",
            minVal=("percentBu", 1.1),
        )
        self.assertIsNone(assem)

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

        newSettings = {"plotShuffleArrows": True}
        # now repeat shuffles
        newSettings["explicitRepeatShuffles"] = "armiRun-SHUFFLES.txt"
        self.o.cs = self.o.cs.modified(newSettings=newSettings)

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
        self.assertEqual(firstMove[0], "002-001")
        self.assertEqual(firstMove[1], "SFP")
        self.assertEqual(len(firstMove[2]), numblocks)
        self.assertEqual(firstMove[3], "igniter fuel")
        self.assertEqual(firstMove[4], None)

        # check the move that came back out of the SFP
        sfpMove = moves[2][-2]
        self.assertEqual(sfpMove[0], "SFP")
        self.assertEqual(sfpMove[1], "005-003")
        self.assertEqual(sfpMove[4], "A0085")  # name of assem in SFP

    def test_processMoveList(self):
        fh = fuelHandlers.FuelHandler(self.o)
        moves = fh.readMoves("armiRun-SHUFFLES.txt")
        (
            loadChains,
            loopChains,
            _,
            _,
            loadNames,
            _,
        ) = fh.processMoveList(moves[2])
        self.assertIn("A0085", loadNames)
        self.assertIn(None, loadNames)
        self.assertNotIn("SFP", loadChains)
        self.assertNotIn("LoadQueue", loadChains)
        self.assertFalse(loopChains)

    def test_getFactorList(self):
        fh = fuelHandlers.FuelHandler(self.o)
        factors, _ = fh.getFactorList(0)
        self.assertIn("eqShuffles", factors)

    def test_simpleAssemblyRotation(self):
        fh = fuelHandlers.FuelHandler(self.o)
        newSettings = {"assemblyRotationStationary": True}
        self.o.cs = self.o.cs.modified(newSettings=newSettings)
        hist = self.o.getInterface("history")
        assems = hist.o.r.core.getAssemblies(Flags.FUEL)[:5]
        addSomeDetailAssemblies(hist, assems)
        b = self.o.r.core.getFirstBlock(Flags.FUEL)
        rotNum = b.getRotationNum()
        fh.simpleAssemblyRotation()
        fh.simpleAssemblyRotation()
        self.assertEqual(b.getRotationNum(), rotNum + 2)

    def test_linPowByPin(self):
        fh = fuelHandlers.FuelHandler(self.o)
        hist = self.o.getInterface("history")
        newSettings = {"assemblyRotationStationary": True}
        self.o.cs = self.o.cs.modified(newSettings=newSettings)
        assem = self.o.r.core.getFirstAssembly(Flags.FUEL)
        b = assem.getBlocks(Flags.FUEL)[0]

        b.p.linPowByPin = [1, 2, 3]
        self.assertEqual(type(b.p.linPowByPin), np.ndarray)

        b.p.linPowByPin = np.array([1, 2, 3])
        self.assertEqual(type(b.p.linPowByPin), np.ndarray)

    def test_linPowByPinNeutron(self):
        fh = fuelHandlers.FuelHandler(self.o)
        hist = self.o.getInterface("history")
        newSettings = {"assemblyRotationStationary": True}
        self.o.cs = self.o.cs.modified(newSettings=newSettings)
        assem = self.o.r.core.getFirstAssembly(Flags.FUEL)
        b = assem.getBlocks(Flags.FUEL)[0]

        b.p.linPowByPinNeutron = [1, 2, 3]
        self.assertEqual(type(b.p.linPowByPinNeutron), np.ndarray)

        b.p.linPowByPinNeutron = np.array([1, 2, 3])
        self.assertEqual(type(b.p.linPowByPinNeutron), np.ndarray)

    def test_linPowByPinGamma(self):
        fh = fuelHandlers.FuelHandler(self.o)
        hist = self.o.getInterface("history")
        newSettings = {"assemblyRotationStationary": True}
        self.o.cs = self.o.cs.modified(newSettings=newSettings)
        assem = self.o.r.core.getFirstAssembly(Flags.FUEL)
        b = assem.getBlocks(Flags.FUEL)[0]

        b.p.linPowByPinGamma = [1, 2, 3]
        self.assertEqual(type(b.p.linPowByPinGamma), np.ndarray)

        b.p.linPowByPinGamma = np.array([1, 2, 3])
        self.assertEqual(type(b.p.linPowByPinGamma), np.ndarray)

    def test_buReducingAssemblyRotation(self):
        fh = fuelHandlers.FuelHandler(self.o)
        hist = self.o.getInterface("history")
        newSettings = {"assemblyRotationStationary": True}
        self.o.cs = self.o.cs.modified(newSettings=newSettings)
        assem = self.o.r.core.getFirstAssembly(Flags.FUEL)

        # apply dummy pin-level data to allow intelligent rotation
        for b in assem.getBlocks(Flags.FUEL):
            b.breakFuelComponentsIntoIndividuals()
            b.initializePinLocations()
            b.p.percentBuMaxPinLocation = 10
            b.p.percentBuMax = 5
            b.p.linPowByPin = list(reversed(range(b.getNumPins())))

        addSomeDetailAssemblies(hist, [assem])
        rotNum = b.getRotationNum()
        fh.buReducingAssemblyRotation()
        self.assertNotEqual(b.getRotationNum(), rotNum)

    def test_buildRingSchedule(self):
        fh = fuelHandlers.FuelHandler(self.o)

        # simple divergent
        schedule, widths = fh.buildRingSchedule(1, 9)
        self.assertEqual(schedule, [9, 8, 7, 6, 5, 4, 3, 2, 1])

        # simple with no jumps
        schedule, widths = fh.buildRingSchedule(9, 1, jumpRingTo=1)
        self.assertEqual(schedule, [1, 2, 3, 4, 5, 6, 7, 8, 9])

        # simple with 1 jump
        schedule, widths = fh.buildRingSchedule(9, 1, jumpRingFrom=6)
        self.assertEqual(schedule, [5, 4, 3, 2, 1, 6, 7, 8, 9])
        self.assertEqual(widths, [0, 0, 0, 0, 0, 0, 0, 0, 0])

        # 1 jump plus auto-correction to core size
        schedule, widths = fh.buildRingSchedule(1, 17, jumpRingFrom=5)
        self.assertEqual(schedule, [6, 7, 8, 9, 5, 4, 3, 2, 1])
        self.assertEqual(widths, [0, 0, 0, 0, 0, 0, 0, 0, 0])

        # crash on invalid jumpring
        with self.assertRaises(ValueError):
            schedule, widths = fh.buildRingSchedule(1, 17, jumpRingFrom=0)

        # test 4: Mid way jumping
        schedule, widths = fh.buildRingSchedule(1, 9, jumpRingTo=6, jumpRingFrom=3)
        self.assertEqual(schedule, [9, 8, 7, 4, 5, 6, 3, 2, 1])

    def test_buildConvergentRingSchedule(self):
        fh = fuelHandlers.FuelHandler(self.o)
        schedule, widths = fh.buildConvergentRingSchedule(17, 1)
        self.assertEqual(schedule, [1, 17])
        self.assertEqual(widths, [16, 1])

    def test_buildEqRingSchedule(self):
        fh = fuelHandlers.FuelHandler(self.o)
        locSchedule = fh.buildEqRingSchedule([2, 1])
        self.assertEqual(locSchedule, ["002-001", "002-002", "001-001"])

        fh.cs["circularRingOrder"] = "distanceSmart"
        locSchedule = fh.buildEqRingSchedule([2, 1])
        self.assertEqual(locSchedule, ["002-001", "002-002", "001-001"])

        fh.cs["circularRingOrder"] = "somethingCrazy"
        locSchedule = fh.buildEqRingSchedule([2, 1])
        self.assertEqual(locSchedule, ["002-001", "002-002", "001-001"])

    def test_swapFluxParamSameLength(self):
        """
        Test the _swapFluxParams method for the usual case,
        where each of the input assembles have the same number of assemblies,
        on the same mesh
        """
        # grab the assemblies
        assems = self.r.core.getAssemblies(Flags.FEED)
        self.assertEqual(len(assems), 14)

        for a in assems:
            self.assertEqual(len(a.getBlocks()), 5)

        # make two copies of an arbitraty assembly
        a1 = copy.deepcopy(list(assems)[1])
        a2 = copy.deepcopy(list(assems)[1])
        blocks1 = list(a1.getBlocks())
        blocks2 = list(a2.getBlocks())
        self.assertEqual(len(blocks1), 5)
        self.assertEqual(len(blocks2), 5)
        self.assertEqual(blocks1[3].p.height, 25)
        self.assertEqual(blocks2[3].p.height, 25)

        # 1. alter the values of a single block in assembly 2
        b2 = list(blocks2)[1]
        b2.p.flux = b2.p.flux * 2
        b2.p.power = 1000
        b2.p.pdens = b2.p.power / b2.getVolume()

        # grab the power before the swap
        power1 = sum([b.p.power for b in a1.getBlocks()])
        power2 = sum([b.p.power for b in a2.getBlocks()])

        # 2. validate the situation is as you'd expect
        self.assertEqual(list(a1.getBlocks())[1].p.flux, 50000000000.0)
        self.assertEqual(list(a2.getBlocks())[1].p.flux, 100000000000.0)
        self.assertEqual(list(a1.getBlocks())[1].p.power, 0.0)
        self.assertEqual(list(a2.getBlocks())[1].p.power, 1000.0)
        self.assertEqual(list(a1.getBlocks())[1].p.pdens, 0.0)
        self.assertGreater(list(a2.getBlocks())[1].p.pdens, 0.0)

        # 3. do the swap
        fh = fuelHandlers.FuelHandler(self.o)
        fh._swapFluxParam(a1, a2)

        # 4. validate the swap worked
        self.assertEqual(list(a1.getBlocks())[1].p.flux, 100000000000.0)
        self.assertEqual(list(a2.getBlocks())[1].p.flux, 50000000000.0)
        self.assertEqual(list(a1.getBlocks())[1].p.power, 1000.0)
        self.assertEqual(list(a2.getBlocks())[1].p.power, 0.0)
        self.assertGreater(list(a1.getBlocks())[1].p.pdens, 0.0)
        self.assertEqual(list(a2.getBlocks())[1].p.pdens, 0.0)
        self.assertEqual(sum([b.p.power for b in a1.getBlocks()]), power2)
        self.assertEqual(sum([b.p.power for b in a2.getBlocks()]), power1)

    def test_swapFluxParamDifferentLengths(self):
        """
        Test the _swapFluxParams method for the less common, and more complicated case,
        where the input assembles have different numbers of blocks, potentially on
        wildly different point meshes.
        """
        # grab the assemblies
        assems = self.r.core.getAssemblies(Flags.FEED)

        # make two copies of an arbitraty assembly
        a1 = copy.deepcopy(list(assems)[1])
        a2 = copy.deepcopy(list(assems)[1])
        height2 = 25.0
        self.assertEqual(list(a1.getBlocks())[3].p.height, height2)
        self.assertEqual(list(a2.getBlocks())[3].p.height, height2)

        # grab the blocks from the second assembly
        blocks2 = list(a2.getBlocks())
        self.assertEqual(len(blocks2), 5)

        # grab a single block from the second assembly, to be altered
        b2 = list(blocks2)[1]
        self.assertEqual(b2.p.height, height2)
        self.assertEqual(b2.p.flux, 50000000000.0)
        self.assertIsNone(b2.p.mgFlux)
        self.assertEqual(b2.p.power, 0.0)
        self.assertEqual(b2.p.pdens, 0.0)
        volume2 = 6074.356
        self.assertAlmostEqual(b2.getVolume(), volume2, delta=0.1)

        # split the the block into two of half the heights
        b20 = copy.deepcopy(b2)
        b21 = copy.deepcopy(b2)
        b20.setHeight(height2 / 2)
        b21.setHeight(height2 / 2)
        self.assertAlmostEqual(b20.getVolume(), volume2 / 2, delta=0.1)
        self.assertAlmostEqual(b21.getVolume(), volume2 / 2, delta=0.1)

        # give the two new (smaller) blocks some power/pdens
        b20.p.power = 1000
        b21.p.power = 2000
        b20.p.pdens = b20.p.power / b20.getVolume()
        b21.p.pdens = b21.p.power / b21.getVolume()
        self.assertEqual(b20.p.power, 1000.0)
        self.assertEqual(b21.p.power, 2000.0)
        self.assertAlmostEqual(b20.p.pdens, 0.3292, delta=0.1)
        self.assertAlmostEqual(b21.p.pdens, 0.6585, delta=0.1)

        # give the second assembly the new blocks
        a2.removeAll()
        a2.setChildren([blocks2[0]] + [b20, b21] + blocks2[2:])

        # validate the situation is as you'd expect
        self.assertEqual(len(a1.getBlocks()), 5)
        self.assertEqual(len(a2.getBlocks()), 6)

        # validate the power before the swap
        power1 = [b.p.power for b in a1.getBlocks()]
        power2 = [b.p.power for b in a2.getBlocks()]

        self.assertEqual(power1, [0, 0, 0, 0, 0])
        self.assertEqual(power2, [0, 1000, 2000, 0, 0, 0])

        # validate the power density before the swap
        for b in a1.getBlocks():
            self.assertEqual(b.p.pdens, 0.0)

        pdens2i = [0, 0.32925299379047496, 0.6585059875809499, 0, 0, 0]
        for i, b in enumerate(a2.getBlocks()):
            self.assertAlmostEqual(b.p.pdens, pdens2i[i], msg=i)

        # validate the flux before the swap
        for b in a1.getBlocks():
            self.assertEqual(b.p.flux, 50000000000.0)

        for b in a2.getBlocks():
            self.assertEqual(b.p.flux, 50000000000.0)

        # do the swap, using averages
        fh = fuelHandlers.FuelHandler(self.o)
        fh._swapFluxParam(a1, a2)

        # grab the power after the swap
        power1f = [b.p.power for b in a1.getBlocks()]
        power2f = [b.p.power for b in a2.getBlocks()]

        # validate the swap worked
        self.assertEqual(len(a1.getBlocks()), 5)
        self.assertEqual(len(a2.getBlocks()), 6)

        self.assertEqual(power1f, [0, 3000, 0, 0, 0])
        self.assertEqual(power2f, [0, 0, 0, 0, 0, 0])

        # validate the power density after the swap
        pdens1f = [0, 0.4938794906857124, 0, 0, 0]
        for i, b in enumerate(a1.getBlocks()):
            self.assertAlmostEqual(b.p.pdens, pdens1f[i], msg=i)

        for i, b in enumerate(a2.getBlocks()):
            self.assertAlmostEqual(b.p.pdens, 0, msg=i)

        # validate the flux after the swap
        for b in a1.getBlocks():
            self.assertEqual(b.p.flux, 50000000000.0)

        for b in a2.getBlocks():
            self.assertEqual(b.p.flux, 50000000000.0)


class TestFuelPlugin(unittest.TestCase):
    """Tests that make sure the plugin is being discovered well."""

    def test_settingsAreDiscovered(self):
        cs = caseSettings.Settings()
        nm = settings.CONF_CIRCULAR_RING_ORDER
        self.assertEqual(cs[nm], "angle")

        setting = cs.getSetting(nm)
        self.assertIn("distance", setting.options)


def addSomeDetailAssemblies(hist, assems):
    for a in assems:
        hist.detailAssemblyNames.append(a.getName())


if __name__ == "__main__":
    unittest.main()
