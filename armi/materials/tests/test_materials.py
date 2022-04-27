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

r"""Tests materials.py"""
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access,no-member,invalid-name
import pickle
import unittest

from numpy import testing

from armi import materials, settings
from armi.nucDirectory import nuclideBases
from armi.reactor import blueprints
from armi.utils import units


class _Material_Test:
    """Base for all specific material test cases."""

    MAT_CLASS = None

    def setUp(self):
        self.mat = self.MAT_CLASS()

    def test_isPicklable(self):
        """Test that all materials are picklable so we can do MPI communication of state."""
        stream = pickle.dumps(self.mat)
        mat = pickle.loads(stream)

        # check a property that is sometimes interpolated.
        self.assertEqual(
            self.mat.thermalConductivity(500), mat.thermalConductivity(500)
        )


class MaterialConstructionTests(unittest.TestCase):
    def test_material_initialization(self):
        """Make sure all materials can be instantiated without error."""
        for matClass in materials.iterAllMaterialClassesInNamespace(materials):
            matClass()


class MaterialFindingTests(unittest.TestCase):
    """Make sure materials are discoverable as designed."""

    def test_findMaterial(self):
        self.assertIs(
            materials.resolveMaterialClassByName(
                "Void", namespaceOrder=["armi.materials"]
            ),
            materials.Void,
        )
        self.assertIs(
            materials.resolveMaterialClassByName(
                "Void", namespaceOrder=["armi.materials.void"]
            ),
            materials.Void,
        )
        self.assertIs(
            materials.resolveMaterialClassByName(
                "Void", namespaceOrder=["armi.materials.mox", "armi.materials.void"]
            ),
            materials.Void,
        )
        with self.assertRaises(ModuleNotFoundError):
            materials.resolveMaterialClassByName(
                "Void", namespaceOrder=["invalid.namespace", "armi.materials.void"]
            )
        with self.assertRaises(KeyError):
            materials.resolveMaterialClassByName(
                "Unobtanium", namespaceOrder=["armi.materials"]
            )


class Magnesium_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Magnesium

    def test_density(self):
        cur = self.mat.density(923)
        ref = 1.59
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.density(1390)
        ref = 1.466
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)


class MagnesiumOxide_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.MgO

    def test_density(self):
        cur = self.mat.density(923)
        ref = 3.48887
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.density(1390)
        ref = 3.418434
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_linearExpansionPercent(self):
        cur = self.mat.linearExpansionPercent(Tc=100)
        ref = 0.00110667
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.linearExpansionPercent(Tc=400)
        ref = 0.0049909
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))


class Molybdenum_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Molybdenum

    def test_density(self):
        cur = self.mat.density(333)
        ref = 10.28
        delta = ref * 0.0001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.density(1390)
        ref = 10.28
        delta = ref * 0.0001
        self.assertAlmostEqual(cur, ref, delta=delta)


class NaCl_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.NaCl

    def test_density(self):
        cur = self.mat.density(Tc=100)
        ref = 2.113204
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.density(Tc=300)
        ref = 2.050604
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))


class NiobiumZirconium_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.NZ

    def test_density(self):
        cur = self.mat.density(Tk=100)
        ref = 8.66
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.density(Tk=1390)
        ref = 8.66
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))


class Potassium_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Potassium

    def test_density(self):
        cur = self.mat.density(Tk=333)
        ref = 0.828
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.density(Tk=500)
        ref = 0.7909
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.density(Tk=750)
        ref = 0.732
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)


class ScandiumOxide_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Sc2O3

    def test_density(self):
        cur = self.mat.density(Tc=100)
        ref = 3.86
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.density(Tc=400)
        ref = 3.86
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

    def test_linearExpansionPercent(self):
        cur = self.mat.linearExpansionPercent(Tc=100)
        ref = 0.0623499
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.linearExpansionPercent(Tc=400)
        ref = 0.28322
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))


class Sodium_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Sodium

    def test_density(self):
        cur = self.mat.density(300)
        ref = 0.941
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.density(1700)
        ref = 0.597
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_specificVolumeLiquid(self):
        cur = self.mat.specificVolumeLiquid(300)
        ref = 0.001062
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.specificVolumeLiquid(1700)
        ref = 0.001674
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_enthalpy(self):
        cur = self.mat.enthalpy(300)
        ref = 107518.523
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.enthalpy(1700)
        ref = 1959147.963
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_thermalConductivity(self):
        cur = self.mat.thermalConductivity(300)
        ref = 95.1776
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.thermalConductivity(1700)
        ref = 32.616
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)


class Tantalum_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Tantalum

    def test_density(self):
        cur = self.mat.density(Tc=100)
        ref = 16.6
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.density(Tc=300)
        ref = 16.6
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))


