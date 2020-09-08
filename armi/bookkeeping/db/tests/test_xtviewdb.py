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

"""Tests for HDF database."""
import os
import math
import unittest
import platform

import numpy


from armi.bookkeeping.db import xtviewDB
from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT, ARMI_RUN_PATH
from armi.reactor import parameters
from armi.reactor.flags import Flags
from armi import settings


class TestHDF(unittest.TestCase):
    def setUp(self):
        self.db = xtviewDB.XTViewDatabase(self._testMethodName + ".h5", "w")

    def tearDown(self):
        self.db.close()
        os.remove(self.db.name)

    def test_unicodeDoesntWork(self):
        """Proof that HDF doesn't work with unicode"""
        with self.assertRaises(TypeError):
            self.db._hdf_file.create_dataset(
                "banana", numpy.array([u"oklahoma", u"arkansas"])
            )

    def test_noneDoesntWork(self):
        """Proof that HDF doesn't work with None"""
        with self.assertRaises(TypeError):
            self.db._hdf_file.create_dataset("banana2", numpy.array([None, "potato"]))

    def test_nonesSiftingArrays(self):
        name = "basename"
        arrays = {
            "parameter_uno": numpy.array(
                [0, 1, None, 2, 3, None, 4, 5, None, None, 6, 7, None]
            ),
            "parameter_dos": numpy.array([0, 1, 2, 3, 4, 5, 6, 7]),
            "parameter_tres": numpy.array(
                ["apple", None, "banana", None, None, "1", "", "3"]
            ),
            "parameter_quatro": numpy.array(
                [0.2, float("inf"), None, 4332.2332, -float("inf"), None, numpy.NaN]
            ),
            "parameter_cinco": [None] * 5,
        }
        self.db._create_1d_datasets(name, arrays)
        if platform.system() == "Windows":
            # fun fact: Windows 64-bit long ints are 32-bits!
            self.assertEqual(
                self.db._hdf_file["basename/parameter_uno"].dtype, numpy.int32
            )
        else:
            self.assertEqual(
                self.db._hdf_file["basename/parameter_uno"].dtype, numpy.int64
            )
        self.assertEqual(
            self.db._hdf_file["basename/parameter_tres"].dtype, numpy.dtype("|S6")
        )

        self.assertEqual(
            self.db._hdf_file["basename/parameter_uno"].attrs[self.db._NONE_ATTR].dtype,
            numpy.bool,
        )
        with self.assertRaises(KeyError):
            self.db._hdf_file["basename/parameter_dos"].attrs[self.db._NONE_ATTR]

        for key, pre_array in arrays.items():
            post_array = self.db._get_1d_dataset("{}/{}".format(name, key))
            for pre, post in zip(pre_array, post_array):
                try:
                    self.assertEqual(pre, post)
                except AssertionError as original_err:
                    try:
                        self.assertTrue(numpy.isnan(pre))
                        self.assertTrue(numpy.isnan(post))
                    except TypeError:  # freaking numpy should just return False if it's not a NaN, not crash
                        raise original_err

    def test_jaggedPaddedArrays(self):
        name = "basename2"
        arrays = {
            "parameter_uno": [[1, 2], [3, 4, 7], [5, 6], [1], [4, 5, 6, 7, 8, 9]],
            "parameter_dos": [[1, 2], [3, 4], [5, 6]],
            "parameter_tres": [["apple", "banana"], ["peach", "plum"], ["apricot"]],
            "parameter_quatro": [
                numpy.array([1, 2]),
                None,
                numpy.array([5, 6]),
                numpy.array([1]),
                numpy.array([4, 5, 6, 7, 8, 9]),
            ],
            "parameter_cinco": [
                numpy.array([1, 2]),
                None,
                [5, 6],
                [],
                numpy.array([4, 5, 6, 7, 8, 9]),
            ],
            "parameter_seis": [None, None, [5, 6], [], [1]],
            "parameter_siete": numpy.array([None, None, [5, 6], [], [1]]),
        }
        # to ensure the original data isn't messed with
        pre_length = [len(v) for v in arrays["parameter_uno"]]

        self.db._create_1d_datasets(name, arrays)

        if platform.system() == "Windows":
            # see above: windows 64-bit long ints are 32-bits
            self.assertEqual(
                self.db._hdf_file["basename2/parameter_uno"].dtype, numpy.int32
            )
        else:
            self.assertEqual(
                self.db._hdf_file["basename2/parameter_uno"].dtype, numpy.int64
            )
        self.assertEqual(
            self.db._hdf_file["basename2/parameter_tres"].dtype, numpy.dtype("|S7")
        )

        self.assertEqual(
            self.db._hdf_file["basename2/parameter_uno"]
            .attrs[self.db._JAGGED_ATTR]
            .dtype,
            numpy.int,
        )
        with self.assertRaises(KeyError):
            self.db._hdf_file["basename2/parameter_dos"].attrs[self.db._JAGGED_ATTR]

        for key, pre_array in arrays.items():
            post_array = self.db._get_1d_dataset("{}/{}".format(name, key))
            for pre, post in zip(pre_array, post_array):
                if pre is None and post is None:
                    continue
                self.assertEqual(len(pre), len(post))
                for pre_v, post_v in zip(pre, post):
                    self.assertEqual(pre_v, post_v)

        # did the original data get manipulated?
        post_length = [len(v) for v in arrays["parameter_uno"]]
        self.assertEqual(pre_length, post_length)

    def test_doesNotWriteObjectTypes(self):
        with self.assertRaises(
            (ValueError, TypeError)
        ):  # ValueError from TypeError: Object dtype dtype('O') has no native HDF5 equivalent
            self.db._create_1d_datasets(
                "hello",
                {
                    "BADDYBAD2": [
                        [5, 6],
                        ["apple", "banana", "jaguar"],
                        [],
                        [4, None, 6, 7, 8, 9],
                    ]
                },
            )

    def test_writeInputs(self):
        cs = settings.Settings(ARMI_RUN_PATH)
        self.db.writeInputsToDB(cs)

        with open(cs.path, "r") as fileStream:
            self.assertEqual(
                fileStream.read(), self.db._hdf_file["inputs/settings"][()]
            )
            self.assertIn("inputs/geomFile", self.db._hdf_file)
            self.assertIn("inputs/blueprints", self.db._hdf_file)


