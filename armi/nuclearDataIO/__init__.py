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
This package implements classes for reading and writing **standard interface files for reactor
physics codes** [CCCC-IV]_.

This module is designed to read/write Fortran record-based binary files that
comply with the format established by the Committee on Computer Code Coordination (CCCC).

.. [CCCC-IV] R. Douglas O'Dell, "Standard Interface Files and Procedures for Reactor Physics
             Codes, Version IV," LA-6941-MS, Los Alamos National Laboratory (September 1977).
             Web. doi:10.2172/5369298. (`OSTI <https://www.osti.gov/biblio/5369298>`_)

It may also read other nuclear data I/O formats as appropriate.

"""
from __future__ import print_function

import os
import struct
import math
import re
import traceback

import glob
import numpy
import pylab
import scipy.interpolate

from armi.utils import properties
from armi import runLog
from armi import settings
from armi.localization import exceptions
from armi.utils import units
from armi.nuclearDataIO import cccc
from armi.physics import neutronics


def getExpectedISOTXSFileName(cycle=None, suffix=None, xsID=None):
    """
    Return the ISOTXS file that matches either the current cycle or xsID with a suffix.

    See Also
    --------
    getExpectedCOMPXSFileName
    getExpectedGAMISOFileName
    getExpectedPMATRXFileName
    """
    if xsID is not None and cycle is not None:
        raise ValueError("Both `xsID` and `cycle` cannot be specified together.")

    if suffix is not None and cycle is not None:
        raise ValueError("Both `suffix` and ``cycle cannot be specified together.")

    if xsID is not None:
        neutronFileName = neutronics.ISOTXS[:3]
    else:
        neutronFileName = neutronics.ISOTXS
    return _findExpectedNeutronFileName(
        neutronFileName, _getNeutronKeywords(cycle, suffix, xsID)
    )


def getExpectedCOMPXSFileName(cycle=None):
    """
    Return the COMPXS file that matches either the current cycle.

    See Also
    --------
    getExpectedISOTXSFileName
    getExpectedGAMISOFileName
    getExpectedPMATRXFileName
    """
    return _findExpectedNeutronFileName(
        neutronics.COMPXS, _getNeutronKeywords(cycle, suffix=None, xsID=None)
    )


def _findExpectedNeutronFileName(fileType, fileNameKeywords):
    return fileType + "".join(fileNameKeywords)


def _getNeutronKeywords(cycle, suffix, xsID):
    if cycle is not None and xsID is not None:
        raise ValueError("Keywords are over-specified. Choose `cycle` or `xsID` only")

    # If neither cycle or xsID are provided there are no additional keywords to add
    # to the file name
    if cycle is None and xsID is None:
        keywords = []
    else:
        # example: ISOTXS-c0
        if cycle is not None:
            keywords = ["-c", str(cycle)]
        # example: ISOAA-test
        elif xsID is not None:
            keywords = [xsID]
            if suffix not in [None, ""]:
                keywords.append("-" + suffix)
        else:
            raise ValueError("The cycle or XS ID must be specified.")
    return keywords


def getExpectedGAMISOFileName(cycle=None, suffix=None, xsID=None):
    """
    Return the GAMISO file that matches either the ``cycle`` or ``xsID`` and ``suffix``.

    For example:
        If ``cycle`` is set to 0, then ``cycle0.gamiso`` will be returned.
        If ``xsID`` is set to ``AA`` with a ``suffix`` of ``test``, then
        ``AA-test.gamiso`` will be returned.

    See Also
    --------
    getExpectedISOTXSFileName
    getExpectedCOMPXSFileName
    getExpectedPMATRXFileName
    """
    return _findExpectedGammaFileName(
        neutronics.GAMISO, _getGammaKeywords(cycle, suffix, xsID)
    )


def getExpectedPMATRXFileName(cycle=None, suffix=None, xsID=None):
    """
    Return the PMATRX file that matches either the ``cycle`` or ``xsID`` and ``suffix``.

    For example:
        If ``cycle`` is set to 0 d, then ``cycle0.pmatrx`` will be returned.
        If ``xsID`` is set to ``AA`` with a ``suffix`` of ``test``, then
        ``AA-test.pmatrx`` will be returned.

    See Also
    --------
    getExpectedISOTXSFileName
    getExpectedCOMPXSFileName
    getExpectedGAMISOFileName
    """
    return _findExpectedGammaFileName(
        neutronics.PMATRX, _getGammaKeywords(cycle, suffix, xsID)
    )


def _findExpectedGammaFileName(fileType, fileNameKeywords):
    return "".join(fileNameKeywords) + fileType


def _getGammaKeywords(cycle, suffix, xsID):
    if cycle is not None and xsID is not None:
        raise ValueError("Keywords are over-specified. Choose `cycle` or `xsID` only")

    # If neither cycle or xsID are provided there are no additional keywords to add
    # to the file name
    if cycle is None and xsID is None:
        keywords = []
    else:
        # example: cycle0.gamiso
        if cycle is not None:
            keywords = ["cycle", str(cycle)]
        elif xsID is not None:
            keywords = [xsID]
            if suffix not in [None, ""]:
                if not suffix.startswith("-"):
                    suffix = "-" + suffix
                keywords.append(suffix)
        else:
            raise ValueError("The cycle or XS ID must be specified.")
        keywords.append(".")
    return keywords


def ISOTXS(fName="ISOTXS"):
    # load a library that is in the ARMI tree. This should
    # be a small library with LFPs, Actinides, structure, and coolant
    from armi.nuclearDataIO import isotxs

    return isotxs.readBinary(fName)


def GAMISO(fName="GAMISO"):
    # load a library that is in the ARMI tree. This should
    # be a small library with LFPs, Actinides, structure, and coolant
    from armi.nuclearDataIO import gamiso

    return gamiso.readBinary(fName)


class NHFLUX(cccc.CCCCReader):
    """
    Read a binary NHFLUX or NAFLUX file from DIF3D nodal output.

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
    self.fc : file control
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

    def __init__(self, fName="NHFLUX", variant=False):
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

        cccc.CCCCReader.__init__(self, fName)

        self.variantFlag = variant

        self.fc = {}  # file control info (sort of global for this library)

        # Initialize class array variables.
        self.geodstCoordMap = []
        self.externalCurrentPointers = []
        self.fluxMoments = []
        self.partialCurrentsHex = []
        self.partialCurrentsHex_ext = []
        self.partialCurrentsZ = []
        self.incomingPointersToAllAssemblies = []

        self.readFileID()

    def _getNumExtSurfaces(self, nSurf=6):
        if self.variantFlag:
            numExternalSurfaces = self.fc["npcbdy"]
        else:
            numExternalSurfaces = self.fc["npcxy"] - self.fc["nintxy"] * nSurf

        return numExternalSurfaces

    def readAllData(self, numDataSetsToRead=1):
        r"""
        Read everything from the DIF3D binary file NHFLUX that is necessary for pin flux and power reconstruction.

        Read all surface-averaged partial currents, all planar moments,
        and the DIF3D "four color" nodal coordinate mapping system.

        Parameters
        ----------
        numDataSetsToRead : int, optional
            The number of whole-core flux data sets included in this NHFLUX/NAFLUX file that one wishes to be read.
            Some NHFLUX/NAFLUX files, such as NAFLUX files written by SASSYS/DIF3D-K, contain more than one flux
            data set. Each data set overwrites the previous one on the NHFLUX class object, which will contain
            only the numDataSetsToRead-th data set. The first numDataSetsToRead-1 data sets are essentially
            skipped over.

        Outputs
        -------
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

        # Read basic data parameters (number of energy groups, assemblies, axial nodes, etc.)
        self.readBasicFileData1D()

        # Read the hex ordering map between DIF3D "four color" nodal and DIF3D GEODST
        # Also read index pointers to incoming partial currents on outer reactor surface
        # (these don't belong to any assembly)
        # Incoming partial currents are non-zero due to flux extrapolation
        self.readGeodstCoordMap2D()

        ng = self.fc["ngroup"]  # number of energy groups
        nz = self.fc["nintk"]  # number of axial nodes (same for each assembly in DIF3D)

        # number of lateral hex surfaces on the outer core boundary
        # (usually vacuum - internal reflective boundaries do NOT count)

        numExternalSurfaces = self._getNumExtSurfaces()

        # Note: All flux and current data has units of n/cm^2/s
        self.fluxMoments = numpy.zeros((self.fc["nintxy"], nz, self.fc["nMom"], ng))
        self.partialCurrentsHex = numpy.zeros(
            (self.fc["nintxy"], nz, self.fc["nSurf"], ng)
        )
        self.partialCurrentsHex_ext = numpy.zeros((numExternalSurfaces, nz, ng))
        self.partialCurrentsZ = numpy.zeros((self.fc["nintxy"], nz + 1, 2, ng))

        for _n in range(numDataSetsToRead):

            # Each record contains nodal data for ONE energy group in ONE axial core slice.
            # Must loop through all energy groups and all axial core slices.

            # The axial surface partial currents are indexed by axial surface (NOT by axial node),
            # so there are nz+1 records for z-surface currents

            # Loop through all energy groups: high-to-low for real, low-to-high for adjoint
            for g in range(ng):  # loop through energy groups

                gEff = self.getEnergyGroupIndex(g)

                for z in range(nz):  # loop through axial nodes
                    self.fluxMoments[:, z, :, gEff] = self.readFluxMoments3D()
                for z in range(nz):  # loop through axial nodes
                    (
                        self.partialCurrentsHex[:, z, :, gEff],
                        self.partialCurrentsHex_ext[:, z, gEff],
                    ) = self.readHexPartialCurrents4D()
                for z in range(
                    nz + 1
                ):  # loop through axial surfaces (NOT axial nodes, because there is a "+1")
                    self.partialCurrentsZ[:, z, :, gEff] = self.readZPartialCurrents5D()

        self.f.close()

    def readBasicFileData1D(self):
        r"""
        Read parameters from the NHFLUX 1D block (file control).

        This contains a bunch of single-number integer or double values
        necessary to read all data from the other records of NHFLUX.

        See Also
        --------
        nuclearDataIO.NHFLUX.__init__
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
        ] = record.getInt()  # outer iteration number at which NHFLUX data was written
        self.fc["effk"] = record.getFloat()  # keff
        self.fc["power"] = record.getFloat()  # total core power (Watts)
        self.fc[
            "nSurf"
        ] = (
            record.getInt()
        )  # number of lateral surfaces on a hex block (always 6, I think)
        self.fc[
            "nMom"
        ] = record.getInt()  # number of flux moments per hex assembly block
        # total number of assemblies in core (for example, 91 for 1/3 core with 10 full rings)
        self.fc["nintxy"] = record.getInt()
        # total number of unique partial currents in the x-y plane = 6*nintxy + numberOfExternalSurfaces
        self.fc["npcxy"] = record.getInt()

        # Extra parameters from VARIANT version of NHFLUX:
        self.fc["nscoef"] = record.getInt()
        self.fc["itrord"] = record.getInt()
        self.fc["iaprx"] = record.getInt()
        self.fc["ileak"] = record.getInt()
        self.fc["iaprxz"] = record.getInt()
        self.fc["ileakz"] = record.getInt()
        self.fc["iorder"] = record.getInt()

        # Read extra parameters that only occur in VARIANT v10.0 (not in v8.0!)
        # 'npcbdy' is essential for reading the VARIANT NHFLUX/NAFLUX files
        # Basically, VARIANT v8.0 is bugged for reading NHFLUX/NAFLUX!
        if self.variantFlag:
            self.fc["npcbdy"] = record.getInt()
            self.fc["npcsym"] = record.getInt()
            self.fc["npcsec"] = record.getInt()
            self.fc["iwnhfl"] = record.getInt()
            self.fc["nMoms"] = record.getInt()

        self.fc["idum"] = record.getInt()

    def readGeodstCoordMap2D(self):
        r"""
        Read core geometry indexing from the NHFLUX 2D block (file control).

        This reads the 2-D (x,y) indexing for hex assemblies.
        geodstCoordMap maps DIF3D "four color" nodal hex indexing to DIF3D GEODST hex indexing.
        This DIF3D GEODST indexing is different than (but similar to) the MCNP GEODST hex ordering.
        See TP1-1.9.31-RPT-0010 for more details on hex ordering.

        Let N be the number of assemblies. Let M be the number of "external hex surfaces" exposed to
        the outer reactor boundary (usually vacuum). M does NOT include reflective surfaces!

        N = self.fc['nintxy']
        M = self.fc['npcxy'] - self.fc['nintxy']*6
        N*6 + M = self.fc['npcxy']

        Returns
        -------
        geodstCoordMap : list of int
            This is an index map between DIF3D "four color" nodal and DIF3D GEODST. It is absolutely necessary for
            interpreting that data read by nuclearDataIO.NHFLUX.readHexPartialCurrents4D.

        externalCurrentPointers : list of int
            This is an index map for the "external hex surfaces" between DIF3D "four color" nodal indexing
            and DIF3D GEODST indexing. "External surfaces" are important, because they contain the
            INCOMING partial currents from the outer reactor boundary.
            This uses the same hex ordering as geodstCoordMap, except that each hex now has 6 subsequent indices.
            If hex of index n (0 to N-1) has a surface of index k (0 to 5) that lies on the vacuum boundary,
            then the index of that surface is N*6 + k + 1.

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

        record = self.getRecord()
        # Number of unique hex assemblies - this is N in the comments above
        nAssem = self.fc["nintxy"]
        # Number of lateral surfaces per hex assembly (always 6)
        nSurf = self.fc["nSurf"]

        numExternalSurfaces = self._getNumExtSurfaces()

        # Initialize numpy arrays to store all hex ordering (and hex surface ordering) data.
        # We don't actually use incomingPointersToAllAssemblies (basically equivalent to nearest neighbors indices),
        # but it's here in case someone needs it in the future.

        # Index pointers to INCOMING partial currents to this assembly
        self.incomingPointersToAllAssemblies = numpy.zeros((nAssem * nSurf), dtype=int)
        # Index pointers to INCOMING partial currents on core outer boundary
        self.externalCurrentPointers = numpy.zeros((numExternalSurfaces), dtype=int)
        # Index pointers to DIF3D GEODST ordering of each assembly
        self.geodstCoordMap = numpy.zeros((nAssem), dtype=int)

        # surfaceIndex = numpy.zeros((nAssem*nSurf))
        # nodeIndex = numpy.zeros((nAssem*nSurf))

        # Loop through all surfaces of all assemblies in the x-y plane.
        for i in range(nAssem):
            for j in range(nSurf):
                self.incomingPointersToAllAssemblies[nSurf * i + j] = record.getInt()
                # surfaceIndex[nSurf*i + j] = math.fmod(nSurf*i+j,nSurf) + 1
                # nodeIndex[nSurf*i + j] = (nSurf*i+j)/nSurf + 1

        # Loop through all external surfaces on the outer core boundary (usually vacuum).
        for i in range(numExternalSurfaces):
            self.externalCurrentPointers[i] = record.getInt()

        # Loop through all assemblies.
        for i in range(nAssem):
            self.geodstCoordMap[i] = record.getInt()

    def readFluxMoments3D(self):
        r"""
        Read multigroup flux moments from the NHFLUX 3D block (file control).

        This reads all 5 planar moments for each DIF3D node on ONE x,y plane. The planar moments for
        DIF3D nodes on different x,y planes (different axial slices) are in a different 3D record.

        Returns
        -------
        fluxMoments : 2-D list of float
            This contains all the flux moments for all core assemblies at ONE axial position.
            The jth planar flux moment of assembly i is fluxMoments[i][j].
            The hex assemblies are ordered according to self.geodstCoordMap.

        See Also
        --------
        nuclearDataIO.NHFLUX.__init__
        nuclearDataIO.NHFLUX.readBasicFileData1D
        nuclearDataIO.NHFLUX.readGeodstCoordMap2D
        fluxRecon.computePinMGFluxAndPower
        nuclearDataIO.ISOTXS.read3D

        """

        record = self.getRecord()

        nAssem = self.fc["nintxy"]  # Number of assemblies in core.
        nMom = self.fc[
            "nMom"
        ]  # There are nMom flux moments per hex block (a hexagonal prism).

        fluxMoments = numpy.zeros(
            (nAssem, nMom)
        )  # Numpy array to store nMom flux moments per assembly in this x-y plane.

        # Loop through all flux moments of all assemblies.
        for i in range(nAssem):
            for j in range(nMom):
                fluxMoments[i, j] = record.getDouble()

        return fluxMoments

    def readHexPartialCurrents4D(self):
        r"""
        Read multigroup hexagonal/laterial partial currents from the NHFLUX 4D block (file control).

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

        N = self.fc['nintxy']
        M = self.fc['npcxy'] - self.fc['nintxy']*6
        N*6 + M = self.fc['npcxy']

        Returns
        -------
        surfCurrents : 2-D list of float
            This contains all the OUTGOING partial currents for each assembly in the given axial plane.
            The OUTGOING partial current on surface j in assembly i is surfCurrents[i][j].
            The hex assemblies are ordered according to self.geodstCoordMap.

        externalSurfCurrents : 1-D list of floats
            This contains all the INCOMING partial currents on "external hex surfaces", which are
                adjacent to the reactor outer boundary (usually vacuum). Internal reflective surfaces
                are NOT included in this!
            These "external hex surfaces" are ordered according to self.externalCurrentPointers.

        See Also
        --------
        nuclearDataIO.NHFLUX.readBasicFileData1D
        nuclearDataIO.NHFLUX.readGeodstCoordMap2D
        nuclearDataIO.NHFLUX.readZPartialCurrents5D
        fluxRecon.computePinMGFluxAndPower
        nuclearDataIO.ISOTXS.read4D

        """

        record = self.getRecord()

        nAssem = self.fc["nintxy"]  # number of assemblies in core x,y plane
        nSurf = self.fc[
            "nSurf"
        ]  # number of lateral surfaces per hex assembly - always 6
        nscoef = self.fc["nscoef"]

        numExternalSurfaces = self._getNumExtSurfaces(nSurf)

        # Create numpy arrays to store all surface-averaged partial currents in this x-y plane
        surfCurrents = numpy.zeros((nAssem, nSurf))
        externalSurfCurrents = numpy.zeros((numExternalSurfaces))

        # Loop through all lateral hex surfaces of all assemblies
        for i in range(nAssem):
            for j in range(nSurf):
                for m in range(nscoef):
                    if m == 0:
                        # OUTGOING partial currents on each lateral hex surface in each assembly
                        surfCurrents[i, j] = record.getDouble()
                    else:
                        record.getDouble()  # other NSCOEF options (like half-angle integrated flux)

        for j in range(numExternalSurfaces):
            for m in range(nscoef):
                if m == 0:
                    # INCOMING current at each surface of outer core boundary
                    externalSurfCurrents[j] = record.getDouble()
                else:
                    record.getDouble()  # other NSCOEF options (like half-angle integrated flux)

        return surfCurrents, externalSurfCurrents

    def readZPartialCurrents5D(self):
        r"""
        Read multigroup axial partial currents from the NHFLUX 5D block (file control).

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

        record = self.getRecord()

        nAssem = self.fc["nintxy"]  # number of assemblies in core x,y plane
        nSurf = 2  # number of axial surfaces per hex block (always 2 - top and bottom)
        nscoef = self.fc["nscoef"]

        # Create numpy array to store all axial (up and down) partial currents on this single x,y plane
        surfCurrents = numpy.zeros((nAssem, nSurf))

        # Loop through all (up and down) partial currents on all hexes
        # These loops are in a different order than in the 4D record above!!!
        # Here we loop through surface FIRST and assemblies SECOND!!!
        for j in range(nSurf):
            for i in range(nAssem):
                for m in range(nscoef):
                    if m == 0:
                        surfCurrents[
                            i, j
                        ] = record.getDouble()  # outward partial current
                    else:
                        record.getDouble()  # other NSCOEF options

        return surfCurrents

    def getEnergyGroupIndex(self, g):
        r"""
        Real fluxes stored in NHFLUX have "normal" (or "forward") energy groups.
        Also see the subclass method NAFLUX.getEnergyGroupIndex().
        """

        return g