class ThoriumOxide_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.ThU

    def test_density(self):
        cur = self.mat.density(Tc=100)
        ref = 11.68
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.density(Tc=300)
        ref = 11.68
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

    def test_meltingPoint(self):
        cur = self.mat.meltingPoint()
        ref = 2025.0
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

    def test_thermalConductivity(self):
        cur = self.mat.thermalConductivity(Tc=100)
        ref = 43.1
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.thermalConductivity(Tc=300)
        ref = 43.1
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

    def test_linearExpansion(self):
        cur = self.mat.linearExpansion(Tc=100)
        ref = 11.9e-6
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.linearExpansion(Tc=300)
        ref = 11.9e-6
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))


class Uranium_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Uranium

    def test_thermalConductivity(self):
        cur = self.mat.thermalConductivity(Tc=100)
        ref = 28.489312629207500293659904855
        self.assertAlmostEqual(cur, ref, delta=10e-10)

        cur = self.mat.thermalConductivity(Tc=300)
        ref = 32.789271449207497255429188954
        self.assertAlmostEqual(cur, ref, delta=10e-10)

        cur = self.mat.thermalConductivity(Tc=500)
        ref = 37.561790269207499193271360127
        self.assertAlmostEqual(cur, ref, delta=10e-10)

        cur = self.mat.thermalConductivity(Tc=700)
        ref = 42.806869089207502554472739575
        self.assertAlmostEqual(cur, ref, delta=10e-10)

        cur = self.mat.thermalConductivity(Tc=900)
        ref = 48.524507909207507339033327298
        self.assertAlmostEqual(cur, ref, delta=10e-10)


class UraniumOxide_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.UraniumOxide

    def test_adjustMassEnrichment(self):
        o16 = nuclideBases.byName["O"].weight
        u235 = nuclideBases.byName["U235"].weight
        u238 = nuclideBases.byName["U238"].weight
        self.mat.adjustMassEnrichment(0.02)

        gPerMol = 2 * o16 + 0.02 * u235 + 0.98 * u238
        massFracs = self.mat.p.massFrac

        testing.assert_allclose(massFracs["O"], 2 * o16 / gPerMol, rtol=5e-4)
        testing.assert_allclose(
            massFracs["U235"], 0.02 * (u235 * 0.02 + u238 * 0.98) / gPerMol, rtol=5e-4
        )
        testing.assert_allclose(
            massFracs["U238"], 0.98 * (u235 * 0.02 + u238 * 0.98) / gPerMol, rtol=5e-4
        )

        self.mat.adjustMassEnrichment(0.2)
        massFracs = self.mat.p.massFrac
        gPerMol = 2 * o16 + 0.8 * u238 + 0.2 * u235

        testing.assert_allclose(massFracs["O"], 2 * o16 / gPerMol, rtol=5e-4)
        testing.assert_allclose(
            massFracs["U235"], 0.2 * (u235 * 0.2 + u238 * 0.8) / gPerMol, rtol=5e-4
        )
        testing.assert_allclose(
            massFracs["U238"], 0.8 * (u235 * 0.2 + u238 * 0.8) / gPerMol, rtol=5e-4
        )

    def test_meltingPoint(self):
        cur = self.mat.meltingPoint()
        ref = 3123.0
        self.assertEqual(cur, ref)

    def test_density(self):
        # Reference data taken from ORNL/TM-2000/351. "Thermophysical Properties of MOX and UO2
        # Fuels Including the Effects of Irradiation.", Popov, et al.  Table 3.2 "Parameters of
        # thermal expansion of stoichiometric MOX fuel and density of UO2 as a function of
        # temperature"
        cur = self.mat.density(Tk=700)
        ref = 1.0832e4 * 0.001  # Convert to grams/cc
        delta = ref * 0.02
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.density(Tk=2600)
        ref = 9.9698e3 * 0.001  # Convert to grams/cc
        delta = ref * 0.02
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_thermalConductivity(self):
        cur = self.mat.thermalConductivity(600)
        ref = 4.864
        accuracy = 3
        self.assertAlmostEqual(cur, ref, accuracy)

        cur = self.mat.thermalConductivity(1800)
        ref = 2.294
        accuracy = 3
        self.assertAlmostEqual(cur, ref, accuracy)

        cur = self.mat.thermalConductivity(2700)
        ref = 1.847
        accuracy = 3
        self.assertAlmostEqual(cur, ref, accuracy)

    def test_linearExpansion(self):
        cur = self.mat.linearExpansion(300)
        ref = 9.93e-6
        accuracy = 2
        self.assertAlmostEqual(cur, ref, accuracy)

        cur = self.mat.linearExpansion(1500)
        ref = 1.0639e-5
        accuracy = 2
        self.assertAlmostEqual(cur, ref, accuracy)

        cur = self.mat.linearExpansion(3000)
        ref = 1.5821e-5
        accuracy = 2
        self.assertAlmostEqual(cur, ref, accuracy)

    def test_linearExpansionPercent(self):
        cur = self.mat.linearExpansionPercent(Tk=500)
        ref = 0.222826
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.linearExpansionPercent(Tk=950)
        ref = 0.677347
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

    def test_heatCapacity(self):
        """Check against Figure 4.2 from ORNL 2000-1723 EFG"""
        self.assertAlmostEqual(self.mat.heatCapacity(300), 230.0, delta=20)
        self.assertAlmostEqual(self.mat.heatCapacity(1000), 320.0, delta=20)
        self.assertAlmostEqual(self.mat.heatCapacity(2000), 380.0, delta=20)

    def test_getTemperatureAtDensity(self):
        expectedTemperature = 100.0
        tAtTargetDensity = self.mat.getTemperatureAtDensity(
            self.mat.density(Tc=expectedTemperature), 30.0
        )
        self.assertAlmostEqual(expectedTemperature, tAtTargetDensity)

    def test_getDensityExpansion3D(self):
        expectedTemperature = 100.0
        self.mat.p.refDens = 10.9
        density3D = self.mat.density3KgM3(Tc=expectedTemperature)
        self.assertAlmostEqual(10.86792660463439e3, density3D)

    def test_removeNucMassFrac(self):
        self.mat.removeNucMassFrac("O")
        massFracs = [str(k) for k in self.mat.p.massFrac.keys()]
        self.assertListEqual(["U235", "U238"], massFracs)

    def test_densityTimesHeatCapactiy(self):
        Tc = 500.0
        expectedRhoCp = self.mat.density(Tc=Tc) * 1000.0 * self.mat.heatCapacity(Tc=Tc)
        self.assertAlmostEqual(expectedRhoCp, self.mat.densityTimesHeatCapacity(Tc=Tc))

    def test_getTempChangeForDensityChange(self):
        Tc = 500.0
        linearExpansion = self.mat.linearExpansion(Tc=Tc)
        densityFrac = 1.001
        linearChange = densityFrac ** (-1.0 / 3.0) - 1.0
        expectedDeltaT = linearChange / linearExpansion
        actualDeltaT = self.mat.getTempChangeForDensityChange(
            Tc, densityFrac, quiet=False
        )
        self.assertAlmostEqual(expectedDeltaT, actualDeltaT)

    def test_duplicate(self):
        duplicateU = self.mat.duplicate()
        for key in self.mat.p:
            self.assertEqual(duplicateU.p[key], self.mat.p[key])

        for key in self.mat.p.massFrac:
            self.assertEqual(duplicateU.p.massFrac[key], self.mat.p.massFrac[key])

        duplicateMassFrac = self.mat.getMassFracCopy()
        for key in self.mat.p.massFrac.keys():
            self.assertEqual(duplicateMassFrac[key], self.mat.p.massFrac[key])


