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
"""Tests for the uniform mesh geometry converter."""

import collections
import copy
import os
import random
import unittest
from unittest.mock import Mock

import numpy as np

from armi.nuclearDataIO.cccc import isotxs
from armi.physics.neutronics.settings import CONF_XS_KERNEL
from armi.reactor.converters import uniformMesh
from armi.reactor.flags import Flags
from armi.reactor.tests import test_assemblies, test_blocks
from armi.settings.fwSettings.globalSettings import CONF_UNIFORM_MESH_MINIMUM_SIZE
from armi.testing import loadTestReactor, reduceTestReactorRings
from armi.tests import ISOAA_PATH, TEST_ROOT


class DummyFluxOptions:
    def __init__(self, cs):
        self.cs = cs
        self.photons = False
        self.calcReactionRatesOnMeshConversion = True


class TestConverterFactory(unittest.TestCase):
    def setUp(self):
        self.o, self.r = loadTestReactor(inputFilePath=os.path.join(TEST_ROOT, "detailedAxialExpansion"))

        self.dummyOptions = DummyFluxOptions(self.o.cs)

    def test_converterFactory(self):
        self.dummyOptions.photons = False
        neutronConverter = uniformMesh.converterFactory(self.dummyOptions)
        self.assertTrue(neutronConverter, uniformMesh.NeutronicsUniformMeshConverter)

        self.dummyOptions.photons = True
        gammaConverter = uniformMesh.converterFactory(self.dummyOptions)
        self.assertTrue(gammaConverter, uniformMesh.GammaUniformMeshConverter)