class NAFLUX(NHFLUX):
    """
    NAFLUX is similar in format to the NHFLUX, but contains adjoint flux.
    
    It has reversed energy group ordering.
    """

    def getEnergyGroupIndex(self, g):
        r"""
        Adjoint fluxes stored in NAFLUX have "reversed" (or "backward") energy groups.
        """
        ng = self.fc["ngroup"]
        return ng - g - 1


class VARSRC(NHFLUX):
    """
    Fixed source file format for use with variant.
    
    See [VARIANT-2014]_.
    """

    def __init__(self, fName="VARSRC", variant=True):
        """
        Initialize the VARSRC reader object.

        Parameters
        ----------
        fName : str, optional
            The file name of the NHFLUX binary file to be read.

        variant : bool, optional
            Whether or not this NHFLUX/NAFLUX file has the VARIANT output format, which is a bit different than
            the DIF3D nodal format.

        """

        NHFLUX.__init__(self, fName, variant=variant)
        self.srcMoments = []

    def readAllData(self, numDataSetsToRead=1):
        """
        Read all source moments from the DIF3D binary file VARSRC.

        Parameters
        ----------
        numDataSetsToRead : int, optional
            The number of whole-core flux data sets included in this NHFLUX/NAFLUX file that one wishes to be read.
            Some NHFLUX/NAFLUX files, such as NAFLUX files written by SASSYS/DIF3D-K, contain more than one flux
            data set. Each data set overwrites the previous one on the NHFLUX class object, which will contain
            only the numDataSetsToRead-th data set. The first numDataSetsToRead-1 data sets are essentially
            skipped over.

        Outputs
        -------
        self.srcMoments : 2-D list of float
            This contains all the flux moments for all core assemblies at ONE axial position.
            The jth planar flux moment of assembly i is fluxMoments[i][j].
            The hex assemblies are ordered according to self.geodstCoordMap.

        See Also
        --------
        fluxRecon.computePinMGFluxAndPower
        nuclearDataIO.NHFLUX.readFileID
        nuclearDataIO.NHFLUX.readBasicFileData1D
        nuclearDataIO.NHFLUX.readFluxMoments3D
        nuclearDataIO.ISOTXS.__init__

        """

        # Read basic data parameters (number of energy groups, assemblies, axial nodes, etc.)
        self.readBasicFileData1D()

        ng = self.fc["ngroup"]  # number of energy groups
        nz = self.fc["nintk"]  # number of axial nodes (same for each assembly in DIF3D)

        # Note: All flux and current data has units of n/cm^2/s
        self.srcMoments = numpy.zeros((self.fc["nintxy"], nz, self.fc["nMom"], ng))

        for _n in range(numDataSetsToRead):

            # Each record contains nodal data for ONE energy group in ONE axial core slice.
            # Must loop through all energy groups and all axial core slices.

            # The axial surface partial currents are indexed by axial surface (NOT by axial node),
            # so there are nz+1 records for z-surface currents

            # Loop through all energy groups: high-to-low for real, low-to-high for adjoint
            for g in range(ng):  # loop through energy groups

                gEff = self.getEnergyGroupIndex(g)

                for z in range(nz):  # loop through axial nodes
                    self.srcMoments[:, z, :, gEff] = self.readFluxMoments3D()

    def _getNumberOfOddParityTerms(self, pnOrder):
        return self_getNumberOfEvenParityTerms(pnOrder) + pnOrder + 1

    def _getNumberOfEvenParityTerms(self, pnOrder):
        return pnOrder * (pnOrder + 1) / 2