class Thorium_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Thorium

    def test_setDefaultMassFracs(self):
        self.mat.setDefaultMassFracs()
        cur = self.mat.p.massFrac
        ref = {"TH232": 1.0}
        self.assertEqual(cur, ref)

    def test_density(self):
        cur = self.mat.density(400)
        ref = 11.68
        accuracy = 4
        self.assertAlmostEqual(cur, ref, accuracy)

    def test_linearExpansion(self):
        cur = self.mat.linearExpansion(400)
        ref = 11.9e-6
        accuracy = 4
        self.assertAlmostEqual(cur, ref, accuracy)

    def test_thermalConductivity(self):
        cur = self.mat.thermalConductivity(400)
        ref = 43.1
        accuracy = 4
        self.assertAlmostEqual(cur, ref, accuracy)

    def test_meltingPoint(self):
        cur = self.mat.meltingPoint()
        ref = 2025.0
        accuracy = 4
        self.assertAlmostEqual(cur, ref, accuracy)


class ThoriumOxide_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.ThoriumOxide

    def test_density(self):
        cur = self.mat.density(400)
        ref = 10.00
        accuracy = 4
        self.assertAlmostEqual(cur, ref, accuracy)

    def test_linearExpansion(self):
        cur = self.mat.linearExpansion(400)
        ref = 9.67e-6
        accuracy = 4
        self.assertAlmostEqual(cur, ref, accuracy)

    def test_thermalConductivity(self):
        cur = self.mat.thermalConductivity(400)
        ref = 6.20
        accuracy = 4
        self.assertAlmostEqual(cur, ref, accuracy)

    def test_meltingPoint(self):
        cur = self.mat.meltingPoint()
        ref = 3643.0
        accuracy = 4
        self.assertAlmostEqual(cur, ref, accuracy)


class Void_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Void

    def test_setDefaultMassFracs(self):
        self.mat.setDefaultMassFracs()
        cur = self.mat.p.density
        ref = 0.0
        self.assertEqual(cur, ref)

    def test_linearExpansion(self):
        cur = self.mat.linearExpansion(400)
        ref = 0.0
        self.assertEqual(cur, ref)


