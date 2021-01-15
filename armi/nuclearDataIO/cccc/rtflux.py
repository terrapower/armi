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
Read and write the Regular Total flux from a RTFLUX CCCC interface file.

RTFLUX is a CCCC standard data file for storing multigroup total flux on a mesh of any
geometry type. It is defined in [CCCC-IV]_.

ATFLUX is in the same format but holds adjoint flux rather than regular flux.

Examples
--------
>>> flux = rtflux.RtfluxStream.readBinary("RTFLUX")
>>> rtflux.RtfluxStream.writeBinary(flux, "RTFLUX2")
>>> adjointFlux = rtflux.AtfluxStream.readBinary("ATFLUX")

See Also
--------
NHFLUX
    Reads/write nodal hex flux moments

RZFLUX
    Reads/writes total fluxes from zones
"""
import math

import numpy
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection

from armi.nuclearDataIO import cccc

RTFLUX = "RTFLUX"
ATFLUX = "ATFLUX"

# See CCCC-IV documentation for definitions
FILE_SPEC_1D_KEYS = (
    "NDIM",
    "NGROUP",
    "NINTI",
    "NINTJ",
    "NINTK",
    "ITER",
    "EFFK",
    "POWER",
    "NBLOK",
)


class RtfluxData(cccc.DataContainer):
    """
    Multigroup flux as a function of i,j,k and g indices.

    The metadata also contains the power and k-eff.

    This is the data structure that is read from or written to a RTFLUX file.
    """

    def __init__(self):
        cccc.DataContainer.__init__(self)

        self.groupFluxes: numpy.ndarray = numpy.array([])
        """Maps i,j,k,g indices to total real or adjoint flux in n/cm^2-s"""


class RtfluxStream(cccc.StreamWithDataContainer):
    """
    Stream for reading/writing a RTFLUX or ATFLUX file.

    Parameters
    ----------
    flux : RtfluxData
        Data structure
    fileName: str
        path to RTFLUX file
    fileMode: str
        string indicating if ``fileName`` is being read or written, and
        in ascii or binary format

    """

    @staticmethod
    def _getDataContainer() -> RtfluxData:
        return RtfluxData()

    def readWrite(self):
        """
        Step through the structure of the file and read/write it.
        """
        self._rwFileID()
        self._rw1DRecord()
        if self._metadata["NDIM"] == 1:
            self._rw2DRecord()
        elif self._metadata["NDIM"] >= 2:
            self._rw3DRecord()
        else:
            raise ValueError(f"Invalid NDIM value {self._metadata['NDIM']} in {self}.")

    def _rwFileID(self):
        """
        Read/write file id record.

        Notes
        -----
        The username, version, etc are embedded in this string but it's
        usually blank.
        """
        with self.createRecord() as record:
            self._metadata["label"] = record.rwString(self._metadata["label"], 28)

    def _rw1DRecord(self):
        """
        Read/write File specifications on 1D record.
        """
        with self.createRecord() as record:
            self._metadata.update(
                record.rwImplicitlyTypedMap(FILE_SPEC_1D_KEYS, self._metadata)
            )

    def _rw2DRecord(self):
        """
        Read/write 1-dimensional regular total flux.
        """
        raise NotImplementedError("1-D RTFLUX files are not yet implemented.")

    def _rw3DRecord(self):
        """
        Read/write multi-dimensional regular total flux.

        The records contain blocks of values in the i-j planes.
        """

        ng = self._metadata["NGROUP"]
        imax = self._metadata["NINTI"]
        jmax = self._metadata["NINTJ"]
        kmax = self._metadata["NINTK"]
        nblck = self._metadata["NBLOK"]

        if self._data.groupFluxes.size == 0:
            self._data.groupFluxes = numpy.zeros((imax, jmax, kmax, ng))

        for gi in range(ng):
            gEff = self.getEnergyGroupIndex(gi)
            for k in range(kmax):
                # data in i-j plane may be blocked
                for bi in range(nblck):
                    # compute blocking parameters
                    jLow, jUp = cccc.getBlockBandwidth(bi + 1, jmax, nblck)
                    numZonesInBlock = jUp - jLow + 1
                    with self.createRecord() as record:
                        # pass in shape in fortran (read) order
                        self._data.groupFluxes[
                            :, jLow : jUp + 1, k, gEff
                        ] = record.rwDoubleMatrix(
                            self._data.groupFluxes[:, jLow : jUp + 1, k, gEff],
                            numZonesInBlock,
                            imax,
                        )

    def getEnergyGroupIndex(self, g):
        r"""
        Real fluxes stored in RTFLUX have "normal" (or "forward") energy groups.
        Also see the subclass method ATFLUX.getEnergyGroupIndex().

        0 based, so if NG=33 and you want the third group, this return 2.
        """
        return g


class AtfluxStream(RtfluxStream):
    r"""
    This is a subclass for the ATFLUX file, which is identical in format to the RTFLUX file except
    that it contains the adjoint flux and has reversed energy group ordering.
    """

    def getEnergyGroupIndex(self, g):
        r"""
        Adjoint fluxes stored in ATFLUX have "reversed" (or "backward") energy groups.

        0 based, so if NG=33 and you want the third group (g=2), this returns 30.
        """

        ng = self._metadata["NGROUP"]
        return ng - g - 1


def getFDFluxReader(adjointFlag):
    r"""
    Returns the appropriate DIF3D FD flux binary file reader class,
    either RTFLUX (real) or ATFLUX (adjoint).
    """

    if adjointFlag:
        return AtfluxStream
    else:
        return RtfluxStream


def plotTriangleFlux(
    rtfluxData: RtfluxData,
    axialZ,
    energyGroup,
    hexPitch=math.sqrt(3.0),
    hexSideSubdivisions=1,
    imgFileExt=".png",
):
    """
    Plot region total flux for one core-wide axial slice on triangular/hexagonal geometry.

    .. warning:: This will run on non-triangular meshes but will look wrong.

    Parameters
    ----------
    rtfluxData : RtfluxData object
        The RTFLUX/ATFLUX data object containing all read file data.
        Alternatively, this could be a FIXSRC file object,
        but only if FIXSRC.fixSrc is first renamed FIXSRC.triangleFluxes.

    axialZ : int
        The DIF3D axial node index of the core-wide slice to plot.

    energyGroup : int
        The energy group index to plot.

    hexPitch: float, optional
        The flat-to-flat hexagonal assembly pitch in this core.
        By default, it is sqrt(3) so that the triangle edge length is 1 if hexSideSubdivisions=1.

    hexSideSubdivisions : int, optional
        By default, it is 1 so that the triangle edge length is 1 if hexPitch=sqrt(3).

    imgFileExt : str, optional
        The image file extension.

    """

    triHeightInCm = hexPitch / 2.0 / hexSideSubdivisions
    sideLengthInCm = triHeightInCm / (math.sqrt(3.0) / 2.0)
    s2InCm = sideLengthInCm / 2.0

    vals = rtfluxData.groupFluxes[:, :, axialZ, energyGroup]
    patches = []
    colorVals = []
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            flipped = i % 2  # use (i+j)%2 for rectangular meshing
            xInCm = s2InCm * (i - j)
            yInCm = triHeightInCm * j + sideLengthInCm / 2.0 / math.sqrt(3) * (
                1 + flipped
            )

            flux = vals[i][j]

            if flux:

                triangle = mpatches.RegularPolygon(
                    (xInCm, yInCm),
                    3,
                    sideLengthInCm / math.sqrt(3),
                    orientation=math.pi * flipped,
                    linewidth=0.0,
                )

                patches.append(triangle)
                colorVals.append(flux)

    collection = PatchCollection(patches, alpha=1.0, linewidths=(0,), edgecolors="none")
    collection.set_array(
        numpy.array(colorVals)
    )  # add color map to this collection ONLY (pins, not ducts)

    plt.figure()
    ax = plt.gca()
    ax.add_collection(collection)
    colbar = plt.colorbar(collection)
    colbar.set_label("n/s/cm$^3$")
    # colbar.set_label('n*cm/s')
    plt.ylabel("cm")
    plt.xlabel("cm")
    ax.autoscale_view()
    plt.savefig("RTFLUX-z" + str(axialZ + 1) + "-g" + str(energyGroup + 1) + imgFileExt)
    plt.close()


if __name__ == "__main__":
    rtflux = RtfluxStream.readBinary("RTFLUX")
    plotTriangleFlux(rtflux, axialZ=10, energyGroup=4)
