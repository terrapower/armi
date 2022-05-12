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

"""Tests assemblies.py"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access,invalid-name
import pathlib
import random
import unittest

from numpy.testing import assert_allclose

from armi import settings
from armi import tests
from armi.reactor import assemblies
from armi.reactor import blueprints
from armi.reactor import components
from armi.reactor import parameters
from armi.reactor import reactors
from armi.reactor import geometry
from armi.reactor.assemblies import (
    blocks,
    copy,
    Flags,
    grids,
    HexAssembly,
    math,
    numpy,
    runLog,
)
from armi.tests import TEST_ROOT
from armi.utils import directoryChangers
from armi.utils import textProcessors
from armi.reactor.tests import test_reactors
from armi.reactor.assemblies import getAssemNum
from armi.reactor.assemblies import resetAssemNumCounter


NUM_BLOCKS = 3


def buildTestAssemblies():
    """
    Build some assembly objects that will be used in testing.

    This builds 2 HexBlocks:
        * One with half UZr pins and half UTh pins
        * One with all UThZr pins
    """
    caseSetting = settings.Settings()
    settings.setMasterCs(caseSetting)

    temperature = 273.0
    fuelID = 0.0
    fuelOD = 1.0
    cladOD = 1.1
    # generate a reactor with assemblies
    # generate components with materials
    nPins = 100

    fuelDims = {
        "Tinput": temperature,
        "Thot": temperature,
        "od": fuelOD,
        "id": fuelID,
        "mult": nPins,
    }

    fuelUZr = components.Circle("fuel", "UZr", **fuelDims)
    fuelUTh = components.Circle("fuel UTh", "ThU", **fuelDims)

    fuelDims2nPins = {
        "Tinput": temperature,
        "Thot": temperature,
        "od": fuelOD,
        "id": fuelID,
        "mult": 2 * nPins,
    }

    fuelUThZr = components.Circle("fuel B", "UThZr", **fuelDims2nPins)

    cladDims = {
        "Tinput": temperature,
        "Thot": temperature,
        "od": cladOD,
        "id": fuelOD,
        "mult": 2 * nPins,
    }

    clad = components.Circle("clad", "HT9", **cladDims)

    interDims = {
        "Tinput": temperature,
        "Thot": temperature,
        "op": 16.8,
        "ip": 16.0,
        "mult": 1.0,
    }

    interSodium = components.Hexagon("interCoolant", "Sodium", **interDims)

    block = blocks.HexBlock("fuel")
    block2 = blocks.HexBlock("fuel")
    block.setType("fuel")
    block.setHeight(10.0)
    block.add(fuelUZr)
    block.add(fuelUTh)
    block.add(clad)
    block.add(interSodium)
    block.p.axMesh = 1
    block.p.molesHmBOL = 1.0
    block.p.molesHmNow = 1.0

    block2.setType("fuel")
    block2.setHeight(10.0)
    block2.add(fuelUThZr)
    block2.add(clad)
    block2.add(interSodium)
    block2.p.axMesh = 1
    block2.p.molesHmBOL = 2
    block2.p.molesHmNow = 1.0

    assemblieObjs = []
    for numBlocks, blockTemplate in zip([1, 1, 5, 4], [block, block2, block, block]):
        assembly = assemblies.HexAssembly("testAssemblyType")
        assembly.spatialGrid = grids.axialUnitGrid(numBlocks)
        assembly.spatialGrid.armiObject = assembly
        for _i in range(numBlocks):
            newBlock = copy.deepcopy(blockTemplate)
            assembly.add(newBlock)
        assembly.calculateZCoords()
        assembly.reestablishBlockOrder()
        assemblieObjs.append(assembly)

    return assemblieObjs


class MaterialInAssembly_TestCase(unittest.TestCase):
    def setUp(self):
        # pylint: disable=unbalanced-tuple-unpacking
        (
            self.assembly,
            self.assembly2,
            self.assembly3,
            self.assembly4,
        ) = buildTestAssemblies()

    def test_sortNoLocator(self):
        self.assembly.spatialLocator = None
        self.assembly2.spatialLocator = None
        self.assertFalse(self.assembly < self.assembly2)
        self.assertFalse(self.assembly2 < self.assembly)
        grid = grids.HexGrid()
        self.assembly.spatialLocator = grid[0, 0, 0]
        self.assembly2.spatialLocator = grid[0, 1, 0]
        self.assertTrue(self.assembly < self.assembly2)
        self.assertFalse(self.assembly2 < self.assembly)

    def test_UThZrMaterial(self):
        """
        Test the ternary UThZr material.

        """
        b2 = self.assembly2[0]
        uThZrFuel = b2.getComponent(Flags.FUEL | Flags.B)
        mat = uThZrFuel.getProperties()
        mat.applyInputParams(0.1, 0.0, 0.30)
        self.assertAlmostEqual(
            uThZrFuel.getMass("U235")
            / (uThZrFuel.getMass("U238") + uThZrFuel.getMass("U235")),
            0.1,
        )
        self.assertAlmostEqual(uThZrFuel.getMassFrac("TH232"), 0.3)


def makeTestAssembly(
    numBlocks, assemNum, spatialGrid=grids.HexGrid.fromPitch(1.0), r=None
):
    coreGrid = r.core.spatialGrid if r is not None else spatialGrid
    a = HexAssembly("TestAssem", assemNum=assemNum)
    a.spatialGrid = grids.axialUnitGrid(numBlocks)
    a.spatialGrid.armiObject = a
    a.spatialLocator = coreGrid[2, 2, 0]
    return a


class Assembly_TestCase(unittest.TestCase):
    def setUp(self):
        self.name = "A0015"
        self.assemNum = 15
        self.height = 10
        self.cs = settings.getMasterCs()
        # Print nothing to the screen that would normally go to the log.
        runLog.setVerbosity("error")

        self.r = tests.getEmptyHexReactor()
        self.r.core.symmetry = geometry.SymmetryType(
            geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC
        )

        self.assembly = makeTestAssembly(NUM_BLOCKS, self.assemNum, r=self.r)
        self.r.core.add(self.assembly)

        # Use these if they are needed
        self.blockParams = {
            "height": self.height,
            "avgFuelTemp": 873.0,
            "bondRemoved": 0.0,
            "bu": 15.1,
            "buGroupNum": 0,
            "buLimit": 35,
            "buRate": 0.0,
            "eqRegion": -1,
            "id": 212.0,
            "pdens": 10.0,
            "percentBu": 25.3,
            "power": 100000.0,
            "residence": 4.0,
            "smearDensity": 0.6996721711791459,
            "timeToLimit": 2.7e5,
            "xsTypeNum": 40,
            "zbottom": 97.3521,
            "ztop": 111.80279999999999,
        }

        self.blockSettings = {
            "axMesh": 1,
            "baseBu": 0.0,
            "basePBu": 0.0,
            "bondBOL": 0.0028698019026172574,
            "buGroup": "A",
            "height": 14.4507,
            "molesHmAtBOL": 65.8572895758245,
            "nHMAtBOL": 0.011241485251783766,
            "nPins": 169.0,
            "name": "B0011F",
            "newDPA": 0.0,
            "pitch": 16.79,
            "regName": False,
            "topIndex": 5,
            "tsIndex": 0,
            "type": "igniter fuel",
            "xsType": "C",
            "z": 104.57745,
        }
        # add some blocks with a component
        self.blockList = []
        for i in range(NUM_BLOCKS):
            b = blocks.HexBlock("TestHexBlock")
            b.setHeight(self.height)

            self.hexDims = {
                "Tinput": 273.0,
                "Thot": 273.0,
                "op": 0.76,
                "ip": 0.0,
                "mult": 1.0,
            }
            h = components.Hexagon("fuel", "UZr", **self.hexDims)

            # non-flaggy name important for testing
            b.setType("igniter fuel unitst")
            b.add(h)
            b.parent = self.assembly
            b.setName(b.makeName(self.assembly.getNum(), i))
            self.assembly.add(b)
            self.blockList.append(b)

        self.assembly.calculateZCoords()

    def test_resetAssemNumCounter(self):
        resetAssemNumCounter()
        cur = 0
        ref = getAssemNum()
        self.assertEqual(cur, ref)

    def test_iter(self):
        cur = []
        for block in self.assembly:
            cur.append(block)
        ref = self.blockList
        self.assertEqual(cur, ref)

    def test_len(self):
        cur = len(self.assembly)
        ref = len(self.blockList)
        self.assertEqual(cur, ref)

    def test_append(self):
        b = blocks.HexBlock("TestBlock")
        self.blockList.append(b)
        self.assembly.append(b)
        cur = self.assembly.getBlocks()
        ref = self.blockList
        self.assertEqual(cur, ref)

    def test_extend(self):
        blockList = []
        for _ in range(2):
            b = blocks.HexBlock("TestBlock")
            self.blockList.append(b)
            blockList.append(b)

        self.assembly.extend(blockList)
        cur = self.assembly.getBlocks()
        ref = self.blockList
        self.assertEqual(cur, ref)

    def test_add(self):
        a = makeTestAssembly(1, 1)
        b = blocks.HexBlock("TestBlock")
        a.add(b)
        self.assertIn(b, a)
        self.assertEqual(b.parent, a)

    def test_moveTo(self):
        ref = self.r.core.spatialGrid.getLocatorFromRingAndPos(3, 10)
        i, j = grids.HexGrid.getIndicesFromRingAndPos(3, 10)
        locator = self.r.core.spatialGrid[i, j, 0]
        self.assembly.moveTo(locator)

        cur = self.assembly.spatialLocator
        self.assertEqual(cur, ref)

    def test_getName(self):
        cur = self.assembly.getName()
        ref = self.name
        self.assertEqual(cur, ref)

    def test_getNum(self):
        cur = self.assembly.getNum()
        ref = self.assemNum
        self.assertEqual(cur, ref)

    def test_getLocation(self):
        cur = self.assembly.getLocation()
        ref = str("005-003")
        self.assertEqual(cur, ref)

    def test_getArea(self):
        cur = self.assembly.getArea()
        ref = math.sqrt(3) / 2.0 * self.hexDims["op"] ** 2
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getVolume(self):
        cur = self.assembly.getVolume()
        ref = math.sqrt(3) / 2.0 * self.hexDims["op"] ** 2 * self.height * NUM_BLOCKS
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_doubleResolution(self):
        b = self.assembly[0]
        initialHeight = b.p.heightBOL
        self.assembly.doubleResolution()
        cur = len(self.assembly.getBlocks())
        ref = 2 * len(self.blockList)
        self.assertEqual(cur, ref)

        cur = self.assembly.getBlocks()[0].getHeight()
        ref = self.height / 2.0
        places = 6
        self.assertNotEqual(initialHeight, b.p.heightBOL)
        self.assertAlmostEqual(cur, ref, places=places)

    def test_adjustResolution(self):
        # Make a second assembly with 4 times the resolution
        assemNum2 = self.assemNum * 4
        height2 = self.height / 4.0
        assembly2 = makeTestAssembly(assemNum2, assemNum2)

        # add some blocks with a component
        for _ in range(assemNum2):
            b = blocks.HexBlock("TestBlock")
            b.setHeight(height2)
            assembly2.add(b)

        self.assembly.adjustResolution(assembly2)

        cur = len(self.assembly.getBlocks())
        ref = 4.0 * len(self.blockList)
        self.assertEqual(cur, ref)

        cur = self.assembly.getBlocks()[0].getHeight()
        ref = self.height / 4.0
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getAxialMesh(self):
        cur = self.assembly.getAxialMesh()
        ref = [i * self.height + self.height for i in range(NUM_BLOCKS)]
        self.assertEqual(cur, ref)

    def test_calculateZCoords(self):
        self.assembly.calculateZCoords()

        places = 6
        bottom = 0.0
        for b in self.assembly:
            top = bottom + self.height

            cur = b.p.z
            ref = bottom + (top - bottom) / 2.0

            self.assertAlmostEqual(cur, ref, places=places)

            cur = b.p.zbottom
            ref = bottom
            self.assertAlmostEqual(cur, ref, places=places)

            cur = b.p.ztop
            ref = top
            self.assertAlmostEqual(cur, ref, places=places)

            bottom = top

    def test_getTotalHeight(self):
        cur = self.assembly.getTotalHeight()
        ref = self.height * NUM_BLOCKS
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getHeight(self):
        cur = self.assembly.getHeight()
        ref = self.height * NUM_BLOCKS
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getReactiveHeight(self):
        self.assembly[2].getComponent(Flags.FUEL).adjustMassEnrichment(0.01)
        self.assembly[2].setNumberDensity("PU239", 0.0)
        bottomElevation, reactiveHeight = self.assembly.getReactiveHeight(
            enrichThresh=0.02
        )
        self.assertEqual(bottomElevation, 0.0)
        self.assertEqual(reactiveHeight, 20.0)

    def test_getFissileMass(self):
        cur = self.assembly.getFissileMass()
        ref = sum(bi.getMass(["U235", "PU239"]) for bi in self.assembly)
        self.assertAlmostEqual(cur, ref)

    def test_getPuFrac(self):
        puAssem = self.assembly.getPuFrac()
        fuelBlock = self.assembly[1]
        puBlock = fuelBlock.getPuFrac()
        self.assertAlmostEqual(puAssem, puBlock)

        #
        fuelComp = fuelBlock.getComponent(Flags.FUEL)
        fuelComp.setNumberDensity("PU239", 0.012)
        self.assertGreater(self.assembly.getPuFrac(), puAssem)
        self.assertGreater(fuelBlock.getPuFrac(), puAssem)

    def test_getMass(self):
        mass0 = self.assembly.getMass("U235")
        mass1 = sum(bi.getMass("U235") for bi in self.assembly)
        self.assertAlmostEqual(mass0, mass1)

        fuelBlock = self.assembly.getBlocks(Flags.FUEL)[0]
        blockU35Mass = fuelBlock.getMass("U235")
        fuelBlock.setMass("U235", 2 * blockU35Mass)
        self.assertAlmostEqual(fuelBlock.getMass("U235"), blockU35Mass * 2)
        self.assertAlmostEqual(self.assembly.getMass("U235"), mass0 + blockU35Mass)

        fuelBlock.setMass("U238", 0.0)
        self.assertAlmostEqual(blockU35Mass * 2, fuelBlock.getMass("U235"))

    def test_getZrFrac(self):
        self.assertAlmostEqual(self.assembly.getZrFrac(), 0.1)

    def test_getMaxUraniumMassEnrich(self):
        baseEnrich = self.assembly[0].getUraniumMassEnrich()
        self.assertAlmostEqual(self.assembly.getMaxUraniumMassEnrich(), baseEnrich)
        self.assembly[2].setNumberDensity("U235", 2e-1)
        self.assertGreater(self.assembly.getMaxUraniumMassEnrich(), baseEnrich)

    def test_getAge(self):
        res = 5.0
        for b in self.assembly:
            b.p.residence = res

        cur = self.assembly.getAge()
        ref = res
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_makeAxialSnapList(self):
        # Make a second assembly with 4 times the resolution
        assemNum2 = self.assemNum * 4
        height2 = self.height / 4.0
        assembly2 = makeTestAssembly(assemNum2, assemNum2)

        # add some blocks with a component
        for _i in range(assemNum2):

            self.hexDims = {
                "Tinput": 273.0,
                "Thot": 273.0,
                "op": 0.76,
                "ip": 0.0,
                "mult": 1.0,
            }

            h = components.Hexagon("fuel", "UZr", **self.hexDims)
            b = blocks.HexBlock("fuel")
            b.setType("igniter fuel")
            b.add(h)
            b.setHeight(height2)
            assembly2.add(b)

        self.assembly.makeAxialSnapList(assembly2)

        cur = []
        for b in self.assembly:
            cur.append(b.p.topIndex)

        ref = [3, 7, 11]
        self.assertEqual(cur, ref)

    def test_snapAxialMeshToReference(self):
        ref = [11, 22, 33]
        for b, i in zip(self.assembly, range(self.assemNum)):
            b.p.topIndex = i

        self.assembly.setBlockMesh(ref)

        cur = []
        for b in self.assembly:
            cur.append(b.p.ztop)

        self.assertEqual(cur, ref)

    def test_updateFromAssembly(self):
        assembly2 = makeTestAssembly(self.assemNum, self.assemNum)

        params = {}
        params["maxPercentBu"] = 30.0
        params["numMoves"] = 5.0
        params["maxPercentBu"] = 0
        params["timeToLimit"] = 2.7e5
        params["arealPd"] = 110.0
        params["maxDpaPeak"] = 14.0
        params["kInf"] = 60.0

        for key, param in params.items():
            assembly2.p[key] = param

        self.assembly.updateParamsFrom(assembly2)

        for key, param in params.items():
            cur = self.assembly.p[key]
            ref = param
            self.assertEqual(cur, ref)

    def _setup_blueprints(self, filename="refSmallReactor.yaml"):
        # need this for the getAllNuclides call
        with directoryChangers.DirectoryChanger(TEST_ROOT):
            newSettings = {"loadingFile": filename}
            self.cs = self.cs.modified(newSettings=newSettings)

            with open(self.cs["loadingFile"], "r") as y:
                y = textProcessors.resolveMarkupInclusions(
                    y, pathlib.Path(self.cs.inputDirectory)
                )
                self.r.blueprints = blueprints.Blueprints.load(y)

            self.r.blueprints._prepConstruction(self.cs)

    def test_duplicate(self):
        self._setup_blueprints()

        # Perform the copy
        assembly2 = copy.deepcopy(self.assembly)

        for refBlock, curBlock in zip(self.assembly, assembly2):
            numNucs = 0
            for nuc in self.assembly.getAncestorWithFlags(
                Flags.REACTOR
            ).blueprints.allNuclidesInProblem:
                numNucs += 1
                # Block level density
                ref = refBlock.getNumberDensity(nuc)
                cur = curBlock.getNumberDensity(nuc)
                self.assertEqual(cur, ref)

            self.assertGreater(numNucs, 5)

            refFracs = refBlock.getVolumeFractions()
            curFracs = curBlock.getVolumeFractions()

            # Block level area fractions
            for ref, cur in zip(refFracs, curFracs):
                ref = ref[1]
                cur = cur[1]
                places = 6
                self.assertAlmostEqual(cur, ref, places=places)

            # Block level params
            for refParam in refBlock.p:
                if refParam == "serialNum":
                    continue
                ref = refBlock.p[refParam]
                cur = curBlock.p[refParam]
                if isinstance(cur, numpy.ndarray):
                    self.assertTrue((cur == ref).all())
                else:
                    if refParam == "location":
                        ref = str(ref)
                        cur = str(cur)
                    self.assertEqual(
                        cur,
                        ref,
                        msg="The {} param differs: {} vs. {}".format(
                            refParam, cur, ref
                        ),
                    )

        # Block level height
        for b, b2 in zip(self.assembly, assembly2):
            ref = b.getHeight()
            cur = b2.getHeight()
            self.assertEqual(cur, ref)
            assert_allclose(b.spatialLocator.indices, b2.spatialLocator.indices)

        # Assembly level params
        for param in self.assembly.p:
            if param == "serialNum":
                continue
            ref = self.assembly.p[param]
            cur = assembly2.p[param]
            if isinstance(cur, numpy.ndarray):
                assert_allclose(cur, ref)
            else:
                self.assertEqual(cur, ref)

        # Block level reactor and parent
        for b in assembly2:
            self.assertEqual(b.r, None)
            self.assertEqual(b.parent, assembly2)

    def test_hasFlags(self):
        self.assembly.setType("fuel")

        cur = self.assembly.hasFlags(Flags.FUEL)
        self.assertTrue(cur)

    def test_renameBlocksAccordingToAssemblyNum(self):
        self.assembly.p.assemNum = 55
        self.assembly.renameBlocksAccordingToAssemblyNum()
        self.assertIn(
            "{0:04d}".format(self.assembly.getNum()), self.assembly[1].getName()
        )

    def test_getBlocks(self):
        cur = self.assembly.getBlocks()
        ref = self.blockList
        self.assertEqual(cur, ref)

    def test_getFirstBlock(self):
        cur = self.assembly.getFirstBlock()
        ref = self.blockList[0]
        self.assertAlmostEqual(cur, ref)

    def test_getFirstBlockByType(self):
        b = self.assembly.getFirstBlockByType("igniter fuel unitst")
        self.assertEqual(b.getType(), "igniter fuel unitst")
        b = self.assembly.getFirstBlockByType("i do not exist")
        self.assertIsNone(b)

    def test_getBlockData(self):
        paramDict = {
            "timeToLimit": 40.0,
            "fastFluence": 1.01,
            "fastFluencePeak": 50.0,
            "power": 10000.0,
            "buGroup": 4,
            "residence": 3.145,
            "eqRegion": -1,
            "id": 299.0,
            "bondRemoved": 33.7,
            "buRate": 42.0,
        }
        # Set some params
        for b in self.assembly:
            for param, paramVal in paramDict.items():
                b.p[param] = paramVal

        for param in paramDict:
            cur = list(self.assembly.getChildParamValues(param))
            ref = []
            x = 0
            for b in self.blockList:
                ref.append(self.blockList[x].p[param])
                x += 1
            places = 6
            self.assertAlmostEqual(cur, ref, places=places)

    def test_getMaxParam(self):

        for bi, b in enumerate(self.assembly):
            b.p.power = bi
        self.assertAlmostEqual(
            self.assembly.getMaxParam("power"), len(self.assembly) - 1
        )

    def test_getElevationsMatchingParamValue(self):
        self.assembly[0].p.power = 0.0
        self.assembly[1].p.power = 20.0
        self.assembly[2].p.power = 10.0

        heights = self.assembly.getElevationsMatchingParamValue("power", 15.0)

        self.assertListEqual(heights, [12.5, 20.0])

    def test_calcAvgParam(self):
        nums = []
        for b in self.assembly:
            nums.append(random.random())
            b.p.power = nums[-1]
        self.assertGreater(len(nums), 2)
        self.assertAlmostEqual(
            self.assembly.calcAvgParam("power"), sum(nums) / len(nums)
        )

    def test_calcTotalParam(self):
        # Remake original assembly
        self.assembly = makeTestAssembly(self.assemNum, self.assemNum)

        # add some blocks with a component
        for i in range(self.assemNum):
            b = blocks.HexBlock("TestBlock")

            # Set the 1st block to have higher params than the rest.
            self.blockParamsTemp = {}
            for key, val in self.blockParams.items():
                b.p[key] = self.blockParamsTemp[key] = (
                    val * i
                )  # Iterate with i in self.assemNum, so higher assemNums get the high values.

            b.setHeight(self.height)
            b.setType("fuel")

            self.hexDims = {
                "Tinput": 273.0,
                "Thot": 273.0,
                "op": 0.76,
                "ip": 0.0,
                "mult": 1.0,
            }

            h = components.Hexagon("intercoolant", "Sodium", **self.hexDims)

            b.add(h)

            self.assembly.add(b)

        for param in self.blockParamsTemp:
            tot = 0.0
            for b in self.assembly:
                try:
                    tot += b.p[param]
                except TypeError:
                    pass
            ref = tot

            try:
                cur = self.assembly.calcTotalParam(param)
                places = 6
                self.assertAlmostEqual(cur, ref, places=places)
            except TypeError:
                pass

    def test_reattach(self):
        # Remake original assembly
        self.assembly = makeTestAssembly(self.assemNum, self.assemNum)
        self.assertEqual(0, len(self.assembly.getBlocks()))

        # add some blocks with a component
        for i in range(self.assemNum):
            b = blocks.HexBlock("TestBlock")

            # Set the 1st block to have higher params than the rest.
            self.blockParamsTemp = {}
            for key, val in self.blockParams.items():
                # Iterate with i in self.assemNum, so higher assemNums get the high values.
                b.p[key] = self.blockParamsTemp[key] = val * (i + 1)

            b.setHeight(self.height)
            b.setType("fuel")

            self.hexDims = {
                "Tinput": 273.0,
                "Thot": 273.0,
                "op": 0.76,
                "ip": 0.0,
                "mult": 1.0,
            }

            h = components.Hexagon("intercoolant", "Sodium", **self.hexDims)
            b.add(h)

            self.assembly.add(b)

        self.assertEqual(self.assemNum, len(self.assembly.getBlocks()))
        for b in self.assembly.getBlocks():
            self.assertEqual("fuel", b.getType())

    def test_reestablishBlockOrder(self):
        self.assertEqual(self.assembly.spatialLocator.indices[0], 2)
        self.assertEqual(self.assembly[0].spatialLocator.getRingPos(), (5, 3))
        self.assertEqual(self.assembly[0].spatialLocator.indices[2], 0)
        axialIndices = [2, 1, 0]
        for ai, b in zip(axialIndices, self.assembly):
            b.spatialLocator = self.assembly.spatialGrid[0, 0, ai]
        self.assembly.reestablishBlockOrder()
        cur = []
        for b in self.assembly:
            cur.append(b.getLocation())
        ref = ["005-003-000", "005-003-001", "005-003-002"]
        self.assertEqual(cur, ref)

    def test_countBlocksOfType(self):
        cur = self.assembly.countBlocksWithFlags(Flags.IGNITER | Flags.FUEL)
        self.assertEqual(cur, 3)

    def test_getDim(self):
        cur = self.assembly.getDim(Flags.FUEL, "op")
        ref = self.hexDims["op"]
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getDominantMaterial(self):
        cur = self.assembly.getDominantMaterial(Flags.FUEL).getName()
        ref = "UZr"
        self.assertEqual(cur, ref)

        self.assertEqual(self.assembly.getDominantMaterial().getName(), ref)

    def test_iteration(self):
        r"""Tests the ability to doubly-loop over assemblies (under development)"""
        a = self.assembly

        for bi, b in enumerate(a):
            if bi == 2:
                h = 0.0
                for bi2, b2 in enumerate(a):
                    if bi2 == 0:
                        self.assertEqual(
                            b2,
                            a[0],
                            msg="First block in new iteration is not the first block of assembly",
                        )
                    h += b2.getHeight()

            # make sure the loop continues with the right counter
            self.assertEqual(
                b,
                a[bi],
                msg="The {0}th block in the loop ({1}) is not equal to the"
                " {0}th block in the assembly {2}".format(bi, b, "dummy"),
            )

    def test_getBlocksAndZ(self):
        blocksAndCenters = self.assembly.getBlocksAndZ()
        lastZ = -1.0
        for b, c in blocksAndCenters:
            self.assertIn(b, self.assembly.getBlocks())
            self.assertGreater(c, lastZ)
            lastZ = c

        self.assertRaises(TypeError, self.assembly.getBlocksAndZ, 1.0)

    def test_getBlocksBetweenElevations(self):
        # assembly should have 3 blocks of 10 cm in it

        blocksAndHeights = self.assembly.getBlocksBetweenElevations(0, 10)
        self.assertEqual(blocksAndHeights[0], (self.assembly[0], 10.0))

        blocksAndHeights = self.assembly.getBlocksBetweenElevations(0, 5.0)
        self.assertEqual(blocksAndHeights[0], (self.assembly[0], 5.0))

        blocksAndHeights = self.assembly.getBlocksBetweenElevations(1.0, 5.0)
        self.assertEqual(blocksAndHeights[0], (self.assembly[0], 4.0))

        blocksAndHeights = self.assembly.getBlocksBetweenElevations(9.0, 21.0)
        self.assertEqual(blocksAndHeights[0], (self.assembly[0], 1.0))
        self.assertEqual(blocksAndHeights[1], (self.assembly[1], 10.0))
        self.assertEqual(blocksAndHeights[2], (self.assembly[2], 1.0))

        blocksAndHeights = self.assembly.getBlocksBetweenElevations(-10, 1000.0)
        self.assertEqual(len(blocksAndHeights), len(self.assembly))
        self.assertAlmostEqual(
            sum([height for _b, height in blocksAndHeights]), self.assembly.getHeight()
        )

    def test_getParamValuesAtZ(self):
        # single value param
        for b, temp in zip(self.assembly, [800, 850, 900]):
            b.p.avgFuelTemp = temp
        avgFuelTempDef = b.p.paramDefs["avgFuelTemp"]
        originalLoc = avgFuelTempDef.location
        try:
            self.assertAlmostEqual(
                875, self.assembly.getParamValuesAtZ("avgFuelTemp", 20.0)
            )
            avgFuelTempDef.location = parameters.ParamLocation.BOTTOM
            self.assertAlmostEqual(
                825,
                self.assembly.getParamValuesAtZ("avgFuelTemp", 5.0, fillValue="extend"),
            )
            avgFuelTempDef.location = parameters.ParamLocation.TOP
            self.assertAlmostEqual(
                825, self.assembly.getParamValuesAtZ("avgFuelTemp", 15.0)
            )
            for b in self.assembly:
                b.p.avgFuelTemp = None
            self.assertTrue(
                numpy.isnan(self.assembly.getParamValuesAtZ("avgFuelTemp", 25.0))
            )

            # multiDimensional param
            for b, flux in zip(self.assembly, [[1, 10], [2, 8], [3, 6]]):
                b.p.mgFlux = flux
            self.assertTrue(
                numpy.allclose(
                    [2.5, 7.0], self.assembly.getParamValuesAtZ("mgFlux", 20.0)
                )
            )
            self.assertTrue(
                numpy.allclose(
                    [1.5, 9.0], self.assembly.getParamValuesAtZ("mgFlux", 10.0)
                )
            )
            for b in self.assembly:
                b.p.mgFlux = [0.0] * 2
            self.assertTrue(
                numpy.allclose(
                    [0.0, 0.0], self.assembly.getParamValuesAtZ("mgFlux", 10.0)
                )
            )

            # single value param at corner
            for b, temp in zip(self.assembly, [100, 200, 300]):
                b.p.THcornTemp = [temp + iCorner for iCorner in range(6)]
            value = self.assembly.getParamValuesAtZ("THcornTemp", 20.0)
            self.assertTrue(numpy.allclose([200, 201, 202, 203, 204, 205], value))
        finally:
            avgFuelTempDef.location = originalLoc

    def test_hasContinuousCoolantChannel(self):
        self.assertFalse(self.assembly.hasContinuousCoolantChannel())
        modifiedAssem = self.assembly
        coolantDims = {"Tinput": 273.0, "Thot": 273.0}
        h = components.DerivedShape("coolant", "Sodium", **coolantDims)
        for b in modifiedAssem:
            b.add(h)
        self.assertTrue(modifiedAssem.hasContinuousCoolantChannel())

    def test_carestianCoordinates(self):
        """Check the coordinates of the assembly within the core with a CarestianGrid."""
        a = makeTestAssembly(
            numBlocks=1,
            assemNum=1,
            spatialGrid=grids.CartesianGrid.fromRectangle(1.0, 1.0),
        )
        self.assertEqual(a.coords(), (2.0, 2.0))

    def test_pinPlenumVolume(self):
        """Test the volume of a pin in the assembly's plenum."""
        pinPlenumVolume = 5.951978000285659e-05

        self._setup_blueprints("refSmallReactorBase.yaml")
        assembly = self.r.blueprints.assemblies.get("igniter fuel")
        self.assertEqual(pinPlenumVolume, assembly.getPinPlenumVolumeInCubicMeters())

    def test_averagePlenumTemperature(self):
        """Test an assembly's average plenum temperature with a single block outlet."""
        averagePlenumTemp = 42.0
        plenumBlock = makeTestAssembly(
            1, 2, grids.CartesianGrid.fromRectangle(1.0, 1.0)
        )

        plenumBlock.setType("plenum", Flags.PLENUM)
        plenumBlock.p.THcoolantOutletT = averagePlenumTemp
        self.assembly.setBlockMesh([10.0, 20.0, 30.0], conserveMassFlag="auto")
        self.assembly.append(plenumBlock)

        self.assertEqual(averagePlenumTemp, self.assembly.getAveragePlenumTemperature())

    def test_rotate(self):
        """Test rotation of an assembly spatial objects"""
        a = makeTestAssembly(1, 1)
        b = blocks.HexBlock("TestBlock")
        b.p.THcornTemp = [400, 450, 500, 550, 600, 650]
        rotTemp = [600, 650, 400, 450, 500, 550]
        b.p.displacementX = 0
        b.p.displacementY = 1
        rotX = -math.sqrt(3) / 2
        rotY = -0.5
        a.add(b)
        a.rotate(math.radians(120))
        self.assertEqual(a.getBlocks()[0].p.THcornTemp, rotTemp)
        self.assertAlmostEqual(a.getBlocks()[0].p.displacementX, rotX)
        self.assertAlmostEqual(a.getBlocks()[0].p.displacementY, rotY)


