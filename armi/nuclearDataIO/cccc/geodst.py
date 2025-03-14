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

import numpy as np

from armi.nuclearDataIO import cccc

GEODST = "GEODST"

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


class GeodstData(cccc.DataContainer):
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
        cccc.DataContainer.__init__(self)

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


class GeodstStream(cccc.StreamWithDataContainer):
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

    @staticmethod
    def _getDataContainer() -> GeodstData:
        return GeodstData()

    def readWrite(self):
        """
        Step through the structure of a GEODST file and read/write it.

        Logic to control which records will be present is here, which
        comes directly off the File specification.

        .. impl:: Tool to read and write GEODST files.
            :id: I_ARMI_NUCDATA_GEODST
            :implements: R_ARMI_NUCDATA_GEODST

            Reading and writing GEODST files is performed using the general
            nuclear data I/O functionalities described in
            :need:`I_ARMI_NUCDATA`. Reading/writing a GEODST file is performed
            through the following steps:

            #. Read/write file ID record

            #. Read/write file specifications on 1D record.

            #. Based on the geometry type (``IGOM``), one of following records
               are read/written:

                * Slab (1), cylinder (3), or sphere (3): Read/write 1-D coarse
                  mesh boundaries and fine mesh intervals.
                * X-Y (6), R-Z (7), Theta-R (8), uniform triangular (9),
                  hexagonal (10), or R-Theta (11): Read/write 2-D coarse mesh
                  boundaries and fine mesh intervals.
                * R-Theta-Z (12, 15), R-Theta-Alpha (13, 16), X-Y-Z (14),
                  uniform triangular-Z (17), hexagonal-Z(18): Read/write 3-D
                  coarse mesh boundaries and fine mesh intervals.

            #. If the geometry is not zero-dimensional (``IGOM`` > 0) and
               buckling values are specified (``NBS`` > 0): Read/write geometry
               data from 5D record.

            #. If the geometry is not zero-dimensional (``IGOM`` > 0) and region
               assignments are coarse-mesh-based (``NRASS`` = 0): Read/write
               region assignments to coarse mesh interval.

            #. If the geometry is not zero-dimensional (``IGOM`` > 0) and region
               assignments are fine-mesh-based (``NRASS`` = 1): Read/write
               region assignments to fine mesh interval.
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
        The number 28 was actually obtained from
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
        """Read/write 1-D coarse mesh boundaries and fine mesh intervals."""
        with self.createRecord() as record:
            self._data.xmesh = record.rwList(self._data.xmesh, "double", self._metadata["NCINTI"] + 1)
            self._data.iintervals = record.rwList(self._data.iintervals, "int", self._metadata["NCINTI"])

    def _rw3DRecord(self):
        """Read/write 2-D coarse mesh boundaries and fine mesh intervals."""
        with self.createRecord() as record:
            self._data.xmesh = record.rwList(self._data.xmesh, "double", self._metadata["NCINTI"] + 1)
            self._data.ymesh = record.rwList(self._data.ymesh, "double", self._metadata["NCINTJ"] + 1)
            self._data.iintervals = record.rwList(self._data.iintervals, "int", self._metadata["NCINTI"])
            self._data.jintervals = record.rwList(self._data.jintervals, "int", self._metadata["NCINTJ"])

    def _rw4DRecord(self):
        """Read/write 3-D coarse mesh boundaries and fine mesh intervals."""
        with self.createRecord() as record:
            self._data.xmesh = record.rwList(self._data.xmesh, "double", self._metadata["NCINTI"] + 1)
            self._data.ymesh = record.rwList(self._data.ymesh, "double", self._metadata["NCINTJ"] + 1)
            self._data.zmesh = record.rwList(self._data.zmesh, "double", self._metadata["NCINTK"] + 1)
            self._data.iintervals = record.rwList(self._data.iintervals, "int", self._metadata["NCINTI"])
            self._data.jintervals = record.rwList(self._data.jintervals, "int", self._metadata["NCINTJ"])
            self._data.kintervals = record.rwList(self._data.kintervals, "int", self._metadata["NCINTK"])

    def _rw5DRecord(self):
        """Read/write Geometry data from 5D record."""
        with self.createRecord() as record:
            self._data.regionVolumes = record.rwList(self._data.regionVolumes, "float", self._metadata["NREG"])
            self._data.bucklings = record.rwList(self._data.bucklings, "float", self._metadata["NBS"])
            self._data.boundaryConstants = record.rwList(self._data.boundaryConstants, "float", self._metadata["NBCS"])
            self._data.internalBlackBoundaryConstants = record.rwList(
                self._data.internalBlackBoundaryConstants,
                "float",
                self._metadata["NIBCS"],
            )
            self._data.zonesWithBlackAbs = record.rwList(self._data.zonesWithBlackAbs, "int", self._metadata["NZWBB"])
            self._data.zoneClassifications = record.rwList(
                self._data.zoneClassifications, "int", self._metadata["NZONE"]
            )
            self._data.regionZoneNumber = record.rwList(self._data.regionZoneNumber, "int", self._metadata["NREG"])

    def _rw6DRecord(self):
        """Read/write region assignments to coarse mesh interval."""
        if self._data.coarseMeshRegions is None:
            # initialize all-zeros here before reading now that we
            # have the matrix dimension metadata available.
            self._data.coarseMeshRegions = np.zeros(
                (
                    self._metadata["NCINTI"],
                    self._metadata["NCINTJ"],
                    self._metadata["NCINTK"],
                ),
                dtype=np.int16,
            )
        for ki in range(self._metadata["NCINTK"]):
            with self.createRecord() as record:
                self._data.coarseMeshRegions[:, :, ki] = record.rwIntMatrix(
                    self._data.coarseMeshRegions[:, :, ki],
                    self._metadata["NCINTJ"],
                    self._metadata["NCINTI"],
                )

    def _rw7DRecord(self):
        """Read/write region assignments to fine mesh interval."""
        if self._data.fineMeshRegions is None:
            # initialize all-zeros here before reading now that we
            # have the matrix dimension metadata available.
            self._data.fineMeshRegions = np.zeros(
                (
                    self._metadata["NINTI"],
                    self._metadata["NINTJ"],
                    self._metadata["NINTK"],
                ),
                dtype=np.int16,
            )
        for ki in range(self._metadata["NINTK"]):
            with self.createRecord() as record:
                self._data.fineMeshRegions[:, :, ki] = record.rwIntMatrix(
                    self._data.fineMeshRegions[:, :, ki],
                    self._metadata["NINTJ"],
                    self._metadata["NINTI"],
                )


readBinary = GeodstStream.readBinary
readAscii = GeodstStream.readAscii
writeBinary = GeodstStream.writeBinary
writeAscii = GeodstStream.writeAscii
