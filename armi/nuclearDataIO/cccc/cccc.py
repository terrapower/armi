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
Defines containers for the reading and writing standard interface files for reactor physics codes.

.. impl:: Generic tool for reading and writing Committee on Computer Code Coordination (CCCC) format
    files for reactor physics codes
    :id: I_ARMI_NUCDATA
    :implements: R_ARMI_NUCDATA_ISOTXS,
                 R_ARMI_NUCDATA_GAMISO,
                 R_ARMI_NUCDATA_GEODST,
                 R_ARMI_NUCDATA_DIF3D,
                 R_ARMI_NUCDATA_PMATRX,
                 R_ARMI_NUCDATA_DLAYXS

    This module provides a number of base classes that implement general capabilities for binary and
    ASCII file I/O. The :py:class:`IORecord` serves as an abstract base class that instantiates a
    number of methods that the binary and ASCII children classes are meant to implement. These
    methods, prefixed with ``rw``, are meant to convert literal data types, e.g. float or int, to
    either binary or ASCII. This base class does its own conversion for container data types, e.g.
    list or matrix, relying on the child implementation of the literal types that the container
    possesses. The binary conversion is implemented in :py:class:`BinaryRecordReader` and
    :py:class:`BinaryRecordWriter`. The ASCII conversion is implemented in
    :py:class:`AsciiRecordReader` and :py:class:`AsciiRecordWriter`.

    These :py:class:`IORecord` classes are used within :py:class:`Stream` objects for the data
    conversion. :py:class:`Stream` is a context manager that opens a file for reading or writing on
    the ``__enter__`` and closes that file upon ``__exit__``. :py:class:`Stream` is an abstract base
    class that is subclassed for each CCCC file. It is subclassed directly for the CCCC files that
    contain cross-section data:

      * :py:class:`ISOTXS <armi.nuclearDataIO.cccc.isotxs.IsotxsIO>`
      * :py:mod:`GAMISO <armi.nuclearDataIO.cccc.gamiso>`
      * :py:class:`PMATRX <armi.nuclearDataIO.cccc.pmatrx.PmatrxIO>`
      * :py:class:`DLAYXS <armi.nuclearDataIO.cccc.dlayxs.DlayxsIO>`
      * :py:mod:`COMPXS <armi.nuclearDataIO.cccc.compxs>`

    For the CCCC file types that are outputs from a flux solver such as DIF3D (e.g., GEODST, DIF3D,
    NHFLUX) the streams are subclassed from :py:class:`StreamWithDataContainer`, which is a special
    abstract subclass of :py:class:`Stream` that implements a common pattern used for these file
    types. In a :py:class:`StreamWithDataContainer`, the data is directly read to or written from a
    specialized data container.

    The data container structure for each type of CCCC file is implemented in the module for that
    file, as a subclass of :py:class:`DataContainer`. The subclasses for each CCCC file type define
    standard attribute names for the data that will be read from or written to the CCCC file. CCCC
    file types that follow this pattern include:

      * :py:class:`GEODST <armi.nuclearDataIO.cccc.geodst.GeodstData>`
      * :py:class:`DIF3D <armi.nuclearDataIO.cccc.dif3d.Dif3dData>`
      * :py:class:`NHFLUX <armi.nuclearDataIO.cccc.nhflux.NHFLUX>` (and multiple sub-classes)
      * :py:class:`LABELS <armi.nuclearDataIO.cccc.labels.LabelsData>`
      * :py:class:`PWDINT <armi.nuclearDataIO.cccc.pwdint.PwdintData>`
      * :py:class:`RTFLUX <armi.nuclearDataIO.cccc.rtflux.RtfluxData>`
      * :py:class:`RZFLUX <armi.nuclearDataIO.cccc.rzflux.RzfluxData>`
      * :py:class:`RTFLUX <armi.nuclearDataIO.cccc.rtflux.RtfluxData>`

    The logic to parse or write each specific file format is contained within the
    :py:meth:`Stream.readWrite` implementations of the respective subclasses.
