"""
Module for reading/writing RZFLUX CCCC interface file.

RZFLUX contains Regular Zone Flux, or multigroup flux by neutron energy group
in each zone. It also can hold some convergence and neutron balance information.

The format is defined in [CCCC-IV]_.

Examples
--------
>>> flux = rzflux.readBinary("RZFLUX")

"""

import numpy

from armi.nuclearDataIO import cccc, nuclearFileMetadata

# See CCCC-IV documentation for definitions
FILE_SPEC_1D_KEYS = (
    "TIME",
    "POWER",
    "VOL",
    "EFFK",
    "EIVS",
    "DKDS",
    "TNL",
    "TNA",
    "TNSL",
    "TNBL",
    "TNBAL",
    "TNCRA",
    "X1",
    "X2",
    "X3",
    "NBLOK",
    "ITPS",
    "NZONE",
    "NGROUP",
    "NCY",
)

IMPLICIT_INT = "IJKLMN"


class RzfluxData:
    """
    Data representation that can be read from or written to a RZFLUX file.

    Notes
    -----
    Analogous to a IsotxsLibrary for ISTOXS files.
    """

    def __init__(self):
        # Need Metadata subclass for default keys
        self.metadata = nuclearFileMetadata._Metadata()

        # 2D data
        self.groupFluxes = None


class RzfluxStream(cccc.Stream):
    """
    Stream for reading to/writing from with RZFLUX data.

    Parameters
    ----------
    flux : RzfluxData
        Data structure
    fileName: str
        path to RZFLUX file
    fileMode: str
        string indicating if ``fileName`` is being read or written, and
        in ascii or binary format

    """

    def __init__(self, flux: RzfluxData, fileName: str, fileMode: str):
        cccc.Stream.__init__(self, fileName, fileMode)
        self.fc = {}  # file control info (sort of global for this library)
        self._flux = flux
        self._metadata = self._getFileMetadata()

    def _getFileMetadata(self):
        return self._flux.metadata

    @classmethod
    def _read(cls, fileName: str, fileMode: str) -> RzfluxData:
        flux = RzfluxData()
        return cls._readWrite(
            flux,
            fileName,
            fileMode,
        )

    # pylint: disable=arguments-differ
    @classmethod
    def _write(cls, flux: RzfluxData, fileName: str, fileMode: str):
        return cls._readWrite(flux, fileName, fileMode)

    @classmethod
    def _readWrite(cls, flux: RzfluxData, fileName: str, fileMode: str) -> RzfluxData:
        with RzfluxStream(flux, fileName, fileMode) as rw:
            rw.readWrite()
        return flux

    def readWrite(self):
        """
        Step through the structure of the file and read/write it.
        """
        self._rwFileID()
        self._rw1DRecord()
        self._rw2DRecord()

    def _rwFileID(self):
        """
        Read/write file id record.

        Notes
        -----
        The username, version, etc are embedded in this string but it's
        usually blank. The number 28 was actually obtained from
        a hex editor and may be code specific.
        """
        with self.createRecord() as record:
            self._metadata["label"] = record.rwString(self._metadata["label"], 28)

    def _rw1DRecord(self):
        """
        Read/write File specifications on 1D record.

        This record contains 27 integers.
        """
        with self.createRecord() as record:
            for key in FILE_SPEC_1D_KEYS:
                # ready for some implicit madness from the FORTRAN 77 days?
                if key[0] in IMPLICIT_INT:
                    self._metadata[key] = record.rwInt(self._metadata[key])
                else:
                    self._metadata[key] = record.rwFloat(self._metadata[key])

    def _rw2DRecord(self):
        """
        Read/write the multigroup fluxes (n/cm^2/2) into a NxG matrix.

        Notes
        -----
        Zones are blocked into multiple records so we have to block or unblock
        them.

        _rwMatrix reverses the indices into FORTRAN data order so be
        very careful with the indices.
        """
        nz = self._metadata["NZONE"]
        ng = self._metadata["NGROUP"]
        nb = self._metadata["NBLOK"]
        if self._flux.groupFluxes is None:
            # initialize all-zeros here before reading now that we
            # have the matrix dimension metadata available.
            self._flux.groupFluxes = numpy.zeros(
                (ng, nz),
                dtype=numpy.float32,
            )
        blockRatio = (nz - 1) // nb + 1
        for bi in range(nb):
            # compute data-blocking bounds, convert to base 0
            jLow = bi * blockRatio
            jUp = (bi + 1) * blockRatio
            jUp = min(nz, jUp) - 1
            numZonesInBlock = jUp - jLow + 1
            with self.createRecord() as record:
                # pass in shape in fortran (read) order
                # pylint: disable=protected-access
                self._flux.groupFluxes[:, jLow : jUp + 1] = record._rwMatrix(
                    self._flux.groupFluxes[:, jLow : jUp + 1],
                    record.rwFloat,
                    numZonesInBlock,
                    ng,
                )


readBinary = RzfluxStream.readBinary  # pylint: disable=invalid-name
readAscii = RzfluxStream.readAscii  # pylint: disable=invalid-name
writeBinary = RzfluxStream.writeBinary  # pylint: disable=invalid-name
writeAscii = RzfluxStream.writeAscii  # pylint: disable=invalid-name
