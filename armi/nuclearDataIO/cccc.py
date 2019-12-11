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

"""
Standard interface files for reactor physics codes.

This module is designed to read/write Fortran record-based binary files that
comply with the format established by the Committee on Computer Code
Coordination (CCCC). [CCCC-IV]_

Notes
-----
A CCCC record consists of a leading and ending integer, which indicates the size of the record in
bytes. As a result, it is possible to perform a check when reading in a record to determine if it
was read correctly, by making sure the record size at the beginning and ending of a record are
always equal.

There are similarities between this code and that in the PyNE cccc subpackage.
This is the original source of the code. TerraPower authorized the publication
of some of the CCCC code to the PyNE project way back in the 2011 era. 
This code has since been updated significantly to both read and 
write the files.

This was originally created following Prof. James Paul Holloway's alpha
release of ccccutils written in c++ from 2001. 
"""
import io
import itertools
import struct
import os
from copy import deepcopy

import numpy

from armi.localization import exceptions
from armi import runLog


class CCCCRecord(object):
    """
    A single record from a CCCC file

    Reads binary information sequentially. 
    """

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.intSize = struct.calcsize("i")
        self.floatSize = struct.calcsize("f")

    def getInt(self):
        (i,) = struct.unpack("i", self.data[self.pos : self.pos + self.intSize])
        self.pos += self.intSize
        return i

    def getFloat(self):
        (f,) = struct.unpack("f", self.data[self.pos : self.pos + self.floatSize])
        self.pos += self.floatSize
        return f

    def getDouble(self):
        (d,) = struct.unpack("d", self.data[self.pos : self.pos + self.floatSize * 2])
        self.pos += self.floatSize * 2
        return d

    def getString(self, length):
        relevantData = self.data[self.pos : self.pos + length]
        (s,) = struct.unpack("%ds" % length, relevantData)
        self.pos += length
        return s

    def getList(self, ltype, length, strLength=0):
        if ltype == "int":
            results = [self.getInt() for _i in range(length)]
        elif ltype == "float":
            results = [self.getFloat() for _i in range(length)]
        elif ltype == "double":
            results = [self.getDouble() for _i in range(length)]
        elif ltype == "string":
            results = [self.getString(strLength).strip() for _i in range(length)]
        else:
            print("Do not recognize type: {0}".format(type))
            return None
        return results


class CCCCReader(object):
    """
    Reads a binary file according to CCCC standards.
    """

    def __init__(self, fName="ISOTXS"):
        self.intSize = struct.calcsize("i")
        self.floatSize = struct.calcsize("d")
        self.f = open(fName, "rb")

    def getInt(self):
        """
        Get an integer from the file before we have a record.

        Required for reading a record.

        See Also
        --------
        armi.nuclearDataIO.CCCCReader.getInt : gets integers once a record is already read
        """
        (i,) = struct.unpack("i", self.f.read(self.intSize))
        return i

    def getFloat(self):
        (f,) = struct.unpack("d", self.f.read(self.floatSize))
        return f

    def getRecord(self):
        r"""CCCC records start with an int and end with the same int. This int represents the number of bytes
        that the record is. That makes it easy to read. """
        numBytes = self.getInt()
        if numBytes % self.intSize:
            raise ValueError(
                "numBytes %d is not a multiple of byte size: %d"
                % (numBytes, self.intSize)
            )

        rec = self.f.read(numBytes)

        # now read end of record
        numBytes2 = self.getInt()
        if numBytes2 != numBytes:
            raise ValueError(
                "numBytes2 %d is not a equal to original byte count: %d"
                % (numBytes2, numBytes)
            )

        return CCCCRecord(rec)

    def readFileID(self):

        r"""
        This reads the file ID record in the binary file.

        This information is currently not used - just getting to the next record.

        """

        fileIdRec = self.getRecord()
        self.label = fileIdRec.getString(24)
        _fileID = fileIdRec.getInt()


