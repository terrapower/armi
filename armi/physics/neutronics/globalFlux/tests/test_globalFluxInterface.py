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
"""
Tests for generic global flux interface.
"""
import unittest

import numpy

from armi import settings

from armi.physics.neutronics.globalFlux import globalFluxInterface
from armi.reactor.tests import test_reactors
from armi.reactor.tests import test_blocks
from armi.reactor import geometry
from armi.tests import ISOAA_PATH
from armi.nuclearDataIO.cccc import isotxs

# pylint: disable=missing-class-docstring
# pylint: disable=abstract-method
# pylint: disable=protected-access
class MockParams:
    pass


class MockCore:
    def __init__(self):
        # just pick a random geomType
        self.geomType = geometry.GeomType.CARTESIAN
        self.symmetry = "full"
        self.p = MockParams()


class MockReactor:
    def __init__(self):
        self.core = MockCore()
        self.o = None


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


class TestGlobalFluxInterfaceWithExecuters(unittest.TestCase):
    """Tests for the default global flux execution."""

    @classmethod
    def setUpClass(cls):
        cs = settings.Settings()
        _o, cls.r = test_reactors.loadTestReactor()
        cls.r.core.p.keff = 1.0
        cls.gfi = MockGlobalFluxWithExecuters(cls.r, cs)

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
        _o, r = test_reactors.loadTestReactor(customSettings={"xsKernel": "MC2v2"})
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

        # Test DoseResultsMapper. Pass in full list of blocks to apply() in order
        # to exercise blockList option (does not change behavior, since this is what
        # apply() does anyway)
        opts = globalFluxInterface.GlobalFluxOptions("test")
        dosemapper = globalFluxInterface.DoseResultsMapper(1000, opts)
        dosemapper.apply(r, blockList=r.core.getBlocks())
        self.assertGreater(block.p.detailedDpa, 0)

        mapper.clearFlux()
        self.assertTrue(len(block.p.mgFlux) == 0)


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


def applyDummyFlux(r, ng=33):
    """Set arbitrary flux distribution on reactor."""
    for b in r.core.getBlocks():
        b.p.power = 1.0
        b.p.mgFlux = numpy.arange(ng, dtype=numpy.float64)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
