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
Read/write a CCCC PWDINT power density definition file.

PWDINT files power density at mesh intervals.

File format definition is from [CCCC-IV]_.

Examples
--------
>>> pwr = pwdint.readBinary("PWDINT")
>>> pwdint.writeBinary(pwr, "PWDINT2")

"""

import numpy as np

from armi.nuclearDataIO import cccc

PWDINT = "PWDINT"

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


class PwdintData(cccc.DataContainer):
    """
    Data representation that can be read from or written to a PWDINT file.

    This contains a mapping from the i,j,k GEODST mesh to power density
    in Watts/cm^3.
    """

    def __init__(self):
        cccc.DataContainer.__init__(self)
        self.powerDensity = np.array([])


class PwdintStream(cccc.StreamWithDataContainer):
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

    @staticmethod
    def _getDataContainer() -> PwdintData:
        return PwdintData()

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
        """Read/write File specifications on 1D record."""
        with self.createRecord() as record:
            self._metadata.update(record.rwImplicitlyTypedMap(FILE_SPEC_1D_KEYS, self._metadata))

    def _rw2DRecord(self):
        """Read/write power density by mesh point."""
        imax = self._metadata["NINTI"]
        jmax = self._metadata["NINTJ"]
        kmax = self._metadata["NINTK"]
        nblck = self._metadata["NBLOK"]
        if self._data.powerDensity.size == 0:
            # initialize all-zeros here before reading now that we
            # have the matrix dimension metadata available.
            self._data.powerDensity = np.zeros(
                (imax, jmax, kmax),
                dtype=np.float32,
            )
        for ki in range(kmax):
            for bi in range(nblck):
                jL, jU = cccc.getBlockBandwidth(bi + 1, jmax, nblck)
                with self.createRecord() as record:
                    self._data.powerDensity[:, jL : jU + 1, ki] = record.rwMatrix(
                        self._data.powerDensity[:, jL : jU + 1, ki],
                        jU - jL + 1,
                        imax,
                    )


readBinary = PwdintStream.readBinary
readAscii = PwdintStream.readAscii
writeBinary = PwdintStream.writeBinary
writeAscii = PwdintStream.writeAscii