class AssemblyInReactor_TestCase(unittest.TestCase):
    def setUp(self):
        self.o, self.r = test_reactors.loadTestReactor(TEST_ROOT)

    def test_snapAxialMeshToReferenceConservingMassBasedOnBlockIgniter(self):
        originalMesh = [25.0, 50.0, 75.0, 100.0, 175.0]
        refMesh = [26.0, 52.0, 79.0, 108.0, 175.0]

        grid = self.r.core.spatialGrid

        ################################
        # examine mass change in igniterFuel
        ################################
        igniterFuel = self.r.core.childrenByLocator[grid[0, 0, 0]]
        # gridplate, fuel, fuel, fuel, plenum
        b = igniterFuel[0]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        igniterMassGrid = b.getMass() - coolMass
        igniterMassGridTotal = b.getMass()

        b = igniterFuel[1]
        igniterHMMass1 = b.getHMMass()
        igniterZircMass1 = b.getMass("ZR")
        igniterFuelBlockMass = b.getMass()

        coolMass = 0
        b = igniterFuel[4]
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        igniterPlenumMass = b.getMass() - coolMass

        # expand the core to the new reference mesh
        for a in self.r.core.getAssemblies():
            a.setBlockMesh(refMesh, conserveMassFlag="auto")

        #############################
        # check igniter mass after expansion
        #############################
        # gridplate, fuel, fuel, fuel, plenum
        b = igniterFuel[0]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        igniterMassGridAfterExpand = b.getMass() - coolMass

        b = igniterFuel[1]
        igniterHMMass1AfterExpand = b.getHMMass()
        igniterZircMass1AfterExpand = b.getMass("ZR")

        coolMass = 0
        b = igniterFuel[4]
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        igniterPlenumMassAfterExpand = b.getMass() - coolMass

        self.assertAlmostEqual(igniterMassGrid, igniterMassGridAfterExpand, 7)
        self.assertAlmostEqual(igniterHMMass1, igniterHMMass1AfterExpand, 7)
        self.assertAlmostEqual(igniterZircMass1, igniterZircMass1AfterExpand, 7)
        # Note the masses are linearly different by the amount that the plenum shrunk
        self.assertAlmostEqual(
            igniterPlenumMass, igniterPlenumMassAfterExpand * 75 / 67.0, 7
        )

        # Shrink the core back to the original mesh size to see if mass is conserved
        for a in self.r.core.getAssemblies():
            a.setBlockMesh(originalMesh, conserveMassFlag="auto")

        #############################
        # check igniter mass after shrink to original
        #############################
        # gridplate, fuel, fuel, fuel, plenum
        b = igniterFuel[0]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        igniterMassGridAfterShrink = b.getMass() - coolMass
        igniterMassGridTotalAfterShrink = b.getMass()

        b = igniterFuel[1]
        igniterHMMass1AfterShrink = b.getHMMass()
        igniterZircMass1AfterShrink = b.getMass("ZR")
        igniterFuelBlockMassAfterShrink = b.getMass()

        coolMass = 0
        b = igniterFuel[4]
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        igniterPlenumMassAfterShrink = b.getMass() - coolMass

        self.assertAlmostEqual(igniterMassGrid, igniterMassGridAfterShrink, 7)
        self.assertAlmostEqual(igniterMassGridTotal, igniterMassGridTotalAfterShrink, 7)
        self.assertAlmostEqual(igniterHMMass1, igniterHMMass1AfterShrink, 7)
        self.assertAlmostEqual(igniterZircMass1, igniterZircMass1AfterShrink, 7)
        self.assertAlmostEqual(igniterFuelBlockMass, igniterFuelBlockMassAfterShrink, 7)
        self.assertAlmostEqual(igniterPlenumMass, igniterPlenumMassAfterShrink, 7)

    def test_snapAxialMeshToReferenceConservingMassBasedOnBlockShield(self):
        originalMesh = [25.0, 50.0, 75.0, 100.0, 175.0]
        refMesh = [26.0, 52.0, 79.0, 108.0, 175.0]

        # access the shield in ring 9, pos 2
        grid = self.r.core.spatialGrid
        i, j = grid.getIndicesFromRingAndPos(9, 2)

        ################################
        # examine mass change in radial shield
        ################################
        a = self.r.core.childrenByLocator[grid[i, j, 0]]
        # gridplate, axial shield, axial shield, axial shield, plenum
        b = a[0]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        shieldMassGrid = b.getMass() - coolMass

        b = a[1]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        shieldShieldMass = b.getMass() - coolMass

        b = a[4]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        shieldPlenumMass = b.getMass() - coolMass

        # expand the core to the new reference mesh
        for a in self.r.core.getAssemblies():
            a.setBlockMesh(refMesh, conserveMassFlag="auto")

        ################################
        # examine mass change in radial shield after expansion
        ################################
        # gridplate, axial shield, axial shield, axial shield, plenum
        b = a[0]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        shieldMassGridAfterExpand = b.getMass() - coolMass

        b = a[1]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        shieldShieldMassAfterExpand = b.getMass() - coolMass

        b = a[4]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        shieldPlenumMassAfterExpand = b.getMass() - coolMass

        # non mass conserving expansions
        self.assertAlmostEqual(
            shieldMassGrid * 26.0 / 25.0, shieldMassGridAfterExpand, 7
        )
        self.assertAlmostEqual(
            shieldShieldMass * 26.0 / 25.0, shieldShieldMassAfterExpand, 7
        )
        self.assertAlmostEqual(
            shieldPlenumMass, shieldPlenumMassAfterExpand * 75.0 / 67.0, 7
        )

        # Shrink the core back to the original mesh size to see if mass is conserved
        for a in self.r.core.getAssemblies():
            a.setBlockMesh(originalMesh, conserveMassFlag="auto")

        ################################
        # examine mass change in radial shield after shrink to original
        ################################
        # gridplate, axial shield, axial shield, axial shield, plenum
        b = a[0]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        shieldMassGridAfterShrink = b.getMass() - coolMass

        b = a[1]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        shieldShieldMassAfterShrink = b.getMass() - coolMass

        b = a[4]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        shieldPlenumMassAfterShrink = b.getMass() - coolMass

        # non mass conserving expansions
        self.assertAlmostEqual(shieldMassGrid, shieldMassGridAfterShrink, 7)
        self.assertAlmostEqual(shieldShieldMass, shieldShieldMassAfterShrink, 7)
        self.assertAlmostEqual(shieldPlenumMass, shieldPlenumMassAfterShrink, 7)


