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
Converts reactor with arbitrary axial meshing (e.g. multiple assemblies with different
axial meshes) to one with a global uniform axial mesh.

Useful for preparing inputs for physics codes that require structured meshes
from a more flexible ARMI reactor mesh.

This is implemented generically but includes a concrete subclass for
neutronics-specific parameters. This is used for build input files
for codes like DIF3D which require axially uniform meshes.

Requirements
------------
1. Build an average reactor with aligned axial meshes from a reactor with arbitrarily
   unaligned axial meshes in a way that conserves nuclide mass
2. Translate state information computed on the uniform mesh back to the unaligned mesh.
3. For neutronics cases, all neutronics-related block params should be translated, as
   well as the multigroup real and adjoint flux.


.. warning: This procedure can cause numerical diffusion in some cases. For example, 
    if a control rod tip block has a large coolant block below it, things like peak
    absorption rate can get lost into it. We recalculate some but not all 
    reaction rates in the re-mapping process based on a flux remapping. To avoid this,
    finer meshes will help. Always perform mesh sensitivity studies to ensure appropriate
    convergence for your needs.


Examples
--------
converter = uniformMesh.NeutronicsUniformMeshConverter()
converter.convert(reactor)
uniformReactor = converter.convReactor
# do calcs, then:
converter.applyStateToOriginal()

The mesh mapping happens as described in the figure:

.. figure:: /.static/axial_homogenization.png

