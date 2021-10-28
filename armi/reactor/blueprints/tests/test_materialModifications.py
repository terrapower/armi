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
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access

from io import StringIO
import logging
import unittest

from numpy.testing import assert_allclose

from armi import context
from armi import materials
from armi import runLog
from armi import settings
from armi.reactor import blueprints


class TestMaterialModifications(unittest.TestCase):
    uZrInput = r"""
nuclide flags:
    U: {burn: false, xs: true}
    ZR: {burn: false, xs: true}
blocks:
    fuel: &block_fuel
        fuel: &component_fuel_fuel
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

    boronInput = uZrInput.replace("UZr", "B")

    def loadUZrAssembly(self, materialModifications):
        yamlString = self.uZrInput + "\n" + materialModifications
        design = blueprints.Blueprints.load(yamlString)
        design._prepConstruction(settings.getMasterCs())
        return design.assemblies["fuel a"]

    def test_noMaterialModifications(self):
        a = self.loadUZrAssembly("")
        # mass fractions should be whatever UZr is
        uzr = materials.UZr()
        fuelComponent = a[0][0]
        totalMass = fuelComponent.getMass()
        for nucName in uzr.p.massFrac:
            massFrac = fuelComponent.getMass(nucName) / totalMass
            assert_allclose(uzr.p.massFrac[nucName], massFrac)

    def test_u235_wt_frac_modification(self):
        a = self.loadUZrAssembly(
            """
        material modifications:
            U235_wt_frac: [0.20]
        """
        )
        fuelComponent = a[0][0]
        u235 = fuelComponent.getMass("U235")
        u = fuelComponent.getMass("U")
        assert_allclose(0.20, u235 / u)

    def test_zr_wt_frac_modification(self):
        a = self.loadUZrAssembly(
            """
        material modifications:
            ZR_wt_frac: [0.077]
        """
        )
        fuelComponent = a[0][0]
        totalMass = fuelComponent.getMass()
        zr = fuelComponent.getMass("ZR")
        assert_allclose(0.077, zr / totalMass)

    def test_both_u235_zr_wt_frac_modification(self):
        # init the _RunLog object
        log = runLog.LOG = runLog._RunLog(0)
        log.startLog("test_both_u235_zr_wt_frac_modification")
        context.createLogDir(0)
        log.setVerbosity(logging.INFO)

        # divert the logging to a stream, to make testing easier
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        log.logger.handlers = [handler]

        # load an assembly, with only valid mat mods
        a = self.loadUZrAssembly(
            """
        material modifications:
            ZR_wt_frac: [0.077]
            U235_wt_frac: [0.20]
        """
        )
        fuelComponent = a[0][0]

        # check u235 enrichment
        u235 = fuelComponent.getMass("U235")
        u = fuelComponent.getMass("U")
        assert_allclose(0.20, u235 / u)

        # check zr frac
        totalMass = fuelComponent.getMass()
        zr = fuelComponent.getMass("ZR")
        assert_allclose(0.077, zr / totalMass)

        # test that we don't get the "invalid material mod" warnings
        streamVal = stream.getvalue()
        self.assertNotIn("material modifications", streamVal, msg=streamVal)
        self.assertNotIn("ZR_wt_frac", streamVal, msg=streamVal)
        self.assertNotIn("U235_wt_frac", streamVal, msg=streamVal)

    def test_unusedMaterialModifications(self):
        """
        Users will want to be warned if the explictly put material modifications in a YAML file, but they aren't
        used. If it is a spelling error or invalid string, errors should not pass silently.
        """
        # init the _RunLog object
        log = runLog.LOG = runLog._RunLog(0)
        log.startLog("test_unusedMaterialModifications")
        context.createLogDir(0)
        log.setVerbosity(logging.INFO)

        # divert the logging to a stream, to make testing easier
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        log.logger.handlers = [handler]

        # load an assembly, with a wonky mat mod
        a = self.loadUZrAssembly(
            """
        material modifications:
            this_is_a_fake_setting: [0.5]
        """
        )

        # test that the invalid mat mod was logged
        streamVal = stream.getvalue()
        self.assertIn("material modifications", streamVal, msg=streamVal)
        self.assertIn("this_is_a_fake_setting", streamVal, msg=streamVal)


if __name__ == "__main__":
    unittest.main()
