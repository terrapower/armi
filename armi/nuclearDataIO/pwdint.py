"""
Read/write a CCCC PWDINT power density definition file.

PWDINT files power density at mesh intervals.

File format definition is from [CCCC-IV]_.

Examples
--------
>>> pwr = pwdint.readBinary("PWDINT")
>>> pwdint.writeBinary(pwr, "PWDINT2")

"""

import numpy

from armi.nuclearDataIO import cccc, nuclearFileMetadata

# See CCCC-IV documentation for definitions
FILE_SPEC_1D_KEYS = (
    "TIME",
    "POWER",
    "VOL",
    "NINTI",
    "NINTJ",
    "NINTK",
    "NCY",
    "NBLOK",
)


class PwdintData:
    """
    Data representation that can be read from or written to a PWDINT file.

    This contains a mapping from the i,j,k GEODST mesh to power density
    in Watts/cm^3.
    """

    def __init__(self):
        self.metadata = nuclearFileMetadata._Metadata()
        self.powerDensity = numpy.array([])


class PwdintStream(cccc.Stream):
    """
    Stream for reading to/writing from with PWDINT data.

    Parameters
    ----------
    power : PwdintData
        Data structure
    fileName: str
        path to pwdint file
    fileMode: str
        string indicating if ``fileName`` is being read or written, and
        in ascii or binary format
    """

    def __init__(self, power: PwdintData, fileName: str, fileMode: str):
        cccc.Stream.__init__(self, fileName, fileMode)
        self.fc = {}  # file control info (sort of global for this library)
        self._power = power
        self._metadata = self._getFileMetadata()

    def _getFileMetadata(self):
        return self._power.metadata

    @classmethod
    def _read(cls, fileName: str, fileMode: str) -> PwdintData:
        power = PwdintData()
        return cls._readWrite(
            power,
            fileName,
            fileMode,
        )

    # pylint: disable=arguments-differ
    @classmethod
    def _write(cls, power: PwdintData, fileName: str, fileMode: str):
        return cls._readWrite(power, fileName, fileMode)

    @classmethod
    def _readWrite(cls, power: PwdintData, fileName: str, fileMode: str) -> PwdintData:
        with PwdintStream(power, fileName, fileMode) as rw:
            rw.readWrite()
        return power

    def readWrite(self):
        """
        Step through the structure of a PWDINT file and read/write it.

        Logic to control which records will be present is here, which
        comes directly off the File specification.
        """
        self._rwFileID()
        self._rw1DRecord()
        self._rw2DRecord()

    def _rwFileID(self):
        with self.createRecord() as record:
            self._metadata["hname"] = record.rwString(self._metadata["hname"], 8)
            for name in ["huse", "huse2"]:
                self._metadata[name] = record.rwString(self._metadata[name], 6)
            self._metadata["version"] = record.rwInt(self._metadata["version"])
            self._metadata["mult"] = record.rwInt(self._metadata["mult"])

    def _rw1DRecord(self):
        """
        Read/write File specifications on 1D record.
        """
        with self.createRecord() as record:
            for key in FILE_SPEC_1D_KEYS:
                if key[0] in cccc.IMPLICIT_INT:
                    self._metadata[key] = record.rwInt(self._metadata[key])
                else:
                    self._metadata[key] = record.rwFloat(self._metadata[key])

    def _rw2DRecord(self):
        """Read/write power density by mesh point."""
        imax = self._metadata["NINTI"]
        jmax = self._metadata["NINTJ"]
        kmax = self._metadata["NINTK"]
        nblck = self._metadata["NBLOK"]
        if self._power.powerDensity.size == 0:
            # initialize all-zeros here before reading now that we
            # have the matrix dimension metadata available.
            self._power.powerDensity = numpy.zeros(
                (imax, jmax, kmax),
                dtype=numpy.float32,
            )
        for ki in range(kmax):
            for bi in range(nblck):
                jL, jU = cccc.getBlockBandwidth(bi + 1, jmax, nblck)
                with self.createRecord() as record:
                    self._power.powerDensity[:, jL : jU + 1, ki] = record.rwMatrix(
                        self._power.powerDensity[:, jL : jU + 1, ki],
                        jU - jL + 1,
                        imax,
                    )


readBinary = PwdintStream.readBinary
readAscii = PwdintStream.readAscii
writeBinary = PwdintStream.writeBinary
writeAscii = PwdintStream.writeAscii
