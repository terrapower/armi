"""
NHFLUX is a CCCC interface file that handles nodal hexagonal flux moments.

Examples
--------
>>> nhfluxData = NfluxStream.readBinary("NHFLUX")
>>> NhfluxStream.writeAscii(nhfluxData, "nhflux.ascii")

"""
import numpy

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

FILE_SPEC_1D_KEYS_VARIANT10 = (
    "npcbdy",
    "npcsym",
    "npcsec",
    "iwnhfl",
    "nMoms",
)


class NHFLUX(cccc.DataContainer):
    """
    An abstraction of a NHFLUX file.

    Important Note: DIF3D outputs NHFLUX at every time node,
    but REBUS outputs NHFLUX only at every cycle.

    This format is defined in DIF3D manual.

    See also [VARIANT-95]_ and [VARIANT-2014]_.

    .. [VARIANT-95] G. Palmiotti, E. E. Lewis, and C. B. Carrico, VARIANT: VARIational Anisotropic Nodal Transport
       for Multidimensional Cartesian and Hexagonal Geometry Calculation, ANL-95/40, Argonne National Laboratory, Argonne, IL (October 1995).

    .. [VARIANT-2014] Smith, M. A., Lewis, E. E., and Shemon, E. R. DIF3D-VARIANT 11.0: A Decade of Updates.
       United States: N. p., 2014. Web. doi:10.2172/1127298. https://publications.anl.gov/anlpubs/2014/04/78313.pdf

    Attributes
    ----------
    self._metadata : file control
        The NHFLUX file control info (sort of global for this library).

    self.geodstCoordMap : list of int
        This is an index map between DIF3D "four color" nodal and DIF3D GEODST. It is absolutely necessary for
        interpreting that data read by nuclearDataIO.NHFLUX.readHexPartialCurrents4D.

    self.externalCurrentPointers : list of int
        This is an index map for the "external hex surfaces" between DIF3D "four color" nodal indexing
        and DIF3D GEODST indexing. "External surfaces" are important, because they contain the
        INCOMING partial currents from the outer reactor boundary.
        This uses the same hex ordering as geodstCoordMap, except that each hex now has 6 subsequent indices.
        If hex of index n (0 to N-1) has a surface of index k (0 to 5) that lies on the vacuum boundary,
        then the index of that surface is N*6 + k + 1.

    self.fluxMoments : 2-D list of float
        This contains all the flux moments for all core assemblies at ONE axial position.
        The jth planar flux moment of assembly i is fluxMoments[i][j].
        The hex assemblies are ordered according to self.geodstCoordMap.

    self.partialCurrentsHex : 2-D list of float
        This contains all the OUTGOING partial currents for each assembly in the given axial plane.
        The OUTGOING partial current on surface j in assembly i is surfCurrents[i][j].
        The hex assemblies are ordered according to self.geodstCoordMap.

    self.partialCurrentsHex_ext : 1-D list of floats
        This contains all the INCOMING partial currents on "external hex surfaces", which are
        adjacent to the reactor outer boundary (usually vacuum). Internal reflective surfaces
        are NOT included in this!
        These "external hex surfaces" are ordered according to self.externalCurrentPointers.

    self.partialCurrentsZ  : 2-D list of float
        This contains all the upward and downward partial currents in all assemblies on ONE whole-core axial slice.
        The hex assemblies are ordered according to self.geodstCoordMap.

    """

    def __init__(self, fName="NHFLUX", variant=False, numDataSetsToRead=1):
        """
        Initialize the NHFLUX or NAFLUX reader object.

        Parameters
        ----------
        fName : str, optional
            The file name of the NHFLUX binary file to be read.

        variant : bool, optional
            Whether or not this NHFLUX/NAFLUX file has the VARIANT output format, which is a bit different than
            the DIF3D nodal format.

        """

        cccc.DataContainer.__init__(self)

        self.metadata["variantFlag"] = variant
        self.metadata["numDataSetsToRead"] = numDataSetsToRead

        # Initialize class array variables.
        self.geodstCoordMap: numpy.ndarray = numpy.array([])
        self.externalCurrentPointers: numpy.ndarray = numpy.array([])
        self.fluxMoments: numpy.ndarray = numpy.array([])
        self.partialCurrentsHex: numpy.ndarray = numpy.array([])
        self.partialCurrentsHex_ext: numpy.ndarray = numpy.array([])
        self.partialCurrentsZ: numpy.ndarray = numpy.array([])
        self.incomingPointersToAllAssemblies: numpy.ndarray = numpy.array([])


