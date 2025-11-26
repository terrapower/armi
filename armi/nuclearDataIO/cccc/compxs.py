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
COMPXS is a binary file that contains multigroup macroscopic cross sections for homogenized
regions in a full core. The file format can be found in [DIF3D]_.

.. [DIF3D] Derstine, K. L. DIF3D: A Code to Solve One-, Two-, and
           Three-Dimensional Finite-Difference Diffusion Theory Problems,
           report, April 1984; Argonne, Illinois.
           (https://digital.library.unt.edu/ark:/67531/metadc283553/:
           accessed October 17, 2019), University of North Texas Libraries,
           Digital Library, https://digital.library.unt.edu; crediting UNT
           Libraries Government Documents Department.

The file structure is listed here ::

          RECORD TYPE                           PRESENT IF
          ===================================   ==========
          SPECIFICATIONS                        ALWAYS
          COMPOSITION INDEPENDENT DATA          ALWAYS
    ********* (REPEAT FOR ALL COMPOSITIONS)
    *     COMPOSITION SPECIFICATIONS            ALWAYS
    *  ****** (REPEAT FOR ALL ENERGY GROUPS
    *  *       IN THE ORDER OF DECREASING
    *  *       ENERGY)
    *  *  COMPOSITION MACROSCOPIC GROUP         ALWAYS
    *  *  CROSS SECTIONS
    *********
          POWER CONVERSION FACTORS              ALWAYS

See Also
--------
:py:mod:`armi.nuclearDataIO.cccc.isotxs`

Examples
--------
    >>> from armi.nuclearDataIO import compxs
    >>> lib = compxs.readBinary("COMPXS")
    >>> r0 = lib.regions[0]
    >>> r0.macros.fission
    # returns fission XS for this region
    >>> r0.macros.higherOrderScatter[1]
    # returns P1 scattering matrix
    >>> r0.macros.higherOrderScatter[5] *= 0  # zero out P5 scattering matrix
    >>> compxs.writeBinary(lib, "COMPXS2")

Notes
-----
Power conversion factors are used by some codes to determine how to scale the flux
in a region to a desired power based on either fissions/watt-second or
captures/watt-second. If the user does not plan on using these values, the COMPXS
format indicates the values should be set to ``-1E+20``.

The value of ``powerConvMult`` "times the group J integrated flux for the regions
containing the current composition yields the total power in those regions and
energy group J due to fissions and non-fission absorptions."

