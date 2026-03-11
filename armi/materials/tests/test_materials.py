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
"""Tests materials.py."""

import math
import pickle
import unittest
from copy import deepcopy

from numpy import testing

from armi import context, materials, settings
from armi.materials import _MATERIAL_NAMESPACE_ORDER, setMaterialNamespaceOrder
from armi.reactor import blueprints
from armi.utils import units


class AbstractMaterialTest:
    """Base for material tests."""

    MAT_CLASS = None
    VALID_TEMP_K = 500

    def setUp(self):
        self.mat = self.MAT_CLASS()

    def test_isPicklable(self):
        """Test that all materials are picklable so we can do MPI communication of state."""
        stream = pickle.dumps(self.mat)
        mat = pickle.loads(stream)

        # check a property that is sometimes interpolated.
        self.assertEqual(self.mat.density(self.VALID_TEMP_K), mat.density(self.VALID_TEMP_K))

    def test_density(self):
        """Test that all materials produce a non-zero density."""
        self.assertNotEqual(self.mat.density(self.VALID_TEMP_K), 0)

    def test_TD(self):
        """Test the material density."""
        self.assertEqual(self.mat.getTD(), self.mat.theoreticalDensityFrac)

        self.mat.clearCache()
        self.mat._setCache("dummy", 666)
        self.assertEqual(self.mat.cached, {"dummy": 666})
        self.mat.adjustTD(0.5)
        self.assertEqual(0.5, self.mat.theoreticalDensityFrac)
        self.assertEqual(self.mat.cached, {})

    def test_duplicate(self):
        """Test the material duplication."""
        mat = self.mat.duplicate()

        self.assertEqual(len(mat.massFrac), len(self.mat.massFrac))
        for key in self.mat.massFrac:
            self.assertEqual(mat.massFrac[key], self.mat.massFrac[key])

        self.assertEqual(mat.parent, self.mat.parent)
        self.assertEqual(mat.refDens, self.mat.refDens)
        self.assertEqual(mat.theoreticalDensityFrac, self.mat.theoreticalDensityFrac)

    def test_cache(self):
        """Test the material cache."""
        self.mat.clearCache()
        self.assertEqual(len(self.mat.cached), 0)

        self.mat._setCache("Emmy", "Noether")
        self.assertEqual(len(self.mat.cached), 1)

        val = self.mat._getCached("Emmy")
        self.assertEqual(val, "Noether")


class MaterialConstructionTests(unittest.TestCase):
    def test_material_initialization(self):
        """Make sure all materials can be instantiated without error."""
        for matClass in materials.iterAllMaterialClassesInNamespace(materials):
            matClass()


class MaterialFindingTests(unittest.TestCase):
    """Make sure materials are discoverable as designed."""

    def test_findMaterial(self):
        """Test resolveMaterialClassByName() function.

        .. test:: Materials can be grabbed from a list of namespaces.
            :id: T_ARMI_MAT_NAMESPACE0
            :tests: R_ARMI_MAT_NAMESPACE
        """
        self.assertIs(
            materials.resolveMaterialClassByName("Void", namespaceOrder=["armi.materials"]),
            materials.Void,
        )
        self.assertIs(
            materials.resolveMaterialClassByName("Void", namespaceOrder=["armi.materials.mox", "armi.materials"]),
            materials.Void,
        )
        with self.assertRaises(ModuleNotFoundError):
            materials.resolveMaterialClassByName("Void", namespaceOrder=["invalid.namespace", "armi.materials"])
        with self.assertRaises(KeyError):
            materials.resolveMaterialClassByName("Unobtanium", namespaceOrder=["armi.materials"])

    def __validateMaterialNamespace(self):
        """Helper method to validate the material namespace a little."""
        self.assertTrue(isinstance(_MATERIAL_NAMESPACE_ORDER, list))
        self.assertGreater(len(_MATERIAL_NAMESPACE_ORDER), 0)
        for nameSpace in _MATERIAL_NAMESPACE_ORDER:
            self.assertTrue(isinstance(nameSpace, str))

    @unittest.skipUnless(context.MPI_RANK == 0, "test only on root node")
    def test_namespacing(self):
        """Test loading materials with different material namespaces, to cover how they work.

        .. test:: Material can be found in defined packages.
            :id: T_ARMI_MAT_NAMESPACE1
            :tests: R_ARMI_MAT_NAMESPACE

        .. test:: Material namespaces register materials with an order of priority.
            :id: T_ARMI_MAT_ORDER
            :tests: R_ARMI_MAT_ORDER
        """
        # let's do a quick test of getting a material from the default namespace
        setMaterialNamespaceOrder(["armi.materials"])
        uraniumOxide = materials.resolveMaterialClassByName("UraniumOxide", namespaceOrder=["armi.materials"])
        self.assertGreater(uraniumOxide().density(500), 0)

        # validate the default namespace in ARMI
        self.__validateMaterialNamespace()

        # show you can add a material namespace
        newMats = "armi.utils.tests.test_densityTools"
        setMaterialNamespaceOrder(["armi.materials", newMats])
        self.__validateMaterialNamespace()

        # in the case of duplicate materials, show that the material namespace determines
        # which material is chosen
        uraniumOxideTest = materials.resolveMaterialClassByName(
            "UraniumOxide", namespaceOrder=[newMats, "armi.materials"]
        )
        for t in range(200, 600):
            self.assertEqual(uraniumOxideTest().density(t), 0)
            self.assertEqual(uraniumOxideTest().pseudoDensity(t), 0)

        # for safety, reset the material namespace list and order
        setMaterialNamespaceOrder(["armi.materials"])


class CaliforniumTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Californium

    def test_pseudoDensity(self):
        ref = 15.1

        cur = self.mat.pseudoDensity(923)
        self.assertEqual(cur, ref)

        cur = self.mat.pseudoDensity(1390)
        self.assertEqual(cur, ref)

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)

    def test_porosities(self):
        self.mat.parent = None
        self.assertEqual(self.mat.liquidPorosity, 0.0)
        self.assertEqual(self.mat.gasPorosity, 0.0)


class CesiumTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Cs

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(250)
        ref = 1.93
        self.assertAlmostEqual(cur, ref, delta=ref * 0.05)

        cur = self.mat.pseudoDensity(450)
        ref = 1.843
        self.assertAlmostEqual(cur, ref, delta=ref * 0.05)

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)


class MagnesiumTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Magnesium
    VALID_TEMP_K = 1000

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(923)
        ref = 1.5897
        delta = ref * 0.0001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.pseudoDensity(1390)
        ref = 1.4661
        delta = ref * 0.0001
        self.assertAlmostEqual(cur, ref, delta=delta)


class MagnesiumOxideTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.MgO

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(923)
        ref = 3.48887
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.pseudoDensity(1250)
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


class MolybdenumTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Molybdenum

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(333)
        ref = 10.28
        delta = ref * 0.0001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.pseudoDensity(1390)
        ref = 10.28
        delta = ref * 0.0001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)


class MOXTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.MOX

    def test_density(self):
        cur = self.mat.density(333)
        ref = 10.926
        delta = ref * 0.0001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_getMassFracPuO2(self):
        ref = 0.176067
        self.assertAlmostEqual(self.mat.getMassFracPuO2(), ref, delta=ref * 0.001)

    def test_getMolFracPuO2(self):
        ref = 0.209
        self.assertAlmostEqual(self.mat.getMolFracPuO2(), ref, delta=ref * 0.001)

    def test_getMeltingPoint(self):
        ref = 2996.788765
        self.assertAlmostEqual(self.mat.meltingPoint(), ref, delta=ref * 0.001)

    def test_applyInputParams(self):
        massFracNameList = [
            "AM241",
            "O16",
            "PU238",
            "PU239",
            "PU240",
            "PU241",
            "PU242",
            "U235",
            "U238",
        ]
        massFracRefValList = [
            0.000998,
            0.118643,
            0.000156,
            0.119839,
            0.029999,
            0.00415,
            0.000858,
            0.166759,
            0.558597,
        ]

        self.mat.applyInputParams()

        for name, frac in zip(massFracNameList, massFracRefValList):
            cur = self.mat.massFrac[name]
            self.assertEqual(cur, frac)

        # bonus code coverage for clearMassFrac()
        self.mat.clearMassFrac()
        self.assertEqual(len(self.mat.massFrac), 0)


class NaClTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.NaCl

    def test_density(self):
        cur = self.mat.density(Tc=100)
        ref = 2.113204
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.density(Tc=300)
        ref = 2.050604
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)


class NiobiumZirconiumTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.NZ

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(Tk=100)
        ref = 8.66
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.pseudoDensity(Tk=1390)
        ref = 8.66
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)


class PotassiumTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Potassium

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(Tc=100)
        print(self.mat.pseudoDensity(Tc=100))
        print(self.mat.density(Tc=100))
        print(self.mat.linearExpansionPercent(Tc=100))
        ref = 0.8195
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.pseudoDensity(Tc=333)
        ref = 0.7664
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.pseudoDensity(Tc=500)
        ref = 0.7267
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.pseudoDensity(Tc=750)
        ref = 0.6654
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.pseudoDensity(Tc=1200)
        ref = 0.5502
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)


class ScandiumOxideTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Sc2O3

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(Tc=25)
        ref = 3.86
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

    def test_linearExpansionPercent(self):
        cur = self.mat.linearExpansionPercent(Tc=100)
        ref = 0.0623499
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.linearExpansionPercent(Tc=400)
        ref = 0.28322
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))


class SodiumTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Sodium

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(372)
        ref = 0.92546
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.pseudoDensity(1700)
        ref = 0.597
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_enthalpy(self):
        cur = self.mat.enthalpy(372)
        ref = 208100.1914
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.enthalpy(1700)
        ref = 1959147.963
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_thermalConductivity(self):
        cur = self.mat.thermalConductivity(372)
        ref = 89.36546
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.thermalConductivity(1500)
        ref = 38.24675
        delta = ref * 0.001
        self.assertAlmostEqual(cur, ref, delta=delta)


class TantalumTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Tantalum

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(Tc=100)
        ref = 16.6
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.pseudoDensity(Tc=300)
        ref = 16.6
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)


class ThoriumUraniumMetalTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.ThU

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(Tc=100)
        ref = 11.68
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.pseudoDensity(Tc=300)
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

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 1)


class UraniumTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Uranium

    def test_applyInputParams(self):
        # check the defaults when applyInputParams is applied without arguments
        U235_wt_frac_default = 0.0071136523
        self.mat.applyInputParams()
        self.assertAlmostEqual(self.mat.massFrac["U235"], U235_wt_frac_default)
        densityTemp = materials.Uranium._densityTableK[0]
        density0 = self.mat.density(Tk=materials.Uranium._densityTableK[0])
        expectedDensity = materials.Uranium._densityTable[0]
        self.assertEqual(density0, expectedDensity)

        newWtFrac = 1.0
        newTDFrac = 0.5
        self.mat.applyInputParams(U235_wt_frac=newWtFrac, TD_frac=newTDFrac)
        self.assertEqual(self.mat.massFrac["U235"], newWtFrac)
        self.assertEqual(self.mat.density(Tk=densityTemp), expectedDensity * newTDFrac)
        self.assertAlmostEqual(self.mat.pseudoDensity(Tk=densityTemp), 9.535)

    def test_thermalConductivity(self):
        cur = self.mat.thermalConductivity(Tc=100)
        ref = 28.4893126292075
        self.assertAlmostEqual(cur, ref, delta=10e-10)

        cur = self.mat.thermalConductivity(Tc=300)
        ref = 32.7892714492074972
        self.assertAlmostEqual(cur, ref, delta=10e-10)

        cur = self.mat.thermalConductivity(Tc=500)
        ref = 37.5617902692074991
        self.assertAlmostEqual(cur, ref, delta=10e-10)

        cur = self.mat.thermalConductivity(Tc=700)
        ref = 42.8068690892075025
        self.assertAlmostEqual(cur, ref, delta=10e-10)

        cur = self.mat.thermalConductivity(Tc=900)
        ref = 48.5245079092075073
        self.assertAlmostEqual(cur, ref, delta=10e-10)

    def test_propertyValidTemperature(self):
        self.assertGreater(len(self.mat.propertyValidTemperature), 0)

        # ensure that material properties check the bounds and that the bounds
        # align with what is expected
        for propName, methodName in zip(
            [
                "thermal conductivity",
                "heat capacity",
                "density",
                "linear expansion",
                "linear expansion percent",
            ],
            [
                "thermalConductivity",
                "heatCapacity",
                "density",
                "linearExpansion",
                "linearExpansionPercent",
            ],
        ):
            lowerBound = self.mat.propertyValidTemperature[propName][0][0]
            upperBound = self.mat.propertyValidTemperature[propName][0][1]

            with self.assertRaises(ValueError):
                getattr(self.mat, methodName)(lowerBound - 1)

            with self.assertRaises(ValueError):
                getattr(self.mat, methodName)(upperBound + 1)

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(Tc=500)
        ref = 18.74504534852846
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))

        cur = self.mat.pseudoDensity(Tc=1000)
        ref = 18.1280492780791
        self.assertAlmostEqual(cur, ref, delta=abs(ref * 0.001))


class UraniumOxideTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.UraniumOxide

    def test_adjustMassEnrichment(self):
        o16 = 15.999304875697801
        u235 = 235.043929425
        u238 = 238.050788298
        self.mat.adjustMassEnrichment(0.02)

        gPerMol = 2 * o16 + 0.02 * u235 + 0.98 * u238
        massFracs = self.mat.massFrac

        testing.assert_allclose(massFracs["O"], 2 * o16 / gPerMol, rtol=5e-4)
        testing.assert_allclose(massFracs["U235"], 0.02 * (u235 * 0.02 + u238 * 0.98) / gPerMol, rtol=5e-4)
        testing.assert_allclose(massFracs["U238"], 0.98 * (u235 * 0.02 + u238 * 0.98) / gPerMol, rtol=5e-4)

        self.mat.adjustMassEnrichment(0.2)
        massFracs = self.mat.massFrac
        gPerMol = 2 * o16 + 0.8 * u238 + 0.2 * u235

        testing.assert_allclose(massFracs["O"], 2 * o16 / gPerMol, rtol=5e-4)
        testing.assert_allclose(massFracs["U235"], 0.2 * (u235 * 0.2 + u238 * 0.8) / gPerMol, rtol=5e-4)
        testing.assert_allclose(massFracs["U238"], 0.8 * (u235 * 0.2 + u238 * 0.8) / gPerMol, rtol=5e-4)

    def test_meltingPoint(self):
        cur = self.mat.meltingPoint()
        self.assertEqual(cur, 3123.0)

    def test_density(self):
        # Reference data taken from ORNL/TM-2000/351. "Thermophysical Properties of MOX and UO2 Fuels Including the
        # Effects of Irradiation.", Popov, et al. Table 3.2 "Parameters of thermal expansion of stoichiometric MOX fuel
        # and density of UO2 as a function of temperature"
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
        """Check against Figure 4.2 from ORNL 2000-1723 EFG."""
        self.assertAlmostEqual(self.mat.heatCapacity(300), 230.0, delta=20)
        self.assertAlmostEqual(self.mat.heatCapacity(1000), 320.0, delta=20)
        self.assertAlmostEqual(self.mat.heatCapacity(2000), 380.0, delta=20)

    def test_getDensityExpansion3D(self):
        expectedTemperature = 100.0

        ref_density = 10.86792660463439e3
        test_density = self.mat.density(Tc=expectedTemperature) * 1000.0
        error = math.fabs((ref_density - test_density) / ref_density)
        self.assertLess(error, 0.005)

    def test_duplicate(self):
        """Test the material duplication.

        .. test:: Materials shall calc mass fracs at init.
            :id: T_ARMI_MAT_FRACS4
            :tests: R_ARMI_MAT_FRACS
        """
        duplicateU = self.mat.duplicate()

        for key in self.mat.massFrac:
            self.assertEqual(duplicateU.massFrac[key], self.mat.massFrac[key])

        duplicateMassFrac = deepcopy(self.mat.massFrac)
        for key in self.mat.massFrac.keys():
            self.assertEqual(duplicateMassFrac[key], self.mat.massFrac[key])

    def test_propertyValidTemperature(self):
        self.assertGreater(len(self.mat.propertyValidTemperature), 0)

    def test_applyInputParams(self):
        uo2 = materials.UraniumOxide()
        original = uo2.density(500)
        uo2.applyInputParams(TD_frac=0.1)
        new = uo2.density(500)
        ratio = new / original
        self.assertAlmostEqual(ratio, 0.1)

        uo2 = materials.UraniumOxide()
        original = uo2.pseudoDensity(500)
        uo2.applyInputParams(TD_frac=0.1)
        new = uo2.pseudoDensity(500)
        ratio = new / original
        self.assertAlmostEqual(ratio, 0.01)


class ThoriumTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Thorium

    def test_setDefaultMassFracs(self):
        """
        Test default mass fractions.

        .. test:: The materials generate nuclide mass fractions.
            :id: T_ARMI_MAT_FRACS0
            :tests: R_ARMI_MAT_FRACS
        """
        self.mat.setDefaultMassFracs()
        cur = self.mat.massFrac
        ref = {"TH232": 1.0}
        self.assertEqual(cur, ref)

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(30)
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


class ThoriumOxideTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.ThoriumOxide

    def test_density(self):
        cur = self.mat.density(Tc=25)
        ref = 10.00
        accuracy = 4
        self.assertAlmostEqual(cur, ref, accuracy)

        # make sure that material modifications are correctly applied
        self.mat.applyInputParams(TD_frac=0.1)
        cur = self.mat.density(Tc=25)
        self.assertAlmostEqual(cur, ref * 0.1, accuracy)

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

    def test_propertyValidTemperature(self):
        self.assertGreater(len(self.mat.propertyValidTemperature), 0)


class VoidTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Void

    def test_pseudoDensity(self):
        """This material has a no pseudo-density."""
        self.mat.setDefaultMassFracs()
        for t in range(0, 1000, 100):
            cur = self.mat.pseudoDensity(Tc=t)
            self.assertEqual(cur, 0.0)

    def test_density(self):
        """This material has no density."""
        self.assertEqual(self.mat.density(500), 0)

        self.mat.setDefaultMassFracs()
        for t in range(0, 1000, 100):
            cur = self.mat.density(Tc=t)
            self.assertEqual(cur, 0.0)

    def test_linearExpansion(self):
        """This material does not expand linearly."""
        cur = self.mat.linearExpansion(400)
        ref = 0.0
        self.assertEqual(cur, ref)

    def test_propertyValidTemperature(self):
        """This material has no valid temperatures."""
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)


class MixtureTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials._Mixture

    def test_density(self):
        """This material has no density function."""
        self.assertEqual(self.mat.density(500), 0)

    def test_setDefaultMassFracs(self):
        """
        Test default mass fractions.

        .. test:: The materials generate nuclide mass fractions.
            :id: T_ARMI_MAT_FRACS1
            :tests: R_ARMI_MAT_FRACS
        """
        self.mat.setDefaultMassFracs()
        cur = self.mat.pseudoDensity(500)
        self.assertEqual(cur, 0.0)

    def test_linearExpansion(self):
        cur = self.mat.linearExpansion(400)
        self.assertEqual(cur, 0.0)

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)


class LeadTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Lead
    VALID_TEMP_K = 600

    def test_linearExpansion(self):
        """Unit tests for lead materials linear expansion.

        .. test:: Fluid materials do not linearly expand, at any temperature.
            :id: T_ARMI_MAT_FLUID2
            :tests: R_ARMI_MAT_FLUID
        """
        for t in range(300, 901, 25):
            cur = self.mat.linearExpansion(t)
            self.assertEqual(cur, 0)

    def test_setDefaultMassFracs(self):
        """
        Test default mass fractions.

        .. test:: The materials generate nuclide mass fractions.
            :id: T_ARMI_MAT_FRACS2
            :tests: R_ARMI_MAT_FRACS
        """
        self.mat.setDefaultMassFracs()
        cur = self.mat.massFrac
        ref = {"PB": 1}
        self.assertEqual(cur, ref)

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(634.39)
        ref = 10.6120
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.pseudoDensity(1673.25)
        ref = 9.4231
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_heatCapacity(self):
        cur = self.mat.heatCapacity(1200)
        ref = 138.647
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)


class LeadBismuthTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.LeadBismuth

    def test_setDefaultMassFracs(self):
        """
        Test default mass fractions.

        .. test:: The materials generate nuclide mass fractions.
            :id: T_ARMI_MAT_FRACS3
            :tests: R_ARMI_MAT_FRACS
        """
        self.mat.setDefaultMassFracs()
        cur = self.mat.massFrac
        ref = {"BI209": 0.555, "PB": 0.445}
        for refKey, refVal in ref.items():
            self.assertAlmostEqual(cur[refKey], refVal)

    def test_pseudoDensity(self):
        cur = self.mat.pseudoDensity(404.77)
        ref = 10.5617
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.pseudoDensity(1274.20)
        ref = 9.3627
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_heatCapacity(self):
        cur = self.mat.heatCapacity(400)
        ref = 149.2592
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

        cur = self.mat.heatCapacity(800)
        ref = 141.7968
        delta = ref * 0.05
        self.assertAlmostEqual(cur, ref, delta=delta)

    def test_dynamicVisc(self):
        ref = self.mat.dynamicVisc(Tc=150)
        cur = 0.0029355
        self.assertAlmostEqual(ref, cur, delta=ref * 0.001)

        ref = self.mat.dynamicVisc(Tc=200)
        cur = 0.0024316
        self.assertAlmostEqual(ref, cur, delta=ref * 0.001)


class CopperTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Cu

    def test_setDefaultMassFracs(self):
        cur = self.mat.massFrac
        ref = {"CU63": 0.6915, "CU65": 0.3085}
        self.assertEqual(cur, ref)

    def test_densityNeverChanges(self):
        for t in range(-200, 501, 100):
            cur = self.mat.density(Tc=t)
            self.assertAlmostEqual(cur, 8.913, 4)

    def test_linearExpansionPercent(self):
        temps = [100.0, 200.0, 600.0]
        expansions = [-0.2955, -0.1500, 0.5326]
        for i, temp in enumerate(temps):
            cur = self.mat.linearExpansionPercent(Tk=temp)
            self.assertAlmostEqual(cur, expansions[i], 4)

    def test_getChildren(self):
        self.assertEqual(len(self.mat.getChildren()), 0)

    def test_getChildrenWithFlags(self):
        self.assertEqual(len(self.mat.getChildrenWithFlags("anything")), 0)


