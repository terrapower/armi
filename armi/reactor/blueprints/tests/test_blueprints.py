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

"""Tests the blueprints (loading input) file."""
import io
import os
import pathlib
import unittest

import yamlize

from armi import settings
from armi.nucDirectory.elements import bySymbol
from armi.physics.neutronics.settings import CONF_XS_KERNEL
from armi.reactor import blueprints, parameters
from armi.reactor.blueprints.componentBlueprint import ComponentBlueprint
from armi.reactor.blueprints.gridBlueprint import saveToStream
from armi.reactor.blueprints.isotopicOptions import CustomIsotopics, NuclideFlags
from armi.reactor.flags import Flags
from armi.settings.fwSettings.globalSettings import CONF_INPUT_HEIGHTS_HOT
from armi.tests import TEST_ROOT
from armi.utils import directoryChangers, textProcessors


class TestBlueprints(unittest.TestCase):
    """Test that the basic functionality of faithfully receiving user input to construct ARMI data
    model objects works as expected.

    Try to ensure you test for ideas and not exact matches here, to make the tests more robust.
    """

    @classmethod
    def setUpClass(cls):
        cls.cs = settings.Settings()
        cls.directoryChanger = directoryChangers.DirectoryChanger(TEST_ROOT)
        cls.directoryChanger.open()

        y = textProcessors.resolveMarkupInclusions(
            pathlib.Path(os.getcwd()) / "refSmallReactor.yaml"
        )
        cls.blueprints = blueprints.Blueprints.load(y)
        cls.blueprints._prepConstruction(cls.cs)

    @classmethod
    def tearDownClass(cls):
        cls.directoryChanger.close()

    @staticmethod
    def __stubify(latticeMap):
        """Little helper method to allow lattie maps to be compared free of whitespace."""
        return latticeMap.replace(" ", "").replace("-", "").replace("\n", "")

    def test_roundTripCompleteBP(self):
        """Test the round-tip of reading and writing blueprint files.

        .. test:: Validates the round trip of reading and writing blueprints.
            :id: T_ARMI_BP_TO_DB1
            :tests: R_ARMI_BP_TO_DB
        """
        # the correct lattice map
        latticeMap = """-   -   SH
  -   SH  SH
-   SH  OC  SH
  SH  OC  OC  SH
    OC  IC  OC  SH
  OC  IC  IC  OC  SH
    IC  IC  IC  OC  SH
      IC  IC  PC  OC  SH
    IC  PC  IC  IC  OC  SH
      LA  IC  IC  IC  OC
        IC  IC  IC  IC  SH
      IC  LB  IC  IC  OC
        IC  IC  PC  IC  SH
          LA  IC  IC  OC
        IC  IC  IC  IC  SH
          IC  IC  IC  OC
        IC  IC  IC  PC  SH"""
        latticeMap = self.__stubify(latticeMap)

        # validate some core elements from the blueprints
        self.assertEqual(self.blueprints.gridDesigns["core"].symmetry, "third periodic")
        map0 = self.__stubify(self.blueprints.gridDesigns["core"].latticeMap)
        self.assertEqual(map0, latticeMap)

        # save the blueprint to a stream
        stream = io.StringIO()
        stream.seek(0)
        self.blueprints.dump(self.blueprints)
        saveToStream(stream, self.blueprints, True, True)
        stream.seek(0)

        with directoryChangers.TemporaryDirectoryChanger():
            # save the stream to a file
            filePath = "test_roundTripCompleteBP.yaml"
            with open(filePath, "w") as fout:
                fout.write(stream.read())

            # load the blueprint from that file again
            bp = blueprints.Blueprints.load(open(filePath, "r").read())

            # re-validate some core elements from the blueprints
            self.assertEqual(bp.gridDesigns["core"].symmetry, "third periodic")
            map1 = self.__stubify(bp.gridDesigns["core"].latticeMap)
            self.assertEqual(map1, latticeMap)

    def test_nuclides(self):
        """Tests the available sets of nuclides work as expected."""
        actives = set(self.blueprints.activeNuclides)
        inerts = set(self.blueprints.inertNuclides)
        self.assertEqual(
            actives.union(inerts), set(self.blueprints.allNuclidesInProblem)
        )
        self.assertEqual(actives.intersection(inerts), set())

    def test_getAssemblyTypeBySpecifier(self):
        aDesign = self.blueprints.assemDesigns.bySpecifier["IC"]
        self.assertEqual(aDesign.name, "igniter fuel")
        self.assertEqual(aDesign.specifier, "IC")

    def test_specialIsotopicVectors(self):
        mox = self.blueprints.customIsotopics["MOX"]
        allNucsInProblem = set(self.blueprints.allNuclidesInProblem)
        for a in mox.keys():
            self.assertIn(a, allNucsInProblem)
        self.assertIn("U235", mox)
        self.assertAlmostEqual(mox["PU239"], 0.00286038)

    def test_componentDimensions(self):
        """Tests that the user can specify the dimensions of a component with arbitrary fidelity.

        .. test:: A component can be correctly created from a blueprint file.
            :id: T_ARMI_BP_COMP
            :tests: R_ARMI_BP_COMP
        """
        fuelAssem = self.blueprints.constructAssem(self.cs, name="igniter fuel")
        fuel = fuelAssem.getComponents(Flags.FUEL)[0]
        self.assertAlmostEqual(fuel.getDimension("od", cold=True), 0.86602)
        self.assertAlmostEqual(fuel.getDimension("id", cold=True), 0.0)
        self.assertAlmostEqual(fuel.getDimension("od"), 0.87763665, 4)
        self.assertAlmostEqual(fuel.getDimension("id"), 0.0)
        self.assertAlmostEqual(fuel.getDimension("mult"), 169)

    def test_traceNuclides(self):
        """Ensure that armi.reactor.blueprints.componentBlueprint.insertDepletableNuclideKeys runs.

        .. test:: Users marking components as depletable will affect number densities.
            :id: T_ARMI_BP_NUC_FLAGS1
            :tests: R_ARMI_BP_NUC_FLAGS
        """
        fuel = (
            self.blueprints.constructAssem(self.cs, "igniter fuel")
            .getFirstBlock(Flags.FUEL)
            .getComponent(Flags.FUEL)
        )
        self.assertIn("AM241", fuel.getNuclides())
        self.assertLess(fuel.getNumberDensity("AM241"), 1e-5)


