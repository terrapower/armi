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
"""Tests for generic global flux interface."""

import unittest
from unittest.mock import patch

import numpy as np

from armi import settings
from armi.nuclearDataIO.cccc import isotxs
from armi.physics.neutronics.globalFlux import globalFluxInterface
from armi.physics.neutronics.settings import (
    CONF_GRID_PLATE_DPA_XS_SET,
    CONF_XS_KERNEL,
)
from armi.reactor import geometry
from armi.reactor.blocks import HexBlock
from armi.reactor.flags import Flags
from armi.reactor.tests import test_blocks, test_reactors
from armi.tests import ISOAA_PATH


class MockReactorParams:
    def __init__(self):
        self.cycle = 1
        self.timeNode = 2


class MockCoreParams:
    pass


class MockCore:
    def __init__(self):
        # just pick a random geomType
        self.geomType = geometry.GeomType.CARTESIAN
        self.symmetry = "full"
        self.p = MockCoreParams()


class MockReactor:
    def __init__(self):
        self.core = MockCore()
        self.o = None
        self.p = MockReactorParams()


class MockGlobalFluxInterface(globalFluxInterface.GlobalFluxInterface):
    """
    Add fake keff calc to a the general gf interface.

    This simulates a 1000 pcm keff increase over 1 step.
    """

    def interactBOC(self, cycle=None):
        globalFluxInterface.GlobalFluxInterface.interactBOC(self, cycle=cycle)
        self.r.core.p.keff = 1.00

    def interactEveryNode(self, cycle, node):
        globalFluxInterface.GlobalFluxInterface.interactEveryNode(self, cycle, node)
        self.r.core.p.keff = 1.01


class MockGlobalFluxWithExecuters(globalFluxInterface.GlobalFluxInterfaceUsingExecuters):
    def getExecuterCls(self):
        return MockGlobalFluxExecuter


class MockGlobalFluxWithExecutersNonUniform(MockGlobalFluxWithExecuters):
    def getExecuterOptions(self, label=None):
        """Return modified executerOptions."""
        opts = globalFluxInterface.GlobalFluxInterfaceUsingExecuters.getExecuterOptions(self, label=label)
        opts.hasNonUniformAssems = True  # to increase test coverage
        return opts


class MockGlobalFluxExecuter(globalFluxInterface.GlobalFluxExecuter):
    """Tests for code that uses Executers, which rely on OutputReaders to update state."""

    def _readOutput(self):
        class MockOutputReader:
            def apply(self, r):
                r.core.p.keff += 0.01

            def getKeff(self):
                return 1.05

        return MockOutputReader()


class TestGlobalFluxOptions(unittest.TestCase):
    """Tests for GlobalFluxOptions."""

    def test_readFromSettings(self):
        """Test reading global flux options from case settings.

        .. test:: Tests GlobalFluxOptions.
            :id: T_ARMI_FLUX_OPTIONS_CS
            :tests: R_ARMI_FLUX_OPTIONS
        """
        cs = settings.Settings()
        opts = globalFluxInterface.GlobalFluxOptions("neutronics-run")
        opts.fromUserSettings(cs)
        self.assertFalse(opts.adjoint)

    def test_readFromReactors(self):
        """Test reading global flux options from reactor objects.

        .. test:: Tests GlobalFluxOptions.
            :id: T_ARMI_FLUX_OPTIONS_R
            :tests: R_ARMI_FLUX_OPTIONS
        """
        reactor = MockReactor()
        opts = globalFluxInterface.GlobalFluxOptions("neutronics-run")
        opts.fromReactor(reactor)
        self.assertEqual(opts.geomType, geometry.GeomType.CARTESIAN)
        self.assertFalse(opts.savePhysicsFiles)

    def test_savePhysicsFiles(self):
        reactor = MockReactor()
        opts = globalFluxInterface.GlobalFluxOptions("neutronics-run")

        # savePhysicsFilesList matches MockReactor parameters
        opts.savePhysicsFilesList = ["001002"]
        opts.fromReactor(reactor)
        self.assertTrue(opts.savePhysicsFiles)

        # savePhysicsFilesList does not match MockReactor parameters
        opts.savePhysicsFilesList = ["001000"]
        opts.fromReactor(reactor)
        self.assertFalse(opts.savePhysicsFiles)