class ZrTests(AbstractMaterialTest, unittest.TestCase):
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
        tempsK = [
            293,
            400,
            500,
            600,
            700,
            800,
            900,
            1000,
            1100,
            1200,
            1400,
            1600,
            1800,
        ]
        expectedValues = [
            0.0007078312624,
            0.0602048,
            0.123025,
            0.1917312,
            0.2652626,
            0.3425584,
            0.4225578,
            0.5042,
            0.5864242,
            0.5390352,
            0.7249496,
            0.9221264,
            1.1380488,
        ]
        for i, Tk in enumerate(tempsK):
            Tc = Tk - units.C_TO_K
            self.assertAlmostEqual(self.mat.linearExpansionPercent(Tc=Tc), expectedValues[i], msg=str(Tc))
            self.assertAlmostEqual(self.mat.linearExpansionPercent(Tk=Tk), expectedValues[i], msg=str(Tk))

    def test_pseudoDensity(self):
        tempsK = [
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
            1200,
            1400,
            1600,
            1800,
        ]
        expectedValues = [
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
            6.49973710507,
            6.47576529821,
            6.45048593916,
            6.4229727005,
        ]
        for i, Tk in enumerate(tempsK):
            Tc = Tk - units.C_TO_K
            self.assertAlmostEqual(self.mat.pseudoDensity(Tc=Tc), expectedValues[i], msg=str(Tc))
            self.assertAlmostEqual(self.mat.pseudoDensity(Tk=Tk), expectedValues[i], msg=str(Tk))


class InconelTests(AbstractMaterialTest, unittest.TestCase):
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

    def test_pseudoDensity(self):
        self.assertEqual(self.Inconel.pseudoDensity(Tc=25), 8.3600)
        self.assertEqual(self.Inconel800.pseudoDensity(Tc=21.0), 7.94)
        self.assertEqual(self.InconelPE16.pseudoDensity(Tc=25), 8.00)

    def test_Iconel800_linearExpansion(self):
        temps = [100, 200, 300, 400, 500, 600, 700, 800]
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

        for Tc, ref in zip(temps, refList):
            cur = self.Inconel800.linearExpansionPercent(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.Inconel.propertyValidTemperature), 0)
        self.assertEqual(len(self.InconelPE16.propertyValidTemperature), 0)
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)


class Inconel600Tests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Inconel600

    def test_setDefaultMassFracs(self):
        massFracNameList = ["NI", "CR", "FE", "C", "MN55", "S", "SI", "CU"]
        massFracRefValList = [0.7541, 0.1550, 0.0800, 0.0008, 0.0050, 0.0001, 0.0025, 0.0025]

        for name, ref in zip(massFracNameList, massFracRefValList):
            cur = self.mat.getMassFrac(name)
            self.assertAlmostEqual(cur, ref)

    def test_linearExpansionPercent(self):
        temps = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            0.105392,
            0.246858,
            0.395768,
            0.552122,
            0.71592,
            0.887162,
            1.065848,
            1.251978,
        ]

        for Tc, ref in zip(temps, refList):
            cur = self.mat.linearExpansionPercent(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))

    def test_linearExpansion(self):
        temps = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            1.37744e-5,
            1.45188e-5,
            1.52632e-5,
            1.60076e-5,
            1.6752e-5,
            1.74964e-5,
            1.82408e-5,
            1.89852e-5,
        ]

        for Tc, ref in zip(temps, refList):
            cur = self.mat.linearExpansion(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))

    def test_pseudoDensity(self):
        temps = [100, 200, 300, 400, 500, 600, 700, 800]
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

        for Tc, ref in zip(temps, refList):
            cur = self.mat.pseudoDensity(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))

    def test_heatCapacity(self):
        ref = self.mat.heatCapacity(Tc=100)
        cur = 461.947021
        self.assertAlmostEqual(ref, cur, delta=cur * 0.001)

        ref = self.mat.heatCapacity(Tc=200)
        cur = 482.742084
        self.assertAlmostEqual(ref, cur, delta=cur * 0.001)


