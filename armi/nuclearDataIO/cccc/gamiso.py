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
Module for reading GAMISO files which contains gamma cross section data

GAMISO is a binary file created by MC**2-v3 that contains multigroup microscopic gamma cross sections. GAMISO data is
contained within a :py:class:`~armi.nuclearDataIO.xsLibraries.XSLibrary`.

See [GAMSOR]_. 

.. [GAMSOR] Smith, M. A., Lee, C. H., and Hill, R. N. GAMSOR: Gamma Source Preparation and DIF3D Flux Solution. United States: 
            N. p., 2016. Web. doi:10.2172/1343095. `On OSTI <https://www.osti.gov/biblio/1343095-gamsor-gamma-source-preparation-dif3d-flux-solution>`_
            
"""

from armi import runLog
from armi.nuclearDataIO.cccc import isotxs
from armi.nuclearDataIO import xsLibraries
from armi.nuclearDataIO import xsNuclides


def compare(lib1, lib2):
    """Compare two XSLibraries, and return True if equal, or False if not."""
    equal = True
    # first check the lib properties (also need to unlock to prevent from getting an exception).
    equal &= xsLibraries.compareXSLibraryAttribute(lib1, lib2, "gammaEnergyUpperBounds")
    # compare the meta data
    equal &= lib1.gamisoMetadata.compare(lib2.gamisoMetadata, lib1, lib2)
    # check the nuclides
    for nucName in set(lib1.nuclideLabels + lib2.nuclideLabels):
        nuc1 = lib1.get(nucName, None)
        nuc2 = lib2.get(nucName, None)
        if nuc1 is None or nuc2 is None:
            continue
        equal &= compareNuclideXS(nuc1, nuc2)
    return equal


def compareNuclideXS(nuc1, nuc2):
    equal = nuc1.gamisoMetadata.compare(
        nuc2.gamisoMetadata, nuc1.container, nuc2.container
    )
    equal &= nuc1.gammaXS.compare(nuc2.gammaXS, [])
    return equal


def addDummyNuclidesToLibrary(lib, dummyNuclides):
    """
    This method adds DUMMY nuclides to the current GAMISO library.

    Parameters
    ----------
    lib : obj
        GAMISO library object

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
            "Cannot add dummy nuclide data to GAMISO library {} containing data for more than 1 XS ID.".format(
                lib
            )
        )
        return False

    dummyNuclideKeysAddedToLibrary = []
    for dummyNuclide in dummyNuclides:
        dummyKey = dummyNuclide.nucLabel
        if len(lib.xsIDs):
            dummyKey += lib.xsIDs[0]
        if dummyKey in lib:
            continue

        runLog.debug("Adding {} nuclide data to {}".format(dummyKey, lib))
        newDummy = xsNuclides.XSNuclide(lib, dummyKey)

        # Copy gamiso metadata from the isotxs metadata of the given dummy nuclide
        for kk, vv in dummyNuclide.isotxsMetadata.items():
            if kk in ["jj", "jband"]:
                newDummy.gamisoMetadata[kk] = {}
                for mm in vv:
                    newDummy.gamisoMetadata[kk][mm] = 1
            else:
                newDummy.gamisoMetadata[kk] = vv

        lib[dummyKey] = newDummy
        dummyNuclideKeysAddedToLibrary.append(dummyKey)

    return any(dummyNuclideKeysAddedToLibrary)


class _GamisoIO(isotxs._IsotxsIO):  # pylint: disable=protected-access,abstract-method
    """
    A reader/writer for GAMISO data files.

    Notes
    -----
    The GAMISO file format is identical to ISOTXS.
    """

    def _getFileMetadata(self):
        return self._lib.gamisoMetadata

    def _getNuclideIO(self):
        return _GamisoNuclideIO

    def _rwMessage(self):
        runLog.debug(
            "{} GAMISO data {}".format(
                "Reading" if "r" in self._fileMode else "Writing", self
            )
        )

    def _rwLibraryEnergies(self, record):
        # neutron velocity (cm/s)
        metadata = self._getFileMetadata()
        metadata["gammaVelocity..NOT"] = record.rwList(
            metadata["gammaVelocity..NOT"], "float", self._metadata["numGroups"]
        )
        # read emax for each group in descending eV.
        self._lib.gammaEnergyUpperBounds = record.rwMatrix(
            self._lib.gammaEnergyUpperBounds, self._metadata["numGroups"]
        )


readBinary = _GamisoIO.readBinary
readAscii = _GamisoIO.readAscii
writeBinary = _GamisoIO.writeBinary
writeAscii = _GamisoIO.writeAscii


class _GamisoNuclideIO(
    isotxs._IsotxsNuclideIO
):  # pylint: disable=protected-access,abstract-method
    """
    A reader/writer for GAMISO nuclides.

    Notes
    -----
    The GAMISO file format is identical to ISOTXS.
    """

    _FILE_LABEL = u"GAMISO"

    def _getFileMetadata(self):
        return self._lib.gamisoMetadata

    def _getNuclideMetadata(self):
        return self._nuclide.gamisoMetadata

    def _getMicros(self):
        return self._nuclide.gammaXS
