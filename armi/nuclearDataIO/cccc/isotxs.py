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
This module reads and writes ISOTXS files.

ISOTXS is a binary file that contains multigroup microscopic cross sections.
ISOTXS stands for  *Isotope Cross Sections*.

ISOTXS files are often created by a lattice physics code such as MC2 or DRAGON and
used as input to a global flux solver such as DIF3D.

This module implements reading and writing of the
ISOTXS file format, consistent with [CCCC-IV]_.

Examples
--------
>>> from armi.nuclearDataIO.cccc import isotxs
>>> myLib = isotxs.readBinary('ISOTXS-ref')
>>> nuc = myLib.getNuclide('U235','AA')
>>> fis5 = nuc.micros.fission[5]
>>> scat = nuc.micros.scatter[(0, 5, 6, 1)] # 1st order elastic scatter from group 5->6
>>> nuc.micros.fission[7] = fis5*1.01       # you can modify the isotxs too.
>>> captureEnergy = nuc.isotxsMetadata["ecapt"]
>>> isotxs.writeBinary(myLib, 'ISOTXS-modified')

"""

import itertools
import traceback

import numpy as np
from scipy import sparse

from armi import runLog
from armi.nuclearDataIO import cccc, xsLibraries, xsNuclides
from armi.utils import properties

# scattering block definitions from ISOTXS
# The definition is:
TOTAL_SCATTER = 0  # 000 + NN = total scattering for Legendre Order NN
ELASTIC_SCATTER = 100  # 100 + NN, ELASTIC SCATTERING
INELASTIC_SCATTER = 200  # 200 + NN, INELASTIC SCATTERING
N2N_SCATTER = 300  # 300 + NN, (N,2N) SCATTERING


def compareSet(fileNames, tolerance=0.0, verbose=False):
    """
    takes a list of strings and reads all binaries with that name comparing them in all combinations.

    Notes
    -----
    useful for finding mcc bugs when you want to compare a series of very similar isotxs outputs
    Verbose gets VERY long
    """
    comparisons = []

    xsLibs = [readBinary(fileName) for fileName in fileNames]
    for thisXSLib, thatXSLib in itertools.combinations(xsLibs, 2):
        # all unique combinations with 2 items
        runLog.info("\n*****\n*****comparing {} and {}\n*****".format(thisXSLib, thatXSLib))
        comparisons.append((compare(thisXSLib, thatXSLib, tolerance, verbose), thisXSLib, thatXSLib))

    sameFileNames = "\n"
    for comparison in comparisons:
        if comparison[0]:
            sameFileNames += "\t{} and {}\n".format(comparison[1], comparison[2])

    sameFileNames = sameFileNames + "None were the same" if sameFileNames == "\n" else sameFileNames
    runLog.info("the following libraries are the same within the specified tolerance:{}".format(sameFileNames))


def compare(lib1, lib2, tolerance=0.0, verbose=False):
    """
    Compare two XSLibraries, and return True if equal, or False if not.

    Notes
    -----
    Tolerance allows the user to ignore small changes that may be caused by
    small library differences or floating point calculations
    the closer to zero the more differences will be shown
    10**-5 is a good tolerance to use if not using default.
    Verbose shows the XS matrixes that are not equal
    """
    equal = True
    # first check the lib properties (also need to unlock to prevent from getting an exception).
    equal &= xsLibraries.compareLibraryNeutronEnergies(lib1, lib2, tolerance)
    # compare the meta data
    equal &= lib1.isotxsMetadata.compare(lib2.isotxsMetadata, lib1, lib2)
    # check the nuclides
    for nucName in set(lib1.nuclideLabels + lib2.nuclideLabels):
        nuc1 = lib1.get(nucName, None)
        nuc2 = lib2.get(nucName, None)
        if nuc1 is None or nuc2 is None:
            warning = "Nuclide {:>20} in library {} is not present in library {} and cannot be compared"
            if nuc1:
                runLog.warning(warning.format(nuc1, 1, 2))
            if nuc2:
                runLog.warning(warning.format(nuc2, 2, 1))
            equal = False
            continue
        nucEqual = compareNuclideXS(nuc1, nuc2, tolerance, verbose, nucName)
        equal &= nucEqual
    return equal


def compareNuclideXS(nuc1, nuc2, tolerance=0.0, verbose=False, nucName=""):
    equal = nuc1.isotxsMetadata.compare(nuc2.isotxsMetadata, nuc1, nuc2)
    equal &= nuc1.micros.compare(nuc2.micros, [], tolerance, verbose, nucName=nucName)
    return equal


def addDummyNuclidesToLibrary(lib, dummyNuclides):
    """
    This method adds DUMMY nuclides to the current ISOTXS library.

    Parameters
    ----------
    lib : obj
        ISOTXS library object

    dummyNuclides: list
        List of DUMMY nuclide objects that will be copied and added to the GAMISO file

    Notes
    -----
    Since MC2-3 does not write DUMMY nuclide information for GAMISO files, this is necessary to provide a
    consistent set of nuclide-level data across all the nuclides in a
    :py:class:`~armi.nuclearDataIO.xsLibraries.XSLibrary`.
    """
    if not dummyNuclides:
        runLog.important("No dummy nuclide data provided to be added to {}".format(lib))
        return False
    elif len(lib.xsIDs) > 1:
        runLog.warning(
            "Cannot add dummy nuclide data to ISOTXS library {} containing data for more than 1 XS ID.".format(lib)
        )
        return False

    dummyNuclideKeysAddedToLibrary = []
    for dummyNuclide in dummyNuclides:
        dummyKey = dummyNuclide.nucLabel
        if len(lib.xsIDs):
            dummyKey += lib.xsIDs[0]
        if dummyKey in lib:
            continue

        newDummy = xsNuclides.XSNuclide(lib, dummyKey)
        newDummy.micros = dummyNuclide.micros
        # Copy isotxs metadata from the isotxs metadata of the given dummy nuclide
        for kk, vv in dummyNuclide.isotxsMetadata.items():
            if kk in ["jj", "jband"]:
                newDummy.isotxsMetadata[kk] = {}
                for mm in vv:
                    newDummy.isotxsMetadata[kk][mm] = 1
            else:
                newDummy.isotxsMetadata[kk] = vv

        lib[dummyKey] = newDummy
        dummyNuclideKeysAddedToLibrary.append(dummyKey)

    return any(dummyNuclideKeysAddedToLibrary)


class IsotxsIO(cccc.Stream):
    """
    A semi-abstract stream for reading and writing to a :py:class:`~armi.nuclearDataIO.isotxs.Isotxs`.

    Notes
    -----
    This is a bit of a special case compared to most other CCCC files because of the special
    nuclide-level container in addition to the XSLibrary container.

    The :py:meth:`~armi.nuclearDataIO.isotxs.IsotxsIO.readWrite` defines the ISOTXS file structure as
    specified in http://t2.lanl.gov/codes/transx-hyper/isotxs.html.
    """

    _FILE_LABEL = "ISOTXS"

    def __init__(self, fileName, lib, fileMode, getNuclideFunc):
        cccc.Stream.__init__(self, fileName, fileMode)
        self._lib = lib
        self._metadata = self._getFileMetadata()
        self._metadata.fileNames.append(fileName)
        self._getNuclide = getNuclideFunc

    def _getFileMetadata(self):
        return self._lib.isotxsMetadata

    def _getNuclideIO(self):
        return _IsotxsNuclideIO

    @classmethod
    def _read(cls, fileName, fileMode):
        lib = xsLibraries.IsotxsLibrary()
        return cls._readWrite(
            lib,
            fileName,
            fileMode,
            lambda containerKey: xsNuclides.XSNuclide(lib, containerKey),
        )

    @classmethod
    def _write(cls, lib, fileName, fileMode):
        return cls._readWrite(lib, fileName, fileMode, lambda containerKey: lib[containerKey])

    @classmethod
    def _readWrite(cls, lib, fileName, fileMode, getNuclideFunc):
        with cls(fileName, lib, fileMode, getNuclideFunc) as rw:
            rw.readWrite()
        return lib

    def _rwMessage(self):
        runLog.debug("{} ISOTXS data {}".format("Reading" if "r" in self._fileMode else "Writing", self))

    def _updateFileLabel(self):
        """
        Update the file label when reading in the ISOTXS-like file if it differs from its expected value.

        Notes
        -----
        This occurs when MC2-3 is preparing GAMISO files.
        The merging of ISOTXS-like files fail if the labels are not unique (i.e. merging ISOTXS into GAMISO with
        each file having a file label of `ISOTXS`.
        """
        if self._metadata["label"] != self._FILE_LABEL:
            runLog.debug(
                "File label in {} is not the expected type. Updating the label from {} to {}".format(
                    self, self._metadata["label"], self._FILE_LABEL
                )
            )
            self._metadata["label"] = self._FILE_LABEL

    def readWrite(self):
        """Read and write ISOTSX file.

        .. impl:: Tool to read and write ISOTXS files.
            :id: I_ARMI_NUCDATA_ISOTXS
            :implements: R_ARMI_NUCDATA_ISOTXS

            Reading and writing ISOTXS files is performed using the general
            nuclear data I/O functionalities described in
            :need:`I_ARMI_NUCDATA`. Reading/writing a ISOTXS file is performed
            through the following steps:

            #. Read/write file ID record
            #. Read/write file 1D record, which includes:

                * Number of energy groups (``NGROUP``)
                * Maximum number of up-scatter groups (``MAXUP``)
                * Maximum number of down-scatter groups (``MAXDN``)
                * Maximum scattering order (``MAXORD``)
                * File-wide specification on fission spectrum type, i.e. vector
                  or matrix (``ICHIST``)
                * Maximum number of blocks of scattering data (``MSCMAX``)
                * Subblocking control for scatter matrices (``NSBLOK``)

            #. Read/write file 2D record, which includes:

                * Library IDs for each isotope (``HSETID(I)``)
                * Isotope names (``HISONM(I)``)
                * Global fission spectrum (``CHI(J)``) if file-wide spectrum is
                  specified (``ICHIST`` = 1)
                * Energy group structure (``EMAX(J)`` and ``EMIN``)
                * Locations of each nuclide record in the file (``LOCA(I)``)

                    .. note::

                        The offset data is not read from the binary file because
                        the ISOTXS reader can dynamically calculate the offset
                        itself. Therefore, during a read operation, this data is
                        ignored.

            #. Read/write file 4D record for each nuclide, which includes
               isotope-dependent, group-independent data.
            #. Read/write file 5D record for each nuclide, which includes
               principal cross sections.
            #. Read/write file 6D record for each nuclide, which includes
               fission spectrum if it is flagged as a matrix (``ICHI`` > 1).
            #. Read/write file 7D record for each nuclide, which includes the
               scattering matrices.
        """
        self._rwMessage()
        properties.unlockImmutableProperties(self._lib)
        try:
            self._fileID()
            numNucs = self._rw1DRecord(len(self._lib))
            nucNames = self._rw2DRecord(numNucs, self._lib.nuclideLabels)
            if self._metadata["fileWideChiFlag"] > 1:
                self._rw3DRecord()
            for nucLabel in nucNames:
                # read nuclide name, other global stuff from the ISOTXS library
                nuc = self._getNuclide(nucLabel)
                if "r" in self._fileMode:
                    # on add nuclides when reading
                    self._lib[nucLabel] = nuc
                nuclideIO = self._getNuclideIO()(nuc, self, self._lib)
                nuclideIO.rwNuclide()
        except Exception:
            raise OSError("Failed to read/write {} \n\n\n{}".format(self, traceback.format_exc()))
        finally:
            properties.lockImmutableProperties(self._lib)

    def _fileID(self):
        with self.createRecord() as record:
            self._metadata["label"] = record.rwString(self._metadata["label"], 24)
            self._metadata["fileId"] = record.rwInt(self._metadata["fileId"])
            self._updateFileLabel()

    def _rw1DRecord(self, numNucs):
        with self.createRecord() as record:
            self._metadata["numGroups"] = record.rwInt(self._metadata["numGroups"])
            numNucs = record.rwInt(numNucs)
            self._metadata["maxUpScatterGroups"] = record.rwInt(self._metadata["maxUpScatterGroups"])
            self._metadata["maxDownScatterGroups"] = record.rwInt(self._metadata["maxDownScatterGroups"])
            self._metadata["maxScatteringOrder"] = record.rwInt(self._metadata["maxScatteringOrder"])
            self._metadata["fileWideChiFlag"] = record.rwInt(self._metadata["fileWideChiFlag"])
            self._metadata["maxScatteringBlocks"] = record.rwInt(self._metadata["maxScatteringBlocks"])
            self._metadata["subblockingControl"] = record.rwInt(self._metadata["subblockingControl"])
        return numNucs

    def _rw2DRecord(self, numNucs, nucNames):
        """
        Read 2D ISOTXS record.

        Notes
        -----
        Contains isotope names, global chi distribution, energy group structure, and locations of
        each nuclide record in the file
        """
        with self.createRecord() as record:
            # skip "merger   test..." string
            self._metadata["libraryLabel"] = record.rwString(self._metadata["libraryLabel"], 12 * 8)
            nucNames = record.rwList(nucNames, "string", numNucs, 8)
            if self._metadata["fileWideChiFlag"] == 1:
                # file-wide chi distribution vector listed here.
                self._metadata["chi"] = record.rwMatrix(self._metadata["chi"], self._metadata["numGroups"])
            self._rwLibraryEnergies(record)
            self._metadata["minimumNeutronEnergy"] = record.rwFloat(self._metadata["minimumNeutronEnergy"])
            record.rwList(self._computeNuclideRecordOffset(), "int", numNucs)
        return nucNames

    def _rwLibraryEnergies(self, record):
        # neutron velocity (cm/s)
        self._lib.neutronVelocity = record.rwMatrix(self._lib.neutronVelocity, self._metadata["numGroups"])
        # read emax for each group in descending eV.
        self._lib.neutronEnergyUpperBounds = record.rwMatrix(
            self._lib.neutronEnergyUpperBounds, self._metadata["numGroups"]
        )

    def _rw3DRecord(self):
        """Read file-wide chi-distribution matrix."""
        raise NotImplementedError

    def _computeNuclideRecordOffset(self):
        """
        Compute the record offset of each nuclide.

        Notes
        -----
        The offset data is not read from the binary file because the ISOTXS
        reader can dynamically calculate the offset itself. Therefore, during a
        read operation, this data is ignored.
        """
        recordsPerNuclide = [self._computeNumIsotxsRecords(nuc) for nuc in self._lib.nuclides]
        return [sum(recordsPerNuclide[0:ii]) for ii in range(len(self._lib))]

    def _computeNumIsotxsRecords(self, nuclide):
        """Compute the number of ISOTXS records for a specific nuclide."""
        numRecords = 2
        metadata = self._getNuclideIO()(nuclide, self, self._lib)._getNuclideMetadata()
        if metadata["chiFlag"] > 1:
            numRecords += 1
        numRecords += sum(1 for _ord in metadata["ords"] if _ord > 0)
        return numRecords


readBinary = IsotxsIO.readBinary
readAscii = IsotxsIO.readAscii
writeBinary = IsotxsIO.writeBinary
writeAscii = IsotxsIO.writeAscii


class _IsotxsNuclideIO:
    """
    A reader/writer class for ISOTXS nuclides.

    Notes
    -----
    This is to be used in conjunction with an IsotxsIO object.
    """

    def __init__(self, nuclide, isotxsIO, lib):
        self._nuclide = nuclide
        self._metadata = self._getNuclideMetadata()
        self._isotxsIO = isotxsIO
        self._lib = lib
        self._fileWideChiFlag = self._getFileMetadata()["fileWideChiFlag"]
        self._fileWideChi = self._getFileMetadata()["chi"]
        self._numGroups = self._getFileMetadata()["numGroups"]
        self._maxScatteringBlocks = self._getFileMetadata()["maxScatteringBlocks"]
        self._subblockingControl = self._getFileMetadata()["subblockingControl"]

    def _getFileMetadata(self):
        return self._lib.isotxsMetadata

    def _getNuclideMetadata(self):
        return self._nuclide.isotxsMetadata

    def _getMicros(self):
        return self._nuclide.micros

    def rwNuclide(self):
        """Read nuclide name, other global stuff from the ISOTXS library."""
        properties.unlockImmutableProperties(self._nuclide)
        try:
            self._rw4DRecord()
            self._nuclide.updateBaseNuclide()
            self._rw5DRecord()
            if self._metadata["chiFlag"] > 1:
                self._rw6DRecord()

            # get scatter matrix
            for blockNumIndex in range(self._maxScatteringBlocks):
                for subBlock in range(self._subblockingControl):
                    if self._metadata["ords"][blockNumIndex] > 0:
                        # ords flag == 1 implies this scatter type of scattering exists on this nuclide.
                        self._rw7DRecord(blockNumIndex, subBlock)
        finally:
            properties.lockImmutableProperties(self._nuclide)

    def _rw4DRecord(self):
        """
        Read 4D ISOTXS record.

        Notes
        -----
        Read the following individual nuclide XS record. Load data into nuc.
        This record contains non-mg data like atomic mass, temperature, and some flags.
        """
        with self._isotxsIO.createRecord() as nucRecord:
            # read string data
            for datum in ["nuclideId", "libName", "isoIdent"]:
                self._metadata[datum] = nucRecord.rwString(self._metadata[datum], 8)

            # read float data
            for datum in ["amass", "efiss", "ecapt", "temp", "sigPot", "adens"]:
                self._metadata[datum] = nucRecord.rwFloat(self._metadata[datum])

            # read integer data
            for datum in [
                "classif",
                "chiFlag",
                "fisFlag",
                "nalph",
                "np",
                "n2n",
                "nd",
                "nt",
                "ltot",
                "ltrn",
                "strpd",
            ]:
                self._metadata[datum] = nucRecord.rwInt(self._metadata[datum])

            # defines what kind of scattering block each block is; total, inelastic, elastic, n2n
            self._metadata["scatFlag"] = nucRecord.rwList(self._metadata["scatFlag"], "int", self._maxScatteringBlocks)

            # number of scattering orders in this block. if 0, this block isn't present.
            self._metadata["ords"] = nucRecord.rwList(self._metadata["ords"], "int", self._maxScatteringBlocks)
            # bandwidth of this block: number of groups that scatter into this group, including this one.
            jband = self._metadata["jband"] or {}
            for n in range(self._maxScatteringBlocks):
                for j in range(self._numGroups):
                    jband[j, n] = nucRecord.rwInt(jband.get((j, n), None))
            self._metadata["jband"] = jband

            # position of in-group scattering for scattering data in group j
            jj = self._metadata["jj"] or {}
            # Some mcc**2 cases seem to just have a bunch of 1's listed here.
            # does this mean we never have upscatter? possibly.
            for n in range(self._maxScatteringBlocks):
                for j in range(self._numGroups):
                    jj[j, n] = nucRecord.rwInt(jj.get((j, n), None))
            self._metadata["jj"] = jj

    def _rw5DRecord(self):
        """Read principal microscopic MG XS data for a nuclide."""
        with self._isotxsIO.createRecord() as record:
            micros = self._getMicros()
            nuc = self._nuclide
            numGroups = self._numGroups
            micros.transport = record.rwMatrix(micros.transport, self._metadata["ltrn"], numGroups)
            micros.total = record.rwMatrix(micros.total, self._metadata["ltot"], numGroups)
            micros.nGamma = record.rwMatrix(micros.nGamma, numGroups)

            if self._metadata["fisFlag"] > 0:
                micros.fission = record.rwMatrix(micros.fission, numGroups)
                micros.neutronsPerFission = record.rwMatrix(micros.neutronsPerFission, numGroups)
            else:
                micros.fission = micros.getDefaultXs(numGroups)
                micros.neutronsPerFission = micros.getDefaultXs(numGroups)

            if self._metadata["chiFlag"] == 1:
                micros.chi = record.rwMatrix(micros.chi, numGroups)
            elif self._metadata["fisFlag"] > 0:
                if self._fileWideChiFlag != 1:
                    raise OSError("Fissile nuclide {} in library but no individual or global chi!".format(nuc))
                micros.chi = self._fileWideChi
            else:
                micros.chi = micros.getDefaultXs(numGroups)

            # read some other important XS, if they exist
            for xstype in ["nalph", "np", "n2n", "nd", "nt"]:
                if self._metadata[xstype]:
                    micros.__dict__[xstype] = record.rwMatrix(micros.__dict__[xstype], numGroups)
                else:
                    micros.__dict__[xstype] = micros.getDefaultXs(numGroups)

            # coordinate direction transport cross section (for various coordinate directions)
            if self._metadata["strpd"] > 0:
                micros.strpd = record.rwMatrix(micros.strpd, self._metadata["strpd"], numGroups)
            else:
                micros.strpd = micros.getDefaultXs(numGroups)

    def _rw6DRecord(self):
        """Reads nuclide-level chi dist."""
        raise NotImplementedError

    def _rw7DRecord(self, blockNumIndex, subBlock):
        """
        Read scatter matrix.

        Parameters
        ----------
        blockNumIndex : int
            Index of the scattering block (aka type of scattering) in this nuclide

        subBlock : int
            Index-tracking integer. Since neutrons don't scatter to and from all energies,
            there is a bandwidth defined to save on storage.

        Notes
        -----
        The data is stored as a giant array, and read in as a CSR matrix. The below matrix is
        lower triangular, where periods are non-zero.

            . 0 0 0 0 0
            . . 0 0 0 0
            . . . 0 0 0
            . . . . 0 0
            . . . . . 0
            . . . . . .

        The data is read in rows starting at the top and going to the bottom.
        Per row, there are JBAND non-zero entries. Per row, there are JJ non-zero entries on or
        beyond the diagonal.

            . 0 0 0 0 0
            - - - - - -
            - - - - - -
            - - - - - -
            - - - - - -
            - - - - - -

        Additionally, the data is reversed for whatever reason. So, let's say we are reading the
        third row in our ficitious matrix. JBAND is 2, JJ is 1. We will read "1" first, and then
        "2" from the ISOTXS. Since they are backwards, we need to reverse the numbers before
        putting them into the matrix.

            . 0 0 0 0 0
            . . - - - -
            . 2 1 - - -
            - - - - - -
            - - - - - -
            - - - - - -

        However, since we are reading a CSR, we can just add the indices in reverse (this is fast)
        and read the data in as is (which is a bit slower). Then we will allow the CSR matrix to
        fix the order later on, if necessary.
        """
        scatter = self._getScatterMatrix(blockNumIndex)
        if scatter is not None:
            scatter = scatter.toarray()
        with self._isotxsIO.createRecord() as record:
            ng = self._numGroups
            nsblok = self._subblockingControl
            m = subBlock + 1  # fix starting at zero problem and use same indices as CCCC specification
            # be careful with starting indices at 0 here!!
            lordn = self._metadata["ords"][blockNumIndex]
            # this is basically how many scattering cross sections there are for this scatter type for this nuclide
            jl = (m - 1) * ((ng - 1) // nsblok + 1) + 1
            jup = m * ((ng - 1) // nsblok + 1)
            ju = min(ng, jup)

            metadata = self._metadata
            indptr = [0]
            indices = []
            dataVals = []
            for _scatterLoopOrder in range(lordn):
                for g in range(jl - 1, ju):
                    jup = g + metadata["jj"][g, blockNumIndex]
                    bandWidth = metadata["jband"][g, blockNumIndex]
                    jdown = jup - bandWidth
                    if scatter is None:
                        indptr.append(len(indices) + bandWidth)
                        # add the indices in reverse
                        indices.extend(range(jup - 1, jdown - 1, -1))
                        # read the data as-is
                        for _ in range(bandWidth):
                            dataVals.append(record.rwFloat(0.0))
                    else:
                        for xs in reversed(scatter[g, jdown:jup].tolist()):
                            record.rwFloat(xs)

        if scatter is None:
            # we're reading.
            scatter = sparse.csr_matrix((np.array(dataVals), indices, indptr), shape=(ng, ng))
            scatter.eliminate_zeros()
            self._setScatterMatrix(blockNumIndex, scatter)

    def _getScatterBlockNum(self, scatterType):
        """
        Determine which scattering block is elastic scattering.

        This information is stored in the scatFlab libparam and is
        possibly different for each nuclide (e.g. C, B-10, etc.)

        Parameters
        ----------
        scatterType : int
            ISOTXS-defined special int flag for a scatter type (100 for elastic, etc.)

        Returns
        -------
        blockNum : int
            A index of the scatter matrix.
        """
        try:
            return np.where(self._metadata["scatFlag"] == scatterType)[0][0]
        except IndexError:
            return None

    def _getElasticScatterBlockNumIndex(self, legendreOrder=0):
        return self._getScatterBlockNum(ELASTIC_SCATTER + legendreOrder)

    def _getInelasticScatterBlockNumIndex(self):
        return self._getScatterBlockNum(INELASTIC_SCATTER)

    def _getN2nScatterBlockNumIndex(self):
        return self._getScatterBlockNum(N2N_SCATTER)

    def _getTotalScatterBlockNumIndex(self):
        return self._getScatterBlockNum(TOTAL_SCATTER)

    def _setScatterMatrix(self, blockNumIndex, scatterMatrix):
        """
        Sets scatter matrix data to the proper ``scatterMatrix`` for this ``blockNum``.

        blockNumIndex : int
            Index of a scattering block.
        """
        if blockNumIndex == self._getElasticScatterBlockNumIndex():
            self._getMicros().elasticScatter = scatterMatrix
        elif blockNumIndex == self._getInelasticScatterBlockNumIndex():
            self._getMicros().inelasticScatter = scatterMatrix
        elif blockNumIndex == self._getN2nScatterBlockNumIndex():
            self._getMicros().n2nScatter = scatterMatrix
        elif blockNumIndex == self._getTotalScatterBlockNumIndex():
            self._getMicros().totalScatter = scatterMatrix
        elif blockNumIndex == self._getElasticScatterBlockNumIndex(1):
            self._getMicros().elasticScatter1stOrder = scatterMatrix
        else:
            self._getMicros().higherOrderScatter[blockNumIndex] = scatterMatrix

    def _getScatterMatrix(self, blockNumIndex):
        """
        Get the scatter matrix for a particular blockNum.

        Notes
        -----
        This logic could be combined with _setScatterMatrix.
        """
        if blockNumIndex == self._getElasticScatterBlockNumIndex():
            scatterMatrix = self._getMicros().elasticScatter
        elif blockNumIndex == self._getInelasticScatterBlockNumIndex():
            scatterMatrix = self._getMicros().inelasticScatter
        elif blockNumIndex == self._getN2nScatterBlockNumIndex():
            scatterMatrix = self._getMicros().n2nScatter
        elif blockNumIndex == self._getTotalScatterBlockNumIndex():
            scatterMatrix = self._getMicros().totalScatter
        elif blockNumIndex == self._getElasticScatterBlockNumIndex(1):
            scatterMatrix = self._getMicros().elasticScatter1stOrder
        else:
            scatterMatrix = self._getMicros().higherOrderScatter.get(blockNumIndex, None)

        return scatterMatrix
