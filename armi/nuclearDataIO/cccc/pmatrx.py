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
Module for reading PMATRX files which contain gamma productions from fission reactions.

See  [GAMSOR]_ and [MC23]_.

.. [MC23] Lee, Changho, Jung, Yeon Sang, and Yang, Won Sik. MC2-3: Multigroup Cross Section
          Generation Code for Fast Reactor Analysis Nuclear. United States: N. p., 2018. Web.
          doi:10.2172/1483949. (`OSTI
          <https://www.osti.gov/biblio/1483949-mc2-multigroup-cross-section-generation-code-fast-reactor-analysis-nuclear>`__)
"""

import traceback

from armi import runLog
from armi.nuclearDataIO import cccc, xsLibraries, xsNuclides
from armi.utils import properties


def compare(lib1, lib2):
    """Compare two XSLibraries, and return True if equal, or False if not."""
    equal = True
    # first check the lib properties (also need to unlock to prevent from getting an exception).
    equal &= xsLibraries.compareXSLibraryAttribute(
        lib1, lib2, "neutronEnergyUpperBounds"
    )
    equal &= xsLibraries.compareXSLibraryAttribute(lib1, lib2, "gammaEnergyUpperBounds")
    equal &= xsLibraries.compareXSLibraryAttribute(
        lib1, lib2, "neutronDoseConversionFactors"
    )
    equal &= xsLibraries.compareXSLibraryAttribute(
        lib1, lib2, "gammaDoseConversionFactors"
    )
    # compare the meta data
    equal &= lib1.pmatrxMetadata.compare(lib2.pmatrxMetadata, lib1, lib2)
    # check the nuclides
    for nucName in set(lib1.nuclideLabels + lib2.nuclideLabels):
        nuc1 = lib1.get(nucName, None)
        nuc2 = lib2.get(nucName, None)
        if nuc1 is None or nuc2 is None:
            continue
        equal &= compareNuclideXS(nuc1, nuc2)
    return equal


def compareNuclideXS(nuc1, nuc2):
    equal = nuc1.pmatrxMetadata.compare(
        nuc2.pmatrxMetadata, nuc1.container, nuc2.container
    )
    for attrName in [
        "neutronHeating",
        "neutronDamage",
        "gammaHeating",
        "isotropicProduction",
        "linearAnisotropicProduction",
        "nOrderProductionMatrix",
    ]:
        val1 = getattr(nuc1, attrName)
        val2 = getattr(nuc2, attrName)
        if not properties.numpyHackForEqual(val1, val2):
            runLog.important(
                "{} and {} have different `{}` attributes:\n{}\n{}".format(
                    nuc1, nuc2, attrName, val1, val2
                )
            )
            equal &= False
    return equal


def addDummyNuclidesToLibrary(lib, dummyNuclides):
    """
    This method adds DUMMY nuclides to the current PMATRX library.

    Parameters
    ----------
    lib : obj
        PMATRX  library object

    dummyNuclides: list
        List of DUMMY nuclide objects that will be copied and added to the PMATRX file

    Notes
    -----
    Since MC2-3 does not write DUMMY nuclide information for PMATRX files, this is necessary to provide a
    consistent set of nuclide-level data across all the nuclides in a
    :py:class:`~armi.nuclearDataIO.xsLibraries.XSLibrary`.
    """
    if not dummyNuclides:
        runLog.important("No dummy nuclide data provided to be added to {}".format(lib))
        return False
    if len(lib.xsIDs) > 1:
        runLog.warning(
            "Cannot add dummy nuclide data to PMATRX library {} containing data for more than 1 XS ID.".format(
                lib
            )
        )
        return False
    dummyNuclideKeysAddedToLibrary = []
    for dummy in dummyNuclides:
        dummyKey = dummy.nucLabel + lib.xsIDs[0]
        if dummyKey in lib:
            continue
        runLog.debug("Adding {} nuclide data to {}".format(dummyKey, lib))
        newDummy = xsNuclides.XSNuclide(lib, dummyKey)
        newDummy.pmatrxMetadata["hasNeutronHeatingAndDamage"] = False
        newDummy.pmatrxMetadata["maxScatteringOrder"] = 0
        newDummy.pmatrxMetadata["hasGammaHeating"] = False
        newDummy.pmatrxMetadata["numberNeutronXS"] = 0
        newDummy.pmatrxMetadata["collapsingRegionNumber"] = 0
        lib[dummyKey] = newDummy
        dummyNuclideKeysAddedToLibrary.append(dummyKey)

    return any(dummyNuclideKeysAddedToLibrary)


def readBinary(fileName):
    """Read a binary PMATRX file into an :py:class:`~armi.nuclearDataIO.xsLibraries.IsotxsLibrary` object."""
    return _read(fileName, "rb")


def readAscii(fileName):
    """Read an ASCII PMATRX file into an :py:class:`~armi.nuclearDataIO.xsLibraries.IsotxsLibrary` object."""
    return _read(fileName, "r")


def _read(fileName, fileMode):
    lib = xsLibraries.IsotxsLibrary()
    return _readWrite(
        lib,
        fileName,
        fileMode,
        lambda containerKey: xsNuclides.XSNuclide(lib, containerKey),
    )


def writeBinary(lib, fileName):
    """Write the PMATRX data from an :py:class:`~armi.nuclearDataIO.xsLibraries.IsotxsLibrary`
    object to a binary file.
    """
    return _write(lib, fileName, "wb")


def writeAscii(lib, fileName):
    """Write the PMATRX data from an :py:class:`~armi.nuclearDataIO.xsLibraries.IsotxsLibrary`
    object to an ASCII file.
    """
    return _write(lib, fileName, "w")


def _write(lib, fileName, fileMode):
    return _readWrite(lib, fileName, fileMode, lambda containerKey: lib[containerKey])


def _readWrite(lib, fileName, fileMode, getNuclideFunc):
    with PmatrxIO(fileName, lib, fileMode, getNuclideFunc) as rw:
        rw.readWrite()

    return lib


class PmatrxIO(cccc.Stream):
    def __init__(self, fileName, xsLib, fileMode, getNuclideFunc):
        cccc.Stream.__init__(self, fileName, fileMode)
        self._lib = xsLib
        self._metadata = xsLib.pmatrxMetadata
        self._metadata.fileNames.append(fileName)
        self._getNuclide = getNuclideFunc
        self._dummyNuclideKeysAddedToLibrary = []

    def _rwMessage(self):
        runLog.debug(
            "{} PMATRX data {}".format(
                "Reading" if "r" in self._fileMode else "Writing", self
            )
        )

    def readWrite(self):
        """Read and write PMATRX files.

        .. impl:: Tool to read and write PMATRX files.
            :id: I_ARMI_NUCDATA_PMATRX
            :implements: R_ARMI_NUCDATA_PMATRX

            Reading and writing PMATRX files is performed using the general
            nuclear data I/O functionalities described in
            :need:`I_ARMI_NUCDATA`. Reading/writing a PMATRX file is performed
            through the following steps:

            #. Read/write global information including:

                * Number of gamma energy groups
                * Number of neutron energy groups
                * Maximum scattering order
                * Maximum number of compositions
                * Maximum number of materials
                * Maximum number of regions

            #. Read/write energy group structure for neutrons and gammas
            #. Read/write dose conversion factors
            #. Read/write gamma production matrices for each nuclide, as well as
               other reaction constants related to neutron-gamma production.
        """
        self._rwMessage()
        properties.unlockImmutableProperties(self._lib)
        try:
            numNucs = self._rwFileID()
            self._rwGroupStructure()
            self._rwDoseConversionFactor()
            self._rwIsotopes(numNucs)
        except Exception:
            runLog.error(traceback.format_exc())
            raise OSError("Failed to read/write {}".format(self))
        finally:
            properties.lockImmutableProperties(self._lib)

    def _rwFileID(self):
        with self.createRecord() as record:
            for name in [
                "numberCollapsingSpatialRegions",
                "numGammaGroups",
                "numNeutronGroups",
            ]:
                self._metadata[name] = record.rwInt(self._metadata[name])
            self._metadata["hasInPlateData"] = record.rwBool(
                self._metadata["hasInPlateData"]
            )
            numNucs = record.rwInt(len(self._lib))
            self._metadata["hasDoseConversionFactor"] = record.rwBool(
                self._metadata["hasDoseConversionFactor"]
            )
            for name in [
                "maxScatteringOrder",
                "maxNumberOfCompositions",
                "maxMaterials",
                "maxNumberOfRegions",
                "maxNumberOfCollapsingRegions",
                "_dummy1",
                "_dummy2",
            ]:
                self._metadata[name] = record.rwInt(self._metadata[name])
        return numNucs

    def _rwGroupStructure(self):
        with self.createRecord() as record:
            self._lib.neutronEnergyUpperBounds = record.rwMatrix(
                self._lib.neutronEnergyUpperBounds, self._metadata["numNeutronGroups"]
            )
            self._metadata["minimumNeutronEnergy"] = record.rwFloat(
                self._metadata["minimumNeutronEnergy"]
            )
            # The lower bound energy is included in this list. We'll drop it to maintain consistency with other
            # libs by holding only the upper bounds.
            self._lib.gammaEnergyUpperBounds = record.rwMatrix(
                self._lib.gammaEnergyUpperBounds, self._metadata["numGammaGroups"]
            )
            self._metadata["minimumGammaEnergy"] = record.rwFloat(
                self._metadata["minimumGammaEnergy"]
            )

    def _rwDoseConversionFactor(self):
        if self._metadata["hasDoseConversionFactor"]:
            with self.createRecord() as record:
                self._lib.neutronDoseConversionFactors = record.rwList(
                    self._lib.neutronDoseConversionFactors,
                    "float",
                    self._metadata["numNeutronGroups"],
                )
                self._lib.gammaDoseConversionFactors = record.rwList(
                    self._lib.gammaDoseConversionFactors,
                    "float",
                    self._metadata["numGammaGroups"],
                )

    def _rwIsotopes(self, numNucs):
        with self.createRecord() as record:
            nuclideLabels = record.rwList(self._lib.nuclideLabels, "string", numNucs, 8)
            record.rwList([1000] * numNucs, "int", numNucs)
        numNeutronGroups = self._metadata["numNeutronGroups"]
        numGammaGroups = self._metadata["numGammaGroups"]
        for nucLabel in nuclideLabels:
            nuclide = self._getNuclide(nucLabel)
            nuclide.updateBaseNuclide()
            nuclideReader = _PmatrxNuclideIO(
                nuclide, self, numNeutronGroups, numGammaGroups
            )
            nuclideReader.rwNuclide()
            if "r" in self._fileMode:
                # on add nuclides when reading
                self._lib[nucLabel] = nuclide

    def _rwCompositions(self):
        if self._metadata["hasInPlateData"]:
            raise NotImplementedError()


class _PmatrxNuclideIO:
    def __init__(self, nuclide, pmatrixIO, numNeutronGroups, numGammaGroups):
        self._nuclide = nuclide
        self._metadata = nuclide.pmatrxMetadata
        self._pmatrixIO = pmatrixIO
        self._numNeutronGroups = numNeutronGroups
        self._numGammaGroups = numGammaGroups

    def rwNuclide(self):
        self._rwNuclideHeading()
        self._rwNeutronHeatingAndDamage()
        self._rwReactionXS()
        self._rwGammaHeating()
        self._rwCellAveragedProductionMatrix()

    def _rwNuclideHeading(self):
        with self._pmatrixIO.createRecord() as record:
            self._metadata["hasNeutronHeatingAndDamage"] = record.rwBool(
                self._metadata["hasNeutronHeatingAndDamage"]
            )
            self._metadata["maxScatteringOrder"] = record.rwInt(
                self._metadata["maxScatteringOrder"]
            )
            self._metadata["hasGammaHeating"] = record.rwBool(
                self._metadata["hasGammaHeating"]
            )
            self._metadata["numberNeutronXS"] = record.rwInt(
                self._metadata["numberNeutronXS"]
            )
            self._metadata["collapsingRegionNumber"] = record.rwInt(
                self._metadata["collapsingRegionNumber"]
            )

    def _rwNeutronHeatingAndDamage(self):
        if not self._metadata["hasNeutronHeatingAndDamage"]:
            return
        with self._pmatrixIO.createRecord() as record:
            self._nuclide.neutronHeating = record.rwMatrix(
                self._nuclide.neutronHeating, self._numNeutronGroups
            )
            self._nuclide.neutronDamage = record.rwMatrix(
                self._nuclide.neutronDamage, self._numNeutronGroups
            )

    def _rwReactionXS(self):
        numActivationXS = self._metadata["numberNeutronXS"]
        pmatrixParams = self._metadata
        activationXS = self._metadata["activationXS"] = (
            self._metadata["activationXS"] or [None] * numActivationXS
        )
        activationMT = self._metadata["activationMT"] = (
            self._metadata["activationMT"] or [None] * numActivationXS
        )
        activationMTU = self._metadata["activationMTU"] = (
            self._metadata["activationMTU"] or [None] * numActivationXS
        )
        for xsNum in range(numActivationXS):
            with self._pmatrixIO.createRecord() as record:
                pmatrixParams["activationXS"][xsNum] = record.rwList(
                    activationXS[xsNum], self._numNeutronGroups
                )
                pmatrixParams["activationMT"][xsNum] = record.rwInt(activationMT[xsNum])
                pmatrixParams["activationMTU"][xsNum] = record.rwInt(
                    activationMTU[xsNum]
                )

    def _rwGammaHeating(self):
        if not self._metadata["hasGammaHeating"]:
            return
        with self._pmatrixIO.createRecord() as record:
            self._nuclide.gammaHeating = record.rwMatrix(
                self._nuclide.gammaHeating, self._numGammaGroups
            )

    def _rwCellAveragedProductionMatrix(self):
        for lrd in range(1, 1 + self._metadata["maxScatteringOrder"]):
            with self._pmatrixIO.createRecord() as record:
                prodMatrix = self._getProductionMatrix(lrd)
                prodMatrix = record.rwMatrix(
                    prodMatrix, self._numNeutronGroups, self._numGammaGroups
                )
                self._setProductionMatrix(lrd, prodMatrix)

    def _getProductionMatrix(self, order):
        if order == 1:
            return self._nuclide.isotropicProduction
        elif order == 2:
            return self._nuclide.linearAnisotropicProduction
        else:
            return self._nuclide.nOrderProductionMatrix[order]

    def _setProductionMatrix(self, order, matrix):
        if order == 1:
            self._nuclide.isotropicProduction = matrix
        elif order == 2:
            self._nuclide.linearAnisotropicProduction = matrix
        else:
            self._nuclide.nOrderProductionMatrix[order] = matrix