class Lead_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Lead

    def test_volumetricExpansion(self):
        self.assertAlmostEqual(
            self.mat.volumetricExpansion(800),
            1.1472e-4,
            4,
            msg="\n\nIncorrect Lead volumetricExpansion(Tk=None,Tc=None)\nReceived:{}\nExpected:{}\n".format(
                self.mat.volumetricExpansion(800), 1.1472e-4
            ),
        )
        self.assertAlmostEqual(
            self.mat.volumetricExpansion(1200),
            1.20237e-4,
            4,
            msg="\n\nIncorrect Lead volumetricExpansion(Tk=None,Tc=None)\nReceived:{}\nExpected:{}\n".format(
                self.mat.volumetricExpansion(1200), 1.20237e-4
            ),
        )

    def test_linearExpansion(self):
        cur = self.mat.linearExpansion(400)
        ref = 0.0
        self.assertEqual(cur, ref)

    def test_setDefaultMassFracs(self):
        self.mat.setDefaultMassFracs()
        cur = self.mat.p.massFrac
        ref = {"PB": 1}
        self.assertEqual(cur, ref)

    def test_density(self):
        cur = self.mat.density(634.39)
        ref = 10.6120
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.density(1673.25)
        ref = 9.4231
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_heatCapacity(self):
        cur = self.mat.heatCapacity(1200)
        ref = 138.647
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)


class LeadBismuth_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.LeadBismuth

    def test_setDefaultMassFracs(self):
        self.mat.setDefaultMassFracs()
        cur = self.mat.p.massFrac
        ref = {"BI209": 0.555, "PB": 0.445}
        self.assertEqual(cur, ref)

    def test_density(self):
        cur = self.mat.density(404.77)
        ref = 10.5617
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.density(1274.20)
        ref = 9.3627
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_volumetricExpansion(self):
        cur = self.mat.volumetricExpansion(400)
        ref = 1.2526e-4
        accuracy = 4
        self.assertAlmostEqual(cur, ref, accuracy)

        cur = self.mat.volumetricExpansion(800)
        ref = 1.3187e-4
        accuracy = 4
        self.assertAlmostEqual(cur, ref, accuracy)

    def test_heatCapacity(self):
        cur = self.mat.heatCapacity(400)
        ref = 149.2592
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.heatCapacity(800)
        ref = 141.7968
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_getTempChangeForDensityChange(self):
        Tc = 800.0
        densityFrac = 1.001
        currentDensity = self.mat.density(Tc=Tc)
        perturbedDensity = currentDensity * densityFrac
        tAtPerturbedDensity = self.mat.getTemperatureAtDensity(perturbedDensity, Tc)
        expectedDeltaT = tAtPerturbedDensity - Tc
        actualDeltaT = self.mat.getTempChangeForDensityChange(
            Tc, densityFrac, quiet=False
        )
        self.assertAlmostEqual(expectedDeltaT, actualDeltaT)

    def test_dynamicVisc(self):
        ref = self.mat.dynamicVisc(Tc=100)
        cur = 0.0037273
        self.assertAlmostEqual(ref, cur, delta=ref * 0.001)

        ref = self.mat.dynamicVisc(Tc=200)
        cur = 0.0024316
        self.assertAlmostEqual(ref, cur, delta=ref * 0.001)


class Sulfur_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Sulfur

    def test_setDefaultMassFracs(self):
        cur = self.mat.p.massFrac
        ref = {"S34": 0.0429, "S36": 0.002, "S33": 0.0076, "S32": 0.9493}
        self.assertEqual(cur, ref)

    def test_density(self):
        cur = self.mat.density(400)
        ref = 1.7956
        accuracy = 4
        self.assertAlmostEqual(cur, ref, accuracy)

    def test_volumetricExpansion(self):
        cur = self.mat.volumetricExpansion(334)
        ref = 5.28e-4
        accuracy = 4
        self.assertAlmostEqual(cur, ref, accuracy)