class TestAssemblyUniformMesh(unittest.TestCase):
    """
    Tests individual operations of the uniform mesh converter.

    Uses the test reactor for detailedAxialExpansion
    """

    def setUp(self):
        self.o, self.r = loadTestReactor(inputFilePath=os.path.join(TEST_ROOT, "detailedAxialExpansion"))

        self.converter = uniformMesh.NeutronicsUniformMeshConverter(cs=self.o.cs)
        self.converter._sourceReactor = self.r
        self.converter._setParamsToUpdate("in")

    def test_makeAssemWithUniformMesh(self):
        sourceAssem = self.r.core.getFirstAssembly(Flags.IGNITER)

        self.converter._generateUniformMesh(minimumMeshSize=0.01)
        b = sourceAssem.getFirstBlock(Flags.FUEL)
        newAssem = self.converter.makeAssemWithUniformMesh(
            sourceAssem,
            self.converter._uniformMesh,
            paramMapper=uniformMesh.ParamMapper([], ["power"], b),
            mapNumberDensities=True,
        )

        prevB = None
        for newB in newAssem:
            sourceB = sourceAssem.getBlockAtElevation(newB.p.z)
            if newB.isFuel() and sourceB.isFuel():
                self.assertEqual(newB.p["xsType"], sourceB.p["xsType"])
            elif not newB.isFuel() and not sourceB.isFuel():
                self.assertEqual(newB.p["xsType"], sourceB.p["xsType"])
            elif newB.isFuel() and not sourceB.isFuel():
                # a newB that is fuel can overwrite the xsType of a nonfuel sourceB;
                # this is the expected behavior immediately above the fuel block
                self.assertEqual(newB.p["xsType"], prevB.p["xsType"])
            elif sourceB.isFuel() and not newB.isFuel():
                raise ValueError(
                    f"The source block {sourceB} is fuel but uniform mesh convertercreated a nonfuel block {newB}."
                )
            prevB = newB

        newAssemNumberDens = newAssem.getNumberDensities()
        for nuc, val in sourceAssem.getNumberDensities().items():
            self.assertAlmostEqual(val, newAssemNumberDens[nuc])

        for nuc, val in sourceAssem.getNumberDensities().items():
            if not val:
                continue
            self.assertAlmostEqual(newAssem.getNumberOfAtoms(nuc) / sourceAssem.getNumberOfAtoms(nuc), 1.0)

    def test_makeAssemWithUniformMeshSubmesh(self):
        """If sourceAssem has submesh, check that newAssem splits into separate blocks."""
        # assign axMesh to blocks randomly
        sourceAssem = self.r.core.refAssem
        for i, b in enumerate(sourceAssem):
            b.p.axMesh = i % 2 + 1

        self.r.core.updateAxialMesh()
        newAssem = self.converter.makeAssemWithUniformMesh(
            sourceAssem,
            self.r.core.p.axialMesh[1:],
            paramMapper=uniformMesh.ParamMapper([], ["power"], b),
        )

        self.assertNotEqual(len(newAssem), len(sourceAssem))
        newHeights = [b.getHeight() for b in newAssem]
        sourceHeights = [b.getHeight() / b.p.axMesh for b in sourceAssem for i in range(b.p.axMesh)]
        self.assertListEqual(newHeights, sourceHeights)

    def test_makeAssemUniformMeshParamMappingSameMesh(self):
        """Tests creating a uniform mesh assembly while mapping both number densities and specified parameters."""
        sourceAssem = self.r.core.getFirstAssembly(Flags.IGNITER)
        for b in sourceAssem:
            b.p.flux = 1.0
            b.p.power = 10.0
            b.p.mgFlux = [1.0, 2.0]

        # Create a new assembly that has the same mesh as the source assem, but also
        # demonstrates the transfer of number densities and parameter data as a 1:1 mapping
        # without any volume integration/data migration based on a differing mesh.
        bpNames = ["flux", "power", "mgFlux"]
        newAssem = self.converter.makeAssemWithUniformMesh(
            sourceAssem,
            sourceAssem.getAxialMesh(),
            paramMapper=uniformMesh.ParamMapper([], bpNames, b),
            mapNumberDensities=True,
        )
        for b, origB in zip(newAssem, sourceAssem):
            self.assertEqual(b.p.flux, 1.0)
            self.assertEqual(b.p.power, 10.0)
            self.assertListEqual(list(b.p.mgFlux), [1.0, 2.0])

            self.assertEqual(b.p.flux, origB.p.flux)
            self.assertEqual(b.p.power, origB.p.power)
            self.assertListEqual(list(b.p.mgFlux), list(origB.p.mgFlux))
            originalNDens = origB.getNumberDensities()
            for nuc, val in b.getNumberDensities().items():
                self.assertAlmostEqual(val, originalNDens[nuc])

        # Now, let's update the flux, power, and mgFlux on the new assembly
        # and test that it can be transferred back to the source assembly.
        for b in newAssem:
            b.p.flux = 2.0
            b.p.power = 20.0
            b.p.mgFlux = [2.0, 4.0]
        bpNames = ["flux", "power", "mgFlux"]
        uniformMesh.UniformMeshGeometryConverter.setAssemblyStateFromOverlaps(
            sourceAssembly=newAssem,
            destinationAssembly=sourceAssem,
            paramMapper=uniformMesh.ParamMapper([], bpNames, b),
        )
        for b, updatedB in zip(newAssem, sourceAssem):
            self.assertEqual(b.p.flux, 2.0)
            self.assertEqual(b.p.power, 20.0)
            self.assertListEqual(list(b.p.mgFlux), [2.0, 4.0])

            self.assertEqual(b.p.flux, updatedB.p.flux)
            self.assertEqual(b.p.power, updatedB.p.power)
            self.assertListEqual(list(b.p.mgFlux), list(updatedB.p.mgFlux))
            originalNDens = updatedB.getNumberDensities()
            for nuc, val in b.getNumberDensities().items():
                self.assertAlmostEqual(val, originalNDens[nuc])

    def test_clearAssemblyState(self):
        """Tests clearing the parameter state of an assembly and returning the cached parameters."""
        sourceAssem = self.r.core.getFirstAssembly(Flags.IGNITER)
        for b in sourceAssem:
            b.p.flux = 1.0
            b.p.power = 10.0
            b.p.mgFlux = [1.0, 2.0]

        for b in sourceAssem:
            self.assertEqual(b.p.flux, 1.0)
            self.assertEqual(b.p.power, 10.0)
            self.assertListEqual(list(b.p.mgFlux), [1.0, 2.0])

        # Let's test the clearing of the assigned parameters on the source assembly.
        cachedBlockParams = uniformMesh.UniformMeshGeometryConverter.clearStateOnAssemblies(
            [sourceAssem],
            blockParamNames=["flux", "power", "mgFlux"],
            cache=True,
        )
        for b in sourceAssem:
            self.assertEqual(b.p.flux, b.p.pDefs["flux"].default)
            self.assertEqual(b.p.power, b.p.pDefs["flux"].default)
            self.assertEqual(b.p.mgFlux, b.p.pDefs["mgFlux"].default)

            self.assertEqual(cachedBlockParams[b]["flux"], 1.0)
            self.assertEqual(cachedBlockParams[b]["power"], 10.0)
            self.assertListEqual(list(cachedBlockParams[b]["mgFlux"]), [1.0, 2.0])


