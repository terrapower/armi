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
FIXSRC is a CCCC standard data file for storing multigroup fixed sources on a triangular mesh.

Currently, the FIXSRC writing capability assumes a gamma (not neutron) fixed source problem.
This enables photon transport problems. [CCCC-IV]_
"""

import collections

import numpy as np

from armi import runLog
from armi.nuclearDataIO import cccc


def readBinary(fileName):
    """Read a binary FIXSRC file."""
    with FIXSRC(fileName, "rb", np.zeros((0, 0, 0, 0))) as fs:
        fs.readWrite()
    return fs.fixSrc


def writeBinary(fileName, fixSrcArray):
    """Write fixed source data to a FIXSRC file."""
    with FIXSRC(fileName, "wb", fixSrcArray) as fs:
        fs.readWrite()


class FIXSRC(cccc.Stream):
    """Read or write a binary FIXSRC file from DIF3D fixed source input."""

    def __init__(self, fileName, fileMode, fixSrc):
        """
        Initialize a gamma FIXSRC class for reading or writing a binary FIXSRC file for DIF3D gamma
        fixed source input.

        If the intent is to write a gamma FIXSRC file, the variable FIXSRC.fixSrc, which contains
        to-be-written core-wide multigroup gamma fixed source data, is constructed from an existing
        neutron RTFLUX file.

        Parameters
        ----------
        fileName : str, optional
            The file name of the RTFLUX/ATFLUX binary file to be read.

        fileMode : str, optional
            If 'wb', this class writes a FIXSRC binary file.
            If 'rb', this class reads a preexisting FIXSRC binary file.

        fixSrc : np.ndarray
            Core-wide multigroup gamma fixed-source data.
        """
        cccc.Stream.__init__(self, fileName, fileMode)

        # copied from a sample FIXSRC output from "type 19" DIF3D input
        self.label = "FIXSRC                  "
        self.fileId = 1
        self.fixSrc = fixSrc

        ni, nj, nz, ng = self.fixSrc.shape
        self.fc = collections.OrderedDict(
            [
                ("itype", 0),
                ("ndim", 3),
                ("ngroup", ng),
                ("ninti", ni),
                ("nintj", nj),
                ("nintk", nz),
                ("idists", 1),
                ("ndcomp", 1),
                ("nscomp", 0),
                ("nedgi", 0),
                ("nedgj", 0),
                ("nedjk", 0),
                ("nblok", 1),
            ]
        )

    def readWrite(self):
        """Read or write a binary FIXSRC file for DIF3D fixed source input."""
        runLog.info("{} gamma fixed source file {}".format("Reading" if "r" in self._fileMode else "Writing", self))

        self._rwFileID()
        self._rw1DRecord()

        ng = self.fc["ngroup"]
        nz = self.fc["nintk"]
        for g in range(ng):
            for z in range(nz):
                self._rw3DRecord(g, z)

    def _rwFileID(self):
        """Read file identification information."""
        with self.createRecord() as fileIdRecord:
            self.label = fileIdRecord.rwString(self.label, 24)
            self.fileId = fileIdRecord.rwInt(self.fileId)

    def _rw1DRecord(self):
        """Read/write parameters from/to the FIXSRC 1D block (file control)."""
        with self.createRecord() as record:
            for var in self.fc.keys():
                self.fc[var] = record.rwInt(self.fc[var])

    def _rw3DRecord(self, g, z):
        """
        Read/write fixed source data from 3D block records.

        Parameters
        ----------
        g : int
            The gamma energy group index.

        z : int
            The DIF3D axial node index.
        """
        with self.createRecord() as record:
            ni = self.fc["ninti"]
            nj = self.fc["nintj"]

            for j in range(nj):
                for i in range(ni):
                    self.fixSrc[i, j, z, g] = record.rwDouble(self.fixSrc[i, j, z, g])
