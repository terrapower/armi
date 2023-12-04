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
"""Tests of the Parameters class."""
from distutils.spawn import find_executable
import copy
import unittest

from armi import context
from armi.reactor import composites
from armi.reactor import parameters

# determine if this is a parallel run, and MPI is installed
MPI_EXE = None
if find_executable("mpiexec.exe") is not None:
    MPI_EXE = "mpiexec.exe"
elif find_executable("mpiexec") is not None:
    MPI_EXE = "mpiexec"


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

    def test_writeSomeParamsToDB(self):
        """
        This tests the ability to specify which parameters should be
        written to the database. It assumes that the list returned by
        ParameterDefinitionCollection.toWriteToDB() is used to filter for which
        parameters to include in the database.

        .. test:: Restrict parameters from DB write.
            :id: T_ARMI_PARAM_DB
            :tests: R_ARMI_PARAM_DB
        """
        pDefs = parameters.ParameterDefinitionCollection()
        with pDefs.createBuilder() as pb:
            pb.defParam("write_me", "units", "description", "location", default=42)
            pb.defParam("and_me", "units", "description", "location", default=42)
            pb.defParam(
                "dont_write_me",
                "units",
                "description",
                "location",
                default=42,
                saveToDB=False,
            )
        db_params = pDefs.toWriteToDB(32)
        self.assertListEqual(["write_me", "and_me"], [p.name for p in db_params])

    def test_serializer_pack_unpack(self):
        """
        This tests the ability to add a serializer to a parameter instantiation line.
        It assumes that if this parameter is not None, that the pack and unpack methods
        will be called during storage to and reading from the database. See
        database3._writeParams for an example use of this functionality.

        .. test:: Custom parameter serializer
            :id: T_ARMI_PARAM_SERIALIZE
            :tests: R_ARMI_PARAM_SERIALIZE
        """

        class TestSerializer(parameters.Serializer):
            @staticmethod
            def pack(data):
                array = [d + 1 for d in data]
                return array

            @staticmethod
            def unpack(data):
                array = [d - 1 for d in data]
                return array

        param = parameters.Parameter(
            name="myparam",
            units="kg",
            description="a param",
            location=None,
            saveToDB=True,
            default=[1],
            setter=None,
            categories=None,
            serializer=TestSerializer(),
        )
        param.assigned = [1]

        packed = param.serializer.pack(param.assigned)
        unpacked = param.serializer.unpack(packed)

        self.assertEqual(packed, [2])
        self.assertEqual(unpacked, [1])

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
        """Test the Parameter setter() tooling, that signifies if a Parameter has been updated.

        .. test:: Tooling that allows a Parameter to signal it needs to be updated across processes.
            :id: T_ARMI_PARAM_PARALLEL0
            :tests: R_ARMI_PARAM_PARALLEL
        """

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
        """Test the Parameter setter/getter tooling, through the lifecycle of a Parameter being updated.

        .. test:: Tooling that allows a Parameter to signal it needs to be updated across processes.
            :id: T_ARMI_PARAM_PARALLEL1
            :tests: R_ARMI_PARAM_PARALLEL
        """

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
        self.assertNotIn("n", mock)
        self.assertIn("nPlus1", mock)

        # basic tests of __eq__ method
        mock2 = copy.deepcopy(mock)
        self.assertEqual(mock, mock)
        self.assertNotEqual(mock, mock2)

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

        # same name along a different branch from the base ParameterCollection should
        # be fine
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
        """Tests we prevent accidental creation of attributes."""
        self.assertEqual(
            set(["_hist", "_backup", "assigned", "_p_serialNum", "serialNum"]),
            set(parameters.ParameterCollection._slots),
        )

        class MockPC(parameters.ParameterCollection):
            pass

        pc = MockPC()
        with self.assertRaises(AssertionError):
            pc.whatever = 22

        # try again after using a ParameterBuilder
        class MockPC(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            # use of the ParameterBuilder creates an empty __slots__
            with pDefs.createBuilder() as pb:
                pb.defParam("p0", "units", "p0 description", "location")

        pc = MockPC()

        self.assertIn("_p_p0", MockPC._slots)
        # Make sure we aren't making any weird copies of anything
        self.assertEqual(pc._slots, MockPC._slots)
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
    """Helper method for MPI sync tests: mock up a Composite with a minimal param collections."""
    c = composites.Composite(name)
    c.p = MockSyncPC()
    return c


class SynchronizationTests(unittest.TestCase):
    """Some tests that must be run with mpirun instead of the standard unittest system."""

    def setUp(self):
        self.r = makeComp("reactor")
        self.r.core = makeComp("core")
        self.r.add(self.r.core)
        for ai in range(context.MPI_SIZE * 3):
            a = makeComp("assembly{}".format(ai))
            self.r.core.add(a)
            for bi in range(3):
                a.add(makeComp("block{}-{}".format(ai, bi)))

        self.comps = [self.r.core] + self.r.core.getChildren(deep=True)

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_noConflicts(self):
        """Make sure sync works across processes.

        .. test:: Synchronize a reactor's state across processes.
            :id: T_ARMI_CMP_MPI0
            :tests: R_ARMI_CMP_MPI
        """
        _syncCount = self.r.syncMpiState()

        for ci, comp in enumerate(self.comps):
            if ci % context.MPI_SIZE == context.MPI_RANK:
                comp.p.param1 = (context.MPI_RANK + 1) * 30.0
            else:
                self.assertNotEqual((context.MPI_RANK + 1) * 30.0, comp.p.param1)

        syncCount = self.r.syncMpiState()
        self.assertEqual(len(self.comps), syncCount)

        for ci, comp in enumerate(self.comps):
            self.assertEqual((ci % context.MPI_SIZE + 1) * 30.0, comp.p.param1)

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_withConflicts(self):
        """Test conflicts arise correctly if we force a conflict.

        .. test:: Raise errors when there are conflicts across processes.
            :id: T_ARMI_CMP_MPI1
            :tests: R_ARMI_CMP_MPI
        """
        self.r.core.p.param1 = (context.MPI_RANK + 1) * 99.0
        with self.assertRaises(ValueError):
            self.r.syncMpiState()

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_withConflictsButSameValue(self):
        """Test that conflicts are ignored if the values are the same.

        .. test:: Don't raise errors when multiple processes make the same changes.
            :id: T_ARMI_CMP_MPI2
            :tests: R_ARMI_CMP_MPI
        """
        self.r.core.p.param1 = (context.MPI_SIZE + 1) * 99.0
        self.r.syncMpiState()
        self.assertEqual((context.MPI_SIZE + 1) * 99.0, self.r.core.p.param1)

    @unittest.skipIf(context.MPI_SIZE <= 1 or MPI_EXE is None, "Parallel test only")
    def test_conflictsMaintainWithStateRetainer(self):
        """Test that the state retainer fails correctly when it should."""
        with self.r.retainState(parameters.inCategory("cat2")):
            for _, comp in enumerate(self.comps):
                comp.p.param2 = 99 * context.MPI_RANK

        with self.assertRaises(ValueError):
            self.r.syncMpiState()
