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
Reads and writes region and composition label data from a LABELS interface file.

LABELS files are produced by DIF3D/VARIANT. They are very similar in structure
and format to CCCC files but are not officially in the CCCC documents.

The file structure is listed here::

        RECORD TYPE                        PRESENT IF
        ===============================    ================
        FILE IDENTIFICATION                ALWAYS
        SPECIFICATIONS                     ALWAYS
        LABEL AND AREA DATA                ALWAYS
        FINITE-GEOMETRY TRANSVERSE         NHTS1.GT.0 OR
          DISTANCES                         NGTS2.GT.0
        NUCLIDE SET LABELS                 NSETS.GT.1
        ALIAS ZONE LABELS                  NALIAS.GT.0
        GENERAL CONTROL-ROD MODEL DATA     NBANKS.GT.0

 ***********(REPEAT FOR ALL BANKS)
 *      CONTROL-ROD BANK DATA              NBANKS.GT.0
 *
 *  *******(REPEAT FOR ALL RODS IN BANK)
 *  *   CONTROL-ROD CHANNEL DATA           (LLCHN+LLROD+MMESH).GT.0
 **********
        BURNUP DEPENDENT CROSS SECTION     NVARY.GT.0
          SPECIFICATIONS
        BURNUP DEPENDENT GROUPS            MAXBRN.GT.0
        BURNUP DEPENDENT FITTING           MAXORD.GT.0
          COEFFICIENTS


Reference: [DIF3D]_.

