"""
Read/write a CCCC GEODST geometry definition file.

GEODST files define fine and coarse meshes and mappings between
region numbers and mesh indices. They also store some zone
information.

File format definition is from [CCCC-IV]_.

Examples
--------
>>> geo = geodst.readBinary("GEODST")
>>> print(geo.xmesh)
>>> geo.zmesh[-1]*=2  # make a modification to data
>>> geodst.writeBinary(geo, "GEODST2")

"""

import numpy

from armi.nuclearDataIO import cccc, nuclearFileMetadata

# See CCCC-IV documentation for definitions
FILE_SPEC_1D_KEYS = (
    "IGOM",
    "NZONE",
    "NREG",
    "NZCL",
    "NCINTI",
    "NCINTJ",
    "NCINTK",
    "NINTI",
    "NINTJ",
    "NINTK",
    "IMB1",
    "IMB2",
    "JMB1",
    "JMB2",
    "KMB1",
    "KMB2",
    "NBS",
    "NBCS",
    "NIBCS",
    "NZWBB",
    "NTRIAG",
    "NRASS",
    "NTHPT",
    "NGOP1",
    "NGOP2",
    "NGOP3",
    "NGOP4",
)


class GeodstData:
    """
    Data representation that can be read from or written to a GEODST file.

    The region numbers in this data structure START AT 1, not zero! Thus
    you must always remember the off-by-one conversion when comparing
    with list or matrix indices.

    Notes
    -----
    Analogous to a IsotxsLibrary for ISTOXS files.
    """

    def __init__(self):
        # Need Metadata subclass for default keys
        self.metadata = nuclearFileMetadata._Metadata()

        # 4D data
        self.xmesh = None
        self.ymesh = None
        self.zmesh = None
        self.iintervals = None
        self.jintervals = None
        self.kintervals = None

        # 5D data
        self.regionVolumes = None
        self.bucklings = None
        self.boundaryConstants = None
        self.internalBlackBoundaryConstants = None
        self.zonesWithBlackAbs = None
        self.zoneClassifications = None
        self.regionZoneNumber = None

        # 6d
        self.coarseMeshRegions = None

        # 7d
        self.fineMeshRegions = None


