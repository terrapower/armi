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
"""Test CCCC."""

import io
import unittest

from armi.nuclearDataIO import cccc


class CcccIOStreamTests(unittest.TestCase):
    def test_initWithFileMode(self):
        self.assertIsInstance(cccc.Stream("some-file", "rb"), cccc.Stream)
        self.assertIsInstance(cccc.Stream("some-file", "wb"), cccc.Stream)
        self.assertIsInstance(cccc.Stream("some-file", "r"), cccc.Stream)
        self.assertIsInstance(cccc.Stream("some-file", "w"), cccc.Stream)
        with self.assertRaises(KeyError):
            cccc.Stream("some-file", "bacon")


class CcccBinaryRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.writerClass = cccc.BinaryRecordWriter
        cls.readerClass = cccc.BinaryRecordReader

    def setUp(self):
        self.streamCls = io.BytesIO

    def test_writeAndReadSimpleIntegerRecord(self):
        value = 42
        stream = self.streamCls()
        with self.writerClass(stream) as writer:
            writer.rwInt(value)
        with self.readerClass(self.streamCls(stream.getvalue())) as reader:
            self.assertEqual(writer.numBytes, reader.numBytes)
            self.assertEqual(value, reader.rwInt(None))
        self.assertEqual(4, writer.numBytes)

    def test_writeAndReadSimpleFloatRecord(self):
        stream = self.streamCls()
        value = -33.322222
        with self.writerClass(stream) as writer:
            writer.rwFloat(value)
        with self.readerClass(self.streamCls(stream.getvalue())) as reader:
            self.assertEqual(writer.numBytes, reader.numBytes)
            self.assertAlmostEqual(value, reader.rwFloat(None), 5)
        self.assertEqual(4, writer.numBytes)

    def test_writeAndReadSimpleStringRecord(self):
        stream = self.streamCls()
        value = "Howdy, partner!"
        size = 8 * 8
        with self.writerClass(stream) as writer:
            writer.rwString(value, size)
        with self.readerClass(self.streamCls(stream.getvalue())) as reader:
            self.assertEqual(writer.numBytes, reader.numBytes)
            self.assertEqual(value, reader.rwString(None, size))
        self.assertEqual(size, writer.numBytes)

    def test_notReadingAnEntireRecordRaisesException(self):
        # I'm going to create a record with two pieces of data, and only read one...
        stream = self.streamCls()
        value = 99
        with self.writerClass(stream) as writer:
            writer.rwInt(value)
            writer.rwInt(value)
        self.assertEqual(8, writer.numBytes)
        with self.assertRaises(BufferError):
            with self.readerClass(self.streamCls(stream.getvalue())) as reader:
                self.assertEqual(value, reader.rwInt(None))

    def test_readingBeyondRecordRaisesException(self):
        # I'm going to create a record with two pieces of data, and only read one...
        stream = self.streamCls()
        value = 77
        with self.writerClass(stream) as writer:
            writer.rwInt(value)
        self.assertEqual(4, writer.numBytes)
        with self.assertRaises(BufferError):
            with self.readerClass(self.streamCls(stream.getvalue())) as reader:
                self.assertEqual(value, reader.rwInt(None))
                self.assertEqual(4, reader.rwInt(None))


class CcccAsciiRecordTests(CcccBinaryRecordTests):
    """Runs the same tests as CcccBinaryRecordTests, but using ASCII readers and writers."""

    @classmethod
    def setUpClass(cls):
        cls.writerClass = cccc.AsciiRecordWriter
        cls.readerClass = cccc.AsciiRecordReader

    def setUp(self):
        self.streamCls = io.StringIO
