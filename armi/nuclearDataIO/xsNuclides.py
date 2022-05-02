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

r"""
This module contains cross section nuclides, which are a wrapper around the
:py:class:`~armi.nucDirectory.nuclideBases.INuclide` objects. The cross section nuclide objects contain
cross section information from a specific calculation (e.g. neutron, or gamma cross sections).

:py:class:`XSNuclide` objects also contain meta data from the original file, so that another file can be
reconstructed.

.. warning::
    :py:class:`XSNuclide` objects should only be created by reading data into
    :py:class:`~armi.nuclearDataIO.xsLibrary.XSLibrary` objects, and then retrieving them through their label
    index (i.e. "PU39AA").
"""
from armi.nucDirectory import nuclideBases
from armi.nuclearDataIO import xsCollections
from armi.nuclearDataIO import xsLibraries
from armi.nuclearDataIO import nuclearFileMetadata
from armi.utils.customExceptions import warn_when_root


@warn_when_root
def NuclideLabelDoesNotMatchNuclideLabel(nuclide, label, xsID):
    return "The label {} (xsID:{}) for nuclide {}, does not match the nucDirectory label.".format(
        label, xsID, nuclide
    )


class XSNuclide(nuclideBases.NuclideWrapper):
    """
    A nuclide object for a specific library.

    XSNuclide objects can contain GAMISO, ISOTXS, and PMATRX data all on a single instance.
    """

    _ensuredBurnInfo = False

    def __init__(self, xsCollection, xsCollectionKey):
        nuclideBases.NuclideWrapper.__init__(self, xsCollection, xsCollectionKey)
        self.xsId = xsLibraries.getSuffixFromNuclideLabel(xsCollectionKey)
        self.source = 0.0
        # 2D record... nucNames
        # 4D record
        self.isotxsMetadata = nuclearFileMetadata.NuclideMetadata()
        self.gamisoMetadata = nuclearFileMetadata.NuclideMetadata()
        self.pmatrxMetadata = nuclearFileMetadata.NuclideMetadata()
        # 5D and 7D records
        self.micros = xsCollections.XSCollection(parent=self)
        self.gammaXS = xsCollections.XSCollection(parent=self)
        self.neutronHeating = None
        self.neutronDamage = None
        self.gammaHeating = None
        self.isotropicProduction = None
        self.linearAnisotropicProduction = None
        self.nOrderProductionMatrix = {}
        XSNuclide._ensuredBurnInfo = False

    def updateBaseNuclide(self):
        """
        Update which nuclide base this :py:class:`XSNuclide` points to.

        Notes
        -----
        During instantiation, not everything is available, only they user-supplied nuclide label,
        i.e. :py:class:`~armi.nucDirectory.nuclideBases.NuclideWrapper.containerKey`.
        During the read operation,
        """
        if self._base is not None:
            return
        # most nuclides have the correct NuclideBase ID
        nuclideId = self.isotxsMetadata["nuclideId"]
        nuclideBase = nuclideBases.byMccId.get(nuclideId, None)
        if nuclideBase is None or isinstance(
            nuclideBase, nuclideBases.DummyNuclideBase
        ):
            # FP, DUMMY, DUMP
            nuclideBase = nuclideBases.byLabel.get(self.nucLabel, None)
            if nuclideBase is None:
                raise OSError(
                    "Could not determine NuclideBase for label {}".format(self.nucLabel)
                )
        if self.nucLabel != nuclideBase.label:
            NuclideLabelDoesNotMatchNuclideLabel(nuclideBase, self.nucLabel, self.xsId)
            nuclideBases.changeLabel(nuclideBase, self.nucLabel)
        self._base = nuclideBase

    def getMicroXS(self, interaction, group):
        r"""Returns the microscopic xs as the ISOTXS value if it exists or a 0 since it doesn't"""
        if interaction in self.micros.__dict__:
            try:
                return self.micros[interaction][group]
            except:
                raise IndexError(
                    "Group {0} not found in interaction {1} of nuclide {2}".format(
                        group, interaction, self.name
                    )
                )
        else:
            return 0

    def getXS(self, interaction):
        r"""Get the cross section of a particular interaction.

        See Also
        --------
        armi.nucDirectory.homogRegion.getXS
        """
        return self.micros[interaction]

    def buildNormalizedScatterColumns(self, scatterMatrixKey):
        """
        Build normalized columns of a scatter matrix.

        the vectors represent all scattering out of each group.
        The rows of the scatter matrix represent in-scatter and the columns
        represent out-scatter. So this sums up the columns.

        Returns
        -------
        scatterWeights : dict
            keys are fromG indices, values are sparse matrix columns (size: Gx1)
            containing normalized columns of the scatter matrix.
        """
        scatter = self.micros[scatterMatrixKey]
        scatterWeights = {}
        if scatter is None:
            return scatterWeights
        for fromG in range(self.container.numGroups):
            outScatter = scatter[:, fromG]  # fromG column of scatter matrix.
            total = outScatter.sum()
            if total != 0.0:
                normalizedOutScatter = outScatter / total
            else:
                normalizedOutScatter = outScatter
            scatterWeights[fromG] = normalizedOutScatter

        return scatterWeights

    @property
    def trans(self):
        """Get the transmutations for this nuclide.

        Notes
        -----
        This is a property wrapper around the base nuclide's :code:`trans` attribute
        """
        return self._base.trans

    @property
    def decays(self):
        """Get the decays for this nuclide.

        Notes
        -----
        This is a property wrapper around the base nuclide's :code:`decays` attribute
        """
        return self._base.decays

    def merge(self, other):
        """
        Merge the attributes of two XSNuclides.

        Parameters
        ----------
        other : armi.nuclearDataIO.xsNuclides.XSNuclide
            The other nuclide to merge information.

        Notes
        -----
        The merge is really more like "cannibalize" in that the object performing the merge takes on the attributes of
        the :code:`other`. It isn't necessary to create new objects for the newly merged attributes, because the 99%
        usage is only used during runtime, where the second XSNuclide, and it's container (e.g. ISTOXS, GAMISO, etc.)
        are discarded after the merge.
        """
        self.isotxsMetadata = self.isotxsMetadata.merge(
            other.isotxsMetadata, self, other, "ISOTXS", AttributeError
        )
        self.gamisoMetadata = self.gamisoMetadata.merge(
            other.gamisoMetadata, self, other, "GAMISO", AttributeError
        )
        self.pmatrxMetadata = self.pmatrxMetadata.merge(
            other.pmatrxMetadata, self, other, "PMATRX", AttributeError
        )
        self.micros.merge(other.micros)
        self.gammaXS.merge(other.gammaXS)
        self.neutronHeating = _mergeAttributes(self, other, "neutronHeating")
        self.neutronDamage = _mergeAttributes(self, other, "neutronDamage")
        self.gammaHeating = _mergeAttributes(self, other, "gammaHeating")
        self.isotropicProduction = _mergeAttributes(self, other, "isotropicProduction")
        self.linearAnisotropicProduction = _mergeAttributes(
            self, other, "linearAnisotropicProduction"
        )
        # this is lazy, but should work, because the n-order wouldn't be set without the others being set first.
        self.nOrderProductionMatrix = (
            self.nOrderProductionMatrix or other.nOrderProductionMatrix
        )