Examples
--------
>>> labelData = LabelStream.readBinary("LABELS")
"""

from armi import runLog
from armi.nuclearDataIO import cccc

LABELS = "LABELS"

FILE_SPEC_1D_KEYS = [
    "numZones",
    "numRegions",
    "numAreas",
    "numRegionAreaAssignments",
    "numHalfHeightsDirection1",
    "numHalfHeightsDirection2",
    "numNuclideSets",
    "numZoneAliases",
    "numTrianglesPerHex",
    "numHexagonalRings",
    "numControlRodChannels",
    "numControlRodBanks",
    "numAxialFineMeshBins",
    "maxControlRodBankTimes",
    "maxControlRodsPerBank",
    "maxControlRodsMeshes",
    "maxControlRodPieces",
    "maxControlRodChannels",
    "numBurnupDependentIsotopes",
    "maxBurnupDependentGroups",
    "maxBurnupPolynomialOrder",
    "modelDimensions",
]


class LabelsData(cccc.DataContainer):
    """
    Data structure containing various region, zone, area, nuclide labels.

    This is the data structure that is read from or written to a LABELS file.
    """

    def __init__(self):
        cccc.DataContainer.__init__(self)
        self.regionLabels = []
        self.zoneLabels = []
        self.areaLabels = []
        self.regionAreaAssignments = []
        self.halfHeightsDirection1 = []
        self.halfHeightsDirection2 = []
        self.extrapolationDistance1 = []
        self.extrapolationDistance2 = []
        self.nuclideSetLabels = []
        self.aliasZoneLabels = []


class LabelsStream(cccc.StreamWithDataContainer):
    """
    Class for reading and writing the LABELS interface file produced by DIF3D/VARIANT.

    Notes
    -----
    Contains region and composition labels, area data, half heights, nuclide set labels, alias zone labels,
    control-rod model data, and burnup dependent cross section data.

    See Also
    --------
    armi.nuclearDataIO.cccc.compxs
    """

    @staticmethod
    def _getDataContainer() -> LabelsData:
        return LabelsData()

    def readWrite(self):
        runLog.info("{} LABELS data {}".format("Reading" if "r" in self._fileMode else "Writing", self))
        self._rwFileID()
        self._rw1DRecord()
        self._rw2DRecord()
        if self._metadata["numHalfHeightsDirection1"] > 0 or self._metadata["numHalfHeightsDirection2"] > 0:
            self._rw3DRecord()
        if self._metadata["numNuclideSets"] > 1:
            self._rw4DRecord()
        if self._metadata["numZoneAliases"] > 0:
            self._rw5DRecord()
        if self._metadata["numControlRodBanks"] > 0:
            self._rw6DRecord()
            self._rw7DRecord()
            self._rw8DRecord()
        if self._metadata["numBurnupDependentIsotopes"] > 0:
            self._rw9DRecord()
        if self._metadata["maxBurnupDependentGroups"] > 0:
            self._rw10DRecord()
        if self._metadata["maxBurnupPolynomialOrder"] > 0:
            self._rw11DRecord()

    def _rwFileID(self):
        with self.createRecord() as record:
            for name in ["hname", "huse", "huse2"]:
                self._metadata[name] = record.rwString(self._metadata[name], 8)
            self._metadata["version"] = record.rwInt(self._metadata["version"])

    def _rw1DRecord(self):
        """Read/write the file specification data."""
        with self.createRecord() as record:
            for param in FILE_SPEC_1D_KEYS:
                self._metadata[param] = record.rwInt(self._metadata[param])
            self._metadata["dummy"] = record.rwList(self._metadata["dummy"], "int", 2)

    def _rw2DRecord(self):
        """Read/write the label and area data."""
        with self.createRecord() as record:
            self._data.zoneLabels = record.rwList(self._data.zoneLabels, "string", self._metadata["numZones"], 8)
            self._data.regionLabels = record.rwList(
                self._data.regionLabels,
                "string",
                self._metadata["numRegions"],
                8,
            )
            self._data.areaLabels = record.rwList(self._data.areaLabels, "string", self._metadata["numAreas"], 8)
            self._data.regionAreaAssignments = record.rwList(
                self._data.regionAreaAssignments,
                "string",
                self._metadata["numRegionAreaAssignments"],
                8,
            )

    def _rw3DRecord(self):
        """Read/write the finite-geometry transverse distances."""
        with self.createRecord() as record:
            self._data.halfHeightsDirection1 = record.rwList(
                self._data.halfHeightsDirection1,
                "float",
                self._metadata["numHalfHeightsDirection1"],
            )
            self._data.extrapolationDistance1 = record.rwList(
                self._data.extrapolationDistance1,
                "float",
                self._metadata["numHalfHeightsDirection1"],
            )
            self._data.halfHeightsDirection2 = record.rwList(
                self._data.halfHeightsDirection2,
                "float",
                self._metadata["numHalfHeightsDirection2"],
            )
            self._data.extrapolationDistance2 = record.rwList(
                self._data.extrapolationDistance2,
                "float",
                self._metadata["numHalfHeightsDirection2"],
            )

    def _rw4DRecord(self):
        """Read/write the nuclide labels."""
        with self.createRecord() as record:
            self._data.nuclideSetLabels = record.rwList(
                self._data.nuclideSetLabels,
                "string",
                self._metadata["numNuclideSets"],
                8,
            )

    def _rw5DRecord(self):
        """Read/write the zone aliases."""
        with self.createRecord() as record:
            self._data.aliasZoneLabels = record.rwList(
                self._data.aliasZoneLabels,
                "string",
                self._metadata["numZoneAliases"],
                8,
            )

    def _rw6DRecord(self):
        """Read/write the general control-rod model data."""
        raise NotImplementedError("Control rod data not implemented")

    def _rw7DRecord(self):
        """Read/write the control-rod bank data."""
        raise NotImplementedError("Control rod data not implemented")

    def _rw8DRecord(self):
        """Read/write the control-rod channel data."""
        raise NotImplementedError("Control rod data not implemented")

    def _rw9DRecord(self):
        """Read/write the burnup-dependent cross section specifications."""
        raise NotImplementedError("BU dependent XS data not implemented")

    def _rw10DRecord(self):
        """Read/write the burnup-dependent group data."""
        raise NotImplementedError("BU dependent XS data not implemented")

    def _rw11DRecord(self):
        """Read/write the burnup-dependent fitting coefficient data."""
        raise NotImplementedError("BU dependent XS data not implemented")


readBinary = LabelsStream.readBinary
readAscii = LabelsStream.readAscii
writeBinary = LabelsStream.writeBinary
writeAscii = LabelsStream.writeAscii
