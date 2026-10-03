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
import struct
import unittest

import numpy as np

from armi.nuclearDataIO import cccc

# A non-square shape so that transposed or misordered reads fail. Matrices are passed in
# as (outer, inner) and come back as (inner, outer), stored column-major (FORTRAN order).
MATRIX_SHAPE = (3, 4)
FORTRAN_SHAPE = (4, 3)
MATRIX_TYPES = (("rwMatrix", "f"), ("rwDoubleMatrix", "d"), ("rwIntMatrix", "i"))


def _expectedMatrix(typeCode):
    """Values that are exact in every type, where element [i, j] is the (i + 4j)-th stored."""
    return (np.arange(12) * 0.5 - 2.0 if typeCode != "i" else np.arange(12) - 5).reshape(FORTRAN_SHAPE, order="F")


class TestCcccIOStream(unittest.TestCase):
    def test_initWithFileMode(self):
        self.assertIsInstance(cccc.Stream("some-file", "rb"), cccc.Stream)
        self.assertIsInstance(cccc.Stream("some-file", "wb"), cccc.Stream)
        self.assertIsInstance(cccc.Stream("some-file", "r"), cccc.Stream)
        self.assertIsInstance(cccc.Stream("some-file", "w"), cccc.Stream)
        with self.assertRaises(KeyError):
            cccc.Stream("some-file", "bacon")


class TestCcccBinaryRecord(unittest.TestCase):
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

    def test_readPartialRecord(self):
        """Not reading an entire record raises an exception."""
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

    def test_writeAndReadMatrices(self):
        for methodName, typeCode in MATRIX_TYPES:
            with self.subTest(methodName):
                expected = _expectedMatrix(typeCode)
                stream = self.streamCls()
                with self.writerClass(stream) as writer:
                    getattr(writer, methodName)(expected, *MATRIX_SHAPE)
                with self.readerClass(self.streamCls(stream.getvalue())) as reader:
                    actual = getattr(reader, methodName)(None, *MATRIX_SHAPE)
                self.assertEqual(writer.numBytes, reader.numBytes)
                np.testing.assert_array_equal(actual, expected)


class TestCcccBinaryMatrixRead(unittest.TestCase):
    """Check binary matrix reads against a known byte layout and the generic per-value read."""

    @staticmethod
    def _packRecord(typeCode, values):
        """Pack a record with leading and trailing byte counts, like a sequential FORTRAN file."""
        payload = struct.pack(f"{len(values)}{typeCode}", *values)
        size = struct.pack("i", len(payload))
        return size + payload + size

    def _storedValues(self, typeCode):
        return _expectedMatrix(typeCode).ravel(order="F").tolist()

    def test_readKnownLayout(self):
        for methodName, typeCode in MATRIX_TYPES:
            with self.subTest(methodName):
                record = self._packRecord(typeCode, self._storedValues(typeCode))
                with cccc.BinaryRecordReader(io.BytesIO(record)) as reader:
                    actual = getattr(reader, methodName)(None, *MATRIX_SHAPE)
                self.assertEqual(actual.shape, FORTRAN_SHAPE)
                np.testing.assert_array_equal(actual, _expectedMatrix(typeCode))

    def test_matchesGenericRead(self):
        """The whole-matrix read must give the same result as reading value by value."""
        for methodName, typeCode in MATRIX_TYPES:
            with self.subTest(methodName):
                record = self._packRecord(typeCode, self._storedValues(typeCode))
                with cccc.BinaryRecordReader(io.BytesIO(record)) as reader:
                    fast = getattr(reader, methodName)(None, *MATRIX_SHAPE)
                with cccc.BinaryRecordReader(io.BytesIO(record)) as reader:
                    generic = getattr(cccc.IORecord, methodName)(reader, None, *MATRIX_SHAPE)
                self.assertEqual(fast.dtype, generic.dtype)
                np.testing.assert_array_equal(fast, generic)

    def test_readIntoExistingArray(self):
        """Reads fill a provided array in place and keep its dtype."""
        record = self._packRecord("f", self._storedValues("f"))
        contents = np.zeros(FORTRAN_SHAPE, dtype=np.float32)
        with cccc.BinaryRecordReader(io.BytesIO(record)) as reader:
            actual = reader.rwMatrix(contents, *MATRIX_SHAPE)
        self.assertIs(actual, contents)
        self.assertEqual(actual.dtype, np.float32)
        np.testing.assert_array_equal(actual, _expectedMatrix("f"))


class TestCcccAsciiRecord(TestCcccBinaryRecord):
    """Runs the same tests as TestCcccBinaryRecord, but using ASCII readers and writers."""

    @classmethod
    def setUpClass(cls):
        cls.writerClass = cccc.AsciiRecordWriter
        cls.readerClass = cccc.AsciiRecordReader

    def setUp(self):
        self.streamCls = io.StringIO