class TestBlueprintsSchema(unittest.TestCase):
    """Test the blueprint schema checks."""

    _yamlString = r"""blocks:
    fuel: &block_fuel
        fuel: &component_fuel_fuel
            shape: Hexagon
            material: UZr
            Tinput: 25.0
            Thot: 600.0
            ip: 0.0
            mult: 1.0
            op: 10.0
    fuel2: &block_fuel2
        group1:
            shape: Group
        duct:
            shape: Hexagon
            material: UZr
            Tinput: 25.0
            Thot: 600.0
            ip: 9.0
            mult: 1.0
            op: 10.0
        matrix:
            shape: DerivedShape
            material: Graphite
            Tinput: 25.0
            Thot: 600.0

components:
    freefuel:
        shape: Sphere
        material: UZr
        Tinput: 25.0
        Thot: 600.0
        id: 0.0
        mult: 1.0
        od: 4.0
    freeclad:
        shape: Sphere
        material: HT9
        Tinput: 25.0
        Thot: 600.0
        id: 4.0
        mult: 1.0
        od: 4.1

component groups:
    group1:
      freefuel:
        mult: 1.0
      freeclad:
        mult: 1.0

assemblies:
    fuel a: &assembly_a
        specifier: IC
        blocks: [*block_fuel]
        height: [1.0]
        axial mesh points: [1]
        xs types: [A]
    fuel b:
        <<: *assembly_a
        hotChannelFactors: Reactor
    fuel c: &assembly_c
        specifier: OC
        blocks: [*block_fuel2]
        height: [1.0]
        axial mesh points: [1]
        xs types: [A]
grids:
    pins:
        geom: cartesian
        lattice map: |
            2 2 2 2 2
            2 1 1 1 2
            2 1 3 1 2
            2 3 1 1 2
            2 2 2 2 2
"""

    def test_noDuplicateKeysInYamlBlueprints(self):
        """
        Prove that if you duplicate a section of a YAML blueprint file,
        a hard error will be thrown.
        """
        # loop through a few different sections, to test blueprints broadly
        sections = ["blocks:", "components:", "component groups:"]
        for sectionName in sections:
            # modify blueprint YAML to duplicate this section
            yamlString = str(self._yamlString)
            i = yamlString.find(sectionName)
            lenSection = yamlString[i:].find("\n\n")
            section = yamlString[i : i + lenSection]
            yamlString = yamlString[:i] + section + yamlString[i : i + lenSection]

            # validate that this is now an invalid YAML blueprint
            with self.assertRaises(Exception):
                _design = blueprints.Blueprints.load(yamlString)

    def test_assemblyParameters(self):
        cs = settings.Settings()
        design = blueprints.Blueprints.load(self._yamlString)
        fa = design.constructAssem(cs, name="fuel a")
        fb = design.constructAssem(cs, name="fuel b")
        for paramDef in fa.p.paramDefs.inCategory(
            parameters.Category.assignInBlueprints
        ):
            # Semantics of __iter__() and items() is different now in the parameter
            # system. Since we aren't using __slots__ anymore, we use the parameter
            # definitions (which have a global-ish sense of `assigned`ness), so we can't
            # tell, per-object, whether they've been set.
            self.assertEqual(paramDef.default, fa.p[paramDef.name])
            self.assertIn(paramDef.name, fb.p)

        self.assertEqual(fa.p.hotChannelFactors, "Default")
        self.assertEqual(fb.p.hotChannelFactors, "Reactor")

    def test_nuclidesMc2v2(self):
        """Tests that ZR is not expanded to its isotopics for this setting."""
        cs = settings.Settings()
        newSettings = {CONF_XS_KERNEL: "MC2v2"}
        cs = cs.modified(newSettings=newSettings)

        design = blueprints.Blueprints.load(self._yamlString)
        design._prepConstruction(cs)
        self.assertTrue(
            set({"U238", "U235", "ZR"}).issubset(set(design.allNuclidesInProblem))
        )

        assem = design.constructAssem(cs, name="fuel a")
        self.assertTrue(
            set(assem.getNuclides()).issubset(set(design.allNuclidesInProblem))
        )

    def test_nuclidesMc2v3(self):
        """Tests that ZR is expanded to its isotopics for MC2v3."""
        cs = settings.Settings()
        newSettings = {CONF_XS_KERNEL: "MC2v3"}
        cs = cs.modified(newSettings=newSettings)

        design = blueprints.Blueprints.load(self._yamlString)
        design._prepConstruction(cs)

        # 93 and 95 are not naturally occurring.
        zrNucs = {"ZR" + str(A) for A in range(90, 97)} - {"ZR93", "ZR95"}
        self.assertTrue(
            set({"U238", "U235"} | zrNucs).issubset(set(design.allNuclidesInProblem))
        )
        self.assertTrue(zrNucs.issubset(set(design.inertNuclides)))

        assem = design.constructAssem(cs, name="fuel a")
        # the assembly won't get non-naturally occurring nuclides
        unnaturalZr = (n.name for n in bySymbol["ZR"].nuclides if n.abundance == 0.0)
        designNucs = set(design.allNuclidesInProblem).difference(unnaturalZr)
        self.assertTrue(set(assem.getNuclides()).issubset(designNucs))

    def test_merge(self):
        yamlString = r"""
nuclide flags:
    B10: {burn: true, xs: true}
    B11: {burn: true, xs: true}
    DUMP1: {burn: true, xs: true}
    FE: {burn: true, xs: true}
    NI: {burn: true, xs: true}
    C: {burn: true, xs: true}
    MO: {burn: true, xs: true}
    SI: {burn: true, xs: true}
    CR: {burn: true, xs: true}
    MN:  {burn: true, xs: true}
    NA:  {burn: true, xs: true}
    V:  {burn: true, xs: true}
    W:  {burn: true, xs: true}
blocks:
    nomerge block: &unmerged_block
        A: &comp_a
            shape: Circle
            material: B4C
            Tinput: 50.0
            Thot: 500.0
            id: 0.0
            mult: 1
            od: .5
        Gap1: &comp_gap
            shape: Circle
            material: Void
            Tinput: 50.0
            Thot: 500.0
            id: A.od
            mult: 1
            od: B.id
        B: &gcomp_b
            shape: Circle
            material: HT9
            Tinput: 20.0
            Thot: 600.0
            id: .5
            mult: 1
            od: .75
        Gap2: &comp_gap2
            shape: Circle
            material: Void
            Tinput: 50.0
            Thot: 500.0
            id: B.od
            mult: 1
            od: Clad.id
        Clad: &comp_clad
            shape: Circle
            material: HT9
            Tinput: 20.0
            Thot: 700.0
            id: .75
            mult: 1
            od: 1.0
        coolant: &comp_coolant
            shape: DerivedShape
            material: Sodium
            Tinput: 600.0
            Thot: 600.0
        duct: &comp_duct
            shape: Hexagon
            material: HT9
            Tinput: 20.0
            Thot: 500.0
            ip: 1.2
            mult: 1
            op: 1.4
        intercoolant: &comp_intercoolant
            shape: Hexagon
            material: Sodium
            Tinput: 500.0
            Thot: 500.0
            ip: duct.op
            mult: 1
            op: 1.6
    merge block: &merged_block
        A:
            <<: *comp_a
            mergeWith: Clad
        Gap1: *comp_gap
        B:
            <<: *gcomp_b
            mergeWith: Clad
        Gap2: *comp_gap2
        Clad: *comp_clad
        coolant: *comp_coolant
        duct: *comp_duct
        intercoolant: *comp_intercoolant
assemblies:
    a: &assembly_a
        specifier: IC
        blocks: [*merged_block, *unmerged_block]
        height: [1.0, 1.0]
        axial mesh points: [1, 1]
        xs types: [A, A]
"""
        bp = blueprints.Blueprints.load(yamlString)
        a = bp.constructAssem(settings.Settings(), name="a")
        mergedBlock, unmergedBlock = a
        self.assertNotIn("A", mergedBlock.getComponentNames())
        self.assertNotIn("B", mergedBlock.getComponentNames())

        self.assertEqual(len(mergedBlock) + 4, len(unmergedBlock))
        self.assertAlmostEqual(
            sum(c.getArea() for c in mergedBlock),
            sum(c.getArea() for c in unmergedBlock),
        )

        mergedNucs, unmergedNucs = (
            mergedBlock.getNumberDensities(),
            unmergedBlock.getNumberDensities(),
        )
        errorMessage = ""
        for nucName in set(unmergedNucs) | set(mergedNucs):
            n1, n2 = unmergedNucs[nucName], mergedNucs[nucName]
            try:
                self.assertAlmostEqual(n1, n2)
            except AssertionError:
                errorMessage += "\nnuc {} not equal. unmerged: {} merged: {}".format(
                    nucName, n1, n2
                )
        self.assertTrue(not errorMessage, errorMessage)
        self.assertAlmostEqual(mergedBlock.getMass(), unmergedBlock.getMass())

    def test_nuclideFlags(self):
        with self.assertRaises(yamlize.YamlizingError):
            NuclideFlags.load("{potato: {burn: true, xs: true}}")

        with self.assertRaises(yamlize.YamlizingError):
            NuclideFlags.load("{U238: {burn: 12, xs: 0}}")

    def test_customIsotopics(self):
        with self.assertRaises(yamlize.YamlizingError):
            CustomIsotopics.load("MOX: {input format: applesauce}")

        with self.assertRaises(yamlize.YamlizingError):
            CustomIsotopics.load("MOX: {input format: number densities, density: -0.1}")

        with self.assertRaises(yamlize.YamlizingError):
            CustomIsotopics.load(
                "MOX: {input format: number densities, density: 1.5, FAKENUC234: 0.000286}"
            )

    def test_components(self):
        bads = [
            # bad shape
            {
                "shape": "potato",
                "name": "name",
                "material": "HT9",
                "Tinput": 1.0,
                "Thot": 1.0,
            },
            # bad merge
            {
                "shape": "circle",
                "name": "name",
                "material": "HT9",
                "Tinput": 1.0,
                "Thot": 1.0,
                "mergeWith": 6,
            },
            # bad isotopics
            {
                "shape": "circle",
                "name": "name",
                "material": "HT9",
                "Tinput": 1.0,
                "Thot": 1.0,
                "isotopics": 4,
            },
            # bad key
            {
                "shape": "circle",
                "name": "name",
                "material": "HT9",
                "Tinput": 1.0,
                "Thot": 1.0,
                5: "od",
            },
            # bad linked dimension
            {
                "shape": "circle",
                "name": "name",
                "material": "HT9",
                "Tinput": 1.0,
                "Thot": 1.0,
                "mult": "potato,mult",
            },
        ]
        for bad in bads:
            with self.assertRaises(yamlize.YamlizingError):
                ComponentBlueprint.load(repr(bad))

    def test_cladding_invalid(self):
        """Make sure cladding input components are flagged as invalid."""
        bad = {
            "name": "cladding",
            "shape": "Circle",
            "material": "HT9",
            "Tinput": 1.0,
            "Thot": 1.0,
        }
        with self.assertRaises(yamlize.YamlizingError):
            ComponentBlueprint.load(repr(bad))

    def test_withoutBlocks(self):
        # Some projects use a script to generate an input that has completely unique blocks,
        # so the blocks: section is not needed
        yamlWithoutBlocks = """
nuclide flags:
    U238: {burn: true, xs: true}
    U235: {burn: true, xs: true}
    LFP35: {burn: true, xs: true}
    U236: {burn: true, xs: true}
    PU239: {burn: true, xs: true}
    DUMP2: {burn: true, xs: true}
    DUMP1: {burn: true, xs: true}
    NP237: {burn: true, xs: true}
    PU238: {burn: true, xs: true}
    PU236: {burn: true, xs: true}
    LFP39: {burn: true, xs: true}
    PU238: {burn: true, xs: true}
    LFP40: {burn: true, xs: true}
    PU241: {burn: true, xs: true}
    LFP38: {burn: true, xs: true}
    U234: {burn: true, xs: true}
    AM241: {burn: true, xs: true}
    LFP41: {burn: true, xs: true}
    PU242: {burn: true, xs: true}
    AM243: {burn: true, xs: true}
    CM244: {burn: true, xs: true}
    CM242: {burn: true, xs: true}
    AM242: {burn: true, xs: true}
    PU240: {burn: true, xs: true}
    CM245: {burn: true, xs: true}
    NP238: {burn: true, xs: true}
    CM243: {burn: true, xs: true}
    CM246: {burn: true, xs: true}
    CM247: {burn: true, xs: true}
    ZR: {burn: false, xs: true}

assemblies:
    fuel a: &assembly_a
        specifier: FF
        blocks:
        - { name: fuel,
            fuel: { shape: Hexagon, material: UZr, Tinput: 25.0, Thot: 600.0, ip: 0.0, mult: 1.0, op: 10.0} }
        height: [1.0]
        axial mesh points: [1]
        xs types: [A]
    fuel b:
        <<: *assembly_a
        specifier: IF
        """
        cs = settings.Settings()
        design = blueprints.Blueprints.load(yamlWithoutBlocks)
        design.constructAssem(cs, name="fuel a")
        fa = design.constructAssem(cs, name="fuel a")
        fb = design.constructAssem(cs, name="fuel b")
        for a in (fa, fb):
            self.assertEqual(1, len(a))
            self.assertEqual(1, len(a[0]))

    def test_topLevelComponentInput(self):
        """
        Make sure components defined at the top level are loaded.

        Components can be loaded either within the block blueprint
        or on their own outside of blocks. This checks the latter
        form.

        We specified a 3D component in the test input (sphere)
        so that it has a height and therefore a volume
        without requiring a parent.
        """
        cs = settings.Settings()
        design = blueprints.Blueprints.load(self._yamlString)
        # The following is needed to prep customisotopics
        # which is required during construction of a component
        design._resolveNuclides(cs)
        componentDesign = design.componentDesigns["freefuel"]
        topComponent = componentDesign.construct(design, {}, cs[CONF_INPUT_HEIGHTS_HOT])
        self.assertEqual(topComponent.getDimension("od", cold=True), 4.0)
        self.assertGreater(topComponent.getVolume(), 0.0)
        self.assertGreater(topComponent.getMass("U235"), 0.0)

    def test_componentGroupInput(self):
        """Make sure component groups can be input in blueprints."""
        design = blueprints.Blueprints.load(self._yamlString)
        componentGroup = design.componentGroups["group1"]
        self.assertEqual(componentGroup["freefuel"].name, "freefuel")
        self.assertEqual(componentGroup["freefuel"].mult, 1.0)