def _mergeAttributes(this, other, attrName):
    """Function for merging XSNuclide attributes.

    Notes
    -----
    This function checks to see that the attribute has only been assigned for a single instance, and then uses uses
    the one that has been assigned.

    Returns
    -------
    The proper value for the attribute.
    """
    attr1 = getattr(this, attrName)
    attr2 = getattr(other, attrName)
    if attr1 is not None and attr2 is not None:
        raise AttributeError(
            "Cannot merge {} and {}, the attribute `{}` has been assigned on both"
            "instances.".format(this, other, attrName)
        )
    return attr1 if attr1 is not None else attr2


def plotScatterMatrix(scatterMatrix, scatterTypeLabel="", fName=None):
    r"""plots a matrix to show scattering."""
    from matplotlib import pyplot

    pyplot.imshow(scatterMatrix.todense(), interpolation="nearest")
    pyplot.grid(color="0.70")
    pyplot.xlabel("From group")
    pyplot.ylabel("To group")
    pyplot.title("{0} scattering XS".format(scatterTypeLabel))
    pyplot.colorbar()
    if fName:
        pyplot.savefig(fName)
    else:
        pyplot.show()


def plotCompareScatterMatrix(scatterMatrix1, scatterMatrix2, fName=None):
    """Compares scatter matrices graphically between libraries."""
    from matplotlib import pyplot

    diff = scatterMatrix1 - scatterMatrix2

    pyplot.imshow(diff.todense(), interpolation="nearest")
    pyplot.grid(color="0.70")
    pyplot.xlabel("From group")
    pyplot.ylabel("To group")
    pyplot.title("scattering XS difference ", fontsize=6)
    pyplot.colorbar()
    if fName:
        pyplot.savefig(fName)
    else:
        pyplot.show()
