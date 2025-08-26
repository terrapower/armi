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

Generally, the cross section manager is a attribute of the lattice physics code interface

Examples
--------
    csm = CrossSectionGroupManager()
    csm._setBuGroupBounds(cs['buGroups'])
    csm._setTempGroupBounds(cs['tempGroups']) # or empty list
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

import collections
import copy
import os
import string
import sys

import numpy as np

from armi import context, interfaces, runLog
from armi.physics.neutronics import LatticePhysicsFrequency
from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.reactor import flags
from armi.reactor.components import basicShapes
from armi.reactor.flags import Flags
from armi.utils import safeCopy
from armi.utils.units import C_TO_K, TRACE_NUMBER_DENSITY

ORDER = interfaces.STACK_ORDER.BEFORE + interfaces.STACK_ORDER.CROSS_SECTIONS


def describeInterfaces(cs):
    """Function for exposing interface(s) to other code."""
    from armi.physics.neutronics.settings import CONF_NEUTRONICS_KERNEL

    if "MCNP" not in cs[CONF_NEUTRONICS_KERNEL]:  # MCNP does not use CSGM
        return (CrossSectionGroupManager, {})

    return None


_ALLOWABLE_XS_TYPE_LIST = list(string.ascii_uppercase + string.ascii_lowercase)


def getXSTypeNumberFromLabel(xsTypeLabel: str) -> int:
    """
    Convert a XSID label (e.g. 'AA') to an integer.

    Useful for visualizing XS type in XTVIEW.

    2-digit labels are supported when there is only one burnup group.
    """
    return int("".join(["{:02d}".format(ord(si)) for si in xsTypeLabel]))


def getXSTypeLabelFromNumber(xsTypeNumber: int) -> str:
    """
    Convert a XSID label (e.g. 65) to an XS label (e.g. 'A').

    Useful for visualizing XS type in XTVIEW.

    2-digit labels are supported when there is only one burnup group.
    """
    try:
        if xsTypeNumber > ord("Z"):
            # two digit. Parse
            return chr(int(str(xsTypeNumber)[:2])) + chr(int(str(xsTypeNumber)[2:]))
        elif xsTypeNumber < ord("A"):
            raise ValueError(
                f"Cannot convert invalid xsTypeNumber `{xsTypeNumber}` to char. "
                "The number must be >= 65 (corresponding to 'A')."
            )
        else:
            return chr(xsTypeNumber)
    except ValueError:
        runLog.error("Error converting {} to label.".format(xsTypeNumber))
        raise


