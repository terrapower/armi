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
from armi.nucDirectory import nuclideBases
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
        self._globalLFPs = lumpedFissionProduct.lumpedFissionProductFactory(self.cs)
        # Boolean that tracks if `setAllBlockLFPs` was called previously.
        self._initialized = False

    @property
    def _explicitFissionProducts(self):
        return self.cs["fpModel"] == "explicitFissionProducts"

    @property
    def _useGlobalLFPs(self):
        if self.cs["makeAllBlockLFPsIndependent"] or self._explicitFissionProducts:
            return False
        else:
            return True

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
        if blockType is None and self._explicitFissionProducts:
            raise ValueError(
                f"Expicit fission products model is not compatible with the MCNP interface."
            )
        return blockType

    def interactBOL(self):
        interfaces.Interface.interactBOL(self)
        self.setAllBlockLFPs()

    def setAllBlockLFPs(self):
        """
        Sets all the block lumped fission products attributes and adds fission products
        to each block if `self._explicitFissionProducts` is set to True.
        See Also
        --------
        armi.reactor.components.Component.setLumpedFissionProducts
        """
        for b in self.r.core.getBlocks(self._fissionProductBlockType, includeAll=True):
            if self._useGlobalLFPs:
                b.setLumpedFissionProducts(self.getGlobalLumpedFissionProducts())
            else:
                lfps = self.getGlobalLumpedFissionProducts()
                if lfps is None:
                    b.setLumpedFissionProducts(None)
                else:
                    independentLFPs = self.getGlobalLumpedFissionProducts().duplicate()
                    b.setLumpedFissionProducts(independentLFPs)

            # Initialize the fission products explicitly on the block component
            # that matches the `self._fissionProductBlockType` if it exists.
            if self._explicitFissionProducts and not self._initialized:
                targetComponent = b.getComponent(self._fissionProductBlockType)
                if not targetComponent:
                    continue
                ndens = targetComponent.getNumberDensities()
                updatedNDens = {}
                for nuc in self.r.blueprints.allNuclidesInProblem:
                    if nuc in ndens:
                        continue
                    updatedNDens[nuc] = 0.0
                targetComponent.updateNumberDensities(updatedNDens)
        self._initialized = True

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

    def getAllFissionProductNames(self):
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

        return fissionProductNames

    def removeFissionGasesFromBlocks(self, gasRemovalFractions: dict):
        """
        Removes the fission gases from each of the blocks in the core.

        Parameters
        ----------
        gasRemovalFractions : dict
            Dictionary with block objects as the keys and the fraction
            of gaseous fission products to remove.

        Notes
        -----
        The current implementation will update the number density vector
        of each of the blocks and the gaseous fission products are not
        moved or displaced to another area in the core.
        """
        
        def _getGaseousFissionProductNumberDensities(block, lfp):
            """Look into a single lumped fission product object and pull out just the gaseous atom number densities."""
            numberDensities = {}
            for nuc in lfp.keys():
                nb = nuclideBases.byName[nuc]
                if not lumpedFissionProduct.isGas(nb):
                    continue
                yld = lfp[nuc]
                ndens = block.getNumberDensity(lfp.name)
                numberDensities[nuc] = ndens * yld
            return numberDensities
                
        
        runLog.info(f"Removing the gaseous fission products from the core.")
        if not isinstance(gasRemovalFractions, dict):
            raise TypeError(f"The gas removal fractions input is not a dictionary.")

        if self._explicitFissionProducts:
            for b in self.r.core.getBlocks():
                if b not in gasRemovalFractions:
                    continue
                updatedNumberDensities = {}
                removedFraction = gasRemovalFractions[b]
                remainingFraction = 1.0 - removedFraction
                for nuc, val in b.getNumberDensities().items():
                    nb = nuclideBases.byName[nuc]
                    if lumpedFissionProduct.isGas(nb):
                        val = remainingFraction * val
                    updatedNumberDensities[nuc] = val
                b.updateNumberDensities(updatedNumberDensities)
                
        else:
            avgGasReleased = {}
            totalWeight = {}
            for block in self.r.core.getBlocks():
                lfpCollection = block.getLumpedFissionProductCollection()
                # Skip this block if there is no lumped fission product
                # collection or this block is not in the dictionary
                # of gas removal fractions.
                if lfpCollection is None or b not in gasRemovalFractions:
                    continue
                
                
                numberDensities = block.getNumberDensities()
                for lfp in lfpCollection:
                    ndens = _getGaseousFissionProductNumberDensities(block, lfp)
                    removedFraction = gasRemovalFractions[b]
                    
                    # If the lumped fission products are global then we are going
                    # release the average across all the blocks in the core and these
                    # this data is collected iteratively.
                    if self._useGlobalLFPs: 
                        avgGasReleased[lfp] += sum(ndens.values()) * removedFraction
                        totalWeight[lfp] += block.getVolume() * (block.p.flux or 1.0)
                        
                    # Otherwise, if the lumped fission products are not global
                    # go ahead of make the change now.
                    else:
                        updatedLFPNumberDensity = numberDensities[lfp.name] - sum(ndens.values()) * removedFraction
                        numberDensities.update({lfp.name: updatedLFPNumberDensity})
                        block.setNumberDensities(numberDensities)
    
            # adjust global lumps if they exist.
            if self._useGlobalLFPs and totalWeight:
                for b in self.r.core.getBlocks():
                    lfpCollection = block.getLumpedFissionProductCollection()
                    # Skip this block if there is no lumped fission product
                    # collection or this block is not in the dictionary
                    # of gas removal fractions.
                    if lfpCollection is None or b not in gasRemovalFractions:
                        continue
                    
                    for lfp in lfpCollection:
                        updatedLFPNumberDensity = numberDensities[lfp.name] - (avgGasReleased[lfp] / totalWeight[lfp])
                        numberDensities.update({lfp.name: updatedLFPNumberDensity})
                        block.setNumberDensities(numberDensities)
                    
                