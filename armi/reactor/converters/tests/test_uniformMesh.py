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
Tests for the uniform mesh geometry converter
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import collections
import os
import random
import unittest

from armi.nuclearDataIO.cccc import isotxs
from armi.reactor.converters import uniformMesh
from armi.reactor.flags import Flags
from armi.reactor.tests import test_assemblies
from armi.reactor.tests.test_reactors import loadTestReactor, reduceTestReactorRings
from armi.tests import TEST_ROOT, ISOAA_PATH


class DummyFluxOptions:
    def __init__(self):
        self.photons = False


class TestConverterFactory(unittest.TestCase):
    def setUp(self):
        self.o, self.r = loadTestReactor(
            inputFilePath=os.path.join(TEST_ROOT, "detailedAxialExpansion")
        )
        reduceTestReactorRings(self.r, self.o.cs, 2)

        self.dummyOptions = DummyFluxOptions()

    def test_converterFactory(self):
        self.dummyOptions.photons = False
        neutronConverter = uniformMesh.converterFactory(self.dummyOptions)
        self.assertTrue(neutronConverter, uniformMesh.NeutronicsUniformMeshConverter)

        self.dummyOptions.photons = True
        gammaConverter = uniformMesh.converterFactory(self.dummyOptions)
        self.assertTrue(gammaConverter, uniformMesh.GammaUniformMeshConverter)


