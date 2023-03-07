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
"""Tests for generic global flux interface"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access,invalid-name,no-self-use,no-method-argument,import-outside-toplevel
import unittest

import numpy

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
from armi.reactor.tests import test_blocks
from armi.reactor.tests import test_reactors
from armi.tests import ISOAA_PATH


# pylint: disable=abstract-method
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


class MockGlobalFluxWithExecuters(
    globalFluxInterface.GlobalFluxInterfaceUsingExecuters
):
    def getExecuterCls(self):
        return MockGlobalFluxExecuter


class MockGlobalFluxWithExecutersNonUniform(MockGlobalFluxWithExecuters):
    def getExecuterOptions(self, label=None):
        """
        Return modified executerOptions
        """
        opts = globalFluxInterface.GlobalFluxInterfaceUsingExecuters.getExecuterOptions(
            self, label=label
        )
        opts.hasNonUniformAssems = True  # to increase test coverage
        return opts


class MockGlobalFluxExecuter(globalFluxInterface.GlobalFluxExecuter):
    """Tests for code that uses Executers, which rely on OutputReaders to update state."""

    def _readOutput(self):
        class MockOutputReader:
            def apply(self, r):  # pylint: disable=no-self-use
                r.core.p.keff += 0.01

            def getKeff(self):
                return 1.05

        return MockOutputReader()


class TestGlobalFluxOptions(unittest.TestCase):
    def test_readFromSettings(self):
        cs = settings.Settings()
        opts = globalFluxInterface.GlobalFluxOptions("neutronics-run")
        opts.fromUserSettings(cs)
        self.assertFalse(opts.adjoint)

    def test_readFromReactors(self):
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
    def test_interaction(self):
        """
        Ensure the basic interaction hooks work

        Check that a 1000 pcm rx swing is observed due to the mock.
        """
        cs = settings.Settings()
        _o, r = test_reactors.loadTestReactor()
        gfi = MockGlobalFluxInterface(r, cs)
        gfi.interactBOC()
        gfi.interactEveryNode(0, 0)
        gfi.interactEOC()
        self.assertAlmostEqual(r.core.p.rxSwing, 1000)

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
        cs = settings.Settings()
        _o, r = test_reactors.loadTestReactor()
        gfi = MockGlobalFluxInterface(r, cs)
        gfi._checkEnergyBalance()


class TestGlobalFluxInterfaceWithExecuters(unittest.TestCase):
    """Tests for the default global flux execution."""

    @classmethod
    def setUpClass(cls):
        cls.cs = settings.Settings()
        _o, cls.r = test_reactors.loadTestReactor()

    def setUp(self):
        self.r.core.p.keff = 1.0
        self.gfi = MockGlobalFluxWithExecuters(self.r, self.cs)

    def test_executerInteraction(self):
        gfi, r = self.gfi, self.r
        gfi.interactBOC()
        gfi.interactEveryNode(0, 0)
        r.p.timeNode += 1
        gfi.interactEveryNode(0, 1)
        gfi.interactEOC()
        self.assertAlmostEqual(r.core.p.rxSwing, (1.02 - 1.01) / 1.01 * 1e5)

    def test_calculateKeff(self):
        self.assertEqual(self.gfi.calculateKeff(), 1.05)  # set in mock

    def test_getExecuterCls(self):
        class0 = globalFluxInterface.GlobalFluxInterfaceUsingExecuters.getExecuterCls()
        self.assertEqual(class0, globalFluxInterface.GlobalFluxExecuter)

    def test_setTightCouplingDefaults(self):
        """assert that tight coupling defaults are only set if cs["tightCoupling"]=True"""
        self.assertIsNone(self.gfi.coupler)
        self._setTightCouplingTrue()
        self.assertEqual(self.gfi.coupler.parameter, "keff")
        self._setTightCouplingFalse()

    def test_getTightCouplingValue(self):
        """test getTightCouplingValue returns the correct value for keff and type for power"""
        self._setTightCouplingTrue()
        self.assertEqual(self.gfi.getTightCouplingValue(), 1.0)  # set in setUp
        self.gfi.coupler.parameter = "power"
        for a in self.r.core.getChildren():
            for b in a:
                b.p.power = 10.0
        self.assertIsInstance(self.gfi.getTightCouplingValue(), list)
        self._setTightCouplingFalse()

    def _setTightCouplingTrue(self):
        # pylint: disable=no-member,protected-access
        self.cs["tightCoupling"] = True
        self.gfi._setTightCouplingDefaults()

    def _setTightCouplingFalse(self):
        self.cs["tightCoupling"] = False


class TestGlobalFluxInterfaceWithExecutersNonUniform(unittest.TestCase):
    """Tests for global flux execution with non-uniform assemblies."""

    @classmethod
    def setUpClass(cls):
        cs = settings.Settings()
        _o, cls.r = test_reactors.loadTestReactor()
        cls.r.core.p.keff = 1.0
        cls.gfi = MockGlobalFluxWithExecutersNonUniform(cls.r, cs)

    def test_executerInteractionNonUniformAssems(self):
        gfi, r = self.gfi, self.r
        gfi.interactBOC()
        gfi.interactEveryNode(0, 0)
        r.p.timeNode += 1
        gfi.interactEveryNode(0, 1)
        gfi.interactEOC()
        self.assertAlmostEqual(r.core.p.rxSwing, (1.02 - 1.01) / 1.01 * 1e5)

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
        # Switch to MC2v2 setting to make sure the isotopic/elemental expansions are compatible
        # with actually doing some math using the ISOAA test microscopic library
        o, r = test_reactors.loadTestReactor(customSettings={CONF_XS_KERNEL: "MC2v2"})
        applyDummyFlux(r)
        r.core.lib = isotxs.readBinary(ISOAA_PATH)
        mapper = globalFluxInterface.GlobalFluxResultMapper()
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
        block.p.pointsEdgeDpa = numpy.array([0 for i in range(6)])
        block.p.pointsCornerDpa = numpy.array([0 for i in range(6)])
        block.p.pointsEdgeDpaRate = numpy.array([1.0e-5 for i in range(6)])
        block.p.pointsCornerDpaRate = numpy.array([1.0e-5 for i in range(6)])

        # Test DoseResultsMapper. Pass in full list of blocks to apply() in order
        # to exercise blockList option (does not change behavior, since this is what
        # apply() does anyway)
        opts = globalFluxInterface.GlobalFluxOptions("test")
        opts.fromUserSettings(o.cs)
        dosemapper = globalFluxInterface.DoseResultsMapper(1000, opts)
        dosemapper.apply(r, blockList=r.core.getBlocks())
        self.assertGreater(block.p.detailedDpa, 0)
        self.assertGreater(numpy.min(block.p.pointsCornerDpa), 0)
        self.assertGreater(numpy.min(block.p.pointsEdgeDpa), 0)

        mapper.clearFlux()
        self.assertEqual(len(block.p.mgFlux), 0)

    def test_getDpaXs(self):
        mapper = globalFluxInterface.GlobalFluxResultMapper()

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
        mapper = globalFluxInterface.GlobalFluxResultMapper()

        # test fuel block
        mapper.cs["burnupPeakingFactor"] = 0.0
        b = HexBlock("fuel", height=10.0)
        b.p.flux = 100.0
        b.p.fluxPeak = 250.0
        factor = mapper.getBurnupPeakingFactor(b)
        self.assertEqual(factor, 2.5)


class TestGlobalFluxUtils(unittest.TestCase):
    def test_calcReactionRates(self):
        """
        Test that the reaction rate code executes and sets a param > 0.0.

        .. warning: This does not validate the reaction rate calculation.
        """
        b = test_blocks.loadTestBlock()
        test_blocks.applyDummyData(b)
        self.assertAlmostEqual(b.p.rateAbs, 0.0)
        globalFluxInterface.calcReactionRates(b, 1.01, b.r.core.lib)
        self.assertGreater(b.p.rateAbs, 0.0)
        vfrac = b.getComponentAreaFrac(Flags.FUEL)
        self.assertEqual(b.p.fisDens, b.p.rateFis / vfrac)
        self.assertEqual(b.p.fisDensHom, b.p.rateFis)


def applyDummyFlux(r, ng=33):
    """Set arbitrary flux distribution on reactor."""
    for b in r.core.getBlocks():
        b.p.power = 1.0
        b.p.mgFlux = numpy.arange(ng, dtype=numpy.float64)


if __name__ == "__main__":
    unittest.main()