class Zr_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Zr

    def test_thermalConductivity(self):
        cur = self.mat.thermalConductivity(372.7273)
        ref = 19.8718698709447
        self.assertAlmostEqual(cur, ref)

        cur = self.mat.thermalConductivity(1172.727)
        ref = 23.193177102455
        self.assertAlmostEqual(cur, ref)

    def test_linearExpansion(self):
        cur = self.mat.linearExpansion(400)
        ref = 5.9e-6
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.linearExpansion(800)
        ref = 7.9e-6
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_linearExpansionPercent(self):
        testTemperaturesInK = [
            293,
            400,
            500,
            600,
            700,
            800,
            900,
            1000,
            1100,
            1137,
            1200,
            1400,
            1600,
            1800,
        ]
        expectedLinearExpansionValues = [
            0.0007078312624,
            0.0602048,
            0.123025,
            0.1917312,
            0.2652626,
            0.3425584,
            0.4225578,
            0.5042,
            0.5864242,
            0.481608769233,
            0.5390352,
            0.7249496,
            0.9221264,
            1.1380488,
        ]
        for i, temp in enumerate(testTemperaturesInK):
            Tk = temp
            Tc = temp - units.C_TO_K
            self.assertAlmostEqual(
                self.mat.linearExpansionPercent(Tc=Tc), expectedLinearExpansionValues[i]
            )
            self.assertAlmostEqual(
                self.mat.linearExpansionPercent(Tk=Tk), expectedLinearExpansionValues[i]
            )

    def test_density(self):
        testTemperaturesInK = [
            293,
            298.15,
            400,
            500,
            600,
            700,
            800,
            900,
            1000,
            1100,
            1137,
            1200,
            1400,
            1600,
            1800,
        ]
        expectedDensityValues = [
            6.56990469455,
            6.56955491852,
            6.56209393299,
            6.55386200572,
            6.54487650252,
            6.53528040809,
            6.52521578203,
            6.51482358662,
            6.50424356114,
            6.49361414192,
            6.50716858169,
            6.49973710507,
            6.47576529821,
            6.45048593916,
            6.4229727005,
        ]
        for i, temp in enumerate(testTemperaturesInK):
            Tk = temp
            Tc = temp - units.C_TO_K
            self.assertAlmostEqual(self.mat.density(Tc=Tc), expectedDensityValues[i])
            self.assertAlmostEqual(self.mat.density(Tk=Tk), expectedDensityValues[i])


class Inconel_TestCase(_Material_Test, unittest.TestCase):
    def setUp(self):
        self.Inconel = materials.Inconel()
        self.Inconel800 = materials.Inconel800()
        self.InconelPE16 = materials.InconelPE16()
        self.mat = self.Inconel

    def tearDown(self):
        self.Inconel = None
        self.Inconel800 = None
        self.InconelPE16 = None

    def test_setDefaultMassFracs(self):
        self.Inconel.setDefaultMassFracs()
        self.Inconel800.setDefaultMassFracs()
        self.InconelPE16.setDefaultMassFracs()

        self.assertAlmostEqual(self.Inconel.getMassFrac("MO"), 0.09)
        self.assertAlmostEqual(self.Inconel800.getMassFrac("AL"), 0.00375)
        self.assertAlmostEqual(self.InconelPE16.getMassFrac("CR"), 0.165)

    def test_density(self):
        self.assertEqual(self.Inconel.density(), 8.3600)
        self.assertEqual(self.Inconel800.density(Tc=21.0), 7.94)
        self.assertEqual(self.InconelPE16.density(), 8.00)

    def test_Iconel800_linearExpansion(self):
        TcList = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            0.11469329415,
            0.27968864560,
            0.454195022850,
            0.63037690440,
            0.80645936875,
            0.98672809440,
            1.18152935985,
            1.4072700436,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.Inconel800.linearExpansionPercent(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Inconel 800 linearExpansionPercent()\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)


class Inconel600_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Inconel600

    def test_00_setDefaultMassFracs(self):
        massFracNameList = ["NI", "CR", "FE", "C", "MN55", "S", "SI", "CU"]
        massFracRefValList = [
            0.7541,
            0.1550,
            0.0800,
            0.0008,
            0.0050,
            0.0001,
            0.0025,
            0.0025,
        ]

        for name, frac in zip(massFracNameList, massFracRefValList):
            cur = self.mat.getMassFrac(name)
            ref = frac
            self.assertAlmostEqual(cur, ref)

    def test_01_linearExpansionPercent(self):
        TcList = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            0.105392,
            0.24685800000000002,
            0.39576799999999995,
            0.552122,
            0.7159199999999999,
            0.8871619999999999,
            1.065848,
            1.251978,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.linearExpansionPercent(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Inconel 600 linearExpansionPercent(Tk=None,Tc=None)\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)

    def test_02_linearExpansion(self):
        TcList = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            1.3774400000000001e-05,
            1.45188e-05,
            1.52632e-05,
            1.60076e-05,
            1.6752e-05,
            1.74964e-05,
            1.82408e-05,
            1.8985200000000002e-05,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.linearExpansion(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Inconel 600 linearExpansion(Tk=None,Tc=None)\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)

    def test_03_density(self):
        TcList = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            8.452174779681522,
            8.428336592376965,
            8.40335281361706,
            8.377239465159116,
            8.35001319823814,
            8.321691270531865,
            8.292291522488402,
            8.261832353071625,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.density(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Inconel 600 density(Tk=None,Tc=None)\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)

    def test_polyfitThermalConductivity(self):
        ref = self.mat.polyfitThermalConductivity(power=2)
        cur = [3.49384e-06, 0.01340, 14.57241]

        self.assertEqual(len(ref), len(cur))
        for i, curVal in enumerate(cur):
            self.assertAlmostEqual(ref[i], curVal, delta=curVal * 0.001)

    def test_polyfitHeatCapacity(self):
        ref = self.mat.polyfitHeatCapacity(power=2)
        cur = [7.40206e-06, 0.20573, 441.29945]

        self.assertEqual(len(ref), len(cur))
        for i, curVal in enumerate(cur):
            self.assertAlmostEqual(ref[i], curVal, delta=curVal * 0.001)

    def test_polyfitLinearExpansionPercent(self):
        ref = self.mat.polyfitLinearExpansionPercent(power=2)
        cur = [3.72221e-07, 0.00130308, -0.0286255941973353]

        self.assertEqual(len(ref), len(cur))
        for i, curVal in enumerate(cur):
            self.assertAlmostEqual(ref[i], curVal, delta=abs(curVal * 0.001))

    def test_heatCapacity(self):
        ref = self.mat.heatCapacity(Tc=100)
        cur = 461.947021
        self.assertAlmostEqual(ref, cur, delta=cur * 0.001)

        ref = self.mat.heatCapacity(Tc=200)
        cur = 482.742084
        self.assertAlmostEqual(ref, cur, delta=cur * 0.001)