class TestGlobalFluxInterface(unittest.TestCase):
    def test_computeDpaRate(self):
        """
        Compute DPA and DPA rates from multi-group neutron flux and cross sections.

        .. test:: Compute DPA rates.
            :id: T_ARMI_FLUX_DPA
            :tests: R_ARMI_FLUX_DPA
        """
        xs = [1, 2, 3]
        flx = [0.5, 0.75, 2]
        res = globalFluxInterface.computeDpaRate(flx, xs)
        self.assertEqual(res, 10**-24 * (0.5 + 1.5 + 6))

    def test_interaction(self):
        """
        Ensure the basic interaction hooks work.

        Check that a 1000 pcm rx swing is observed due to the mock.
        """
        cs = settings.Settings()
        cs["burnSteps"] = 2
        _o, r = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        gfi = MockGlobalFluxInterface(r, cs)
        bocKeff = 1.1
        r.core.p.keffUnc = 1.1
        gfi.interactBOC()

        r.p.cycle, r.p.timeNode = 0, 0
        gfi.interactEveryNode(0, 0)
        self.assertAlmostEqual(gfi._bocKeff, r.core.p.keffUnc)
        r.core.p.keffUnc = 1.05
        r.p.cycle, r.p.timeNode = 0, 1
        gfi.interactEveryNode(0, 1)
        # doesn't change since its not the first node
        self.assertAlmostEqual(gfi._bocKeff, bocKeff)
        r.core.p.keffUnc = 1.01
        r.p.cycle, r.p.timeNode = 0, 2
        gfi.interactEveryNode(0, 2)
        self.assertAlmostEqual(gfi._bocKeff, bocKeff)
        self.assertAlmostEqual(r.core.p.rxSwing, -1e5 * (1.1 - 1.01) / (1.1 * 1.01))
        gfi.interactBOC(0)
        # now its zeroed at BOC
        self.assertAlmostEqual(r.core.p.rxSwing, 0)

    def test_getIOFileNames(self):
        cs = settings.Settings()
        gfi = MockGlobalFluxInterface(MockReactor(), cs)
        inf, _outf, _stdname = gfi.getIOFileNames(1, 2, 1)
        self.assertEqual(inf, "armi001_2_001.GlobalFlux.inp")

    def test_getHistoryParams(self):
        params = globalFluxInterface.GlobalFluxInterface.getHistoryParams()
        self.assertEqual(len(params), 3)
        self.assertIn("detailedDpa", params)

    def test_checkEnergyBalance(self):
        """Test energy balance check.

        .. test:: Block-wise power is consistent with reactor data model power.
            :id: T_ARMI_FLUX_CHECK_POWER
            :tests: R_ARMI_FLUX_CHECK_POWER
        """
        cs = settings.Settings()
        _o, r = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        gfi = MockGlobalFluxInterface(r, cs)
        self.assertEqual(gfi.checkEnergyBalance(), None)

        # Test when nameplate power doesn't equal sum of block power
        r.core.p.power = 1e-10
        with self.assertRaises(ValueError):
            gfi.checkEnergyBalance()


