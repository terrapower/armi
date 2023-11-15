# Copyright 2023 TerraPower, LLC
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
Module for reading from and writing to DIF3D files, which are module dependent
binary inputs for the DIF3D code.
"""

from armi import runLog
from armi.nuclearDataIO import cccc


FILE_SPEC_2D_PARAMS = (
    [
        "IPROBT",
        "ISOLNT",
        "IXTRAP",
        "MINBSZ",
        "NOUTMX",
        "IRSTRT",
        "LIMTIM",
        "NUPMAX",
        "IOSAVE",
        "IOMEG1",
        "INRMAX",
        "NUMORP",
        "IRETRN",
    ]
    + [f"IEDF{e}" for e in range(1, 11)]
    + [
        "NOUTBQ",
        "I0FLUX",
        "NOEDIT",
        "NOD3ED",
        "ISRHED",
        "NSN",
        "NSWMAX",
        "NAPRX",
        "NAPRXZ",
        "NFMCMX",
        "NXYSWP",
        "NZSWP",
        "ISYMF",
        "NCMRZS",
        "ISEXTR",
        "NPNO",
        "NXTR",
        "IOMEG2",
        "IFULL",
        "NVFLAG",
        "ISIMPL",
        "IWNHFL",
        "IPERT",
        "IHARM",
    ]
)

FILE_SPEC_3D_PARAMS = [
    "EPS1",
    "EPS2",
    "EPS3",
    "EFFK",
    "FISMIN",
    "PSINRM",
    "POWIN",
    "SIGBAR",
    "EFFKQ",
    "EPSWP",
] + [f"DUM{e}" for e in range(1, 21)]

TITLE_RANGE = 11


class Dif3dData(cccc.DataContainer):
    def __init__(self):
        cccc.DataContainer.__init__(self)

        self.twoD = {e: None for e in FILE_SPEC_2D_PARAMS}
        self.threeD = {e: None for e in FILE_SPEC_3D_PARAMS}
        self.fourD = None
        self.fiveD = None


class Dif3dStream(cccc.StreamWithDataContainer):
    """Tool to read and write DIF3D files.

    .. impl:: Tool to read and write DIF3D files.
        :id: I_ARMI_NUCDATA_DIF3D
        :implements: R_ARMI_NUCDATA_DIF3D
    """

    @staticmethod
    def _getDataContainer() -> Dif3dData:
        return Dif3dData()

    def _rwFileID(self) -> None:
        """
        Record for file identification information.

        The parameters are stored as a dictionary under the attribute `metadata`.
        """
        with self.createRecord() as record:
            for param in ["HNAME", "HUSE1", "HUSE2"]:
                self._metadata[param] = record.rwString(self._metadata[param], 8)
            self._metadata["VERSION"] = record.rwInt(self._metadata["VERSION"])

    def _rw1DRecord(self) -> None:
        """
        Record for problem title, storage, and dump specifications.

        The parameters are stored as a dictionary under the attribute `metadata`.
        """
        with self.createRecord() as record:
            for i in range(TITLE_RANGE):
                param = f"TITLE{i}"
                self._metadata[param] = record.rwString(self._metadata[param], 8)
            self._metadata["MAXSIZ"] = record.rwInt(self._metadata["MAXSIZ"])
            self._metadata["MAXBLK"] = record.rwInt(self._metadata["MAXBLK"])
            self._metadata["IPRINT"] = record.rwInt(self._metadata["IPRINT"])

    def _rw2DRecord(self) -> None:
        """
        Record for DIF3D integer control parameters.

        The parameters are stored as a dictionary under the attribute `twoD`.
        """
        with self.createRecord() as record:
            for param in FILE_SPEC_2D_PARAMS:
                self._data.twoD[param] = record.rwInt(self._data.twoD[param])

    def _rw3DRecord(self) -> None:
        """
        Record for convergence criteria and other sundry floating point data (such as
        k-effective).

        The parameters are stored as a dictionary under the attribute `threeD`.
        """
        with self.createRecord() as record:
            for param in FILE_SPEC_3D_PARAMS:
                self._data.threeD[param] = record.rwDouble(self._data.threeD[param])

    def _rw4DRecord(self) -> None:
        """
        Record for the optimum overrelaxation factors. This record is only present when
        using DIF3D-FD and if `NUMORP` is greater than 0.

        The parameters are stored as a dictionary under the attribute `fourD`. This
        could be changed into a list in the future since this record represents groupwise
        data.
        """
        if self._data.twoD["NUMORP"] != 0:
            omegaParams = [f"OMEGA{e}" for e in range(1, self._data.twoD["NUMORP"] + 1)]

            with self.createRecord() as record:
                # Initialize the record if we're reading
                if self._data.fourD is None:
                    self._data.fourD = {omegaParam: None for omegaParam in omegaParams}

                for omegaParam in omegaParams:
                    self._data.fourD[omegaParam] = record.rwDouble(
                        self._data.fourD[omegaParam]
                    )

    def _rw5DRecord(self) -> None:
        """
        Record for the axial coarse mesh rebalancing boundaries. Coarse mesh balancing is
        disabled in DIF3D-VARIANT, so this record is only relevant for DIF3D-Nodal. This
        record is only present if `NCMRZS` is greater than 0.

        The parameters are stored as a dictionary under the attribute `fiveD`.
        """
        if self._data.twoD["NCMRZS"] != 0:
            zcmrcParams = [f"ZCMRC{e}" for e in range(1, self._data.twoD["NCMRZS"] + 1)]
            nzintsParams = [
                f"NZINTS{e}" for e in range(1, self._data.twoD["NCMRZS"] + 1)
            ]

            with self.createRecord() as record:
                # Initialize the record if we're reading
                if self._data.fiveD is None:
                    self._data.fiveD = {zcmrcParam: None for zcmrcParam in zcmrcParams}
                    self._data.fiveD.update(
                        {nzintsParam: None for nzintsParam in nzintsParams}
                    )

                for zcmrcParam in zcmrcParams:
                    self._data.fiveD[zcmrcParam] = record.rwDouble(
                        self._data.fiveD[zcmrcParam]
                    )
                for nzintsParam in nzintsParams:
                    self._data.fiveD[nzintsParam] = record.rwInt(
                        self._data.fiveD[nzintsParam]
                    )

    def readWrite(self):
        """Reads or writes metadata and data from 5 records."""
        msg = f"{'Reading' if 'r' in self._fileMode else 'Writing'} DIF3D binary data {self}"
        runLog.info(msg)

        self._rwFileID()
        self._rw1DRecord()
        self._rw2DRecord()
        self._rw3DRecord()
        self._rw4DRecord()
        self._rw5DRecord()


readBinary = Dif3dStream.readBinary
readAscii = Dif3dStream.readAscii
writeBinary = Dif3dStream.writeBinary
writeAscii = Dif3dStream.writeAscii