class Inconel625_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Inconel625

    def test_00_setDefaultMassFracs(self):
        massFracNameList = [
            "NI",
            "CR",
            "FE",
            "MO",
            "TA181",
            "C",
            "MN55",
            "SI",
            "P31",
            "S",
            "AL27",
            "TI",
            "CO59",
        ]
        massFracRefValList = [
            0.6188,
            0.2150,
            0.0250,
            0.0900,
            0.0365,
            0.0005,
            0.0025,
            0.0025,
            0.0001,
            0.0001,
            0.0020,
            0.0020,
            0.0050,
        ]

        for name, frac in zip(massFracNameList, massFracRefValList):
            cur = self.mat.getMassFrac(name)
            ref = frac
            self.assertAlmostEqual(cur, ref)

    def test_01_linearExpansionPercent(self):
        TcList = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            0.09954299999999999,
            0.22729199999999997,
            0.36520699999999995,
            0.513288,
            0.671535,
            0.8399479999999999,
            1.018527,
            1.207272,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.linearExpansionPercent(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Inconel 625 linearExpansionPercent(Tk=None,Tc=None)\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)

    def test_02_linearExpansion(self):
        TcList = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            1.22666e-05,
            1.32832e-05,
            1.4299800000000002e-05,
            1.53164e-05,
            1.6333e-05,
            1.73496e-05,
            1.83662e-05,
            1.93828e-05,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.linearExpansion(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Inconel 625 linearExpansion(Tk=None,Tc=None)\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)

    def test_03_density(self):
        TcList = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            8.423222197446128,
            8.401763522409897,
            8.378689129846913,
            8.354019541533887,
            8.327776582263244,
            8.299983337593213,
            8.270664109510587,
            8.239844370152333,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.density(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Inconel 625 density(Tk=None,Tc=None)\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)

    def test_polyfitThermalConductivity(self):
        ref = self.mat.polyfitThermalConductivity(power=2)
        cur = [2.7474128e-06, 0.01290669, 9.6253227]

        self.assertEqual(len(ref), len(cur))
        for i, curVal in enumerate(cur):
            self.assertAlmostEqual(ref[i], curVal, delta=abs(curVal * 0.001))

    def test_polyfitHeatCapacity(self):
        ref = self.mat.polyfitHeatCapacity(power=2)
        cur = [-5.377736582e-06, 0.250006, 404.26111]

        self.assertEqual(len(ref), len(cur))
        for i, curVal in enumerate(cur):
            self.assertAlmostEqual(ref[i], curVal, delta=abs(curVal * 0.001))

    def test_polyfitLinearExpansionPercent(self):
        ref = self.mat.polyfitLinearExpansionPercent(power=2)
        cur = [5.08303200671101e-07, 0.001125487, -0.0180449]

        self.assertEqual(len(ref), len(cur))
        for i, curVal in enumerate(cur):
            self.assertAlmostEqual(ref[i], curVal, delta=abs(curVal * 0.001))

    def test_heatCapacity(self):
        ref = self.mat.heatCapacity(Tc=100)
        cur = 429.206223
        self.assertAlmostEqual(ref, cur, delta=cur * 0.001)

        ref = self.mat.heatCapacity(Tc=200)
        cur = 454.044892
        self.assertAlmostEqual(ref, cur, delta=cur * 0.001)