class TestGlobalFluxInterfaceWithExecuters(unittest.TestCase):
    """Tests for the default global flux execution."""

    @classmethod
    def setUpClass(cls):
        cls.cs = settings.Settings()
        cls.r = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")[1]

    def setUp(self):
        self.r.core.p.keff = 1.0
        self.gfi = MockGlobalFluxWithExecuters(self.r, self.cs)

    @patch("armi.physics.neutronics.globalFlux.globalFluxInterface.GlobalFluxExecuter._execute")
    @patch("armi.physics.neutronics.globalFlux.globalFluxInterface.GlobalFluxExecuter._performGeometryTransformations")
    def test_executerInteraction(self, mockGeometryTransform, mockExecute):
        """Run the global flux interface and executer though one time now.

        .. test:: Run the global flux interface to check that the mesh converter is called before the neutronics solver.
            :id: T_ARMI_FLUX_GEOM_TRANSFORM_ORDER
            :tests: R_ARMI_FLUX_GEOM_TRANSFORM
        """
        call_order = []
        mockGeometryTransform.side_effect = lambda *a, **kw: call_order.append(mockGeometryTransform)
        mockExecute.side_effect = lambda *a, **kw: call_order.append(mockExecute)
        gfi = self.gfi
        gfi.interactBOC()
        gfi.interactEveryNode(0, 0)
        self.assertEqual([mockGeometryTransform, mockExecute], call_order)

    def test_calculateKeff(self):
        self.assertEqual(self.gfi.calculateKeff(), 1.05)  # set in mock

    def test_getExecuterCls(self):
        class0 = globalFluxInterface.GlobalFluxInterfaceUsingExecuters.getExecuterCls()
        self.assertEqual(class0, globalFluxInterface.GlobalFluxExecuter)

    def test_setTightCouplingDefaults(self):
        """Assert that tight coupling defaults are only set if cs["tightCoupling"]=True."""
        self.assertIsNone(self.gfi.coupler)
        self._setTightCouplingTrue()
        self.assertEqual(self.gfi.coupler.parameter, "keff")
        self._setTightCouplingFalse()

    def test_getTightCouplingValue(self):
        """Test getTightCouplingValue returns the correct value for keff and type for power."""
        self._setTightCouplingTrue()
        self.assertEqual(self.gfi.getTightCouplingValue(), 1.0)  # set in setUp
        self.gfi.coupler.parameter = "power"
        for a in self.r.core:
            for b in a:
                b.p.power = 10.0
        self.assertEqual(
            self.gfi.getTightCouplingValue(),
            self._getCouplingPowerDistributions(self.r.core),
        )
        self._setTightCouplingFalse()

    @staticmethod
    def _getCouplingPowerDistributions(core):
        scaledPowers = []
        for a in core:
            assemblyPower = sum(b.p.power for b in a)
            scaledPowers.append([b.p.power / assemblyPower for b in a])

        return scaledPowers

    def _setTightCouplingTrue(self):
        self.cs["tightCoupling"] = True
        self.gfi._setTightCouplingDefaults()

    def _setTightCouplingFalse(self):
        self.cs["tightCoupling"] = False


class TestGlobalFluxInterfaceWithExecutersNonUniform(unittest.TestCase):
    """Tests for global flux execution with non-uniform assemblies."""

    @classmethod
    def setUpClass(cls):
        cs = settings.Settings()
        _o, cls.r = test_reactors.loadTestReactor(inputFileName="smallestTestReactor/armiRunSmallest.yaml")
        cls.r.core.p.keff = 1.0
        cls.gfi = MockGlobalFluxWithExecutersNonUniform(cls.r, cs)

    @patch("armi.reactor.converters.uniformMesh.converterFactory")
    def test_executerInteractionNonUniformAssems(self, mockConverterFactory):
        """Run the global flux interface with non-uniform assemblies.

        This will serve as a broad end-to-end test of the interface, and also
        stress test the mesh issues with non-uniform assemblies.

        .. test:: Run the global flux interface to show the geometry converter is called when the
            nonuniform mesh option is used.
            :id: T_ARMI_FLUX_GEOM_TRANSFORM_CONV
            :tests: R_ARMI_FLUX_GEOM_TRANSFORM
        """
        gfi = self.gfi
        gfi.interactBOC()
        gfi.interactEveryNode(0, 0)
        self.assertTrue(gfi.getExecuterOptions().hasNonUniformAssems)
        mockConverterFactory.assert_called()

    def test_calculateKeff(self):
        self.assertEqual(self.gfi.calculateKeff(), 1.05)  # set in mock

    def test_getExecuterCls(self):
        class0 = globalFluxInterface.GlobalFluxInterfaceUsingExecuters.getExecuterCls()
        self.assertEqual(class0, globalFluxInterface.GlobalFluxExecuter)