class NhfluxStream(cccc.StreamWithDataContainer):
    @staticmethod
    def _getDataContainer() -> NHFLUX:
        return NHFLUX()

    def readWrite(self):
        r"""
        Read everything from the DIF3D binary file NHFLUX that is necessary for pin flux and power reconstruction.

        Read all surface-averaged partial currents, all planar moments,
        and the DIF3D "four color" nodal coordinate mapping system.

        Notes
        -----
        This method should be private but conflicts with ``_readWrite`` so we need a better name.

        Parameters
        ----------
        numDataSetsToRead : int, optional
            The number of whole-core flux data sets included in this NHFLUX/NAFLUX file that one wishes to be read.
            Some NHFLUX/NAFLUX files, such as NAFLUX files written by SASSYS/DIF3D-K, contain more than one flux
            data set. Each data set overwrites the previous one on the NHFLUX class object, which will contain
            only the numDataSetsToRead-th data set. The first numDataSetsToRead-1 data sets are essentially
            skipped over.

        """
        self._rwFileID()
        self._rwBasicFileData1D()

        # Read the hex ordering map between DIF3D "four color" nodal and DIF3D GEODST
        # Also read index pointers to incoming partial currents on outer reactor surface
        # (these don't belong to any assembly)
        # Incoming partial currents are non-zero due to flux extrapolation
        self._rwGeodstCoordMap2D()

        ng = self._metadata["ngroup"]  # number of energy groups
        # number of axial nodes (same for each assembly in DIF3D)
        nz = self._metadata["nintk"]

        # number of lateral hex surfaces on the outer core boundary
        # (usually vacuum - internal reflective boundaries do NOT count)

        numExternalSurfaces = self._getNumExtSurfaces()

        # Note: All flux and current data has units of n/cm^2/s
        if self._data.fluxMoments.size == 0:
            # initialize using metadata info for reading
            self._data.fluxMoments = numpy.zeros(
                (self._metadata["nintxy"], nz, self._metadata["nMom"], ng)
            )
            self._data.partialCurrentsHex = numpy.zeros(
                (self._metadata["nintxy"], nz, self._metadata["nSurf"], ng)
            )
            self._data.partialCurrentsHex_ext = numpy.zeros(
                (numExternalSurfaces, nz, ng)
            )
            self._data.partialCurrentsZ = numpy.zeros(
                (self._metadata["nintxy"], nz + 1, 2, ng)
            )

        for _n in range(self._metadata["numDataSetsToRead"]):

            # Each record contains nodal data for ONE energy group in ONE axial core slice.
            # Must loop through all energy groups and all axial core slices.

            # The axial surface partial currents are indexed by axial surface (NOT by axial node),
            # so there are nz+1 records for z-surface currents

            # Loop through all energy groups: high-to-low for real, low-to-high for adjoint
            for g in range(ng):  # loop through energy groups

                gEff = self._getEnergyGroupIndex(g)

                for z in range(nz):  # loop through axial nodes
                    self._data.fluxMoments[:, z, :, gEff] = self._rwFluxMoments3D(
                        self._data.fluxMoments[:, z, :, gEff]
                    )
                for z in range(nz):  # loop through axial nodes
                    (
                        self._data.partialCurrentsHex[:, z, :, gEff],
                        self._data.partialCurrentsHex_ext[:, z, gEff],
                    ) = self._rwHexPartialCurrents4D(
                        self._data.partialCurrentsHex[:, z, :, gEff],
                        self._data.partialCurrentsHex_ext[:, z, gEff],
                    )

                for z in range(nz + 1):
                    # loop through axial surfaces (NOT axial nodes, because there is a "+1")
                    self._data.partialCurrentsZ[
                        :, z, :, gEff
                    ] = self._rwZPartialCurrents5D(
                        self._data.partialCurrentsZ[:, z, :, gEff]
                    )

    def _getNumExtSurfaces(self, nSurf=6):
        if self._metadata["variantFlag"]:
            numExternalSurfaces = self._metadata["npcbdy"]
        else:
            numExternalSurfaces = (
                self._metadata["npcxy"] - self._metadata["nintxy"] * nSurf
            )

        return numExternalSurfaces

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
        """
        Read basic data parameters (number of energy groups, assemblies, axial nodes, etc.)
        """
        if self._metadata["variantFlag"]:
            keys = FILE_SPEC_1D_KEYS + FILE_SPEC_1D_KEYS_VARIANT10
        else:
            keys = FILE_SPEC_1D_KEYS + ("IDUM",) * 11

        with self.createRecord() as record:
            self._metadata.update(record.rwImplicitlyTypedMap(keys, self._metadata))

    def _rwGeodstCoordMap2D(self):
        """
        Read/write core geometry indexing from the NHFLUX 2D block (file control).

        This reads the 2-D (x,y) indexing for hex assemblies.
        geodstCoordMap maps DIF3D "four color" nodal hex indexing to DIF3D GEODST hex indexing.
        This DIF3D GEODST indexing is different than (but similar to) the MCNP GEODST hex ordering.
        See TP1-1.9.31-RPT-0010 for more details on hex ordering.

        Let N be the number of assemblies. Let M be the number of "external hex surfaces" exposed to
        the outer reactor boundary (usually vacuum). M does NOT include reflective surfaces!

        N = self._metadata['nintxy']
        M = self._metadata['npcxy'] - self._metadata['nintxy']*6
        N*6 + M = self._metadata['npcxy']

        Examples
        --------
        geodstCoordMap[fourColorNodalIndex] = geodstIndex

        See Also
        --------
        nuclearDataIO.NHFLUX.__init__
        nuclearDataIO.NHFLUX.readHexPartialCurrents4D
        fluxRecon.computePinMGFluxAndPower
        nuclearDataIO.ISOTXS.read2D
        nuclearDataIO.SPECTR.read2D

        """

        with self.createRecord() as record:
            # Number of unique hex assemblies - this is N in the comments above
            nAssem = self._metadata["nintxy"]
            # Number of lateral surfaces per hex assembly (always 6)
            nSurf = self._metadata["nSurf"]
            numExternalSurfaces = self._getNumExtSurfaces()

            # Initialize numpy arrays to store all hex ordering (and hex surface ordering) data.
            # We don't actually use incomingPointersToAllAssemblies (basically equivalent to nearest neighbors indices),
            # but it's here in case someone needs it in the future.

            # initialize data size when reading
            if self._data.incomingPointersToAllAssemblies.size == 0:
                # Index pointers to INCOMING partial currents to this assembly
                self._data.incomingPointersToAllAssemblies = numpy.zeros(
                    (nSurf, nAssem), dtype=int
                )
                # Index pointers to INCOMING partial currents on core outer boundary
                self._data.externalCurrentPointers = numpy.zeros(
                    (numExternalSurfaces), dtype=int
                )
                # Index pointers to DIF3D GEODST ordering of each assembly
                self._data.geodstCoordMap = numpy.zeros(nAssem, dtype=int)

            self._data.incomingPointersToAllAssemblies = record.rwIntMatrix(
                self._data.incomingPointersToAllAssemblies, nAssem, nSurf
            )

            self._data.externalCurrentPointers = record.rwList(
                self._data.externalCurrentPointers, "int", numExternalSurfaces
            )

            self._data.geodstCoordMap = record.rwList(
                self._data.geodstCoordMap, "int", nAssem
            )

    def _rwFluxMoments3D(self, contents):
        r"""
        Read/write multigroup flux moments from the NHFLUX 3D block (file control).

        This reads/writes all 5 planar moments for each DIF3D node on ONE x,y plane. The planar moments for
        DIF3D nodes on different x,y planes (different axial slices) are in a different 3D record.

        Format is ``((FLUX(I,J),I=1,NMOM),J=1,NINTXY)`` so we must pass in ``NINTXY`` as
        the first item in the shape. However, the caller of this method wants the shape
        to be (nintxy, nMom) so we actually have to transpose it on the way in/out.
        """

        with self.createRecord() as record:
            fluxMoments = record.rwDoubleMatrix(
                contents.T,
                self._metadata["nintxy"],
                self._metadata["nMom"],
            )

        return fluxMoments.T

    def _rwHexPartialCurrents4D(self, surfCurrents, externalSurfCurrents):
        r"""
        Read/write multigroup hexagonal/laterial partial currents from the NHFLUX 4D block (file control).

        This reads all OUTGOING partial currents for all assembly block lateral surfaces at a fixed axial position.
        There are 6 surfaces per assembly axial block. The 2 axial surfaces of each block are in the 5D records.

        Each 4D record contains all the hex surface (6 per assembly) partial currents on ONE x,y plane.
        The hex surface data on different x,y planes (different axial slices) are in a different 4D record.

        NHFLUX contains only the 6 OUTGOING partial currents for each hex assembly. To obtain INCOMING partial
        currents and to construct NET currents, one must find the OUTGOING partial currents on the hex nearest
        neighbors (this is done in fluxRecon, not in nuclearDataIO.NHFLUX).

        If the reactor contains N hex assemblies and M exterior hex surfaces (surfaces adjacent to vacuum boundary),
        this record will contain N*6 + M partial currents. The N*6 assembly OUTGOING partial currents are listed first,
        followed by the M INCOMING partial currents from the outer reactor edge.

        N = self._metadata['nintxy']
        M = self._metadata['npcxy'] - self._metadata['nintxy']*6
        N*6 + M = self._metadata['npcxy']

        Notes
        -----
        These data are harder to read with rwMatrix, though it could be done if we
        discarded the unwanted data at another level if that is much faster.

        """
        dummy = 0.0
        with self.createRecord() as record:

            nAssem = self._metadata["nintxy"]
            nSurf = self._metadata["nSurf"]
            nscoef = self._metadata["nscoef"]

            numExternalSurfaces = self._getNumExtSurfaces(nSurf)

            # Loop through all lateral hex surfaces of all assemblies
            for i in range(nAssem):
                for j in range(nSurf):
                    for m in range(nscoef):
                        if m == 0:
                            # OUTGOING partial currents on each lateral hex surface in each assembly
                            surfCurrents[i, j] = record.rwDouble(surfCurrents[i, j])
                        else:
                            # other NSCOEF options (like half-angle integrated flux)
                            dummy = record.rwDouble(dummy)

            for j in range(numExternalSurfaces):
                for m in range(nscoef):
                    if m == 0:
                        # INCOMING current at each surface of outer core boundary
                        externalSurfCurrents[j] = record.rwDouble(
                            externalSurfCurrents[j]
                        )
                    else:
                        # other NSCOEF options (like half-angle integrated flux)
                        dummy = record.rwDouble(dummy)

            return surfCurrents, externalSurfCurrents

    def _rwZPartialCurrents5D(self, surfCurrents):
        """
        Read/write multigroup axial partial currents from the NHFLUX 5D block (file control).

        All other NHFLUX data is indexed by DIF3D node (each axial core slice in its own record).
        HOWEVER, "top" and "bottom" surfaces of each DIF3D node are indexed by axial surface.
        If there are Z axial nodes, then there are Z+1 axial surfaces.
        Thus, there are Z+1 5D records, while there are only Z 3D and Z 4D records.

        Each 5D record (each axial surface) contains two partial currents for each assembly position.
        The first is the UPWARD partial current, while the second is the DOWNWARD partial current.
        These are assigned to specific ARMI blocks in fluxRecon.computePinMGFluxAndPower.

        Returns
        -------
        surfCurrents : 2-D list of float
            This contains all the upward and downward partial currents in all assemblies on ONE whole-core axial slice.
            The hex assemblies are ordered according to self.geodstCoordMap.

        See Also
        --------
        nuclearDataIO.NHFLUX.readBasicFileData1D
        nuclearDataIO.NHFLUX.readGeodstCoordMap2D
        fluxRecon.computePinMGFluxAndPower
        nuclearDataIO.ISOTXS.read5D

        """
        dummy = 0.0
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
                        if m == 0:
                            surfCurrents[i, j] = record.rwDouble(
                                surfCurrents[i, j]
                            )  # outward partial current
                        else:
                            record.rwDouble(dummy)  # other NSCOEF options

        return surfCurrents

    def _getEnergyGroupIndex(self, g):
        r"""
        Real fluxes stored in NHFLUX have "normal" (or "forward") energy groups.
        Also see the subclass method NAFLUX.getEnergyGroupIndex().
        """

        return g