class InconelX750_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.InconelX750

    def test_00_setDefaultMassFracs(self):
        massFracNameList = [
            "NI",
            "CR",
            "FE",
            "TI",
            "AL27",
            "NB93",
            "MN55",
            "SI",
            "S",
            "CU",
            "C",
            "CO59",
        ]
        massFracRefValList = [
            0.7180,
            0.1550,
            0.0700,
            0.0250,
            0.0070,
            0.0095,
            0.0050,
            0.0025,
            0.0001,
            0.0025,
            0.0004,
            0.0050,
        ]

        for name, frac in zip(massFracNameList, massFracRefValList):
            cur = self.mat.getMassFrac(name)
            ref = frac
            self.assertAlmostEqual(cur, ref)

    def test_01_linearExpansionPercent(self):
        TcList = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            0.09927680000000001,
            0.2253902,
            0.36517920000000004,
            0.5186438000000001,
            0.6857840000000001,
            0.8665998000000001,
            1.0610912000000001,
            1.2692582000000001,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.linearExpansionPercent(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Inconel X750 linearExpansionPercent(Tk=None,Tc=None)\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)

    def test_02_linearExpansion(self):
        TcList = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            1.1927560000000001e-05,
            1.329512e-05,
            1.466268e-05,
            1.603024e-05,
            1.73978e-05,
            1.876536e-05,
            2.013292e-05,
            2.150048e-05,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.linearExpansion(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Inconel X750 linearExpansion(Tk=None,Tc=None)\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)

    def test_03_density(self):
        TcList = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            8.263584211566972,
            8.242801193765645,
            8.219855974833411,
            8.194776170511199,
            8.167591802868142,
            8.138335221416156,
            8.107041018806447,
            8.073745941486463,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.density(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Inconel X750 density(Tk=None,Tc=None)\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)

    def test_polyfitThermalConductivity(self):
        ref = self.mat.polyfitThermalConductivity(power=2)
        cur = [1.48352396e-06, 0.012668, 11.631576]

        self.assertEqual(len(ref), len(cur))
        for i, curVal in enumerate(cur):
            self.assertAlmostEqual(ref[i], curVal, delta=abs(curVal * 0.001))

    def test_polyfitHeatCapacity(self):
        ref = self.mat.polyfitHeatCapacity(power=2)
        cur = [0.000269809, 0.05272799, 446.51227]

        self.assertEqual(len(ref), len(cur))
        for i, curVal in enumerate(cur):
            self.assertAlmostEqual(ref[i], curVal, delta=abs(curVal * 0.001))

    def test_polyfitLinearExpansionPercent(self):
        ref = self.mat.polyfitLinearExpansionPercent(power=2)
        cur = [6.8377787e-07, 0.0010559998, -0.013161]

        self.assertEqual(len(ref), len(cur))
        for i, curVal in enumerate(cur):
            self.assertAlmostEqual(ref[i], curVal, delta=abs(curVal * 0.001))

    def test_heatCapacity(self):
        ref = self.mat.heatCapacity(Tc=100)
        cur = 459.61381
        self.assertAlmostEqual(ref, cur, delta=cur * 0.001)

        ref = self.mat.heatCapacity(Tc=200)
        cur = 484.93968
        self.assertAlmostEqual(ref, cur, delta=cur * 0.001)


class Alloy200_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Alloy200

    def test_nickleContent(self):
        """Assert alloy 200 has more than 99% nickle per its spec"""
        self.assertGreater(self.mat.p.massFrac["NI"], 0.99)


class CaH2_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.CaH2

    def test_density(self):
        cur = 1.7

        ref = self.mat.density(Tc=100)
        self.assertAlmostEqual(cur, ref, ref * 0.01)

        ref = self.mat.density(Tc=300)
        self.assertAlmostEqual(cur, ref, ref * 0.01)


class Hafnium_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Hafnium

    def test_density(self):
        cur = 13.07

        ref = self.mat.density(Tc=100)
        self.assertAlmostEqual(cur, ref, ref * 0.01)

        ref = self.mat.density(Tc=300)
        self.assertAlmostEqual(cur, ref, ref * 0.01)


