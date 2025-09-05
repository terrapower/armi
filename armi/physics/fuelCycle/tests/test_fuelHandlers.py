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

import collections
import copy
import os
import tempfile
import unittest
from unittest.mock import PropertyMock, patch

import numpy as np

from armi.physics.fuelCycle import fuelHandlers, settings
from armi.physics.fuelCycle.fuelHandlers import AssemblyMove
from armi.physics.fuelCycle.settings import (
    CONF_ASSEM_ROTATION_STATIONARY,
    CONF_ASSEMBLY_ROTATION_ALG,
    CONF_PLOT_SHUFFLE_ARROWS,
    CONF_RUN_LATTICE_BEFORE_SHUFFLING,
    CONF_SHUFFLE_SEQUENCE_FILE,
)
from armi.physics.neutronics.crossSectionGroupManager import CrossSectionGroupManager
from armi.physics.neutronics.latticePhysics.latticePhysicsInterface import (
    LatticePhysicsInterface,
)
from armi.reactor import assemblies, blocks, components, grids
from armi.reactor.flags import Flags
from armi.reactor.parameters import ParamLocation
from armi.reactor.tests import test_reactors
from armi.reactor.zones import Zone
from armi.settings import caseSettings
from armi.settings.fwSettings.globalSettings import CONF_TRACK_ASSEMS
from armi.tests import TEST_ROOT, ArmiTestHelper, mockRunLogs
from armi.utils import directoryChangers
from armi.utils.customExceptions import InputError