class TestUniformMeshGenerator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        newSettings = {
            CONF_XS_KERNEL: "MC2v2",
            CONF_UNIFORM_MESH_MINIMUM_SIZE: 3.0,
        }
        cls.o, cls.r = loadTestReactor(TEST_ROOT, customSettings=newSettings)
        reduceTestReactorRings(cls.r, cls.o.cs, 5)
        cls.r.core.lib = isotxs.readBinary(ISOAA_PATH)

        # make the mesh a little non-uniform
        a4 = cls.r.core[4]
        a4[2].setHeight(a4[2].getHeight() * 1.05)
        a3 = cls.r.core[3]
        a3[2].setHeight(a3[2].getHeight() * 1.20)

    def setUp(self):
        self.generator = uniformMesh.UniformMeshGenerator(self.r, self.o.cs[CONF_UNIFORM_MESH_MINIMUM_SIZE])

    def test_computeAverageAxialMesh(self):
        refMesh = self.r.core.findAllAxialMeshPoints([self.r.core.getFirstAssembly(Flags.FUEL)])[1:]
        self.generator._computeAverageAxialMesh()
        avgMesh = self.generator._commonMesh

        self.assertEqual(len(refMesh), len(avgMesh))
        self.assertEqual(refMesh[0], avgMesh[0])
        self.assertNotEqual(refMesh[4], avgMesh[4], "Not equal above the fuel.")

    def test_filterMesh(self):
        """
        Test that the mesh can be correctly filtered.

        .. test:: Produce a uniform mesh with a size no smaller than a user-specified value.
            :id: T_ARMI_UMC_MIN_MESH1
            :tests: R_ARMI_UMC_MIN_MESH
        """
        meshList = [1.0, 3.0, 4.0, 7.0, 9.0, 12.0, 16.0, 19.0, 20.0]
        anchorPoints = [4.0, 16.0]
        combinedMesh = self.generator._filterMesh(
            meshList,
            self.generator.minimumMeshSize,
            anchorPoints,
            preference="bottom",
        )
        self.assertListEqual(combinedMesh, [1.0, 4.0, 7.0, 12.0, 16.0, 19.0])

        combinedMesh = self.generator._filterMesh(
            meshList,
            self.generator.minimumMeshSize,
            anchorPoints,
            preference="top",
        )
        self.assertListEqual(combinedMesh, [1.0, 4.0, 9.0, 12.0, 16.0, 20.0])

        anchorPoints = [3.0, 4.0]
        with self.assertRaises(ValueError):
            self.generator._filterMesh(
                meshList,
                self.generator.minimumMeshSize,
                anchorPoints,
                preference="top",
            )

    def test_filteredTopAndBottom(self):
        fuelBottoms, fuelTops = self.generator._getFilteredMeshTopAndBottom(Flags.FUEL)
        self.assertListEqual(fuelBottoms, [25.0])
        self.assertListEqual(fuelTops, [101.25, 105.0])

        # ctrlAndFuelBottoms and ctrlAndFuelTops include the fuelBottoms and fuelTops, respectively
        (
            ctrlAndFuelBottoms,
            ctrlAndFuelTops,
        ) = self.generator._getFilteredMeshTopAndBottom(Flags.CONTROL, fuelBottoms, fuelTops)
        self.assertListEqual(ctrlAndFuelBottoms, [25.0, 50.0])
        self.assertListEqual(ctrlAndFuelTops, [75.0, 101.25, 105.0])

    def test_generateCommonMesh(self):
        """
        Covers generateCommonmesh() and _decuspAxialMesh().

        .. test:: Produce a uniform mesh with a size no smaller than a user-specified value.
            :id: T_ARMI_UMC_MIN_MESH0
            :tests: R_ARMI_UMC_MIN_MESH

        .. test:: Preserve the boundaries of fuel and control material.
            :id: T_ARMI_UMC_NON_UNIFORM0
            :tests: R_ARMI_UMC_NON_UNIFORM
        """
        self.generator.generateCommonMesh()
        expectedMesh = [
            25.0,
            50.0,
            75.0,
            101.25,
            105.0,
            119.04761904761905,
            137.79761904761904,
            156.54761904761904,
            175.29761904761904,
        ]
        self.assertListEqual(list(self.generator._commonMesh), expectedMesh)


