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
import random
import unittest

from numpy.testing import assert_allclose

from armi import settings
from armi import tests
from armi.reactor import assemblies
from armi.reactor import blueprints
from armi.reactor import components
from armi.reactor import geometry
from armi.reactor import parameters
from armi.reactor import reactors
from armi.reactor.assemblies import *
from armi.tests import TEST_ROOT
from armi.utils import directoryChangers
from armi.utils import textProcessors
import armi.reactor.tests.test_reactors


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

    block = blocks.HexBlock("fuel", caseSetting)
    block2 = blocks.HexBlock("fuel", caseSetting)
    block.setType("fuel")
    block.setHeight(10.0)
    block.addComponent(fuelUZr)
    block.addComponent(fuelUTh)
    block.addComponent(clad)
    block.addComponent(interSodium)
    block.p.axMesh = 1
    block.p.molesHmBOL = 1.0
    block.p.molesHmNow = 1.0

    block2.setType("fuel")
    block2.setHeight(10.0)
    block2.addComponent(fuelUThZr)
    block2.addComponent(clad)
    block2.addComponent(interSodium)
    block2.p.axMesh = 1
    block2.p.molesHmBOL = 2
    block2.p.molesHmNow = 1.0

    assemblieObjs = []
    for numBlocks, blockTemplate in zip([1, 1, 5, 4], [block, block2, block, block]):
        assembly = assemblies.HexAssembly("testAssemblyType")
        assembly.spatialGrid = grids.axialUnitGrid(numBlocks)
        assembly.spatialGrid.armiObject = assembly
        for i in range(numBlocks):
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