The ``d<1,2,3>Multiplier`` values are the first, second, and third dimension
directional diffusion coefficient multipliers, respectively. Similarly, the ``d<1,2,3>Additive``
values are the first, second, and third dimension directional diffusion coefficient
additive terms, respectively.
"""

from traceback import format_exc

import numpy as np
from scipy.sparse import csc_matrix

from armi import runLog
from armi.nuclearDataIO import cccc
from armi.nuclearDataIO.nuclearFileMetadata import (
    COMPXS_POWER_CONVERSION_FACTORS,
    REGIONXS_POWER_CONVERT_DIRECTIONAL_DIFF,
    RegionXSMetadata,
)
from armi.nuclearDataIO.xsCollections import XSCollection
from armi.utils.properties import lockImmutableProperties, unlockImmutableProperties


def _getRegionIO():
    return _CompxsRegionIO


def _flattenScatteringVector(colVector, group, numUpScatter, numDownScatter):
    flatVector = colVector[group - numDownScatter : group + numUpScatter + 1].toarray().flatten()
    return list(reversed(flatVector))


def compare(lib1, lib2, tolerance=0.0, verbose=False):
    """
    Compare two COMPXS libraries and return True if equal, or False if not equal.

    Parameters
    ----------
    lib1: XSLibrary
        first library
    lib2: XSLibrary
        second library
    tolerance: float
        Disregard errors that are less than tolerance.
    verbose: bool
        show the macroscopic cross sections that are not equal

    Returns
    -------
    equals: bool
        True if libraries are equal, else false
    """
    from armi.nuclearDataIO.xsLibraries import compareLibraryNeutronEnergies

    equals = True
    equals &= compareLibraryNeutronEnergies(lib1, lib2, tolerance)
    equals &= lib1.compxsMetadata.compare(lib2.compxsMetadata, lib1, lib2, tolerance)
    for regionName in set(lib1.regionLabels + lib2.regionLabels):
        region1 = lib1[regionName]
        region2 = lib2[regionName]
        if region1 is None or region2 is None:
            warning = "Region {} is not in library {} and cannot be compared"
            if region1:
                runLog.warning(warning.format(region1, 2))
            if region2:
                runLog.warning(warning.format(region2, 1))
                equals = False
                continue
        equals &= _compareRegionXS(region1, region2, tolerance, verbose)
    return equals


def _compareRegionXS(region1, region2, tolerance, verbose):
    """Compare the macroscopic cross sections between two homogenized regions."""
    return region1.macros.compare(region2.macros, None, tolerance, verbose)


class _CompxsIO(cccc.Stream):
    """Semi-abstract stream used for reading to/writing from a COMPXS file.

    Parameters
    ----------
    fileName: str
        path to compxs file
    lib: armi.nuclearDataIO.xsLibrary.CompxsLibrary
        Compxs library that is being written to or read from `fileName`
    fileMode: str
        string indicating if ``fileName`` is being read or written, and
        in ascii or binary format
    getRegionFunc: function
        function that returns a :py:class:`CompxsRegion` object given the name of
        the region.

    See Also
    --------
    armi.nuclearDataIO.cccc.isotxs.IsotxsIO
    """

    _METADATA_TAGS = (
        "numComps",
        "numGroups",
        "fileWideChiFlag",
        "numFissComps",
        "maxUpScatterGroups",
        "maxDownScatterGroups",
        "numDelayedFam",
        "maxScatteringOrder",
    )

    def __init__(self, fileName, lib, fileMode, getRegionFunc):
        cccc.Stream.__init__(self, fileName, fileMode)
        self._lib = lib
        self._metadata = self._getFileMetadata()
        self._metadata.fileNames.append(fileName)
        self._getRegion = getRegionFunc
        self._isReading = "r" in self._fileMode

    def _getFileMetadata(self):
        return self._lib.compxsMetadata

    def isReadingCompxs(self):
        return self._isReading

    def fileMode(self):
        return self._fileMode

    @classmethod
    def _read(cls, fileName, fileMode):
        from armi.nuclearDataIO.xsLibraries import CompxsLibrary

        lib = CompxsLibrary()
        return cls._readWrite(
            lib,
            fileName,
            fileMode,
            lambda containerKey: CompxsRegion(lib, containerKey),
        )

    @classmethod
    def _write(cls, lib, fileName, fileMode):
        return cls._readWrite(lib, fileName, fileMode, lambda containerKey: lib[containerKey])

    @classmethod
    def _readWrite(cls, lib, fileName, fileMode, getRegionFunc):
        with _CompxsIO(fileName, lib, fileMode, getRegionFunc) as rw:
            rw.readWrite()
        return lib

    def readWrite(self):
        """
        Read from or write to the COMPXS file.

        See Also
        --------
        armi.nuclearDataIO.cccc.isotxs.IsotxsIO.readWrite : reading/writing ISOTXS files
        """
        runLog.info("{} macroscopic cross library {}".format("Reading" if self._isReading else "Writing", self))
        unlockImmutableProperties(self._lib)
        try:
            regNames = self._rw1DRecord(self._lib.regionLabels)
            self._rw2DRecord()
            for regLabel in regNames:
                region = self._getRegion(regLabel)
                regionIO = _getRegionIO()(region, self, self._lib)
                regionIO.rwRegionData()
            self._rw5DRecord()
        except Exception:
            raise OSError("Failed to {} {} \n\n\n{}".format("read" if self._isReading else "write", self, format_exc()))
        finally:
            lockImmutableProperties(self._lib)

    def _rw1DRecord(self, regNames):
        """Write the specifications block."""
        with self.createRecord() as record:
            for datum in self._METADATA_TAGS:
                self._metadata[datum] = record.rwInt(self._metadata[datum])
            self._metadata["reservedFlag1"] = record.rwInt(self._metadata["reservedFlag1"])
            self._metadata["reservedFlag2"] = record.rwInt(self._metadata["reservedFlag2"])
            regNames = list(range(self._metadata["numComps"]))
        return regNames

    def _rw2DRecord(self):
        """Write the composition independent data block."""
        with self.createRecord() as record:
            if self._metadata["fileWideChiFlag"]:
                self._metadata["fileWideChi"] = record.rwMatrix(
                    self._metadata["fileWideChi"],
                    (self._metadata["fileWideChiFlag"], self._metadata["numGroups"]),
                )
            self._rwLibraryEnergies(record)
            self._metadata["minimumNeutronEnergy"] = record.rwDouble(self._metadata["minimumNeutronEnergy"])
            self._rwDelayedProperties(record, self._metadata["numDelayedFam"])

    def _rwLibraryEnergies(self, record):
        self._lib.neutronVelocity = record.rwList(self._lib.neutronVelocity, "double", self._metadata["numGroups"])
        self._lib.neutronEnergyUpperBounds = record.rwList(
            self._lib.neutronEnergyUpperBounds, "double", self._metadata["numGroups"]
        )

    def _rwDelayedProperties(self, record, numDelayedFam):
        if numDelayedFam:
            self._metadata["delayedChi"] = record.rwMatrix(
                self._metadata["delayedChi"],
                (self._metadata["numGroups"], numDelayedFam),
            )

            self._metadata["delayedDecayConstant"] = record.rwList(
                self._metadata["delayedDecayConstant"], "double", numDelayedFam
            )

        self._metadata["compFamiliesWithPrecursors"] = record.rwList(
            self._metadata["compFamiliesWithPrecursors"],
            "int",
            self._metadata["numComps"],
        )

    def _rw5DRecord(self):
        """Write power conversion factors."""
        numComps = self._getFileMetadata()["numComps"]
        with self.createRecord() as record:
            for factor in COMPXS_POWER_CONVERSION_FACTORS:
                self._getFileMetadata()[factor] = record.rwList(self._getFileMetadata()[factor], "double", numComps)


readBinary = _CompxsIO.readBinary
readAscii = _CompxsIO.readAscii
writeBinary = _CompxsIO.writeBinary
writeAscii = _CompxsIO.writeAscii


class _CompxsRegionIO:
    """
    Specific object assigned a single region to read/write composition information.

    Used with _COMPXS object to read/write 3D and 4D records -
    composition specifications and compsosition macroscopic cross sections.

    Cross sections are read/written in order of decreasing energy.

    This differs from the _COMPXS object, as this object acts on a single region, but
    uses the file mode and file path from the _COMPXS region that instantiated this object.
    """

    _ORDERED_PRIMARY_XS = ("absorption", "total", "removal", "transport")

    def __init__(self, region, compxsIO, lib):
        self._lib = lib
        self._compxsIO = compxsIO
        self._region = region
        self._numGroups = self._getFileMetadata()["numGroups"]
        self._fileMode = compxsIO.fileMode()
        self._isReading = compxsIO.isReadingCompxs()

    def _getRegionMetadata(self):
        return self._region.metadata

    def _getFileMetadata(self):
        return self._lib.compxsMetadata

    def rwRegionData(self):
        """Read/write the region specific information for this composition."""
        self._rw3DRecord()
        self._rw4DRecord()

    def _rw3DRecord(self):
        r"""Write the composition specifications block."""
        with self._compxsIO.createRecord() as record:
            self._getRegionMetadata()["chiFlag"] = record.rwInt(self._getRegionMetadata()["chiFlag"])
            self._getRegionMetadata()["numUpScatterGroups"] = record.rwList(
                self._getRegionMetadata()["numUpScatterGroups"], "int", self._numGroups
            )
            self._getRegionMetadata()["numDownScatterGroups"] = record.rwList(
                self._getRegionMetadata()["numDownScatterGroups"],
                "int",
                self._numGroups,
            )
            if self._getRegionMetadata()["numPrecursorFamilies"]:
                self._getRegionMetadata()["numFamI"] = record.rwList(
                    self._getRegionMetadata()["numFamI"],
                    "int",
                    self._getRegionMetadata()["numPrecursorFamilies"],
                )

    def _rw4DRecord(self):
        r"""Write the composition macroscopic cross sections."""
        if self._isReading:
            self._region.allocateXS(self._getFileMetadata()["numGroups"])

        for group in range(self._getFileMetadata()["numGroups"]):
            with self._compxsIO.createRecord() as record:
                self._rwGroup4DRecord(record, group, self._region.macros)
        if self._isReading:
            self._region.makeScatteringMatrices()

    def _rwGroup4DRecord(self, record, group, macros):
        self._rwPrimaryXS(record, group, macros)
        self._rwScatteringMatrix(record, group, macros, 0)

        for datum in REGIONXS_POWER_CONVERT_DIRECTIONAL_DIFF:
            self._getRegionMetadata()[datum][group] = record.rwDouble(self._getRegionMetadata()[datum][group])

        if self._getRegionMetadata()["numPrecursorFamilies"]:
            self._getRegionMetadata()["numPrecursorsProduced", group] = record.rwList(
                self._getRegionMetadata()["numPrecursorsProduced", group],
                "int",
                self._getRegionMetadata()["numPrecursorFamilies"],
            )

        macros.n2n[group] = record.rwDouble(macros.n2n[group])
        for higherOrder in range(1, self._getFileMetadata()["maxScatteringOrder"] + 1):
            self._rwScatteringMatrix(record, group, macros, higherOrder)

    def _rwPrimaryXS(self, record, group, macros):
        for xs in self._ORDERED_PRIMARY_XS:
            macros[xs][group] = record.rwDouble(macros[xs][group])

        if self._getRegionMetadata()["chiFlag"]:
            macros["fission"][group] = record.rwDouble(macros["fission"][group])
            macros["nuSigF"][group] = record.rwDouble(macros["nuSigF"][group])
            macros["chi"][group] = record.rwList(macros["chi"][group], "double", self._getRegionMetadata()["chiFlag"])

    def _rwScatteringMatrix(self, record, group, macros, order):
        numUpScatter = self._getRegionMetadata()["numUpScatterGroups"][group]
        numDownScatter = self._getRegionMetadata()["numDownScatterGroups"][group]

        sparseMat = macros.higherOrderScatter[order] if order else macros.totalScatter

        dataj = (
            None
            if self._isReading
            else _flattenScatteringVector(sparseMat[:, group], group, numUpScatter, numDownScatter)
        )

        dataj = record.rwList(dataj, "double", numUpScatter + 1 + numDownScatter)
        indicesj = list(reversed(range(group - numDownScatter, group + numUpScatter + 1)))

        if self._isReading:
            sparseMat.addColumnData(dataj, indicesj)


class _CompxsScatterMatrix:
    """When reading COMPXS scattering blocks, store the data here and then reconstruct after."""

    def __init__(self, shape):
        self.data = []
        self.indices = []
        self.indptr = [0]
        self.shape = shape

    def addColumnData(self, dataj, indicesj):
        self.data.extend(dataj)
        self.indices.extend(indicesj)
        self.indptr.append(len(dataj) + self.indptr[-1])

    def makeSparse(self, sparseFunc=csc_matrix):
        self.data = np.array(self.data, dtype="d")
        self.indices = np.array(self.indices, dtype="d")
        self.indptr = np.array(self.indptr, dtype="d")
        return sparseFunc((self.data, self.indices, self.indptr), shape=self.shape)


class CompxsRegion:
    """
    Class for creating/tracking homogenized region information.

    Notes
    -----
    Region objects are created from reading COMPXS files through
    :py:meth:`~_CompxsIO.readWrite` and connected to the resulting library,
    similar to instances of :py:class:`~armi.nuclearDataIO.xsNuclides.XSNuclide`. This allows instances
    of :py:class:`~armi.nuclearDataIO.xsLibraries.CompxsLibrary` to read from and write to ``COMPXS`` files,
    access region information by name, and plot macroscopic cross sections from the homogenized regions.

    The main attributes for an instance of `Region` are the macroscopic cross sections,
    ``macros``, and the metadata. The metadata deals primarily with delayed neutron information
    and use of the ``fileWideChi``, if that option is set.

    See Also
    --------
    armi.nuclearDataIO.xsNuclides.XSNuclide

    Examples
    --------
    >>> lib = compxs.readBinary("COMPXS")
    >>> lib.regions
        <Region REG00>
        <Region REG01>
        <Region REG02>
        ...
        <Region RegNN>
    >>> r0 = lib.regions[0]
    >>> r10 = lib.regions[10]
    >>> r0.isFissile
        False
    >>> r10.isFissile
        True
    >>> r10.macros.fission
        array([0.01147095,  0.01006284,  0.0065597,  0.00660079,  0.005587,
               ...
               0.08920149,  0.13035864,  0.16192732]
    """

    _primaryXS = ("absorption", "total", "removal", "transport", "n2n")

    def __init__(self, lib, regionNumber):
        self.container = lib
        lib[regionNumber] = self
        self.regionNumber = regionNumber
        self.macros = XSCollection(parent=self)
        self.metadata = self._getMetadata()

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, self.regionNumber)

    def _getFileMetadata(self):
        return self.container.compxsMetadata

    def _getMetadata(self):
        specs = RegionXSMetadata()
        chiFlag = specs["fileWideChiFlag"] = self._getFileMetadata()["fileWideChiFlag"]
        if chiFlag:
            self.macros.chi = specs["fileWideChi"] = self._getFileMetadata()["fileWideChi"]
        compFamiliesWithPrecursors = self._getFileMetadata()["compFamiliesWithPrecursors"]
        if compFamiliesWithPrecursors is not None and compFamiliesWithPrecursors.size:
            specs["numPrecursorFamilies"] = compFamiliesWithPrecursors[self.regionNumber]
        else:
            specs["numPrecursorFamilies"] = 0

        return specs

    def initMetadata(self, groups):
        """Initialize the metadata for this region."""
        self.metadata = self._getMetadata()
        for datum in REGIONXS_POWER_CONVERT_DIRECTIONAL_DIFF:
            if "Additive" in datum:
                quantity = 0.0
            else:
                quantity = 1.0
            self.metadata[datum] = groups * [quantity]
        for datum in COMPXS_POWER_CONVERSION_FACTORS:
            self.metadata[datum] = 1.0

    @property
    def isFissile(self):
        return self.macros.fission is not None

    def allocateXS(self, numGroups):
        r"""
        Allocate the cross section arrays.

        When reading in the cross sections from a COMPXS file, the cross sections are read
        for each energy group, i.e. ..math::

            \Sigma_{a,1},\Sigma_{t,1},\Sigma_{rem,1}, \cdots,
            \Sigma_{a,2},\Sigma_{t,2},\Sigma_{rem,2}, \cdots,
            \Sigma_{a,G},\Sigma_{t,G{,\Sigma_{rem,G}

        Since the cross sections can not be read in with a single read command, the
        arrays are allocated here to be populated later.

        Scattering matrices are read in as columns of a sparse scattering matrix and
        reconstructed after all energy groups have been read in.

        See Also
        --------
        :py:meth:`makeScatteringMatrices`
        """
        for xs in self._primaryXS:
            self.macros[xs] = np.zeros(numGroups)

        self.macros.totalScatter = _CompxsScatterMatrix((numGroups, numGroups))

        if self.metadata["chiFlag"]:
            self.macros.fission = np.zeros(numGroups)
            self.macros.nuSigF = np.zeros(numGroups)
            self.macros.chi = np.zeros((numGroups, self.metadata["chiFlag"]))

        if self._getFileMetadata()["maxScatteringOrder"]:
            for scatterOrder in range(1, self._getFileMetadata()["maxScatteringOrder"] + 1):
                self.macros.higherOrderScatter[scatterOrder] = _CompxsScatterMatrix((numGroups, numGroups))

        for datum in REGIONXS_POWER_CONVERT_DIRECTIONAL_DIFF:
            self.metadata[datum] = (np.zeros(numGroups) if "Additive" in datum else np.ones(numGroups)).tolist()

    def makeScatteringMatrices(self):
        r"""
        Create the sparse scattering matrix from components.

        The scattering matrix :math:`S_{i,j}=\Sigma_{s,i\rightarrow j}` is read in
        from the COMPXS as segments on each column in three parts: ..math::

            XSCATU_J = \lbrace S_{g', J}\vert g'=J+NUP(J), J+NUP(J)-1, cdots, J+1\rbrace

            XSCATJ_J = S_{J,J}

            XSCATD_J = \lbrace S_{g', J}\vert g'=J-1, J-2, \cdots, J_NDN(J) \rbrace

        where :math:`NUP(J)` and :math:`NDN(J)` are the number of group that upscatter and
        downscatter into energy group :math:`J`

        See Also
        --------
        :py:class:`scipy.sparse.csc_matrix`
        """
        self.macros.totalScatter = self.macros.totalScatter.makeSparse()
        self.macros.totalScatter.eliminate_zeros()
        if self._getFileMetadata()["maxScatteringOrder"]:
            for sctOrdr, sctObj in self.macros.higherOrderScatter.items():
                self.macros.higherOrderScatter[sctOrdr] = sctObj.makeSparse()
                self.macros.higherOrderScatter[sctOrdr].eliminate_zeros()

    def getXS(self, interaction):
        """
        Get the macroscopic cross sections for a specific interaction.

        See Also
        --------
        :py:meth:`armi.nucDirectory.XSNuclide.getXS`
        """
        return self.macros[interaction]

    def merge(self, other):
        """Merge attributes of two homogenized Regions."""
        self.metadata = self.metadata.merge(other.metadata, self, other, "COMPXS", OSError)
        self.macros.merge(other.macros)
