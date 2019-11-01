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
RTFLUX is a CCCC standard data file for storing multigroup flux on a triangular mesh.

[CCCC-IV]_
"""
import math

import numpy
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection

from armi.nuclearDataIO import cccc
from armi.reactor import locations


class RTFLUX(cccc.CCCCReader):
    """
    Read a binary RTFLUX or ATFLUX file from DIF3D output.

    While NHFLUX stores nodal flux output data, RTFLUX stores finite difference flux output data.
    While NHFLUX stores data by hexagon, RTFLUX stores data by triangle.
    This can also read ATFLUX, which stores the finite difference adjoint flux output data.
    """

    def __init__(self, fName="RTFLUX"):
        r"""
        Initialize the RTFLUX or ATFLUX reader object.

        Parameters
        ----------
        fName : str, optional
            The file name of the RTFLUX/ATFLUX binary file to be read.

        """
        cccc.CCCCReader.__init__(self, fName)

        self.fc = {}  # file control info (sort of global for this library)
        self.triangleFluxes = []

        self.readFileID()  # Read RTFLUX file ID

    def readAllData(self):
        r"""
        Read multigroup fluxes from the original DIF3D FD triangular-z mesh points.
        RTFLUX contains the real fluxes, while ATFLUX contains the adjoint fluxes.

        """

        # Read basic data parameters (number of energy groups, assemblies, axial nodes, etc.)
        self.read1D()

        # Read the hex ordering map between DIF3D "four color" nodal and DIF3D GEODST
        # Also read index pointers to incoming partial currents on outer reactor surface
        # (these don't belong to any assembly)
        # Incoming partial currents are non-zero due to flux extrapolation
        ng = self.fc["ngroup"]  # number of energy groups
        imax = self.fc[
            "ninti"
        ]  # number of triangular mesh cells in "i" direction (rhombus or rectangle cells)
        jmax = self.fc[
            "nintj"
        ]  # number of triangular mesh cells in "j" direction (rhombus or rectangle cells)
        zmax = self.fc[
            "nintk"
        ]  # number of axial nodes (same for each assembly in DIF3D)

        self.triangleFluxes = numpy.zeros((imax, jmax, zmax, ng))

        for g in range(ng):  # loop through energy groups

            gEff = self.getEnergyGroupIndex(g)

            for z in range(zmax):  # loop through axial nodes
                self.triangleFluxes[
                    :, :, z, gEff
                ] = self.readTriangleFluxes()  # read fluxes on this i-j plane

        self.f.close()

    def read1D(self):
        r"""
        Read parameters from the RTFLUX/ATFLUX 1D block (file control).

        This contains a bunch of single-number integer or double values
        necessary to read all data from the other records of RTFLUX/ATFLUX.
        See the comments following each quantity in the code.

        See Also
        --------
        rtflux.RTFLUX.__init__
        nuclearDataIO.ISOTXS.read1D
        nuclearDataIO.SPECTR.read1D

        """

        record = self.getRecord()

        self.fc[
            "ndim"
        ] = (
            record.getInt()
        )  # number of dimensions of DIF3D mesh nodes (always 3 for a 3D core)
        self.fc["ngroup"] = record.getInt()  # number of energy groups
        self.fc[
            "ninti"
        ] = record.getInt()  # maximum x coordinate index of assemblies (DIF3D GEODST)
        self.fc[
            "nintj"
        ] = record.getInt()  # maximum y coordinate index of assemblies (DIF3D GEODST)
        self.fc[
            "nintk"
        ] = (
            record.getInt()
        )  # number of DIF3D axial mesh nodes (same for all assemblies)
        self.fc[
            "iter"
        ] = record.getInt()  # outer iteration number at which RTFLUX data was written
        self.fc["effk"] = record.getFloat()  # keff
        self.fc["power"] = record.getFloat()  # total core power (Watts)
        self.fc["nblck"] = record.getInt()  # data blocking factor

    def readTriangleFluxes(self):
        r"""
        Read finite difference triangle-z fluxes from the RTFLUX/ATFLUX 3D block (file control).

        This reads all volume-averaged triangle fluxes in ONE energy group on ONE x, y plane of the core.
        The fluxes on different x, y planes (different axial slices) and different groups are in a different 3D record.

        If the reactor has 1/3 core symmetry, these triangles are indexed in "rhomboid" order.
        If the reactor is full-core, these triangles are indexed in "rectangular" order.
        However, this distinction should not matter for this function.

        Returns
        -------
        triangleFluxes : list of float
            This contains all the OUTGOING partial currents for each assembly in the given axial plane.
            The OUTGOING partial current on surface j in assembly i is surfCurrents[i][j].
            The hex assemblies are ordered according to self.geodstCoordMap.

        See Also
        --------
        RTFLUX.read1D
        perturbationTheory.readTriangleFDFluxes

        """

        imax = self.fc[
            "ninti"
        ]  # maximum x coordinate index of assemblies (DIF3D GEODST)
        jmax = self.fc[
            "nintj"
        ]  # maximum y coordinate index of assemblies (DIF3D GEODST)
        nblck = self.fc["nblck"]  # data blocking factor

        m = 1
        j1 = (m - 1) * (
            (jmax - 1) // nblck + 1
        ) + 1  # minimum y coordinate triangle index
        jup = m * (
            (jmax - 1) // nblck + 1
        )  # what the maximum y coordinate triangle index should be given j1
        j2 = min(jmax, jup)  # maximum y coordinate triangle index

        record = self.getRecord()

        # Numpy array to store 5 flux moments per assembly in this x-y plane.
        triangleFluxes = numpy.zeros((imax, jmax))

        # Loop through all flux moments of all assemblies.
        for j in range(j1 - 1, j2):
            for i in range(imax):
                triangleFluxes[i][j] = record.getDouble()

        return triangleFluxes

    def getEnergyGroupIndex(self, g):
        r"""
        Real fluxes stored in RTFLUX have "normal" (or "forward") energy groups.
        Also see the subclass method ATFLUX.getEnergyGroupIndex().
        """

        return g


class ATFLUX(RTFLUX):
    r"""
    This is a subclass for the ATFLUX file, which is identical in format to the RTFLUX file except
    that it contains the adjoint flux and has reversed energy group ordering.
    """

    def getEnergyGroupIndex(self, g):
        r"""
        Adjoint fluxes stored in ATFLUX have "reversed" (or "backward") energy groups.
        """

        ng = self.fc["ngroup"]
        return ng - g - 1


def getFDFluxReader(adjointFlag):
    r"""
    Returns the appropriate DIF3D FD flux binary file reader class,
    either RTFLUX (real) or ATFLUX (adjoint).
    """

    if adjointFlag:
        return ATFLUX
    else:
        return RTFLUX


def plotTriangleFlux(
    rtfluxFile,
    axialZ,
    energyGroup,
    hexPitch=math.sqrt(3.0),
    hexSideSubdivisions=1,
    imgFileExt=".png",
):
    r"""
    Plot region total flux for one core-wide axial slice on triangular/hexagonal geometry.

    Parameters
    ----------
    rtfluxFile : RTFLUX object
        The RTFLUX/ATFLUX file object containing all read file data.
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

    vals = rtfluxFile.triangleFluxes[:, :, axialZ, energyGroup]
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
    rtfluxFile = nodalFluxReader(fName)
    rtfluxFile.readAllData()

    hexFlux = rtfluxFile.triangleFluxes  # multigroup triangle fluxes

    i_geodst_max = rtfluxFile.fc["ninti"]
    j_geodst_max = rtfluxFile.fc["nintj"]
    nz = rtfluxFile.fc["nintk"]  # number of axial nodes

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
    RTFLUX_FILE = RTFLUX()
    plotTriangleFlux(RTFLUX_FILE, axialZ=10, energyGroup=4)