class TestUniformMeshComponents(unittest.TestCase):
    """
    Tests individual operations of the uniform mesh converter.

    Only loads reactor once per suite.
    """

    @classmethod
    def setUpClass(cls):
        cls.o, cls.r = loadTestReactor(TEST_ROOT, customSettings={CONF_XS_KERNEL: "MC2v2"})
        reduceTestReactorRings(cls.r, cls.o.cs, 4)
        cls.r.core.lib = isotxs.readBinary(ISOAA_PATH)

        # make the mesh a little non-uniform
        a = cls.r.core[4]
        a[2].setHeight(a[2].getHeight() * 1.05)

    def setUp(self):
        self.converter = uniformMesh.NeutronicsUniformMeshConverter(cs=self.o.cs)
        self.converter._sourceReactor = self.r

    def test_blueprintCopy(self):
        """Ensure that necessary blueprint attributes are set."""
        convReactor = self.converter.initNewReactor(self.converter._sourceReactor, self.o.cs)
        converted = convReactor.blueprints
        original = self.converter._sourceReactor.blueprints
        toCompare = [
            "activeNuclides",
            "allNuclidesInProblem",
            "elementsToExpand",
            "inertNuclides",
        ]  # Note: items within toCompare must be list or "list-like", like an ordered set
        for attr in toCompare:
            for c, o in zip(getattr(converted, attr), getattr(original, attr)):
                self.assertEqual(c, o)
        # ensure that the assemblies were copied over
        self.assertTrue(converted.assemblies, msg="Assembly objects not copied!")


def applyNonUniformHeightDistribution(reactor):
    """Modifies some assemblies to have non-uniform axial meshes."""
    for a in reactor.core:
        delta = 0.0
        for b in a[:-1]:
            origHeight = b.getHeight()
            newHeight = origHeight * (1 + 0.03 * random.uniform(-1, 1))
            b.setHeight(newHeight)
            delta += newHeight - origHeight
        a[-1].setHeight(a[-1].getHeight() - delta)
        a.calculateZCoords()

    reactor.normalizeNames()


