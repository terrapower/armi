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

# pylint: disable = invalid-name, wrong-import-position
import unittest
import os
from armi.reactor.flags import Flags
from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT
from armi.utils import densityTools
from armi.reactor.converters.tests.test_axialExpansionChanger import (
    buildTestAssemblyWithFakeMaterial,
)
from armi.reactor.converters import uniformMesh_V2_beta
from armi.reactor.converters.uniformMesh_V2_beta import UniformMeshV2


class TestMassConservation(unittest.TestCase):
    """ensure that mass is conserved"""

    def setUp(self) -> None:
        _o, self.r = test_reactors.loadTestReactor(
            os.path.join(TEST_ROOT, "detailedAxialExpansion"),
            customSettings={
                "detailedAxialExpansion": True,
                "inputHeightsConsideredHot": False,
            },
        )
        self.origCoreMass = self.r.core.getMass()
        self.origAssemblyMass = {}
        self.newAssemblyMass = {}
        self.origBlockMass = {}
        self.newBlockMass = {}

        self.uniMesher = UniformMeshV2(
            self.r.core, primaryFlag="fuel", secondaryFlag="control"
        )
        self.uniMesher.getCoreWideUniformMesh()

    def calculateAssemblyAndBlockMasses(self):
        """calculates the assembly and block masses for the origin and uniform mesh assemblies

        Notes
        -----
        - the actions contained in loop over r.core.getAssemblies() is the same as
          uniforMesh_V2::applyCoreWideUniformMesh. However, that function can't be
          used since assembly and block masses need to be calculated at intermediate steps
        - uniforMesh_V2::applyCoreWideUniformMesh is directly tested in test_CoreWideUniformMesh
        """
        for a in self.r.core.getAssemblies():
            # calculate uniform mesh for assembly
            uniAssem = self.uniMesher.updateAssemblyAxialMesh(a)
            # get spatial locator and remove original assembly from core
            loc = a.spatialLocator
            self.r.core.removeAssembly(a, discharge=False)
            # stash original assembly and block masses
            self.origAssemblyMass[a.name] = a.getMass()
            self.getOriginalBlockMass(a)
            # store new assembly and block masses
            self.newAssemblyMass[a.name] = uniAssem.getMass()
            self.newBlockMass[a.name] = []
            for b in uniAssem.getChildren():
                self.newBlockMass[a.name].append(b.getMass())
            # add uniAssem to loc in core
            self.r.core.add(uniAssem, loc)

    def getOriginalBlockMass(self, a):
        """get original block mass that corresponds to uniform mesh
        - accounts for overlap between original and uniform mesh
        """
        self.origBlockMass[a.name] = []
        zLower = 0.0
        for zUpper in self.uniMesher.uniformMesh:
            overlappingBlockInfo = a.getBlocksBetweenElevations(zLower, zUpper)
            self.origBlockMass[a.name].append(
                getPredictedUniformMeshBlockMass(overlappingBlockInfo)
            )
            zLower = zUpper

    def test_massConservation(self):
        self.calculateAssemblyAndBlockMasses()
        for (
            key
        ) in (
            self.origAssemblyMass.keys()
        ):  # pylint: disable=consider-iterating-dictionary
            # check block masses
            for i, (orig, new) in enumerate(
                zip(self.origBlockMass[key], self.newBlockMass[key])
            ):
                self.assertAlmostEqual(
                    orig,
                    new,
                    msg="Assembly key {0}; Block number {1}; Mass is not conserved.".format(
                        key, i
                    ),
                )
            # then check assembly masses
            self.assertAlmostEqual(
                self.origAssemblyMass[key],
                self.newAssemblyMass[key],
                msg="Assembly {0} mass is not conserved.".format(key),
            )

    def test_CoreWideUniformMesh(self):
        self.uniMesher.applyCoreWideUniformMesh()
        # check core mass
        self.assertAlmostEqual(
            self.origCoreMass,
            self.r.core.getMass(),
            places=5,
            msg="Core mass is not conserved.",
        )
        # check core axial mesh aligns with self.uniformMesh
        self.uniMesher.uniformMesh.insert(
            0, 0.0
        )  # insert bottom mesh point into uniformMesh
        for i, _val in enumerate(self.uniMesher.uniformMesh):
            self.assertAlmostEqual(
                self.uniMesher.uniformMesh[i],
                self.r.core.p.axialMesh[i],
                msg="The core uniform mesh doesn't align with the calculated uniform mesh.",
            )


def getPredictedUniformMeshBlockMass(overlappingBlockInfo: list):
    """calculates the mass of a hypothetical block whose contributions are determined by overlappingBlockInfo

    Parameters
    ----------
    overlappingBlockInfo: list
        output from a.getBlocksBetweenElevations(zLower, zUpper)

    Returns
    -------
    mass : float
        predicted block mass
    """
    mass = 0.0
    for _i, (b, h) in enumerate(overlappingBlockInfo):
        for c in b:
            nuclideNames = c._getNuclidesFromSpecifier(
                None
            )  # pylint: disable=protected-access
            volume = (c.getArea() * h) / (b.getSymmetryFactor())
            densities = c.getNuclideNumberDensities(nuclideNames)
            mass += sum(
                densityTools.getMassInGrams(nucName, volume, numberDensity)
                for nucName, numberDensity in zip(nuclideNames, densities)
            )
    return mass


class TestExceptions(unittest.TestCase):
    """make sure hardcoded exceptions work as expected"""

    def test_checkAxialMeshValidity_invalidMesh(self):
        failMesh = [1.0, 2.0, 3.0, 5.0, 4.0]
        with self.assertRaises(RuntimeError) as cm:
            uniformMesh_V2_beta.checkAxialMeshValidity(failMesh)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_checkAxialMeshValidity_preservationFail(self):
        """
        Notes
        ----
        - testMesh has a "mesh discrepancy" between testMesh[2] and testMesh[1]
        - If preservedMesh is None, the uniform mesh point would simply be an average of these values.
        - Since preservedMesh is not None, we have to choose which ever mesh point (either 2.0 or 2.05)
          that is in preservedMesh (the lowest gets checked first and therefore has priority).
        - Ideally, either of these options are in preservedMesh. However, to induce the RuntimeError,
          we do not include either.
        """
        testMesh = [1.0, 2.0, 2.05, 3.05, 4.05, 5.0]
        preservedMesh = [1.0, 2.01, 3.0, 4.0, 4.95, 5.0]
        with self.assertRaises(RuntimeError) as cm:
            uniformMesh_V2_beta.checkAxialMeshValidity(testMesh, preservedMesh)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)

    def test_updateAssemblyAxialMesh(self):
        a = buildTestAssemblyWithFakeMaterial(name="FakeMat")
        uniMesh = UniformMeshV2(None, "fuel", "control")
        uniMesh.uniformMesh = [1.0, 2.0, 2.0, 3.0, 3.0, 4.0, 5.0]
        with self.assertRaises(ValueError) as cm:
            uniMesh.updateAssemblyAxialMesh(a)
            the_exception = cm.exception
            self.assertEqual(the_exception.error_code, 3)
