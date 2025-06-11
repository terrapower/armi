# Copyright 2022 TerraPower, LLC
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
"""Tests for the db Layout and associated tools."""

import os
import unittest

from armi import context
from armi.bookkeeping.db import database, layout
from armi.reactor import grids
from armi.utils.directoryChangers import TemporaryDirectoryChanger


class TestLocationPacking(unittest.TestCase):
    """Tests for database location."""

    def setUp(self):
        self.td = TemporaryDirectoryChanger()
        self.td.__enter__()

    def tearDown(self):
        self.td.__exit__(None, None, None)

    def test_locationPacking(self):
        loc1 = grids.IndexLocation(1, 2, 3, None)
        loc2 = grids.CoordinateLocation(4.0, 5.0, 6.0, None)
        loc3 = grids.MultiIndexLocation(None)
        loc3.append(grids.IndexLocation(7, 8, 9, None))
        loc3.append(grids.IndexLocation(10, 11, 12, None))

        locs = [loc1, loc2, loc3]
        tp, data = layout._packLocations(locs)

        self.assertEqual(tp[0], layout.LOC_INDEX)
        self.assertEqual(tp[1], layout.LOC_COORD)
        self.assertEqual(tp[2], layout.LOC_MULTI + "2")

        unpackedData = layout._unpackLocations(tp, data)

        self.assertEqual(unpackedData[0], (1, 2, 3))
        self.assertEqual(unpackedData[1], (4.0, 5.0, 6.0))
        self.assertEqual(unpackedData[2], [(7, 8, 9), (10, 11, 12)])

    def test_locationPackingOlderVersions(self):
        for version in [1, 2]:
            loc1 = grids.IndexLocation(1, 2, 3, None)
            loc2 = grids.CoordinateLocation(4.0, 5.0, 6.0, None)
            loc3 = grids.MultiIndexLocation(None)
            loc3.append(grids.IndexLocation(7, 8, 9, None))
            loc3.append(grids.IndexLocation(10, 11, 12, None))

            locs = [loc1, loc2, loc3]
            tp, data = layout._packLocations(locs, minorVersion=version)

            self.assertEqual(tp[0], "IndexLocation")
            self.assertEqual(tp[1], "CoordinateLocation")
            self.assertEqual(tp[2], "MultiIndexLocation")

            unpackedData = layout._unpackLocations(tp, data, minorVersion=version)

            self.assertEqual(unpackedData[0], (1, 2, 3))
            self.assertEqual(unpackedData[1], (4.0, 5.0, 6.0))
            self.assertEqual(unpackedData[2][0].tolist(), [7, 8, 9])
            self.assertEqual(unpackedData[2][1].tolist(), [10, 11, 12])

    def test_locationPackingOldVersion(self):
        version = 3

        loc1 = grids.IndexLocation(1, 2, 3, None)
        loc2 = grids.CoordinateLocation(4.0, 5.0, 6.0, None)
        loc3 = grids.MultiIndexLocation(None)
        loc3.append(grids.IndexLocation(7, 8, 9, None))
        loc3.append(grids.IndexLocation(10, 11, 12, None))

        locs = [loc1, loc2, loc3]
        tp, data = layout._packLocations(locs, minorVersion=version)

        self.assertEqual(tp[0], "I")
        self.assertEqual(tp[1], "C")
        self.assertEqual(tp[2], "M:2")

        unpackedData = layout._unpackLocations(tp, data, minorVersion=version)

        self.assertEqual(unpackedData[0], (1, 2, 3))
        self.assertEqual(unpackedData[1], (4.0, 5.0, 6.0))
        self.assertEqual(unpackedData[2][0], (7, 8, 9))
        self.assertEqual(unpackedData[2][1], (10, 11, 12))

    def test_close(self):
        intendedFileName = "xyz.h5"

        db = database.Database(intendedFileName, "w")
        self.assertEqual(db._fileName, intendedFileName)
        self.assertIsNone(db._fullPath)  # this isn't set until the db is opened

        db.open()
        self.assertEqual(db._fullPath, os.path.join(context.getFastPath(), intendedFileName))

        db.close()  # this should move the file out of the FAST_PATH
        self.assertEqual(db._fullPath, os.path.join(os.path.abspath("."), intendedFileName))
