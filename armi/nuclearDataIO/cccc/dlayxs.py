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
Module to read DLAYXS files, which contain delayed neutron precursor data, including decay constants
and emission spectra.

Similar to ISOTXS files, DLAYXS files are often created by a lattice physics code such as MC2 and
used as input to a global flux solver such as DIF3D.

This module implements reading and writing of the DLAYXS, consistent with [CCCC-IV]_.
"""
import collections

import numpy as np

from armi import runLog
from armi.nucDirectory import nuclideBases
from armi.nuclearDataIO import cccc, nuclearFileMetadata

ALLOWED_NUCLIDE_CONTRIBUTION_ERROR = 1e-5


class DelayedNeutronData:
    """
    Container of information about delayed neutron precursors.

    This info should be enough to perform point kinetics problems and to compute the delayed neutron
    fraction.

    This object represents data related to either one nuclide (as read from a data library) or an
    average over many nuclides (as computed after a delayed-neutron fraction calculation).

    For a problem with P precursor groups and G energy groups, delayed neutron precursor information
    includes the three attributes of this class listed below.

    Attributes
    ----------
    precursorDecayConstants : array
        This is P-length list of decay constants in (1/s) that characterize the decay rates of the
        delayed neutron precursors. When a precursor decays, it emits a delayed neutron.

    delayEmissionSpectrum : array
        fraction of delayed neutrons emitted into each neutron energy group from each precursor family
        This is a PxG matrix
        The emission spectrum from the first precursor group is delayEmissionSpectrum[0,:].
        Aka delayed-chi

     delayNeutronsPerFission : array
        The multigroup number of delayed neutrons released per decay for each precursor group. Note
        that this is equivalent to the number of delayed neutron precursors produced per fission in
        each family and energy group. Structure is identical to delayEmissionSpectrum. Aka delayed-
        nubar.
    """

    def __init__(self, numEnergyGroups, numPrecursorGroups):
        self.precursorDecayConstants = np.zeros(numPrecursorGroups)
        self.delayEmissionSpectrum = np.zeros((numPrecursorGroups, numEnergyGroups))
        self.delayNeutronsPerFission = np.zeros((numPrecursorGroups, numEnergyGroups))


def compare(lib1, lib2):
    """Compare two XSLibraries, and return True if equal, or False if not."""
    # basically everything is stored in meta-data... so this is a simplified comparison
    return lib1.metadata.compare(lib2.metadata, lib1, lib2)


def readBinary(fileName):
    """Read a binary DLAYXS file into an :py:class:`~armi.nuclearDataIO.dlayxs.Dlayxs` object."""
    return _read(fileName, "rb")


def readAscii(fileName):
    """Read an ASCII DLAYXS file into an :py:class:`~armi.nuclearDataIO.dlayxs.Dlayxs` object."""
    return _read(fileName, "r")


def _read(fileName, fileMode):
    delay = Dlayxs()
    return _readWrite(delay, fileName, fileMode)


def writeBinary(delay, fileName):
    """Write the DLAYXS data from an :py:class:`~armi.nuclearDataIO.dlayxs.Dlayxs` object to a binary file."""
    return _write(delay, fileName, "wb")


def writeAscii(delay, fileName):
    """Write the DLAYXS data from an :py:class:`~armi.nuclearDataIO.dlayxs.Dlayxs` object to an ASCII file."""
    return _write(delay, fileName, "w")


def _write(delay, fileName, fileMode):
    return _readWrite(delay, fileName, fileMode)


def _readWrite(delay, fileName, fileMode):
    with DlayxsIO(fileName, fileMode, delay) as rw:
        rw.readWrite()
    return delay


class Dlayxs(collections.OrderedDict):
    """
    Contains DLAYXS file information according to CCCC specification.

    This object contains nuclide-dependent delayed neutron data. Each nuclide is represented
    with its own ``DelayedNeutronData`` object.

    Keys are nuclideBases objects. It's an ordered dictionary to maintain order of file that was read in.

    Module that use delayed neutron data should expect a ``DelayedNeutronData`` object as input.
    If you want an average over all nuclides, then you need to produce it using the properly-computed
    average contributions of each nuclide.

    Attributes
    ----------
    nuclideFamily : dict
        There are a number of delayed neutron "families", which in
        the ideal case would be numFamilies = numNuclides * numPrecursorGroups.
        Since some nuclides do not have their own data (like Pu242),
        the nuclide shares data with other nuclides. This mapping is done via
        the nuclideFamilies attribute.

    numPrecursorGroups : int
        number of delayed neutron precursor groups, each with independent decay constants and emission spectra

    neutronEnergyUpperBounds : array
        upper bounds in eV

    nuclideContributionFractions : dict
        Fractions of beta due to each nuclide. Needed for making composition-dependent averages of delayed neutron data.
        This is dependent on beta-effective at some reactor state. Must therefore be computed during beta calculation

    See Also
    --------
    armi.physics.safety.perturbationTheory.PerturbationTheoryInterface.calculateBeta : computes nuclide
        contributions
    """

    def __init__(self, *args, **kwargs):
        collections.OrderedDict.__init__(self, *args, **kwargs)
        self.nuclideFamily = {}
        self.numPrecursorGroups = 6
        self.metadata = nuclearFileMetadata.FileMetadata()
        self.neutronEnergyUpperBounds = None
        self.nuclideContributionFractions = {}

    @property
    def G(self):
        """Number of energy groups."""
        return len(self.neutronEnergyUpperBounds)

    def generateAverageDelayedNeutronConstants(self):
        """
        Use externally-computed ``nuclideContributionFractions`` to produce an average
        ``DelayedNeutronData`` object.

        Solves typical averaging equation but weights already sum to 1.0 so we can skip
        normalization at the end.
        """
        avg = DelayedNeutronData(self.G, self.numPrecursorGroups)

        self._checkContributions()
        for nucBase, nucDelayedNeutronConstants in self.items():
            contribution = self.nuclideContributionFractions[nucBase]
            avg.precursorDecayConstants += (
                contribution * nucDelayedNeutronConstants.precursorDecayConstants
            )
            avg.delayEmissionSpectrum += (
                contribution * nucDelayedNeutronConstants.delayEmissionSpectrum
            )
            avg.delayNeutronsPerFission += (
                contribution * nucDelayedNeutronConstants.delayNeutronsPerFission
            )

        return avg

    def _checkContributions(self):
        totalContrib = sum(self.nuclideContributionFractions.values())
        if abs(totalContrib - 1.0) > ALLOWED_NUCLIDE_CONTRIBUTION_ERROR:
            raise RuntimeError(
                "Cannot average delayed neutron fractions unless contributions sum to 1.0. "
                "They sum to {:.4e}".format(totalContrib)
            )
        if len(self.nuclideContributionFractions) != len(self):
            raise RuntimeError(
                "Cannot average delayed neutron fractions with {} nuclides and {} "
                "contribution fractions".format(
                    len(self), len(self.nuclideContributionFractions)
                )
            )


class DlayxsIO(cccc.Stream):
    """Contains DLAYXS read/writers."""

    def __init__(self, fileName, fileMode, dlayxs):
        cccc.Stream.__init__(self, fileName, fileMode)
        self.dlayxs = dlayxs
        self.metadata = dlayxs.metadata

    def readWrite(self):
        r"""Read and write DLAYXS files.

        .. impl:: Tool to read and write DLAYXS files.
            :id: I_ARMI_NUCDATA_DLAYXS
            :implements: R_ARMI_NUCDATA_DLAYXS

            Reading and writing DLAYXS delayed neutron data files is performed
            using the general nuclear data I/O functionalities described in
            :need:`I_ARMI_NUCDATA`. Reading/writing a DLAYXS file is performed
            through the following steps:

            #. Read/write the data ``label`` for identification.

                .. note::

                    MC\ :sup:`2`-3  file does not use the expected number of
                    characters for the ``label``, so its length needs to be
                    stored in the :py:class:`~.cccc.IORecord`.

            #. Read/write file control information, i.e. the 1D record, which includes:

                * Number of energy groups
                * Number of nuclides
                * Number of precursor families

            #. Read/write spectral data, including:

                * Nuclide IDs
                * Decay constants
                * Emission spectra
                * Energy group bounds
                * Number of families to which fission in a given nuclide
                  contributes delayed neutron precursors

            #. Read/write 3D delayed neutron yield matrix on the 3D record,
               indexed by nuclide, precursor family, and outgoing neutron energy
               group.
        """
        runLog.info(
            "{} DLAYXS library {}".format(
                "Reading" if "r" in self._fileMode else "Writing", self
            )
        )
        self._rwFileID()
        numNuclides = self._rwFileControl()
        self._rwSpectra(numNuclides)
        self._rwYield()

        # if the data objects are empty, then we are reading, otherwise the data already exists...
        # If we are reading, then we have to map all the metadata into the DelayedNeutronData structures
        if not np.any(list(self.dlayxs.values())[0].delayEmissionSpectrum):
            for nuc, dlayData in self.dlayxs.items():
                for ii, family in enumerate(self.dlayxs.nuclideFamily[nuc]):
                    dlayData.precursorDecayConstants[ii] = self.metadata[
                        "precursorDecayConstants"
                    ][family - 1]
                    dlayData.delayEmissionSpectrum[ii, :] = self.metadata[
                        "delayEmissionSpectrum"
                    ][:, family - 1]

    def _rwFileID(self):
        with self.createRecord() as fileIdRecord:
            # unfortunately, the MCC3 file doesn't have the "correct" number of characters, so we need to compute it
            # when reading/writing
            label = self.dlayxs.metadata["label"]
            labelLength = len(label) if label is not None else fileIdRecord.numBytes
            self.dlayxs.metadata["label"] = fileIdRecord.rwString(label, labelLength)

    def _rwFileControl(self):
        with self.createRecord() as fileControl:
            self.metadata["numEnergyGroups"] = fileControl.rwInt(
                self.metadata["numEnergyGroups"]
            )
            numNuclides = fileControl.rwInt(len(self.dlayxs))
            self.metadata["numFamilies"] = fileControl.rwInt(
                self.metadata["numFamilies"]
            )
            self.metadata["dummy"] = fileControl.rwInt(self.metadata["dummy"])
        return numNuclides

    def _rwSpectra(self, numNuclides):
        """
        Read or write precursor decay constants and emission spectra, as well as energy group structure for each family.

        nkfam is the number of families to which fission in a given nuclide contributes delayed neutron precursors
        """
        with self.createRecord() as fileData:
            self.metadata["nuclideIDs"] = fileData.rwList(
                self.metadata["nuclideIDs"], "string", numNuclides, 8
            )

            if len(self.dlayxs) == 0:
                # create data structure if reading
                nuclides = [
                    nuclideBases.byMcc3Id[nucName]
                    for nucName in self.metadata["nuclideIDs"]
                ]
                for nuc in nuclides:
                    self.dlayxs[nuc] = DelayedNeutronData(
                        self.metadata["numEnergyGroups"], self.dlayxs.numPrecursorGroups
                    )

            # Read decay constants for each family
            self.metadata["precursorDecayConstants"] = fileData.rwMatrix(
                self.metadata["precursorDecayConstants"], self.metadata["numFamilies"]
            )
            # Read the delayed neutron spectra for each family
            self.metadata["delayEmissionSpectrum"] = fileData.rwMatrix(
                self.metadata["delayEmissionSpectrum"],
                self.metadata["numFamilies"],
                self.metadata["numEnergyGroups"],
            )

            # This reads the maximum E for each energy group in eV as well as the
            # minimum energy bound of the set in eV.
            self.dlayxs.neutronEnergyUpperBounds = fileData.rwMatrix(
                self.dlayxs.neutronEnergyUpperBounds, self.metadata["numEnergyGroups"]
            )
            self.metadata["minEnergy"] = fileData.rwFloat(self.metadata["minEnergy"])
            self.metadata["nkfam"] = fileData.rwList(
                self.metadata["nkfam"], "int", len(self.dlayxs)
            )
            self.metadata["recordsToSkip"] = fileData.rwList(
                self.metadata["recordsToSkip"], "int", len(self.dlayxs)
            )
            if self.metadata["dummy2"] is not None:
                fileData.rwList(
                    self.metadata["dummy2"], "string", len(self.metadata["dummy2"]), 4
                )
            else:
                self.metadata["dummy2"] = fileData.rwList(
                    None, "string", (fileData.numBytes - fileData.byteCount) // 4, 4
                )

    def _rwYield(self):
        """
        Read or write delayed neutron precursor yield data (3D record).

        Also reads the family numbers, which represent the family number of the
        k-th yield vector in delayNeutronsPerFission
        """
        for ii, (nuc, dlayData) in enumerate(self.dlayxs.items()):
            with self.createRecord() as yieldData:
                delayNeutronsPerFission = dlayData.delayNeutronsPerFission
                delayNeutronsPerFission = delayNeutronsPerFission.transpose()
                dlayData.delayNeutronsPerFission = yieldData.rwMatrix(
                    delayNeutronsPerFission,
                    self.metadata["nkfam"][ii],
                    self.metadata["numEnergyGroups"],
                ).transpose()
                self.dlayxs.nuclideFamily[nuc] = yieldData.rwList(
                    self.dlayxs.nuclideFamily.get(nuc, None),
                    "int",
                    self.dlayxs.numPrecursorGroups,
                )