class TestUniformMesh(unittest.TestCase):
    """
    Tests full uniform mesh converter.

    Loads reactor once per test
    """

    @classmethod
    def setUpClass(cls):
        # random seed to support random mesh in unit tests below
        random.seed(987324987234)

    def setUp(self):
        self.o, self.r = loadTestReactor(TEST_ROOT, customSettings={CONF_XS_KERNEL: "MC2v2"})
        reduceTestReactorRings(self.r, self.o.cs, 3)
        self.r.core.lib = isotxs.readBinary(ISOAA_PATH)
        self.r.core.p.keff = 1.0

        self.converter = uniformMesh.NeutronicsUniformMeshConverter(cs=self.o.cs, calcReactionRates=True)

        # reactor parameters
        self.r.core.p.beta = 700
        self.r.core.p.betaComponents = [100, 150, 150, 100, 100, 100]
        self.r.core.p.power = 10
        self.reactorParamNames = ["beta", "betaComponents", "power", "keff", "keffUnc"]
        self.converter._cachedReactorCoreParamData = {"powerDensity": 1.0}
        self.paramMapper = uniformMesh.ParamMapper(self.reactorParamNames, [], self.r.core.getFirstBlock())

    def test_convertNumberDensities(self):
        """
        Test the reactor mass before and after conversion.

        .. test:: Make a copy of the reactor where the new reactor core has a uniform axial mesh.
            :id: T_ARMI_UMC
            :tests: R_ARMI_UMC
        """
        refMass = self.r.core.getMass("U235")
        # perturb the heights of the assemblies -> changes the mass of everything in the core
        applyNonUniformHeightDistribution(self.r)
        perturbedCoreMass = self.r.core.getMass("U235")
        self.assertNotEqual(refMass, perturbedCoreMass)
        self.converter.convert(self.r)

        uniformReactor = self.converter.convReactor
        uniformMass = uniformReactor.core.getMass("U235")

        # conversion conserved mass
        self.assertAlmostEqual(perturbedCoreMass, uniformMass)
        # conversion didn't change source reactor mass
        self.assertAlmostEqual(self.r.core.getMass("U235"), perturbedCoreMass)
        # conversion results in uniform axial mesh
        refAssemMesh = self.converter.convReactor.core.refAssem.getAxialMesh()
        for a in self.converter.convReactor.core:
            mesh = a.getAxialMesh()
            for ref, check in zip(refAssemMesh, mesh):
                self.assertEqual(ref, check)

    def test_applyStateToOriginal(self):
        """
        Test applyStateToOriginal() to revert mesh conversion.

        .. test:: Map select parameters from composites on the new mesh to the original mesh.
            :id: T_ARMI_UMC_PARAM_BACKWARD0
            :tests: R_ARMI_UMC_PARAM_BACKWARD
        """
        applyNonUniformHeightDistribution(self.r)  # note: this perturbs the ref mass

        self.converter.convert(self.r)
        for ib, b in enumerate(self.converter.convReactor.core.iterBlocks()):
            b.p.mgFlux = list(range(1, 34))
            b.p.adjMgFlux = list(range(1, 34))
            b.p.fastFlux = 2.0
            b.p.flux = 5.0
            b.p.power = 5.0
            b.p.pdens = 0.5
            b.p.fluxPeak = 10.0 + (-1) ** ib

        # check integral and density params
        assemblyPowers = [a.calcTotalParam("power") for a in self.converter.convReactor.core]
        totalPower = self.converter.convReactor.core.calcTotalParam("power", generationNum=2)
        totalPower2 = self.converter.convReactor.core.calcTotalParam("pdens", volumeIntegrated=True, generationNum=2)

        self.converter.applyStateToOriginal()

        for b in self.r.core.iterBlocks():
            self.assertAlmostEqual(b.p.fastFlux, 2.0)
            self.assertAlmostEqual(b.p.flux, 5.0)
            self.assertAlmostEqual(b.p.pdens, 0.5)

            # fluxPeak is mapped differently as a ParamLocation.MAX value
            # make sure that it's one of the two exact possible values
            self.assertIn(b.p.fluxPeak, [9.0, 11.0])

        for expectedPower, a in zip(assemblyPowers, self.r.core):
            self.assertAlmostEqual(a.calcTotalParam("power"), expectedPower)

        self.assertAlmostEqual(
            self.r.core.calcTotalParam("pdens", volumeIntegrated=True, generationNum=2),
            totalPower2,
        )
        self.assertAlmostEqual(self.r.core.calcTotalParam("power", generationNum=2), totalPower)

        self.converter.updateReactionRates()
        for a in self.r.core:
            for b in a:
                self.assertTrue(b.p.rateAbs)
                self.assertTrue(b.p.rateCap)

        # reactor parameters
        self.assertEqual(self.r.core.p.power, 10)
        self.assertEqual(self.r.core.p.beta, 700)
        self.assertEqual(self.r.core.p.powerDensity, 1.0)
        self.assertEqual(self.r.core.p.keff, 1.0)
        self.assertEqual(self.r.core.p.keffUnc, 0.0)
        self.assertListEqual(self.r.core.p.betaComponents, [100, 150, 150, 100, 100, 100])


