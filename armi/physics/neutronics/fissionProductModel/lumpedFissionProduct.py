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
The lumped fission product (LFP)  module deals with representing LFPs and loading
them from files.

These are generally managed by the
:py:mod:`~armi.physics.neutronics.fissionProductModel.fissionProductModel.FissionProductModel`


"""
import re

from armi.utils import strings
from armi.nucDirectory import nuclideBases
from armi import runLog
from armi.utils import densityTools

from armi.nucDirectory.elements import LANTHANIDE_ELEMENTS, GASEOUS_ELEMENTS

from .fissionProductModelSettings import CONF_LFP_COMPOSITION_FILE_PATH


class LumpedFissionProduct:
    r"""
    Lumped fission product.

    The yields are in number fraction and they sum to 2.0 in general so a
    fission of an actinide results in one LFP, which represents 2 real FPs.

    This object is a data structure and works a lot like a dictionary in terms
    of accessing and modifying the data.

    The yields are indexed by nuclideBase -- in self.yld the yield fraction is
    indexed by nuclideBases of the individual fission product isotopes

    Examples
    --------
    >>> fpd = FissionProductDefinitionFile(stream)
    >>> lfp = fpd.createSingleLFPFromFile('LFP39')
    >>> lfp[<nuclidebase for EU151>]
    2.9773e-05

    See Also
    --------
    armi.reactor.blocks.Block.getLumpedFissionProductCollection : how you should access these.
    """

    def __init__(self, name=None):
        """
        Make a LFP

        Parameters
        ----------
        name : str, optional
            A name for the LFP. Will be overwritten if you load from file. Provide only
            if you are spinning your own custom LFPs.
        """
        self.name = name
        self.yld = {}
        self.gasRemainingFrac = 1.0

    def duplicate(self):
        """
        Make a copy of this w/o using deepcopy
        """
        new = self.__class__(self.name)
        new.gasRemainingFrac = self.gasRemainingFrac
        for key, val in self.yld.items():
            new.yld[key] = val
        return new

    def __getitem__(self, fissionProduct, default=None):
        r"""
        Return the FP yield of a particular FP

        This allows the LFP to be accessed via indexing, like this: ``lfp[fp]``

        Returns
        -------
        yld : yield of the fission product. Defaults to None.
        """
        yld = self.yld.get(fissionProduct, default)
        if yld and isGas(fissionProduct):
            yld *= self.gasRemainingFrac
        return yld

    def __setitem__(self, key, val):
        if self.gasRemainingFrac != 1.0 and isGas(key):
            raise RuntimeError(
                "Cannot set {0} yield on {1} when gas frac is {2}"
                "".format(key, self, self.gasRemainingFrac)
            )
        self.yld[key] = val

    def __contains__(self, item):
        return item in self.yld

    def __repr__(self):
        return "<Lumped Fission Product {0}>".format(self.name)

    def keys(self):
        return self.yld.keys()

    def values(self):
        return self.yld.values()

    def items(self):
        """
        make sure gas fraction gets applied
        """
        for nuc in self.keys():
            yield nuc, self[nuc]

    def setGasRemovedFrac(self, removedFrac):
        """
        Set the fraction of total fission gas that is removed from this LFP.
        """
        self.gasRemainingFrac = 1.0 - removedFrac

    def getGasRemovedFrac(self):
        return 1.0 - self.gasRemainingFrac

    def getTotalYield(self):
        r"""
        Get the fractional yield of all nuclides in this lumped fission product

        Accounts for any fission gas that may be removed.

        Returns
        -------
        total yield of all fps
        """
        return sum([self[nuc] for nuc in self.yld])

    def getMassFracs(self):
        """
        Return a dictionary of mass fractions indexed by nuclide.

        Returns
        -------
        massFracs : dict
            mass fractions (floats) of LFP masses
        """

        massFracs = {}
        for nuc in self.keys():
            massFracs[nuc] = self.getMassFrac(nuclideBase=nuc)
        return massFracs

    def getNumberFracs(self):
        """
        Return a dictionary of number fractions indexed by nuclide.

        Returns
        -------
        numberFracs : dict
            number fractions (floats) of fission products indexed by nuclide.
        """

        numberFracs = {}
        totalNumber = sum(self.yld.values())
        for nuc, yld in self.yld.items():
            numberFracs[nuc] = yld / totalNumber
        return numberFracs

    def getMassFrac(
        self, nucName=None, nuclideBase=None, useCache=True, storeCache=True
    ):
        """
        Return the mass fraction of the given nuclide.

        Returns
        -------
        nuclide mass fraction (float)
        """
        massFracDenom = self.getMassFracDenom(useCache=useCache, storeCache=storeCache)
        if not nuclideBase:
            nuclideBase = nuclideBases.byName[nucName]
        return self.__getitem__(nuclideBase, default=0) * (
            nuclideBase.weight / massFracDenom
        )

    def getMassFracDenom(self, useCache=True, storeCache=True):
        """
        See Also
        --------
        armi.physics.neutronics.fissionProductModel.lumpedFissionProduct.LumpedFissionProduct.getMassFrac
        """
        if hasattr(self, "massFracDenom") and useCache:
            return self.massFracDenom
        else:
            massFracDenom = 0
            for nuc in self.keys():
                massFracDenom += self[nuc] * nuc.weight
            if storeCache:
                self.massFracDenom = massFracDenom
            return massFracDenom

    def getExpandedMass(self, mass=1.0):
        """
        returns a dictionary of masses indexed by nuclide base objects

        Parameters
        ----------
        mass : float,
            the mass of all the expanded mass of the given LFP.
        """

        massVector = self.getMassFracs()
        massVector.update((nuc, mass * mFrac) for nuc, mFrac in massVector.items())

        return massVector

    def getGasFraction(self):
        r"""
        get the fraction of gas that is from Xe and Kr gas

        Returns
        -------
        gasFrac : float
            Fraction of LFP that is gaseous
        """
        totalGas = 0

        # sum up all of the nuclides that are XE or KR
        for nuc, val in self.items():
            if isGas(nuc):
                totalGas += val

        # normalize the total gas released by the total yield fraction and return
        return totalGas / self.getTotalYield()

    def getLanthanideFraction(self):
        """Return the fraction of fission products that are lanthanides."""

        totalLanthanides = 0

        # sum up all of the nuclides that are XE or KR
        for nuc, val in self.items():
            for element in LANTHANIDE_ELEMENTS:
                if element in nuc.name:
                    totalLanthanides += val

        # normalize the total gas released by the total yield fraction and return
        return totalLanthanides / self.getTotalYield()

    def printDensities(self, lfpDens):
        """Print densities of nuclides given a LFP density."""
        for n in sorted(self.keys()):
            runLog.info("{0:6s} {1:.7E}".format(n.name, lfpDens * self[n]))


class LumpedFissionProductCollection(dict):
    """
    A set of lumped fission products

    Typically there would be one of these on a block or on a global level.
    """

    def __init__(self):
        super(LumpedFissionProductCollection, self).__init__()
        self.collapsible = False

    def duplicate(self):
        new = self.__class__()
        for lfpName, lfp in self.items():
            new[lfpName] = lfp.duplicate()
        return new

    def getLumpedFissionProductNames(self):
        return self.keys()

    def getAllFissionProductNames(self):
        """
        Gets names of all fission products in this collection

        TODO: This can use a set, continually updated from the keys() for each lfp, then converted
        to a list. This will change the order of the fission products, though, so should be done
        with care
        """
        fpNames = []
        for lfp in self.values():
            for fp in lfp.keys():
                if fp not in fpNames:
                    fpNames.append(fp.name)
        return fpNames

    def getAllFissionProductNuclideBases(self):
        """
        Gets names of all fission products in this collection
        """
        clideBases = []
        for _lfpName, lfp in self.items():
            for fp in lfp.keys():
                if fp not in clideBases:
                    clideBases.append(fp)
        return clideBases

    def getNumberDensities(self, objectWithParentDensities=None, densFunc=None):
        """
        Gets all FP number densities in collection

        Parameters
        ----------
        objectWithParentDensities : ArmiObject
            object (probably block) that can be called with getNumberDensity('LFP35'), etc. to get densities of LFPs.
        densFunc : function, optional
            Optional method to extract LFP densities

        Returns
        -------
        fpDensities : dict
            keys are fp names, vals are fission product number density in atoms/bn-cm.
        """
        if not densFunc:
            densFunc = lambda lfpName: objectWithParentDensities.getNumberDensity(
                lfpName
            )
        fpDensities = {}
        for lfpName, lfp in self.items():
            lfpDens = densFunc(lfpName)
            for fp, fpFrac in lfp.items():
                fpDensities[fp.name] = fpDensities.get(fp.name, 0.0) + fpFrac * lfpDens
        return fpDensities

    def getMassFrac(self, oldMassFrac=None):
        """
        returns the mass fraction vector of the collection of lumped fission products
        """
        if not oldMassFrac:
            raise ValueError("You must define a massFrac vector")

        massFrac = {}

        for lfpName, lfp in self.items():
            lfpMFrac = oldMassFrac[lfpName]
            for nuc, mFrac in lfp.getMassFracs().items():
                try:
                    massFrac[nuc] += lfpMFrac * mFrac
                except KeyError:
                    massFrac[nuc] = lfpMFrac * mFrac

        return massFrac

    def setGasRemovedFrac(self, removedFrac):
        """
        Set the fraction of total fission gas that is removed from all LFPs.
        """
        for lfp in self.values():
            lfp.setGasRemovedFrac(removedFrac)

    def getGasRemovedFrac(self):
        """
        Get the fraction of total fission gas that is removed from all LFPs.
        """
        lastVal = -1
        for lfp in self.values():
            myVal = lfp.getGasRemovedFrac()
            if lastVal not in (-1, lastVal):
                raise RuntimeError(
                    "Fission gas release fracs in {0} are decoupled" "".format(self)
                )
            lastVal = myVal
        return lastVal


class SingleLumpedFissionProductCollection(LumpedFissionProductCollection):
    """
    This is a subclass of LumpedFissionProductCollection to be used when you
    want to collapse all the fission products into a single lumped fission product

    There were numerous checks in places to ensure that a collection of
    fission products only had 1 lfp and this object consolidates them.

    Notes
    -----
    armi.physics.neutronics.fissionProductModel.lumpedFissionProduct.FissionProductDefinitionFile.createSingleLFPFromFile
        is a factory for these

    """

    def __init__(self):
        super(SingleLumpedFissionProductCollection, self).__init__()
        self.collapsible = True

    def getFirstLfp(self):
        return list(self.values())[0]

    def getName(self):
        return list(self.keys())[0]

    def updateYieldVector(self, numberDensities=None, massFrac=None, fpFiltered=False):
        """update the yield values on the single lumped fission product"""
        if massFrac is not None:
            numberDensities = densityTools.getNDensFromMasses(1, massFrac)

        if numberDensities is None:
            raise ValueError(
                "massFrac -- {} -- or numberDensities -- {} -- must be populated".format(
                    massFrac, numberDensities
                )
            )
        self._updateYieldVectorFromNumberDensities(
            numberDensities, fpFiltered=fpFiltered
        )

    def _updateYieldVectorFromNumberDensities(self, numberDensities, fpFiltered=False):
        """
        This method updates the yield distribution of the first lfp to reflect
        whatever is on the massFrac vector

        Parameters
        ----------
        numberDensities : dict
            This is a <material>.p.massFrac format mass fraction vector indexed by
            nuclide name

        fpFiltered : bool
            This is a flag to let this method know whether it needs to filter
            the mass fraction vector for fission products

        """
        lfp = self.getFirstLfp()
        lfpNumberFrac = lfp.getNumberFracs()

        if fpFiltered:
            fpNumberDensities = numberDensities
        else:
            fpNumberDensities = {}
            # filter massFracs for only fission products
            lfpNumberDensity = numberDensities.get(self.getName(), 0)
            for nucName in sorted(self.getAllFissionProductNames()):
                nb = nuclideBases.byName[nucName]
                fpNumberDensities[nb] = numberDensities.get(
                    nucName, 0
                ) + lfpNumberDensity * lfpNumberFrac.get(nb, 0)

        totalFPNumberDensity = sum(fpNumberDensities.values())
        if totalFPNumberDensity:
            # check to see that you want to update the yields AND that there is
            # a distribution of fission products -- at BOL this has a zero
            # division bc there are no fission products.
            for nb in lfp.keys():
                lfp[nb] = (
                    fpNumberDensities.get(nb, 0) / totalFPNumberDensity
                ) * 2.0  # part of ARMI task T331
        else:
            runLog.debug(
                "fpMassFrac vector should be populated -- not updating the yield vector"
            )
        # update the weight on the nuclide base object
        # This is a GLOBAL operation, which is a bit problematic if it
        # is being changed and should be upgraded accordingly.
        nb = nuclideBases.byName[lfp.name]
        nb.weight = (
            2
            * sum([yld * nb.weight for nb, yld in lfp.yld.items()])
            / sum([yld for yld in self.getFirstLfp().values()])
        )


class FissionProductDefinitionFile:
    """
    Reads a file that has definitions of one or more LFPs in it to produce LFPs

    The format for this file is effectively input lines from a MC2-2 file::

        13          LFP35 GE73 5  5.9000E-06
        13          LFP35 GE74 5  1.4000E-05
        13          LFP35 GE76 5  1.6000E-04
        13          LFP35 AS75 5  8.9000E-05

    and so on

    Examples
    --------
    >>> fpd = FissionProductDefinitionFile(stream)
    >>> lfps = fpd.createLFPsFromFile()

    The path to this file name is specified by the
    """

    fpPat = re.compile(
        r"13\s+([A-Z]+\d+)\s+(......)\s+(" + strings.SCIENTIFIC_PATTERN + ")"
    )

    def __init__(self, stream):
        self.stream = stream

    def createLFPsFromFile(self):
        """
        Read the file and create LFPs from the contents

        Returns
        -------
        lfps : list
            List of LumpedFissionProducts contained in the file
        """
        lfps = LumpedFissionProductCollection()
        for lfpLines in self._splitIntoIndividualLFPLines():
            lfp = self._readOneLFP(lfpLines)
            lfps[lfp.name] = lfp
        return lfps

    def createSingleLFPFromFile(self, name):
        """
        Read one LFP from the file
        """
        lfpLines = self._splitIntoIndividualLFPLines(name)
        lfp = self._readOneLFP(lfpLines[0])  # only one LFP expected. Use it.
        return lfp

    def createSingleLFPCollectionFromFile(self, name):
        """
        Creates a LFPCollection with only one LFP from the file
        """
        lfps = SingleLumpedFissionProductCollection()
        lfpLines = self._splitIntoIndividualLFPLines(name)
        lfp = self._readOneLFP(lfpLines[0])  # only one LFP expected. Use it.
        lfps[lfp.name] = lfp
        return lfps

    def _splitIntoIndividualLFPLines(self, lfpName=None):
        """
        The lfp file can contain one or more LFPs. This splits them.

        Ignores DUMPs.
        Parameters
        ----------
        lfpName : str, optional
            Restrict to just these names if desired.

        Returns
        -------
        allLFPLines : list of list
            each entry is a list of lines that define one LFP
        """
        lines = self.stream.readlines()

        allLFPLines = []
        thisLFPLines = []
        lastName = None
        for line in lines:
            name = line.split()[1]
            if "DUMP" in name or (lfpName and lfpName not in name):
                continue
            if lastName and name != lastName:
                allLFPLines.append(thisLFPLines)
                thisLFPLines = []
            thisLFPLines.append(line)
            lastName = name

        if thisLFPLines:
            allLFPLines.append(thisLFPLines)

        return allLFPLines

    def _readOneLFP(self, linesOfOneLFP):
        lfp = LumpedFissionProduct()
        totalYield = 0.0
        for line in linesOfOneLFP:
            match = re.search(self.fpPat, line)
            if not match:
                raise ValueError(
                    "Invalid LFP data file {0}. Line is invalid:\n{1}".format(
                        self.fName, line
                    )
                )
            parent = match.group(1)
            nucLibId = match.group(2)
            nuc = nuclideBases.byMccId[nucLibId]
            yld = float(match.group(3))
            lfp.yld[nuc] = yld
            totalYield += yld

        lfp.name = parent  # e.g. LFP38
        runLog.debug(
            "Loaded {0} {1} nuclides for a total yield of {2}"
            "".format(len(lfp.yld), lfp.name, totalYield)
        )

        return lfp


def lumpedFissionProductFactory(cs):
    """Build lumped fission products."""
    if cs["fpModel"] == "MO99":
        runLog.warning(
            "Activating MO99-fission product model. All FPs are treated a MO99!"
        )
        return _buildMo99LumpedFissionProduct()

    lfpPath = cs[CONF_LFP_COMPOSITION_FILE_PATH]
    if not lfpPath:
        return None
    runLog.extra(f"Loading global lumped fission products (LFPs) from {lfpPath}")
    with open(lfpPath) as lfpStream:
        lfpFile = FissionProductDefinitionFile(lfpStream)
        lfps = lfpFile.createLFPsFromFile()
    return lfps


def _buildMo99LumpedFissionProduct():
    """
    Build a dummy MO-99 LFP collection.

    This is a very bad FP approximation from a physics standpoint but can be very useful
    for rapid-running test cases.
    """
    mo99 = nuclideBases.byName["MO99"]
    mo99LFPs = LumpedFissionProductCollection()
    for lfp in nuclideBases.where(
        lambda nb: isinstance(nb, nuclideBases.LumpNuclideBase)
    ):
        # Not all lump nuclide bases defined are fission products, so ensure that only fission products are considered.
        if not "FP" in lfp.name:
            continue
        mo99FP = LumpedFissionProduct(lfp.name)
        mo99FP[mo99] = 2.0
        mo99LFPs[lfp.name] = mo99FP
    return mo99LFPs


def expandFissionProducts(massFrac, lumpedFissionProducts):
    """
    expands lumped fission products in a massFrac vector

    Parameters
    ----------
    massFrac : dict

    lumpedFissionProducts : LumpedFissionProductCollection (acts like a dict)
        result of <fissionProductInterface>.getGlobalLumpedFissionProducts

    Returns
    -------
    newMassFracs : dict
    """
    lfpNbs = []
    elementalNbs = []
    newMassFrac = {}

    for nucName in massFrac.keys():
        nB = nuclideBases.byName[nucName]
        if isinstance(nB, nuclideBases.LumpNuclideBase):
            lfpNbs.append(nB)
        elif isinstance(nB, nuclideBases.NaturalNuclideBase):
            elementalNbs.append(nB)
        else:
            newMassFrac[nucName] = massFrac[nucName]

    for lfp in lfpNbs:
        if massFrac[lfp.name] != 0:
            try:
                lfpFP = lumpedFissionProducts[lfp.name]
            except KeyError:
                errorMessage = ["{}".format(lumpedFissionProducts)]
                errorMessage.append("\ntype {}".format(type(lumpedFissionProducts)))
                errorMessage.append("\nmassFrac dict {}".format(massFrac))
                errorMessage.append("\nLumped Fission Product Name {}".format(lfp.name))
                runLog.debug("".join(errorMessage))

            for nB in lfpFP.keys():
                newMassFrac[nB.name] = massFrac.get(nB.name, 0) + massFrac[
                    lfp.name
                ] * lfpFP.getMassFrac(nuclideBase=nB)

    for element in elementalNbs:
        for nB in element.getNaturalIsotopics():
            newMassFrac[nB.name] = (
                massFrac.get(nB.name, 0)
                + massFrac[element.name] * nB.abundance * nB.weight / element.weight
            )
    return newMassFrac


def collapseFissionProducts(
    massFracs, lumpedFissionProducts, updateLumpedFissionProduct=False
):
    """
    collapses fission products into a single lumped fission product

    Parameters
    ----------
    massFracs : dict

    lumpedFissionProducts - LumpedFissionProductCollection (acts like a dict)
        result of <fissionProductInterface>.getGlobalLumpedFissionProducts

    Returns
    -------
    newMassFracs : dict

    Notes
    -----
    collapsing only works if there is a 'single lumped fission product collection' -- otherwise its confusing to
    determine how much of what isotope goes to which lumped fission products
    """

    assert isinstance(lumpedFissionProducts, SingleLumpedFissionProductCollection)
    lfp = lumpedFissionProducts.getFirstLfp()
    newMassFracs = {}
    lumpedFissionProductsMassFracs = {}

    for nb in lfp.keys():
        lumpedFissionProductsMassFracs[nb.name] = massFracs.get(nb.name, 0)

    newMassFracs[lumpedFissionProducts.getName()] = sum(
        lumpedFissionProductsMassFracs.values()
    )
    for nucName in massFracs.keys():
        if nucName not in lumpedFissionProductsMassFracs.keys():
            newMassFracs[nucName] = massFracs[nucName]

    if updateLumpedFissionProduct:
        lumpedFissionProducts.updateYieldVector(massFrac=lumpedFissionProductsMassFracs)

    return newMassFracs


def isGas(nuc):
    """True if nuclide is considered a gas."""
    for elementName in GASEOUS_ELEMENTS:
        if elementName in nuc.name:
            return True
    return False