class TestReadMovesYamlErrors(unittest.TestCase):
    """Ensure malformed YAML inputs raise informative ``InputError``."""

    def _run(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
            tf.write(text)
            fname = tf.name
        try:
            fuelHandlers.FuelHandler.readMovesYaml(fname)
        finally:
            os.remove(fname)

    def test_missingSequence(self):
        yaml_text = "foo: []\n"
        with self.assertRaisesRegex(InputError, "sequence"):
            self._run(yaml_text)

    def test_duplicateCycle(self):
        yaml_text = "sequence:\n  1: []\n  1: []\n"
        with self.assertRaisesRegex(InputError, r"(?i)\bduplicate key\b"):
            self._run(yaml_text)

    def test_unknownActionKey(self):
        yaml_text = "sequence:\n  1:\n    - badAction: []\n"
        with self.assertRaisesRegex(InputError, "Unknown action"):
            self._run(yaml_text)

    def test_badCascade(self):
        cases = [
            ("sequence:\n  1:\n    - cascade: ['only']\n", "cascade"),
            ("sequence:\n  1:\n    - cascade: ['outer fuel', 1]\n", "cascade"),
        ]
        for yaml_text, msg in cases:
            with self.subTest(yaml_text=yaml_text):
                with self.assertRaisesRegex(InputError, msg):
                    self._run(yaml_text)

    def test_badMisloadSwap(self):
        yaml_text = "sequence:\n  1:\n    - misloadSwap: ['009-045']\n"
        with self.assertRaisesRegex(InputError, "misloadSwap"):
            self._run(yaml_text)

    def test_badFuelEnrichment(self):
        cases = [
            (
                """sequence:\n  1:\n    - cascade: ['outer fuel', '009-045']\n      fuelEnrichment: ['a']\n""",
                "fuelEnrichment",
            ),
            (
                """sequence:\n  1:\n    - cascade: ['outer fuel', '009-045']\n      fuelEnrichment: [-1]\n""",
                "fuelEnrichment",
            ),
            (
                """sequence:\n  1:\n    - cascade: ['outer fuel', '009-045']\n      fuelEnrichment: [101]\n""",
                "fuelEnrichment",
            ),
        ]
        for yaml_text, msg in cases:
            with self.subTest(yaml_text=yaml_text):
                with self.assertRaisesRegex(InputError, msg):
                    self._run(yaml_text)

    def test_rotationInvalidLocation(self):
        yaml_text = "sequence:\n  1:\n    - extraRotations: {'badLoc': 30}\n"
        with self.assertRaisesRegex(InputError, "Invalid location"):
            self._run(yaml_text)

    def test_duplicateCascadeLocation(self):
        yaml_text = (
            "sequence:\n  1:\n    - cascade: ['outer', '009-045', '008-001']\n"
            "    - cascade: ['outer', '009-045', '007-002']\n"
        )
        with self.assertRaisesRegex(InputError, "009-045"):
            self._run(yaml_text)

    def test_invalidCascadeLocation(self):
        yaml_text = "sequence:\n  1:\n    - cascade: ['outer', 'badLoc']\n"
        with self.assertRaisesRegex(InputError, "Invalid location"):
            self._run(yaml_text)

    def test_missingCycle(self):
        yaml_text = "sequence:\n  1: []\n  3: []\n"
        with self.assertRaisesRegex(InputError, "Missing cycle 2"):
            self._run(yaml_text)


class TestReadMovesYamlFeatures(unittest.TestCase):
    """Miscellaneous behavior of :meth:`FuelHandler.readMovesYaml`."""

    def _read(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
            tf.write(text)
            fname = tf.name
        try:
            moves, _ = fuelHandlers.FuelHandler.readMovesYaml(fname)
            return moves
        finally:
            os.remove(fname)

    def test_cyclesOutOfOrder(self):
        yaml_text = "sequence:\n  1: []\n  2: []\n  4: []\n  3: []\n"
        moves = self._read(yaml_text)
        self.assertEqual(list(moves), [1, 2, 4, 3])


class FuelHandlerTestHelper(ArmiTestHelper):
    @classmethod
    def setUpClass(cls):
        # prepare the input files. This is important so the unit tests run from wherever
        # they need to run from.
        cls.directoryChanger = directoryChangers.DirectoryChanger(TEST_ROOT, dumpOnException=False)
        cls.directoryChanger.open()

    @classmethod
    def tearDownClass(cls):
        cls.directoryChanger.close()

    def setUp(self):
        """
        Build a dummy reactor without using input files.

        There are some igniters and feeds but none of these have any number densities.
        """
        self.o, self.r = test_reactors.loadTestReactor(
            self.directoryChanger.destination,
            customSettings={"nCycles": 3, "trackAssems": True},
        )

        allBlocks = self.r.core.getBlocks()
        fakeBu = 30.0 / len(allBlocks)
        for bi, b in enumerate(allBlocks):
            b.p.flux = 5e10
            if b.isFuel():
                b.p.percentBu = fakeBu * bi
        self.nfeed = len(self.r.core.getAssemblies(Flags.FEED))
        self.nigniter = len(self.r.core.getAssemblies(Flags.IGNITER))
        self.nSfp = len(self.r.excore["sfp"])

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
        self.assembly.spatialGrid = grids.AxialGrid.fromNCells(1)
        for _ in range(1):
            self.assembly.add(copy.deepcopy(self.block))

        # copy the assembly to make a list of assemblies and have a reference assembly
        self.aList = []
        for _ in range(6):
            self.aList.append(copy.deepcopy(self.assembly))

        self.refAssembly = copy.deepcopy(self.assembly)
        self.directoryChanger.open()
        self.r.core.locateAllAssemblies()

    def tearDown(self):
        # clean up the test
        self.block = None
        self.assembly = None
        self.aList = None
        self.refAssembly = None
        self.r = None
        self.o = None

        self.directoryChanger.close()


class MockLatticePhysicsInterface(LatticePhysicsInterface):
    """A mock lattice physics interface that does nothing for interactBOC."""

    name = "MockLatticePhysicsInterface"

    def _getExecutablePath(self):
        return "/mock/"

    def interactBOC(self, cycle=None):
        pass


class MockXSGM(CrossSectionGroupManager):
    """A mock cross section group manager that does nothing for interactBOC."""

    def interactBOC(self, cycle=None):
        pass


class TestFuelHandler(FuelHandlerTestHelper):
    @patch("armi.reactor.assemblies.Assembly.getSymmetryFactor")
    def test_getParamMax(self, mockGetSymmetry):
        a = self.assembly
        mockGetSymmetry.return_value = 1
        expectedValue = 0.5
        a.p["kInf"] = expectedValue
        for b in a:
            b.p["kInf"] = expectedValue

        with patch(
            "armi.reactor.parameters.parameterDefinitions.Parameter.location", new_callable=PropertyMock
        ) as mock_assemblyParameterLocation:
            mock_assemblyParameterLocation.return_value = ParamLocation.VOLUME_INTEGRATED
            # symmetry factor == 1
            res = fuelHandlers.FuelHandler._getParamMax(a, "kInf", True)
            self.assertEqual(res, expectedValue)

            res = fuelHandlers.FuelHandler._getParamMax(a, "kInf", False)
            self.assertEqual(res, expectedValue)

            # symmetry factor == 3
            mockGetSymmetry.return_value = 3
            res = fuelHandlers.FuelHandler._getParamMax(a, "kInf", True)
            self.assertAlmostEqual(res, expectedValue * 3)

            res = fuelHandlers.FuelHandler._getParamMax(a, "kInf", False)
            self.assertAlmostEqual(res, expectedValue * 3)

            # not volume integrated and symmetry factor == 3
            mock_assemblyParameterLocation.return_value = ParamLocation.AVERAGE
            res = fuelHandlers.FuelHandler._getParamMax(a, "kInf", True)
            self.assertEqual(res, expectedValue)

            res = fuelHandlers.FuelHandler._getParamMax(a, "kInf", False)
            self.assertEqual(res, expectedValue)

    def test_interactBOC(self):
        # set up mock interface
        self.o.addInterface(MockLatticePhysicsInterface(self.r, self.o.cs))
        self.o.removeInterface(interfaceName="xsGroups")
        self.o.addInterface(MockXSGM(self.r, self.o.cs))
        # adjust case settings
        self.o.cs[CONF_RUN_LATTICE_BEFORE_SHUFFLING] = True
        # run fhi.interactBOC
        fhi = self.o.getInterface("fuelHandler")
        with mockRunLogs.BufferLog() as mock:
            fhi.interactBOC()
            self.assertIn("lattice physics before fuel management due to the", mock._outputStream)

    def test_findHighBu(self):
        loc = self.r.core.spatialGrid.getLocatorFromRingAndPos(5, 4)
        a = self.r.core.childrenByLocator[loc]
        # set burnup way over 1.0, which is otherwise the highest bu in the core
        a[0].p.percentBu = 50

        fh = fuelHandlers.FuelHandler(self.o)
        a1 = fh.findAssembly(param="percentBu", compareTo=100, blockLevelMax=True, typeSpec=None)
        self.assertIs(a, a1)

    @patch("armi.physics.fuelCycle.fuelHandlers.FuelHandler.chooseSwaps")
    def test_outage(self, mockChooseSwaps):
        # mock up a fuel handler
        fh = fuelHandlers.FuelHandler(self.o)
        mockChooseSwaps.return_value = list(self.r.core.getAssemblies())

        # edge case: cannot perform two outages on the same FuelHandler
        fh.moved = [self.r.core.getFirstAssembly()]
        with self.assertRaises(ValueError):
            fh.outage(factor=1.0)

        # edge case: fail if the shuffle file is missing
        fh.moved = []
        self.o.cs = self.o.cs.modified(newSettings={"explicitRepeatShuffles": "fakePath"})
        with self.assertRaises(RuntimeError):
            fh.outage(factor=1.0)

        # a successful run
        fh.moved = []
        self.o.cs = self.o.cs.modified(
            newSettings={
                "explicitRepeatShuffles": "",
                "fluxRecon": True,
                CONF_ASSEMBLY_ROTATION_ALG: "simpleAssemblyRotation",
            }
        )
        fh.outage(factor=1.0)
        self.assertEqual(len(fh.moved), 0)

    def test_outageEdgeCase(self):
        """Check that an error is raised if the list of moved assemblies is invalid."""

        class MockFH(fuelHandlers.FuelHandler):
            def chooseSwaps(self, factor=1.0):
                self.moved = [None]

        # mock up a fuel handler
        fh = MockFH(self.o)

        # test edge case
        with self.assertRaises(AttributeError):
            fh.outage(factor=1.0)

    def test_isAssemblyInAZone(self):
        # build a fuel handler
        fh = fuelHandlers.FuelHandler(self.o)

        # test the default value if there are no zones
        a = self.r.core.getFirstAssembly()
        self.assertTrue(fh.isAssemblyInAZone(None, a))

        # If our assembly isn't in one of the supplied zones
        z = Zone("test_isAssemblyInAZone")
        self.assertFalse(fh.isAssemblyInAZone([z], a))

        # If our assembly IS in one of the supplied zones
        z.addLoc(a.getLocation())
        self.assertTrue(fh.isAssemblyInAZone([z], a))

    def test_width(self):
        """Tests the width capability of findAssembly."""
        fh = fuelHandlers.FuelHandler(self.o)
        assemsByRing = collections.defaultdict(list)
        for a in self.r.core:
            assemsByRing[a.spatialLocator.getRingPos()[0]].append(a)

        # instantiate reactor power. more power in more outer rings
        for ring, power in zip(range(1, 8), range(10, 80, 10)):
            aList = assemsByRing[ring]
            for a in aList:
                sf = a.getSymmetryFactor()  # center assembly is only 1/3rd in the core
                for b in a:
                    b.p.power = power / sf

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
        a = fh.findAssembly(targetRing=3, width=(1, 0), param=paramName, blockLevelMax=True, compareTo=0)
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
        a = fh.findAssembly(targetRing=3, width=(2, 1), param=paramName, blockLevelMax=True, compareTo=0)
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
        """Tests the ``findMany`` and type aspects of the fuel handler."""
        fh = fuelHandlers.FuelHandler(self.o)

        igniters = fh.findAssembly(typeSpec=Flags.IGNITER | Flags.FUEL, findMany=True)
        feeds = fh.findAssembly(typeSpec=Flags.FEED | Flags.FUEL, findMany=True)
        fewFeeds = fh.findAssembly(typeSpec=Flags.FEED | Flags.FUEL, findMany=True, maxNumAssems=4)

        self.assertEqual(
            len(igniters),
            self.nigniter,
            "Found {0} igniters. Should have found {1}".format(len(igniters), self.nigniter),
        )
        self.assertEqual(
            len(feeds),
            self.nfeed,
            "Found {0} feeds. Should have found {1}".format(len(igniters), self.nfeed),
        )
        self.assertEqual(
            len(fewFeeds),
            4,
            "Reduced findMany returned {0} assemblies instead of {1}".format(len(fewFeeds), 4),
        )

    def test_findInSFP(self):
        """Tests ability to pull from the spent fuel pool."""
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
            "Found {0} assems in SFP. Should have found {1}".format(len(spent), self.nSfp),
        )
        burnups = [a.getMaxParam("percentBu") for a in spent]
        bu = spent[0].getMaxParam("percentBu")
        self.assertEqual(
            bu,
            max(burnups),
            "First assembly does not have the highest burnup ({0}). It has ({1})".format(max(burnups), bu),
        )

    def test_findByCoords(self):
        fh = fuelHandlers.FuelHandler(self.o)
        assem = fh.findAssembly(coords=(0, 0))
        self.o.r.core.sortAssemsByRing()
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
        lastB = None
        for b in self.r.core.iterBlocks(Flags.FUEL):
            if b.p.percentBu > 20:
                break
            lastB = b
        expected = lastB.parent
        self.assertIs(assem, expected)

        # test the impossible: an block with burnup less than 110% of its own burnup
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
            for a in self.r.excore["sfp"]:
                self.assertEqual(a.getLocation(), "SFP")
            for b in self.r.core.iterBlocks(Flags.FUEL):
                self.assertGreater(b.p.kgHM, 0.0, "b.p.kgHM not populated!")
                self.assertGreater(b.p.kgFis, 0.0, "b.p.kgFis not populated!")

        fh.interactEOL()

    def test_repeatShuffles(self):
        """Loads the ARMI test reactor with a custom shuffle logic file and shuffles assemblies
        twice.

        .. test:: Execute user-defined shuffle operations based on a reactor model.
            :id: T_ARMI_SHUFFLE
            :tests: R_ARMI_SHUFFLE

        Notes
        -----
        The custom shuffle logic is executed by
        :py:meth:`armi.physics.fuelCycle.fuelHandlerInterface.FuelHandlerInterface.manageFuel` in
        :py:meth:`armi.physics.fuelCycle.tests.test_fuelHandlers.TestFuelHandler.runShuffling`.
        There are two primary assertions: spent fuel pool assemblies are in the correct location and
        the assemblies were shuffled into their correct locations. This process is repeated twice to
        ensure repeatability.
        """
        # check labels before shuffling:
        for a in self.r.excore["sfp"]:
            self.assertEqual(a.getLocation(), "SFP")

        # do some shuffles
        fh = self.o.getInterface("fuelHandler")
        self.runShuffling(fh)  # changes caseTitle

        # Make sure the generated shuffles file matches the tracked one.  This will need to be
        # updated if/when more assemblies are added to the test reactor but must be done carefully.
        # Do not blindly rebaseline this file.
        self.compareFilesLineByLine("armiRun-SHUFFLES.txt", "armiRun2-SHUFFLES.txt")

        # store locations of each assembly
        firstPassResults = {}
        for a in self.r.core:
            firstPassResults[a.getLocation()] = a.getName()
            self.assertNotIn(a.getLocation(), ["SFP", "LoadQueue", "ExCore"])

        # reset core to BOL state
        # reset assembly counter to get the same assem nums.
        self.setUp()

        newSettings = {CONF_PLOT_SHUFFLE_ARROWS: True}
        # now repeat shuffles
        newSettings["explicitRepeatShuffles"] = "armiRun-SHUFFLES.txt"
        self.o.cs = self.o.cs.modified(newSettings=newSettings)

        fh = self.o.getInterface("fuelHandler")

        self.runShuffling(fh)

        # make sure the shuffle was repeated perfectly
        for a in self.r.core:
            self.assertEqual(a.getName(), firstPassResults[a.getLocation()])

        for a in self.r.excore["sfp"]:
            self.assertEqual(a.getLocation(), "SFP")

        # Do some cleanup, since the fuelHandler Interface has code that gets
        # around the TempDirectoryChanger
        os.remove("armiRun2-SHUFFLES.txt")
        os.remove("armiRun2.shuffles_0.png")
        os.remove("armiRun2.shuffles_1.png")
        os.remove("armiRun2.shuffles_2.png")

    def test_readMoves(self):
        """
        Depends on the ``shuffleLogic`` created by ``repeatShuffles``.

        See Also
        --------
        runShuffling : creates the shuffling file to be read in.
        """
        numblocks = len(self.r.core.getFirstAssembly())
        fh = fuelHandlers.FuelHandler(self.o)
        moves = fh.readMoves("armiRun-SHUFFLES.txt")
        self.assertEqual(len(moves), 3)
        firstMove = moves[1][0]
        self.assertEqual(firstMove.fromLoc, "002-001")
        self.assertEqual(firstMove.toLoc, "SFP")
        self.assertEqual(len(firstMove.enrichList), numblocks)
        self.assertEqual(firstMove.assemType, "igniter fuel")
        self.assertIsNone(firstMove.nameAtDischarge)

        # check the move that came back out of the SFP
        sfpMove = moves[2][-2]
        self.assertEqual(sfpMove.fromLoc, "SFP")
        self.assertEqual(sfpMove.toLoc, "005-003")
        self.assertEqual(sfpMove.nameAtDischarge, "A0073")  # name of assem in SFP

        # make sure we fail hard if the file doesn't exist
        with self.assertRaises(RuntimeError):
            fh.readMoves("totall_fictional_file.txt")

    def test_readMovesYaml(self):
        fh = fuelHandlers.FuelHandler(self.o)
        moves, swaps = fh.readMovesYaml("armiRun-SHUFFLES.yaml")
        self.maxDiff = None
        expected = {
            1: [
                AssemblyMove("LoadQueue", "009-045", [0.0, 0.12, 0.14, 0.15, 0.0], "outer fuel"),
                AssemblyMove("009-045", "008-004"),
                AssemblyMove("008-004", "007-001"),
                AssemblyMove("007-001", "006-005"),
                AssemblyMove("006-005", "ExCore"),
                AssemblyMove("009-045", "009-045", rotation=60.0),
                AssemblyMove("LoadQueue", "010-046", [0.0, 0.12, 0.14, 0.15, 0.0], "outer fuel"),
                AssemblyMove("010-046", "011-046"),
                AssemblyMove("011-046", "012-046"),
                AssemblyMove("012-046", "ExCore"),
            ],
            2: [
                AssemblyMove("LoadQueue", "009-045", [0.0, 0.12, 0.14, 0.15, 0.0], "outer fuel"),
                AssemblyMove("009-045", "008-004"),
                AssemblyMove("008-004", "007-001"),
                AssemblyMove("007-001", "006-005"),
                AssemblyMove("006-005", "ExCore"),
                AssemblyMove("009-045", "009-045", rotation=60.0),
                AssemblyMove("LoadQueue", "010-046", [0.0, 0.12, 0.14, 0.15, 0.0], "outer fuel"),
                AssemblyMove("010-046", "011-046"),
                AssemblyMove("011-046", "012-046"),
                AssemblyMove("012-046", "ExCore"),
            ],
            3: [
                AssemblyMove("LoadQueue", "009-045", [0.0, 0.12, 0.14, 0.15, 0.0], "outer fuel"),
                AssemblyMove("009-045", "008-004"),
                AssemblyMove("008-004", "007-001"),
                AssemblyMove("007-001", "006-005"),
                AssemblyMove("006-005", "ExCore"),
            ],
        }
        self.assertEqual(moves, expected)
        self.assertEqual(swaps, {3: [("009-045", "008-004"), ("007-001", "006-005")]})

    def test_performShuffleYamlIntegration(self):
        fh = fuelHandlers.FuelHandler(self.o)
        yaml_text = """
        sequence:
            1:
                - misloadSwap: ["009-045", "008-004"]
                - cascade: ["igniter fuel", "009-045", "008-004", "007-001", "006-005"]
                  fuelEnrichment: [0, 0.12, 0.14, 0.15, 0]
                - extraRotations: {"009-045": 60}
        """
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
            tf.write(yaml_text)
            fname = tf.name
        try:
            locs = ["009-045", "008-004", "007-001", "006-005"]
            before = {loc: self.r.core.getAssemblyWithStringLocation(loc).getName() for loc in locs}
            self.r.p.cycle = 1
            self.o.cs = self.o.cs.modified(newSettings={CONF_SHUFFLE_SEQUENCE_FILE: fname, CONF_TRACK_ASSEMS: False})
            self.r.core._trackAssems = False
            fh.outage()

            fresh = self.r.core.getAssemblyWithStringLocation("008-004")
            self.assertEqual(fresh.getType(), "igniter fuel")
            self.assertNotIn(fresh.getName(), before.values())

            rotated = self.r.core.getAssemblyWithStringLocation("009-045")
            self.assertEqual(rotated.getName(), before["009-045"])
            self.assertAlmostEqual(rotated.p.orientation[2], 60.0)

            self.assertEqual(
                self.r.core.getAssemblyWithStringLocation("007-001").getName(),
                before["008-004"],
            )
            self.assertEqual(
                self.r.core.getAssemblyWithStringLocation("006-005").getName(),
                before["007-001"],
            )
            self.assertIsNone(self.r.excore["sfp"].getAssembly(before["006-005"]))
        finally:
            os.remove(fname)

    def test_yamlSfpOverridesTrackAssems(self):
        fh = fuelHandlers.FuelHandler(self.o)
        yaml_text = """
        sequence:
            1:
                - cascade: ["igniter fuel", "009-045", "SFP"]
                  fuelEnrichment: [0, 0.12, 0.14, 0.15, 0]
        """
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
            tf.write(yaml_text)
            fname = tf.name
        try:
            before = self.r.core.getAssemblyWithStringLocation("009-045").getName()
            self.r.p.cycle = 1
            self.o.cs = self.o.cs.modified(newSettings={CONF_SHUFFLE_SEQUENCE_FILE: fname, CONF_TRACK_ASSEMS: False})
            self.r.core._trackAssems = False
            fh.outage()

            self.assertFalse(self.r.core._trackAssems)
            self.assertIsNotNone(self.r.excore["sfp"].getAssembly(before))
        finally:
            os.remove(fname)

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
            rotations,
            _,
        ) = fh.processMoveList(moves[2])
        self.assertIn("A0073", loadNames)
        self.assertIn(None, loadNames)
        self.assertNotIn("SFP", loadChains)
        self.assertNotIn("LoadQueue", loadChains)
        self.assertFalse(loopChains)
        self.assertFalse(rotations)

    def test_processMoveList_yaml(self):
        fh = fuelHandlers.FuelHandler(self.o)
        moves, _ = fh.readMovesYaml("armiRun-SHUFFLES.yaml")
        loadChains, loopChains, enriches, loadTypes, loadNames, _, rotations, _ = fh.processMoveList(moves[1])
        self.assertEqual(len(loadChains), 2)
        self.assertTrue(any(enriches))
        self.assertTrue(rotations)

    def test_getFactorList(self):
        fh = fuelHandlers.FuelHandler(self.o)
        factors, _ = fh.getFactorList(0)
        self.assertIn("eqShuffles", factors)

    def test_linPowByPin(self):
        _fh = fuelHandlers.FuelHandler(self.o)
        _hist = self.o.getInterface("history")
        newSettings = {CONF_ASSEM_ROTATION_STATIONARY: True}
        self.o.cs = self.o.cs.modified(newSettings=newSettings)
        assem = self.o.r.core.getFirstAssembly(Flags.FUEL)
        b = next(assem.iterBlocks(Flags.FUEL))

        b.p.linPowByPin = [1, 2, 3]
        self.assertEqual(type(b.p.linPowByPin), np.ndarray)

        b.p.linPowByPin = np.array([1, 2, 3])
        self.assertEqual(type(b.p.linPowByPin), np.ndarray)

    def test_linPowByPinNeutron(self):
        _fh = fuelHandlers.FuelHandler(self.o)
        _hist = self.o.getInterface("history")
        newSettings = {CONF_ASSEM_ROTATION_STATIONARY: True}
        self.o.cs = self.o.cs.modified(newSettings=newSettings)
        assem = self.o.r.core.getFirstAssembly(Flags.FUEL)
        b = next(assem.iterBlocks(Flags.FUEL))

        b.p.linPowByPinNeutron = [1, 2, 3]
        self.assertEqual(type(b.p.linPowByPinNeutron), np.ndarray)

        b.p.linPowByPinNeutron = np.array([1, 2, 3])
        self.assertEqual(type(b.p.linPowByPinNeutron), np.ndarray)

    def test_linPowByPinGamma(self):
        _fh = fuelHandlers.FuelHandler(self.o)
        _hist = self.o.getInterface("history")
        newSettings = {CONF_ASSEM_ROTATION_STATIONARY: True}
        self.o.cs = self.o.cs.modified(newSettings=newSettings)
        assem = self.o.r.core.getFirstAssembly(Flags.FUEL)
        b = next(assem.iterBlocks(Flags.FUEL))

        b.p.linPowByPinGamma = [1, 2, 3]
        self.assertEqual(type(b.p.linPowByPinGamma), np.ndarray)

        b.p.linPowByPinGamma = np.array([1, 2, 3])
        self.assertEqual(type(b.p.linPowByPinGamma), np.ndarray)

    def test_transferStationaryBlocks(self):
        """Test the _transferStationaryBlocks method.

        .. test:: User-specified blocks can remain in place during shuffling
            :id: T_ARMI_SHUFFLE_STATIONARY0
            :tests: R_ARMI_SHUFFLE_STATIONARY
        """
        # grab stationary block flags
        sBFList = self.r.core.stationaryBlockFlagsList

        # grab the assemblies
        assems = self.r.core.getAssemblies(Flags.FUEL)

        # grab two arbitrary assemblies
        a1 = assems[1]
        a2 = assems[2]

        # grab the stationary blocks pre swap
        a1PreSwapStationaryBlocks = [
            [block.getName(), block.spatialLocator.k] for block in a1 if any(block.hasFlags(sbf) for sbf in sBFList)
        ]

        a2PreSwapStationaryBlocks = [
            [block.getName(), block.spatialLocator.k] for block in a2 if any(block.hasFlags(sbf) for sbf in sBFList)
        ]

        # swap the stationary blocks
        fh = fuelHandlers.FuelHandler(self.o)
        fh._transferStationaryBlocks(a1, a2)

        # grab the stationary blocks post swap
        a1PostSwapStationaryBlocks = [
            [block.getName(), block.spatialLocator.k] for block in a1 if any(block.hasFlags(sbf) for sbf in sBFList)
        ]

        a2PostSwapStationaryBlocks = [
            [block.getName(), block.spatialLocator.k] for block in a2 if any(block.hasFlags(sbf) for sbf in sBFList)
        ]

        # validate the stationary blocks have swapped locations and are aligned
        self.assertEqual(a1PostSwapStationaryBlocks, a2PreSwapStationaryBlocks)
        self.assertEqual(a2PostSwapStationaryBlocks, a1PreSwapStationaryBlocks)

    def test_transferDifferentNumberStationaryBlocks(self):
        """
        Test the _transferStationaryBlocks method for the case where the input assemblies have
        different numbers of stationary blocks.
        """
        # grab stationary block flags
        sBFList = self.r.core.stationaryBlockFlagsList

        # grab the assemblies
        assems = self.r.core.getAssemblies(Flags.FUEL)

        # grab two arbitrary assemblies
        a1 = assems[1]
        a2 = assems[2]

        # change a block in assembly 1 to be flagged as a stationary block
        for block in a1:
            if not any(block.hasFlags(sbf) for sbf in sBFList):
                a1[block.spatialLocator.k].setType(a1[block.spatialLocator.k].p.type, sBFList[0])
                self.assertTrue(any(block.hasFlags(sbf) for sbf in sBFList))
                break

        # try to swap stationary blocks between assembly 1 and 2
        fh = fuelHandlers.FuelHandler(self.o)
        with self.assertRaises(ValueError):
            fh._transferStationaryBlocks(a1, a2)

    def test_transferUnalignedLocationStationaryBlocks(self):
        """
        Test the _transferStationaryBlocks method for the case where the input assemblies have
        unaligned locations of stationary blocks.
        """
        # grab stationary block flags
        sBFList = self.r.core.stationaryBlockFlagsList

        # grab the assemblies
        assems = self.r.core.getAssemblies(Flags.FUEL)

        # grab two arbitrary assemblies
        a1 = assems[1]
        a2 = assems[2]

        # move location of a stationary flag in assembly 1
        for block in a1:
            if any(block.hasFlags(sbf) for sbf in sBFList):
                # change flag of first identified stationary block to fuel
                a1[block.spatialLocator.k].setType(a1[block.spatialLocator.k].p.type, Flags.FUEL)
                self.assertTrue(a1[block.spatialLocator.k].hasFlags(Flags.FUEL))
                # change next or previous block flag to stationary flag
                try:
                    a1[block.spatialLocator.k + 1].setType(a1[block.spatialLocator.k + 1].p.type, sBFList[0])
                    self.assertTrue(any(a1[block.spatialLocator.k + 1].hasFlags(sbf) for sbf in sBFList))
                except Exception:
                    a1[block.spatialLocator.k - 1].setType(a1[block.spatialLocator.k - 1].p.type, sBFList[0])
                    self.assertTrue(any(a1[block.spatialLocator.k - 1].hasFlags(sbf) for sbf in sBFList))
                break

        # try to swap stationary blocks between assembly 1 and 2
        fh = fuelHandlers.FuelHandler(self.o)
        with self.assertRaises(ValueError):
            fh._transferStationaryBlocks(a1, a2)

    def test_transferIncompatibleHeightStationaryBlocks(self):
        """
        Test the _transferStationaryBlocks method
        for the case where the total height of the
        stationary blocks is unequal between input assemblies.
        """
        # grab stationary block flags
        sBFList = self.r.core.stationaryBlockFlagsList

        # grab the assemblies
        assems = self.r.core.getAssemblies(Flags.FUEL)

        # grab two arbitrary assemblies
        a1 = assems[1]
        a2 = assems[2]

        # change height of a stationary block in assembly 1
        for block in a1:
            if any(block.hasFlags(sbf) for sbf in sBFList):
                # change height of first identified stationary block
                nomHeight = block.getHeight()
                a1[block.spatialLocator.k].setHeight(nomHeight - 1e-5)

        # try to swap stationary blocks between assembly 1 and 2
        fh = fuelHandlers.FuelHandler(self.o)
        with mockRunLogs.BufferLog() as mock:
            fh._transferStationaryBlocks(a1, a2)
            self.assertIn("top elevation of stationary", mock.getStdout())

    def test_dischargeSwap(self):
        """Remove an assembly from the core and replace it with one from the SFP.

        .. test:: User-specified blocks can remain in place during shuffling
            :id: T_ARMI_SHUFFLE_STATIONARY1
            :tests: R_ARMI_SHUFFLE_STATIONARY
        """
        # grab stationary block flags
        sBFList = self.r.core.stationaryBlockFlagsList

        # grab an arbitrary fuel assembly from the core and from the SFP
        a1 = self.r.core.getFirstAssembly(Flags.FUEL)
        a2 = self.r.excore["sfp"].getChildrenWithFlags(Flags.FUEL)[0]

        # grab the stationary blocks pre swap
        a1PreSwapStationaryBlocks = [
            [block.getName(), block.spatialLocator.k] for block in a1 if any(block.hasFlags(sbf) for sbf in sBFList)
        ]

        a2PreSwapStationaryBlocks = [
            [block.getName(), block.spatialLocator.k] for block in a2 if any(block.hasFlags(sbf) for sbf in sBFList)
        ]

        # test discharging assembly 1 and replacing with assembly 2
        fh = fuelHandlers.FuelHandler(self.o)
        fh.dischargeSwap(a2, a1)
        self.assertTrue(a1.getLocation() in a1.NOT_IN_CORE)
        self.assertTrue(a2.getLocation() not in a2.NOT_IN_CORE)

        # grab the stationary blocks post swap
        a1PostSwapStationaryBlocks = [
            [block.getName(), block.spatialLocator.k] for block in a1 if any(block.hasFlags(sbf) for sbf in sBFList)
        ]

        a2PostSwapStationaryBlocks = [
            [block.getName(), block.spatialLocator.k] for block in a2 if any(block.hasFlags(sbf) for sbf in sBFList)
        ]

        # validate the stationary blocks have swapped locations correctly and are aligned
        self.assertEqual(a1PostSwapStationaryBlocks, a2PreSwapStationaryBlocks)
        self.assertEqual(a2PostSwapStationaryBlocks, a1PreSwapStationaryBlocks)

    def test_dischargeSwapIncompatibleStationaryBlocks(self):
        """
        Test the _transferStationaryBlocks method for the case where the input assemblies have
        different numbers as well as unaligned locations of stationary blocks.
        """
        # grab stationary block flags
        sBFList = self.r.core.stationaryBlockFlagsList

        # grab an arbitrary fuel assembly from the core and from the SFP
        a1 = self.r.core.getFirstAssembly(Flags.FUEL)
        a2 = self.r.excore["sfp"].getChildren(Flags.FUEL)[0]

        # change a block in assembly 1 to be flagged as a stationary block
        for block in a1:
            if not any(block.hasFlags(sbf) for sbf in sBFList):
                a1[block.spatialLocator.k].setType(a1[block.spatialLocator.k].p.type, sBFList[0])
                self.assertTrue(any(block.hasFlags(sbf) for sbf in sBFList))
                break

        # try to discharge assembly 1 and replace with assembly 2
        fh = fuelHandlers.FuelHandler(self.o)
        with self.assertRaises(ValueError):
            fh.dischargeSwap(a2, a1)

        # re-initialize assemblies
        self.setUp()
        a1 = self.r.core.getFirstAssembly(Flags.FUEL)
        a2 = self.r.excore["sfp"].getChildren(Flags.FUEL)[0]

        # move location of a stationary flag in assembly 1
        for block in a1:
            if any(block.hasFlags(sbf) for sbf in sBFList):
                # change flag of first identified stationary block to fuel
                a1[block.spatialLocator.k].setType(a1[block.spatialLocator.k].p.type, Flags.FUEL)
                self.assertTrue(a1[block.spatialLocator.k].hasFlags(Flags.FUEL))
                # change next or previous block flag to stationary flag
                try:
                    a1[block.spatialLocator.k + 1].setType(a1[block.spatialLocator.k + 1].p.type, sBFList[0])
                    self.assertTrue(any(a1[block.spatialLocator.k + 1].hasFlags(sbf) for sbf in sBFList))
                except Exception:
                    a1[block.spatialLocator.k - 1].setType(a1[block.spatialLocator.k - 1].p.type, sBFList[0])
                    self.assertTrue(any(a1[block.spatialLocator.k - 1].hasFlags(sbf) for sbf in sBFList))
                break

        # try to discharge assembly 1 and replace with assembly 2
        with self.assertRaises(ValueError):
            fh.dischargeSwap(a2, a1)

    def test_getAssembliesInRings(self):
        fh = fuelHandlers.FuelHandler(self.o)
        aList0 = fh._getAssembliesInRings([0], Flags.FUEL, False, None, False)
        self.assertEqual(len(aList0), 1)

        aList1 = fh._getAssembliesInRings([0, 1, 2], Flags.FUEL, False, None, False)
        self.assertEqual(len(aList1), 3)

        aList2 = fh._getAssembliesInRings([0, 1, 2], Flags.FUEL, True, None, False)
        self.assertEqual(len(aList2), 3)

        aList3 = fh._getAssembliesInRings([0, 1, 2, "SFP"], Flags.FUEL, True, None, False)
        self.assertEqual(len(aList3), 4)

        aList4 = fh._getAssembliesInRings([0, 1, 2], Flags.FUEL, False, None, True)
        self.assertEqual(len(aList4), 3)


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