class TestCalcReationRates(unittest.TestCase):
    def test_calcReactionRatesBlockList(self):
        """
        Test that the efficient reaction rate code executes and sets a param > 0.0.

        .. test:: Return the reaction rates for a given list of ArmiObjects.
            :id: T_ARMI_FLUX_RX_RATES_BY_XS_ID
            :tests: R_ARMI_FLUX_RX_RATES
        """
        b = test_blocks.loadTestBlock()
        test_blocks.applyDummyData(b)
        self.assertAlmostEqual(b.p.rateAbs, 0.0)
        blockList = [copy.deepcopy(b) for _i in range(3)]
        xsID = b.getMicroSuffix()
        xsNucDict = {nuc: b.core.lib.getNuclide(nuc, xsID) for nuc in b.getNuclides()}
        uniformMesh.UniformMeshGeometryConverter._calcReactionRatesBlockList(blockList, 1.01, xsNucDict)
        for b in blockList:
            self.assertGreater(b.p.rateAbs, 0.0)
            vfrac = b.getComponentAreaFrac(Flags.FUEL)
            self.assertEqual(b.p.fisDens, b.p.rateFis / vfrac)
            self.assertEqual(b.p.fisDensHom, b.p.rateFis)


class TestGammaUniformMesh(unittest.TestCase):
    """
    Tests gamma uniform mesh converter.

    Loads reactor once per test
    """

    @classmethod
    def setUpClass(cls):
        # random seed to support random mesh in unit tests below
        random.seed(987324987234)

    def setUp(self):
        self.o, self.r = loadTestReactor(TEST_ROOT, customSettings={CONF_XS_KERNEL: "MC2v2"})
        self.r.core.lib = isotxs.readBinary(ISOAA_PATH)
        self.r.core.p.keff = 1.0
        self.converter = uniformMesh.GammaUniformMeshConverter(cs=self.o.cs)

    def test_convertNumberDensities(self):
        refMass = self.r.core.getMass("U235")
        applyNonUniformHeightDistribution(self.r)  # this changes the mass of everything in the core
        perturbedCoreMass = self.r.core.getMass("U235")
        self.assertNotEqual(refMass, perturbedCoreMass)
        self.converter.convert(self.r)

        uniformReactor = self.converter.convReactor
        uniformMass = uniformReactor.core.getMass("U235")

        self.assertAlmostEqual(perturbedCoreMass, uniformMass)  # conversion conserved mass
        self.assertAlmostEqual(
            self.r.core.getMass("U235"), perturbedCoreMass
        )  # conversion didn't change source reactor mass

    def test_applyStateToOriginal(self):
        """
        Test applyStateToOriginal() to revert mesh conversion.

        .. test:: Map select parameters from composites on the new mesh to the original mesh.
            :id: T_ARMI_UMC_PARAM_BACKWARD1
            :tests: R_ARMI_UMC_PARAM_BACKWARD
        """
        applyNonUniformHeightDistribution(self.r)  # note: this perturbs the ref. mass

        # set original parameters on pre-mapped core with non-uniform assemblies
        for b in self.r.core.iterBlocks():
            b.p.mgFlux = list(range(33))
            b.p.adjMgFlux = list(range(33))
            b.p.fastFlux = 2.0
            b.p.flux = 5.0
            b.p.power = 5.0
            b.p.linPow = 2.0

        # set new parameters on core with uniform assemblies (emulate a physics kernel)
        self.converter.convert(self.r)
        for b in self.converter.convReactor.core.iterBlocks():
            b.p.powerGamma = 0.5
            b.p.powerNeutron = 0.5
            b.p.linPow = 10.0
            b.p.power = b.p.powerGamma + b.p.powerNeutron

        # check integral and density params
        assemblyPowers = [a.calcTotalParam("power") for a in self.converter.convReactor.core]
        assemblyGammaPowers = [a.calcTotalParam("powerGamma") for a in self.converter.convReactor.core]
        totalPower = self.converter.convReactor.core.calcTotalParam("power", generationNum=2)
        totalPowerGamma = self.converter.convReactor.core.calcTotalParam("powerGamma", generationNum=2)

        self.converter.applyStateToOriginal()

        for b in self.r.core.iterBlocks():
            # equal to original value because these were never mapped
            self.assertEqual(b.p.fastFlux, 2.0)
            self.assertEqual(b.p.flux, 5.0)

            # not equal because blocks are different size
            self.assertNotEqual(b.p.powerGamma, 0.5)
            self.assertNotEqual(b.p.powerNeutron, 0.5)
            self.assertNotEqual(b.p.power, 1.0)

            # has updated value
            self.assertAlmostEqual(b.p.linPow, 10.0)

        # equal because these are mapped
        for expectedPower, expectedGammaPower, a in zip(assemblyPowers, assemblyGammaPowers, self.r.core):
            self.assertAlmostEqual(a.calcTotalParam("power"), expectedPower)
            self.assertAlmostEqual(a.calcTotalParam("powerGamma"), expectedGammaPower)

        self.assertAlmostEqual(self.r.core.calcTotalParam("powerGamma", generationNum=2), totalPowerGamma)
        self.assertAlmostEqual(self.r.core.calcTotalParam("power", generationNum=2), totalPower)


