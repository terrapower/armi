# Copyright 2026 TerraPower, LLC
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

"""Program that runs all of the tests contained in PropertyTests class."""

import os
import unittest
from os import path

from armi.matProps import loadMaterial
from armi.matProps.prop import defProp, properties


class PropertyTests(unittest.TestCase):
    """Class which contains tests for the matProps Property class."""

    @classmethod
    def setUpClass(cls):
        # Properties allowed for based on SDID.
        cls.allowedPropertiesList = [
            "density",
            "specific heat capacity",
            "thermal conductivity",
            "thermal diffusivity",
            "dynamic viscosity",
            "kinematic viscosity",
            "melting temperature",
            "boiling temperature",
            "surface tension",
            "vapor pressure",
            "electrical conductance",
            "isothermal compressibility",
            "mean coefficient of thermal expansion",
            "instantaneous coefficient of thermal expansion",
            "Young's modulus",
            "shear modulus",
            "elongation",
            "Poisson's ratio",
            "yield strength",
            "tensile strength",
            "design stress",
            "design reference stress",
            "allowable stress",
            "time dependent design stress",
            "service reference stress",
            "stress to rupture",
            "tensile strength reduction factor",
            "yield strength reduction factor",
            "weld strength reduction factor",
            "allowable time to rupture",
            "allowable time to allowable stress",
            "design fatigue strain range",
            "strain from isochronous stress-strain curve",
            "design fatigue stress",
            "linear expansion",
            "vapor specific volume",
            "speed of sound",
            "solidus temperature",
            "liquidus temperature",
            "volumetric expansion",
            "enthalpy",
            "temperature from enthalpy",
            "enthalpy of fusion",
            "latent heat of vaporization",
            "fracture toughness",
            "Brinell Hardness",
            "factor f from ASME.III.5 Fig. HBB-T-1432-2",
            "factor Kv' from ASME.III.5 Fig. HBB-T-1432-3",
        ]

    def test_propertiesUnique(self):
        """Ensure the Property.name and Property.symbol are all unique inside the matProps.properties container."""
        num = len(properties)
        self.assertEqual(num, len({p.name for p in properties}))
        self.assertEqual(num, len({p.symbol for p in properties}))

    def test_propertiesNames(self):
        """Ensure that we have the correct set of Properties in matProps."""
        propertySet = {p.name for p in properties}
        allowedPropertiesSet = set(self.allowedPropertiesList)
        self.assertEqual(propertySet, allowedPropertiesSet)

    def test_propertiesInvName(self):
        """Ensure loadNode fails correctly when provided when provided an unknown property."""
        tempFileName = os.path.join(os.path.dirname(__file__), "invalidTestFiles", "badProperty.yaml")

        with self.assertRaisesRegex(KeyError, "Invalid property node"):
            loadMaterial(tempFileName)

    def test_propertiesDefinitions(self):
        """
        Check a logic branch in the Function.factory method which initializes armi.matProps.Function objects to be
        null. armi.matProps.Function objects only get set to a non-null object if the appropriate property node is
        provided in the YAML file. A test YAML file with only the density property provided. It checks to make sure that
        the Material.rho object corresponding with density is not a null object and performs an evaluation. A check is
        then performed on the Material.k object. This object, which corresponds to the thermal conductivity property,
        should be null as it is not defined in the test YAML file.
        """
        # Only the density property exists for the material below. It is a constant function
        yamlFilePath = path.join(path.dirname(path.realpath(__file__)), "testDir1", "a.yaml")
        mat = loadMaterial(yamlFilePath)
        # Name of density function is rho for materials
        self.assertIsNotNone(mat.rho)
        self.assertAlmostEqual(mat.rho.calc({"T": 150.0}), 1.0)
        # k corresponds to thermal conductivity which is not provided in test file.
        self.assertIsNone(mat.k)

    def test_spotCheckAllPropsDict(self):
        """Spot check every property at least once, using a dictionary of input values."""
        pathToTestYaml = path.join(path.dirname(path.realpath(__file__)), "testDir4")
        testMat = loadMaterial(path.join(pathToTestYaml, "sampleProperty.yaml"))
        self.assertAlmostEqual(testMat.rho.calc({"T": 300.0}), 1.0)
        self.assertAlmostEqual(testMat.c_p.calc({"T": 300.0}), 2.0)
        self.assertAlmostEqual(testMat.k.calc({"T": 300.0}), 3.0)
        self.assertAlmostEqual(testMat.alpha_d.calc({"T": 300.0}), 4.0)
        self.assertAlmostEqual(testMat.mu_d.calc({"T": 300.0}), 5.0)
        self.assertAlmostEqual(testMat.mu_k.calc({"T": 300.0}), 6.0)
        self.assertAlmostEqual(testMat.T_melt.calc({"T": 300.0}), 7.0)
        self.assertAlmostEqual(testMat.T_boil.calc({"T": 300.0}), 8.0)
        self.assertAlmostEqual(testMat.dH_vap.calc({"T": 300.0}), 9.0)
        self.assertAlmostEqual(testMat.dH_fus.calc({"T": 300.0}), 10.0)
        self.assertAlmostEqual(testMat.gamma.calc({"T": 300.0}), 11.0)
        self.assertAlmostEqual(testMat.P_sat.calc({"T": 300.0}), 12.0)
        self.assertAlmostEqual(testMat.kappa.calc({"T": 300.0}), 13.0)
        self.assertAlmostEqual(testMat.alpha_mean.calc({"T": 300.0}), 14.0)
        self.assertAlmostEqual(testMat.alpha_inst.calc({"T": 300.0}), 15.0)
        self.assertAlmostEqual(testMat.E.calc({"T": 300.0}), 16.0)
        self.assertAlmostEqual(testMat.nu.calc({"T": 300.0}), 17.0)
        self.assertAlmostEqual(testMat.Sy.calc({"T": 300.0}), 18.0)
        self.assertAlmostEqual(testMat.Su.calc({"T": 300.0}), 19.0)
        self.assertAlmostEqual(testMat.Sm.calc({"T": 300.0}), 20.0)
        self.assertAlmostEqual(testMat.So.calc({"T": 300.0}), 21.0)
        self.assertAlmostEqual(testMat.Sa.calc({"T": 300.0}), 22.0)
        self.assertAlmostEqual(testMat.St.calc({"T": 300.0}), 23.0)
        self.assertAlmostEqual(testMat.Smt.calc({"T": 300.0}), 24.0)
        self.assertAlmostEqual(testMat.Sr.calc({"T": 300.0}), 25.0)
        self.assertAlmostEqual(testMat.TSRF.calc({"T": 300.0}), 26.0)
        self.assertAlmostEqual(testMat.YSRF.calc({"T": 300.0}), 27.0)
        self.assertAlmostEqual(testMat.WSRF.calc({"T": 300.0}), 28.0)
        self.assertAlmostEqual(testMat.tMaxSr.calc({"T": 300.0}), 29.0)
        self.assertAlmostEqual(testMat.tMaxSt.calc({"T": 300.0}), 30.0)
        self.assertAlmostEqual(testMat.eps_t.calc({"T": 300.0}), 31.0)
        self.assertAlmostEqual(testMat.eps_iso.calc({"T": 300.0}), 32.0)
        self.assertAlmostEqual(testMat.SaFat.calc({"T": 300.0}), 33.0)
        self.assertAlmostEqual(testMat.dl_l.calc({"T": 300.0}), 34.0)
        self.assertAlmostEqual(testMat.nu_g.calc({"T": 300.0}), 35.0)
        self.assertAlmostEqual(testMat.v_sound.calc({"T": 300.0}), 36.0)
        self.assertAlmostEqual(testMat.T_sol.calc({"T": 300.0}), 37.0)
        self.assertAlmostEqual(testMat.T_liq.calc({"T": 300.0}), 38.0)
        self.assertAlmostEqual(testMat.dV.calc({"T": 300.0}), 39.0)
        self.assertAlmostEqual(testMat.H.calc({"T": 300.0}), 40.0)
        self.assertAlmostEqual(testMat.H_calc_T.calc({"T": 300.0}), 41.0)
        self.assertAlmostEqual(testMat.K_IC.calc({"T": 300.0}), 42.0)
        self.assertAlmostEqual(testMat.HBW.calc({"T": 300.0}), 43.0)
        self.assertAlmostEqual(testMat.f.calc({"T": 300.0}), 44.0)
        self.assertAlmostEqual(testMat.Kv_prime.calc({"T": 300.0}), 45.0)
        self.assertAlmostEqual(testMat.S.calc({"T": 300.0}), 46.0)
        self.assertAlmostEqual(testMat.Elong.calc({"T": 300.0}), 47.0)

    def test_spotCheckAllPropsKwargs(self):
        """Spot check every property at least once, using kwargs."""
        pathToTestYaml = path.join(path.dirname(path.realpath(__file__)), "testDir4")
        testMat = loadMaterial(path.join(pathToTestYaml, "sampleProperty.yaml"))
        self.assertAlmostEqual(testMat.rho.calc(T=300.0), 1.0)
        self.assertAlmostEqual(testMat.c_p.calc(T=300.0), 2.0)
        self.assertAlmostEqual(testMat.k.calc(T=300.0), 3.0)
        self.assertAlmostEqual(testMat.alpha_d.calc(T=300.0), 4.0)
        self.assertAlmostEqual(testMat.mu_d.calc(T=300.0), 5.0)
        self.assertAlmostEqual(testMat.mu_k.calc(T=300.0), 6.0)
        self.assertAlmostEqual(testMat.T_melt.calc(T=300.0), 7.0)
        self.assertAlmostEqual(testMat.T_boil.calc(T=300.0), 8.0)
        self.assertAlmostEqual(testMat.dH_vap.calc(T=300.0), 9.0)
        self.assertAlmostEqual(testMat.dH_fus.calc(T=300.0), 10.0)
        self.assertAlmostEqual(testMat.gamma.calc(T=300.0), 11.0)
        self.assertAlmostEqual(testMat.P_sat.calc(T=300.0), 12.0)
        self.assertAlmostEqual(testMat.kappa.calc(T=300.0), 13.0)
        self.assertAlmostEqual(testMat.alpha_mean.calc(T=300.0), 14.0)
        self.assertAlmostEqual(testMat.alpha_inst.calc(T=300.0), 15.0)
        self.assertAlmostEqual(testMat.E.calc(T=300.0), 16.0)
        self.assertAlmostEqual(testMat.nu.calc(T=300.0), 17.0)
        self.assertAlmostEqual(testMat.Sy.calc(T=300.0), 18.0)
        self.assertAlmostEqual(testMat.Su.calc(T=300.0), 19.0)
        self.assertAlmostEqual(testMat.Sm.calc(T=300.0), 20.0)
        self.assertAlmostEqual(testMat.So.calc(T=300.0), 21.0)
        self.assertAlmostEqual(testMat.Sa.calc(T=300.0), 22.0)
        self.assertAlmostEqual(testMat.St.calc(T=300.0), 23.0)
        self.assertAlmostEqual(testMat.Smt.calc(T=300.0), 24.0)
        self.assertAlmostEqual(testMat.Sr.calc(T=300.0), 25.0)
        self.assertAlmostEqual(testMat.TSRF.calc(T=300.0), 26.0)
        self.assertAlmostEqual(testMat.YSRF.calc(T=300.0), 27.0)
        self.assertAlmostEqual(testMat.WSRF.calc(T=300.0), 28.0)
        self.assertAlmostEqual(testMat.tMaxSr.calc(T=300.0), 29.0)
        self.assertAlmostEqual(testMat.tMaxSt.calc(T=300.0), 30.0)
        self.assertAlmostEqual(testMat.eps_t.calc(T=300.0), 31.0)
        self.assertAlmostEqual(testMat.eps_iso.calc(T=300.0), 32.0)
        self.assertAlmostEqual(testMat.SaFat.calc(T=300.0), 33.0)
        self.assertAlmostEqual(testMat.dl_l.calc(T=300.0), 34.0)
        self.assertAlmostEqual(testMat.nu_g.calc(T=300.0), 35.0)
        self.assertAlmostEqual(testMat.v_sound.calc(T=300.0), 36.0)
        self.assertAlmostEqual(testMat.T_sol.calc(T=300.0), 37.0)
        self.assertAlmostEqual(testMat.T_liq.calc(T=300.0), 38.0)
        self.assertAlmostEqual(testMat.dV.calc(T=300.0), 39.0)
        self.assertAlmostEqual(testMat.H.calc(T=300.0), 40.0)
        self.assertAlmostEqual(testMat.H_calc_T.calc(T=300.0), 41.0)
        self.assertAlmostEqual(testMat.K_IC.calc(T=300.0), 42.0)
        self.assertAlmostEqual(testMat.HBW.calc(T=300.0), 43.0)
        self.assertAlmostEqual(testMat.f.calc(T=300.0), 44.0)
        self.assertAlmostEqual(testMat.Kv_prime.calc(T=300.0), 45.0)
        self.assertAlmostEqual(testMat.S.calc(T=300.0), 46.0)
        self.assertAlmostEqual(testMat.Elong.calc(T=300.0), 47.0)

    def test_defPropDup(self):
        with self.assertRaises(KeyError):
            defProp("rho", "density", "kg/m^3", "rho")
