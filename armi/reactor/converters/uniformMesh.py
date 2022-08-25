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
    """
    This geometry converter can be used to change the axial mesh structure of the reactor core.

    Notes
    -----
    There are several staticmethods available on this class that allow for:
        - Creation of a new reactor without applying a new uniform axial mesh. See: `<UniformMeshGeometryConverter.initNewReactor>`
        - Creation of a new assembly with a new axial mesh applied. See: `<UniformMeshGeometryConverter.makeAssemWithUniformMesh>`
        - Resetting the parameter state of an assembly back to the defaults for the provided block parameters. See: `<UniformMeshGeometryConverter.clearStateOnAssemblies>`
        - Mapping number densities and block parameters between one assembly to another. See: `<UniformMeshGeometryConverter.setAssemblyStateFromOverlaps>`
    """

    def __init__(self, cs=None):
        GeometryConverter.__init__(self, cs)
        self._uniformMesh = None
        self.reactorParamNames = []
        self.blockScalarParamNames = []
        self.blockArrayParamNames = []

        # These dictionaries represent back-up data from the source reactor
        # that can be recovered if the data is not being brought back from
        # the uniform mesh reactor when ``applyStateToOriginal`` to called.
        # This prevents clearing out data on the original reactor that should
        # be preserved since no changes were applied.
        self._cachedReactorCoreParamData = {}

    def convert(self, r=None):
        """Create a new reactor core with a uniform mesh."""
        if r is None:
            raise ValueError(f"No reactor provided in {self}")

        runLog.extra("Building copy of {} with a uniform axial mesh".format(r))
        completeStartTime = timer()
        self._sourceReactor = r
        self.convReactor = self.initNewReactor(r)
        self._setParamsToUpdate()
        self._computeAverageAxialMesh()
        self._buildAllUniformAssemblies()
        self._mapStateFromReactorToOther(self._sourceReactor, self.convReactor)
        self.convReactor.core.updateAxialMesh()

        self._newAssembliesAdded = self.convReactor.core.getAssemblies()

        self._checkConversion()
        completeEndTime = timer()
        runLog.extra(
            f"Reactor core conversion time: {completeEndTime-completeStartTime} seconds"
        )

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

    def applyStateToOriginal(self):
        """Apply the state of the converted reactor back to the original reactor, mapping number densities and block parameters."""
        runLog.extra(
            f"Applying uniform neutronics results from {self.convReactor} to {self._sourceReactor}"
        )
        completeStartTime = timer()

        # Clear the state of the original source reactor to ensure that
        # a clean mapping between the converted reactor for data that has been
        # changed. In this case, we cache the original reactor's data so that
        # after the mapping has been applied, we can recover data from any
        # parameters that did not change.
        self._cachedReactorCoreParamData = {}
        self._clearStateOnReactor(self._sourceReactor, cache=True)
        self._mapStateFromReactorToOther(self.convReactor, self._sourceReactor)

        # We want to map the converted reactor core's library to the source reactor
        # because in some instances this has changed (i.e., when generating cross sections).
        self._sourceReactor.core.lib = self.convReactor.core.lib
        completeEndTime = timer()
        runLog.extra(
            f"Parameter remapping time: {completeEndTime-completeStartTime} seconds"
        )
        self.reset()

    @staticmethod
    def makeAssemWithUniformMesh(
        sourceAssem, newMesh, blockScalarParamNames=None, blockArrayParamNames=None
    ):
        """
        Build new assembly based on a source assembly but apply the uniform mesh.

        Notes
        -----
        This creates a new assembly based on the provided source assembly, applies
        a new uniform mesh and then maps number densities and block-level parameters
        to the new assembly from the source assembly.

        Parameters
        ----------
        sourceAssem : `Assembly <armi.reactor.assemblies.Assembly>` object
            Assembly that is used to map number densities and block-level parameters to
            a new mesh structure.
        newMesh : List[float]
            A list of the new axial mesh coordinates of the blocks. Note that these mesh
            coordinates are in cm and should represent the top axial mesh coordinates of
            the new blocks.
         blockScalarParamNames : List[str], optional
            A list of block parameter names that can be assigned scalar values (i.e., int/float/string).
            Examples: `flux`, `power`. If this is not provided then no scalar parameters will be mapped.
        blockArrayParamNames : List[str], optional
            A list of block parameter names that can be assigned array values (i.e., numpy.array/list).
            Example: `mgFlux`. If this is not provided then no array parameters will be mapped.
        See Also
        --------
        setAssemblyStateFromOverlaps
            This can be used to reverse the number density and parameter mappings
            between two assemblies.
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
                    f"Ensure a valid mesh is provided. Mesh given: {newMesh}"
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
            newAssem.add(block)
            bottom = topMeshPoint

        newAssem.reestablishBlockOrder()
        newAssem.calculateZCoords()

        UniformMeshGeometryConverter.setAssemblyStateFromOverlaps(
            sourceAssem, newAssem, blockScalarParamNames, blockArrayParamNames
        )
        return newAssem

    @staticmethod
    def setAssemblyStateFromOverlaps(
        sourceAssembly,
        destinationAssembly,
        blockScalarParamNames=None,
        blockArrayParamNames=None,
    ):
        """
        Set state data (i.e., number densities and block-level parameters) on a assembly based on a source
        assembly with a different axial mesh.

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
        blockScalarParamNames : List[str], optional
            A list of block parameter names that can be assigned scalar values (i.e., int/float/string).
            Examples: `flux`, `power`. If this is not provided then no scalar parameters will be mapped.
        blockArrayParamNames : List[str], optional
            A list of block parameter names that can be assigned array values (i.e., numpy.array/list).
            Example: `mgFlux`. If this is not provided then no array parameters will be mapped.

        Notes
        -----
        setter and getter are meant to be generated with particular state info (e.g. mgFlux or params).

        See Also
        --------
        _setNumberDensitiesFromOverlaps : does this but does smarter caching for number densities.
        """
        if blockScalarParamNames is None:
            blockScalarParamNames = []
        if blockArrayParamNames is None:
            blockArrayParamNames = []

        if not isinstance(blockScalarParamNames, list):
            raise TypeError(
                f"The ``blockScalarParamNames`` parameters names are not provided "
                f"as a list. Value(s) given: {blockScalarParamNames}"
            )
        if not isinstance(blockArrayParamNames, list):
            raise TypeError(
                f"The ``blockArrayParamNames`` parameters names are not provided "
                f"as a list. Value(s) given: {blockArrayParamNames}"
            )

        cachedParams = UniformMeshGeometryConverter.clearStateOnAssemblies(
            [destinationAssembly],
            blockScalarParamNames,
            blockArrayParamNames,
            cache=True,
        )
        for destBlock in destinationAssembly:

            # Check that the parameters on the destination block have been cleared first before attempting to
            # map the data. These parameters should be cleared using ``UniformMeshGeometryConverter.clearStateOnAssemblies``.
            for getter, paramNames in [
                (BlockParamMapper.scalarParamGetter, blockScalarParamNames),
                (BlockParamMapper.arrayParamGetter, blockArrayParamNames),
            ]:

                existingDestBlockParamVals = getter(destBlock, paramNames)
                clearedValues = [
                    True if not val else False for val in existingDestBlockParamVals
                ]
                if not all(clearedValues):
                    raise ValueError(
                        f"The state of {destBlock} on {destinationAssembly} "
                        f"was not cleared prior to calling ``setAssemblyStateFromOverlaps``. "
                        f"This indicates an implementation bug in the mesh converter that should "
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

            _setNumberDensitiesFromOverlaps(destBlock, sourceBlocksInfo)

            for setter, getter, paramNames in [
                (
                    BlockParamMapper.scalarParamSetter,
                    BlockParamMapper.scalarParamGetter,
                    blockScalarParamNames,
                ),
                (
                    BlockParamMapper.arrayParamSetter,
                    BlockParamMapper.arrayParamGetter,
                    blockArrayParamNames,
                ),
            ]:

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
                            integrationFactor = (
                                sourceBlockOverlapHeight / sourceBlockHeight
                            )

                        # If the parameter is not volume integrated (e.g., volumetric reaction rate)
                        # then calculate the fraction contribution on the destination block.
                        # This smears the parameter over the destination block.
                        else:
                            integrationFactor = (
                                sourceBlockOverlapHeight / destinationBlockHeight
                            )

                        updatedDestVals[paramName] += sourceBlockVal * integrationFactor

                    setter(destBlock, updatedDestVals.values(), updatedDestVals.keys())

                UniformMeshGeometryConverter._applyCachedParamValues(
                    destBlock, paramNames, cachedParams
                )

    @staticmethod
    def _applyCachedParamValues(destBlock, paramNames, cachedParams):
        """
        Applies the cached parameter values back to the destination block, if there are any.

        Notes
        -----
        This is implemented to ensure that if certain parameters are not set on the original
        block that the destination block has the parameter data recovered rather than zeroing
        the data out. The destination block is cleared before the mapping occurs in ``clearStateOnAssemblies``.
        """

        # For parameters that have not been set on the destination block, recover these
        # back to their originals based on the cached values.
        for paramName in paramNames:

            # Skip over any parameter names that were not previously cached.
            if paramName not in cachedParams[destBlock]:
                continue

            if isinstance(destBlock.p[paramName], numpy.ndarray):
                # Using just all() on the list/array is not sufficient because if a zero value exists
                # in the data then this would then lead to overwritting the data. This is an edge case see
                # in the testing, so this excludes zero values on the check.
                if (
                    not all([val for val in destBlock.p[paramName] if val != 0.0])
                    or not destBlock.p[paramName].size > 0
                ):
                    destBlock.p[paramName] = cachedParams[destBlock][paramName]
            elif isinstance(destBlock.p[paramName], list):
                if (
                    not all([val for val in destBlock.p[paramName] if val != 0.0])
                    or not destBlock.p[paramName]
                ):
                    destBlock.p[paramName] = cachedParams[destBlock][paramName]
            else:
                if not destBlock.p[paramName]:
                    destBlock.p[paramName] = cachedParams[destBlock][paramName]

    @staticmethod
    def clearStateOnAssemblies(
        assems, blockScalarParamNames=None, blockArrayParamNames=None, cache=True
    ):
        """
        Clears the parameter state of blocks for a list of assemblies.

        Parameters
        ----------
        assems : List[`Assembly <armi.reactor.assemblies.Assembly>`]
            List of assembly objects.
        blockScalarParamNames : List[str], optional
            A list of block parameter names that can be assigned scalar values (i.e., int/float/string).
            Examples: `flux`, `power`. If this is not provided then no scalar parameters will be mapped.
        blockArrayParamNames : List[str], optional
            A list of block parameter names that can be assigned array values (i.e., numpy.array/list).
            Example: `mgFlux`. If this is not provided then no array parameters will be mapped.
        cache : bool
            If True, the block parameters that were cleared are stored
            and returned as a dictionary of ``{b: {param1: val1, param2: val2}, b2: {...}, ...}``
        """
        if blockScalarParamNames is None:
            blockScalarParamNames = []
        if blockArrayParamNames is None:
            blockArrayParamNames = []

        cachedBlockParamData = collections.defaultdict(dict)

        blocks = []
        for a in assems:
            blocks.extend(a.getBlocks())
        for b in blocks:
            for paramName in blockScalarParamNames + blockArrayParamNames:
                if cache:
                    cachedBlockParamData[b][paramName] = b.p[paramName]
                b.p[paramName] = b.p.pDefs[paramName].default

        return cachedBlockParamData

    def plotConvertedReactor(self):
        """Generate a radial layout image of the converted reactor core."""
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

    def reset(self):
        """Clear out stored attributes and reset the global assembly number."""
        self.reactorParamNames = []
        self.blockScalarParamNames = []
        self.blockArrayParamNames = []
        self._cachedReactorCoreParamData = {}
        super().reset()

    def _setParamsToUpdate(self):
        """Activate conversion of various paramters."""
        self.reactorParamNames = []
        self.blockScalarParamNames = []
        self.blockArrayParamNames = []

    def _checkConversion(self):
        """Perform checks to ensure conversion occurred properly."""
        pass

    def _computeAverageAxialMesh(self):
        """
        Computes an average axial mesh based on the core's reference assembly.

        Notes
        -----
        This iterates over all the assemblies in the core and collects all assembly meshes
        that have the same number of fine-mesh points as the `refAssem` for the core. Based on
        this, the proposed uniform mesh will be some average of many assemblies in the core.
        The reason for this is to account for the fact that multiple assemblies (i.e., fuel assemblies)
        may have a different mesh due to differences in thermal and/or burn-up expansion.
        """
        src = self._sourceReactor
        refAssem = src.core.refAssem
        # Get the number of reference mesh points, including the sub-mesh. This subtracts 1
        # to remove the first value (typically zero).
        refNumPoints = (
            len(src.core.findAllAxialMeshPoints([refAssem], applySubMesh=True)) - 1
        )
        allMeshes = []
        for a in src.core:
            # Get the mesh points of the assembly, neglecting the first coordinate (typically zero).s
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

    def _mapStateFromReactorToOther(self, sourceReactor, destReactor):
        """
        Map parameters from one reactor to another.

        Notes
        -----
        This can be implemented in sub-classes to map specific reactor and assembly data.
        """
        pass


class NeutronicsUniformMeshConverter(UniformMeshGeometryConverter):
    """
    A uniform mesh converter that specifically maps neutronics parameters.

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
        self.calcReactionRates = calcReactionRates

    def _setParamsToUpdate(self):
        """Activate conversion of various neutronics-only paramters."""
        UniformMeshGeometryConverter._setParamsToUpdate(self)

        self.reactorParamNames.extend(
            self._sourceReactor.core.p.paramDefs.inCategory(
                parameters.Category.neutronics
            ).names
        )

        b = self._sourceReactor.core.getFirstBlock()
        self.blockScalarParamNames.extend(
            b.p.paramDefs.inCategory(parameters.Category.detailedAxialExpansion).names
        )
        self.blockArrayParamNames.extend(
            b.p.paramDefs.inCategory(parameters.Category.multiGroupQuantities).names
        )

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

    def _mapStateFromReactorToOther(self, sourceReactor, destReactor):
        UniformMeshGeometryConverter._mapStateFromReactorToOther(
            self, sourceReactor, destReactor
        )

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
            UniformMeshGeometryConverter.setAssemblyStateFromOverlaps(
                aSource, aDest, self.blockScalarParamNames, self.blockArrayParamNames
            )

            # If requested, the reaction rates will be calculated based on the
            # mapped neutron flux and the XS library.
            if self.calcReactionRates:
                for b in aDest:
                    # Checks if the block has a multi-group flux defined and if it
                    # does not then this will skip the reaction rate calculation. This
                    # is captured by the TypeError, due to a `NoneType` divide by float
                    # error.
                    try:
                        b.getMgFlux()
                    except TypeError:
                        continue
                    globalFluxInterface.calcReactionRates(
                        b, destReactor.core.p.keff, destReactor.core.lib
                    )

        # Clear the cached data after it has been mapped to prevent issues with
        # holding on to block data long-term.
        self._cachedReactorCoreParamData = {}