class TestAssemblyUniformMesh(unittest.TestCase):
    """
    Tests individual operations of the uniform mesh converter

    Uses the test reactor for detailedAxialExpansion
    """

    def setUp(self):
        self.o, self.r = loadTestReactor(
            inputFilePath=os.path.join(TEST_ROOT, "detailedAxialExpansion")
        )
        reduceTestReactorRings(self.r, self.o.cs, 2)

        self.converter = uniformMesh.NeutronicsUniformMeshConverter(cs=self.o.cs)
        self.converter._sourceReactor = self.r

    def test_makeAssemWithUniformMesh(self):

        sourceAssem = self.r.core.getFirstAssembly(Flags.IGNITER)

        self.converter._computeAverageAxialMesh()
        newAssem = self.converter.makeAssemWithUniformMesh(
            sourceAssem,
            self.converter._uniformMesh,
            blockParamNames=["power"],
            mapNumberDensities=True,
        )

        prevB = None
        for newB, sourceB in zip(newAssem.getBlocks(), sourceAssem.getBlocks()):
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
                    f"The source block {sourceB} is fuel but uniform mesh converter"
                    f"created a nonfuel block {newB}."
                )
            prevB = newB

        newAssemNumberDens = newAssem.getNumberDensities()
        for nuc, val in sourceAssem.getNumberDensities().items():
            self.assertAlmostEqual(val, newAssemNumberDens[nuc])

        for nuc, val in sourceAssem.getNumberDensities().items():
            if not val:
                continue
            self.assertAlmostEqual(
                newAssem.getNumberOfAtoms(nuc) / sourceAssem.getNumberOfAtoms(nuc), 1.0
            )

    def test_makeAssemWithUniformMeshSubmesh(self):
        """If sourceAssem has submesh, check that newAssem splits into separate blocks"""

        # assign axMesh to blocks randomly
        sourceAssem = self.r.core.refAssem
        for i, b in enumerate(sourceAssem):
            b.p.axMesh = i % 2 + 1

        self.r.core.updateAxialMesh()
        newAssem = self.converter.makeAssemWithUniformMesh(
            sourceAssem, self.r.core.p.axialMesh[1:], blockParamNames=["power"]
        )

        self.assertNotEqual(len(newAssem), len(sourceAssem))
        newHeights = [b.getHeight() for b in newAssem]
        sourceHeights = [
            b.getHeight() / b.p.axMesh for b in sourceAssem for i in range(b.p.axMesh)
        ]
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
        newAssem = self.converter.makeAssemWithUniformMesh(
            sourceAssem,
            sourceAssem.getAxialMesh(),
            blockParamNames=["flux", "power", "mgFlux"],
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
        uniformMesh.UniformMeshGeometryConverter.setAssemblyStateFromOverlaps(
            sourceAssembly=newAssem,
            destinationAssembly=sourceAssem,
            blockParamNames=["flux", "power", "mgFlux"],
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
        cachedBlockParams = (
            uniformMesh.UniformMeshGeometryConverter.clearStateOnAssemblies(
                [sourceAssem],
                blockParamNames=["flux", "power", "mgFlux"],
                cache=True,
            )
        )
        for b in sourceAssem:
            self.assertEqual(b.p.flux, b.p.pDefs["flux"].default)
            self.assertEqual(b.p.power, b.p.pDefs["flux"].default)
            self.assertEqual(b.p.mgFlux, b.p.pDefs["mgFlux"].default)

            self.assertEqual(cachedBlockParams[b]["flux"], 1.0)
            self.assertEqual(cachedBlockParams[b]["power"], 10.0)
            self.assertListEqual(list(cachedBlockParams[b]["mgFlux"]), [1.0, 2.0])


class TestUniformMeshComponents(unittest.TestCase):
    """
    Tests individual operations of the uniform mesh converter

    Only loads reactor once per suite.
    """

    @classmethod
    def setUpClass(cls):
        cls.o, cls.r = loadTestReactor(TEST_ROOT, customSettings={"xsKernel": "MC2v2"})
        reduceTestReactorRings(cls.r, cls.o.cs, 4)
        cls.r.core.lib = isotxs.readBinary(ISOAA_PATH)

        # make the mesh a little non-uniform
        a = cls.r.core[4]
        a[2].setHeight(a[2].getHeight() * 1.05)

    def setUp(self):
        self.converter = uniformMesh.NeutronicsUniformMeshConverter(cs=self.o.cs)
        self.converter._sourceReactor = self.r

    def test_computeAverageAxialMesh(self):
        refMesh = self.r.core.findAllAxialMeshPoints(
            [self.r.core.getFirstAssembly(Flags.FUEL)]
        )[1:]
        self.converter._computeAverageAxialMesh()
        avgMesh = self.converter._uniformMesh

        self.assertEqual(len(refMesh), len(avgMesh))
        self.assertEqual(refMesh[0], avgMesh[0])
        self.assertNotEqual(refMesh[4], avgMesh[4], "Not equal above the fuel.")

    def test_blueprintCopy(self):
        """Ensure that necessary blueprint attributes are set"""
        convReactor = self.converter.initNewReactor(
            self.converter._sourceReactor, self.o.cs
        )
        converted = convReactor.blueprints
        original = self.converter._sourceReactor.blueprints
        toCompare = [
            "activeNuclides",
            "allNuclidesInProblem",
            "elementsToExpand",
            "inertNuclides",
        ]  # note, items within toCompare must be list or "list-like", like an ordered set
        for attr in toCompare:
            for c, o in zip(getattr(converted, attr), getattr(original, attr)):
                self.assertEqual(c, o)
        # ensure that the assemblies were copied over
        self.assertTrue(converted.assemblies, msg="Assembly objects not copied!")


def applyNonUniformHeightDistribution(reactor):
    """Modifies some assemblies to have non-uniform axial meshes"""
    for a in reactor.core:
        delta = 0.0
        for b in a[:-1]:
            origHeight = b.getHeight()
            newHeight = origHeight * (1 + 0.03 * random.uniform(-1, 1))
            b.setHeight(newHeight)
            delta += newHeight - origHeight
        a[-1].setHeight(a[-1].getHeight() - delta)
        a.calculateZCoords()


class TestUniformMesh(unittest.TestCase):
    """
    Tests full uniform mesh converter

    Loads reactor once per test
    """

    @classmethod
    def setUpClass(cls):
        # random seed to support random mesh in unit tests below
        random.seed(987324987234)

    def setUp(self):
        self.o, self.r = loadTestReactor(
            TEST_ROOT, customSettings={"xsKernel": "MC2v2"}
        )
        reduceTestReactorRings(self.r, self.o.cs, 3)
        self.r.core.lib = isotxs.readBinary(ISOAA_PATH)
        self.r.core.p.keff = 1.0

        self.converter = uniformMesh.NeutronicsUniformMeshConverter(
            cs=self.o.cs, calcReactionRates=True
        )

    def test_convertNumberDensities(self):
        refMass = self.r.core.getMass("U235")
        applyNonUniformHeightDistribution(
            self.r
        )  # this changes the mass of everything in the core
        perturbedCoreMass = self.r.core.getMass("U235")
        self.assertNotEqual(refMass, perturbedCoreMass)
        self.converter.convert(self.r)

        uniformReactor = self.converter.convReactor
        uniformMass = uniformReactor.core.getMass("U235")

        self.assertAlmostEqual(
            perturbedCoreMass, uniformMass
        )  # conversion conserved mass
        self.assertAlmostEqual(
            self.r.core.getMass("U235"), perturbedCoreMass
        )  # conversion didn't change source reactor mass

    def test_applyStateToOriginal(self):
        applyNonUniformHeightDistribution(self.r)  # note: this perturbs the ref. mass

        self.converter.convert(self.r)
        for b in self.converter.convReactor.core.getBlocks():
            b.p.mgFlux = range(33)
            b.p.adjMgFlux = range(33)
            b.p.fastFlux = 2.0
            b.p.flux = 5.0
            b.p.power = 5.0
            b.p.pdens = 0.5

        # check integral and density params
        assemblyPowers = [
            a.calcTotalParam("power") for a in self.converter.convReactor.core
        ]
        totalPower = self.converter.convReactor.core.calcTotalParam(
            "power", generationNum=2
        )
        totalPower2 = self.converter.convReactor.core.calcTotalParam(
            "pdens", volumeIntegrated=True, generationNum=2
        )

        self.converter.applyStateToOriginal()

        for b in self.r.core.getBlocks():
            self.assertAlmostEqual(b.p.fastFlux, 2.0)
            self.assertAlmostEqual(b.p.flux, 5.0)
            self.assertAlmostEqual(b.p.pdens, 0.5)

        for expectedPower, a in zip(assemblyPowers, self.r.core):
            self.assertAlmostEqual(a.calcTotalParam("power"), expectedPower)

        self.assertAlmostEqual(
            self.r.core.calcTotalParam("pdens", volumeIntegrated=True, generationNum=2),
            totalPower2,
        )
        self.assertAlmostEqual(
            self.r.core.calcTotalParam("power", generationNum=2), totalPower
        )


class TestGammaUniformMesh(unittest.TestCase):
    """
    Tests gamma uniform mesh converter

    Loads reactor once per test
    """

    @classmethod
    def setUpClass(cls):
        # random seed to support random mesh in unit tests below
        random.seed(987324987234)

    def setUp(self):
        self.o, self.r = loadTestReactor(
            TEST_ROOT, customSettings={"xsKernel": "MC2v2"}
        )
        self.r.core.lib = isotxs.readBinary(ISOAA_PATH)
        self.r.core.p.keff = 1.0
        self.converter = uniformMesh.GammaUniformMeshConverter(
            cs=self.o.cs, calcReactionRates=False
        )

    def test_convertNumberDensities(self):
        refMass = self.r.core.getMass("U235")
        applyNonUniformHeightDistribution(
            self.r
        )  # this changes the mass of everything in the core
        perturbedCoreMass = self.r.core.getMass("U235")
        self.assertNotEqual(refMass, perturbedCoreMass)
        self.converter.convert(self.r)

        uniformReactor = self.converter.convReactor
        uniformMass = uniformReactor.core.getMass("U235")

        self.assertAlmostEqual(
            perturbedCoreMass, uniformMass
        )  # conversion conserved mass
        self.assertAlmostEqual(
            self.r.core.getMass("U235"), perturbedCoreMass
        )  # conversion didn't change source reactor mass

    def test_applyStateToOriginal(self):
        applyNonUniformHeightDistribution(self.r)  # note: this perturbs the ref. mass

        # set original parameters on pre-mapped core with non-uniform assemblies
        for b in self.r.core.getBlocks():
            b.p.mgFlux = range(33)
            b.p.adjMgFlux = range(33)
            b.p.fastFlux = 2.0
            b.p.flux = 5.0
            b.p.power = 5.0

        # set original parameters on pre-mapped core with non-uniform assemblies
        self.converter.convert(self.r)
        for b in self.converter.convReactor.core.getBlocks():
            b.p.powerGamma = 0.5
            b.p.powerNeutron = 0.5

        # check integral and density params
        assemblyPowers = [
            a.calcTotalParam("power") for a in self.converter.convReactor.core
        ]
        assemblyGammaPowers = [
            a.calcTotalParam("powerGamma") for a in self.converter.convReactor.core
        ]
        totalPower = self.converter.convReactor.core.calcTotalParam(
            "power", generationNum=2
        )
        totalPowerGamma = self.converter.convReactor.core.calcTotalParam(
            "powerGamma", generationNum=2
        )

        self.converter.applyStateToOriginal()

        for b in self.r.core.getBlocks():
            # equal to original value because these were never mapped
            self.assertEqual(b.p.fastFlux, 2.0)
            self.assertEqual(b.p.flux, 5.0)
            self.assertEqual(b.p.fastFlux, 2.0)
            self.assertEqual(b.p.power, 5.0)

            # not equal because blocks are different size
            self.assertNotEqual(b.p.powerGamma, 0.5)
            self.assertNotEqual(b.p.powerNeutron, 0.5)

        # equal because these are mapped
        for expectedPower, expectedGammaPower, a in zip(
            assemblyPowers, assemblyGammaPowers, self.r.core
        ):
            self.assertAlmostEqual(a.calcTotalParam("power"), expectedPower)
            self.assertAlmostEqual(a.calcTotalParam("powerGamma"), expectedGammaPower)

        self.assertAlmostEqual(
            self.r.core.calcTotalParam("powerGamma", generationNum=2), totalPowerGamma
        )
        self.assertAlmostEqual(
            self.r.core.calcTotalParam("power", generationNum=2), totalPower
        )


class TestParamConversion(unittest.TestCase):
    def setUp(self):
        """
        Build two assemblies.

        The source assembly has two blocks, heights 3 and 7 cm. The destination
        has one big block that's 10 cm. Flux is set to 5 and 10 respectively on
        the two source blocks. They are populated with arbitrary flux and pdens
        values.
        """
        self.sourceAssem, self.destinationAssem = test_assemblies.buildTestAssemblies()[
            2:
        ]
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
            b.p["mgNeutronVelocity"] = self._cachedBlockParamData[b][
                "mgNeutronVelocity"
            ]

    def test_setStateFromOverlaps(self):
        """
        Test that state is translated correctly from source to dest assems.

        Here we set flux and pdens to 3 on the source blocks.
        """
        paramList = ["flux", "pdens"]
        for pName in paramList:
            for b in self.sourceAssem:
                b.p[pName] = 3

        uniformMesh.UniformMeshGeometryConverter.setAssemblyStateFromOverlaps(
            self.sourceAssem,
            self.destinationAssem,
            blockParamNames=paramList + ["mgNeutronVelocity"],
        )

        for paramName in paramList:
            sourceVal1 = self.sourceAssem[0].p[paramName]
            sourceVal2 = self.sourceAssem[1].p[paramName]
            self.assertAlmostEqual(
                self.destinationAssem[0].p[paramName],
                (sourceVal1 * self.height1 + sourceVal2 * self.height2)
                / (self.height1 + self.height2),
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
                "xsKernel": "MC2v2",
                "nonUniformAssemFlags": ["primary control"],
            },
        )
        self.r.core.lib = isotxs.readBinary(ISOAA_PATH)
        self.r.core.p.keff = 1.0
        self.converter = uniformMesh.NeutronicsUniformMeshConverter(
            cs=self.o.cs, calcReactionRates=True
        )

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


if __name__ == "__main__":
    unittest.main()
