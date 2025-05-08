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
This module contains the implementation of the ``FissionProductModel`` interface.


This ``FissionProductModel`` class implements the management of fission products within 
the reactor core and can be extended to support more general applications. Currently, the 
fission product model supports explicit modeling of fission products in each of the 
blocks/components, independent management of lumped fission products for each
blocks/components within the core, or global management of lumped fission products
where the fission products between all blocks/components are shared and are modified
together.

Within the framework, there is a coupling between the management of the fission products
through this model to neutronics evaluations of flux and depletion calculations. 

When using a Monte Carlo solver, such as MCNP (i.e., there is an interface that is attached
to the operator that has a name of "mcnp"), the fission products will always be treated
independently and fission products (either explicit or lumped) will be added to all 
blocks/components in the core. The reason for this is that Monte Carlo solvers, like MCNP, 
may implement their own coupling between flux and depletion evaluations and having the 
initialization of these fission products in each block/component independently will
allow that solver to manage the inventory over time.

When determining which fission product model to use (either explicit or lumped) it is
important to consider which cross section data is available to the flux and/or depletion
solvers, and what level of fidelity is required for the analysis. This is where decisions 
as a developer/user need to be made, and the implementation of this specific model may 
not be, in general, accurate for any reactor system. It is dependent on which plugins 
are implemented and the requirements of the individual flux/depletion solver.

Lumped fission products are generally useful for fast reactor applications, especially
in fuel cycle calculations or scoping evaluations where the tracking of the detailed
nuclide inventory would not have substantial impacts on core reactivity predictions.
This is typically done by collapsing all fission products into lumped nuclides, like
``LFP35``, ``LFP38``, ``LFP39``, ``LFP40``, and ``LFP41``. This is the implementation
in the framework, which is discussed a bit more in the ``fpModel`` setting. These
lumped fission products are separated into different bins that represent the fission
product yields from U-235, U-238, Pu-239, Pu-240, and Pu-241/Am-241, respectively. The
exact binning of which fission events from which target nuclides is specified by the
``burn-chain.yaml`` file, which can be modified by a user/developer. When selecting this
modeling option, the blocks/components will have these ``LFP`` nuclides in the number
density dictionaries. The key thing here is that these lumped nuclides do not exist
in nature and therefore do not have nuclear data directly available in cross section
evaluations, like ENDF/B. If the user wishes to consider these nuclides in the flux/depletion
evaluations, then cross sections for these ``LFP`` nuclides will need to be prepared. Generally
speaking, the the ``crossSectionGroupManager`` and the  ``latticePhysicsInterface`` could be
used to implement this for cross section generation codes, like NJOY, CASMO, MC2-3, Serpent,
etc.

.. warning::
    
    The lumped fission product model and the ``burn-chain.yaml`` data may not be directly
    applicable to light water reactor systems, especially if there are strong reactivity 
    impacts with fission products like ``Xe`` and ``Sm`` that need to be tracked independently.
    A user/developer may update the ``referenceFissionProducts.dat`` data file to exclude
    these important nuclides from the lumped fission product models if need be, but this
    would also require updating the ``burn-chain.yaml`` file as well as updating the
    ``nuclideFlags`` specification within the reactor blueprints input.

A further simplified option for lumped fission product treatment that is available is to
treat all fission products explicitly as ``Mo-99``. This is not guaranteed to be an accurate
treatment of the fission products from a reactivity/depletion perspective, but it is 
available for quick scoping evaluations and model building.

Finally, the explicit fission product modeling aims to include as many nuclides on the 
blocks/components as the user wishes to consider, but the nuclides that are modeled
must be compatible with the plugins that are implemented for the application. When using this 
option, the user should look to set the ``fpModelLibrary`` setting. 

    - If this setting is not set, then it is expected that the user will need to manually add 
      all nuclides to the ``nuclideFlags`` section of the reactor core blueprints. 

    - If the ``fpModelLibrary`` is selected then this will automatically add to the 
      ``nuclideFlags`` input using :py:func:`isotopicOptions.autoUpdateNuclideFlags` 
      and this class will initialize all added nuclides to have zero number densities.

.. warning::

    The explicit fission product model is being implemented with the vision of using
    generating multi-group cross sections for nuclides that are added with the
    ``fpModelLibrary`` setting with follow-on depletion calculations that will be managed by
    a detailed depletion solver, like ORIGEN. There are many caveats to how this model
    is initialized and may not be an out-of-the-box general solution.