"""
import io
import itertools
import os
import struct
from copy import deepcopy
from typing import List

import numpy as np

from armi import runLog
from armi.nuclearDataIO import nuclearFileMetadata

IMPLICIT_INT = "IJKLMN"
"""Letters that trigger implicit integer types in old FORTRAN 77 codes."""


class IORecord:
    """
    A single CCCC record.

    Reads or writes information to or from a stream.

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
        str(2**31 - 1)
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
            raise BufferError(
                "Failed to close record, {}.\n{}\n"
                "It is possible too much data was read from the "
                "record, and the end of the stream was reached.\n"
                "".format(self, ee)
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
        """
        A method for reading and writing a (array) of items of a specific type.

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
        action = actions.get(containedType)
        if action is None:
            raise Exception(
                'Cannot pack or unpack the type "{}".'.format(containedType)
            )
        # this little trick will make this work for both reading and writing, yay!
        if contents is None or len(contents) == 0:
            contents = [None for _ in range(length)]
        return np.array([action(contents[ii]) for ii in range(length)])

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

    def rwIntMatrix(self, contents, *shape):
        """Read or write a matrix of int values."""
        return self._rwMatrix(contents, self.rwInt, *shape)

    @staticmethod
    def _rwMatrix(contents, func, *shape):
        """
        Read/write a matrix.

        Notes
        -----
        This can be important for performance when reading large matrices (e.g. scatter
        matrices). It may be worth investigating ``np.frombuffer`` on read and
        something similar on write.

        With shape, the first shape argument should be the outermost loop because
        these are stored in column major order (the FORTRAN way).

        Note that np.ndarrays can be built with ``order="F"`` to have column-major ordering.

        So if you have ``((MR(I,J),I=1,NCINTI),J=1,NCINTJ)`` you would pass in
        the shape as (NCINTJ, NCINTI).
        """
        fortranShape = list(reversed(shape))
        if contents is None or contents.size == 0:
            contents = np.empty(fortranShape)
        for index in itertools.product(*[range(ii) for ii in shape]):
            fortranIndex = tuple(reversed(index))
            contents[fortranIndex] = func(contents[fortranIndex])
        return contents

    def rwImplicitlyTypedMap(self, keys: List[str], contents) -> dict:
        """
        Read a dict of floats and/or ints with FORTRAN77-style implicit typing.

        Length of list is determined by length of list of keys passed in.
        """
        for key in keys:
            # ready for some implicit madness from the FORTRAN 77 days?
            if key[0].upper() in IMPLICIT_INT:
                contents[key] = self.rwInt(contents[key])
            else:
                contents[key] = self.rwFloat(contents[key])
        return contents


class BinaryRecordReader(IORecord):
    """
    Writes a single CCCC record in binary format.

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
            raise BufferError(
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
    """
    Reads a single CCCC record in binary format.

    Reads binary information sequentially.
    """

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
    """
    Reads a single CCCC record in ASCII format.

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
    r"""
    Writes a single CCCC record in ASCII format.

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


class DataContainer:
    """
    Data representation that can be read/written to/from with a cccc.Stream.

    This is an optional convenience class expected to be used in
    concert with :py:class:`StreamWithDataStructure`.
    """

    def __init__(self):
        # Need Metadata subclass for default keys
        self.metadata = nuclearFileMetadata._Metadata()


class Stream:
    """
    An abstract CCCC IO stream.

    Warning
    -------
    This is more of a stream Parser/Serializer than an actual stream.

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
        """
        Create an instance of a :py:class:`~armi.nuclearDataIO.cccc.Stream`.

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
            raise KeyError(
                "{} not in {}".format("fileMode", list(self._fileModes.keys()))
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
        """At the inception of a with command, open up the file for a read/write."""
        try:
            self._stream = open(self._fileName, self._fileMode)
        except IOError:
            runLog.error("Cannot find {} in {}".format(self._fileName, os.getcwd()))
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """At the termination of a with command, close the file."""
        self._stream.close()

    def readWrite(self):
        """This method should be implemented on any sub-classes to specify the order of records."""
        raise NotImplementedError()

    def createRecord(self, hasRecordBoundaries=True):
        recordClass = self._fileModes[self._fileMode]
        return recordClass(self._stream, hasRecordBoundaries)

    @classmethod
    def readBinary(cls, fileName: str):
        """Read data from a binary file into a data structure."""
        return cls._read(fileName, "rb")

    @classmethod
    def readAscii(cls, fileName: str):
        """Read data from an ASCII file into a data structure."""
        return cls._read(fileName, "r")

    @classmethod
    def _read(cls, fileName, fileMode):
        raise NotImplementedError()

    @classmethod
    def writeBinary(cls, data: DataContainer, fileName: str):
        """Write the contents of a data container to a binary file."""
        return cls._write(data, fileName, "wb")

    @classmethod
    def writeAscii(cls, data: DataContainer, fileName: str):
        """Write the contents of a data container to an ASCII file."""
        return cls._write(data, fileName, "w")

    @classmethod
    def _write(cls, lib, fileName, fileMode):
        raise NotImplementedError()


class StreamWithDataContainer(Stream):
    """
    A cccc.Stream that reads/writes to a specialized data container.

    This is a relatively common pattern so some of the boilerplate
    is handled here.

    Warning
    -------
    This is more of a stream Parser/Serializer than an actual stream.

    Notes
    -----
    It should be possible to fully merge this with ``Stream``, which may make
    this a little less confusing.
    """

    def __init__(self, data: DataContainer, fileName: str, fileMode: str):
        Stream.__init__(self, fileName, fileMode)
        self._data = data
        self._metadata = self._data.metadata

    @staticmethod
    def _getDataContainer() -> DataContainer:
        raise NotImplementedError()

    @classmethod
    def _read(cls, fileName: str, fileMode: str):
        data = cls._getDataContainer()
        return cls._readWrite(
            data,
            fileName,
            fileMode,
        )

    @classmethod
    def _write(cls, data: DataContainer, fileName: str, fileMode: str):
        return cls._readWrite(data, fileName, fileMode)

    @classmethod
    def _readWrite(cls, data: DataContainer, fileName: str, fileMode: str):
        with cls(data, fileName, fileMode) as rw:
            rw.readWrite()
        return data


def getBlockBandwidth(m, nintj, nblok):
    """
    Return block bandwidth JL, JU from CCCC interface files.

    It is common for CCCC files to block data in various records with
    a description along the lines of::

        WITH M AS THE BLOCK INDEX, JL=(M-1)*((NINTJ-1)/NBLOK +1)+1
        AND JU=MIN0(NINTJ,JUP) WHERE JUP=M*((NINTJ-1)/NBLOK +1)

    This function computes JL and JU for these purposes. It also converts
    JL and JU to zero based indices rather than 1 based ones, as is almost
    always wanted when dealing with python/numpy matrices.

    The term *bandwidth* refers to a kind of sparse matrix representation.
    Some rows only have columns JL to JH in them rather than 0 to JMAX.
    The non-zero band from JL to JH is what we're talking about here.
    """
    x = (nintj - 1) // nblok + 1
    jLow = (m - 1) * x + 1
    jHigh = min(nintj, m * x)
    return jLow - 1, jHigh - 1
