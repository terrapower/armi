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

The CrossSectionTable is useful for performing isotopic depletion analysis by storing
one-group cross sections of interest to such an analysis. This used to live alongside
the isotopicDepletionInterface, but that proved to be an unpleasant coupling between the
ARMI composite model and the physics code contained therein. Separating it out at least
means that the composite model doesn't need to import the isotopicDepletionInterface to
function.
"""
import collections
from typing import List

import numpy

from armi.nucDirectory import nucDir


class CrossSectionTable(collections.OrderedDict):
    """
    This is a set of one group cross sections for use with isotopicDepletion analysis.

    Really it's a reaction rate table.

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
        Add one group cross secitons to the table

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
        xsData = {
            rateType: xs
            for rateType, xs in zip(self.rateTypes, [nG, nF, n2n, nA, nP, n3n])
        }
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

        oneGroupXS = numpy.asarray(mgCrossSections).dot(mgFlux) / totalFlux

        oneGroupXSbyName = {xsType: xs for xsType, xs in zip(xsTypes, oneGroupXS)}
        oneGroupXSbyName["n3n"] = 0.0

        self.add(nucName, **oneGroupXSbyName)

    def hasValues(self):
        """
        determines if there are non-zero values in this cross section table
        """
        for nuclideCrossSectionSet in self.values():
            if any(nuclideCrossSectionSet.values()):
                return True
        return False

    def getXsecTable(
        self,
        headerFormat="$ xsecs for {}",
        tableFormat="\n{{mcnpId}} {nG:.5e} {nF:.5e} {n2n:.5e} {n3n:.5e} {nA:.5e} {nP:.5e}",
    ):
        """
        make a cross section table for external depletion physics code input decks

        Parameters
        ----------
        headerFormat: string (optional)
            this is the format in which the elements of the header with be returned
            -- i.e. if you use a .format() call with  the case name you'll return a
            formatted list of string elements

        tableFormat: string (optional)
            this is the format in which the elements of the table with be returned
            -- i.e. if you use a .format() call with mcnpId, nG, nF, n2n, n3n, nA,
            and nP you'll get the format you want. If you use a .format() call with  the case name you'll return a
            formatted list of string elements

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
    """

    if nuclides is None:
        nuclides = obj.getNuclides()

    rxRates = {
        nucName: {rxName: 0 for rxName in CrossSectionTable.rateTypes}
        for nucName in nuclides
    }

    for armiObject in obj.getChildren():
        for nucName in nuclides:
            rxnRates = armiObject.getReactionRates(nucName, nDensity=1.0)
            for rxName, rxRate in rxnRates.items():
                rxRates[nucName][rxName] += rxRate

    crossSectionTable = CrossSectionTable()
    crossSectionTable.setName(obj.getName())

    totalFlux = sum(obj.getIntegratedMgFlux())
    if totalFlux:
        for nucName, nucRxRates in rxRates.items():
            xSecs = {
                rxName: rxRate / totalFlux for rxName, rxRate in nucRxRates.items()
            }
            crossSectionTable.add(nucName, **xSecs)

    return crossSectionTable