class TestGlobalFluxResultMapper(unittest.TestCase):
    """
    Test that global flux result mappings run.

    Notes
    -----
    This does not test that the flux mapping is correct. That has to be done
    at another level.
    """

    def test_mapper(self):
        # Switch to MC2v2 setting to make sure the isotopic/elemental expansions are compatible with
        # actually doing some math using the ISOAA test microscopic library
        o, r = test_reactors.loadTestReactor(
            customSettings={CONF_XS_KERNEL: "MC2v2"},
            inputFileName="smallestTestReactor/armiRunSmallest.yaml",
        )
        applyDummyFlux(r)
        r.core.lib = isotxs.readBinary(ISOAA_PATH)
        mapper = globalFluxInterface.GlobalFluxResultMapper(cs=o.cs)
        mapper.r = r
        mapper._renormalizeNeutronFluxByBlock(100)
        self.assertAlmostEqual(r.core.calcTotalParam("power", generationNum=2), 100)

        mapper._updateDerivedParams()
        self.assertGreater(r.core.p.maxPD, 0.0)
        self.assertGreater(r.core.p.maxFlux, 0.0)

        mapper.updateDpaRate()
        block = r.core.getFirstBlock()
        self.assertGreater(block.p.detailedDpaRate, 0)
        self.assertEqual(block.p.detailedDpa, 0)

        mapper.clearFlux()
        self.assertEqual(len(block.p.mgFlux), 0)

    def test_getDpaXs(self):
        cs = settings.Settings()
        mapper = globalFluxInterface.GlobalFluxResultMapper(cs=cs)

        # test fuel block
        b = HexBlock("fuel", height=10.0)
        vals = mapper.getDpaXs(b)
        self.assertEqual(len(vals), 33)
        self.assertAlmostEqual(vals[0], 2345.69, 1)

        # build a grid plate block
        b = HexBlock("grid_plate", height=10.0)
        b.p.flags = Flags.GRID_PLATE
        self.assertTrue(b.hasFlags(Flags.GRID_PLATE))

        # test grid plate block
        mapper.cs[CONF_GRID_PLATE_DPA_XS_SET] = "dpa_EBRII_PE16"
        vals = mapper.getDpaXs(b)
        self.assertEqual(len(vals), 33)
        self.assertAlmostEqual(vals[0], 2478.95, 1)

        # test null case
        mapper.cs[CONF_GRID_PLATE_DPA_XS_SET] = "fake"
        with self.assertRaises(KeyError):
            mapper.getDpaXs(b)

    def test_getBurnupPeakingFactor(self):
        cs = settings.Settings()
        mapper = globalFluxInterface.GlobalFluxResultMapper(cs=cs)

        # test fuel block
        mapper.cs["burnupPeakingFactor"] = 0.0
        b = HexBlock("fuel", height=10.0)
        b.p.flux = 100.0
        b.p.fluxPeak = 250.0
        factor = mapper.getBurnupPeakingFactor(b)
        self.assertEqual(factor, 2.5)

    def test_getBurnupPeakingFactorZero(self):
        cs = settings.Settings()
        mapper = globalFluxInterface.GlobalFluxResultMapper(cs=cs)

        # test fuel block without any peaking factor set
        b = HexBlock("fuel", height=10.0)
        factor = mapper.getBurnupPeakingFactor(b)
        self.assertEqual(factor, 0.0)


class TestGlobalFluxUtils(unittest.TestCase):
    def test_calcReactionRates(self):
        """
        Test that the reaction rate code executes and sets a param > 0.0.

        .. test:: Return the reaction rates for a given ArmiObject.
            :id: T_ARMI_FLUX_RX_RATES
            :tests: R_ARMI_FLUX_RX_RATES
        """
        b = test_blocks.loadTestBlock()
        test_blocks.applyDummyData(b)
        self.assertAlmostEqual(b.p.rateAbs, 0.0)
        globalFluxInterface.calcReactionRates(b, 1.01, b.core.lib)
        self.assertGreater(b.p.rateAbs, 0.0)
        vfrac = b.getComponentAreaFrac(Flags.FUEL)
        self.assertEqual(b.p.fisDens, b.p.rateFis / vfrac)
        self.assertEqual(b.p.fisDensHom, b.p.rateFis)


def applyDummyFlux(r, ng=33):
    """Set arbitrary flux distribution on a Reactor."""
    for b in r.core.iterBlocks():
        b.p.power = 1.0
        b.p.mgFlux = np.arange(ng, dtype=np.float64)