class IORecord(object):
    """
    A single CCCC record.

    Reads, or writes, information to, or from, a stream.

    Parameters
    ----------
    stream
        A collection of data to be read or written

    hasRecordBoundaries : bool
        A True value means the fortran file was written using access='sequential' and contains
        a 4 byte int count at the beginning and end of each record. Otherwise, if False the
        fortran file was written using access='direct'.
        
    Notes
    -----
    The methods in this object often have `rw` prefixes, meaning the same method
    can be used for both reading and writing. We consider this a significant 
    achievement that enforces consistency between the code for reading and writing
    CCCC records. The tradeoff is that it's a bit challenging to comprehend at first.
    """

    _intSize = struct.calcsize("i")
    _longSize = struct.calcsize("q")
    maxsize = len(
        str(2 ** 31 - 1)
    )  # limit to max short even though Python3 can go bigger.
    _intFormat = " {{:>+{}}}".format(maxsize)
    _intLength = maxsize + 1

    _floatSize = struct.calcsize("f")
    _floatFormat = " {:+.16E}"
    _floatLength = 2 + 2 + 16 + 4

    _characterSize = struct.calcsize("c")
    count = 0

    def __init__(self, stream, hasRecordBoundaries=True):
        IORecord.count += 1
        self._stream = stream
        self.numBytes = 0
        self.byteCount = 0
        self._hasRecordBoundaries = hasRecordBoundaries

    def __enter__(self):
        """Open the stream for reading/writing and return :code:`self`.

        See Also
        --------
        armi.nuclearDataIO.cccc.IORecord.open
        """
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            return
        try:
            self.close()
        except Exception as ee:
            runLog.error("Failed to close CCCC record.")
            runLog.error(ee)
            raise exceptions.CcccRecordError(
                "Failed to close record, {}.\n{}\n"
                "It is possible too much data was read from the "
                "record, and the end of the stream was reached.\n"
                "Check stdout for the file name; you may need to "
                "remove any files in the current directory matching "
                "the pattern ISO*.".format(self, ee)
            )

    def open(self):
        """Abstract method for opening the stream."""
        raise NotImplementedError()

    def close(self):
        """Abstract method for closing the stream."""
        raise NotImplementedError()

    def rwInt(self, val):
        """Abstract method for reading or writing an integer.

        Notes
        -----
        The method has a seemingly odd signature, because it is used for both reading and writing.
        When writing, the :code:`val` should have value, but when the record is being read,
        :code:`val` can be :code:`None` or anything else; it is ignored.

        """
        raise NotImplementedError()

    def rwBool(self, val):
        """Read or write a boolean value from an integer."""
        val = False if not isinstance(val, bool) else val
        return bool(self.rwInt(int(val)))

    def rwFloat(self, val):
        """Abstract method for reading or writing a floating point (single precision) value.

        Notes
        -----
        The method has a seemingly odd signature, because it is used for both reading and writing.
        When writing, the :code:`val` should have value, but when the record is being read,
        :code:`val` can be :code:`None` or anything else; it is ignored.

        """
        raise NotImplementedError()

    def rwDouble(self, val):
        """Abstract method for reading or writing a floating point (double precision) value.

        Notes
        -----
        The method has a seemingly odd signature, because it is used for both reading and writing.
        When writing, the :code:`val` should have value, but when the record is being read,
        :code:`val` can be :code:`None` or anything else; it is ignored.

        """
        raise NotImplementedError()

    def rwString(self, val, length):
        """Abstract method for reading or writing a string.

        Notes
        -----
        The method has a seemingly odd signature, because it is used for both reading and writing.
        When writing, the :code:`val` should have value, but when the record is being read,
        :code:`val` can be :code:`None` or anything else; it is ignored.

        """
        raise NotImplementedError()

    def rwList(self, contents, containedType, length, strLength=0):
        """A method for reading and writing a (array) of items of a specific type.

        Notes
        -----
        The method has a seemingly odd signature, because it is used for both reading and writing.
        When writing, the :code:`contents` should have value, but when the record is being read,
        :code:`contents` can be :code:`None` or anything else; it is ignored.

        Warning
        -------
        If a :code:`contents` evaluates to :code:`True`, the array must be the same size as
        :code:`length`.
        """
        actions = {
            "int": self.rwInt,
            "float": self.rwFloat,
            "string": lambda val: self.rwString(val, strLength),
            "double": self.rwDouble,
        }
        action = actions.get(containedType, None)
        if action is None:
            raise Exception(
                'Cannot pack or unpack the type "{}".'.format(containedType)
            )
        # this little trick will make this work for both reading and writing, yay!
        if not contents:
            contents = [None for _ in range(length)]
        return [action(contents[ii]) for ii in range(length)]

    def rwMatrix(self, contents, *shape):
        """A method for reading and writing a matrix of floating point values.

        Notes
        -----
        The method has a seemingly odd signature, because it is used for both reading and writing.
        When writing, the :code:`contents` should have value, but when the record is being read,
        :code:`contents` can be :code:`None` or anything else; it is ignored.

        Warning
        -------
        If a :code:`contents` is not :code:`None`, the array must be the same shape as
        :code:`*shape`.
        """
        return self._rwMatrix(contents, self.rwFloat, *shape)

    def rwDoubleMatrix(self, contents, *shape):
        """Read or write a matrix of floating point values.

        Notes
        -----
        The method has a seemingly odd signature, because it is used for both reading and writing.
        When writing, the :code:`contents` should have value, but when the record is being read,
        :code:`contents` can be :code:`None` or anything else; it is ignored.

        Warning
        -------
        If a :code:`contents` is not :code:`None`, the array must be the same shape as
        :code:`*shape`.
        """
        return self._rwMatrix(contents, self.rwDouble, *shape)

    def _rwMatrix(self, contents, func, *shape):
        fortranShape = list(reversed(shape))
        if contents is None:
            contents = numpy.empty(fortranShape)
        for index in itertools.product(*[range(ii) for ii in shape]):
            fortranIndex = tuple(reversed(index))
            contents[fortranIndex] = func(contents[fortranIndex])
        return contents