class TestParamConversion(unittest.TestCase):
    def setUp(self):
        """
        Build two assemblies.

        The source assembly has two blocks, heights 3 and 7 cm. The destination
        has one big block that's 10 cm. Flux is set to 5 and 10 respectively on
        the two source blocks. They are populated with arbitrary flux and pdens
        values.
        """
        self.sourceAssem, self.destinationAssem = test_assemblies.buildTestAssemblies()[2:]
        self.height1 = 3.0
        self.height2 = 7.0
        self.sourceAssem[0].setHeight(self.height1)
        self.sourceAssem[0].p.flux = 5.0
        self.sourceAssem[1].setHeight(self.height2)
        self.sourceAssem[1].p.flux = 10.0
        self.sourceAssem.calculateZCoords()

        self.destinationAssem[0].setHeight(self.height1 + self.height2)
        self.destinationAssem.calculateZCoords()

        # This sets up a caching for the `mgNeutronVelocity` block
        # parameter on each of the blocks of the destination assembly
        # without setting the data on the blocks of the source assembly
        # to demonstrate that only new parameters set on the source assembly will be
        # mapped to the destination assembly. This ensures that parameters
        # that are not being set on the source assembly are not cleared
        # out on the destination assembly with `setAssemblyStateFromOverlaps`
        # is called.
        self._cachedBlockParamData = collections.defaultdict(dict)
        for b in self.destinationAssem:
            self._cachedBlockParamData[b]["mgNeutronVelocity"] = [1.0] * 33
            b.p["mgNeutronVelocity"] = self._cachedBlockParamData[b]["mgNeutronVelocity"]

    def test_setStateFromOverlaps(self):
        """
        Test that state is translated correctly from source to dest assems.

        Here we set flux and pdens to 3 on the source blocks.

        .. test:: Map select parameters from composites on the original mesh to the new mesh.
            :id: T_ARMI_UMC_PARAM_FORWARD
            :tests: R_ARMI_UMC_PARAM_FORWARD
        """
        paramList = ["flux", "pdens"]
        for pName in paramList:
            for b in self.sourceAssem:
                b.p[pName] = 3

        bpNames = paramList + ["mgNeutronVelocity"]
        uniformMesh.UniformMeshGeometryConverter.setAssemblyStateFromOverlaps(
            self.sourceAssem,
            self.destinationAssem,
            paramMapper=uniformMesh.ParamMapper([], bpNames, b),
        )

        for paramName in paramList:
            sourceVal1 = self.sourceAssem[0].p[paramName]
            sourceVal2 = self.sourceAssem[1].p[paramName]
            self.assertAlmostEqual(
                self.destinationAssem[0].p[paramName],
                (sourceVal1 * self.height1 + sourceVal2 * self.height2) / (self.height1 + self.height2),
            )

        for b in self.sourceAssem:
            self.assertIsNone(b.p.mgNeutronVelocity)

        for b in self.destinationAssem:
            self.assertListEqual(
                b.p.mgNeutronVelocity,
                self._cachedBlockParamData[b]["mgNeutronVelocity"],
            )


