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
Module containing the CrossSectionTable class.

The CrossSectionTable is useful for performing isotopic depletion analysis by storing one-group
cross sections of interest to such an analysis. This used to live alongside the
isotopicDepletionInterface, but that proved to be an unpleasant coupling between the ARMI composite
model and the physics code contained therein. Separating it out at least means that the composite
model doesn't need to import the isotopicDepletionInterface to function.
"""

import collections
from typing import List

import numpy as np

from armi.nucDirectory import nucDir


class CrossSectionTable(collections.OrderedDict):
    """
    This is a set of one group cross sections for use with isotopicDepletion analysis.

    It can also double as a reaction rate table.

    XStable is indexed by nucNames
    (nG), (nF), (n2n), (nA), (nP) and (n3n) are expected
    the cross sections are returned in barns
    """

    rateTypes = ("nG", "nF", "n2n", "nA", "nP", "n3n")

    def __init__(self, *args, **kwargs):
        collections.OrderedDict.__init__(self, *args, **kwargs)
        self._name = None

    def setName(self, name):
        self._name = name

    def getName(self):
        return self._name

    def add(self, nucName, nG=0.0, nF=0.0, n2n=0.0, nA=0.0, nP=0.0, n3n=0.0):
        """
        Add one group cross sections to the table.

        Parameters
        ----------
        nucName - str
            nuclide name -- e.g. 'U235'
        nG - float
            (n,gamma) cross section in barns
        nF - float
            (n,fission) cross section in barns
        n2n - float
            (n,2n) cross section in barns
        nA - float
            (n,alpha) cross section in barns
        nP - float
            (n,proton) cross section in barns
        n3n - float
            (n,3n) cross section in barns
        """
        xsData = {rateType: xs for rateType, xs in zip(self.rateTypes, [nG, nF, n2n, nA, nP, n3n])}
        nb = nucDir.nuclideBases.byName[nucName]
        mcnpNucName = int(nb.getMcnpId())
        self[mcnpNucName] = xsData

    def addMultiGroupXS(self, nucName, microMultiGroupXS, mgFlux, totalFlux=None):
        """
        Perform group collapse to one group cross sections and add to table.

        Parameters
        ----------
        nucName - str
            nuclide name -- e.g. 'U235'
        microMultiGroupXS - XSCollection
            micro cross sections, typically a XSCollection from an ISOTXS
        mgFlux - list like
            The flux in each energy group
        totalFlux - float
            The total flux. Optional argument for increased speed if already available.
        """
        totalFlux = totalFlux if totalFlux is not None else sum(mgFlux)
        xsTypes = ("nG", "nF", "n2n", "nA", "nP")
        mgCrossSections = (
            microMultiGroupXS.nGamma,
            microMultiGroupXS.fission,
            microMultiGroupXS.n2n,
            microMultiGroupXS.nalph,
            microMultiGroupXS.np,
        )

        oneGroupXS = np.asarray(mgCrossSections).dot(mgFlux) / totalFlux

        oneGroupXSbyName = {xsType: xs for xsType, xs in zip(xsTypes, oneGroupXS)}
        oneGroupXSbyName["n3n"] = 0.0

        self.add(nucName, **oneGroupXSbyName)

    def hasValues(self):
        """Determines if there are non-zero values in this cross section table."""
        return any(any(nuclideCrossSectionSet.values()) for nuclideCrossSectionSet in self.values())

    def getXsecTable(
        self,
        headerFormat="$ xsecs for {}",
        tableFormat="\n{{mcnpId}} {nG:.5e} {nF:.5e} {n2n:.5e} {n3n:.5e} {nA:.5e} {nP:.5e}",
    ):
        """
        Make a cross section table for external depletion physics code input decks.

        .. impl:: Generate a formatted cross section table.
            :id: I_ARMI_DEPL_TABLES1
            :implements: R_ARMI_DEPL_TABLES

            Loops over the reaction rates stored as ``self`` to produce a string with the cross
            sections for each nuclide in the block. Cross sections may be populated by
            :py:meth:`~armi.physics.neutronics.isotopicDepletion.crossSectionTable.makeReactionRateTable`

            The string will have a header with the table's name formatted according to
            ``headerFormat`` followed by rows for each unique nuclide/reaction combination, where
            each line is formatted according to ``tableFormat``.

        Parameters
        ----------
        headerFormat: string (optional)
            This is the format in which the elements of the header with be returned -- i.e. if you
            use a .format() call with the case name you'll return a formatted list of strings.

        tableFormat: string (optional)
            This is the format in which the elements of the table with be returned -- i.e. if you
            use a .format() call with mcnpId, nG, nF, n2n, n3n, nA, and nP you'll get the format you
            want. If you use a .format() call with  the case name you'll return a formatted list of
            string elements

        Results
        -------
        output: list
            a list of string elements that together make a xsec card
        """
        output = [headerFormat.format(self.getName())]
        for mcnpNucName in sorted(self.keys()):
            rxRates = self[mcnpNucName]
            dataToWrite = {rateType: rxRates[rateType] for rateType in self.rateTypes}
            if any(dataToWrite[rateType] for rateType in self.rateTypes):
                dataToWrite["mcnpId"] = mcnpNucName
                output.append(tableFormat.format(**dataToWrite))
        return output


def makeReactionRateTable(obj, nuclides: List = None):
    """
    Generate a reaction rate table for given nuclides.

    Often useful in support of depletion.

    .. impl:: Generate a reaction rate table with entries for (nG), (nF), (n2n), (nA), and (nP)
        reactions.
        :id: I_ARMI_DEPL_TABLES0
        :implements: R_ARMI_DEPL_TABLES

        For a given composite object ``obj`` and a list of nuclides ``nuclides`` in that object,
        call ``obj.getReactionRates()`` for each nuclide with a ``nDensity`` parameter of 1.0. If
        ``nuclides`` is not specified, use a list of all nuclides in ``obj``. This will reach
        upwards through the parents of ``obj`` to the associated
        :py:class:`~armi.reactor.reactors.Core` object and pull the ISOTXS library that is stored
        there. If ``obj`` does not belong to a ``Core``, a warning is printed.

        For each child of ``obj``, use the ISOTXS library and the cross-section ID for the
        associated block to produce a reaction rate dictionary in units of inverse seconds for the
        nuclide specified in the original call to ``obj.getReactionRates()``. Because ``nDensity``
        was originally specified as 1.0, this dictionary actually represents the reaction rates per
        unit volume. If the nuclide is not in the ISOTXS library, a warning is printed.

        Combine the reaction rates for all nuclides into a combined dictionary by summing together
        reaction rates of the same type on the same isotope from each of the children of ``obj``.

        If ``obj`` has a non-zero multi-group flux, sum the group-wise flux into the total flux and
        normalize the reaction rates by the total flux, producing a one-group macroscopic cross
        section for each reaction type on each nuclide. Store these values in a
        :py:class:`~armi.physics.neutronics.isotopicDepletion.crossSectionTable.CrossSectionTable`.

    Parameters
    ----------
    nuclides : list, optional
        list of nuclide names for which to generate the cross-section table.
        If absent, use all nuclides obtained by self.getNuclides().

    Notes
    -----
    This also used to do some caching on the block level but that has been removed
    and the calls to this may therefore need to be re-optimized.

    See Also
    --------
    armi.physics.neutronics.isotopicDepletion.isotopicDepletionInterface.CrossSectionTable
    armi.reactor.composites.Composite.getReactionRates
    """
    if nuclides is None:
        nuclides = obj.getNuclides()

    rxRates = {nucName: {rxName: 0 for rxName in CrossSectionTable.rateTypes} for nucName in nuclides}

    for armiObject in obj:
        for nucName in nuclides:
            rxnRates = armiObject.getReactionRates(nucName, nDensity=1.0)
            for rxName, rxRate in rxnRates.items():
                rxRates[nucName][rxName] += rxRate

    crossSectionTable = CrossSectionTable()
    crossSectionTable.setName(obj.getName())

    totalFlux = sum(obj.getIntegratedMgFlux())
    if totalFlux:
        for nucName, nucRxRates in rxRates.items():
            xSecs = {rxName: rxRate / totalFlux for rxName, rxRate in nucRxRates.items()}
            crossSectionTable.add(nucName, **xSecs)

    return crossSectionTable