class Inconel625Tests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Inconel625

    def test_setDefaultMassFracs(self):
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

        for name, ref in zip(massFracNameList, massFracRefValList):
            cur = self.mat.getMassFrac(name)
            self.assertAlmostEqual(cur, ref)

    def test_linearExpansionPercent(self):
        temps = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [0.099543, 0.227292, 0.365207, 0.513288, 0.671535, 0.839948, 1.018527, 1.207272]

        for Tc, ref in zip(temps, refList):
            cur = self.mat.linearExpansionPercent(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))

    def test_linearExpansion(self):
        temps = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            1.22666e-5,
            1.32832e-5,
            1.42998e-5,
            1.53164e-5,
            1.6333e-5,
            1.73496e-5,
            1.83662e-5,
            1.93828e-5,
        ]

        for Tc, ref in zip(temps, refList):
            cur = self.mat.linearExpansion(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))

    def test_pseudoDensity(self):
        temps = [100, 200, 300, 400, 500, 600, 700, 800]
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

        for Tc, ref in zip(temps, refList):
            cur = self.mat.pseudoDensity(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))

    def test_heatCapacity(self):
        ref = self.mat.heatCapacity(Tc=300)
        cur = 478.776007
        self.assertAlmostEqual(ref, cur, delta=cur * 0.001)

        ref = self.mat.heatCapacity(Tc=400)
        cur = 503.399568
        self.assertAlmostEqual(ref, cur, delta=cur * 0.001)


class InconelX750Tests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.InconelX750

    def test_setDefaultMassFracs(self):
        massFracNameList = ["NI", "CR", "FE", "TI", "AL27", "NB93", "MN55", "SI", "S", "CU", "C", "CO59"]
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

        for name, ref in zip(massFracNameList, massFracRefValList):
            cur = self.mat.getMassFrac(name)
            self.assertAlmostEqual(cur, ref)

    def test_linearExpansionPercent(self):
        temps = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            0.0992768,
            0.2253902,
            0.3651792,
            0.5186438,
            0.685784,
            0.8665998,
            1.0610912,
            1.2692582,
        ]

        for Tc, ref in zip(temps, refList):
            cur = self.mat.linearExpansionPercent(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))

    def test_linearExpansion(self):
        temps = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            1.192756e-5,
            1.329512e-5,
            1.466268e-5,
            1.603024e-5,
            1.73978e-5,
            1.876536e-5,
            2.013292e-5,
            2.150048e-5,
        ]

        for Tc, ref in zip(temps, refList):
            cur = self.mat.linearExpansion(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))

    def test_pseudoDensity(self):
        temps = [100, 200, 300, 400, 500, 600, 700, 800]
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

        for Tc, ref in zip(temps, refList):
            cur = self.mat.pseudoDensity(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))

    def test_heatCapacity(self):
        ref = self.mat.heatCapacity(Tc=100)
        cur = 459.61381
        self.assertAlmostEqual(ref, cur, delta=cur * 0.001)

        ref = self.mat.heatCapacity(Tc=200)
        cur = 484.93968
        self.assertAlmostEqual(ref, cur, delta=cur * 0.001)


class Alloy200Tests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Alloy200

    def test_nickleContent(self):
        """Assert alloy 200 has more than 99% nickel per its spec."""
        self.assertGreater(self.mat.massFrac["NI"], 0.99)

    def test_linearExpansion(self):
        ref = self.mat.linearExpansion(Tc=100)
        cur = 13.3e-6
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))

    def test_linearExpansionHotter(self):
        ref = self.mat.linearExpansion(Tk=873.15)
        cur = 15.6e-6
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))


class CaH2Tests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.CaH2

    def test_pseudoDensity(self):
        cur = 1.7
        ref = self.mat.pseudoDensity(Tc=100)
        self.assertAlmostEqual(cur, ref, ref * 0.01)

        ref = self.mat.pseudoDensity(Tc=300)
        self.assertAlmostEqual(cur, ref, ref * 0.01)

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)


class HafniumTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Hafnium

    def test_pseudoDensity(self):
        cur = 13.07
        ref = self.mat.pseudoDensity(Tc=100)
        self.assertAlmostEqual(cur, ref, ref * 0.01)

        ref = self.mat.pseudoDensity(Tc=300)
        self.assertAlmostEqual(cur, ref, ref * 0.01)

    def test_propertyValidTemperature(self):
        self.assertEqual(len(self.mat.propertyValidTemperature), 0)


class HT9Tests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.HT9

    def test_feContent(self):
        self.assertGreater(self.mat.massFrac["FE"], 0.80)
        self.assertLess(self.mat.massFrac["FE"], 0.90)

    def test_linearExpansion(self):
        ref = self.mat.linearExpansion(Tc=200)
        cur = 1.1398126837389904e-5
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))

        ref = self.mat.linearExpansion(Tc=500)
        cur = 1.3766503292589587e-5
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))


class HastelloyNTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.HastelloyN

    def test_thermalConductivity(self):
        temps = [200, 300, 400, 500, 600, 700]
        refList = [13.171442, 14.448584, 16.11144, 18.16001, 20.594294, 23.414292]

        for Tc, ref in zip(temps, refList):
            cur = self.mat.thermalConductivity(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))

    def test_heatCapacity(self):
        temps = [100, 200, 300, 400, 500, 600, 700]
        refList = [419.183138, 438.728472, 459.630622, 464.218088, 480.092250, 556.547128, 573.450902]

        for Tc, ref in zip(temps, refList):
            cur = self.mat.heatCapacity(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))

    def test_linearExpansionPercent(self):
        temps = [100, 200, 300, 400, 500, 600, 700, 800]
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

        for Tc, ref in zip(temps, refList):
            cur = self.mat.linearExpansionPercent(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))

    def test_alpha_mean(self):
        temps = [100, 200, 300, 400, 500, 600, 700, 800]
        refList = [
            1.22066141e-5,
            1.23616846e-5,
            1.25688115e-5,
            1.28279948e-5,
            1.31392345e-5,
            1.35025306e-5,
            1.39178831e-5,
            1.4385292e-5,
        ]

        for Tc, ref in zip(temps, refList):
            cur = self.mat.alpha_mean(T=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-7, msg=str(Tc))


class TZMTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.TZM

    def test_applyInputParams(self):
        massFracNameList = ["C", "TI", "ZR", "MO"]
        massFracRefValList = [2.50749e-5, 0.002502504, 0.000761199, 0.996711222]

        self.mat.applyInputParams()

        for name, ref in zip(massFracNameList, massFracRefValList):
            cur = self.mat.massFrac[name]
            self.assertAlmostEqual(cur, ref)

    def test_pseudoDensity(self):
        ref = 10.16  # g/cc
        cur = self.mat.pseudoDensity(Tc=21.11)
        self.assertEqual(cur, ref)

    def test_linearExpansionPercent(self):
        temps = [
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
            1.60e-1,
            2.03e-1,
            2.53e-1,
            3.03e-1,
            3.03e-1,
            3.42e-1,
            3.66e-1,
            4.21e-1,
            4.68e-1,
            5.04e-1,
        ]

        for Tc, ref in zip(temps, refList):
            cur = self.mat.linearExpansionPercent(Tc=Tc)
            self.assertAlmostEqual(cur, ref, delta=10e-3, msg=str(Tc))


class YttriumOxideTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.Y2O3

    def test_pseudoDensity(self):
        cur = 5.03
        ref = self.mat.pseudoDensity(Tc=25)
        self.assertAlmostEqual(cur, ref, 2)

    def test_linearExpansionPercent(self):
        ref = self.mat.linearExpansionPercent(Tc=100)
        cur = 0.069662
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))

        ref = self.mat.linearExpansionPercent(Tc=100)
        cur = 0.0696622
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))


class ZincOxideTests(AbstractMaterialTest, unittest.TestCase):
    MAT_CLASS = materials.ZnO

    def test_density(self):
        cur = 5.61
        ref = self.mat.density(Tk=10.12)
        self.assertAlmostEqual(cur, ref, 2)

    def test_linearExpansionPercent(self):
        ref = self.mat.linearExpansionPercent(Tc=100)
        cur = 0.04899694350661124
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))

        ref = self.mat.linearExpansionPercent(Tc=300)
        cur = 0.15825020246870625
        self.assertAlmostEqual(ref, cur, delta=abs(ref * 0.001))


class FuelMaterialTests(unittest.TestCase):
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
        design._prepConstruction(settings.Settings())
        return design.assemblies["fuel a"]

    def test_class1Class2Class1WtFrac(self):
        # should error because class1_wt_frac not in (0,1)
        with self.assertRaises(ValueError):
            _a = self.loadAssembly(
                """
        material modifications:
            class1_wt_frac: [2.0]
            class1_custom_isotopics: [customIsotopic1]
            class2_custom_isotopics: [customIsotopic2]
        """
            )

    def test_class1Class2ClassXCustomIsotopics(self):
        # should error because class1_custom_isotopics does not exist
        with self.assertRaises(KeyError):
            _a = self.loadAssembly(
                """
        material modifications:
            class1_wt_frac: [0.5]
            class1_custom_isotopics: [fakeIsotopic]
            class2_custom_isotopics: [customIsotopic2]
        """
            )

        # should error because class2_custom_isotopics does not exist
        with self.assertRaises(KeyError):
            _a = self.loadAssembly(
                """
        material modifications:
            class1_wt_frac: [0.5]
            class1_custom_isotopics: [customIsotopic1]
            class2_custom_isotopics: [fakeIsotopic]
        """
            )