class BlockCollection(list):
    """
    Controls which blocks are representative of a particular cross section type/BU group.

    This is a list with special methods.
    """

    def __init__(self, allNuclidesInProblem, validBlockTypes=None, averageByComponent=False):
        list.__init__(self)
        self.allNuclidesInProblem = allNuclidesInProblem
        self.weightingParam = None
        self.averageByComponent = averageByComponent

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
            weights = [block.p[self.weightingParam] for block in self.getCandidateBlocks()]
        anyNonZeros = any(weights)
        if anyNonZeros and not all(weights):
            # we have at least one non-zero entry and at least one zero. This is bad.
            # find the non-zero ones for debugging
            zeros = [block for block in self if not block.p[self.weightingParam]]
            runLog.error("Blocks with zero `{0}` include: {1}".format(self.weightingParam, zeros))
            raise ValueError(
                "{0} has a mixture of zero and non-zero weighting factors (`{1}`)\nSee stdout for details".format(
                    self, self.weightingParam
                )
            )

    def calcAvgNuclideTemperatures(self):
        r"""
        Calculate the average nuclide temperatures in this collection based on the blocks in the collection.

        If a nuclide is in multiple components, that's taken into consideration.

        .. math::
             T = \frac{\sum{n_i v_i T_i}}{\sum{n_i v_i}}

        where :math:`n_i` is a number density, :math:`v_i` is a volume, and :math:`T_i` is a temperature
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
        """Get value of weighting function for this block."""
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

    def _calcWeightedBurnup(self):
        """
        For a blockCollection that represents fuel, calculate the weighted average burnup.

        Notes
        -----
        - Only used for logging purposes
        - Burnup needs to be weighted by heavy metal mass instead of volume
        """
        weightedBurnup = 0.0
        totalWeight = 0.0
        for b in self:
            # self.getWeight(b) incorporates the volume as does mass, so divide by volume not to double-count
            weighting = b.p.massHmBOL * self.getWeight(b) / b.getVolume()
            totalWeight += weighting
            weightedBurnup += weighting * b.p.percentBu
        return 0.0 if totalWeight == 0.0 else weightedBurnup / totalWeight


class MedianBlockCollection(BlockCollection):
    """Returns the median burnup block. This is a simple and often accurate approximation."""

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
        return getBlockNuclideTemperatureAvgTerms(medianBlock, self.allNuclidesInProblem)

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
    Block collection that builds a new block based on others in collection.

    Averages number densities, fission product yields, and fission gas
    removal fractions.

    .. impl:: Create representative blocks using volume-weighted averaging.
        :id: I_ARMI_XSGM_CREATE_REPR_BLOCKS0
        :implements: R_ARMI_XSGM_CREATE_REPR_BLOCKS

        This class constructs new blocks from an existing block list based on a volume-weighted
        average. Inheriting functionality from the abstract
        :py:class:`Reactor <armi.physics.neutronics.crossSectionGroupManager.BlockCollection>`
        object, this class will construct representative blocks using averaged parameters of all
        blocks in the given collection. Number density averages can be computed at a component level
        or at a block level by default. Average nuclide temperatures and burnup are also included
        when constructing a representative block.
    """

    def _makeRepresentativeBlock(self):
        """Generate a block that best represents all blocks in group."""
        newBlock = self._getNewBlock()
        lfpCollection = self._getLFP()
        newBlock.setLumpedFissionProducts(lfpCollection)
        # check if components are similar
        if self._performAverageByComponent():
            # set number densities and temperatures on a component basis
            for compIndex, c in enumerate(sorted(newBlock.getComponents())):
                c.setNumberDensities(self._getAverageComponentNumberDensities(compIndex))
                c.temperatureInC = self._getAverageComponentTemperature(compIndex)
        else:
            newBlock.setNumberDensities(self._getAverageNumberDensities())

        newBlock.p.percentBu = self._calcWeightedBurnup()
        newBlock.clearCache()
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
        weights = np.array([self.getWeight(b) for b in blocks])
        weights /= weights.sum()  # normalize by total weight
        ndens = weights.dot([b.getNuclideNumberDensities(nuclides) for b in blocks])
        return dict(zip(nuclides, ndens))

    def _getLFP(self):
        """Find lumped fission product collection."""
        b = self.getCandidateBlocks()[0]
        return b.getLumpedFissionProductCollection()

    def _getNucTempHelper(self):
        """All candidate blocks are used in the average."""
        nvt = np.zeros(len(self.allNuclidesInProblem))
        nv = np.zeros(len(self.allNuclidesInProblem))
        for block in self.getCandidateBlocks():
            wt = self.getWeight(block)
            nvtBlock, nvBlock = getBlockNuclideTemperatureAvgTerms(block, self.allNuclidesInProblem)
            nvt += nvtBlock * wt
            nv += nvBlock * wt

        return nvt, nv

    def _getAverageComponentNumberDensities(self, compIndex):
        """
        Get weighted average number densities of a component in the collection.

        Returns
        -------
        numberDensities : dict
            nucName, ndens data (atoms/bn-cm)
        """
        blocks = self.getCandidateBlocks()
        weights = np.array([self.getWeight(b) for b in blocks])
        weights /= weights.sum()  # normalize by total weight
        components = [sorted(b.getComponents())[compIndex] for b in blocks]
        nuclides = self._getAllNucs(components)
        ndens = weights.dot([c.getNuclideNumberDensities(nuclides) for c in components])
        return dict(zip(nuclides, ndens))

    def _getAverageComponentTemperature(self, compIndex):
        """
        Get weighted average component temperature for the collection.

        Notes
        -----
        Weighting is both by the block weight within the collection and the relative mass of the
        Component. The block weight is already scaled by the block volume, so we need to pull that
        out of the block weighting because it would effectively be double-counted in the component
        mass. b.getHeight() is proportional to block volume, so it is used here as a computationally
        cheaper proxy for scaling by block volume.

        Returns
        -------
        numberDensities : dict
            nucName, ndens data (atoms/bn-cm)
        """
        blocks = self.getCandidateBlocks()
        weights = np.array([self.getWeight(b) / b.getHeight() for b in blocks])
        weights /= weights.sum()  # normalize by total weight
        components = [sorted(b.getComponents())[compIndex] for b in blocks]
        weightedAvgComponentMass = sum(w * c.getMass() for w, c in zip(weights, components))
        if weightedAvgComponentMass == 0.0:
            # if there is no component mass (e.g., gap), do a regular average
            return np.mean(np.array([c.temperatureInC for c in components]))
        else:
            return (
                weights.dot(np.array([c.temperatureInC * c.getMass() for c in components])) / weightedAvgComponentMass
            )

    def _performAverageByComponent(self):
        """
        Check if block collection averaging can/should be performed by component.

        If the components of blocks in the collection are similar and the user has requested
        Component-level averaging, return True. Otherwise, return False.
        """
        if not self.averageByComponent:
            return False
        else:
            return self._checkBlockSimilarity()

    def _checkBlockSimilarity(self):
        """
        Check if blocks in the collection have similar components.

        If the components of blocks in the collection are similar and the user has requested
        Component-level averaging, return True. Otherwise, return False.
        """
        cFlags = dict()
        for b in self.getCandidateBlocks():
            cFlags[b] = [c.p.flags for c in sorted(b.getComponents())]
        refB = b
        refFlags = cFlags[refB]
        for b, compFlags in cFlags.items():
            for c, refC in zip(compFlags, refFlags):
                if c != refC:
                    runLog.warning(
                        "Non-matching block in AverageBlockCollection!\n"
                        f"{refC} component flags in {refB} does not match {c} in {b}.\n"
                        f"Number densities will be smeared in representative block."
                    )
                    return False
        else:
            return True

    @staticmethod
    def _getAllNucs(components):
        """Iterate through components and get all unique nuclides."""
        nucs = set()
        for c in components:
            nucs = nucs.union(c.getNuclides())
        return sorted(list(nucs))


def getBlockNuclideTemperature(block, nuclide):
    """Return the average temperature for 1 nuclide."""
    tempIntegratedVolume, volume = getBlockNuclideTemperatureAvgTerms(block, [nuclide])
    return tempIntegratedVolume / volume if volume > 0 else 0.0


def getBlockNuclideTemperatureAvgTerms(block, allNucNames):
    """
    Compute terms (numerator, denominator) of average for this block.

    This volume-weights the densities by component volume fraction.

    It's important to count zero-density nuclides (i.e. ones like AM242 that are expected to build
    up) as trace values at the proper component temperatures.
    """

    def getNumberDensitiesWithTrace(component, allNucNames):
        """Needed to make sure temperature of 0-density nuclides in fuel get fuel temperature."""
        if component.p.nuclides is None:
            return [0.0 for _nuc in allNucNames]

        allByteNucs = [nucName.encode() for nucName in allNucNames]
        ndens = []
        nucCopy = np.array(component.p.nuclides)
        nDensCopy = np.array(component.p.numberDensities)
        reverseIndex = {nuc: i for i, nuc in enumerate(nucCopy)}
        for nuc in allByteNucs:
            i = reverseIndex.get(nuc, -1)
            if i >= 0:
                ndens.append(max(nDensCopy[i], TRACE_NUMBER_DENSITY))
            else:
                ndens.append(0.0)
        return ndens

    vol = block.getVolume()
    components, volFracs = zip(*block.getVolumeFractions())
    # D = CxN matrix of number densities
    ndens = np.array([getNumberDensitiesWithTrace(c, allNucNames) for c in components])

    # C-length temperature array
    temperatures = np.array([c.temperatureInC for c in components])

    # multiply each component's values by volume frac, now NxC
    nvBlock = ndens.T * np.array(volFracs) * vol

    nvt = sum((nvBlock * temperatures).T)  # N-length array summing over components.
    nv = sum(nvBlock.T)  # N-length array
    return nvt, nv


