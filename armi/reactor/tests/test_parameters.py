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
""" tests of the Parameters class """
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access
import copy
import traceback
import unittest

from armi import context
from armi.reactor import parameters
from armi.reactor import composites


class MockComposite:
    def __init__(self, name):
        self.name = name
        self.p = {}


class MockCompositeGrandParent(MockComposite):
    pass


class MockCompositeParent(MockCompositeGrandParent):
    pass


class MockCompositeChild(MockCompositeParent):
    pass


class ParameterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs = parameters.ALL_DEFINITIONS._paramDefs

    @classmethod
    def tearDownClass(cls):
        parameters.ALL_DEFINITIONS._paramDefs = cls.defs

    def setUp(self):
        parameters.ALL_DEFINITIONS._paramDefs = []

    def test_mutableDefaultsNotSupported(self):
        class Mock(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                with self.assertRaises(AssertionError):
                    pb.defParam("units", "description", "location", default=[])
                with self.assertRaises(AssertionError):
                    pb.defParam("units", "description", "location", default={})

            with self.assertRaises(AssertionError):
                fail = pDefs.createBuilder(default=[])

            with self.assertRaises(AssertionError):
                fail = pDefs.createBuilder(default={})

    def test_paramPropertyDoesNotConflict(self):
        class Mock(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam("doodle", "units", "description", "location", default=42)

            with pDefs.createBuilder(MockComposite, default=0.0) as pb:
                pb.defParam("cheese", "kg", "pressed curds of milk", "avg")
                pb.defParam("fudge", "kg", "saturated chocolate", "avg", default=19)
                pb.defParam(
                    "noodles",
                    "kg",
                    "strip, ring, or tube of pasta",
                    "avg",
                    default=None,
                )

        mock1 = Mock()
        mock2 = Mock()
        self.assertEqual(42, mock1.doodle)
        self.assertEqual(42, mock2.doodle)
        self.assertEqual(0.0, mock1.cheese)  # make sure factory default is applied
        self.assertEqual(
            19, mock2.fudge
        )  # make sure we can override the factory default
        self.assertEqual(
            None, mock2.noodles
        )  # make sure we can override the factory default
        mock1.doodle = 17
        self.assertEqual(17, mock1.doodle)
        self.assertEqual(42, mock2.doodle)

    def test_paramPropertyDoesNotConflictWithNoneDefault(self):
        class Mock(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam(
                    "noneDefault", "units", "description", "location", default=None
                )

        mock1 = Mock()
        mock2 = Mock()
        self.assertIsNone(mock1.noneDefault)
        self.assertIsNone(mock2.noneDefault)
        mock1.noneDefault = 1.234
        self.assertEqual(1.234, mock1.noneDefault)
        self.assertEqual(None, mock2.noneDefault)

    def test_getWithoutDefaultRaisesParameterError(self):
        class Mock(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam("noDefault", "units", "description", "location")

        mock = Mock()
        with self.assertRaises(parameters.ParameterError):
            print(mock.noDefault)

    def test_attemptingToSetParamWithoutSetterFails(self):
        class Mock(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam(
                    "noSetter",
                    "noSetter",
                    "units",
                    "description",
                    "location",
                    default="encapsulated",
                    setter=None,
                )

        mock = Mock()
        self.assertEqual("encapsulated", mock.noSetter)
        with self.assertRaises(parameters.ParameterError):
            mock.noSetter = False
        self.assertEqual("encapsulated", mock.noSetter)

    def test_setter(self):
        class Mock(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:

                def n(self, value):
                    self._p_n = value
                    self._p_nPlus1 = value + 1

                pb.defParam("n", "units", "description", "location", setter=n)

                def nPlus1(self, value):
                    self._p_nPlus1 = value
                    self._p_n = value - 1

                pb.defParam("nPlus1", "units", "description", "location", setter=nPlus1)

        mock = Mock()
        self.assertTrue(
            all(
                pd.assigned == parameters.NEVER
                for pd in mock.paramDefs
                if pd.name != "serialNum"
            )
        )
        with self.assertRaises(parameters.ParameterError):
            print(mock.n)
        with self.assertRaises(parameters.ParameterError):
            print(mock.nPlus1)
        mock.n = 15
        self.assertEqual(15, mock.n)
        self.assertEqual(16, mock.nPlus1)

        mock.nPlus1 = 22
        self.assertEqual(21, mock.n)
        self.assertEqual(22, mock.nPlus1)
        self.assertTrue(all(pd.assigned for pd in mock.paramDefs))

    def test_setterGetterBasics(self):
        class Mock(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:

                def n(self, value):
                    self._p_n = value
                    self._p_nPlus1 = value + 1

                pb.defParam("n", "units", "description", "location", setter=n)

                def nPlus1(self, value):
                    self._p_nPlus1 = value
                    self._p_n = value - 1

                pb.defParam("nPlus1", "units", "description", "location", setter=nPlus1)

        mock = Mock()
        mock.n = 15
        mock.nPlus1 = 22

        # basic tests of setters and getters
        self.assertEqual(mock["n"], 21)
        self.assertEqual(mock["nPlus1"], 22)
        with self.assertRaises(parameters.exceptions.UnknownParameterError):
            _ = mock["fake"]
        with self.assertRaises(KeyError):
            _ = mock[123]

        # basic test of __delitem__ method
        del mock["n"]
        with self.assertRaises(parameters.exceptions.UnknownParameterError):
            _ = mock["n"]

        # basic tests of __in__ method
        self.assertFalse("n" in mock)
        self.assertTrue("nPlus1" in mock)

        # basic tests of __eq__ method
        mock2 = copy.deepcopy(mock)
        self.assertTrue(mock == mock)
        self.assertFalse(mock == mock2)

        # basic tests of get() method
        self.assertEqual(mock.get("nPlus1"), 22)
        self.assertIsNone(mock.get("fake"))
        self.assertEqual(mock.get("fake", default=333), 333)

        # basic test of values() method
        vals = mock.values()
        self.assertEqual(len(vals), 2)
        self.assertEqual(vals[0], 22)

        # basic test of update() method
        mock.update({"nPlus1": 100})
        self.assertEqual(mock.get("nPlus1"), 100)

        # basic test of getSyncData() method
        data = mock.getSyncData()
        self.assertEqual(data["n"], 99)
        self.assertEqual(data["nPlus1"], 100)

    def test_cannotDefineParameterWithSameName(self):
        with self.assertRaises(parameters.ParameterDefinitionError):

            class MockParamCollection(parameters.ParameterCollection):
                pDefs = parameters.ParameterDefinitionCollection()
                with pDefs.createBuilder() as pb:
                    pb.defParam("sameName", "units", "description 1", "location")
                    pb.defParam("sameName", "units", "description 2", "location")

            _ = MockParamCollection()

    def test_paramDefinitionsCompose(self):
        class MockBaseParamCollection(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam("base1", "units", "a param on the base collection", "avg")
                pb.defParam(
                    "base2", "units", "another param on the base collection", "avg"
                )

        class MockDerivedACollection(MockBaseParamCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam("derAp1", "units", "derived a p 1", "centroid")
                pb.defParam("derAp2", "units", "derived a p 2", "centroid")

        class MockDerivedBCollection(MockDerivedACollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam("derBp", "units", "derived b param", "centroid")

        base = MockBaseParamCollection()
        derA = MockDerivedACollection()
        derB = MockDerivedBCollection()

        self.assertTrue(
            set(base.paramDefs._paramDefs).issubset(set(derA.paramDefs._paramDefs))
        )
        self.assertTrue(
            set(base.paramDefs._paramDefs).issubset(set(derB.paramDefs._paramDefs))
        )
        self.assertTrue(
            set(derA.paramDefs._paramDefs).issubset(set(derB.paramDefs._paramDefs))
        )

    def test_cannotDefineParameterWithSameNameForCollectionSubclass(self):
        class MockPCParent(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam("sameName", "units", "description 3", "location")

        with self.assertRaises(parameters.ParameterDefinitionError):

            class MockPCChild(MockPCParent):
                pDefs = parameters.ParameterDefinitionCollection()
                with pDefs.createBuilder() as pb:
                    pb.defParam("sameName", "units", "description 4", "location")

            _ = MockPCChild()

        # same name along a different branch from the base ParameterCollection should be fine
        class MockPCUncle(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam("sameName", "units", "description 5", "location")

    def test_cannotCreateAttrbuteOnParameterCollectionSubclass(self):
        class MockPC(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam("someParam", "units", "description", "location")

        _ = MockPC()

    def test_cannotCreateInstanceOf_NoDefault(self):
        with self.assertRaises(NotImplementedError):
            _ = parameters.NoDefault()

    def test_cannotCreateInstanceOf_Undefined(self):
        with self.assertRaises(NotImplementedError):
            _ = parameters.parameterDefinitions._Undefined()

    def test_defaultLocation(self):
        class MockPC(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder(location=parameters.ParamLocation.AVERAGE) as pb:
                pb.defParam("p1", "units", "p1 description")
                pb.defParam(
                    "p2", "units", "p2 description", parameters.ParamLocation.TOP
                )

        pc = MockPC()
        self.assertEqual(pc.paramDefs["p1"].location, parameters.ParamLocation.AVERAGE)
        self.assertEqual(pc.paramDefs["p2"].location, parameters.ParamLocation.TOP)

    def test_categories(self):
        class MockPC0(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam("p0", "units", "p0 description", "location")

        pc = MockPC0()
        self.assertEqual(pc.paramDefs.categories, set())

        class MockPC(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder(categories=["awesome", "stuff"]) as pb:
                pb.defParam("p1", "units", "p1 description", "location")
                pb.defParam(
                    "p2", "units", "p2 description", "location", categories=["bacon"]
                )

            with pDefs.createBuilder() as pb:
                pb.defParam(
                    "p3", "units", "p3 description", "location", categories=["bacon"]
                )

        pc = MockPC()
        self.assertEqual(pc.paramDefs.categories, set(["awesome", "stuff", "bacon"]))

        p1 = pc.paramDefs["p1"]
        p2 = pc.paramDefs["p2"]
        p3 = pc.paramDefs["p3"]
        self.assertEqual(p1.categories, set(["awesome", "stuff"]))
        self.assertEqual(p2.categories, set(["awesome", "stuff", "bacon"]))
        self.assertEqual(p3.categories, set(["bacon"]))

        self.assertEqual(set(pc.paramDefs.inCategory("awesome")), set([p1, p2]))
        self.assertEqual(set(pc.paramDefs.inCategory("stuff")), set([p1, p2]))
        self.assertEqual(set(pc.paramDefs.inCategory("bacon")), set([p2, p3]))

    def test_parameterCollectionsHave__slots__(self):
        """Make sure something is implemented to prevent accidental creation of attributes"""
        self.assertEqual(
            set(["_hist", "_backup", "assigned", "_p_serialNum", "serialNum"]),
            set(parameters.ParameterCollection._slots),
        )

        class MockPC(parameters.ParameterCollection):
            pass

        pc = MockPC()
        # No longer protecting against __dict__ access. If someone REALLY wants to
        # staple something to a parameter collection with no guarantees of anything,
        # that's on them
        # with self.assertRaises(AttributeError):
        #     pc.__dict__["foo"] = 5

        with self.assertRaises(AssertionError):
            pc.whatever = 22

        # try again after using a ParameterBuilder
        class MockPC(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            # use of the ParameterBuilder creates an empty __slots__
            with pDefs.createBuilder() as pb:
                pb.defParam("p0", "units", "p0 description", "location")

        pc = MockPC()

        self.assertTrue("_p_p0" in MockPC._slots)
        # Make sure we aren't making any weird copies of anything
        self.assertTrue(pc._slots is MockPC._slots)
        with self.assertRaises(AssertionError):
            pc.whatever = 33

        self.assertEqual(["serialNum"], pc.keys())
        pc.p0 = "hi"
        self.assertEqual({"p0", "serialNum"}, set(pc.keys()))

        # Also make sure that subclasses of ParameterCollection subclasses use __slots__
        class MockPCChild(MockPC):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam("p2", "foo", "bar")

        pcc = MockPCChild()
        with self.assertRaises(AssertionError):
            pcc.whatever = 33


class MockSyncPC(parameters.ParameterCollection):
    pDefs = parameters.ParameterDefinitionCollection()
    with pDefs.createBuilder(
        default=0.0, location=parameters.ParamLocation.AVERAGE
    ) as pb:
        pb.defParam("param1", "units", "p1 description", categories=["cat1"])
        pb.defParam("param2", "units", "p2 description", categories=["cat2"])
        pb.defParam("param3", "units", "p3 description", categories=["cat3"])


def makeComp(name):
    c = composites.Composite(name)
    c.p = MockSyncPC()
    return c


class SynchronizationTests:
    """Some unit tests that must be run with mpirun instead of the standard unittest system."""

    def setUp(self):
        self.r = makeComp("reactor")
        self.r.core = makeComp("core")
        self.r.add(self.r.core)
        for ai in range(context.MPI_SIZE * 4):
            a = makeComp("assembly{}".format(ai))
            self.r.core.add(a)
            for bi in range(10):
                a.add(makeComp("block{}-{}".format(ai, bi)))
        self.comps = [self.r.core] + self.r.core.getChildren(deep=True)
        for pd in MockSyncPC().paramDefs:
            pd.assigned = parameters.NEVER

    def tearDown(self):
        del self.r

    def run(self, testNamePrefix="mpitest_"):
        with open("mpitest{}.temp".format(context.MPI_RANK), "w") as self.l:
            for methodName in sorted(dir(self)):
                if methodName.startswith(testNamePrefix):
                    self.write("{}.{}".format(self.__class__.__name__, methodName))
                    try:
                        self.setUp()
                        getattr(self, methodName)()
                    except Exception:
                        self.write("failed, big time")
                        traceback.print_exc(file=self.l)
                        self.write("*** printed exception")
                        try:
                            self.tearDown()
                        except:
                            pass
            self.l.write("done.")

    def write(self, msg):
        self.l.write("{}\n".format(msg))
        self.l.flush()

    def assertRaises(self, exceptionType):
        class ExceptionCatcher:
            def __enter__(self):
                pass

            def __exit__(self, exc_type, exc_value, traceback):
                if exc_type is exceptionType:
                    return True
                raise AssertionError(
                    "Expected {}, but got {}".format(exceptionType, exc_type)
                )

        return ExceptionCatcher()

    def assertEqual(self, expected, actual):
        if expected != actual:
            raise AssertionError(
                "(expected) {} != {} (actual)".format(expected, actual)
            )

    def assertNotEqual(self, expected, actual):
        if expected == actual:
            raise AssertionError(
                "(expected) {} == {} (actual)".format(expected, actual)
            )

    def mpitest_noConflicts(self):
        for ci, comp in enumerate(self.comps):
            if ci % context.MPI_SIZE == context.MPI_RANK:
                comp.p.param1 = (context.MPI_RANK + 1) * 30.0
            else:
                self.assertNotEqual((context.MPI_RANK + 1) * 30.0, comp.p.param1)

        self.assertEqual(len(self.comps), self.r.syncMpiState())

        for ci, comp in enumerate(self.comps):
            self.assertEqual((ci % context.MPI_SIZE + 1) * 30.0, comp.p.param1)

    def mpitest_noConflicts_setByString(self):
        """Make sure params set by string also work with sync."""
        for ci, comp in enumerate(self.comps):
            if ci % context.MPI_SIZE == context.MPI_RANK:
                comp.p.param2 = (context.MPI_RANK + 1) * 30.0
            else:
                self.assertNotEqual((context.MPI_RANK + 1) * 30.0, comp.p.param2)

        self.assertEqual(len(self.comps), self.r.syncMpiState())

        for ci, comp in enumerate(self.comps):
            self.assertEqual((ci % context.MPI_SIZE + 1) * 30.0, comp.p.param2)

    def mpitest_withConflicts(self):
        self.r.core.p.param1 = (context.MPI_RANK + 1) * 99.0
        with self.assertRaises(ValueError):
            self.r.syncMpiState()

    def mpitest_withConflictsButSameValue(self):
        self.r.core.p.param1 = (context.MPI_SIZE + 1) * 99.0
        self.r.syncMpiState()
        self.assertEqual((context.MPI_SIZE + 1) * 99.0, self.r.core.p.param1)

    def mpitest_noConflictsMaintainWithStateRetainer(self):
        assigned = []
        with self.r.retainState(parameters.inCategory("cat1")):
            for ci, comp in enumerate(self.comps):
                comp.p.param2 = 99 * ci
                if ci % context.MPI_SIZE == context.MPI_RANK:
                    comp.p.param1 = (context.MPI_RANK + 1) * 30.0
                    assigned.append(parameters.SINCE_ANYTHING)
                else:
                    self.assertNotEqual((context.MPI_RANK + 1) * 30.0, comp.p.param1)
                    assigned.append(parameters.NEVER)

            # 1st inside state retainer
            self.assertEqual(
                True, all(c.p.assigned == parameters.SINCE_ANYTHING for c in self.comps)
            )

        # confirm outside state retainer
        self.assertEqual(assigned, [c.p.assigned for ci, c in enumerate(self.comps)])

        # this rank's "assigned" components are not assigned on the workers, and so will be updated
        self.assertEqual(len(self.comps), self.r.syncMpiState())

        for ci, comp in enumerate(self.comps):
            self.assertEqual((ci % context.MPI_SIZE + 1) * 30.0, comp.p.param1)

    def mpitest_conflictsMaintainWithStateRetainer(self):
        with self.r.retainState(parameters.inCategory("cat2")):
            for _, comp in enumerate(self.comps):
                comp.p.param2 = 99 * context.MPI_RANK

        with self.assertRaises(ValueError):
            self.r.syncMpiState()

    def mpitest_rxCoeffsProcess(self):
        """This test mimics the process for rxCoeffs when doing distributed doppler"""

        def do():
            # we will do this over 4 passes (there are 4 * MPI_SIZE assemblies)
            for passNum in range(4):
                with self.r.retainState(parameters.inCategory("cat2")):
                    self.r.p.param3 = "hi"
                    for c in self.comps:
                        c.p.param1 = (
                            99 * context.MPI_RANK
                        )  # this will get reset after state retainer
                    a = self.r.core[passNum * context.MPI_SIZE + context.MPI_RANK]
                    a.p.param2 = context.MPI_RANK * 20.0
                    for b in a:
                        b.p.param2 = context.MPI_RANK * 10.0

                    for ai, a2 in enumerate(self.r):
                        if ai % context.MPI_SIZE != context.MPI_RANK:
                            assert "param2" not in a2.p

                    self.assertEqual(parameters.SINCE_ANYTHING, param1.assigned)
                    self.assertEqual(parameters.SINCE_ANYTHING, param2.assigned)
                    self.assertEqual(parameters.SINCE_ANYTHING, param3.assigned)
                    self.assertEqual(parameters.SINCE_ANYTHING, a.p.assigned)

                    self.r.syncMpiState()

                    self.assertEqual(
                        parameters.SINCE_ANYTHING
                        & ~parameters.SINCE_LAST_DISTRIBUTE_STATE,
                        param1.assigned,
                    )
                    self.assertEqual(
                        parameters.SINCE_ANYTHING
                        & ~parameters.SINCE_LAST_DISTRIBUTE_STATE,
                        param2.assigned,
                    )
                    self.assertEqual(
                        parameters.SINCE_ANYTHING
                        & ~parameters.SINCE_LAST_DISTRIBUTE_STATE,
                        param3.assigned,
                    )
                    self.assertEqual(
                        parameters.SINCE_ANYTHING
                        & ~parameters.SINCE_LAST_DISTRIBUTE_STATE,
                        a.p.assigned,
                    )

                self.assertEqual(parameters.NEVER, param1.assigned)
                self.assertEqual(parameters.SINCE_ANYTHING, param2.assigned)
                self.assertEqual(parameters.NEVER, param3.assigned)
                self.assertEqual(parameters.SINCE_ANYTHING, a.p.assigned)
                do_assert(passNum)

        param1 = self.r.p.paramDefs["param1"]
        param2 = self.r.p.paramDefs["param2"]
        param3 = self.r.p.paramDefs["param3"]

        def do_assert(passNum):
            # ensure all assemblies and blocks set values for param2, but param1 is empty
            for rank in range(context.MPI_SIZE):
                a = self.r.core[passNum * context.MPI_SIZE + rank]
                assert "param1" not in a.p
                assert "param3" not in a.p
                self.assertEqual(rank * 20, a.p.param2)
                for b in a:
                    self.assertEqual(rank * 10, b.p.param2)
                    assert "param1" not in b.p
                    assert "param3" not in b.p

        if context.MPI_RANK == 0:
            with self.r.retainState(parameters.inCategory("cat2")):
                context.MPI_COMM.bcast(self.r)
                do()
                [do_assert(passNum) for passNum in range(4)]
            [do_assert(passNum) for passNum in range(4)]
        else:
            del self.r
            self.r = context.MPI_COMM.bcast(None)
            do()


if __name__ == "__main__":
    if context.MPI_SIZE == 1:
        unittest.main()
    else:
        SynchronizationTests().run()
