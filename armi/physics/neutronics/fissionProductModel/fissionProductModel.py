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
Fission product model

All blocks have a _lumpedFissionProducts attribute that points to a
:py:class:`~armi.physics.neutronics.fissionProductModel.lumpedFissionProduct.LumpedFissionProductCollection`.
The LFP collection may be global or each block may have its own.
The collection may have multiple LFPs from various parents or just one single one.
This module is the shepherd of the block's _lumpedFissionProducts attribute.
All other modules can just assume there's a LFP collection and use it as needed.


Examples
--------

from armi.physics.neutronics.fissionProductModel import fissionProductModel
fpInterface = fissionProductModel.FissionProductModel()
lfp = fpInterface.getGlobalLumpedFissionProducts()
lfp['LFP35']
lfp35 = lfp['LFP35']
lfp35.printDensities(0.05)
lfp35.values()
allFPs = [(fpY, fpNuc) for (fpNuc,fpY) in lfp35.items()]
allFPs.sort()
lfp35.keys()
"""

from armi import runLog
from armi import interfaces
from armi.reactor.flags import Flags
from armi.physics.neutronics.fissionProductModel import lumpedFissionProduct

NUM_FISSION_PRODUCTS_PER_LFP = 2.0

ORDER = interfaces.STACK_ORDER.AFTER + interfaces.STACK_ORDER.PREPROCESSING


def describeInterfaces(_cs):
    """Function for exposing interface(s) to other code"""

    return (FissionProductModel, {})


class FissionProductModel(interfaces.Interface):
    """
    Code interface that coordinates the fission product model on the reactor.
    """

    name = "fissionProducts"

    def __init__(self, r, cs):
        interfaces.Interface.__init__(self, r, cs)
        self._globalLFPs = None
        self._globalLFPs = lumpedFissionProduct.lumpedFissionProductFactory(self.cs)
        self.fissionProductNames = []

    @property
    def _useGlobalLFPs(self):
        return False if self.cs["makeAllBlockLFPsIndependent"] else True

    @property
    def _fissionProductBlockType(self):
        """
        Set the block type that the fission products will be applied to.

        Notes
        -----
        Some Monte Carlo codes require all nuclides to be consistent in all
        materials when assemblies are shuffled.  This requires that fission
        products be consistent across all blocks, even if fission products are
        not generated when the block is depleted.
        """
        blockType = None if self.getInterface("mcnp") is not None else Flags.FUEL
        return blockType

    def interactBOL(self):
        interfaces.Interface.interactBOL(self)
        self.setAllBlockLFPs()

    def setAllBlockLFPs(self, blockType=None, setMaterialsLFP=False):
        """
        Set ALL the block _lumpedFissionProduct attributes

        Can set them to global or turns on independent block-level LFPs if
        requested

        sets block._lumpedFissionProducts to something other than the global.

        Parameters
        ----------
        blockType : Flags, optional
            this is the type of block that the global lumped fission product is
            being applied to. If this is not provided it will get the default
            behavior from ``self._fissionProductBlockType``.

        setMaterialsLFP : bool, optional
            this is a flag to tell the method whether or not to try to apply
            the global lumped fission product to the component and thereby
            material -- this is only compatable with
            LumpedFissionProductCompatableMaterial

        Examples
        --------
        self.setAllBlockLFPs(blockType='fuel')
        will apply the global lumped fission product or independent LFPs to only
        fuel type blocks

        See Also
        --------
        armi.materials.lumpedFissionProductCompatableMaterial.LumpedFissionProductCompatableMaterial
        armi.reactor.components.Component.setLumpedFissionProducts
        armi.physics.neutronics.fissionProductModel.fissionProductModel.FissionProductModel.setAllBlockLFPs
        """
        blockType = blockType or self._fissionProductBlockType
        for b in self.r.core.getBlocks(blockType, includeAll=True):
            if self._useGlobalLFPs:
                b.setLumpedFissionProducts(self.getGlobalLumpedFissionProducts())
            else:
                independentLFPs = self.getGlobalLumpedFissionProducts().duplicate()
                b.setLumpedFissionProducts(independentLFPs)

        # use two loops to pass setting the material LFPs
        if setMaterialsLFP:
            for b in self.r.core.getBlocks(blockType, includeAll=True):
                if self._useGlobalLFPs:
                    b.setChildrenLumpedFissionProducts(
                        self.getGlobalLumpedFissionProducts()
                    )
                else:
                    independentLFPs = self.getGlobalLumpedFissionProducts().duplicate()
                    b.setChildrenLumpedFissionProducts(independentLFPs)

    def getGlobalLumpedFissionProducts(self):
        r"""
        Lookup the detailed fission product object associated with a xsType and burnup group.

        See Also
        --------
        armi.physics.neutronics.isotopicDepletion.depletion.DepletionInterface.buildFissionProducts
        armi.reactor.blocks.Block.getLumpedFissionProductCollection : same thing, but block-level compatible. Use this
        """
        return self._globalLFPs

    def setGlobalLumpedFissionProducts(self, lfps):
        r"""
        Lookup the detailed fission product object associated with a xsType and burnup group.

        See Also
        --------
        terrapower.physics.neutronics.depletion.depletion.DepletionInterface.buildFissionProducts
        armi.reactor.blocks.Block.getLumpedFissionProductCollection : same thing, but block-level compatible. Use this
        """

        self._globalLFPs = lfps

    def interactBOC(self, cycle=None):
        """
        Update block groups and fg removal

        Cross sections update at BOC, so we must prepare LFPs at BOC.
        """
        self.setAllBlockLFPs()

    def interactEveryNode(self, _cycle, _node):
        self.updateFissionGasRemovalFractions()

    def interactDistributeState(self):
        self.setAllBlockLFPs()

    def _getAllFissionProductNames(self):
        """
        Find all fission product names in the problem

        Considers all LFP collections, whether they be global,
        block-level, or a mix of these.

       sets fissionProductNames, a list of nuclide names of all the
       fission products
        """
        runLog.debug("  Gathering all possible FPs")
        fissionProductNames = []
        lfpCollections = []
        # get all possible lfp collections (global + block-level)
        for b in self.r.core.getBlocks(Flags.FUEL, includeAll=True):
            lfpCollection = b.getLumpedFissionProductCollection()
            if lfpCollection and lfpCollection not in lfpCollections:
                lfpCollections.append(lfpCollection)

        # get all possible FP names in each LFP collection
        for lfpCollection in lfpCollections:
            for fpName in lfpCollection.getAllFissionProductNames():
                if fpName not in fissionProductNames:
                    fissionProductNames.append(fpName)

        self.fissionProductNames = fissionProductNames

    def _cacheLFPDensities(self, blockList):
        # pass 2: Cache all LFP densities for all blocks (so they aren't read
        # for each FP)
        runLog.debug("  Caching LFP densities of all blocks")
        lfpDensities = {}
        for b in blockList:
            for lfpName in self._globalLFPs:
                lfpDensities[lfpName, b.getName()] = b.getNumberDensity(lfpName)
        return lfpDensities

    def updateFissionGasRemovalFractions(self):
        """
        Synchronize fission gas removal fractions of all LFP objects with the reactor state.

        The block parameter ``fgRemoval`` is adjusted by fuel performance
        modules and is applied here.

        If the ``makeAllBlockLFPsIndependent`` setting is not activated
        (default), the global lump gets the flux-weighted average of all blocks.
        Otherwise, each block gets its own fission gas release fraction applied
        to its individual LFPs. For MCNP restart cases, it is recommended to
        activate the ``makeAllBlockLFPsIndependent`` setting.

        Notes
        -----
        The CrossSectionGroupManager does this for each XSG individually for
        lattice physics, but it's important to keep these up to date as well for
        anything else that may be interested in fission product information
        (e.g. MCNP).

        See Also
        --------
        armi.physics.neutronics.crossSectionGroupManager.AverageBlockCollection.getRepresentativeBlock

        """
        runLog.extra("Updating lumped fission product gas removal fractions")
        avgGasReleased = 0.0
        totalWeight = 0.0
        for block in self.r.core.getBlocks(Flags.FUEL):
            if self._useGlobalLFPs:
                # add to average for globals
                weight = block.getVolume() * (block.p.flux or 1.0)
                avgGasReleased += block.p.gasReleaseFraction * weight
                totalWeight += weight
            else:
                # set individually
                block.getLumpedFissionProductCollection().setGasRemovedFrac(
                    block.p.gasReleaseFraction
                )

        # adjust global lumps if they exist.
        if avgGasReleased:
            self.getGlobalLumpedFissionProducts().setGasRemovedFrac(
                avgGasReleased / totalWeight
            )