class CylindricalComponentsAverageBlockCollection(AverageBlockCollection):
    """
    Creates a representative block for the purpose of cross section generation with a one-
    dimensional cylindrical model.

    .. impl:: Create representative blocks using custom cylindrical averaging.
        :id: I_ARMI_XSGM_CREATE_REPR_BLOCKS1
        :implements: R_ARMI_XSGM_CREATE_REPR_BLOCKS

        This class constructs representative blocks based on a volume-weighted average using
        cylindrical blocks from an existing block list. Inheriting functionality from the abstract
        :py:class:`Reactor <armi.physics.neutronics.crossSectionGroupManager.BlockCollection>`
        object, this class will construct representative blocks using averaged parameters of all
        blocks in the given collection. Number density averages are computed at a component level.
        Nuclide temperatures from a median block-average temperature are used and the average burnup
        is evaluated across all blocks in the block list.

    Notes
    -----
    When generating the representative block within this collection, the geometry is checked against
    all other blocks to ensure that the number of components are consistent. This implementation is
    intended to be opinionated, so if a user attempts to put blocks that have geometric differences
    then this will fail.

    This selects a representative block based on the collection of candidates based on the median
    Block-average temperatures as an assumption.
    """

    def _getNewBlock(self):
        newBlock = copy.deepcopy(self._selectCandidateBlock())
        newBlock.name = "1D_CYL_AVG_" + newBlock.getMicroSuffix()
        return newBlock

    def _selectCandidateBlock(self):
        """Selects the candidate block with the median block-average temperature."""
        info = []
        for b in self.getCandidateBlocks():
            info.append((b.getAverageTempInC(), b.getName(), b))
        info.sort()
        medianBlockData = info[len(info) // 2]
        return medianBlockData[-1]

    def _makeRepresentativeBlock(self):
        """Build a representative fuel block based on component number densities."""
        repBlock = self._getNewBlock()
        bWeights = [self.getWeight(b) for b in self.getCandidateBlocks()]
        repBlock.p.percentBu = self._calcWeightedBurnup()
        componentsInOrder = self._orderComponentsInGroup(repBlock)

        for i, (c, allSimilarComponents) in enumerate(zip(sorted(repBlock), componentsInOrder)):
            allNucsNames, densities = self._getAverageComponentNucs(allSimilarComponents, bWeights)
            for nuc, aDensity in zip(allNucsNames, densities):
                c.setNumberDensity(nuc, aDensity)
            c.temperatureInC = self._getAverageComponentTemperature(i)
        repBlock.clearCache()
        self.calcAvgNuclideTemperatures()
        return repBlock

    @staticmethod
    def _checkComponentConsistency(b, repBlock):
        """
        Verify that all components being homogenized have same multiplicity and nuclides.

        Raises
        ------
        ValueError
            When the components in a candidate block do not align with the components in the
            representative Block. This check includes component area, component multiplicity, and
            nuclide composition.
        """
        if len(b) != len(repBlock):
            raise ValueError(f"Blocks {b} and {repBlock} have differing number of components and cannot be homogenized")

        # NOTE: We are using Fe-56 as a proxy for structure and Na-23 as proxy for coolant is
        # undesirably SFR-centric. This should be generalized in the future, if possible.
        consistentNucs = {"PU239", "U238", "U235", "U234", "FE56", "NA23", "O16"}
        for c, repC in zip(sorted(b), sorted(repBlock)):
            compString = f"Component {repC} in block {repBlock} and component {c} in block {b}"
            if c.p.mult != repC.p.mult:
                raise ValueError(
                    f"{compString} must have the same multiplicity, but they have. {repC.p.mult} "
                    f"and {c.p.mult}, respectively."
                )

            theseNucs = set(c.getNuclides())
            thoseNucs = set(repC.getNuclides())
            # check for any differences between which `consistentNucs` the components have
            diffNucs = theseNucs.symmetric_difference(thoseNucs).intersection(consistentNucs)
            if diffNucs:
                raise ValueError(
                    f"{compString} are in the same location, but nuclides "
                    f"differ by {diffNucs}. \n{theseNucs} \n{thoseNucs}"
                )

    def _getAverageComponentNucs(self, components, bWeights):
        """Compute average nuclide densities by block weights and component area fractions."""
        allNucNames = self._getAllNucs(components)
        densities = np.zeros(len(allNucNames))
        totalWeight = 0.0
        for c, bWeight in zip(components, bWeights):
            weight = bWeight * c.getArea()
            totalWeight += weight
            densities += weight * np.array(c.getNuclideNumberDensities(allNucNames))

        if totalWeight > 0.0:
            weightedDensities = densities / totalWeight
        else:
            weightedDensities = np.zeros_like(densities)

        return allNucNames, weightedDensities

    def _orderComponentsInGroup(self, repBlock):
        """Order the components based on dimension and material type within the representative
        Block.
        """
        for b in self.getCandidateBlocks():
            self._checkComponentConsistency(b, repBlock)
        componentLists = [list(sorted(b)) for b in self.getCandidateBlocks()]
        return [list(comps) for comps in zip(*componentLists)]

    def _getNucTempHelper(self):
        """All candidate blocks are used in the average."""
        nvt = np.zeros(len(self.allNuclidesInProblem))
        nv = np.zeros(len(self.allNuclidesInProblem))
        for block in self.getCandidateBlocks():
            wt = self.getWeight(block)
            nvtBlock, nvBlock = getBlockNuclideTemperatureAvgTerms(block, self.allNuclidesInProblem)
            nvt += nvtBlock * wt
            nv += nvBlock * wt
        return nvt, nv


class CylindricalComponentsDuctHetAverageBlockCollection(CylindricalComponentsAverageBlockCollection):
    """
    Creates a representative block for the purpose of cross section generation with a one-
    dimensional cylindrical model where all material inside the duct is homogenized.

    .. impl:: Create partially heterogeneous representative blocks.
        :id: I_ARMI_XSGM_CREATE_REPR_BLOCKS2
        :implements: R_ARMI_XSGM_CREATE_REPR_BLOCKS

        This class constructs representative blocks based on a volume-weighted average using
        cylindrical blocks from an existing block list. Inheriting functionality from the abstract
        :py:class:`Reactor <armi.physics.neutronics.crossSectionGroupManager.BlockCollection>`
        object, this class will construct representative blocks using averaged parameters of all
        blocks in the given collection. Number density averages are computed at a component level.
        Nuclide temperatures from a median block-average temperature are used and the average burnup
        is evaluated across all blocks in the block list.

        The average nuclide temperatures are calculated only for the homogenized region inside of
        the duct. For the non-homogenized regions, the MC2 writer uses the component temperatures.

    Notes
    -----
    The representative block for this collection is the same as the parent. The only difference between
    the two collection types is that this collection calculates average nuclide temperatures based only
    on the components that are inside of the duct.
    """

    def _getNewBlock(self):
        newBlock = copy.deepcopy(self._selectCandidateBlock())
        newBlock.name = "1D_CYL_DUCT_HET_AVG_" + newBlock.getMicroSuffix()
        return newBlock

    def _makeRepresentativeBlock(self):
        """Build a representative fuel block based on component number densities."""
        self.calcAvgNuclideTemperatures()
        return CylindricalComponentsAverageBlockCollection._makeRepresentativeBlock(self)

    def _getNucTempHelper(self):
        """All candidate blocks are used in the average."""
        from armi.reactor.converters.blockConverters import stripComponents

        nvt = np.zeros(len(self.allNuclidesInProblem))
        nv = np.zeros(len(self.allNuclidesInProblem))
        for block in self.getCandidateBlocks():
            wt = self.getWeight(block)
            # remove the duct and intercoolant from the block before
            # calculating average nuclide temps
            newBlock, _mixtureFlags = stripComponents(block, Flags.DUCT)
            nvtBlock, nvBlock = getBlockNuclideTemperatureAvgTerms(newBlock, self.allNuclidesInProblem)
            nvt += nvtBlock * wt
            nv += nvBlock * wt
        return nvt, nv


class SlabComponentsAverageBlockCollection(BlockCollection):
    """
    Creates a representative 1D slab block.

    Notes
    -----
    - Ignores lumped fission products since there is no foreseeable need for burn calculations in 1D
      slab geometry since it is used for low power neutronic validation.
    - Checks for consistent component dimensions for all blocks in a group and then creates a new
      Block.
    - Iterates through components of all blocks and calculates component average number densities.
      This calculation takes the first component of each block, averages the number densities, and
      applies this to the number density to the representative block.
    """

    def _getNewBlock(self):
        newBlock = copy.deepcopy(self.getCandidateBlocks()[0])
        newBlock.name = "1D_SLAB_AVG_" + newBlock.getMicroSuffix()
        return newBlock

    def _makeRepresentativeBlock(self):
        """Build a representative fuel block based on component number densities."""
        repBlock = self._getNewBlock()
        bWeights = [self.getWeight(b) for b in self.getCandidateBlocks()]
        repBlock.p.percentBu = self._calcWeightedBurnup()
        componentsInOrder = self._orderComponentsInGroup(repBlock)

        for c, allSimilarComponents in zip(repBlock, componentsInOrder):
            allNucsNames, densities = self._getAverageComponentNucs(allSimilarComponents, bWeights)
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
    def _checkComponentConsistency(b, repBlock, components=None):
        """
        Verify that all components being homogenized are rectangular and have consistent dimensions.

        Raises
        ------
        ValueError
            When the components in a candidate block do not align with the components in the
            representative block. This check includes component area, component multiplicity, and
            nuclide composition.

        TypeError
            When the shape of the component is not a rectangle.

        Warning
        -------
        This only checks ``consistentNucs`` for ones that are important in ZPPR and BFS.
        """
        comps = b if components is None else components

        consistentNucs = ["PU239", "U238", "U235", "U234", "FE56", "NA23", "O16"]
        for c, repC in zip(comps, repBlock):
            if not isinstance(c, basicShapes.Rectangle):
                raise TypeError(
                    "The shape of component {} in block {} is invalid and must be a rectangle.".format(c, b)
                )
            compString = "Component {} in block {} and component {} in block {}".format(repC, repBlock, c, b)
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
                        "{} are in the same location, but are not consistent in nuclide {}. \n{} \n{}".format(
                            compString, nuc, theseNucs, thoseNucs
                        )
                    )
            if c.p.mult != repC.p.mult:
                raise ValueError("{} must have the same multiplicity to homogenize".format(compString))

    @staticmethod
    def _reverseComponentOrder(block):
        """Move the lattice component to the end of the components list."""
        latticeComponents = [c for c in block if c.isLatticeComponent()]
        components = [c for c in reversed(block) if not c.isLatticeComponent()]
        if len(latticeComponents) > 1:
            raise ValueError(
                "Block {} contains multiple `lattice` components: {}. Remove the additional "
                "lattice components in the reactor blueprints.".format(block, latticeComponents)
            )
        components.append(latticeComponents[0])
        return components

    @staticmethod
    def _removeLatticeComponents(repBlock):
        """
        Remove the lattice component from the representative block.

        Notes
        -----
        - This component does not serve any purpose for XS generation as it contains void material
          with zero area.
        - Removing this component does not modify the blocks within the reactor.
        """
        for c in repBlock.iterComponents():
            if c.isLatticeComponent():
                repBlock.remove(c)
        return repBlock

    def _getAverageComponentNucs(self, components, bWeights):
        """Compute average nuclide densities by block weights and component area fractions."""
        allNucNames = self._getAllNucs(components)
        densities = np.zeros(len(allNucNames))
        totalWeight = 0.0
        for c, bWeight in zip(components, bWeights):
            weight = bWeight * c.getArea()
            totalWeight += weight
            densities += weight * np.array(c.getNuclideNumberDensities(allNucNames))
        if totalWeight > 0.0:
            weightedDensities = densities / totalWeight
        else:
            weightedDensities = np.zeros_like(densities)
        return allNucNames, weightedDensities

    def _orderComponentsInGroup(self, repBlock):
        """Order the components based on dimension and material type within the representative block."""
        orderedComponents = [[] for _ in repBlock]
        for b in self.getCandidateBlocks():
            if len(b) != len(repBlock):
                raise ValueError(
                    "Blocks {} and {} have differing number of components and cannot be homogenized".format(b, repBlock)
                )
            try:
                self._checkComponentConsistency(b, repBlock)
                componentsToAdd = [c for c in b]
            except ValueError:
                runLog.extra(
                    "Checking if components in block {} are in the reverse order of the components in the "
                    "representative block {}".format(b, repBlock)
                )
                reversedComponentOrder = self._reverseComponentOrder(b)
                self._checkComponentConsistency(b, repBlock, components=reversedComponentOrder)
                componentsToAdd = [c for c in reversedComponentOrder]
            for i, c in enumerate(componentsToAdd):
                orderedComponents[i].append(c)  # group similar components
        return orderedComponents