"""
import re
import glob
import copy
import collections
from timeit import default_timer as timer

import numpy

import armi
from armi import runLog
from armi import settings
from armi.utils.mathematics import average1DWithinTolerance
from armi.utils import iterables
from armi.utils import plotting
from armi.reactor import grids
from armi.reactor.flags import Flags
from armi.reactor.converters.geometryConverters import GeometryConverter
from armi.reactor import parameters
from armi.reactor.reactors import Reactor

# unfortunate physics coupling, but still in the framework
from armi.physics.neutronics.globalFlux import globalFluxInterface


class UniformMeshGeometryConverter(GeometryConverter):
    """Build uniform mesh version of the source reactor"""

    def __init__(self, cs=None):
        GeometryConverter.__init__(self, cs)
        self._uniformMesh = None
        self.blockDetailedAxialExpansionParamNames = []
        self.reactorParamNames = []

        # These dictionaries represent back-up data from the source reactor
        # that can be recovered if the data is not being brought back from
        # the uniform mesh reactor when ``applyStateToOriginal`` to called.
        # This prevents clearing out data on the original reactor that should
        # be preserved since no changes were applied.
        self._cachedReactorCoreParamData = {}
        self._cachedBlockParamData = collections.defaultdict(dict)

    def convert(self, r=None):
        """Create a new reactor with a uniform mesh."""
        runLog.extra("Building copy of {} with a uniform axial mesh".format(r))
        completeStartTime = timer()
        self._sourceReactor = r
        self.convReactor = self.initNewReactor(r)
        self._setParamsToUpdate()
        self._computeAverageAxialMesh()
        self._buildAllUniformAssemblies()

        # Clear the state of the converted reactor to ensure there is
        # no data from the creation of a new reactor core
        self._clearStateOnReactor(self.convReactor, cache=False)
        self._mapStateFromReactorToOther(self._sourceReactor, self.convReactor)
        self.convReactor.core.updateAxialMesh()

        self._newAssembliesAdded = self.convReactor.core.getAssemblies()

        self._checkConversion()
        completeEndTime = timer()
        runLog.extra(
            f"Reactor core conversion time: {completeEndTime-completeStartTime} seconds"
        )

    def reset(self):
        self.blockDetailedAxialExpansionParamNames = []
        self.reactorParamNames = []
        self._cachedReactorCoreParamData = {}
        self._cachedBlockParamData = collections.defaultdict(dict)
        super().reset()

    def _checkConversion(self):
        """Perform checks to ensure conversion occurred properly."""

    @staticmethod
    def initNewReactor(sourceReactor):
        """Build a new, yet empty, reactor with the same settings as sourceReactor

        Parameters
        ----------
        sourceReactor : :py:class:`Reactor <armi.reactor.reactors.Reactor>` object.
            original reactor to be copied
        """
        # developer note: deepcopy on the blueprint object ensures that all relevant blueprints
        # attributes are set. Simply calling blueprints.loadFromCs() just initializes
        # a blueprints object and may not set all necessary attributes. E.g., some
        # attributes are set when assemblies are added in coreDesign.construct(), however
        # since we skip that here, they never get set; therefore the need for the deepcopy.
        bp = copy.deepcopy(sourceReactor.blueprints)
        newReactor = Reactor(sourceReactor.name, bp)
        coreDesign = bp.systemDesigns["core"]

        # The source reactor may not have an operator available. This can occur
        # when a different geometry converter is chained together with this. For
        # instance, using the `HexToRZThetaConverter`, the converted reactor
        # does not have an operator attached. In this case, we still need some
        # settings to construct the new core.
        if sourceReactor.o is None:
            cs = settings.getMasterCs()
        else:
            cs = sourceReactor.o.cs

        coreDesign.construct(cs, bp, newReactor, loadAssems=False)
        newReactor.core.lib = sourceReactor.core.lib
        newReactor.core.setPitchUniform(sourceReactor.core.getAssemblyPitch())

        # check if the sourceReactor has been modified from the blueprints
        if sourceReactor.core.isFullCore and not newReactor.core.isFullCore:
            _geometryConverter = newReactor.core.growToFullCore(sourceReactor.o.cs)

        return newReactor

    def _computeAverageAxialMesh(self):
        """
        Computes an average axial mesh based on the first fuel assembly
        """
        src = self._sourceReactor
        refAssem = src.core.refAssem
        refNumPoints = (
            len(src.core.findAllAxialMeshPoints([refAssem], applySubMesh=True)) - 1
        )  # pop off zero
        # skip the first value of the mesh (0.0)
        allMeshes = []
        for a in src.core:
            aMesh = src.core.findAllAxialMeshPoints([a], applySubMesh=True)[1:]
            if len(aMesh) == refNumPoints:
                allMeshes.append(aMesh)
        self._uniformMesh = average1DWithinTolerance(numpy.array(allMeshes))

    @staticmethod
    def _createNewAssembly(sourceAssembly):
        a = sourceAssembly.__class__(sourceAssembly.getType())
        a.spatialGrid = grids.axialUnitGrid(len(sourceAssembly))
        a.setName(sourceAssembly.getName())
        return a

    @staticmethod
    def makeAssemWithUniformMesh(sourceAssem, newMesh):
        """
        Build new assembly based on a source assembly but apply the uniform mesh.

        The new assemblies must have appropriately mapped number densities as
        input for a neutronics solve. They must also have other relevant
        state parameters for follow-on steps. Thus, this maps many parameters
        from the ARMI mesh to the uniform mesh.

        See Also
        --------
        applyStateToOriginal : basically the reverse on the way out.
        """
        newAssem = UniformMeshGeometryConverter._createNewAssembly(sourceAssem)
        runLog.debug(f"Creating a uniform mesh of {newAssem}")
        bottom = 0.0

        for topMeshPoint in newMesh:
            overlappingBlockInfo = sourceAssem.getBlocksBetweenElevations(
                bottom, topMeshPoint
            )
            # This is not expected to occur given that the assembly mesh is consistent with
            # the blocks within it, but this is added for defensive programming and to
            # highlight a developer issue.
            if not overlappingBlockInfo:
                raise ValueError(
                    f"No blocks found between {bottom:.3f} and {topMeshPoint:.3f} in {sourceAssem}. "
                    f"This is a major bug that should be reported to the developers."
                )

            # Iterate over the blocks that are within this region and
            # select one as a "source" for determining which cross section
            # type to use. This uses the following rules:
            #     1. Determine the total height corresponding to each XS type that
            #     appears for blocks with FUEL or CONTROL flags in this domain.
            #     2. Determine the single XS type that represents the largest fraction
            #     of the total height of FUEL or CONTROL cross sections.
            #     3. Use the first block of the majority XS type as the representative block.
            typeHeight = collections.defaultdict(float)
            blocks = [b for b, _h in overlappingBlockInfo]
            for b, h in overlappingBlockInfo:
                if b.hasFlags([Flags.FUEL, Flags.CONTROL]):
                    typeHeight[b.p.xsType] += h

            sourceBlock = None
            # xsType is the one with the majority of overlap
            if len(typeHeight) > 0:
                xsType = next(
                    k for k, v in typeHeight.items() if v == max(typeHeight.values())
                )
                for b in blocks:
                    if b.hasFlags([Flags.FUEL, Flags.CONTROL]):
                        if b.p.xsType == xsType:
                            sourceBlock = b
                            break

            if len(typeHeight) > 1:
                if sourceBlock:
                    totalHeight = sum(typeHeight.values())
                    runLog.extra(
                        f"Multiple XS types exist between {bottom} and {topMeshPoint}. "
                        f"Using the XS type from the largest region, {xsType}"
                    )
                    for xs, h in typeHeight.items():
                        heightFrac = h / totalHeight
                        runLog.extra(f"XSType {xs}: {heightFrac:.4f}")

            # If no blocks meet the FUEL or CONTROL criteria above, or there is only one
            # XS type present, just select the first block as the source block and use
            # its cross section type.
            if sourceBlock is None:
                sourceBlock = blocks[0]
                xsType = blocks[0].p.xsType

            block = copy.deepcopy(sourceBlock)
            block.p.xsType = xsType
            block.setHeight(topMeshPoint - bottom)
            block.p.axMesh = 1
            _setNumberDensitiesFromOverlaps(block, overlappingBlockInfo)
            newAssem.add(block)
            bottom = topMeshPoint

        newAssem.reestablishBlockOrder()
        newAssem.calculateZCoords()
        return newAssem

    def _buildAllUniformAssemblies(self):
        """
        Loop through each new block for each mesh point and apply conservation of atoms.
        We use the submesh and allow blocks to be as small as the smallest submesh to
        avoid unnecessarily diffusing small blocks into huge ones (e.g. control blocks
        into plenum).
        """
        runLog.debug(
            f"Creating new assemblies from {self._sourceReactor.core} "
            f"with a uniform mesh of {self._uniformMesh}"
        )
        for sourceAssem in self._sourceReactor.core:
            newAssem = self.makeAssemWithUniformMesh(sourceAssem, self._uniformMesh)
            src = sourceAssem.spatialLocator
            newLoc = self.convReactor.core.spatialGrid[src.i, src.j, 0]
            self.convReactor.core.add(newAssem, newLoc)

    def plotConvertedReactor(self):
        bpAssems = list(self.convReactor.blueprints.assemblies.values())
        assemsToPlot = []
        for bpAssem in bpAssems:
            coreAssems = self.convReactor.core.getAssemblies(bpAssem.p.flags)
            if not coreAssems:
                continue
            assemsToPlot.append(coreAssems[0])

        # Obtain the plot numbering based on the existing files so that existing plots
        # are not overwritten.
        start = 0
        existingFiles = glob.glob(
            f"{self.convReactor.core.name}AssemblyTypes" + "*" + ".png"
        )
        # This loops over the existing files for the assembly types outputs
        # and makes a unique integer value so that plots are not overwritten. The
        # regular expression here captures the first integer as AssemblyTypesX and
        # then ensures that the numbering in the next enumeration below is 1 above that.
        for f in existingFiles:
            newStart = int(re.search(r"\d+", f).group())
            if newStart > start:
                start = newStart
        for plotNum, assemBatch in enumerate(
            iterables.chunk(assemsToPlot, 6), start=start + 1
        ):
            assemPlotName = f"{self.convReactor.core.name}AssemblyTypes{plotNum}-rank{armi.MPI_RANK}.png"
            plotting.plotAssemblyTypes(
                self.convReactor.blueprints,
                assemPlotName,
                assemBatch,
                maxAssems=6,
                showBlockAxMesh=True,
            )

    def _setParamsToUpdate(self):
        """Gather a list of parameters that will be mapped between reactors."""

    def _clearStateOnReactor(self, reactor, cache):
        """
        Delete existing state that will be updated so they don't increment.

        The summations should start at zero but will happen for all overlaps.
        """
        runLog.debug("Clearing params from source reactor that will be converted.")
        for rp in self.reactorParamNames:
            if cache:
                self._cachedReactorCoreParamData[rp] = reactor.core.p[rp]
            reactor.core.p[rp] = 0.0

        for b in reactor.core.getBlocks():
            for bp in self.blockDetailedAxialExpansionParamNames:
                if cache:
                    self._cachedBlockParamData[b][bp] = b.p[bp]
                b.p[bp] = 0.0

    def applyStateToOriginal(self):
        """
        Now that state is computed on the uniform mesh, map it back to ARMI mesh.
        """
        runLog.extra(
            f"Applying uniform neutronics mesh results from {self.convReactor} to ARMI mesh on {self._sourceReactor}"
        )
        completeStartTime = timer()

        # Clear the state of the original source reactor to ensure that
        # a clean mapping between the converted reactor for data that has been
        # changed. In this case, we cache the original reactor's data so that
        # after the mapping has been applied, we can recover data from any
        # parameters that did not change.
        self._cachedReactorCoreParamData = {}
        self._cachedBlockParamData = collections.defaultdict(dict)
        self._clearStateOnReactor(self._sourceReactor, cache=True)
        self._mapStateFromReactorToOther(self.convReactor, self._sourceReactor)
        self._sourceReactor.core.lib = self.convReactor.core.lib
        completeEndTime = timer()
        runLog.extra(
            f"Parameter remapping time: {completeEndTime-completeStartTime} seconds"
        )
        self.reset()

    def _mapStateFromReactorToOther(self, sourceReactor, destReactor):
        """
        Map parameters from one reactor to another.

        Used for preparing and uniform reactor as well as for mapping its results
        back to the original reactor.
        """


class NeutronicsUniformMeshConverter(UniformMeshGeometryConverter):
    """
    A uniform mesh converter that specifically maps neutronics parameters.

    This is useful for codes like DIF3D.

    Notes
    -----
    If a case runs where two mesh conversions happen one after the other
    (e.g. a fixed source gamma transport step that needs appropriate
    fission rates), it is essential that the neutronics params be
    mapped onto the newly converted reactor as well as off of it
    back to the source reactor.
    """

    def __init__(self, cs=None, calcReactionRates=True):
        """
        Parameters
        ----------
        cs : obj, optional
            Case settings object.

        calcReactionRates : bool, optional
            Set to True by default, but if set to False the reaction
            rate calculation after the neutron flux is remapped will
            not be calculated.
        """
        UniformMeshGeometryConverter.__init__(self, cs)
        self.blockMultigroupParamNames = None
        self.calcReactionRates = calcReactionRates

    def _checkConversion(self):
        """
        Make sure both reactors have the same power and that it's equal to user-input.

        On the initial neutronics run, of course source power will be zero.
        """
        UniformMeshGeometryConverter._checkConversion(self)
        sourcePow = self._sourceReactor.core.getTotalBlockParam("power")
        convPow = self.convReactor.core.getTotalBlockParam("power")
        if sourcePow > 0.0 and convPow > 0.0:
            if abs(sourcePow - convPow) / sourcePow > 1e-5:
                runLog.info(
                    f"Source reactor power ({sourcePow}) is too different from "
                    f"converted power ({convPow})."
                )

            if self._sourceReactor.p.timeNode != 0:
                # only check on nodes other than BOC
                expectedPow = (
                    self._sourceReactor.core.p.power
                    / self._sourceReactor.core.powerMultiplier
                )
                if sourcePow and abs(sourcePow - expectedPow) / sourcePow > 1e-5:
                    raise ValueError(
                        f"Source reactor power ({sourcePow}) is too different from "
                        f"user-input power ({expectedPow})."
                    )

    def _setParamsToUpdate(self):
        """Activate conversion of various neutronics paramters."""
        UniformMeshGeometryConverter._setParamsToUpdate(self)

        self.reactorParamNames = self._sourceReactor.core.p.paramDefs.inCategory(
            parameters.Category.neutronics
        ).names

        runLog.extra(
            f"Reactor parameters that will be mapped are: {self.reactorParamNames}"
        )

        b = self._sourceReactor.core.getFirstBlock()

        self.blockMultigroupParamNames = b.p.paramDefs.inCategory(
            parameters.Category.multiGroupQuantities
        ).names
        self.blockDetailedAxialExpansionParamNames = b.p.paramDefs.inCategory(
            parameters.Category.detailedAxialExpansion
        ).names

        runLog.extra(
            f"Block params that will be mapped are: {self.blockMultigroupParamNames + self.blockDetailedAxialExpansionParamNames}"
        )

    def _clearStateOnReactor(self, reactor, cache):
        """
        Clear all multi-group block parameters.
        """
        UniformMeshGeometryConverter._clearStateOnReactor(self, reactor, cache)
        for b in reactor.core.getBlocks():
            for fluxParam in self.blockMultigroupParamNames:
                if cache:
                    self._cachedBlockParamData[b][fluxParam] = b.p[fluxParam]
                b.p[fluxParam] = []

    def _mapStateFromReactorToOther(self, sourceReactor, destReactor):
        UniformMeshGeometryConverter._mapStateFromReactorToOther(
            self, sourceReactor, destReactor
        )

        def paramSetter(block, vals, paramNames):
            for paramName, val in zip(paramNames, vals):
                block.p[paramName] = val

        def paramGetter(block, paramNames):
            paramVals = []
            for paramName in paramNames:
                val = block.p[paramName]
                if not val:
                    paramVals.append(None)
                else:
                    paramVals.append(val)
            return numpy.array(paramVals, dtype=object)

        def multiGroupParamSetter(block, multiGroupVals, paramNames):
            for paramName, val in zip(paramNames, multiGroupVals):
                block.p[paramName] = numpy.array(val)

        def multiGroupParamGetter(block, paramNames):
            paramVals = []
            for paramName in paramNames:
                val = block.p[paramName]
                if val is None or len(val) == 0:
                    paramVals.append(None)
                else:
                    paramVals.append(numpy.array(val))
            return numpy.array(paramVals, dtype=object)

        # Map reactor core parameters
        for paramName in self.reactorParamNames:
            # Check if the source reactor has a value assigned for this
            # parameter and if so, then apply it. Otherwise, revert back to
            # the original value.
            if (
                sourceReactor.core.p[paramName]
                or paramName not in self._cachedReactorCoreParamData
            ):
                val = sourceReactor.core.p[paramName]
            else:
                val = self._cachedReactorCoreParamData[paramName]
            destReactor.core.p[paramName] = val

        # Map block parameters
        for aSource in sourceReactor.core:
            aDest = destReactor.core.getAssemblyByName(aSource.getName())

            # Map the multi-group flux parameters
            _setStateFromOverlaps(
                aSource,
                aDest,
                multiGroupParamSetter,
                multiGroupParamGetter,
                self.blockMultigroupParamNames,
                self._cachedBlockParamData,
            )

            # Map the detailed axial expansion parameters
            _setStateFromOverlaps(
                aSource,
                aDest,
                paramSetter,
                paramGetter,
                self.blockDetailedAxialExpansionParamNames,
                self._cachedBlockParamData,
            )

            # If requested, the reaction rates will be calculated based on the
            # mapped neutron flux and the XS library.
            if self.calcReactionRates:
                for b in aDest:
                    globalFluxInterface.calcReactionRates(
                        b, destReactor.core.p.keff, destReactor.core.lib
                    )

        # Clear the cached data after it has been mapped to prevent issues with
        # holding on to block data long-term.
        self._cachedReactorCoreParamData = {}
        self._cachedBlockParamData = collections.defaultdict(dict)

        self._cachedReactorCoreParamData = {}
        self._cachedBlockParamData = collections.defaultdict(dict)


def _setNumberDensitiesFromOverlaps(block, overlappingBlockInfo):
    r"""
    Set number densities on a block based on overlapping blocks

    A conservation of number of atoms technique is used to map the non-uniform number densities onto the uniform
    neutronics mesh. When the number density of a height :math:`H` neutronics mesh block :math:`N^{\prime}` is
    being computed from one or more blocks in the ARMI mesh with number densities :math:`N_i` and
    heights :math:`h_i`, the following formula is used:

    .. math::

        N^{\prime} =  \sum_i N_i \frac{h_i}{H}


    See Also
    --------
    _setStateFromOverlaps : does this for state other than number densities.
    """
    totalDensities = {}
    block.clearNumberDensities()
    blockHeightInCm = block.getHeight()
    for overlappingBlock, overlappingHeightInCm in overlappingBlockInfo:
        for nucName, numberDensity in overlappingBlock.getNumberDensities().items():
            totalDensities[nucName] = (
                totalDensities.get(nucName, 0.0)
                + numberDensity * overlappingHeightInCm / blockHeightInCm
            )
    block.setNumberDensities(totalDensities)


def _setStateFromOverlaps(
    sourceAssembly, destinationAssembly, setter, getter, paramNames, cachedParams
):
    r"""
    Set state info on a assembly based on a source assembly with a different axial mesh

    This solves an averaging equation from the source to the destination.

    .. math::
        <P> = \frac{\int_{z_1}^{z_2} P(z) dz}{\int_{z_1}^{z_2} dz}

    which can be solved piecewise for z-coordinates along the source blocks.

    Parameters
    ----------
    sourceAssembly : Assembly
        assem that has the state
    destinationAssembly : Assembly
        assem that has is getting the state from sourceAssembly
    setter : function
        A function that takes (block, val) and sets val as state on block.
    getter : function
        takes block as an argument, returns relevant state that has __add__ capabilities.
    paramNames : list
        List of param names to set/get.
    cachedParams : collections.defaultdict(dict)
        A dictionary containing keys for each original block from the destination assembly
        that are mapped to a dictionary containing key, value pairs of parameter names and original
        values of the parameter from the destination assembly before the conversion process
        took place. In the instance where a block within the source assembly does not have a value,
        it the original cached value will be taken.

    Notes
    -----
    setter and getter are meant to be generated with particular state info (e.g. mgFlux or params).

    See Also
    --------
    _setNumberDensitiesFromOverlaps : does this but does smarter caching for number densities.
    """
    if not isinstance(paramNames, list):
        raise TypeError(
            f"The parameters names are not provided "
            f"as a list. Value(s) given: {paramNames}"
        )

    # The mapping of data from the source assembly to the destination assembly assumes that
    # the parameter values returned from the given ``getter`` have been cleared. If any
    # of these do not return a None before the conversion occurs then the mapping will
    # be incorrect. This checks that the parameters have been cleared and fails otherwise.
    for destBlock in destinationAssembly:
        existingDestBlockParamVals = getter(destBlock, paramNames)
        clearedValues = [
            True if not val else False for val in existingDestBlockParamVals
        ]
        if not all(clearedValues):
            raise ValueError(
                f"The state of {destBlock} on {destinationAssembly} "
                f"was not cleared prior to calling ``_setStateFromOverlaps``. "
                f"This is an implementation bug in the mesh converter that should "
                f"be reported to the developers. The following parameters should be cleared:\n"
                f"Parameters: {paramNames}\n"
                f"Values: {existingDestBlockParamVals}"
            )

    # The destination assembly is the assembly that the results are being mapped to
    # whereas the source assembly is the assembly that is from the uniform model. This
    # loop iterates over each block in the destination assembly and determines the mesh
    # coordinates that the uniform mesh (source assembly) will be mapped to.
    for destBlock in destinationAssembly:
        zLower = destBlock.p.zbottom
        zUpper = destBlock.p.ztop
        destinationBlockHeight = destBlock.getHeight()
        # Determine which blocks in the uniform mesh source assembly are
        # within the lower and upper bounds of the destination block.
        sourceBlocksInfo = sourceAssembly.getBlocksBetweenElevations(zLower, zUpper)

        if not sourceBlocksInfo:
            raise ValueError(
                f"An error occurred when attempting to map to the "
                f"results from {sourceAssembly} to {destinationAssembly}. "
                f"No blocks in {sourceAssembly} exist between the axial "
                f"elevations of {zLower:<8.3e} cm and {zUpper:<8.3e} cm. "
                f"This a major bug in the uniform mesh converter that should "
                f"be reported to the developers."
            )

        # Iterate over each of the blocks that were found in the uniform mesh
        # source assembly within the lower and upper bounds of the destination
        # block and perform the parameter mapping.
        updatedDestVals = collections.defaultdict(float)
        for sourceBlock, sourceBlockOverlapHeight in sourceBlocksInfo:
            sourceBlockVals = getter(sourceBlock, paramNames)
            sourceBlockHeight = sourceBlock.getHeight()

            for paramName, sourceBlockVal in zip(paramNames, sourceBlockVals):
                # The value can be `None` if it has not been set yet. In this case,
                # the mapping should be skipped.
                if sourceBlockVal is None:
                    continue

                # Determine if the parameter is volumed integrated or not.
                isVolIntegrated = sourceBlock.p.paramDefs[paramName].atLocation(
                    parameters.ParamLocation.VOLUME_INTEGRATED
                )

                # If the parameter is volume integrated (e.g., flux, linear power)
                # then calculate the fractional contribution from the source block.
                if isVolIntegrated:
                    integrationFactor = sourceBlockOverlapHeight / sourceBlockHeight

                # If the parameter is not volume integrated (e.g., volumetric reaction rate)
                # then calculate the fraction contribution on the destination block.
                # This smears the parameter over the destination block.
                else:
                    integrationFactor = (
                        sourceBlockOverlapHeight / destinationBlockHeight
                    )

                updatedDestVals[paramName] += sourceBlockVal * integrationFactor

            setter(destBlock, updatedDestVals.values(), updatedDestVals.keys())

        # For parameters that have not been set on the destination block, recover these
        # back to their originals based on the cached values.
        for paramName in paramNames:
            # Skip over any parameter names that were not previously cached.
            if paramName not in cachedParams[destBlock]:
                continue

            if isinstance(destBlock.p[paramName], list) or isinstance(
                destBlock.p[paramName], numpy.ndarray
            ):
                # Using just all() on the list/array is not sufficient because if a zero value exists
                # in the data then this would then lead to overwritting the data. This is an edge case see
                # in the testing, so this excludes zero values on the check.
                if not all([val for val in destBlock.p[paramName] if val != 0.0]):
                    destBlock.p[paramName] = cachedParams[destBlock][paramName]
            else:
                if not destBlock.p[paramName]:
                    destBlock.p[paramName] = cachedParams[destBlock][paramName]
