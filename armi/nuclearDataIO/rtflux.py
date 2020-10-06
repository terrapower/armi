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

from armi.nuclearDataIO import cccc, nuclearFileMetadata
from armi.reactor import locations


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


class RtfluxData:
    """
    Multigroup flux as a function of i,j,k and g indices.

    The metadata also contains the power and k-eff.

    This is the data structure that is read from or written to a RTFLUX file.
    """

    def __init__(self):
        # Need Metadata subclass for default keys
        self.metadata = nuclearFileMetadata._Metadata()

        self.groupFluxes: numpy.ndarray = numpy.array([])
        """Maps i,j,k,g indices to total real or adjoint flux in n/cm^2-s"""


class RtfluxStream(cccc.Stream):
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

    def __init__(self, flux: RtfluxData, fileName: str, fileMode: str):
        cccc.Stream.__init__(self, fileName, fileMode)
        self._flux = flux
        self._metadata = self._getFileMetadata()

    def _getFileMetadata(self):
        return self._flux.metadata

    @classmethod
    def _read(cls, fileName: str, fileMode: str) -> RtfluxData:
        """Specialize the parent by adding a fresh RtfluxData"""
        flux = RtfluxData()
        return cls._readWrite(
            flux,
            fileName,
            fileMode,
        )

    # pylint: disable=arguments-differ
    @classmethod
    def _write(cls, flux: RtfluxData, fileName: str, fileMode: str):
        return cls._readWrite(flux, fileName, fileMode)

    @classmethod
    def _readWrite(cls, flux: RtfluxData, fileName: str, fileMode: str) -> RtfluxData:
        with RtfluxStream(flux, fileName, fileMode) as rw:
            rw.readWrite()
        return flux

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
            for key in FILE_SPEC_1D_KEYS:
                # ready for some implicit madness from the FORTRAN 77 days?
                if key[0] in cccc.IMPLICIT_INT:
                    self._metadata[key] = record.rwInt(self._metadata[key])
                else:
                    self._metadata[key] = record.rwFloat(self._metadata[key])

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
        nblck = self._metadata["NBLOK"]  # data blocking factor

        if self._flux.groupFluxes.size == 0:
            self._flux.groupFluxes = numpy.zeros((imax, jmax, kmax, ng))

        for gi in range(ng):
            gEff = self.getEnergyGroupIndex(gi)
            for k in range(kmax):
                # data in i-j plane may be blocked
                for bi in range(nblck):
                    # compute blocking parameters
                    m = bi + 1
                    blockRatio = (jmax - 1) // nblck + 1
                    jLow = (m - 1) * blockRatio  # subtracted 1
                    jUp = m * blockRatio
                    jUp = min(jmax, jUp) - 1  # subtracted 1
                    numZonesInBlock = jUp - jLow + 1
                    with self.createRecord() as record:
                        # pass in shape in fortran (read) order
                        # pylint: disable=protected-access
                        self._flux.groupFluxes[
                            :, jLow : jUp + 1, k, gEff
                        ] = record._rwMatrix(
                            self._flux.groupFluxes[:, jLow : jUp + 1, k, gEff],
                            record.rwDouble,
                            numZonesInBlock,
                            imax,
                        )

    def getEnergyGroupIndex(self, g):
        r"""
        Real fluxes stored in RTFLUX have "normal" (or "forward") energy groups.
        Also see the subclass method ATFLUX.getEnergyGroupIndex().
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


def assignARMIBlockFluxFromRTFLUX(r, adjoint=False):
    """
    Read whichever RTFLUX (real) or ATFLUX (adjoint) files exist in the current
    case directory. Then average the finite difference triangle fluxes in each
    ARMI block and assign the resulting multigroup flux to the ARMI block object.
    This can be convenient when the DIF3D output reader fails for any reason
    while the RTFLUX/ATFLUX DIF3D output files were created.

    Note: It is the user's responsibility to ensure that the correct RTFLUX/ATFLUX
    files exist in the case directory. If they don't exist, this method will fail.
    If the wrong ones exist, this method will either fail or assign wrong fluxes
    to ARMI blocks.

    WARNING: This function has never been verified to work correctly. Therefore,
    use it at your own risk.

    Parameters
    ----------
    r : Reactor object
        A reactor object with the same geometry as the RTFLUX/ATFLUX file.

    adjoint : bool, optional
        If True, block adjoint fluxes are assigned from ATFLUX data.
        If False, block real fluxes are assigned from RTFLUX data.

    """

    if adjoint:
        fName = "ATFLUX"
    else:
        fName = "RTFLUX"

    nodalFluxReader = getFDFluxReader(adjoint)
    rtflux = nodalFluxReader.readBinary(fName)

    hexFlux = rtflux.groupFluxes  # multigroup triangle fluxes

    i_geodst_max = rtflux.metadata["NINTI"]
    j_geodst_max = rtflux.metadata["NINTJ"]
    nz = rtflux.metadata["NINTK"]  # number of axial nodes

    axMeshArray = numpy.array(r.core.p.axialMesh)  # cm

    for a in r.core.getAssemblies():
        i, j = a.spatialLocator.getRingPos()  # hex indices (i, j) = (ring, pos)

        rotated = []
        i_geodst, j_geodst, rotated = r.core.getDif3dGeodstIndicesFromArmiIndices(
            r.core.isFullCore,
            i,
            j,
            i_geodst_max,
            j_geodst_max,
            rotated,
            rotatedFlag=False,
        )

        bIndex = 0
        b = a[bIndex]
        zTopInCm = b.p.ztop

        for z in range(nz):
            heightInCm = axMeshArray[z + 1] - axMeshArray[z]
            axMeshMidInCm = axMeshArray[z] + heightInCm / 2.0

            if axMeshMidInCm > zTopInCm:
                bIndex += 1
                b = a[bIndex]
                zTopInCm = b.p.ztop

                volumeIntegratedFlux = hexFlux[i_geodst - 1, j_geodst - 1, z, :]
                if adjoint:
                    b.p.adjMgFlux = volumeIntegratedFlux
                else:
                    b.p.mgFlux = volumeIntegratedFlux


def getDif3dGeodstIndicesFromArmiIndices(
    fullcore, i, j, i_geodst_max, j_geodst_max, rotated, rotatedFlag=True
):
    r"""
    Convert an ARMI (i, j) = (ring, position) assembly index pair into a DIF3D (i_geodst, j_geodst)
    assembly index pair. This allows one to locate an ARMI assembly in the SASSYS/DIF3D-K
    text output file..

    Parameters
    ----------
    i : int
        The ARMI hexagonal assembly ring index (starts with 0, not 1).

    j : int
        The ARMI hexagonal assembly position index within ring i (starts with 0, not 1).

    i_geodst_max : int
        The maximum number of "first dimension" hexagonal mesh cells in this DIF3D(-K) core model.
        This number can be found in the same line as the string 'NO. OF FIRST DIMENSION MESH INTERVALS'
        in the SASSYS/DIF3D-K output text file. GEODST is a common hexagonal assembly indexing
        scheme in DIF3D(-K).

    j_geodst_max : int
        The minimum number of "second dimension" hexagonal mesh cells in this DIF3D(-K) core model.
        This number can be found in the same line as the string 'NO. OF SECOND DIMENSION MESH INTERVALS'
        in the SASSYS/DIF3D-K output text file. GEODST is a common hexagonal assembly indexing
        scheme in DIF3D(-K).

    rotated : list of ints
        Stores whether or not each assembly has been rotated in its transformation from
        DIF3D "four color" nodal to ARMI nodal hex orderings. This is a remnant/vestige
        of previously-existing funcationality in fluxRecon.

    rotatedFlag : Boolean, optional
        Whether or not THIS assembly has been rotated in its transformation from
        DIF3D "four color" nodal to ARMI nodal hex orderings. This is a remnant/vestige
        of previously-existing funcationality in fluxRecon.

    Returns
    -------
    i_geodst+1 : int
        The DIF3D-K hexagonal assembly "first dimension" index in the GEODST indexing scheme.

    j_geodst+1 : int
        The DIF3D-K hexagonal assembly "second dimension" index in the GEODST indexing scheme.

    rotated : list of ints
        Stores whether or not each assembly has been rotated in its transformation from
        DIF3D "four color" nodal to ARMI nodal hex orderings. This is a remnant/vestige
        of previously-existing funcationality in fluxRecon.

    """

    if fullcore:

        aSymm = locations.HexLocation(i + 1, j + 1)

        i_geodst, j_geodst = aSymm.indices()  # MCNP GEODST indices

        i_geodst = i_geodst + j_geodst + (i_geodst_max - 1) / 2  # DIF3D GEODST indices
        j_geodst = j_geodst + (j_geodst_max - 1) / 2  # DIF3D GEODST indices

        if rotatedFlag:
            rotated[i][j] = 0  # no assembly rotation in full core (awesome!)

    else:  # third core symmetry (no sixth core capability here yet)
        # get list of two symmetric identicals
        threeSymmetricIdenticals = locations.HexLocation(
            i + 1, j + 1
        ).getSymmetricIdenticalsThird()
        # add assembly itself, so there are three symmetric identicals in one list
        threeSymmetricIdenticals.append(locations.HexLocation(i + 1, j + 1))

        symmCount = -1
        i_geodst = -1
        j_geodst = -1
        for aSymm in threeSymmetricIdenticals:
            symmCount = symmCount + 1
            i_geodst, j_geodst = aSymm.indices()  # MCNP GEODST indices

            i_geodst = i_geodst + j_geodst  # DIF3D GEODST indices

            # In DIF3D GEODST, both indices should be positive (except for central hex)
            # When both are positive, we know we've found the correct symmetric identical,
            # which is the existing ARMI assembly location that corresponds to the DIF3D GEODST location.
            if i_geodst > 0 and j_geodst > 0:
                break

        if rotatedFlag:
            # Keep track of which assemblies have been "reflected" over a 1/3 symmetry line (and thus rotated)
            if symmCount == 0:  # rotated by 2/3 counter-clockwise (two k indices)
                rotated[i][j] = 2
            elif symmCount == 1:  # rotated by 1/6 counter-clockwise (one k index)
                rotated[i][j] = 1
            else:  # not rotated
                rotated[i][j] = 0  # just make this zero again to be sure
            if i == 0:
                rotated[i][j] = 0

    return i_geodst + 1, j_geodst + 1, rotated


if __name__ == "__main__":
    rtflux = RtfluxStream.readBinary("RTFLUX")
    plotTriangleFlux(rtflux, axialZ=10, energyGroup=4)