class BinaryRecordReader(IORecord):
    """Writes a single CCCC record in binary format.

    Notes
    -----
    This class reads a single CCCC record in binary format. A CCCC record consists of a leading and
    ending integer indicating how many bytes the record is. The data contained within the record may
    be integer, float, double, or string.

    """

    def open(self):
        """Open the record by reading the number of bytes in the record, this value will be used
        to ensure the entire record was read.
        """
        if not self._hasRecordBoundaries:
            return
        self.numBytes = self.rwInt(None)
        self.byteCount -= 4

    def close(self):
        """Closes the record by reading the number of bytes from then end of the record, if it
        does not match the initial value, an exception will be raised.
        """
        if not self._hasRecordBoundaries:
            return
        # now read end of record
        numBytes2 = self.rwInt(None)
        self.byteCount -= 4
        if numBytes2 != self.numBytes:
            raise exceptions.CcccRecordError(
                "Number of bytes specified at end the of record, {}, "
                "does not match the originally specified number, {}.\n"
                "Read {} bytes.".format(numBytes2, self.numBytes, self.byteCount)
            )

    def rwInt(self, val):
        """Reads an integer value from the binary stream."""
        self.byteCount += self._intSize
        (i,) = struct.unpack("i", self._stream.read(self._intSize))
        return i

    def rwBool(self, val):
        """Read or write a boolean value from an integer."""
        return IORecord.rwBool(self, val)

    def rwLong(self, val):
        """Reads an integer value from the binary stream."""
        self.byteCount += self._longSize
        (ll,) = struct.unpack("q", self._stream.read(self._longSize))
        return ll

    def rwFloat(self, val):
        """Reads a single precision floating point value from the binary stream."""
        self.byteCount += self._floatSize
        (f,) = struct.unpack("f", self._stream.read(self._floatSize))
        return f

    def rwDouble(self, val):
        """Reads a double precision floating point value from the binary stream."""
        self.byteCount += self._floatSize * 2
        (d,) = struct.unpack("d", self._stream.read(self._floatSize * 2))
        return d

    def rwString(self, val, length):
        """Reads a string of specified length from the binary stream."""
        self.byteCount += length
        (s,) = struct.unpack("%ds" % length, self._stream.read(length))
        return s.rstrip().decode()  # convert bytes to string on reading.


class BinaryRecordWriter(IORecord):
    r"""a single record from a CCCC file

    Reads binary information sequentially. """

    def __init__(self, stream, hasRecordBoundaries=True):
        IORecord.__init__(self, stream, hasRecordBoundaries)
        self.data = None

    def open(self):
        self.data = []

    def close(self):
        if self._hasRecordBoundaries:
            packedNumBytes = self._getPackedNumBytes()
            self._stream.write(packedNumBytes)
        for i in range(0, len(self.data) + 1, io.DEFAULT_BUFFER_SIZE):
            self._write_buffer_to_stream(i)

        if self._hasRecordBoundaries:
            self._stream.write(packedNumBytes)
        self.data = None

    def _getPackedNumBytes(self):
        return struct.pack("i", self.numBytes)

    def _write_buffer_to_stream(self, i):
        self._stream.write(b"".join(self.data[i : i + io.DEFAULT_BUFFER_SIZE]))

    def rwInt(self, val):
        self.numBytes += self._intSize
        self.data.append(struct.pack("i", val))
        return val

    def rwBool(self, val):
        """Read or write a boolean value from an integer."""
        return IORecord.rwBool(self, val)

    def rwLong(self, val):
        """Reads an integer value from the binary stream."""
        self.byteCount += self._longSize
        self.data.append(struct.pack("q", val))
        return val

    def rwFloat(self, val):
        self.numBytes += self._floatSize
        self.data.append(struct.pack("f", val))
        return val

    def rwDouble(self, val):
        self.numBytes += self._floatSize * 2
        self.data.append(struct.pack("d", val))
        return val

    def rwString(self, val, length):
        self.numBytes += length * self._characterSize
        self.data.append(struct.pack("%ds" % length, val.ljust(length).encode("utf-8")))
        return val


