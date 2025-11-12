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
"""Tests for assorted Parameters tools."""

import copy
import os
import unittest
from glob import glob
from shutil import copyfile

from armi.reactor import parameters
from armi.reactor.reactorParameters import makeParametersReadOnly
from armi.testing import loadTestReactor
from armi.tests import TEST_ROOT
from armi.utils.directoryChangers import TemporaryDirectoryChanger


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

        .. test:: Ensure that new parameters can be defined.
            :id: T_ARMI_PARAM0
            :tests: R_ARMI_PARAM
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
        database._writeParams for an example use of this functionality.

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
        self.assertEqual(19, mock2.fudge)  # make sure we can override the factory default
        self.assertEqual(None, mock2.noodles)  # make sure we can override the factory default
        mock1.doodle = 17
        self.assertEqual(17, mock1.doodle)
        self.assertEqual(42, mock2.doodle)

    def test_paramPropNoConflictNoneDefault(self):
        """Parameter property does not conflict with None default."""

        class Mock(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam("noneDefault", "units", "description", "location", default=None)

        mock1 = Mock()
        mock2 = Mock()
        self.assertIsNone(mock1.noneDefault)
        self.assertIsNone(mock2.noneDefault)
        mock1.noneDefault = 1.234
        self.assertEqual(1.234, mock1.noneDefault)
        self.assertEqual(None, mock2.noneDefault)

    def test_getNoDefaultRaisesError(self):
        """Get without default raises parameter error."""

        class Mock(parameters.ParameterCollection):
            pDefs = parameters.ParameterDefinitionCollection()
            with pDefs.createBuilder() as pb:
                pb.defParam("noDefault", "units", "description", "location")

        mock = Mock()
        with self.assertRaises(parameters.ParameterError):
            print(mock.noDefault)

    def test_setParamWithoutSetter(self):
        """Attempting to set paramter without setter fails."""

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
        self.assertTrue(all(pd.assigned == parameters.NEVER for pd in mock.paramDefs if pd.name != "serialNum"))
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
        self.assertTrue(all(pd.assigned != parameters.NEVER for pd in mock.paramDefs))

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

    def test_cannotDefineParamWithSameName(self):
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
                pb.defParam("base2", "units", "another param on the base collection", "avg")

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

        self.assertTrue(set(base.paramDefs._paramDefs).issubset(set(derA.paramDefs._paramDefs)))
        self.assertTrue(set(base.paramDefs._paramDefs).issubset(set(derB.paramDefs._paramDefs)))
        self.assertTrue(set(derA.paramDefs._paramDefs).issubset(set(derB.paramDefs._paramDefs)))

    def test_cannotDefineParamSameNameColSubclass(self):
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

    def test_cannotCreateAttrOnParamColSubclass(self):
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
                pb.defParam("p2", "units", "p2 description", parameters.ParamLocation.TOP)

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
                pb.defParam("p2", "units", "p2 description", "location", categories=["bacon"])

            with pDefs.createBuilder() as pb:
                pb.defParam("p3", "units", "p3 description", "location", categories=["bacon"])

        pc = MockPC()
        self.assertEqual(pc.paramDefs.categories, set(["awesome", "stuff", "bacon"]))

        p1 = pc.paramDefs["p1"]
        p2 = pc.paramDefs["p2"]
        p3 = pc.paramDefs["p3"]
        self.assertEqual(p1.categories, set(["awesome", "stuff"]))
        self.assertEqual(p2.categories, set(["awesome", "stuff", "bacon"]))
        self.assertEqual(p3.categories, set(["bacon"]))

        for p in [p1, p2, p3]:
            self._testCategoryConsistency(p)

        self.assertEqual(set(pc.paramDefs.inCategory("awesome")), set([p1, p2]))
        self.assertEqual(set(pc.paramDefs.inCategory("stuff")), set([p1, p2]))
        self.assertEqual(set(pc.paramDefs.inCategory("bacon")), set([p2, p3]))

    def _testCategoryConsistency(self, p: parameters.Parameter):
        for category in p.categories:
            self.assertTrue(p.hasCategory(category))
        self.assertFalse(p.hasCategory("this_shouldnot_exist"))

    def test_paramColHaveSlots(self):
        """Tests we prevent accidental creation of attributes."""
        self.assertEqual(
            set(
                [
                    "_hist",
                    "_backup",
                    "assigned",
                    "_p_serialNum",
                    "serialNum",
                    "readOnly",
                ]
            ),
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


class ParamCollectionWhere(unittest.TestCase):
    """Tests for ParameterCollection.where."""

    class ScopeParamCollection(parameters.ParameterCollection):
        pDefs = parameters.ParameterDefinitionCollection()
        with pDefs.createBuilder() as pb:
            pb.defParam(
                name="empty",
                description="Bare",
                location=None,
                categories=None,
                units="",
            )
            pb.defParam(
                name="keff",
                description="keff",
                location=parameters.ParamLocation.VOLUME_INTEGRATED,
                categories=[parameters.Category.neutronics],
                units="",
            )
            pb.defParam(
                name="cornerFlux",
                description="corner flux",
                location=parameters.ParamLocation.CORNERS,
                categories=[
                    parameters.Category.neutronics,
                ],
                units="",
            )
            pb.defParam(
                name="edgeTemperature",
                description="edge temperature",
                location=parameters.ParamLocation.EDGES,
                categories=[parameters.Category.thermalHydraulics],
                units="",
            )

    @classmethod
    def setUpClass(cls) -> None:
        """Define a couple useful parameters with categories, locations, etc."""
        cls.pc = cls.ScopeParamCollection()

    def test_onCategory(self):
        """Test the use of Parameter.hasCategory on filtering."""
        names = {"keff", "cornerFlux"}
        for p in self.pc.where(lambda pd: pd.hasCategory(parameters.Category.neutronics)):
            self.assertTrue(p.hasCategory(parameters.Category.neutronics), msg=p)
            names.remove(p.name)
        self.assertFalse(names, msg=f"{names=} should be empty!")

    def test_onLocation(self):
        """Test the use of Parameter.atLocation in filtering."""
        names = {"edgeTemperature"}
        for p in self.pc.where(lambda pd: pd.atLocation(parameters.ParamLocation.EDGES)):
            self.assertTrue(p.atLocation(parameters.ParamLocation.EDGES), msg=p)
            names.remove(p.name)
        self.assertFalse(names, msg=f"{names=} should be empty!")

    def test_complicated(self):
        """Test a multi-condition filter."""
        names = {"cornerFlux"}

        def check(p: parameters.Parameter) -> bool:
            return p.atLocation(parameters.ParamLocation.CORNERS) and p.hasCategory(parameters.Category.neutronics)

        for p in self.pc.where(check):
            self.assertTrue(check(p), msg=p)
            names.remove(p.name)
        self.assertFalse(names, msg=f"{names=} should be empty")


class TestMakeParametersReadOnly(unittest.TestCase):
    def test_makeParametersReadOnly(self):
        with TemporaryDirectoryChanger():
            # copy test reactor to local
            yamls = glob(os.path.join(TEST_ROOT, "smallestTestReactor", "*.yaml"))
            for yamlFile in yamls:
                copyfile(yamlFile, os.path.basename(yamlFile))

            # load some random test reactor
            _o, r = loadTestReactor(os.getcwd(), inputFileName="armiRunSmallest.yaml")

            # prove we can edit various params at will
            r.core.p.keff = 1.01
            b = r.core.getFirstBlock()
            b.p.power = 123.4

            makeParametersReadOnly(r)

            # now show we can no longer edit those parameters
            with self.assertRaises(RuntimeError):
                r.core.p.keff = 0.99

            with self.assertRaises(RuntimeError):
                b.p.power = 432.1
