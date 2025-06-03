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

"""Unit tests for parsing."""

import unittest

from armi.utils import parsing


class LiteralEvalTest(unittest.TestCase):
    def test_tryLiteralEval(self):
        self.assertEqual(parsing.tryLiteralEval("1"), 1)
        self.assertEqual(parsing.tryLiteralEval(1), 1)
        self.assertEqual(parsing.tryLiteralEval("1.0"), 1.0)
        self.assertEqual(parsing.tryLiteralEval(1.0), 1.0)
        self.assertEqual(parsing.tryLiteralEval(1), 1)
        self.assertEqual(
            parsing.tryLiteralEval("['apple','banana','mango']"),
            ["apple", "banana", "mango"],
        )
        self.assertEqual(
            parsing.tryLiteralEval(["apple", "banana", "mango"]),
            ["apple", "banana", "mango"],
        )
        self.assertEqual(
            parsing.tryLiteralEval("{'apple':1,'banana':2,'mango':3}"),
            {"apple": 1, "banana": 2, "mango": 3},
        )
        self.assertEqual(
            parsing.tryLiteralEval({"apple": 1, "banana": 2, "mango": 3}),
            {"apple": 1, "banana": 2, "mango": 3},
        )
        self.assertEqual(parsing.tryLiteralEval("(1,2)"), (1, 2))
        self.assertEqual(parsing.tryLiteralEval((1, 2)), (1, 2))
        self.assertEqual(parsing.tryLiteralEval("u'apple'"), "apple")
        self.assertEqual(parsing.tryLiteralEval("apple"), "apple")
        self.assertEqual(parsing.tryLiteralEval("apple"), "apple")
        self.assertEqual(parsing.tryLiteralEval(tuple), tuple)

    def test_parseValue(self):
        self.assertEqual(parsing.parseValue("5", int), 5)
        self.assertEqual(parsing.parseValue(5, int), 5)
        self.assertEqual(parsing.parseValue("5", float), 5.0)
        self.assertEqual(parsing.parseValue("True", bool), True)
        self.assertEqual(
            parsing.parseValue("['apple','banana','mango']", list),
            ["apple", "banana", "mango"],
        )
        self.assertEqual(
            parsing.parseValue({"apple": 1, "banana": 2, "mango": 3}, dict),
            {"apple": 1, "banana": 2, "mango": 3},
        )
        self.assertEqual(
            parsing.parseValue("{'apple':1,'banana':2,'mango':3}", dict),
            {"apple": 1, "banana": 2, "mango": 3},
        )
        self.assertEqual(parsing.parseValue("(1,2)", tuple), (1, 2))

        self.assertEqual(parsing.parseValue("None", int, True), 0)
        self.assertEqual(parsing.parseValue(None, int, True), 0)
        self.assertEqual(parsing.parseValue("None", bool, True), False)
        self.assertEqual(parsing.parseValue(None, bool, True), False)

        self.assertEqual(parsing.parseValue(None, bool, True, False), None)

        with self.assertRaises(TypeError):
            parsing.parseValue("5", str)
        with self.assertRaises(ValueError):
            parsing.parseValue("5", bool)
