"""
Tests for generic global flux interface.
"""
import unittest

import numpy

from armi import settings
from armi.reactor import reactors

from armi.physics.neutronics.globalFlux import globalFluxInterface as gi
from armi.reactor.tests import test_reactors
from armi.tests import ISOAA_PATH
from armi.nuclearDataIO import isotxs


class MockParams:
    pass


class MockCore:
    def __init__(self):
        self.geomType = "spiral"
        self.symmetry = "full"
        self.p = MockParams()


class MockReactor:
    def __init__(self):
        self.core = MockCore()
        self.o = None


class MockGlobalFluxInterface(gi.GlobalFluxInterface):
    """
    Add fake keff calc to a the general gf interface.
    
    This simulates a 1000 pcm keff increase over 1 step.
    """

    def interactBOC(self, cycle=None):
        gi.GlobalFluxInterface.interactBOC(self, cycle=cycle)
        self.r.core.p.keff = 1.00

    def interactEveryNode(self, cycle, node):
        gi.GlobalFluxInterface.interactEveryNode(self, cycle, node)
        self.r.core.p.keff = 1.01


class MockGlobalFluxWithExecuters(gi.GlobalFluxInterfaceUsingExecuters):
    def getExecuterCls(self):
        return MockGlobalFluxExecuter


class MockGlobalFluxExecuter(gi.GlobalFluxExecuter):
    def _readOutput(self):
        class MockOutputReader:
            def apply(self, r):
                r.core.p.keff += 0.01

        return MockOutputReader()


class TestGlobalFluxOptions(unittest.TestCase):
    def test_readFromSettings(self):
        cs = settings.Settings()
        opts = gi.GlobalFluxOptions("neutronics-run")
        opts.fromUserSettings(cs)
        self.assertFalse(opts.adjoint)

    def test_readFromReactors(self):
        reactor = MockReactor()
        opts = gi.GlobalFluxOptions("neutronics-run")
        opts.fromReactor(reactor)
        self.assertEqual(opts.geomType, "spiral")


class TestGlobalFluxInterface(unittest.TestCase):
    def test_interaction(self):
        """
        Ensure the basic interaction hooks work

        Check that a 1000 pcm rx swing is observed due to the mock.
        """
        cs = settings.Settings()
        o, r = test_reactors.loadTestReactor()
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


class TestGlobalFluxInterfaceWithExecuters(unittest.TestCase):
    """Tests for the default global flux execution."""

    def test_executerInteraction(self):
        cs = settings.Settings()
        _o, r = test_reactors.loadTestReactor()
        r.core.p.keff = 1.0
        gfi = MockGlobalFluxWithExecuters(r, cs)
        gfi.interactBOC()
        gfi.interactEveryNode(0, 0)
        r.p.timeNode += 1
        gfi.interactEveryNode(0, 1)
        gfi.interactEOC()
        self.assertAlmostEqual(r.core.p.rxSwing, (1.02 - 1.01) / 1.01 * 1e5)


class TestGlobalFluxResultMapper(unittest.TestCase):
    def test_mapper(self):
        MCC2_SETTINGS = {"xsKernel": "MC2v2"}  # compat with ISOAA test lib
        _o, r = test_reactors.loadTestReactor(customSettings=MCC2_SETTINGS)
        applyDummyFlux(r)
        r.core.lib = isotxs.readBinary(ISOAA_PATH)
        mapper = gi.GlobalFluxResultMapper()
        mapper.r = r
        mapper._renormalizeNeutronFluxByBlock(100)
        self.assertAlmostEqual(r.core.calcTotalParam("power", generationNum=2), 100)

        mapper._updateDerivedParams()
        self.assertGreater(r.core.p.maxPD, 0.0)
        self.assertGreater(r.core.p.maxFlux, 0.0)

        mapper.updateDpaRate()
        self.assertGreater(r.core.getFirstBlock().p.detailedDpaRate, 0)

        self.assertEqual(r.core.getFirstBlock().p.detailedDpa, 0)
        opts = gi.GlobalFluxOptions("test")
        dosemapper = gi.DoseResultsMapper(1000, opts)
        dosemapper.apply(r)
        self.assertGreater(r.core.getFirstBlock().p.detailedDpa, 0)


def applyDummyFlux(r, ng=33):
    """Set arbitrary flux distribution on reactor."""
    for b in r.core.getBlocks():
        b.p.power = 1.0
        b.p.mgFlux = numpy.arange(ng, dtype=numpy.float64)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