class TestDB(unittest.TestCase):
    """Testing functionality that isn't specific to the nature of the DB being HDF

    Not put in the higher level test modules as HDF is supposedly the DB of the future and
    the base class is an abstract which would be a pain to test without just using a concrete, fast implementation

    Because this class uses a shared DB it is probably best to executing the entire class of tests
    instead of individuals. Though the tests ideally will be written to not rely on that.

    """

    @classmethod
    def setUpClass(cls):
        cls.o, cls.r = test_reactors.loadTestReactor(TEST_ROOT)

    def setUp(self):
        self.db = xtviewDB.XTViewDatabase(self._testMethodName + ".h5", "w")
        # because we are only using setUpClass, retain state (faster than fresh load?)
        self.stateRetainer = self.r.retainState().__enter__()

    def tearDown(self):
        self.db.close()
        os.remove(self.db.name)
        self.stateRetainer.__exit__()

    def test_writeStateToDB(self):
        self.db.writeToDB(self.r, 0)

    def test_quickFailOnBadTimestepLoad(self):
        bad_timesteps = [
            -1,
            math.pi,
            # the last TS should be num-1 so this will fail
            sum(1 for i in self.db.getAllTimesteps()),
            float("inf"),
        ]
        for ts in bad_timesteps:
            with self.assertRaises(ValueError):
                self.db.updateFromDB("This string doesn't matter", ts)

    @unittest.skip(
        "Not sure we even want this behavior. Adding it back in made "
        "database conversions terrible."
    )
    def test_updateFromDBResetsToDefault(self):
        """"
        Test writing and updating db.

        Make sure parameters that are at their default get reset if they aren't in the DB.
        """
        self.db.writeToDB(self.r)
        self.assertEqual(self.r.core.p.paramDefs["keff"].assigned, parameters.NEVER)

        fuelBlock = self.r.core.getFirstBlock(Flags.FUEL)
        fuel = fuelBlock.getComponent(Flags.FUEL)
        originalFuelNumDens = fuel.getNumberDensity("U235")
        originalFuelBlockNumDens = fuelBlock.getNumberDensity("U235")
        originalFuelTemp = fuel.temperatureInC
        originalFuelOD = fuel.getDimension("od")
        originalFuelBU = fuelBlock.p.percentBu

        self.r.core.p.keff = 1.05
        fuelBlock.p.percentBu += 5.0
        fuel.setNumberDensity("U235", originalFuelNumDens * 2)

        # fuel.temperatureInC *= 1.05
        # self.assertNotAlmostEqual(fuel.getDimension('od'), originalFuelOD)
        # self.o.cs['looseCoupling'] = True  # so temperature gets read from db
        self.db.updateFromDB(self.r, sum(1 for i in self.db.getAllTimesteps()) - 1)

        fuelBlockAfterDB = self.r.core.getFirstBlock(Flags.FUEL)
        fuelAfterDB = fuelBlockAfterDB.getComponent(Flags.FUEL)
        self.assertAlmostEqual(
            fuelBlockAfterDB.getNumberDensity("U235"), originalFuelBlockNumDens
        )
        self.assertIs(fuelAfterDB, fuel)
        self.assertEqual(self.r.core.p.keff, self.r.core.p.paramDefs["keff"].default)
        self.assertAlmostEqual(fuel.getNumberDensity("U235"), originalFuelNumDens)
        self.assertAlmostEqual(fuel.temperatureInC, originalFuelTemp)
        self.assertAlmostEqual(fuel.getDimension("od"), originalFuelOD)
        self.assertEqual(fuelBlock.p.percentBu, originalFuelBU)
        self.assertAlmostEqual(
            fuelBlock.getNumberDensity("U235"), originalFuelBlockNumDens
        )

    def test_readAPI(self):
        self.r.p.cycle = 0
        self.r.p.timeNode = 0
        self.db.writeToDB(self.r)
        data = self.db.readBlockParam("enrichmentBOL", 0)
        self.assertTrue(data is not None)

        data = self.db.readBlockParam("spaghetti carbonara", 0)
        self.assertTrue(data is None)


if __name__ == "__main__":
    # import sys; sys.argv = ['', 'TestDB.test_updateFromDBResetsToDefault']
    unittest.main()