def makeTestAssembly(numBlocks, assemNum, pitch=1.0, r=None):
    coreGrid = r.core.spatialGrid if r is not None else grids.hexGridFromPitch(pitch)
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
        runLog.setVerbosity(
            "error"
        )  # Print nothing to the screen that would normally go to the log.

        self.r = tests.getEmptyHexReactor()
        self.r.core.symmetry = "third periodic"

        self.Assembly = makeTestAssembly(NUM_BLOCKS, self.assemNum, r=self.r)
        self.r.core.add(self.Assembly)

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
            "nC": 0.0002082939655729809,
            "nCr": 0.002886865228214986,
            "nFe": 0.018938452726904774,
            "nMn55": 0.00013661373306056112,
            "nMo": 0.0001303849595025718,
            "nNa23": 0.009129000958507699,
            "nNi": 0.00010656078341023939,
            "nSi": 0.00017815341899661907,
            "nU235": 0.0011370748450841566,
            "nU238": 0.01010441040669961,
            "nV": 6.138819542030269e-05,
            "nW182": 9.01562910227868e-06,
            "nW183": 4.868378420270543e-06,
            "nW184": 1.042392172896758e-05,
            "nW186": 9.671859458339502e-06,
            "nZr": 0.003255278491569621,
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
            b = blocks.HexBlock("TestHexBlock", self.cs)
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
            b.addComponent(h)
            b.parent = self.Assembly
            b.setName(b.makeName(self.Assembly.getNum(), i))
            self.Assembly.add(b)
            self.blockList.append(b)

        self.Assembly.calculateZCoords()

    def test_resetAssemNumCounter(self):
        armi.reactor.assemblies.resetAssemNumCounter()
        cur = 0
        ref = armi.reactor.assemblies._assemNum
        self.assertEqual(cur, ref)

    def test_iter(self):
        cur = []
        for block in self.Assembly:
            cur.append(block)
        ref = self.blockList
        self.assertEqual(cur, ref)

    def test_len(self):
        cur = len(self.Assembly)
        ref = len(self.blockList)
        self.assertEqual(cur, ref)

    def test_append(self):
        b = blocks.HexBlock("TestBlock", self.cs)
        self.blockList.append(b)
        self.Assembly.append(b)
        cur = self.Assembly.getBlocks()
        ref = self.blockList
        self.assertEqual(cur, ref)

    def test_extend(self):
        blockList = []
        for i in range(2):
            b = blocks.HexBlock("TestBlock", self.cs)
            self.blockList.append(b)
            blockList.append(b)

        self.Assembly.extend(blockList)
        cur = self.Assembly.getBlocks()
        ref = self.blockList
        self.assertEqual(cur, ref)

    def test_add(self):
        a = makeTestAssembly(1, 1)
        b = blocks.HexBlock("TestBlock")
        a.add(b)
        self.assertIn(b, a)
        self.assertEqual(b.parent, a)

    def test_moveTo(self):
        location = locations.HexLocation(i1=3, i2=10)
        i, j = grids.getIndicesFromRingAndPos(3, 10)
        locator = self.r.core.spatialGrid[i, j, 0]
        self.Assembly.moveTo(locator)

        cur = self.Assembly.getLocation()
        ref = str(location)
        self.assertEqual(cur, ref)

        self.assertEqual(self.Assembly.getLocationObject().label, "A3010")

    def test_getName(self):
        cur = self.Assembly.getName()
        ref = self.name
        self.assertEqual(cur, ref)

    def test_getNum(self):
        cur = self.Assembly.getNum()
        ref = self.assemNum
        self.assertEqual(cur, ref)

    def test_getLocation(self):
        cur = self.Assembly.getLocation()
        ref = str("A5003")
        self.assertEqual(cur, ref)

    def test_getLocationObject(self):
        cur = self.Assembly.getLocationObject()
        self.assertEqual(str(cur), "A5003")

    def test_getArea(self):
        cur = self.Assembly.getArea()
        ref = math.sqrt(3) / 2.0 * self.hexDims["op"] ** 2
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getVolume(self):
        cur = self.Assembly.getVolume()
        ref = math.sqrt(3) / 2.0 * self.hexDims["op"] ** 2 * self.height * NUM_BLOCKS
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_doubleResolution(self):
        b = self.Assembly[0]
        initialHeight = b.p.heightBOL
        self.Assembly.doubleResolution()
        cur = len(self.Assembly.getBlocks())
        ref = 2 * len(self.blockList)
        self.assertEqual(cur, ref)

        cur = self.Assembly.getBlocks()[0].getHeight()
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
        for i in range(assemNum2):
            b = blocks.HexBlock("TestBlock", self.cs)
            b.setHeight(height2)
            assembly2.add(b)

        self.Assembly.adjustResolution(assembly2)

        cur = len(self.Assembly.getBlocks())
        ref = 4.0 * len(self.blockList)
        self.assertEqual(cur, ref)

        cur = self.Assembly.getBlocks()[0].getHeight()
        ref = self.height / 4.0
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getAxialMesh(self):
        cur = self.Assembly.getAxialMesh()
        ref = [i * self.height + self.height for i in range(NUM_BLOCKS)]
        self.assertEqual(cur, ref)

    def test_calculateZCoords(self):
        self.Assembly.calculateZCoords()

        places = 6
        bottom = 0.0
        for b in self.Assembly:
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
        cur = self.Assembly.getTotalHeight()
        ref = self.height * NUM_BLOCKS
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getHeight(self):
        cur = self.Assembly.getHeight()
        ref = self.height * NUM_BLOCKS
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getReactiveHeight(self):
        self.Assembly[2].getComponent(Flags.FUEL).adjustMassEnrichment(0.01)
        self.Assembly[2].setNumberDensity("PU239", 0.0)
        bottomElevation, reactiveHeight = self.Assembly.getReactiveHeight(
            enrichThresh=0.02
        )
        self.assertEqual(bottomElevation, 0.0)
        self.assertEqual(reactiveHeight, 20.0)

    def test_getFissileMass(self):
        cur = self.Assembly.getFissileMass()
        ref = sum(bi.getMass(["U235", "PU239"]) for bi in self.Assembly)
        self.assertAlmostEqual(cur, ref)

    def test_getPuFrac(self):
        puAssem = self.Assembly.getPuFrac()
        fuelBlock = self.Assembly[1]
        puBlock = fuelBlock.getPuFrac()
        self.assertAlmostEqual(puAssem, puBlock)

        #
        fuelComp = fuelBlock.getComponent(Flags.FUEL)
        fuelComp.setNumberDensity("PU239", 0.012)
        self.assertGreater(self.Assembly.getPuFrac(), puAssem)
        self.assertGreater(fuelBlock.getPuFrac(), puAssem)

    def test_getMass(self):
        mass0 = self.Assembly.getMass("U235")
        mass1 = sum(bi.getMass("U235") for bi in self.Assembly)
        self.assertAlmostEqual(mass0, mass1)

        fuelBlock = self.Assembly.getBlocks(Flags.FUEL)[0]
        blockU35Mass = fuelBlock.getMass("U235")
        fuelBlock.setMass("U235", 2 * blockU35Mass)
        self.assertAlmostEqual(fuelBlock.getMass("U235"), blockU35Mass * 2)
        self.assertAlmostEqual(self.Assembly.getMass("U235"), mass0 + blockU35Mass)

        fuelBlock.setMass("U238", 0.0)
        self.assertAlmostEqual(blockU35Mass * 2, fuelBlock.getMass("U235"))

    def test_getZrFrac(self):
        self.assertAlmostEqual(self.Assembly.getZrFrac(), 0.1)

    def test_getMaxUraniumMassEnrich(self):
        baseEnrich = self.Assembly[0].getUraniumMassEnrich()
        self.assertAlmostEqual(self.Assembly.getMaxUraniumMassEnrich(), baseEnrich)
        self.Assembly[2].setNumberDensity("U235", 2e-1)
        self.assertGreater(self.Assembly.getMaxUraniumMassEnrich(), baseEnrich)

    def test_getAge(self):
        res = 5.0
        for b in self.Assembly:
            b.p.residence = res

        cur = self.Assembly.getAge()
        ref = res
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_makeAxialSnapList(self):
        # Make a second assembly with 4 times the resolution
        assemNum2 = self.assemNum * 4
        height2 = self.height / 4.0
        assembly2 = makeTestAssembly(assemNum2, assemNum2)

        # add some blocks with a component
        for i in range(assemNum2):

            self.hexDims = {
                "Tinput": 273.0,
                "Thot": 273.0,
                "op": 0.76,
                "ip": 0.0,
                "mult": 1.0,
            }

            h = components.Hexagon("fuel", "UZr", **self.hexDims)
            b = blocks.HexBlock("fuel", self.cs)
            b.setType("igniter fuel")
            b.addComponent(h)
            b.setHeight(height2)
            assembly2.add(b)

        self.Assembly.makeAxialSnapList(assembly2)

        cur = []
        for b in self.Assembly:
            cur.append(b.p.topIndex)

        ref = [3, 7, 11]
        self.assertEqual(cur, ref)

    def test_snapAxialMeshToReference(self):
        ref = [11, 22, 33]
        for b, i in zip(self.Assembly, range(self.assemNum)):
            b.p.topIndex = i

        self.Assembly.setBlockMesh(ref)

        cur = []
        for b in self.Assembly:
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

        for param in params:
            assembly2.p[param] = params[param]

        self.Assembly.updateParamsFrom(assembly2)

        for param in params:
            cur = self.Assembly.p[param]
            ref = params[param]
            self.assertEqual(cur, ref)

    def _setup_blueprints(self):
        # need this for the getAllNuclides call
        with directoryChangers.DirectoryChanger(TEST_ROOT):
            self.cs["loadingFile"] = "refSmallReactor.yaml"
            with open(self.cs["loadingFile"], "r") as y:
                y = textProcessors.resolveMarkupInclusions(y)
                self.r.blueprints = blueprints.Blueprints.load(y)

            self.r.blueprints._prepConstruction(self.cs)

    def test_duplicate(self):
        self._setup_blueprints()

        # Perform the copy
        assembly2 = copy.deepcopy(self.Assembly)

        for refBlock, curBlock in zip(self.Assembly, assembly2):
            numNucs = 0
            for nuc in self.Assembly.getAncestorWithFlags(
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
        for b, b2 in zip(self.Assembly, assembly2):
            ref = b.getHeight()
            cur = b2.getHeight()
            self.assertEqual(cur, ref)
            assert_allclose(b.spatialLocator.indices, b2.spatialLocator.indices)

        # Assembly level params
        for param in self.Assembly.p:
            if param == "serialNum":
                continue
            ref = self.Assembly.p[param]
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
        self.Assembly.setType("fuel")

        cur = self.Assembly.hasFlags(Flags.FUEL)
        self.assertTrue(cur)

    def test_renameBlocksAccordingToAssemblyNum(self):
        self.Assembly.p.assemNum = 55
        self.Assembly.renameBlocksAccordingToAssemblyNum()
        self.assertIn(
            "{0:04d}".format(self.Assembly.getNum()), self.Assembly[1].getName()
        )

    def test_getBlocks(self):
        cur = self.Assembly.getBlocks()
        ref = self.blockList
        self.assertEqual(cur, ref)

    def test_getFirstBlock(self):
        cur = self.Assembly.getFirstBlock()
        ref = self.blockList[0]
        self.assertAlmostEqual(cur, ref)

    def test_getFirstBlockByType(self):
        b = self.Assembly.getFirstBlockByType("igniter fuel unitst")
        self.assertEqual(b.getType(), "igniter fuel unitst")
        b = self.Assembly.getFirstBlockByType("i do not exist")
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
        for b in self.Assembly:
            for param in paramDict:
                b.p[param] = paramDict[param]

        for param in paramDict:
            cur = list(self.Assembly.getChildParamValues(param))
            ref = []
            x = 0
            for b in self.blockList:
                ref.append(self.blockList[x].p[param])
                x += 1
            places = 6
            self.assertAlmostEqual(cur, ref, places=places)

    def test_getMaxParam(self):

        for bi, b in enumerate(self.Assembly):
            b.p.power = bi
        self.assertAlmostEqual(
            self.Assembly.getMaxParam("power"), len(self.Assembly) - 1
        )

    def test_getElevationsMatchingParamValue(self):
        self.Assembly[0].p.power = 0.0
        self.Assembly[1].p.power = 20.0
        self.Assembly[2].p.power = 10.0

        heights = self.Assembly.getElevationsMatchingParamValue("power", 15.0)

        self.assertListEqual(heights, [12.5, 20.0])

    def test_calcAvgParam(self):
        nums = []
        for b in self.Assembly:
            nums.append(random.random())
            b.p.power = nums[-1]
        self.assertGreater(len(nums), 2)
        self.assertAlmostEqual(
            self.Assembly.calcAvgParam("power"), sum(nums) / len(nums)
        )

    def test_calcTotalParam(self):
        # Remake original assembly
        self.Assembly = self.Assembly = makeTestAssembly(self.assemNum, self.assemNum)

        # add some blocks with a component
        for i in range(self.assemNum):
            b = blocks.HexBlock("TestBlock", self.cs)

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

            b.addComponent(h)

            self.Assembly.add(b)

        for param in self.blockParamsTemp:
            tot = 0.0
            for b in self.Assembly:
                try:
                    tot += b.p[param]
                except TypeError:
                    pass
            ref = tot

            try:
                cur = self.Assembly.calcTotalParam(param)
                places = 6
                self.assertAlmostEqual(cur, ref, places=places)
            except TypeError:
                pass

    def test_reattach(
        self,
    ):  # TODO: this got changed, should make sure it still tests what is intended
        # Remake original assembly
        self.Assembly = makeTestAssembly(self.assemNum, self.assemNum)

        # add some blocks with a component
        for i in range(self.assemNum):
            b = blocks.HexBlock("TestBlock", self.cs)

            # Set the 1st block to have higher params than the rest.
            self.blockParamsTemp = {}
            for key, val in self.blockParams.items():
                b.p[key] = self.blockParamsTemp[key] = val * (
                    i + 1
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
            b.addComponent(h)

            self.Assembly.add(b)

    def test_reestablishBlockOrder(self):
        self.assertEqual(self.Assembly.spatialLocator.indices[0], 2)
        self.assertEqual(self.Assembly[0].getLocation(), "A5003A")
        axialIndices = [2, 1, 0]
        for ai, b in zip(axialIndices, self.Assembly):
            b.spatialLocator = self.Assembly.spatialGrid[0, 0, ai]
        self.Assembly.reestablishBlockOrder()
        cur = []
        for b in self.Assembly:
            cur.append(b.getLocation())
        ref = ["A5003A", "A5003B", "A5003C"]
        self.assertEqual(cur, ref)

    def test_countBlocksOfType(self):
        cur = self.Assembly.countBlocksWithFlags(Flags.IGNITER | Flags.FUEL)
        self.assertEqual(cur, 3)

    def test_axiallyExpandBlockHeights(self):
        r""" heightList = list of floats.  Entry 0 represents the bottom fuel block closes to the grid plate.  Enrty n represents the top fuel block closes to the plenum
        adjust list = list of nuclides to modify """

        self.assemNum = 5

        # Remake original assembly
        self.Assembly = makeTestAssembly(self.assemNum, self.assemNum)

        # add some blocks with a component
        for i in range(self.assemNum):
            b = blocks.HexBlock("TestBlock", self.cs)

            # Set the 1st block to have higher params than the rest.
            self.blockParamsTemp = {}
            for key, val in self.blockParams.items():
                b.p[key] = self.blockParamsTemp[key] = val * (
                    i + 1
                )  # Iterate with i in self.assemNum, so higher assemNums get the high values.

            b.setHeight(self.height)

            self.hexDims = {
                "Tinput": 273.0,
                "Thot": 273.0,
                "op": 0.76,
                "ip": 0.0,
                "mult": 1.0,
            }

            if (i == 0) or (i == 4):
                b.setType("plenum")
                h = components.Hexagon("intercoolant", "Sodium", **self.hexDims)
            else:
                b.setType("fuel")
                h = components.Hexagon("fuel", "UZr", **self.hexDims)

            b.addComponent(h)

            self.Assembly.add(b)

        expandFrac = 1.15
        heightList = [self.height * expandFrac for x in range(self.assemNum - 2)]
        adjustList = ["U238", "ZR", "U235"]

        # Get the original block heights and densities to compare to later.
        heights = {}  # Dictionary with keys of block number, values of block heights.
        densities = (
            {}
        )  # Dictionary with keys of block number, values of dictionaries with keys of nuclide, values of block nuclide density
        for i, b in enumerate(self.Assembly):
            heights[i] = b.getHeight()
            densities[i] = {}
            for nuc, dens in b.getNumberDensities().items():
                densities[i][nuc] = dens

        self.Assembly.axiallyExpandBlockHeights(heightList, adjustList)

        for i, b in enumerate(self.Assembly):
            # Check height
            if i == 0:
                ref = heights[i]
            elif i == 4:
                ref = heights[i] - (expandFrac - 1) * 3 * heights[i]
            else:
                ref = heights[i] * expandFrac
            cur = b.getHeight()
            places = 6
            self.assertAlmostEqual(cur, ref, places=places)

            # Check densities
            for nuc, dens in b.getNumberDensities().items():
                if (i == 0) or (i == 4):
                    ref = densities[i][nuc]
                else:
                    ref = densities[i][nuc] / expandFrac
                cur = b.getNumberDensity(nuc)
                places = 6
                self.assertAlmostEqual(cur, ref, places=places)

    def test_axiallyExpand(self):
        """Build an assembly, grow it, and check it."""
        self.assemNum = 5

        # Remake original assembly
        self.Assembly = makeTestAssembly(self.assemNum, self.assemNum)
        # add some blocks with a component
        for blockI in range(self.assemNum):
            b = blocks.HexBlock("TestBlock", self.cs)

            # Set the 1st block to have higher params than the rest.
            self.blockParamsTemp = {}
            for key, val in self.blockParams.items():
                b.p[key] = self.blockParamsTemp[key] = val * (
                    blockI + 1
                )  # Iterate with i in self.assemNum, so higher assemNums get the high values.
            b.setHeight(self.height)
            self.hexDims = {
                "Tinput": 273.0,
                "Thot": 273.0,
                "op": 0.76,
                "ip": 0.0,
                "mult": 1.0,
            }
            if (blockI == 0) or (blockI == 4):
                b.setType("plenum")
                h = components.Hexagon("intercoolant", "Sodium", **self.hexDims)
            else:
                b.setType("fuel")
                h = components.Hexagon("fuel", "UZr", **self.hexDims)
            b.addComponent(h)
            self.Assembly.add(b)

        expandFrac = 1.15
        adjustList = ["U238", "ZR", "U235"]

        # Get the original block heights and densities to compare to later.
        heights = {}  # Dictionary with keys of block number, values of block heights.
        densities = (
            {}
        )  # Dictionary with keys of block number, values of dictionaries with keys of nuclide, values of block nuclide density
        for i, b in enumerate(self.Assembly):
            heights[i] = b.getHeight()
            densities[i] = {}
            for nuc, dens in b.getNumberDensities().items():
                densities[i][nuc] = dens

        expandPercent = (expandFrac - 1) * 100
        self.Assembly.axiallyExpand(expandPercent, adjustList)

        for i, b in enumerate(self.Assembly):
            # Check height
            if i == 0:
                # bottom block should be unchanged (because plenum)
                ref = heights[i]
            elif i == 4:
                # plenum on top should have grown by 15% of the uniform height * 3 (for each fuel block)
                ref = heights[i] - (expandFrac - 1) * 3 * heights[i]
            else:
                # each of the three fuel blocks should be 15% bigger.
                ref = heights[i] * expandFrac
            self.assertAlmostEqual(b.getHeight(), ref)

            # Check densities
            for nuc, dens in b.getNumberDensities().items():
                if (i == 0) or (i == 4):
                    # these blocks should be unchanged in mass/density.
                    ref = densities[i][nuc]
                else:
                    # fuel blocks should have all three nuclides reduced.
                    ref = densities[i][nuc] / expandFrac
                places = 6
                self.assertAlmostEqual(dens, ref, places=places)

    def test_getDim(self):
        cur = self.Assembly.getDim(Flags.FUEL, "op")
        ref = self.hexDims["op"]
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)

    def test_getDominantMaterial(self):
        cur = self.Assembly.getDominantMaterial(Flags.FUEL).getName()
        ref = "UZr"
        self.assertEqual(cur, ref)

        self.assertEqual(self.Assembly.getDominantMaterial().getName(), ref)

    def test_iteration(self):
        r"""
        Tests the ability to doubly-loop over assemblies (under development)
        """
        a = self.Assembly

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
        blocksAndCenters = self.Assembly.getBlocksAndZ()
        lastZ = -1.0
        for b, c in blocksAndCenters:
            self.assertIn(b, self.Assembly.getBlocks())
            self.assertGreater(c, lastZ)
            lastZ = c

        self.assertRaises(TypeError, self.Assembly.getBlocksAndZ, 1.0)

    def test_getBlocksBetweenElevations(self):
        # assembly should have 3 blocks of 10 cm in it

        blocksAndHeights = self.Assembly.getBlocksBetweenElevations(0, 10)
        self.assertEqual(blocksAndHeights[0], (self.Assembly[0], 10.0))

        blocksAndHeights = self.Assembly.getBlocksBetweenElevations(0, 5.0)
        self.assertEqual(blocksAndHeights[0], (self.Assembly[0], 5.0))

        blocksAndHeights = self.Assembly.getBlocksBetweenElevations(1.0, 5.0)
        self.assertEqual(blocksAndHeights[0], (self.Assembly[0], 4.0))

        blocksAndHeights = self.Assembly.getBlocksBetweenElevations(9.0, 21.0)
        self.assertEqual(blocksAndHeights[0], (self.Assembly[0], 1.0))
        self.assertEqual(blocksAndHeights[1], (self.Assembly[1], 10.0))
        self.assertEqual(blocksAndHeights[2], (self.Assembly[2], 1.0))

        blocksAndHeights = self.Assembly.getBlocksBetweenElevations(-10, 1000.0)
        self.assertEqual(len(blocksAndHeights), len(self.Assembly))
        self.assertAlmostEqual(
            sum([height for _b, height in blocksAndHeights]), self.Assembly.getHeight()
        )

    def test_getParamValuesAtZ(self):
        # single value param
        for b, temp in zip(self.Assembly, [800, 850, 900]):
            b.p.avgFuelTemp = temp
        avgFuelTempDef = b.p.paramDefs["avgFuelTemp"]
        originalLoc = avgFuelTempDef.location
        try:
            self.assertAlmostEqual(
                875, self.Assembly.getParamValuesAtZ("avgFuelTemp", 20.0)
            )
            avgFuelTempDef.location = parameters.ParamLocation.BOTTOM
            self.assertAlmostEqual(
                825,
                self.Assembly.getParamValuesAtZ("avgFuelTemp", 5.0, fillValue="extend"),
            )
            avgFuelTempDef.location = parameters.ParamLocation.TOP
            self.assertAlmostEqual(
                825, self.Assembly.getParamValuesAtZ("avgFuelTemp", 15.0)
            )
            for b in self.Assembly:
                b.p.avgFuelTemp = None
            self.assertTrue(
                numpy.isnan(self.Assembly.getParamValuesAtZ("avgFuelTemp", 25.0))
            )

            # multiDimensional param
            for b, flux in zip(self.Assembly, [[1, 10], [2, 8], [3, 6]]):
                b.p.mgFlux = flux
            self.assertTrue(
                numpy.allclose(
                    [2.5, 7.0], self.Assembly.getParamValuesAtZ("mgFlux", 20.0)
                )
            )
            self.assertTrue(
                numpy.allclose(
                    [1.5, 9.0], self.Assembly.getParamValuesAtZ("mgFlux", 10.0)
                )
            )
            for b in self.Assembly:
                b.p.mgFlux = [0.0] * 2
            self.assertTrue(
                numpy.allclose(
                    [0.0, 0.0], self.Assembly.getParamValuesAtZ("mgFlux", 10.0)
                )
            )

            # single value param at corner
            for b, temp in zip(self.Assembly, [100, 200, 300]):
                b.p.THcornTemp = [temp + iCorner for iCorner in range(6)]
            value = self.Assembly.getParamValuesAtZ("THcornTemp", 20.0)
            self.assertTrue(numpy.allclose([200, 201, 202, 203, 204, 205], value))
        finally:
            avgFuelTempDef.location = originalLoc

    def test_hasContinuousCoolantChannel(self):
        self.assertFalse(self.Assembly.hasContinuousCoolantChannel())
        modifiedAssem = self.Assembly
        coolantDims = {"Tinput": 273.0, "Thot": 273.0}
        h = components.DerivedShape("coolant", "Sodium", **coolantDims)
        for b in modifiedAssem:
            b.addComponent(h)
        self.assertTrue(modifiedAssem.hasContinuousCoolantChannel())


class HexAssembly_TestCase(unittest.TestCase):
    def setUp(self):
        self.name = "A0015"
        self.assemNum = 3
        self.height = 10
        self.cs = settings.Settings()
        self.cs[
            "verbosity"
        ] = "error"  # Print nothing to the screen that would normally go to the log.
        self.cs["stationaryBlocks"] = []
        self.HexAssembly = makeTestAssembly(self.assemNum, self.assemNum, 0.76)
        # add some blocks with a component
        self.blockList = []
        for i in range(self.assemNum):
            b = blocks.HexBlock("TestBlock", self.cs)
            b.setHeight(self.height)
            self.hexDims = {
                "Tinput": 273.0,
                "Thot": 273.0,
                "op": 0.76,
                "ip": 0.0,
                "mult": 1.0,
            }

            h = components.Hexagon("fuel", "UZr", **self.hexDims)
            b.setType("defaultType")
            b.addComponent(h)
            self.HexAssembly.add(b)
            self.blockList.append(b)

    def tearDown(self):
        self.HexAssembly = None

    def test_getPitch(self):
        pList = []
        for b in self.HexAssembly:
            pList.append(b.getPitch())

        cur = self.HexAssembly.getPitch()
        ref = numpy.average(pList)
        places = 6
        self.assertAlmostEqual(cur, ref, places=places)


class CartesianAssembly_TestCase(unittest.TestCase):
    def setUp(self):
        self.name = "A0015"
        self.assemNum = 3
        self.height = 10
        self.cs = settings.Settings()
        self.cs[
            "verbosity"
        ] = "error"  # Print nothing to the screen that would normally go to the log.
        self.cs["stationaryBlocks"] = []
        reactorGrid = grids.cartesianGridFromRectangle(1.0, 1.0)
        a = self.CartesianAssembly = CartesianAssembly(
            "defaultType", assemNum=self.assemNum
        )
        a.spatialGrid = grids.axialUnitGrid(self.assemNum)
        a.spatialLocator = grids.IndexLocation(5, 3, 0, reactorGrid)
        a.spatialGrid.armiObject = a

        # add some blocks with a component
        self.blockList = []

        for _i in range(self.assemNum):
            b = blocks.CartesianBlock("TestCartesianBlock", self.cs)
            b.setHeight(self.height)

            self.cartesianDims = {
                "Tinput": 273.0,
                "Thot": 273.0,
                "widthOuter": 1.0,
                "widthInner": 0.0,
                "mult": 1.0,
            }

            h = components.Square("fuel", "UZr", **self.cartesianDims)
            b.setType("defaultType")
            b.addComponent(h)
            self.CartesianAssembly.add(b)
            self.blockList.append(b)

    def tearDown(self):
        self.CartesianAssembly = None

    def test_coords(self):
        """
        Check coordinates of a Cartesian grid.

        A default Cartesian grid has the center square centered at 0,0.
        So a square at index 5, 3  with indexing starting at 0
        would be centered at 5.0. 3.0.
        """
        cur = self.CartesianAssembly.coords()
        self.assertEqual(cur, (5.0, 3.0))


class AssemblyInReactor_TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        self.o, self.r = armi.reactor.tests.test_reactors.loadTestReactor(TEST_ROOT)

    def test_snapAxialMeshToReferenceConservingMassBasedOnBlockIgniter(self):
        originalMesh = [25.0, 50.0, 75.0, 100.0, 175.0]
        refMesh = [26.0, 52.0, 79.0, 108.0, 175.0]

        igniterFuel = "A1001"

        ################################
        # examine mass change in igniterFuel
        ################################
        a = self.r.core.getAssemblyWithStringLocation(igniterFuel)
        # gridplate, fuel, fuel, fuel, plenum
        b = a[0]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        igniterMassGrid = b.getMass() - coolMass
        igniterMassGridTotal = b.getMass()

        b = a[1]
        igniterHMMass1 = b.getHMMass()
        igniterZircMass1 = b.getMass("ZR")
        igniterFuelBlockMass = b.getMass()

        coolMass = 0
        b = a[4]
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        igniterPlenumMass = b.getMass() - coolMass

        # expand the core to the new reference mesh
        for a in self.r.core.getAssemblies():
            a.setBlockMesh(refMesh, conserveMassFlag="auto")

        #############################
        # check igniter mass after expansion
        #############################
        a = self.r.core.getAssemblyWithStringLocation(igniterFuel)
        # gridplate, fuel, fuel, fuel, plenum
        b = a[0]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        igniterMassGridAfterExpand = b.getMass() - coolMass

        b = a[1]
        igniterHMMass1AfterExpand = b.getHMMass()
        igniterZircMass1AfterExpand = b.getMass("ZR")

        coolMass = 0
        b = a[4]
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
        a = self.r.core.getAssemblyWithStringLocation(igniterFuel)
        # gridplate, fuel, fuel, fuel, plenum
        b = a[0]
        coolantNucs = b.getComponent(Flags.COOLANT).getNuclides()
        coolMass = 0
        for nuc in coolantNucs:
            coolMass += b.getMass(nuc)
        igniterMassGridAfterShrink = b.getMass() - coolMass
        igniterMassGridTotalAfterShrink = b.getMass()

        b = a[1]
        igniterHMMass1AfterShrink = b.getHMMass()
        igniterZircMass1AfterShrink = b.getMass("ZR")
        igniterFuelBlockMassAfterShrink = b.getMass()

        coolMass = 0
        b = a[4]
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

        shield = "A9002"

        ################################
        # examine mass change in radial shield
        ################################
        a = self.r.core.getAssemblyWithStringLocation(shield)
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
        a = self.r.core.getAssemblyWithStringLocation(shield)
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
        a = self.r.core.getAssemblyWithStringLocation(shield)
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
        self.cs["xsKernel"] = "MC2v2"  # don't try to expand elementals
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
    # import sys
    # sys.argv = ['', 'Assembly_TestCase.test_getPuFrac']
    unittest.main()