class FluxWeightedAverageBlockCollection(AverageBlockCollection):
    """Flux-weighted AverageBlockCollection."""

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
        self._buGroupBounds = []
        self._tempGroupBounds = []
        self.representativeBlocks = collections.OrderedDict()
        self.avgNucTemperatures = {}

        # this turns off updates for when core changes are made, but dont want to re-evaluate XS
        # for example if lattice physics was only once per cycle we might not want to re-evaluate groups
        self._envGroupUpdatesEnabled = True
        self._setBuGroupBounds(self.cs["buGroups"])
        self._setTempGroupBounds(self.cs["tempGroups"])
        self._unrepresentedXSIDs = []

    def interactBOL(self):
        """Called at the Beginning-of-Life of a run, before any cycles start.

        .. impl:: The lattice physics interface and cross-section group manager are connected at
            BOL.
            :id: I_ARMI_XSGM_FREQ0
            :implements: R_ARMI_XSGM_FREQ

            This method sets the cross-section block averaging method and and logic for whether all
            blocks in a cross section group should be used when generating a representative block.
            Furthermore, if the control logic for lattice physics frequency updates is set at
            beginning-of-life (`BOL`) through the :py:class:`LatticePhysicsInterface
            <armi.physics.neutronics.latticePhysics>`, the cross-section group manager will
            construct representative blocks for each cross-section IDs at the beginning of the
            reactor state.
        """
        # now that all cs settings are loaded, apply defaults to compound XS settings
        from armi.physics.neutronics.settings import (
            CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION,
            CONF_LATTICE_PHYSICS_FREQUENCY,
            CONF_XS_BLOCK_REPRESENTATION,
        )

        self.cs[CONF_CROSS_SECTION].setDefaults(
            self.cs[CONF_XS_BLOCK_REPRESENTATION],
            self.cs[CONF_DISABLE_BLOCK_TYPE_EXCLUSION_IN_XS_GENERATION],
        )
        self._latticePhysicsFrequency = LatticePhysicsFrequency[self.cs[CONF_LATTICE_PHYSICS_FREQUENCY]]
        if self._latticePhysicsFrequency == LatticePhysicsFrequency.BOL:
            self.createRepresentativeBlocks()

    def interactBOC(self, cycle=None):
        """
        Update representative blocks and block burnup groups.

        .. impl:: The lattice physics interface and cross-section group manager are connected at
            BOC.
            :id: I_ARMI_XSGM_FREQ1
            :implements: R_ARMI_XSGM_FREQ

            This method updates representative blocks and block burnups at the beginning-of-cycle
            for each cross-section ID if the control logic for lattice physics frequency updates is
            set at beginning-of-cycle (`BOC`) through the :py:class:`LatticePhysicsInterface
            <armi.physics.neutronics.latticePhysics>`. At the beginning-of-cycle, the cross-section
            group manager will construct representative blocks for each cross-section IDs for the
            current reactor state.

        Notes
        -----
        The block list each each block collection cannot be emptied since it is used to derive nuclide temperatures.
        """
        if self._latticePhysicsFrequency == LatticePhysicsFrequency.BOC:
            self.createRepresentativeBlocks()

    def interactEOC(self, cycle=None):
        """EOC interaction.

        Clear out big dictionary of all blocks to avoid memory issues and out-of-date representers.
        """
        self.clearRepresentativeBlocks()

    def interactEveryNode(self, cycle=None, tn=None):
        """Interaction at every time node.

        .. impl:: The lattice physics interface and cross-section group manager are connected at
            every time node.
            :id: I_ARMI_XSGM_FREQ2
            :implements: R_ARMI_XSGM_FREQ

            This method updates representative blocks and block burnups at every node for each
            cross-section ID if the control logic for lattices physics frequency updates is set for
            every node (`everyNode`) through the :py:class:`LatticePhysicsInterface
            <armi.physics.neutronics.latticePhysics>`. At every node, the cross-section group
            manager will construct representative blocks for each cross-section ID in the current
            reactor state.
        """
        if self._latticePhysicsFrequency >= LatticePhysicsFrequency.everyNode:
            self.createRepresentativeBlocks()

    def interactCoupled(self, iteration):
        """Update cross-section groups on each physics coupling iteration to get latest
        temperatures.

        .. impl:: The lattice physics interface and cross-section group manager are connected
            during coupling.
            :id: I_ARMI_XSGM_FREQ3
            :implements: R_ARMI_XSGM_FREQ

            This method updates representative blocks and block burnups at every node and the first
            coupled iteration for each cross-section ID if the control logic for lattices physics
            frequency updates is set for the first coupled iteration (``firstCoupledIteration``)
            through the
            :py:class:`LatticePhysicsInterface <armi.physics.neutronics.latticePhysics>`.
            The cross-section group manager will construct representative blocks for each
            cross-section ID at the first iteration of every time node.

        Notes
        -----
        Updating the cross-section on only the first (i.e., iteration == 0) timenode can be a
        reasonable approximation to get new cross sections with some temperature updates but not
        have to run lattice physics on each coupled iteration. If the user desires to have the
        cross sections updated with every coupling iteration, the ``latticePhysicsFrequency: all``
        option.

        See Also
        --------
        :py:meth:`~armi.physics.neutronics.latticePhysics.latticePhysics.LatticePhysicsInterface.interactCoupled`
        """
        if (
            iteration == 0 and self._latticePhysicsFrequency == LatticePhysicsFrequency.firstCoupledIteration
        ) or self._latticePhysicsFrequency == LatticePhysicsFrequency.all:
            self.createRepresentativeBlocks()

    def clearRepresentativeBlocks(self):
        """Clear the representative blocks."""
        runLog.extra("Clearing representative blocks")
        self.representativeBlocks = collections.OrderedDict()
        self.avgNucTemperatures = {}

    def _setBuGroupBounds(self, buGroupBounds):
        """
        Set the burnup group structure.

        Parameters
        ----------
        buGroupBounds : list
            List of upper burnup values in percent.

        Raises
        ------
        ValueError
            If the provided burnup groups are invalid
        """
        lastBu = 0.0
        # validate structure
        for upperBu in buGroupBounds:
            if upperBu <= 0 or upperBu > 100:
                raise ValueError("Burnup group upper bound {0} is invalid".format(upperBu))
            if upperBu < lastBu:
                raise ValueError("Burnup groups must be ascending")
            lastBu = upperBu

        self._buGroupBounds = buGroupBounds + [float("inf")]

    def _setTempGroupBounds(self, tempGroupBounds):
        """Set the temperature group structure."""
        lastTemp = -C_TO_K
        # validate structure
        for upperTemp in tempGroupBounds:
            if upperTemp < -C_TO_K:
                raise ValueError("Temperature boundary is below absolute zero {0}.format(upperTemp)")
            if upperTemp < lastTemp:
                raise ValueError("Temp groups must be ascending")
            lastTemp = upperTemp
        self._tempGroupBounds = tempGroupBounds + [float("inf")]

    def _updateEnvironmentGroups(self, blockList):
        """
        Update the burnup group of each block based on its burnup and temperature .

        If only one burnup group exists, then this is skipped so as to accommodate the possibility
        of 2-character xsGroup values (useful for detailed V&V models w/o depletion).

        See Also
        --------
        armi.reactor.blocks.Block.getMicroSuffix
        """
        if not self._envGroupUpdatesEnabled:
            runLog.debug("Skipping burnup group update of {0} blocks because it is disabled".format(len(blockList)))
            return

        numBuGroups = len(self._buGroupBounds)
        if numBuGroups == 1 and len(self._tempGroupBounds) == 1:
            # dont set block.p.envGroupNum since all 1 group and we want to support 2 char xsGroup
            return
        runLog.debug("Updating env groups of {0} blocks".format(len(blockList)))
        for block in blockList:
            bu = block.p.percentBu
            for buIndex, upperBu in enumerate(self._buGroupBounds):
                if bu <= upperBu:
                    buGroupVal = buIndex
                    tempGroupVal = 0
                    isotope = self._initializeXsID(block.getMicroSuffix()).xsTempIsotope
                    if isotope and len(self._tempGroupBounds) > 1:
                        # if statement saves this somewhat expensive calc if we are not doing temp groups
                        tempC = getBlockNuclideTemperature(block, isotope)
                        for tempIndex, upperTemp in enumerate(self._tempGroupBounds):
                            if tempC <= upperTemp:
                                tempGroupVal = tempIndex
                                break
                    # this ordering groups like-temperatures together in group number
                    block.p.envGroupNum = tempGroupVal * numBuGroups + buGroupVal
                    break

    def _addXsGroupsFromBlocks(self, blockCollectionsByXsGroup, blockList):
        """
        Build all the cross section groups based on their XS type and Env group.

        Also ensures that their Env group is up to date with their environment.
        """
        self._updateEnvironmentGroups(blockList)
        for b in blockList:
            xsID = b.getMicroSuffix()
            xsSettings = self._initializeXsID(xsID)
            if self.cs["tempGroups"] and xsSettings.blockRepresentation == MEDIAN_BLOCK_COLLECTION:
                runLog.warning(
                    "Median block currently only consider median burnup block, and "
                    "not median temperature block in group"
                )
            blockCollectionType = blockCollectionFactory(xsSettings, self.r.blueprints.allNuclidesInProblem)

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
        """Return True if the cross sections for the given ``xsID`` is pre-generated."""
        return self.cs[CONF_CROSS_SECTION][xsID].xsIsPregenerated

    def fluxSolutionIsPregenerated(self, xsID):
        """Return True if an external flux solution file for the given ``xsID`` is pre-generated."""
        return self.cs[CONF_CROSS_SECTION][xsID].fluxIsPregenerated

    def _copyPregeneratedXSFile(self, xsID):
        # stop a race condition to copy files between all processors
        if context.MPI_RANK != 0:
            return

        for xsFileLocation, xsFileName in self._getPregeneratedXsFileLocationData(xsID):
            dest = os.path.join(os.getcwd(), xsFileName)
            runLog.extra(
                "Copying pre-generated XS file {} from {} for XS ID {}".format(
                    xsFileName, os.path.dirname(xsFileLocation), xsID
                )
            )
            # Prevent copy error if the path and destination are the same.
            if xsFileLocation != dest:
                safeCopy(xsFileLocation, dest)

    def _copyPregeneratedFluxSolutionFile(self, xsID):
        # stop a race condition to copy files between all processors
        if context.MPI_RANK != 0:
            return

        fluxFileLocation, fluxFileName = self._getPregeneratedFluxFileLocationData(xsID)
        dest = os.path.join(os.getcwd(), fluxFileName)
        runLog.extra(
            "Copying pre-generated flux solution file {} from {} for XS ID {}".format(
                fluxFileName, os.path.dirname(fluxFileLocation), xsID
            )
        )
        # Prevent copy error if the path and destination are the same.
        if fluxFileLocation != dest:
            safeCopy(fluxFileLocation, dest)

    def _getPregeneratedXsFileLocationData(self, xsID):
        """
        Gather the pre-generated cross section file data and check that the files exist.

        Notes
        -----
        Multiple files can exist on the `file location` setting for a single XS ID. This checks that all files exist
        and returns a list of tuples (file path, fileName).
        """
        fileData = []
        filePaths = self.cs[CONF_CROSS_SECTION][xsID].xsFileLocation
        for filePath in filePaths:
            filePath = os.path.abspath(filePath)
            if not os.path.exists(filePath) or os.path.isdir(filePath):
                raise ValueError(
                    "External cross section path for XS ID {} is not a valid file location {}".format(xsID, filePath)
                )
            fileName = os.path.basename(filePath)
            fileData.append((filePath, fileName))
        return fileData

    def _getPregeneratedFluxFileLocationData(self, xsID):
        """Gather the pre-generated flux solution file data and check that the files exist."""
        filePath = self.cs[CONF_CROSS_SECTION][xsID].fluxFileLocation
        filePath = os.path.abspath(filePath)
        if not os.path.exists(filePath) or os.path.isdir(filePath):
            raise ValueError(
                "External cross section path for XS ID {} is not a valid file location {}".format(xsID, filePath)
            )
        fileName = os.path.basename(filePath)
        return (filePath, fileName)

    def createRepresentativeBlocks(self):
        """Get a representative block from each cross-section ID managed here.

        .. impl:: Create collections of blocks based on cross-section type and burn-up group.
            :id: I_ARMI_XSGM_CREATE_XS_GROUPS
            :implements: R_ARMI_XSGM_CREATE_XS_GROUPS

            This method constructs the representative blocks and block burnups
            for each cross-section ID in the reactor model. Starting with the making of cross-section groups, it will
            find candidate blocks and create representative blocks from that selection.

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
                if self.fluxSolutionIsPregenerated(xsID):
                    self._copyPregeneratedFluxSolutionFile(xsID)
                reprBlock = collection.createRepresentativeBlock()
                representativeBlocks[xsID] = reprBlock
                self.avgNucTemperatures[xsID] = collection.avgNucTemperatures
            else:
                runLog.debug(
                    "No candidate blocks in group for {} (with a valid representative block flag). "
                    "Will apply different environment group".format(xsID)
                )
                self._unrepresentedXSIDs.append(xsID)

        self.representativeBlocks = collections.OrderedDict(sorted(representativeBlocks.items()))
        self._modifyUnrepresentedXSIDs(blockCollectionsByXsGroup)
        self._summarizeGroups(blockCollectionsByXsGroup)

    def createRepresentativeBlocksUsingExistingBlocks(self, blockList, originalRepresentativeBlocks):
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
        originalRepresentativeBlocks : dict
            A dict of unperturbed representative blocks that the new representative blocks are formed from
            keys: XS group ID (e.g., "AA")
            values: representative block for the XS group

        Returns
        -------
        blockCollectionByXsGroup : dict
            Mapping between XS IDs and the new block collections
        modifiedReprBlocks : dict
            Mapping between XS IDs and the new representative blocks
        origXSIDsFromNew : dict
            Mapping of original XS IDs to new XS IDs. New XS IDs are created to
            represent a modified state (e.g., a Doppler temperature perturbation).

        Raises
        ------
        ValueError
            If passed list arguments are empty
        """
        if not blockList:
            raise ValueError("A block list was not supplied to create new representative blocks")
        if not originalRepresentativeBlocks:
            raise ValueError(
                "New representative blocks cannot be created because a list of unperturbed "
                "representative blocks was not provided"
            )
        newBlockCollectionsByXsGroup = collections.OrderedDict()
        blockCollectionByXsGroup = self.makeCrossSectionGroups()
        modifiedReprBlocks, origXSIDsFromNew = self._getModifiedReprBlocks(blockList, originalRepresentativeBlocks)
        if not modifiedReprBlocks:
            return None
        for newXSID in modifiedReprBlocks:
            oldXSID = origXSIDsFromNew[newXSID]
            oldBlockCollection = blockCollectionByXsGroup[oldXSID]

            # create a new block collection that inherits all of the properties
            # and settings from oldBlockCollection.
            validBlockTypes = oldBlockCollection._validRepresentativeBlockTypes
            if validBlockTypes is not None and len(validBlockTypes) > 0:
                validBlockTypes = [
                    flags._toString(Flags, flag) for flag in oldBlockCollection._validRepresentativeBlockTypes
                ]
            newBlockCollection = oldBlockCollection.__class__(
                oldBlockCollection.allNuclidesInProblem,
                validBlockTypes=validBlockTypes,
                averageByComponent=oldBlockCollection.averageByComponent,
            )
            newBlockCollectionsByXsGroup[newXSID] = newBlockCollection
        return newBlockCollectionsByXsGroup, modifiedReprBlocks, origXSIDsFromNew

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
                    nextXSType = self.getNextAvailableXsTypes(excludedXSTypes=modifiedBlockXSTypes.values())[0]
                    modifiedBlockXSTypes[origXSType] = nextXSType
                newXSID = modifiedBlockXSTypes[origXSType] + origXSID[1]  # New XS Type + Old Burnup Group
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

            # copy XS settings to new XS ID
            self.cs[CONF_CROSS_SECTION][newXSID] = copy.deepcopy(self.cs[CONF_CROSS_SECTION][origXSID])
            self.cs[CONF_CROSS_SECTION][newXSID].xsID = newXSID

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
        availableXsTypes = sorted(list(set(_ALLOWABLE_XS_TYPE_LIST).difference(allocatedXSTypes)))
        if len(availableXsTypes) < howMany:
            raise ValueError(
                "There are not enough available xs types. {} have been allocated, {} are available, and "
                "{} have been requested.".format(len(allocatedXSTypes), len(availableXsTypes), howMany)
            )

        # check for lower-case on case-insensitive file system
        if sys.platform.startswith("win"):
            allXSTypes = allocatedXSTypes.union(set(availableXsTypes[:howMany]))
            allCaps = {c.capitalize() for c in allXSTypes}
            if len(allCaps) != len(allXSTypes):
                runLog.warning(
                    "Mixing upper and lower-case XS group types on a Windows system, which is not "
                    "case-sensitive. There is a chance that ARMI could overwrite previously "
                    "generated XS files, which could cause mysterious and/or unpredictable errors."
                )
        return availableXsTypes[:howMany]

    def _getMissingBlueprintBlocks(self, blockCollectionsByXsGroup):
        """
        Gets all blocks with suffixes not yet represented.
        (for blocks in assemblies in the blueprints but not in the core).

        Notes
        -----
        Certain cases (ZPPR validation cases) need to run cross sections for assemblies not in
        the core to get by region cross sections and flux factors.
        """
        missingBlueprintBlocks = []
        blockList = []
        for a in self.r.blueprints.assemblies.values():
            blockList.extend(b for b in a)
        self._updateEnvironmentGroups(blockList)
        for b in blockList:
            if b.getMicroSuffix() not in blockCollectionsByXsGroup:
                b2 = copy.deepcopy(b)
                missingBlueprintBlocks.append(b2)
        return missingBlueprintBlocks

    def makeCrossSectionGroups(self):
        """Make cross section groups for all blocks in reactor and unrepresented blocks from blueprints."""
        bCollectXSGroup = {}  # clear old groups (in case some are no longer existent)
        bCollectXSGroup = self._addXsGroupsFromBlocks(bCollectXSGroup, self.r.core.getBlocks())

        # add blocks that are defined in blueprints, but not in core
        bCollectXSGroup = self._addXsGroupsFromBlocks(bCollectXSGroup, self._getMissingBlueprintBlocks(bCollectXSGroup))
        blockCollectionsByXsGroup = collections.OrderedDict(sorted(bCollectXSGroup.items()))
        return blockCollectionsByXsGroup

    def _getAlternateEnvGroup(self, missingXsType):
        """Get a substitute block to use since there are no blocks with flags for xs gen."""
        for otherXsID in self.representativeBlocks:
            repType, repEnvGroup = otherXsID
            if repType == missingXsType:
                return repEnvGroup

    def _modifyUnrepresentedXSIDs(self, blockCollectionsByXsGroup):
        """
        Adjust the xsID of blocks in the groups that are not represented.

        Try to just adjust the burnup group up to something that is represented
        (can happen to structure in AA when only AB, AC, AD still remain,
        but if some fresh AA happened to be added it might be needed).
        """
        # No blocks in in this ID had a valid representative block flag (such as `fuel` for default),
        # so nothing valid to run lattice physics on...
        for xsID in self._unrepresentedXSIDs:
            missingXsType, _missingEnvGroup = xsID
            nonRepBlocks = blockCollectionsByXsGroup.get(xsID)
            if nonRepBlocks:
                newEnvGroup = self._getAlternateEnvGroup(missingXsType)
                if newEnvGroup:
                    # there were no blocks flagged to xs gen even though there were some not suitable for
                    # generation in the group so can't make XS and use different.
                    runLog.warning(
                        "Changing XSID of {0} blocks from {1} to {2}".format(
                            len(nonRepBlocks), xsID, missingXsType[0] + newEnvGroup
                        )
                    )
                    for b in nonRepBlocks:
                        b.p.envGroup = newEnvGroup
                else:
                    runLog.warning(
                        "No representative blocks with XS type {0} exist in the core. "
                        "There were also no similar blocks to use. "
                        "These XS cannot be generated and must exist in the working "
                        "directory or the run will fail.".format(xsID)
                    )

    def _summarizeGroups(self, blockCollectionsByXsGroup):
        """Summarize current contents of the XS groups."""
        from armi.physics.neutronics.settings import CONF_XS_BLOCK_REPRESENTATION

        runLog.extra("Cross section group manager summary")
        runLog.extra("Averaging performed by `{0}`".format(self.cs[CONF_XS_BLOCK_REPRESENTATION]))
        for xsID, blocks in blockCollectionsByXsGroup.items():
            if blocks:
                xsIDGroup = self._getXsIDGroup(xsID)
                if xsIDGroup == self._REPR_GROUP:
                    reprBlock = self.representativeBlocks.get(xsID)
                    xsSettings = self._initializeXsID(reprBlock.getMicroSuffix())
                    temp = self.avgNucTemperatures[xsID].get(xsSettings.xsTempIsotope, "N/A")
                    runLog.extra(
                        (
                            "XS ID {} contains {:4d} blocks, with avg burnup {} "
                            "and avg fuel temp {}, represented by: {:65s}"
                        ).format(
                            xsID,
                            len(blocks),
                            reprBlock.p.percentBu,
                            temp,
                            reprBlock,
                        )
                    )
                elif xsIDGroup == self._NON_REPR_GROUP:
                    runLog.extra(
                        "XS ID {} contains {:4d} blocks, but no representative block.".format(xsID, len(blocks))
                    )
                elif xsIDGroup == self._PREGEN_GROUP:
                    xsFileNames = [y for _x, y in self._getPregeneratedXsFileLocationData(xsID)]
                    runLog.extra(
                        "XS ID {} contains {:4d} blocks, represented by: {}".format(xsID, len(blocks), xsFileNames)
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

    def disableEnvGroupUpdates(self):
        """
        Turn off updating Env groups based on environment.

        Useful during reactivity coefficient calculations to be consistent with ref. run.

        See Also
        --------
        enableEnvGroupUpdates
        """
        runLog.extra("Environment xs group updating disabled")
        wasEnabled = self._envGroupUpdatesEnabled
        self._envGroupUpdatesEnabled = False
        return wasEnabled

    def enableEnvGroupUpdates(self):
        """
        Turn on updating Env groups based on environment.

        See Also
        --------
        disableEnvGroupUpdates
        """
        runLog.extra("Environment xs group updating enabled")
        self._envGroupUpdatesEnabled = True

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
            an argument will only update the average temperatures of these XS IDs/block collections and will
            result in other XS ID average temperatures not included to be discarded.

        Notes
        -----
        This method does not update any properties of the representative blocks.
        Temperatures are obtained from the BlockCollection class rather than the representative block.
        """
        self.avgNucTemperatures = {}
        blockCollectionsByXsGroup = blockCollectionByXsGroup or self.makeCrossSectionGroups()
        runLog.info(
            "Updating representative block average nuclide temperatures for the following XS IDs: {}".format(
                blockCollectionsByXsGroup.keys()
            )
        )
        for xsID, collection in blockCollectionsByXsGroup.items():
            collection.calcAvgNuclideTemperatures()
            self.avgNucTemperatures[xsID] = collection.avgNucTemperatures
            runLog.extra("XS ID: {}, Collection: {}".format(xsID, collection))


# String constants
MEDIAN_BLOCK_COLLECTION = "Median"
AVERAGE_BLOCK_COLLECTION = "Average"
FLUX_WEIGHTED_AVERAGE_BLOCK_COLLECTION = "FluxWeightedAverage"
SLAB_COMPONENTS_BLOCK_COLLECTION = "ComponentAverage1DSlab"
CYLINDRICAL_COMPONENTS_BLOCK_COLLECTION = "ComponentAverage1DCylinder"
CYLINDRICAL_COMPONENTS_DUCT_HET_BLOCK_COLLECTION = "ComponentAverage1DCylinderDuctHeterogeneous"

# Mapping between block collection string constants and their
# respective block collection classes.
BLOCK_COLLECTIONS = {
    MEDIAN_BLOCK_COLLECTION: MedianBlockCollection,
    AVERAGE_BLOCK_COLLECTION: AverageBlockCollection,
    FLUX_WEIGHTED_AVERAGE_BLOCK_COLLECTION: FluxWeightedAverageBlockCollection,
    SLAB_COMPONENTS_BLOCK_COLLECTION: SlabComponentsAverageBlockCollection,
    CYLINDRICAL_COMPONENTS_BLOCK_COLLECTION: CylindricalComponentsAverageBlockCollection,
    CYLINDRICAL_COMPONENTS_DUCT_HET_BLOCK_COLLECTION: CylindricalComponentsDuctHetAverageBlockCollection,
}


def blockCollectionFactory(xsSettings, allNuclidesInProblem):
    """Build a block collection based on user settings and input."""
    blockRepresentation = xsSettings.blockRepresentation
    if (blockRepresentation == CYLINDRICAL_COMPONENTS_BLOCK_COLLECTION) and xsSettings.ductHeterogeneous:
        blockRepresentation = CYLINDRICAL_COMPONENTS_DUCT_HET_BLOCK_COLLECTION
    validBlockTypes = xsSettings.validBlockTypes
    averageByComponent = xsSettings.averageByComponent
    return BLOCK_COLLECTIONS[blockRepresentation](
        allNuclidesInProblem,
        validBlockTypes=validBlockTypes,
        averageByComponent=averageByComponent,
    )
