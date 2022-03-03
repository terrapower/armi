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
""" tests of the propereties class """
# pylint: disable=missing-function-docstring,missing-class-docstring,abstract-method,protected-access,invalid-name
import os
import time
import unittest

from armi.utils import directoryChangers
from armi.utils import outputCache


class TestOutputCache(unittest.TestCase):
    def test_hashFiles(self):
        with directoryChangers.TemporaryDirectoryChanger() as dc:
            files = ["test_hashFiles1.txt", "test_hashFiles2.txt"]
            for fileName in files:
                with open(fileName, "w") as f:
                    f.write("hi")

            hashed = outputCache._hashFiles(files)

            self.assertEqual(hashed, "e9f5713dec55d727bb35392cec6190ce")

    def test_deleteCache(self):
        with directoryChangers.TemporaryDirectoryChanger() as dc:
            outDir = "snapshotOutput_Cache"
            self.assertFalse(os.path.exists(outDir))

            os.mkdir(outDir)
            with open(os.path.join(outDir, "test_deleteCache2.txt"), "w") as f:
                f.write("hi there")

            self.assertTrue(os.path.exists(outDir))
            time.sleep(2)
            outputCache.deleteCache(outDir)
            self.assertFalse(os.path.exists(outDir))


if __name__ == "__main__":
    unittest.main()
