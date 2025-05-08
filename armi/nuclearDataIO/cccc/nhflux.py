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
NHFLUX is a CCCC interface file that stores flux moments and partial currents from
DIF3D-Nodal and DIF3D-VARIANT.

Examples
--------
>>> nhfluxData = NfluxStream.readBinary("NHFLUX")
>>> NhfluxStream.writeAscii(nhfluxData, "nhflux.ascii")

"""
import numpy as np

from armi.nuclearDataIO import cccc

FILE_SPEC_1D_KEYS = (
    "ndim",
    "ngroup",
    "ninti",
    "nintj",
    "nintk",
    "iter",
    "effk",
    "power",
    "nSurf",
    "nMom",
    "nintxy",
    "npcxy",
    "nscoef",
    "itrord",
    "iaprx",
    "ileak",
    "iaprxz",
    "ileakz",
    "iorder",
)

FILE_SPEC_1D_KEYS_VARIANT11 = (
    "npcbdy",
    "npcsym",
    "npcsec",
    "iwnhfl",
    "nMoms",
)


class NHFLUX(cccc.DataContainer):
    """
    An abstraction of a NHFLUX file. This format is defined in the DIF3D manual. Note that the
    format for DIF3D-Nodal and DIF3D-VARIANT are not the same. The VARIANT NHFLUX format has
    recently changed, so this reader is only compatible with files produced by v11.0 of the solver.

    Attributes
    ----------
    metadata : file control
        The NHFLUX file control info (sort of global for this library). This is the contents of the
        1D data block on the file.

    incomingPointersToAllAssemblies: 2-D list of floats
        This is an index map for the "internal surfaces" between DIF3D nodal indexing and DIF3D
        GEODST indexing. It can be used to process incoming partial currents. This uses the same
        ordering as the geodstCoordMap attribute.

    externalCurrentPointers : list of ints
        This is an index map for the "external surfaces" between DIF3D nodal indexing and DIF3D
        GEODST indexing. "External surfaces" are important because they contain the INCOMING partial
        currents from the outer reactor boundary. This uses the same ordering as geodstCoordMap,
        except that each assembly now has multiple subsequent indices. For example, for a hexagonal
        core, if hex of index n (0 to N-1) has a surface of index k (0 to 5) that lies on the vacuum
        boundary, then the index of that surface is N*6 + k + 1.

    geodstCoordMap : list of ints
        This is an index map between DIF3D nodal and DIF3D GEODST. It is necessary for interpreting
        the ordering of flux and partial current data in the NHFLUX file. Note that this mapping
        between DIF3D-Nodal and DIF3D-VARIANT is not the same.

    outgoingPCSymSeCPointers: list of ints
        This is an index map for the outpgoing partial currents on the symmetric and sector lateral
        boundary. It is only present for DIF3D-VARIANT for hexagonal cores.

    ingoingPCSymSeCPointers: list of ints
        This is an index map for the ingoing (or incoming) partial currents on the symmetric and
        sector lateral boundary. It is only present for DIF3D-VARIANT for hexagonal cores.

    fluxMomentsAll : 4-D list of floats
        This contains all the flux moments for all core assemblies. The jth planar flux moment of
        assembly i in group g in axial node k is fluxMoments[i][k][j][g]. The assemblies are ordered
        according to the geodstCoordMap attribute. For DIF3D-VARIANT, this includes both even and
        odd parity moments.

    partialCurrentsHexAll : 5-D list of floats
        This contains all the OUTGOING partial currents for all core assemblies. The OUTGOING
        partial current on surface j in assembly i in axial node k in group g is
        partialCurrentsHex[i][k][j][g][m], where m=0. The assemblies are ordered according to the
        geodstCoordMap attribute. For DIF3D-VARIANT, higher-order data is available for the m axis.

    partialCurrentsHex_extAll : 4-D list of floats
        This contains all the INCOMING partial currents on "external surfaces", which are adjacent
        to the reactor outer boundary (usually vacuum). Internal reflective surfaces are NOT
        included in this! These "external surfaces" are ordered according to
        externalCurrentPointers. For DIF3D-VARIANT, higher-order data is available for the last
        axis.

    partialCurrentsZAll : 5-D list of floats
        This contains all the upward and downward partial currents for all core assemblies. The
        assemblies are ordered according to the geodstCoordMap attribute. For DIF3D-VARIANT, higher-
        order data is available for the last axis.

    Warning
    -------
    DIF3D outputs NHFLUX at every time node, but REBUS outputs NHFLUX only at every cycle.

    See Also
    --------
    [VARIANT-95]_ and [VARIANT-2014]_.

    .. [VARIANT-95] G. Palmiotti, E. E. Lewis, and C. B. Carrico, VARIANT: VARIational Anisotropic
       Nodal Transport for Multidimensional Cartesian and Hexagonal Geometry Calculation, ANL-95/40,
       Argonne National Laboratory, Argonne, IL (October 1995).

    .. [VARIANT-2014] Smith, M. A., Lewis, E. E., and Shemon, E. R. DIF3D-VARIANT 11.0: A Decade of
       Updates. United States: N. p., 2014. Web. doi:10.2172/1127298.
       https://publications.anl.gov/anlpubs/2014/04/78313.pdf
    """

    def __init__(self, fName="NHFLUX", variant=False, numDataSetsToRead=1):
        """
        Initialize the NHFLUX or NAFLUX reader object.

        Parameters
        ----------
        fName : str, optional
            Filename of the NHFLUX binary file to be read.

        variant : bool, optional
            Whether or not this NHFLUX/NAFLUX file has the DIF3D-VARIANT output format, which is
            different than the DIF3D-Nodal format.
        """
        cccc.DataContainer.__init__(self)

        self.metadata["variantFlag"] = variant
        self.metadata["numDataSetsToRead"] = numDataSetsToRead

        # Initialize instance array variables
        self.incomingPointersToAllAssemblies: np.ndarray = np.array([])
        self.externalCurrentPointers: np.ndarray = np.array([])
        self.geodstCoordMap: np.ndarray = np.array([])
        if self.metadata["variantFlag"]:
            self.outgoingPCSymSecPointers: np.ndarray = np.array([])
            self.ingoingPCSymSecPointers: np.ndarray = np.array([])
        self.fluxMomentsAll: np.ndarray = np.array([])
        self.partialCurrentsHexAll: np.ndarray = np.array([])
        self.partialCurrentsHex_extAll: np.ndarray = np.array([])
        self.partialCurrentsZAll: np.ndarray = np.array([])

    @property
    def fluxMoments(self):
        """
        For DIF3D-Nodal, this property is equivalent to the attribute `fluxMomentsAll`. For
        DIF3D-VARIANT, this property represents the even-parity flux moments.

        Read-only property (there is no setter).
        """
        nMom = self.metadata["nMom"]
        return self.fluxMomentsAll[..., :nMom, :]

    @property
    def partialCurrentsHex(self):
        """
        For DIF3D-Nodal, this property is almost always equivalent to the attribute
        ``partialCurrentsHex``. For DIF3D-VARIANT, this property returns the zeroth-order moment of
        the outgoing radial currents.

        Read-only property (there is no setter).
        """
        return self.partialCurrentsHexAll[..., 0]

    @property
    def partialCurrentsHex_ext(self):
        """
        For DIF3D-Nodal, this property is almost always equivalent to the attribute
        `partialCurrentsHex_ext`. For DIF3D-VARIANT, this property returns the zeroth-order
        moment of the incoming/ingoing radial currents.

        Read-only property (there is no setter).
        """
        return self.partialCurrentsHex_extAll[..., 0]

    @property
    def partialCurrentsZ(self):
        """
        For DIF3D-Nodal, this property is almost always equivalent to the attribute
        `partialCurrentsZ`. For DIF3D-VARIANT, this property returns the zeroth-order
        moment of the axial currents.

        Read-only property (there is no setter).
        """
        return self.partialCurrentsZAll[..., 0]


class NhfluxStream(cccc.StreamWithDataContainer):
    @staticmethod
    def _getDataContainer() -> NHFLUX:
        return NHFLUX()

    def readWrite(self):
        """
        Read everything from the DIF3D binary file NHFLUX.

        Read all surface-averaged partial currents, all planar moments, and the DIF3D nodal
        coordinate mapping system.

        Notes
        -----
        This method should be private but conflicts with ``_readWrite`` so we need a
        better name.

        Parameters
        ----------
        numDataSetsToRead : int, optional
            The number of whole-core flux data sets included in this NHFLUX/NAFLUX file that one
            wishes to be read. Some NHFLUX/NAFLUX files, such as NAFLUX files written by
            SASSYS/DIF3D-K, contain more than one flux data set. Each data set overwrites the
            previous one on the NHFLUX class object, which will contain only the
            ``numDataSetsToRead-th`` data set. The first numDataSetsToRead-1 data sets are
            essentially skipped over.
        """
        self._rwFileID()
        self._rwBasicFileData1D()

        # This control info only exists for VARIANT. We can only process entries with 0 or 1.
        if self._metadata["variantFlag"] and self._metadata["iwnhfl"] == 2:
            msg = (
                "This reader can only read VARIANT NHFLUX files where 'iwnhfl'=0 (both "
                "fluxes and currents are present) or 'iwnhfl'=1 (only fluxes are present). "
            )
            raise ValueError(msg)

        # Read the hex ordering map between DIF3D nodal and DIF3D GEODST. Also read index
        # pointers to incoming partial currents on outer reactor surface (these don't
        # belong to any assembly). Incoming partial currents are non-zero due to flux
        # extrapolation
        self._rwGeodstCoordMap2D()

        # Number of energy groups
        ng = self._metadata["ngroup"]

        # Number of axial nodes (same for each assembly in DIF3D)
        nz = self._metadata["nintk"]

        # Number of XY partial currents on the boundary. Note that for the same model, this
        # number is not the same between Nodal and VARIANT; VARIANT has more.
        numPartialCurrentsHex_ext = (
            self._metadata["npcxy"] - self._metadata["nintxy"] * self._metadata["nSurf"]
        )

        # Typically, flux and current data has units of n/cm^2/s. However, when reading
        # an NHFLUX file produced by VARPOW (where 'iwnhfl'=1), the flux-only data has units
        # of W/cc (there is no current data written to the file).
        if self._data.fluxMomentsAll.size == 0:

            # Initialize using metadata info for reading
            totalMoments = (
                self._metadata["nMom"]
                if not self._metadata["variantFlag"]
                else (self._metadata["nMom"] + self._metadata["nMoms"])
            )
            self._data.fluxMomentsAll = np.zeros(
                (self._metadata["nintxy"], nz, totalMoments, ng)
            )

            if self._metadata["iwnhfl"] != 1:
                self._data.partialCurrentsHexAll = np.zeros(
                    (
                        self._metadata["nintxy"],
                        nz,
                        self._metadata["nSurf"],
                        ng,
                        self._metadata["nscoef"],
                    )
                )
                self._data.partialCurrentsHex_extAll = np.zeros(
                    (numPartialCurrentsHex_ext, nz, ng, self._metadata["nscoef"])
                )
                self._data.partialCurrentsZAll = np.zeros(
                    (self._metadata["nintxy"], nz + 1, 2, ng, self._metadata["nscoef"])
                )

        for _n in range(self._metadata["numDataSetsToRead"]):
            # Each record contains nodal data for ONE energy group in ONE axial core slice.
            # Must loop through all energy groups and all axial core slices.

            # The axial surface partial currents are indexed by axial surface (NOT by axial node),
            # so there are nz+1 records for z-surface currents

            # Loop through all energy groups: high-to-low for forward flux, low-to-high for
            # adjoint flux
            for g in range(ng):
                gEff = self._getEnergyGroupIndex(g)

                # Loop through axial nodes
                for z in range(nz):

                    # Process flux moments
                    self._data.fluxMomentsAll[:, z, :, gEff] = self._rwFluxMoments3D(
                        self._data.fluxMomentsAll[:, z, :, gEff]
                    )

                # Process currents
                if self._metadata["iwnhfl"] != 1:
                    # Loop through axial nodes
                    for z in range(nz):
                        (
                            self._data.partialCurrentsHexAll[:, z, :, gEff, :],
                            self._data.partialCurrentsHex_extAll[:, z, gEff, :],
                        ) = self._rwHexPartialCurrents4D(
                            self._data.partialCurrentsHexAll[:, z, :, gEff, :],
                            self._data.partialCurrentsHex_extAll[:, z, gEff, :],
                        )

                    # Loop through axial surfaces (NOT axial nodes, because there is a "+1")
                    for z in range(nz + 1):
                        self._data.partialCurrentsZAll[
                            :, z, :, gEff, :
                        ] = self._rwZPartialCurrents5D(
                            self._data.partialCurrentsZAll[:, z, :, gEff, :]
                        )

    def _getNumOuterSurfacesHex(self):
        """
        The word "outer" in the method name means along the outside of the core. Thus, this
        is the number of lateral hex surfaces on the outer core boundary (usually vacuum...internal
        reflective boundaries do NOT count).
        """
        # Both Nodal and VARIANT files should return the same number, but they are calculated
        # differently between the two codes
        if self._metadata["variantFlag"]:
            numOuterSurfacesHex = self._metadata["npcbdy"]
        else:
            # Nodal does not have an "npcbdy" metadata parameter, so numOuterSurfacesHex
            # must be calculated differently. Performing the same calculation below in VARIANT,
            # which is possible to do, can return a different number, so that is why
            # we cannot use the same calculation for both codes.
            numOuterSurfacesHex = (
                self._metadata["npcxy"]
                - self._metadata["nintxy"] * self._metadata["nSurf"]
            )

        return numOuterSurfacesHex

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

    def _rwBasicFileData1D(self):
        """Read basic data parameters (number of energy groups, assemblies, axial nodes, etc.)."""
        # Dummy values are stored because sometimes they get assigned
        # unexpected values anyway, and so we still want to preserve those values anyway
        if self._metadata["variantFlag"]:
            keys = (
                FILE_SPEC_1D_KEYS
                + FILE_SPEC_1D_KEYS_VARIANT11
                + tuple(f"IDUM{e:>02}" for e in range(1, 7))
            )
        else:
            keys = FILE_SPEC_1D_KEYS + tuple(
                tuple(f"IDUM{e:>02}" for e in range(1, 12))
            )

        with self.createRecord() as record:
            self._metadata.update(record.rwImplicitlyTypedMap(keys, self._metadata))

    def _rwGeodstCoordMap2D(self):
        """
        Read/write core geometry indexing from the NHFLUX 2D block.

        This reads the 2-D (x,y) indexing for assemblies. geodstCoordMap maps DIF3D
        nodal hex indexing to DIF3D GEODST indexing.
        This DIF3D GEODST indexing is different than (but similar to) the MCNP GEODST ordering.

        For Nodal, let N be the number of assemblies. Let M be the number of
        "external hex surfaces" exposed to the outer reactor boundary (usually vacuum). M
        does NOT include reflective surfaces!

        N = self._metadata['nintxy']
        M = self._metadata['npcxy'] - self._metadata['nintxy']*6
        N*6 + M = self._metadata['npcxy']

        For VARIANT in hexagonal geometry, there are two additional datasets for outgoing
        and ingoing partial currents on the symmetric and sector xy-plane boundary.

        Examples
        --------
            geodstCoordMap[NodalIndex] = geodstIndex

        See Also
        --------
        nuclearDataIO.NHFLUX.__init__
        nuclearDataIO.NHFLUX._rwHexPartialCurrents4D
        nuclearDataIO.ISOTXS.read2D
        nuclearDataIO.SPECTR.read2D
        """
        with self.createRecord() as record:
            # Number of unique assemblies - this is N in the comments above
            nAssem = self._metadata["nintxy"]

            # Number of lateral surfaces per assembly (this is 6 for hexagonal cores)
            nSurf = self._metadata["nSurf"]

            numExternalSurfaces = self._getNumOuterSurfacesHex()

            # Initialize np arrays to store all node ordering (and node surface ordering)
            # data. We don't actually use incomingPointersToAllAssemblies (basically
            # equivalent to nearest neighbors indices), but it's here in case someone
            # needs it in the future.

            # Initialize data size when reading
            if self._data.incomingPointersToAllAssemblies.size == 0:
                # Index pointers to INCOMING partial currents on assemblies
                self._data.incomingPointersToAllAssemblies = np.zeros(
                    (nSurf, nAssem), dtype=int
                )
                # Index pointers to OUTGOING partial currents on core outer boundary
                self._data.externalCurrentPointers = np.zeros(
                    (numExternalSurfaces), dtype=int
                )
                # Index pointers to DIF3D GEODST ordering of each assembly
                self._data.geodstCoordMap = np.zeros(nAssem, dtype=int)

            self._data.incomingPointersToAllAssemblies = record.rwIntMatrix(
                self._data.incomingPointersToAllAssemblies, nAssem, nSurf
            )

            self._data.externalCurrentPointers = record.rwList(
                self._data.externalCurrentPointers, "int", numExternalSurfaces
            )

            self._data.geodstCoordMap = record.rwList(
                self._data.geodstCoordMap, "int", nAssem
            )

            # There is additional data to process for VARIANT
            if self._metadata["variantFlag"]:
                # Number of symmetry and sector surface pointers
                npcsto = self._metadata["npcsym"] + self._metadata["npcsec"]

                if self._data.outgoingPCSymSecPointers.size == 0:
                    self._data.outgoingPCSymSecPointers = np.zeros(npcsto, dtype=int)
                    self._data.ingoingPCSymSecPointers = np.zeros(npcsto, dtype=int)

                self._data.outgoingPCSymSecPointers = record.rwList(
                    self._data.outgoingPCSymSecPointers, "int", npcsto
                )
                self._data.ingoingPCSymSecPointers = record.rwList(
                    self._data.ingoingPCSymSecPointers, "int", npcsto
                )

    def _rwFluxMoments3D(self, contents):
        r"""
        Read/write multigroup flux moments from the NHFLUX 3D block.

        This reads/writes the planar moments for each DIF3D node on ONE x,y plane. The
        planar moments for DIF3D nodes on different x,y planes (different axial slices) are
        in a different 3D record, so this method must be repeatedly executed in order to
        process them all.

        Format is ``((FLUX(I,J),I=1,NMOM),J=1,NINTXY)`` so we must pass in ``NINTXY`` as
        the first item in the shape. However, the caller of this method wants the shape
        to be (nintxy, nMom) so we actually have to transpose it on the way in/out.

        nMom can also be nMoms when reading/writing for VARIANT.
        """
        nMom = self._metadata["nMom"]
        with self.createRecord() as record:
            result = record.rwDoubleMatrix(
                contents[:, :nMom].T,
                self._metadata["nintxy"],
                nMom,
            )
            contents[:, :nMom] = result.T

            # If we have VARIANT data, then we also need to process the odd-parity moments.
            if self._metadata["variantFlag"] and self._metadata["nMoms"] > 0:
                result = record.rwDoubleMatrix(
                    contents[:, nMom:].T,
                    self._metadata["nintxy"],
                    self._metadata["nMoms"],
                )
                contents[:, nMom:] = result.T

        return contents

    def _rwHexPartialCurrents4D(self, surfCurrents, externalSurfCurrents):
        r"""
        Read/write multigroup lateral partial OUTGOING currents from the NHFLUX 4D block.

        This reads all OUTGOING partial currents for all assembly block lateral surfaces
        at a fixed axial position. For a hexagonal core, there are 6 surfaces per assembly
        axial block. The data for the 2 axial surfaces of each block are in the 5D records.

        Each 4D record contains all the surface partial currents on ONE x,y plane. The
        surface data on different x,y planes (different axial slices) are in a different
        4D record, so this method must be repeatedly executed in order to process them all.

        If the reactor contains N assemblies and M exterior surfaces (surfaces adjacent to
        vacuum boundary), this record will contain N*6 + M partial currents. The N*6
        assembly OUTGOING partial currents are listed first, followed by the M INCOMING
        partial currents from the outer reactor edge.

        N = self._metadata['nintxy']
        M = self._metadata['npcxy'] - self._metadata['nintxy']*6
        N*6 + M = self._metadata['npcxy']

        Notes
        -----
        These data are harder to read with rwMatrix, though it could be done if we
        discarded the unwanted data at another level if that is much faster.
        """
        with self.createRecord() as record:

            nAssem = self._metadata["nintxy"]
            nSurf = self._metadata["nSurf"]

            # This is equal to one for Nodal diffusion theory, but greater than one for
            # VARIANT.
            nscoef = self._metadata["nscoef"]

            numPartialCurrentsHex_ext = (
                self._metadata["npcxy"]
                - self._metadata["nintxy"] * self._metadata["nSurf"]
            )

            # Loop through all lateral surfaces of all assemblies
            for i in range(nAssem):
                for j in range(nSurf):
                    for m in range(nscoef):
                        # OUTGOING partial currents on each lateral surface in each assembly.
                        # If m > 0, other NSCOEF options (i.e., half-angle integrated
                        # flux when reading DIF3D-Nodal data, and higher current moments
                        # when reading DIF3D-VARIANT data) are processed.
                        surfCurrents[i, j, m] = record.rwDouble(surfCurrents[i, j, m])

            for j in range(numPartialCurrentsHex_ext):
                for m in range(nscoef):
                    # INCOMING current at each surface of outer core boundary. If m > 0,
                    # other NSCOEF options (i.e., half-angle integrated flux when
                    # reading DIF3D-Nodal data, and higher current moments when reading
                    # DIF3D-VARIANT data) are processed.
                    externalSurfCurrents[j, m] = record.rwDouble(
                        externalSurfCurrents[j, m]
                    )

            return surfCurrents, externalSurfCurrents

    def _rwZPartialCurrents5D(self, surfCurrents):
        """
        Read/write multigroup axial partial currents from the NHFLUX 5D block.

        Most other NHFLUX data is indexed by DIF3D node (each axial core slice in its own record).
        HOWEVER, "top" and "bottom" surfaces of each DIF3D node are instead indexed by axial
        surface. If there are Z axial nodes, then there are Z+1 axial surfaces. Thus, there
        are Z+1 5D records, while there are only Z 3D and Z 4D records.

        Each 5D record (each axial surface) contains two partial currents for each assembly position.
        The first is the UPWARD partial current, while the second is the DOWNWARD partial current.

        Returns
        -------
        surfCurrents : 3-D list of floats
            This contains all the upward and downward partial currents in all assemblies
            on ONE whole-core axial slice. The assemblies are ordered according to
            self.geodstCoordMap.

        See Also
        --------
        nuclearDataIO.NHFLUX._rwBasicFileData1D
        nuclearDataIO.NHFLUX._rwGeodstCoordMap2D
        """
        with self.createRecord() as record:

            nAssem = self._metadata["nintxy"]
            nSurf = 2
            nscoef = self._metadata["nscoef"]

            # Loop through all (up and down) partial currents on all hexes
            # These loops are in a different order than in the 4D record above!!!
            # Here we loop through surface FIRST and assemblies SECOND!!!
            for j in range(nSurf):
                for i in range(nAssem):
                    for m in range(nscoef):
                        # Outward partial current. For m > 0, other NSCOEF options
                        # (i.e., half-angle integrated flux when reading DIF3D-Nodal
                        # data, and higher current moments when reading DIF3D-VARIANT
                        # data) are processed.
                        surfCurrents[i, j, m] = record.rwDouble(surfCurrents[i, j, m])

        return surfCurrents

    def _getEnergyGroupIndex(self, g):
        """
        Real fluxes stored in NHFLUX have "normal" (or "forward") energy groups. Also see the
        subclass method NAFLUX.getEnergyGroupIndex().
        """
        return g


class NafluxStream(NhfluxStream):
    """
    NAFLUX is similar in format to the NHFLUX, but contains adjoint flux.

    It has reversed energy group ordering.
    """

    def _getEnergyGroupIndex(self, g):
        """Adjoint fluxes stored in NAFLUX have "reversed" (or "backward") energy groups."""
        ng = self._metadata["ngroup"]
        return ng - g - 1


class NhfluxStreamVariant(NhfluxStream):
    """
    Stream for VARIANT version of NHFLUX.

    Notes
    -----
    Can be deleted after have the NHFLUX data container be the public interface.
    """

    @staticmethod
    def _getDataContainer() -> NHFLUX:
        return NHFLUX(variant=True)


class NafluxStreamVariant(NafluxStream):
    """
    Stream for VARIANT version of NAFLUX.

    Notes
    -----
    Can be deleted after have the NHFLUX data container be the public interface.
    """

    @staticmethod
    def _getDataContainer() -> NHFLUX:
        return NHFLUX(variant=True)


def getNhfluxReader(adjointFlag, variantFlag):
    """
    Returns the appropriate DIF3D nodal flux binary file reader class, either NHFLUX (real) or
    NAFLUX (adjoint).
    """
    if adjointFlag:
        reader = NafluxStreamVariant if variantFlag else NafluxStream
    else:
        reader = NhfluxStreamVariant if variantFlag else NhfluxStream

    return reader