class GeodstStream(cccc.Stream):
    """
    Stream for reading to/writing from with GEODST data.

    Parameters
    ----------
    geom : GeodstData
        Data structure
    fileName: str
        path to geodst file
    fileMode: str
        string indicating if ``fileName`` is being read or written, and
        in ascii or binary format

    """

    def __init__(self, geom: GeodstData, fileName: str, fileMode: str):
        cccc.Stream.__init__(self, fileName, fileMode)
        self.fc = {}  # file control info (sort of global for this library)
        self._geom = geom
        self._metadata = self._getFileMetadata()

    def _getFileMetadata(self):
        return self._geom.metadata

    @classmethod
    def _read(cls, fileName: str, fileMode: str) -> GeodstData:
        geom = GeodstData()
        return cls._readWrite(
            geom,
            fileName,
            fileMode,
        )

    # pylint: disable=arguments-differ
    @classmethod
    def _write(cls, geom: GeodstData, fileName: str, fileMode: str):
        return cls._readWrite(geom, fileName, fileMode)

    @classmethod
    def _readWrite(cls, geom: GeodstData, fileName: str, fileMode: str) -> GeodstData:
        with cls(geom, fileName, fileMode) as rw:
            rw.readWrite()
        return geom

    def readWrite(self):
        """
        Step through the structure of a GEODST file and read/write it.

        Logic to control which records will be present is here, which
        comes directly off the File specification.
        """
        self._rwFileID()
        self._rw1DRecord()
        geomType = self._metadata["IGOM"]
        if 0 > geomType >= 3:
            self._rw2DRecord()
        elif 6 <= geomType <= 11:
            self._rw3DRecord()
        elif geomType >= 12:
            self._rw4DRecord()

        if geomType > 0 or self._metadata["NBS"] > 0:
            self._rw5DRecord()

        if geomType > 0:
            if self._metadata["NRASS"] == 0:
                self._rw6DRecord()
            elif self._metadata["NRASS"] == 1:
                self._rw7DRecord()

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
                self._metadata[key] = record.rwInt(self._metadata[key])

    def _rw2DRecord(self):
        """Read/write info for 1-D meshes."""
        raise NotImplementedError(
            "1-D geometry not yet implemented in GEODST reader/writer"
        )

    def _rw3DRecord(self):
        """Read/write info for 2-D meshes."""
        raise NotImplementedError(
            "2-D geometry not yet implemented in GEODST reader/writer"
        )

    def _rw4DRecord(self):
        """Read/write 3-D coarse mesh boundaries and fine mesh intervals."""
        with self.createRecord() as record:

            self._geom.xmesh = record.rwList(
                self._geom.xmesh, "double", self._metadata["NCINTI"] + 1
            )
            self._geom.ymesh = record.rwList(
                self._geom.ymesh, "double", self._metadata["NCINTJ"] + 1
            )
            self._geom.zmesh = record.rwList(
                self._geom.zmesh, "double", self._metadata["NCINTK"] + 1
            )
            self._geom.iintervals = record.rwList(
                self._geom.iintervals, "int", self._metadata["NCINTI"]
            )
            self._geom.jintervals = record.rwList(
                self._geom.jintervals, "int", self._metadata["NCINTJ"]
            )
            self._geom.kintervals = record.rwList(
                self._geom.kintervals, "int", self._metadata["NCINTK"]
            )

    def _rw5DRecord(self):
        """Read/write Geometry data from 5D record."""
        with self.createRecord() as record:
            self._geom.regionVolumes = record.rwList(
                self._geom.regionVolumes, "float", self._metadata["NREG"]
            )
            self._geom.bucklings = record.rwList(
                self._geom.bucklings, "float", self._metadata["NBS"]
            )
            self._geom.boundaryConstants = record.rwList(
                self._geom.boundaryConstants, "float", self._metadata["NBCS"]
            )
            self._geom.internalBlackBoundaryConstants = record.rwList(
                self._geom.internalBlackBoundaryConstants,
                "float",
                self._metadata["NIBCS"],
            )
            self._geom.zonesWithBlackAbs = record.rwList(
                self._geom.zonesWithBlackAbs, "int", self._metadata["NZWBB"]
            )
            self._geom.zoneClassifications = record.rwList(
                self._geom.zoneClassifications, "int", self._metadata["NZONE"]
            )
            self._geom.regionZoneNumber = record.rwList(
                self._geom.regionZoneNumber, "int", self._metadata["NREG"]
            )

    def _rw6DRecord(self):
        """Read/write region assignments to coarse mesh interval."""
        if self._geom.coarseMeshRegions is None:
            # initialize all-zeros here before reading now that we
            # have the matrix dimension metadata available.
            self._geom.coarseMeshRegions = numpy.zeros(
                (
                    self._metadata["NCINTI"],
                    self._metadata["NCINTJ"],
                    self._metadata["NCINTK"],
                ),
                dtype=numpy.int16,
            )
        for ki in range(self._metadata["NCINTK"]):
            with self.createRecord() as record:
                self._geom.coarseMeshRegions[:, :, ki] = record.rwIntMatrix(
                    self._geom.coarseMeshRegions[:, :, ki],
                    self._metadata["NCINTJ"],
                    self._metadata["NCINTI"],
                )

    def _rw7DRecord(self):
        """Read/write region assignments to fine mesh interval."""
        if self._geom.fineMeshRegions is None:
            # initialize all-zeros here before reading now that we
            # have the matrix dimension metadata available.
            self._geom.fineMeshRegions = numpy.zeros(
                (
                    self._metadata["NINTI"],
                    self._metadata["NINTJ"],
                    self._metadata["NINTK"],
                ),
                dtype=numpy.int16,
            )
        for ki in range(self._metadata["NINTK"]):
            with self.createRecord() as record:
                self._geom.fineMeshRegions[:, :, ki] = record.rwIntMatrix(
                    self._geom.fineMeshRegions[:, :, ki],
                    self._metadata["NINTJ"],
                    self._metadata["NINTI"],
                )


readBinary = GeodstStream.readBinary
readAscii = GeodstStream.readAscii
writeBinary = GeodstStream.writeBinary
writeAscii = GeodstStream.writeAscii