"""

from armi import interfaces, runLog
from armi.physics.neutronics.fissionProductModel import lumpedFissionProduct
from armi.physics.neutronics.fissionProductModel.fissionProductModelSettings import (
    CONF_FP_MODEL,
    CONF_MAKE_ALL_BLOCK_LFPS_INDEPENDENT,
)
from armi.reactor.flags import Flags

NUM_FISSION_PRODUCTS_PER_LFP = 2.0

ORDER = interfaces.STACK_ORDER.AFTER + interfaces.STACK_ORDER.PREPROCESSING


def describeInterfaces(_cs):
    """Function for exposing interface(s) to other code."""
    return (FissionProductModel, {})


class FissionProductModel(interfaces.Interface):
    """Coordinates the fission product model on the reactor."""

    name = "fissionProducts"

    def __init__(self, r, cs):
        interfaces.Interface.__init__(self, r, cs)
        self._globalLFPs = lumpedFissionProduct.lumpedFissionProductFactory(self.cs)

    @property
    def _explicitFissionProducts(self):
        return self.cs[CONF_FP_MODEL] == "explicitFissionProducts"

    @property
    def _useGlobalLFPs(self):
        return not (
            self.cs[CONF_MAKE_ALL_BLOCK_LFPS_INDEPENDENT]
            or self._explicitFissionProducts
        )

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
        return None if self.getInterface("mcnp") is not None else Flags.FUEL

    def interactBOL(self):
        interfaces.Interface.interactBOL(self)
        if self._explicitFissionProducts:
            self.setAllComponentFissionProducts()
        else:
            self.setAllBlockLFPs()

    def setAllComponentFissionProducts(self):
        """
        Initialize all nuclides for each ``DEPLETABLE`` component in the core.

        Notes
        -----
        This should be called when explicit fission product modeling is enabled to
        ensure that all isotopes are initialized on the depletable components within
        the reactor data model so that there is some density as a starting point.

        When explicit fission products are enabled and the user has not already included
        all fission products in the blueprints (in ``nuclideFlags``), the ``fpModelLibrary`` setting is used
        to autofill all the nuclides in a given library into the ``blueprints.allNuclidesInProblem``
        list. All nuclides that were not manually initialized by the user are added to
        the ``DEPLETABLE`` components throughout every block in the core.

        The ``DEPLETABLE`` flag is based on the user adding this explicitly in the blueprints,
        or is based on the user setting a nuclide to ``burn: true`` in the blueprint ``nuclideFlags``.

        See Also
        --------
        armi.reactor.blueprints.isotopicOptions.autoUpdateNuclideFlags
        armi.reactor.blueprints.isotopicOptions.getAllNuclideBasesByLibrary
        """
        for b in self.r.core.getBlocks(includeAll=True):
            b.setLumpedFissionProducts(None)
            for c in b.getComponents(Flags.DEPLETABLE):
                # Add all isotopes in problem at 0.0 density
                updatedNDens = c.getNumberDensities()
                # self.r.blueprints.allNuclidesInProblem contains ~everything in ENDF if _explicitFissionProducts
                for nuc in self.r.blueprints.allNuclidesInProblem:
                    if nuc in updatedNDens:
                        continue
                    updatedNDens[nuc] = 0.0
                c.updateNumberDensities(updatedNDens)

    def setAllBlockLFPs(self):
        """
        Sets all the block lumped fission products attributes.

        See Also
        --------
        armi.reactor.components.Component.setLumpedFissionProducts
        """
        for b in self.r.core.getBlocks(self._fissionProductBlockType, includeAll=True):
            if self._useGlobalLFPs:
                b.setLumpedFissionProducts(self.getGlobalLumpedFissionProducts())
            else:
                independentLFPs = self.getGlobalLumpedFissionProducts().duplicate()
                b.setLumpedFissionProducts(independentLFPs)

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
        if self._explicitFissionProducts:
            self.setAllComponentFissionProducts()
        else:
            self.setAllBlockLFPs()

    def interactDistributeState(self):
        if self._explicitFissionProducts:
            self.setAllComponentFissionProducts()
        else:
            self.setAllBlockLFPs()

    def getAllFissionProductNames(self):
        """
        Find all fission product names from the lumped fission product collection.

        Notes
        -----
        This considers all LFP collections, whether they are global, block-level,
        or a mix of these.
        """
        runLog.debug("Gathering all possible fission products that are modeled.")
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

    def removeFissionGasesFromBlocks(self):
        """
        Return False to indicate that no fission products are being removed.

        Notes
        -----
        This should be implemented on an application-specific model.
        """
        runLog.warning(f"Fission gas removal is not implemented in {self}")
        return False