class NafluxStream(NhfluxStream):
    """
    NAFLUX is similar in format to the NHFLUX, but contains adjoint flux.

    It has reversed energy group ordering.
    """

    def _getEnergyGroupIndex(self, g):
        r"""
        Adjoint fluxes stored in NAFLUX have "reversed" (or "backward") energy groups.
        """
        ng = self._metadata["ngroup"]
        return ng - g - 1


class NhfluxStreamVariant(NhfluxStream):
    """
    Stream for VARIANT version of NHFLUX.

    Notes
    -----
    Can be deleted after have the NHFLUX data container be the public interface
    """

    @staticmethod
    def _getDataContainer() -> NHFLUX:
        return NHFLUX(variant=True)


class NafluxStreamVariant(NafluxStream):
    """
    Stream for VARIANT version of NAFLUX.

    Notes
    -----
    Can be deleted after have the NHFLUX data container be the public interface
    """

    @staticmethod
    def _getDataContainer() -> NHFLUX:
        return NHFLUX(variant=True)


def getNhfluxReader(adjointFlag, variantFlag):
    r"""
    Returns the appropriate DIF3D nodal flux binary file reader class,
    either NHFLUX (real) or NAFLUX (adjoint).
    """

    if adjointFlag:
        if variantFlag:
            return NafluxStreamVariant
        else:
            return NafluxStream
    else:
        if variantFlag:
            return NhfluxStreamVariant
        else:
            return NhfluxStream