class HastelloyN_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.HastelloyN

    def test_thermalConductivity(self):
        TcList = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            12.280014,
            13.171442,
            14.448584,
            16.11144,
            18.16001,
            20.594294,
            23.414292,
            26.620004,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.thermalConductivity(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Hastelloy N thermalConductivity()\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)

    def test_heatCapacity(self):
        TcList = [100, 200, 300, 400, 500, 600, 700]
        refList = [
            419.183138,
            438.728472,
            459.630622,
            464.218088,
            480.092250,
            556.547128,
            573.450902,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.heatCapacity(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Hastelloy N heatCapacity()\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)

    def test_linearExpansionPercent(self):
        TcList = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            0.0976529128,
            0.2225103228,
            0.351926722,
            0.4874638024,
            0.630683256,
            0.7831467748,
            0.9464160508,
            1.122052776,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.linearExpansionPercent(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Hastelloy N linearExpansionPercent()\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)

    def test_meanCoefficientThermalExpansion(self):
        TcList = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            1.22066141e-05,
            1.23616846e-05,
            1.25688115e-05,
            1.28279948e-05,
            1.31392345e-05,
            1.35025306e-05,
            1.39178831e-05,
            1.4385292e-05,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.meanCoefficientThermalExpansion(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect Hastelloy N meanCoefficientThermalExpansion()\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=errorMsg)


class TZM_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.TZM

    def test_00_applyInputParams(self):
        massFracNameList = ["C", "TI", "ZR", "MO"]
        massFracRefValList = [2.50749e-05, 0.002502504, 0.000761199, 0.996711222]

        self.mat.applyInputParams()

        for name, frac in zip(massFracNameList, massFracRefValList):
            cur = self.mat.p.massFrac[name]
            ref = frac
            self.assertEqual(cur, ref)

    def test_01_density(self):
        ref = 10.16  # g/cc
        cur = self.mat.density()
        self.assertEqual(cur, ref)

    def test_02_linearExpansionPercent(self):
        TcList = [
            21.11,
            456.11,
            574.44,
            702.22,
            840.56,
            846.11,
            948.89,
            1023.89,
            1146.11,
            1287.78,
            1382.22,
        ]
        refList = [
            0.0,
            1.60e-01,
            2.03e-01,
            2.53e-01,
            3.03e-01,
            3.03e-01,
            3.42e-01,
            3.66e-01,
            4.21e-01,
            4.68e-01,
            5.04e-01,
        ]

        for Tc, val in zip(TcList, refList):
            cur = self.mat.linearExpansionPercent(Tc=Tc)
            ref = val
            errorMsg = "\n\nIncorrect TZM linearExpansionPercent(Tk=None,Tc=None)\nReceived:{}\nExpected:{}\n".format(
                cur, ref
            )
            self.assertAlmostEqual(cur, ref, delta=10e-3, msg=errorMsg)


class YttriumOxide_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.Y2O3

    def test_density(self):
        cur = 5.03

        ref = self.mat.density(Tc=100)
        self.assertAlmostEqual(cur, ref, ref * 0.01)

        ref = self.mat.density(Tc=300)
        self.assertAlmostEqual(cur, ref, ref * 0.01)

    def test_linearExpansionPercent(self):
        ref = self.mat.linearExpansionPercent(Tc=100)
        cur = 0.069662
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))

        ref = self.mat.linearExpansionPercent(Tc=100)
        cur = 0.0696622
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))


class ZincOxide_TestCase(_Material_Test, unittest.TestCase):
    MAT_CLASS = materials.ZnO

    def test_density(self):
        cur = 5.61

        ref = self.mat.density(Tc=100)
        self.assertAlmostEqual(cur, ref, ref * 0.01)

        ref = self.mat.density(Tc=300)
        self.assertAlmostEqual(cur, ref, ref * 0.01)

    def test_linearExpansionPercent(self):
        ref = self.mat.linearExpansionPercent(Tc=100)
        cur = -99670.4933
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))

        ref = self.mat.linearExpansionPercent(Tc=100)
        cur = -99670.4933
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))


class FuelMaterial_TestCase(unittest.TestCase):
    baseInput = r"""
nuclide flags:
    U: {burn: false, xs: true}
    ZR: {burn: false, xs: true}
custom isotopics:
    customIsotopic1:
        input format: mass fractions
        density: 1
        U: 1
    customIsotopic2:
        input format: mass fractions
        density: 1
        ZR: 1
blocks:
    fuel: &block_fuel
        fuel1: &component_fuel_fuel1
            shape: Hexagon
            material: UZr
            Tinput: 600.0
            Thot: 600.0
            ip: 0.0
            mult: 1
            op: 10.0
        fuel2: &component_fuel_fuel2
            shape: Hexagon
            material: UZr
            Tinput: 600.0
            Thot: 600.0
            ip: 0.0
            mult: 1
            op: 10.0
assemblies:
    fuel a: &assembly_a
        specifier: IC
        blocks: [*block_fuel]
        height: [1.0]
        axial mesh points: [1]
        xs types: [A]
"""

    def loadAssembly(self, materialModifications):
        yamlString = self.baseInput + "\n" + materialModifications
        design = blueprints.Blueprints.load(yamlString)
        design._prepConstruction(settings.getMasterCs())
        return design.assemblies["fuel a"]

    def test_class1Class2_class1_wt_frac(self):
        # should error because class1_wt_frac not in (0,1)
        with self.assertRaises(ValueError):
            a = self.loadAssembly(
                """
        material modifications:
            class1_wt_frac: [2.0]
            class1_custom_isotopics: [customIsotopic1]
            class2_custom_isotopics: [customIsotopic2]
        """
            )

    def test_class1Class2_classX_custom_isotopics(self):
        # should error because class1_custom_isotopics doesn't exist
        with self.assertRaises(KeyError):
            a = self.loadAssembly(
                """
        material modifications:
            class1_wt_frac: [0.5]
            class1_custom_isotopics: [fakeIsotopic]
            class2_custom_isotopics: [customIsotopic2]
        """
            )

        # should error because class2_custom_isotopics doesn't exist
        with self.assertRaises(KeyError):
            a = self.loadAssembly(
                """
        material modifications:
            class1_wt_frac: [0.5]
            class1_custom_isotopics: [customIsotopic1]
            class2_custom_isotopics: [fakeIsotopic]
        """
            )


if __name__ == "__main__":
    unittest.main()