class BlockParamMapper:
    """
    Namespace for parameter setters/getters that can be used when
    transferring data from one assembly to another during the mesh
    conversion process.
    """

    @staticmethod
    def scalarParamSetter(block, vals, paramNames):
        """Assigns a set of float/integer/string values to a given set of parameters on a block."""
        for paramName, val in zip(paramNames, vals):
            block.p[paramName] = val

    @staticmethod
    def scalarParamGetter(block, paramNames):
        """Returns a set of float/integer/string values for a given set of parameters on a block."""
        paramVals = []
        for paramName in paramNames:
            val = block.p[paramName]
            if val == block.p.pDefs[paramName].default:
                paramVals.append(block.p.pDefs[paramName].default)
            else:
                paramVals.append(val)
        return numpy.array(paramVals, dtype=object)

    @staticmethod
    def arrayParamSetter(block, multiGroupVals, paramNames):
        """Assigns a set of list/array values to a given set of parameters on a block."""
        for paramName, vals in zip(paramNames, multiGroupVals):
            if vals is None:
                continue
            block.p[paramName] = numpy.array(vals)

    @staticmethod
    def arrayParamGetter(block, paramNames):
        """Returns a set of list/array values for a given set of parameters on a block."""
        paramVals = []
        for paramName in paramNames:
            vals = block.p[paramName]
            if vals is None or len(vals) == 0:
                paramVals.append(None)
            else:
                paramVals.append(numpy.array(vals))

        return numpy.array(paramVals, dtype=object)


def _setNumberDensitiesFromOverlaps(block, overlappingBlockInfo):
    r"""
    Set number densities on a block based on overlapping blocks

    A conservation of number of atoms technique is used to map the non-uniform number densities onto the uniform
    neutronics mesh. When the number density of a height :math:`H` neutronics mesh block :math:`N^{\prime}` is
    being computed from one or more blocks in the ARMI mesh with number densities :math:`N_i` and
    heights :math:`h_i`, the following formula is used:

    .. math::

        N^{\prime} =  \sum_i N_i \frac{h_i}{H}
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