class AnnularFuelTestCase(unittest.TestCase):
    """Test fuel with a whole in the center"""

    # pylint: disable=locally-disabled,protected-access
    def setUp(self):
        self.cs = settings.Settings()
        newSettings = {"xsKernel": "MC2v2"}  # don't try to expand elementals
        self.cs = self.cs.modified(newSettings=newSettings)

        settings.setMasterCs(self.cs)
        bp = blueprints.Blueprints()
        self.r = reactors.Reactor("test", bp)
        self.r.add(reactors.Core("Core"))

        inputStr = """blocks:
    ann fuel: &block_ann_fuel
        gap:
            shape: Circle
            material: Void
            Tinput: 20.0
            Thot: 435.0
            id: 0.0
            mult: fuel.mult
            od: fuel.id
        fuel:
            shape: Circle
            material: UZr
            Tinput: 20.0
            Thot: 600.0
            id: 0.1
            mult: 127
            od: 0.8
        gap1:
            shape: Circle
            material: Void
            Tinput: 20.0
            Thot: 435.0
            id: fuel.od
            mult: fuel.mult
            od: clad.id
        clad:
            shape: Circle
            material: HT9
            Tinput: 20.0
            Thot: 435.0
            id: .85
            mult: fuel.mult
            od: .95
        duct: &component_type2_fuel_duct
            shape: Hexagon
            material: HT9
            Tinput: 20.0
            Thot: 435.0
            ip: 13.00
            op: 13.9
            mult: 1
        intercoolant: &component_type2_fuel_intercoolant
            shape: Hexagon
            material: Sodium
            Tinput: 435.0
            Thot: 435.0
            ip: duct.op
            mult: 1
            op: 16
        coolant: &component_type2_fuel_coolant
            shape: DerivedShape
            material: Sodium
            Tinput: 435.0
            Thot: 435.0
assemblies:
    heights: &standard_heights [30.0]
    axial mesh points: &standard_axial_mesh_points [2]
    ann fuel:
        specifier: FA
        blocks: &inner_igniter_fuel_blocks [*block_ann_fuel]
        height: *standard_heights
        axial mesh points: *standard_axial_mesh_points
        hotChannelFactors: TWRPclad
        xs types:  &inner_igniter_fuel_xs_types [D]
"""
        self.blueprints = blueprints.Blueprints.load(inputStr)
        self.blueprints._prepConstruction(self.cs)

    def test_areaCheck(self):
        assembly = list(self.blueprints.assemblies.values())[0]
        fuelBlock = assembly.getFirstBlock(Flags.FUEL)
        intercoolant = fuelBlock.getComponent(Flags.INTERCOOLANT)

        bpAssemblyArea = assembly.getArea()
        actualAssemblyArea = math.sqrt(3) / 2.0 * intercoolant.p.op ** 2

        self.assertAlmostEqual(bpAssemblyArea, actualAssemblyArea)


if __name__ == "__main__":
    unittest.main()