class TestUniformMeshNonUniformAssemFlags(unittest.TestCase):
    """
    Tests a reactor conversion with only a subset of assemblies being
    defined as having a non-uniform mesh.
    """

    @classmethod
    def setUpClass(cls):
        # random seed to support random mesh in unit tests below
        random.seed(987324987234)

    def setUp(self):
        self.o, self.r = loadTestReactor(
            TEST_ROOT,
            customSettings={
                CONF_XS_KERNEL: "MC2v2",
                "nonUniformAssemFlags": ["primary control"],
            },
        )
        self.r.core.lib = isotxs.readBinary(ISOAA_PATH)
        self.r.core.p.keff = 1.0
        self.converter = uniformMesh.NeutronicsUniformMeshConverter(cs=self.o.cs, calcReactionRates=True)

    def test_reactorConversion(self):
        """Tests the reactor conversion to and from the original reactor."""
        self.assertTrue(self.converter._hasNonUniformAssems)
        self.assertTrue(self.r.core.lib)
        self.assertEqual(self.r.core.p.keff, 1.0)

        controlAssems = self.r.core.getAssemblies(Flags.PRIMARY | Flags.CONTROL)
        # Add a bunch of multi-group flux to the control assemblies
        # in the core to demonstrate that data can be mapped back
        # to the original control rod assemblies if they are changed.
        # Additionally, this will check that block-level reaction rates
        # are being calculated (i.e., `rateAbs`).
        for a in controlAssems:
            for b in a:
                b.p.mgFlux = [1.0] * 33
                self.assertFalse(b.p.rateAbs)

        self.converter.convert(self.r)
        self.assertEqual(
            len(controlAssems),
            len(self.converter._nonUniformAssemStorage),
        )

        self.converter.applyStateToOriginal()
        self.assertEqual(
            len(self.converter._nonUniformAssemStorage),
            0,
        )
        for a in controlAssems:
            for b in a:
                self.assertTrue(all(b.getMgFlux()))
                self.assertTrue(b.p.rateAbs)

        self.converter.updateReactionRates()
        for a in controlAssems:
            for b in a:
                self.assertTrue(b.p.rateCap)
                self.assertTrue(b.p.rateAbs)


class TestParamMapper(unittest.TestCase):
    """Test how the ParamMapper maps params."""

    def setUp(self):
        sourceAssem, destinationAssem = test_assemblies.buildTestAssemblies()[2:]
        self.sourceBlock = sourceAssem.getBlocks()[0]
        self.destinationBlock = destinationAssem.getBlocks()[0]

        # volume integrated parameters
        self.sourceBlock.p.power = 2.0
        self.sourceBlock.p.mgFlux = np.array([2.0, 2.0, 2.0])
        self.volumeIntegratedParameterNames = ["power", "mgFlux"]
        # non-volume integrated parameters
        self.sourceBlock.p.rateFis = 2.0
        self.sourceBlock.p.linPowByPin = np.array([2.0, 2.0, 2.0])
        self.regularParameterNames = ["rateFis", "linPowByPin"]
        self.allParameterNames = self.volumeIntegratedParameterNames + self.regularParameterNames

        self.sourceBlock.getSymmetryFactor = Mock()
        self.destinationBlock.getSymmetryFactor = Mock()

    def mappingTestHelper(self, expectedRatioVolumeIntegrated):
        """
        Test helper to run block comparison when mapping parameters.

        Parameters
        ----------
        expectedRatioVolumeIntegrated : int, float
            The ratio expected for volume integrated parameters when dividing the destination value by the source value.
        """
        paramMapper = uniformMesh.ParamMapper([], self.allParameterNames, self.sourceBlock)
        sourceValues = paramMapper.paramGetter(self.sourceBlock, self.allParameterNames)
        paramMapper.paramSetter(self.destinationBlock, sourceValues, self.allParameterNames)
        for paramName in self.volumeIntegratedParameterNames:
            ratio = self.destinationBlock.p[paramName] / self.sourceBlock.p[paramName]
            np.testing.assert_equal(ratio, expectedRatioVolumeIntegrated)
        for paramName in self.regularParameterNames:
            ratio = self.destinationBlock.p[paramName] / self.sourceBlock.p[paramName]
            np.testing.assert_equal(ratio, 1)

    def test_mappingSameSymmetry(self):
        """Test mapping parameters between blocks with similar and dissimilar symmetry factors."""
        self.sourceBlock.getSymmetryFactor.return_value = 3
        self.destinationBlock.getSymmetryFactor.return_value = 3
        self.mappingTestHelper(1)

    def test_mappingDifferentSymmetry(self):
        """Test mapping parameters between blocks with similar and dissimilar symmetry factors."""
        self.sourceBlock.getSymmetryFactor.return_value = 3
        self.destinationBlock.getSymmetryFactor.return_value = 1
        self.mappingTestHelper(3)
