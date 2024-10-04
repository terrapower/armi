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

"""Tests for reactor blueprints."""
import os
import unittest

from armi import settings
from armi.reactor import blueprints
from armi.reactor import reactors
from armi.reactor.blueprints import gridBlueprint
from armi.reactor.blueprints import reactorBlueprint
from armi.reactor.blueprints.tests import test_customIsotopics
from armi.reactor.composites import Composite
from armi.reactor.excoreStructure import ExcoreStructure
from armi.reactor.reactors import Core
from armi.reactor.spentFuelPool import SpentFuelPool

CORE_BLUEPRINT = """
core:
  grid name: core
  origin:
    x: 0.0
    y: 10.1
    z: 1.1
sfp:
    type: sfp
    grid name: sfp
    origin:
        x: 0.0
        y: 12.1
        z: 1.1
evst:
    type: excore
    grid name: evst
    origin:
        x: 0.0
        y: 100.0
        z: 0.0
"""

GRIDS = """
core:
    geom: hex
    symmetry: third core periodic
    grid contents:
      [0, 0]: IC
      [1, 1]: IC
sfp:
    lattice pitch:
        x: 25.0
        y: 25.0
    geom: cartesian
    symmetry: full
    lattice map: |
      IC IC
      IC IC
evst:
    lattice pitch:
        x: 32.0
        y: 32.0
    geom: cartesian
    symmetry: full
    lattice map: |
      IC IC
      IC IC
"""

GEOM = """<?xml version="1.0" ?>
<reactor geom="hex" symmetry="third core periodic">
    <assembly name="IC" pos="1" ring="1"/>
    <assembly name="IC" pos="2" ring="2"/>
</reactor>
"""


class TestReactorBlueprints(unittest.TestCase):
    """Tests for reactor blueprints."""

    def setUp(self):
        # add testMethodName to avoid I/O collisions during parallel testing
        self.systemDesigns = reactorBlueprint.Systems.load(CORE_BLUEPRINT)
        self.gridDesigns = gridBlueprint.Grids.load(GRIDS)

    def test_simpleRead(self):
        self.assertAlmostEqual(self.systemDesigns["core"].origin.y, 10.1)
        self.assertAlmostEqual(self.systemDesigns["sfp"].origin.y, 12.1)
        self.assertAlmostEqual(self.systemDesigns["evst"].origin.y, 100)

    def _setupReactor(self):
        fnames = [self._testMethodName + n for n in ["geometry.xml", "sfp-geom.xml"]]
        for fn in fnames:
            with open(fn, "w") as f:
                f.write(GEOM)

        # test migration from geometry xml files
        cs = settings.Settings()
        newSettings = {"geomFile": self._testMethodName + "geometry.xml"}
        cs = cs.modified(newSettings=newSettings)

        bp = blueprints.Blueprints.load(
            test_customIsotopics.TestCustomIsotopics.yamlString
        )
        bp.systemDesigns = self.systemDesigns
        bp.gridDesigns = self.gridDesigns
        reactor = reactors.Reactor(cs.caseTitle, bp)
        core = bp.systemDesigns["core"].construct(cs, bp, reactor)
        sfp = bp.systemDesigns["sfp"].construct(cs, bp, reactor)
        evst = bp.systemDesigns["evst"].construct(cs, bp, reactor)
        for fn in fnames:
            os.remove(fn)

        return core, sfp, evst

    def test_construct(self):
        """Actually construct some reactor systems.

        .. test:: Create core and spent fuel pool with blueprint.
            :id: T_ARMI_BP_SYSTEMS
            :tests: R_ARMI_BP_SYSTEMS

        .. test:: Create core object with blueprint.
            :id: T_ARMI_BP_CORE
            :tests: R_ARMI_BP_CORE
        """
        core, sfp, evst = self._setupReactor()
        self.assertEqual(len(core), 2)
        self.assertEqual(len(sfp), 4)
        self.assertEqual(len(evst), 4)

        self.assertIsInstance(core, Core)
        self.assertIsInstance(sfp, SpentFuelPool)
        self.assertIsInstance(evst, ExcoreStructure)

    def test_materialDataSummary(self):
        """Test that the material data summary for the core is valid as a printout to the stdout."""
        expectedMaterialData = [("Custom", "ARMI"), ("HT9", "ARMI"), ("UZr", "ARMI")]
        core, _sfp, _evst = self._setupReactor()
        materialData = reactorBlueprint.summarizeMaterialData(core)
        for actual, expected in zip(materialData, expectedMaterialData):
            self.assertEqual(actual, expected)

    def test_excoreStructure(self):
        _core, _sfp, evst = self._setupReactor()
        self.assertIsInstance(evst, ExcoreStructure)
        self.assertEqual(evst.parent.__class__.__name__, "Reactor")
        self.assertEqual(evst.spatialGrid.__class__.__name__, "CartesianGrid")

        # add one composite object and validate
        comp1 = Composite("thing1")
        loc = evst.spatialGrid[(0, 0, 0)]

        self.assertEqual(len(evst.getChildren()), 4)
        evst.add(comp1, loc)
        self.assertEqual(len(evst.getChildren()), 5)

    def test_spentFuelPool(self):
        _core, sfp, evst = self._setupReactor()
        self.assertIsInstance(sfp, SpentFuelPool)
        self.assertEqual(sfp.parent.__class__.__name__, "Reactor")
        self.assertEqual(sfp.spatialGrid.__class__.__name__, "CartesianGrid")
        self.assertEqual(sfp.numColumns, 2)

        # add one assembly and validate
        self.assertEqual(len(sfp.getChildren()), 4)
        sfp.add(evst.getChildren()[0])
        self.assertEqual(len(sfp.getChildren()), 5)