def getNodalFluxReader(adjointFlag):
    r"""
    Returns the appropriate DIF3D nodal flux binary file reader class,
    either NHFLUX (real) or NAFLUX (adjoint).
    """

    if adjointFlag:
        return NAFLUX
    else:
        return NHFLUX


class MacroXS(object):
    """
    Basic macroscopic XS library.

    This is just a thin interface over a dictionary.
     """

    def __init__(self, _debug=False):
        self.macros = {}

    def __repr__(self):
        return "<MacroXS object>"

    def analyzeDifferences(self, otherMacros):
        keys = self.macros.keys()
        keys.sort()
        otherKeys = otherMacros.keys()
        otherKeys.sort()
        missing = []
        for key in keys:
            val = self.macros[key]
            otherval = otherMacros.get(key, 0.0)
            if otherval:
                otherKeys.remove(key)
            elif key[0] not in missing and val:
                missing.append(key[0])

            if val:
                diff = (val - otherval) / val
            else:
                diff = val - otherval

            # ISOTXS is single precision, and skip directional diffusion coeffs.
            if abs(diff) > 1e-7 and key[0] not in ["a1", "a2", "a3", "pc"]:
                runLog.important(
                    "{0:10s} {1: 20.10E} {2: 20.10E}".format(key, val, otherval)
                )

        newKeys = []
        for k in otherKeys:
            if k[0] not in newKeys:
                newKeys.append(k[0])

        missing += newKeys
        if missing:
            print(("Missing keys ", missing))
