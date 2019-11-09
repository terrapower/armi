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
Cross section group manager handles burnup-dependent properties of microscopic cross sections.

Blocks are specified to be in a certain *cross section type* and *burnup group*. Together,
these form the *cross section group*. By advancing blocks by their burnup into
different groups, we capture some of the physical effects related to depletion.

XS types are typically single capital letters like A
BU groups are also capital letters.
A XS group of AB is in XS type ``A`` and burnup group ``B``.

This module groups the blocks according to their XS groups and can determine
which block is to be deemed **representative** of an entire set of blocks in a particular xs group.
Then the representative block is sent to a lattice physics kernel for actual physics
calculations.

Generally, the cross section manager is a attribute of the lattice physics code interface (e.g.
the :py:mod:`~terrapower.physics.neutronics.mc2.mc2Interface`.

Examples
--------

    csm = CrossSectionGroupManager()
    csm._setBuGroupBounds(cs['buGroups'])
    csm._addXsGroupsFromBlocks(blockList)
    csm.createRepresentativeBlocks()
    representativeBlockList = csm.representativeBlocks.values()
    blockThatRepresentsBA = csm.representativeBlocks['BA']


The class diagram is provided in `xsgm-class-diagram`_

.. _xsgm-class-diagram:

.. pyreverse:: armi.physics.neutronics.crossSectionGroupManager
    :align: center
    :alt: XSGM class diagram
    :width: 90%

    Class inheritance diagram for :py:mod:`crossSectionGroupManager`.
"""
import copy
import os
import shutil
import string
import collections

import numpy

import armi
from armi import runLog
from armi import interfaces
from armi.reactor.flags import Flags
from armi.reactor.components import basicShapes
from armi.utils.units import TRACE_NUMBER_DENSITY
from armi.physics.neutronics.const import CONF_CROSS_SECTION

ORDER = interfaces.STACK_ORDER.BEFORE + interfaces.STACK_ORDER.FUEL_MANAGEMENT


def describeInterfaces(cs):
    """Function for exposing interface(s) to other code"""

    if "MCNP" not in cs["neutronicsKernel"]:  # MCNP does not use CSGM
        return (CrossSectionGroupManager, {})

    return None


_ALLOWABLE_XS_TYPE_LIST = list(string.ascii_uppercase)


def getXSTypeNumberFromLabel(xsTypeLabel):
    """
    Convert a XSID label (e.g. 'AA') to an integer.

    Useful for visualizing XS type in XTVIEW.

    2-digit labels are supported when there is only one burnup group.
    """
    return int("".join(["{:02d}".format(ord(si)) for si in xsTypeLabel]))


def getXSTypeLabelFromNumber(xsTypeNumber):
    """
    Convert a XSID label (e.g. 65) to an XS label (e.g. 'A').

    Useful for visualizing XS type in XTVIEW.

    2-digit labels are supported when there is only one burnup group.
    """
    try:
        if xsTypeNumber > ord("Z"):
            # two digit. Parse
            return chr(int(str(xsTypeNumber)[:2])) + chr(int(str(xsTypeNumber)[2:]))
        else:
            return chr(xsTypeNumber)
    except ValueError:
        runLog.error("Error converting {} to label.".format(xsTypeNumber))
        raise


class BlockCollection(list):
    """
    Controls which blocks are representative of a particular cross section type/BU group

    This is a list with special methods.
    """

    def __init__(self, allNuclidesInProblem, validBlockTypes=None):
        list.__init__(self)
        self.allNuclidesInProblem = allNuclidesInProblem
        self.weightingParam = None

        # allowed to be independent of fuel component temperatures b/c Doppler
        self.avgNucTemperatures = {}
        self._validRepresentativeBlockTypes = None
        if validBlockTypes:
            self._validRepresentativeBlockTypes = []
            for t in validBlockTypes:
                self._validRepresentativeBlockTypes.append(Flags.fromString(t))

    def __repr__(self):
        return "<{} with {} blocks>".format(self.__class__.__name__, len(self))

    def _getNewBlock(self):
        """
        Create a new block instance.

        Notes
        -----
        Should only be used by average because of name (which may not matter)
        """
        newBlock = copy.deepcopy(self.getCandidateBlocks()[0])
        newBlock.name = "AVG_" + newBlock.getMicroSuffix()
        return newBlock

    def createRepresentativeBlock(self):
        """Generate a block that best represents all blocks in group."""
        self._checkValidWeightingFactors()
        representativeBlock = self._makeRepresentativeBlock()
        return representativeBlock

    def _makeRepresentativeBlock(self):
        raise NotImplementedError

    def _checkValidWeightingFactors(self):
        """
        Verify the validity of the weighting parameter.

        .. warning:: Don't mix unweighted blocks (flux=0) w/ weighted ones
        """
        if self.weightingParam is None:
            weights = [0.0] * len(self.getCandidateBlocks())
        else:
            weights = [
                block.p[self.weightingParam] for block in self.getCandidateBlocks()
            ]
        anyNonZeros = any(weights)
        if anyNonZeros and not all(weights):
            # we have at least one non-zero entry and at least one zero. This is bad.
            # find the non-zero ones for debugging
            zeros = [block for block in self if not block.p[self.weightingParam]]
            runLog.error(
                "Blocks with zero `{0}` include: {1}".format(self.weightingParam, zeros)
            )
            raise ValueError(
                "{0} has a mixture of zero and non-zero weighting factors (`{1}`)\n"
                "See stdout for details".format(self, self.weightingParam)
            )

    def calcAvgNuclideTemperatures(self):
        r"""
        Calculate the average nuclide temperatures in this collection based on the blocks in the collection.

        If a nuclide is in multiple components, that's taken into consideration.

        .. math::
             T = \frac{\sum{n_i v_i T_i}}{\sum{n_i v_i}}

        where :math:`n_i` is a number density, :math:`v_i` is a volume, and :math:`T_i` is a temperature.

        See Also
        --------
        terrapower.physics.neutronics.mc2.mc2Writers.Mc2Writer._getAllNuclideDensities : uses these values
        """
        self.avgNucTemperatures = {}
        nvt, nv = self._getNucTempHelper()
        for i, nuclide in enumerate(self.allNuclidesInProblem):
            nvtCurrent = nvt[i]
            nvCurrent = nv[i]
            avgTemp = 0.0 if nvCurrent == 0.0 else nvtCurrent / nvCurrent
            self.avgNucTemperatures[nuclide] = avgTemp

    def _getNucTempHelper(self):
        """
        Get temperature averaging numerator and denominator for block collection.

        This is abstract; you must override it.
        """
        raise NotImplementedError

    def getWeight(self, block):
        """
        Get value of weighting function for this block
        """
        vol = block.getVolume() or 1.0
        if not self.weightingParam:
            weight = 1.0
        else:
            # don't return 0
            weight = block.p[self.weightingParam] or 1.0

        return weight * vol

    def getCandidateBlocks(self):
        """
        Get blocks in this collection that are the valid representative type.

        Often, peripheral non-fissile blocks (reflectors, control, shields) need cross sections but
        cannot produce them alone. You can approximate their cross sections by placing them in certain cross
        section groups. However, we do not want these blocks to be included in the spectrum
        calculations that produce cross sections. Therefore the subset of valid representative
        blocks are used to compute compositions, temperatures, etc.

        .. tip:: The proper way to treat non-fuel blocks is to apply a leakage spectrum from fuel onto them.
        """
        return [b for b in self if b.hasFlags(self._validRepresentativeBlockTypes)]


class MedianBlockCollection(BlockCollection):
    """
    Returns the median burnup block. This is a simple and often accurate approximation.
    """

    def _makeRepresentativeBlock(self):
        """Get the median burnup block."""
        medianBlock = self._getMedianBlock()
        # copy so we can adjust LFPs w/o changing the global ones
        newBlock = copy.deepcopy(medianBlock)
        lfpCollection = medianBlock.getLumpedFissionProductCollection()
        if lfpCollection:
            lfpCollection = lfpCollection.duplicate()
            lfpCollection.setGasRemovedFrac(newBlock.p.gasReleaseFraction)
            newBlock.setLumpedFissionProducts(lfpCollection)
        else:
            runLog.warning("Representative block {0} has no LFPs".format(medianBlock))
        self.calcAvgNuclideTemperatures()
        return newBlock

    def _getNucTempHelper(self):
        """
        Return the Median block nuclide temperature terms.

        In this case, there's only one block to average, so return its averaging terms.

        See Also
        --------
        calcAvgNuclideTemperatures
        """
        medianBlock = self._getMedianBlock()
        return getBlockNuclideTemperatureAvgTerms(
            medianBlock, self.allNuclidesInProblem
        )

    def _getMedianBlock(self):
        """
        Return the median burnup Block.

        Build list of items for each block when sorted gives desired order

        Last item in each tuple is always the block itself (for easy retrieval).

        For instance, if you want the median burnup, this list would contain
        tuples of (burnup, blockName, block). Blockname is included so
        the order is consistent between runs when burnups are equal (e.g. 0).
        """
        info = []
        for b in self.getCandidateBlocks():
            info.append((b.p.percentBu * self.getWeight(b), b.getName(), b))
        info.sort()
        medianBlockData = info[len(info) // 2]
        return medianBlockData[-1]


class AverageBlockCollection(BlockCollection):
    """
    Block collection that builds a new block based on others in collection

    Averages number densities, fission product yields, and fission gas
    removal fractions.
    """

    def _makeRepresentativeBlock(self):
        """
        Generate a block that best represents all blocks in group.
        """
        newBlock = self._getNewBlock()
        lfpCollection = self._getAverageFuelLFP()
        newBlock.setLumpedFissionProducts(lfpCollection)
        newBlock.setNumberDensities(self._getAverageNumberDensities())
        self.calcAvgNuclideTemperatures()
        return newBlock

    def _getAverageNumberDensities(self):
        """
        Get weighted average number densities of the collection.

        Returns
        -------
        numberDensities : dict
            nucName, ndens data (atoms/bn-cm)
        """
        nuclides = self.allNuclidesInProblem
        blocks = self.getCandidateBlocks()
        weights = numpy.array([self.getWeight(b) for b in blocks])
        weights /= weights.sum()  # normalize by total weight
        ndens = weights.dot([b.getNuclideNumberDensities(nuclides) for b in blocks])
        return dict(zip(nuclides, ndens))

    def _getAverageFissionGasRemoved(self):
        """
        Get weighted average fission gas release fraction.

        Notes
        -----
        - Will be applied to LFP composition.
        """
        totalWeight = 0.0
        fgRelease = 0.0
        for b in self.getCandidateBlocks():
            weight = self.getWeight(b)
            totalWeight += weight
            fgRelease += b.p.gasReleaseFraction * weight
        return fgRelease / totalWeight

    def _getAverageFuelLFP(self):
        """Compute the average lumped fission products."""
        # TODO: make do actual average of LFPs
        b = self.getCandidateBlocks()[0]
        lfpCollection = b.getLumpedFissionProductCollection()
        if lfpCollection:
            lfpCollectionCopy = lfpCollection.duplicate()
            fgRemoved = self._getAverageFissionGasRemoved()
            lfpCollectionCopy.setGasRemovedFrac(fgRemoved)
        else:
            lfpCollectionCopy = lfpCollection

        return lfpCollectionCopy

    def _getNucTempHelper(self):
        """All candidate blocks are used in the average."""
        nvt = numpy.zeros(len(self.allNuclidesInProblem))
        nv = numpy.zeros(len(self.allNuclidesInProblem))
        for block in self.getCandidateBlocks():
            wt = self.getWeight(block)
            nvtBlock, nvBlock = getBlockNuclideTemperatureAvgTerms(
                block, self.allNuclidesInProblem
            )
            nvt += nvtBlock * wt
            nv += nvBlock * wt
        return nvt, nv


def getBlockNuclideTemperatureAvgTerms(block, allNucNames):
    """
    Compute terms (numerator, denominator) of average for this block.

    This volume-weights the densities by component volume fraction.

    It's important to count zero-density nuclides (i.e. ones like AM242 that are expected to build up)
    as trace values at the proper component temperatures.
    """

    def getNumberDensityWithTrace(component, nucName):
        # needed to make sure temperature of 0-density nuclides in fuel get fuel temperature
        try:
            dens = component.p.numberDensities[nucName] or TRACE_NUMBER_DENSITY
        except KeyError:
            dens = 0.0
        return dens

    vol = block.getVolume()
    components, volFracs = zip(*block.getVolumeFractions())
    # D = CxN matrix of number densities
    ndens = numpy.array(
        [
            [getNumberDensityWithTrace(c, nucName) for nucName in allNucNames]
            for c in components
        ]
    )
    temperatures = numpy.array(
        [c.temperatureInC for c in components]
    )  # C-length temperature array
    nvBlock = (
        ndens.T * numpy.array(volFracs) * vol
    )  # multiply each component's values by volume frac, now NxC
    nvt = sum((nvBlock * temperatures).T)  # N-length array summing over components.
    nv = sum(nvBlock.T)  # N-length array
    return nvt, nv


class SlabComponentsAverageBlockCollection(BlockCollection):
    """
    Creates a representative 1D slab block.

    Notes
    -----
    - Ignores lumped fission products since there is no foreseeable need for burn calculations in 1D slab geometry
      since it is used for low power neutronic validation.
    - Checks for consistent component dimensions for all blocks in a group and then creates a new block.
    - Iterates through components of all blocks and calculates component average number densities. This calculation
      takes the first component of each block, averages the number densities, and applies this to the number density
      to the representative block.
    
    """

    def _makeRepresentativeBlock(self):
        """Build a representative fuel block based on component number densities."""
        repBlock = self._getNewBlock()
        bWeights = [self.getWeight(b) for b in self.getCandidateBlocks()]
        componentsInOrder = self._orderComponentsInGroup(repBlock)

        for c, allSimilarComponents in zip(repBlock, componentsInOrder):
            allNucsNames, densities = self._getAverageComponantNucs(
                allSimilarComponents, bWeights
            )
            for nuc, aDensity in zip(allNucsNames, densities):
                c.setNumberDensity(nuc, aDensity)
        newBlock = self._removeLatticeComponents(repBlock)
        return newBlock

    def _getNucTempHelper(self):
        raise NotImplementedError

    @staticmethod
    def _getAllNucs(components):
        """Iterate through components and get all unique nuclides."""
        nucs = set()
        for c in components:
            nucs = nucs.union(c.getNuclides())
        return sorted(list(nucs))

    @staticmethod
    def _checkComponentConsisteny(b, repBlock, components=None):
        """
        Verify that all components being homogenized are rectangular and have consistent dimensions.

        Raises
        ------
        ValueError
            When the components in a candidate block do not align with
            the components in the representative block. This check includes component area, component multiplicity,
            and nuclide composition.

        TypeError
            When the shape of the component is not a rectangle.

        .. warning:: This only checks ``consistentNucs`` for ones that are important in ZPPR and BFS.
        """
        comps = b if components is None else components

        consistentNucs = ["PU239", "U238", "U235", "U234", "FE56", "NA23", "O16"]
        for c, repC in zip(comps, repBlock):
            if not isinstance(c, basicShapes.Rectangle):
                raise TypeError(
                    "The shape of component {} in block {} is invalid and must be a rectangle.".format(
                        c, b
                    )
                )
            compString = "Component {} in block {} and component {} in block {}".format(
                repC, repBlock, c, b
            )
            if c.getArea() != repC.getArea():
                raise ValueError(
                    "{} are in the same location, but have differing thicknesses. Check that the "
                    "thicknesses are defined correctly. Note: This could also be due to "
                    "thermal expansion".format(compString)
                )

            theseNucs = set(c.getNuclides())
            thoseNucs = set(repC.getNuclides())
            for nuc in consistentNucs:
                if (nuc in theseNucs) != (nuc in thoseNucs):
                    raise ValueError(
                        "{} are in the same location, but are not consistent in nuclide {}. \n{} \n{}"
                        "".format(compString, nuc, theseNucs, thoseNucs)
                    )
            if c.p.mult != repC.p.mult:
                raise ValueError(
                    "{} must have the same multiplicity to homogenize".format(
                        compString
                    )
                )

    @staticmethod
    def _reverseComponentOrder(block):
        """Move the lattice component to the end of the components list."""
        latticeComponents = [c for c in block if c.isLatticeComponent()]
        components = [c for c in reversed(block) if not c.isLatticeComponent()]
        if len(latticeComponents) > 1:
            raise ValueError(
                "Block {} contains multiple `lattice` components: {}. Remove the additional "
                "lattice components in the reactor blueprints.".format(
                    block, latticeComponents
                )
            )
        components.append(latticeComponents[0])
        return components

    @staticmethod
    def _removeLatticeComponents(repBlock):
        """
        Remove the lattice component from the representative block.

        Notes
        -----
        - This component does not serve any purpose for XS generation as it contains void material with zero area.
        - Removing this component does not modify the blocks within the reactor.
        """
        for c in repBlock.getComponents():
            if c.isLatticeComponent():
                repBlock.remove(c)
        return repBlock

    def _getAverageComponantNucs(self, components, bWeights):
        """Compute average nuclide densities by block weights and component area fractions."""
        allNucNames = self._getAllNucs(components)
        densities = numpy.zeros(len(allNucNames))
        totalWeight = 0.0
        for c, bWeight in zip(components, bWeights):
            weight = bWeight * c.getArea()
            totalWeight += weight
            densities += weight * numpy.array(
                [c.getNumberDensity(nucName) for nucName in allNucNames]
            )
        return allNucNames, densities / totalWeight

    def _orderComponentsInGroup(self, repBlock):
        """Order the components based on dimension and material type within the representative block."""
        orderedComponents = [[] for _ in repBlock]
        for b in self.getCandidateBlocks():
            if len(b) != len(repBlock):
                raise ValueError(
                    "Blocks {} and {} have differing number of components and cannot be homogenized".format(
                        b, repBlock
                    )
                )
            try:
                self._checkComponentConsisteny(b, repBlock)
                componentsToAdd = [c for c in b]
            except ValueError:
                runLog.extra(
                    "Checking if components in block {} are in the reverse order of the components in the "
                    "representative block {}".format(b, repBlock)
                )
                reversedComponentOrder = self._reverseComponentOrder(b)
                self._checkComponentConsisteny(
                    b, repBlock, components=reversedComponentOrder
                )
                componentsToAdd = [c for c in reversedComponentOrder]
            for i, c in enumerate(componentsToAdd):
                orderedComponents[i].append(c)  # group similar components
        return orderedComponents


class FluxWeightedAverageBlockCollection(AverageBlockCollection):
    """
    Flux-weighted AverageBlockCollection
    """

    def __init__(self, *args, **kwargs):
        AverageBlockCollection.__init__(self, *args, **kwargs)
        self.weightingParam = "flux"


class CrossSectionGroupManager(interfaces.Interface):
    """
    Looks at the reactor and updates burnup group information based on current burnup.

    Contains a :py:class:`BlockCollection` for each cross section group.

    Notes
    -----
    The representative blocks created in the CrossSectionGroupManager are ordered
    alphabetically by key.
    """

    name = "xsGroups"

    _REPR_GROUP = "represented"
    _NON_REPR_GROUP = "non-represented"
    _PREGEN_GROUP = "pre-generated"

    def __init__(self, r, cs):
        interfaces.Interface.__init__(self, r, cs)
        self._upperBuGroupBounds = None
        self.representativeBlocks = collections.OrderedDict()
        self.avgNucTemperatures = {}
        self._buGroupUpdatesEnabled = True
        self._setBuGroupBounds(self.cs["buGroups"])
        self._unrepresentedXSIDs = []

    def interactBOL(self):
        # now that all cs settings are loaded, apply defaults to compound XS settings
        self.cs[CONF_CROSS_SECTION].setDefaults(self.cs)

    def interactBOC(self, cycle=None):
        """
        Update representative blocks and block burnup groups.

        Notes
        -----
        The block list each each block collection cannot be emptied since it is used to derive nuclide temperatures.
        """
        self.createRepresentativeBlocks()

    def interactEOC(self, cycle=None):
        """
        EOC interaction.

        Clear out big dictionary of all blocks to avoid memory issues and out-of-date representers.
        """
        self.clearRepresentativeBlocks()

    def interactCoupled(self, iteration):
        """Update XS groups on each physics coupling iteration to get latest temperatures."""
        self.interactBOC(cycle=None)

    def clearRepresentativeBlocks(self):
        """Clear the representative blocks."""
        runLog.extra("Clearing representative blocks")
        self.representativeBlocks = collections.OrderedDict()
        self.avgNucTemperatures = {}

    def _setBuGroupBounds(self, upperBuGroupBounds):
        """
        Set the burnup group structure

        Parameters
        ---------
        upperBuGroupBounds : list
            List of upper burnup values in percent.

        Raises
        ------
        ValueError
            If the provided burnup groups are invalid
        """
        self._upperBuGroupBounds = upperBuGroupBounds
        lastBu = 0.0
        for upperBu in self._upperBuGroupBounds:
            if upperBu <= 0 or upperBu > 100:
                raise ValueError(
                    "Burnup group upper bound {0} is invalid".format(upperBu)
                )
            if upperBu < lastBu:
                raise ValueError("Burnup groups must be ascending")
            lastBu = upperBu

    def _updateBurnupGroups(self, blockList):
        """
        Update the burnup group of each block based on its burnup

        If only one burnup group exists, then this is skipped so as to accomodate the possibility
        of 2-character xsGroup values (useful for detailed V&V models w/o depletion).

        See Also
        --------
        armi.reactor.blocks.Block.getMicroSuffix
        """
        if self._buGroupUpdatesEnabled and len(self._upperBuGroupBounds) > 1:
            runLog.debug("Updating burnup groups of {0} blocks".format(len(blockList)))
            for block in blockList:
                bu = block.p.percentBu
                for buGroupIndex, upperBu in enumerate(self._upperBuGroupBounds):
                    if bu <= upperBu:
                        block.p.buGroupNum = buGroupIndex
                        break
                else:
                    raise ValueError("no bu group found for bu={0}".format(bu))
        else:
            runLog.debug(
                "Skipping burnup group update of {0} blocks because it is disabled"
                "".format(len(blockList))
            )

    def _addXsGroupsFromBlocks(self, blockCollectionsByXsGroup, blockList):
        """
        Build all the cross section groups based on their XS type and BU group

        Also ensures that their BU group is up to date with their burnup.
        """
        self._updateBurnupGroups(blockList)
        for b in blockList:
            xsID = b.getMicroSuffix()
            xsSettings = self._initializeXsID(xsID)
            blockCollectionType = blockCollectionFactory(
                xsSettings, self.r.blueprints.allNuclidesInProblem
            )
            group = blockCollectionsByXsGroup.get(xsID, blockCollectionType)
            group.append(b)
            blockCollectionsByXsGroup[xsID] = group
        return blockCollectionsByXsGroup

    def _initializeXsID(self, xsID):
        """Initialize a new xs id."""
        if xsID not in self.cs[CONF_CROSS_SECTION]:
            runLog.debug("Initializing XS ID {}".format(xsID), single=True)
        return self.cs[CONF_CROSS_SECTION][xsID]

    def xsTypeIsPregenerated(self, xsID):
        """Return True if the xs id is pre-generated."""
        return self.cs[CONF_CROSS_SECTION][xsID].isPregenerated

    def _copyPregeneratedXSFile(self, xsID):
        # stop a race condition to copy files between all processors
        if armi.MPI_RANK != 0:
            return

        for xsFileLocation, xsFileName in self._getPregeneratedXsFileLocationData(xsID):
            dest = os.path.join(os.getcwd(), xsFileName)
            # Optimization to reduce the number of times the files are copied over
            if not os.path.exists(dest):
                runLog.extra(
                    "Copying pre-generated XS file {} from {} for XS ID {}".format(
                        xsFileName, os.path.dirname(xsFileLocation), xsID
                    )
                )
                shutil.copy(xsFileLocation, dest)
            else:
                runLog.extra("Using existing pre-generated XS file: {}".format(dest))

    def _getPregeneratedXsFileLocationData(self, xsID):
        """
        Gather the pregenerated cross section file data and check that the files exist.

        Notes
        -----
        Multiple files can exist on the `file location` setting for a single XS ID. This checks that all files exist
        and returns a list of tuples (file path, fileName).
        """
        fileData = []
        filePaths = self.cs[CONF_CROSS_SECTION][xsID].fileLocation
        for filePath in filePaths:
            filePath = os.path.abspath(filePath)
            if not os.path.exists(filePath) or os.path.isdir(filePath):
                raise ValueError(
                    "External cross section path for XS ID {} is not a valid file location {}".format(
                        xsID, filePath
                    )
                )
            fileName = os.path.basename(filePath)
            fileData.append((filePath, fileName))
        return fileData

    def createRepresentativeBlocks(self):
        """
        Get a representative block from each cross section ID managed here.
        """
        representativeBlocks = {}
        self.avgNucTemperatures = {}
        self._unrepresentedXSIDs = []
        runLog.extra("Generating representative blocks for XS")
        blockCollectionsByXsGroup = self.makeCrossSectionGroups()
        for xsID, collection in blockCollectionsByXsGroup.items():
            numCandidateBlocks = len(collection.getCandidateBlocks())
            if self.xsTypeIsPregenerated(xsID):
                self._copyPregeneratedXSFile(xsID)
                continue
            if numCandidateBlocks > 0:
                runLog.debug("Creating representative block for {}".format(xsID))
                reprBlock = collection.createRepresentativeBlock()
                representativeBlocks[xsID] = reprBlock
                self.avgNucTemperatures[xsID] = collection.avgNucTemperatures
            else:
                runLog.debug(
                    "No candidate blocks for {} will apply different burnup group".format(
                        xsID
                    )
                )
                self._unrepresentedXSIDs.append(xsID)

        self.representativeBlocks = collections.OrderedDict(
            sorted(representativeBlocks.items())
        )
        self._modifyUnrepresentedXSIDs(blockCollectionsByXsGroup)
        self._summarizeGroups(blockCollectionsByXsGroup)

    def createRepresentativeBlocksUsingExistingBlocks(
        self, blockList, originalRepresentativeBlocks
    ):
        """
        Create a new set of representative blocks using provided blocks.

        This uses an input list of blocks and creates new representative blocks for these blocks based on the
        compositions and temperatures of their original representative blocks.

        Notes
        -----
        This is required for computing Doppler, Voided-Doppler, Temperature, and Voided-Temperature reactivity
        coefficients, where the composition of the representative block must remain the same, but only the
        temperatures within the representative blocks are to be modified.

        Parameters
        ----------
        blockList : list
            A list of blocks defined within the core
        originalRepresentativeBlocks : list
            A list of unperturbed representative blocks that the new representative blocks are formed from

        Returns
        -------
        blockCollectionByXsGroup : dict
            Mapping between XS IDs and the new block collections
        modifiedReprBlocks : dict
            Mapping between XS IDs and the new representative blocks

        Raises
        ------
        ValueError
            If passed list arguments are empty
        """
        if not blockList:
            raise ValueError(
                "A block list was not supplied to create new representative blocks"
            )
        if not originalRepresentativeBlocks:
            raise ValueError(
                "New representative blocks cannot be created because a list of unperturbed "
                "representative blocks was not provided"
            )
        newBlockCollectionsByXsGroup = collections.OrderedDict()
        blockCollectionByXsGroup = self.makeCrossSectionGroups()
        modifiedReprBlocks, origXSIDsFromNew = self._getModifiedReprBlocks(
            blockList, originalRepresentativeBlocks
        )
        if not modifiedReprBlocks:
            return None
        for newXSID in modifiedReprBlocks:
            oldXSID = origXSIDsFromNew[newXSID]
            oldBlockCollection = blockCollectionByXsGroup[oldXSID]
            newBlockCollection = oldBlockCollection.__class__(
                oldBlockCollection.allNuclidesInProblem
            )
            newBlockCollectionsByXsGroup[newXSID] = newBlockCollection
        return newBlockCollectionsByXsGroup, modifiedReprBlocks

    def _getModifiedReprBlocks(self, blockList, originalRepresentativeBlocks):
        """
        Create a new representative block for each unique XS ID on blocks to be modified.

        Returns
        -------
        modifiedReprBlocks : dict
            Mapping between the new XS IDs and the new representative blocks
        origXSIDsFromNew : dict
            Mapping between the new representative block XS IDs and the original representative block XS IDs
        """
        modifiedBlockXSTypes = collections.OrderedDict()
        modifiedReprBlocks = collections.OrderedDict()
        origXSIDsFromNew = collections.OrderedDict()
        for b in blockList:
            origXSID = b.getMicroSuffix()
            # Filter out the pre-generated XS IDs
            if origXSID not in originalRepresentativeBlocks:
                if self.xsTypeIsPregenerated(origXSID):
                    runLog.warning(
                        "A modified representative block for XS ID `{}` cannot be created because it is "
                        "mapped to a pre-generated cross section set. Please ensure that this "
                        "approximation is valid for the analysis.".format(origXSID),
                        single=True,
                    )
            else:
                origXSType = origXSID[0]
                if origXSType not in modifiedBlockXSTypes.keys():
                    nextXSType = self.getNextAvailableXsTypes(
                        excludedXSTypes=modifiedBlockXSTypes.values()
                    )[0]
                    modifiedBlockXSTypes[origXSType] = nextXSType
                newXSID = (
                    modifiedBlockXSTypes[origXSType] + origXSID[1]
                )  # New XS Type + Old Burnup Group
                origXSIDsFromNew[newXSID] = origXSID
        # Create new representative blocks based on the original XS IDs
        for newXSID, origXSID in origXSIDsFromNew.items():
            runLog.extra(
                "Creating representative block `{}` with composition from representative block `{}`".format(
                    newXSID, origXSID
                )
            )
            newXSType = newXSID[0]
            newReprBlock = copy.deepcopy(originalRepresentativeBlocks[origXSID])
            newReprBlock.p.xsType = newXSType
            newReprBlock.name = "AVG_{}".format(newXSID)
            modifiedReprBlocks[newXSID] = newReprBlock
            # Update the XS types of the blocks that will be modified
            for b in blockList:
                if b.getMicroSuffix() == origXSID:
                    b.p.xsType = newXSType
        return modifiedReprBlocks, origXSIDsFromNew

    def getNextAvailableXsTypes(self, howMany=1, excludedXSTypes=None):
        """Return the next however many available xs types.

        Parameters
        ----------
        howMany : int, optional
            The number of requested xs types
        excludedXSTypes : list, optional
            A list of cross section types to exclude from using

        Raises
        ------
        ValueError
            If there are no available XS types to be allocated
        """
        allocatedXSTypes = set()
        for b in self.r.core.getBlocks(includeAll=True):
            allocatedXSTypes.add(b.p.xsType)
        if excludedXSTypes is not None:
            for xsType in excludedXSTypes:
                allocatedXSTypes.add(xsType)
        availableXsTypes = sorted(
            list(set(_ALLOWABLE_XS_TYPE_LIST).difference(allocatedXSTypes))
        )
        if len(availableXsTypes) < howMany:
            raise ValueError(
                "There are not enough available xs types. {} have been allocated, {} are available, and "
                "{} have been requested.".format(
                    len(allocatedXSTypes), len(availableXsTypes), howMany
                )
            )
        return availableXsTypes[:howMany]

    def _getUnrepresentedBlocks(self, blockCollectionsByXsGroup):
        r"""
        gets all blocks with suffixes not yet represented (for blocks in assemblies in the blueprints but not the core).

        Notes
        -----
        Certain cases (ZPPR validation cases) need to run cross sections for assemblies not in
        the core to get by region cross sections and flux factors.
        """
        unrepresentedBlocks = []
        for a in self.r.blueprints.assemblies.values():
            for b in a:
                if b.getMicroSuffix() not in blockCollectionsByXsGroup:
                    b2 = copy.deepcopy(b)
                    unrepresentedBlocks.append(b2)
        return unrepresentedBlocks

    def makeCrossSectionGroups(self):
        """
        Make cross section groups for all blocks in reactor and unrepresented blocks from blueprints.
        """
        bCollectXSGroup = {}  # clear old groups (in case some are no longer existent)
        bCollectXSGroup = self._addXsGroupsFromBlocks(
            bCollectXSGroup, self.r.core.getBlocks()
        )
        bCollectXSGroup = self._addXsGroupsFromBlocks(
            bCollectXSGroup, self._getUnrepresentedBlocks(bCollectXSGroup)
        )
        blockCollectionsByXsGroup = collections.OrderedDict(
            sorted(bCollectXSGroup.items())
        )
        return blockCollectionsByXsGroup

    def _modifyUnrepresentedXSIDs(self, blockCollectionsByXsGroup):
        """
        adjust the xsID of blocks in the groups that are not represented

        Try to just adjust the burnup group up to something that is represented
        (can happen to structure in AA when only AB, AC, AD still remain).

        """
        for xsID in self._unrepresentedXSIDs:
            missingXsType, _missingBuGroup = xsID
            for otherXsID in self.representativeBlocks:  # order gets closest BU
                repType, repBuGroup = otherXsID
                if repType == missingXsType:
                    nonRepBlocks = blockCollectionsByXsGroup.get(xsID)
                    if nonRepBlocks:
                        runLog.extra(
                            "Changing XSID of {0} blocks from {1} to {2}"
                            "".format(len(nonRepBlocks), xsID, otherXsID)
                        )
                        for b in nonRepBlocks:
                            b.p.buGroup = repBuGroup
                    break
            else:
                runLog.warning(
                    "No representative blocks with XS type {0} exist in the core. "
                    "These XS cannot be generated and must exist in the working "
                    "directory or the run will fail.".format(xsID)
                )

    def _summarizeGroups(self, blockCollectionsByXsGroup):
        """Summarize current contents of the XS groups."""
        runLog.extra("Cross section group manager summary")
        runLog.extra(
            "Averaging performed by `{0}`".format(self.cs["xsBlockRepresentation"])
        )
        for xsID, blocks in blockCollectionsByXsGroup.items():
            if blocks:
                xsIDGroup = self._getXsIDGroup(xsID)
                if xsIDGroup == self._REPR_GROUP:
                    reprBlock = self.representativeBlocks.get(xsID)
                    lfps = reprBlock.getLumpedFissionProductCollection()
                    if lfps:
                        fissionGasRemoved = list(lfps.values())[0].getGasRemovedFrac()
                    else:
                        fissionGasRemoved = 0.0
                    runLog.extra(
                        "XS ID {} contains {:4d} blocks, represented by: {:65s}"
                        " Fission Gas Removal Fraction: {:.2f}".format(
                            xsID, len(blocks), reprBlock, fissionGasRemoved
                        )
                    )
                elif xsIDGroup == self._NON_REPR_GROUP:
                    runLog.extra(
                        "XS ID {} contains {:4d} blocks, but no representative block."
                        "".format(xsID, len(blocks))
                    )
                elif xsIDGroup == self._PREGEN_GROUP:
                    xsFileNames = [
                        y for _x, y in self._getPregeneratedXsFileLocationData(xsID)
                    ]
                    runLog.extra(
                        "XS ID {} contains {:4d} blocks, represented by: {}"
                        "".format(xsID, len(blocks), xsFileNames)
                    )
                else:
                    raise ValueError("No valid group for XS ID {}".format(xsID))

    def _getXsIDGroup(self, xsID):
        if self.xsTypeIsPregenerated(xsID):
            return self._PREGEN_GROUP
        elif xsID in self.representativeBlocks.keys():
            return self._REPR_GROUP
        elif xsID in self._unrepresentedXSIDs:
            return self._NON_REPR_GROUP
        return None

    def disableBuGroupUpdates(self):
        """
        Turn off updating bu groups based on burnup

        Useful during reactivity coefficient calculations to be consistent with ref. run.

        See Also
        --------
        enableBuGroupUpdates
        """
        runLog.extra("Burnup group updating disabled")
        wasEnabled = self._buGroupUpdatesEnabled
        self._buGroupUpdatesEnabled = False
        return wasEnabled

    def enableBuGroupUpdates(self):
        """
        Turn on updating bu groups based on burnup

        See Also
        --------
        disableBuGroupUpdates
        """
        runLog.extra("Burnup group updating enabled")
        self._buGroupUpdatesEnabled = True

    def getNucTemperature(self, xsID, nucName):
        """
        Return the temperature (in C) of the nuclide in the group with specified xsID.

        Notes
        -----
        Returns None if the xsID or nucName are not in the average nuclide temperature dictionary
        `self.avgNucTemperatures`
        """
        if xsID not in self.avgNucTemperatures:
            return None
        return self.avgNucTemperatures[xsID].get(nucName, None)

    def updateNuclideTemperatures(self, blockCollectionByXsGroup=None):
        """
        Recompute nuclide temperatures for the block collections within the core.

        Parameters
        ----------
        blockCollectionByXsGroup : dict, optional
            Mapping between the XS IDs in the core and the block collections. Note that providing this as
            an arugment will only update the average temperatures of these XS IDs/block collections and will
            result in other XS ID average temperatures not included to be discarded.

        Notes
        -----
        This method does not update any properties of the representative blocks.
        Temperatures are obtained from the BlockCollection class rather than the representative block.
        """
        self.avgNucTemperatures = {}
        blockCollectionsByXsGroup = (
            blockCollectionByXsGroup or self.makeCrossSectionGroups()
        )
        runLog.info(
            "Updating representative block average nuclide temperatures for the following XS IDs: {}".format(
                blockCollectionsByXsGroup.keys()
            )
        )
        for xsID, collection in blockCollectionsByXsGroup.items():
            collection.calcAvgNuclideTemperatures()
            self.avgNucTemperatures[xsID] = collection.avgNucTemperatures
            runLog.extra("XS ID: {}, Collection: {}".format(xsID, collection))


BLOCK_COLLECTIONS = {
    "Median": MedianBlockCollection,
    "Average": AverageBlockCollection,
    "ComponentAverage1DSlab": SlabComponentsAverageBlockCollection,
    "FluxWeightedAverage": FluxWeightedAverageBlockCollection,
}

HOMOGENEOUS_BLOCK_COLLECTIONS = {
    "Median": MedianBlockCollection,
    "Average": AverageBlockCollection,
    "FluxWeightedAverage": FluxWeightedAverageBlockCollection,
}


def blockCollectionFactory(xsSettings, allNuclidesInProblem):
    """
    Build a block collection based on user settings and input.
    """
    blockRepresentation = xsSettings.blockRepresentation
    validBlockTypes = xsSettings.validBlockTypes
    return BLOCK_COLLECTIONS[blockRepresentation](
        allNuclidesInProblem, validBlockTypes=validBlockTypes
    )