class AsciiRecordReader(BinaryRecordReader):
    """Reads a single CCCC record in ASCII format.

    See Also
    --------
    AsciiRecordWriter
    """

    def close(self):
        BinaryRecordReader.close(self)
        # read one extra character for the new line \n... python somehow correctly figures out
        # that on windows \r\n is really just a \n... no idea how.
        self._stream.read(1)

    def _getPackedNumBytes(self):
        return self.numBytes

    def _write_buffer_to_stream(self, i):
        self._stream.write("".join(self.data[i : i + io.DEFAULT_BUFFER_SIZE]))

    def rwInt(self, val):
        return int(self._stream.read(self._intLength))

    def rwFloat(self, val):
        return float(self._stream.read(self._floatLength))

    def rwDouble(self, val):
        return self.rwFloat(val)

    def rwString(self, val, length):
        # read one space
        self._stream.read(1)
        return self._stream.read(length).rstrip()


class AsciiRecordWriter(IORecord):
    """Writes a single CCCC record in ASCII format.

    Since there is no specific format of an ASCII CCCC record, the format is roughly the same as
    the :py:class:`BinaryRecordWriter`, except that the :class:`AsciiRecordReader` puts a space in
    front of all values (ints, floats, and strings), and puts a newline character :code:`\\n` at the
    end of all records.
    """

    def __init__(self, stream, hasRecordBoundaries=True):
        IORecord.__init__(self, stream, hasRecordBoundaries)
        self.data = None
        self.numBytes = 0

    def open(self):
        self.data = []

    def close(self):
        self._stream.write(self._intFormat.format(self.numBytes))
        self._stream.write("".join(self.data))
        self._stream.write(self._intFormat.format(self.numBytes))
        self._stream.write("\n")
        self.data = None

    def rwInt(self, val):
        self.numBytes += self._intSize
        self.data.append(self._intFormat.format(val))
        return val

    def rwFloat(self, val):
        self.numBytes += self._floatSize
        self.data.append(self._floatFormat.format(val))
        return val

    def rwDouble(self, val):
        self.numBytes += self._floatSize * 2
        self.data.append(self._floatFormat.format(val))
        return val

    def rwString(self, val, length):
        self.numBytes += length * self._characterSize
        self.data.append(" {value:<{length}}".format(length=length, value=val))
        return val


class Stream(object):
    r"""An abstract CCCC IO stream.

    Notes
    -----
    A concrete instance of this class should implement the
    :py:meth:`~armi.nuclearDataIO.cccc.Stream.readWrite` method.
    """

    _fileModes = {
        "rb": BinaryRecordReader,
        "wb": BinaryRecordWriter,
        "r": AsciiRecordReader,
        "w": AsciiRecordWriter,
    }

    def __init__(self, fileName, fileMode):
        """Create an instance of a :py:class:`~armi.nuclearDataIO.cccc.Stream`.

        Parameters
        ----------
        fileName : str
            name of the file to be read
        fileMode : str
            the file mode, i.e. 'w' for writing ASCII, 'r' for reading ASCII, 'wb' for writing
            binary, and 'rb' for reading binary.
        """
        self._fileName = fileName
        self._fileMode = fileMode
        self._stream = None

        if fileMode not in self._fileModes:
            raise exceptions.InvalidSelectionError(
                "fileMode", fileMode, self._fileModes.keys()
            )

    def __deepcopy__(self, memo):
        """Open file objects can't be deepcopied so we clear them before copying."""
        cls = self.__class__
        result = cls.__new__(cls)
        result._stream = None
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k != "_stream":
                setattr(result, k, deepcopy(v, memo))
        return result

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, self._fileName)

    def __enter__(self):
        """At the inception of a with command, navigate to a new directory if one is supplied
        """
        try:
            self._stream = open(self._fileName, self._fileMode)
        except IOError:
            runLog.error("Cannot find {} in {}".format(self._fileName, os.getcwd()))
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """At the termination of a with command, navigate back to the original directory"""
        self._stream.close()

    def readWrite(self):
        """This method should be implemented on any sub-classes to specify the order of records."""
        raise NotImplementedError()

    def createRecord(self, hasRecordBoundaries=True):
        recordClass = self._fileModes[self._fileMode]
        return recordClass(self._stream, hasRecordBoundaries)

    @classmethod
    def readBinary(cls, fileName):
        return cls._read(fileName, "rb")

    @classmethod
    def readAscii(cls, fileName):
        return cls._read(fileName, "r")

    @classmethod
    def _read(cls, fileName, fileMode):
        raise NotImplementedError()

    @classmethod
    def writeBinary(cls, lib, fileName):
        return cls._write(lib, fileName, "wb")

    @classmethod
    def writeAscii(cls, lib, fileName):
        return cls._write(lib, fileName, "w")

    @classmethod
    def _write(cls, lib, fileName, fileMode):
        raise NotImplementedError()
