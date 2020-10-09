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

from .nhflux import NHFLUX


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
            The number of whole-core flux data sets included in this NHFLUX/NAFLUX file
            that one wishes to be read.  Some NHFLUX/NAFLUX files, such as NAFLUX files
            written by SASSYS/DIF3D-K, contain more than one flux data set. Each data set
            overwrites the previous one on the NHFLUX class object, which will contain
            only the numDataSetsToRead-th data set. The first numDataSetsToRead-1 data
            sets are essentially skipped over.

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
        return self._getNumberOfEvenParityTerms(pnOrder) + pnOrder + 1

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
