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

import unittest
import numpy
import h5py
import os

from armi.reactor.tests import test_reactors
from armi.tests import TEST_ROOT, ARMI_RUN_PATH

from armi.bookkeeping.db import database3 as database


class TestDatabase3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.o, cls.r = test_reactors.loadTestReactor(TEST_ROOT)

    def setUp(self):
        self.db = database.Database3(self._testMethodName + ".h5", "w")
        self.db.open()
        print(self.db._fullPath)
        self.stateRetainer = self.r.retainState().__enter__()

    def tearDown(self):
        self.db.close()
        self.stateRetainer.__exit__()

    def test_replaceNones(self):
        """
        This definitely needs some work.
        """
        data3 = numpy.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        data1 = numpy.array([1, 2, 3, 4, 5, 6, 7, 8])
        data1iNones = numpy.array([1, 2, None, 5, 6])
        data1fNones = numpy.array([None, 2.0, None, 5.0, 6.0])
        data2fNones = numpy.array([None, [[1.0, 2.0, 6.0], [2.0, 3.0, 4.0]]])
        data_jag = numpy.array([[[1, 2], [3, 4]], [[1, 2, 3], [4, 5, 6], [7, 8, 9]]])
        data_dict = numpy.array(
            [{"bar": 2, "baz": 3}, {"foo": 4, "baz": 6}, {"foo": 7, "bar": 8}]
        )
        # nones = numpy.where([d is None for d in data1])[0]
        # conv_d1 = database.replaceNonesWithNonsense(data1, None, nones)
        print("data3: ", database.packSpecialData(data3, ""))
        print("data_jag", database.packSpecialData(data_jag, ""))
        # print("data1", database.packSpecialData(data1, ""))
        print("data1iNones", database.packSpecialData(data1iNones, ""))
        print("data1fNones", database.packSpecialData(data1fNones, ""))
        print("data2fNones", database.packSpecialData(data2fNones, ""))
        print("dataDict", database.packSpecialData(data_dict, ""))

        packedData, attrs = database.packSpecialData(data_jag, "")
        roundTrip = database.unpackSpecialData(packedData, attrs, "")
        print("round-tripped jagged:", roundTrip)
        print("round-tripped dtype:", roundTrip.dtype)

        packedData, attrs = database.packSpecialData(data_dict, "")
        roundTrip = database.unpackSpecialData(packedData, attrs, "")
        print("round-tripped dict:", roundTrip)

    def test_splitDatabase(self):
        for cycle, node in ((cycle, node) for cycle in range(3) for node in range(3)):
            self.r.p.cycle = cycle
            self.r.p.timeNode = node
            # something that splitDatabase won't change, so that we can make sure that
            # the right data went to the right new groups/cycles
            self.r.p.cycleLength = cycle

            self.db.writeToDB(self.r)

        self.db.splitDatabase(
            [(c, n) for c in (1, 2) for n in range(3)], "-all-iterations"
        )

        # Closing to copy back from fast path
        self.db.close()

        with h5py.File("test_splitDatabase.h5", "r") as newDb:
            self.assertTrue(newDb["c00n00/Reactor/cycle"][()] == 0)
            self.assertTrue(newDb["c00n00/Reactor/cycleLength"][()] == 1)
            self.assertTrue("c02n00" not in newDb)
            self.assertTrue(newDb.attrs["databaseVersion"] == "3")


if __name__ == "__main__":
    import sys

    # sys.argv = ["", "TestDatabase3.test_splitDatabase"]
    unittest.main()
