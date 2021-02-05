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
uniformReactor = converter.convert(reactor)
# do calcs, then:
converter.applyStateToOriginal()

The mesh mapping happens as described in the figure:

.. figure:: /.static/axial_homogenization.png

"""
import copy

import numpy

from armi import runLog
from armi import utils
from armi.utils import iterables
from armi.utils import plotting
from armi.reactor import grids
from armi.reactor.flags import Flags
from armi.reactor.converters.geometryConverters import GeometryConverter
from armi.reactor import parameters

# unfortunate physics coupling, but still in the framework
from armi.physics.neutronics.globalFlux import globalFluxInterface


class UniformMeshGeometryConverter(GeometryConverter):
    """
    Build uniform mesh version of the source reactor
    """

    def __init__(self, cs=None):
        GeometryConverter.__init__(self, cs)
        self._uniformMesh = None
        self.blockParamNames = []
        self.reactorParamNames = []

    def convert(self, r=None):
        """Create a new reactor with a uniform mesh."""
        runLog.extra("Building copy of {} with a uniform axial mesh".format(r))
        self._sourceReactor = r
        self.convReactor = self.initNewReactor(r)
        self._setParamsToUpdate()
        self._computeAverageAxialMesh()
        self._buildAllUniformAssemblies()
        self._clearStateOnReactor(self.convReactor)
        self._mapStateFromReactorToOther(self._sourceReactor, self.convReactor)
        self.convReactor.core.updateAxialMesh()
        self._checkConversion()
        return self.convReactor

    def _checkConversion(self):
        """Perform checks to ensure conversion occurred properly."""

    @staticmethod
    def initNewReactor(sourceReactor):
        """
        Built an empty version of the new reactor.
        """
        # XXX: this deepcopy is extremely wasteful because the assemblies copied
        # are immediately removed. It's just laziness of getting the same class
        # of reactor set up.
        newReactor = copy.deepcopy(sourceReactor)
        newReactor.core.removeAllAssemblies()
        newReactor.core.regenAssemblyLists()
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
        self._uniformMesh = utils.average1DWithinTolerance(numpy.array(allMeshes))

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
        bottom = 0.0
        for topMeshPoint in newMesh:
            overlappingBlockInfo = sourceAssem.getBlocksBetweenElevations(
                bottom, topMeshPoint
            )
            if not overlappingBlockInfo:
                # this could be handled by duplicating the block but with the current CR module
                # this situation should just never happen.
                raise RuntimeError(
                    "No block found between {:.3f} and {:.3f} in assembly {}"
                    "".format(bottom, topMeshPoint, sourceAssem)
                )

            # If there are FUEL or CONTROL blocks that are overlapping with the other blocks then the first
            # one is selected to ensure that the correct XS ID is applied to the new block during the deepcopy.
            sourceBlock = None
            specialXSType = None
            for potentialBlock, _overlap in overlappingBlockInfo:
                if sourceBlock is None:
                    sourceBlock = potentialBlock
                if (
                    potentialBlock.hasFlags([Flags.FUEL, Flags.CONTROL])
                    and potentialBlock != sourceBlock
                ):
                    runLog.important(
                        "There are multiple overlapping blocks.  Choosing {} for {} XS sets.".format(
                            potentialBlock.getType(), sourceBlock.getType()
                        )
                    )
                    if specialXSType is None:
                        sourceBlock = potentialBlock
                        specialXSType = sourceBlock.p.xsType
                    elif specialXSType == potentialBlock.p.xsType:
                        pass
                    else:
                        runLog.error(
                            "There are two special block XS types.  Not sure which to choose {} {}"
                            "".format(sourceBlock, potentialBlock)
                        )
                        raise RuntimeError(
                            "There are multiple special block XS types when there should only be one"
                        )

            block = copy.deepcopy(sourceBlock)
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
        for sourceAssem in self._sourceReactor.core:
            newAssem = self.makeAssemWithUniformMesh(sourceAssem, self._uniformMesh)
            newAssem.r = self.convReactor
            # would be nicer if this happened in add but there's  complication between
            # moveTo and add precedence and location-already-filled-issues.
            newAssem.parent = self.convReactor.core
            src = sourceAssem.spatialLocator
            newLoc = self.convReactor.core.spatialGrid[src.i, src.j, 0]
            self.convReactor.core.add(newAssem, newLoc)

    def plotConvertedReactor(self):
        assemsToPlot = self.convReactor.core[:12]
        for plotNum, assemBatch in enumerate(iterables.chunk(assemsToPlot, 6), start=1):
            assemPlotName = f"{self.convReactor.core.name}AssemblyTypes{plotNum}.png"
            plotting.plotAssemblyTypes(
                self.convReactor.core.parent.blueprints,
                assemPlotName,
                assemBatch,
                maxAssems=6,
                showBlockAxMesh=True,
            )

    def _setParamsToUpdate(self):
        """Gather a list of parameters that will be mapped between reactors."""

    def _clearStateOnReactor(self, reactor):
        """
        Delete existing state that will be updated so they don't increment.

        The summations should start at zero but will happen for all overlaps.
        """
        runLog.debug("Clearing params from source reactor that will be converted.")
        for rp in self.reactorParamNames:
            reactor.core.p[rp] = 0.0

        for b in reactor.core.getBlocks():
            for bp in self.blockParamNames:
                b.p[bp] = 0.0

    def applyStateToOriginal(self):
        """
        Now that state is computed on the uniform mesh, map it back to ARMI mesh.
        """
        runLog.extra(
            "Applying uniform neutronics mesh results on {0} to ARMI mesh on {1}".format(
                self.convReactor, self._sourceReactor
            )
        )
        self._clearStateOnReactor(self._sourceReactor)
        self._mapStateFromReactorToOther(self.convReactor, self._sourceReactor)

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
            expectedPow = (
                self._sourceReactor.core.p.power
                / self._sourceReactor.core.powerMultiplier
            )
            if abs(sourcePow - convPow) / sourcePow > 1e-5:
                runLog.info(
                    f"Source reactor power ({sourcePow}) is too different from "
                    f"converted power ({convPow})."
                )
            if sourcePow and abs(sourcePow - expectedPow) / sourcePow > 1e-5:
                raise ValueError(
                    f"Source reactor power ({sourcePow}) is too different from "
                    f"user-input power ({expectedPow})."
                )

    def _setParamsToUpdate(self):
        """Activate conversion of various neutronics paramters."""
        UniformMeshGeometryConverter._setParamsToUpdate(self)
        b = self._sourceReactor.core.getFirstBlock()

        self.blockParamNames = b.p.paramDefs.inCategory(
            parameters.Category.detailedAxialExpansion
        ).names
        self.reactorParamNames = self._sourceReactor.core.p.paramDefs.inCategory(
            parameters.Category.neutronics
        ).names

        runLog.debug(
            "Block params that will be converted include: {0}".format(
                self.blockParamNames
            )
        )
        runLog.debug(
            "Reactor params that will be converted include: {0}".format(
                self.reactorParamNames
            )
        )

    def _clearStateOnReactor(self, reactor):
        """
        Also clear mgFlux params.
        """
        UniformMeshGeometryConverter._clearStateOnReactor(self, reactor)

        for b in reactor.core.getBlocks():
            b.p.mgFlux = []
            b.p.adjMgFlux = []

    def _mapStateFromReactorToOther(self, sourceReactor, destReactor):
        UniformMeshGeometryConverter._mapStateFromReactorToOther(
            self, sourceReactor, destReactor
        )

        def paramSetter(armiObject, vals, paramNames):
            for paramName, val in zip(paramNames, vals):
                armiObject.p[paramName] = val

        def paramGetter(armiObject, paramNames):
            paramVals = []
            for paramName in paramNames:
                paramVals.append(armiObject.p[paramName])
            return numpy.array(paramVals)

        def fluxSetter(block, flux, _paramNames):
            block.p.mgFlux = list(flux)

        def fluxGetter(block, _paramNames):
            val = block.p.mgFlux
            if val is None or len(val) == 0:
                # so the merger can detect and just use incremental value.
                return None
            else:
                return numpy.array(val)

        def adjointFluxSetter(block, flux, _paramNames):
            block.p.adjMgFlux = list(flux)

        def adjointFluxGetter(block, _paramNames):
            val = block.p.adjMgFlux
            if val is None or len(val) == 0:
                # so the merger can detect and just use incremental value.
                return None
            else:
                return numpy.array(val)

        for paramName in self.reactorParamNames:
            destReactor.core.p[paramName] = sourceReactor.core.p[paramName]

        for aSource in sourceReactor.core:
            aDest = destReactor.core.getAssemblyByName(aSource.getName())
            _setStateFromOverlaps(aSource, aDest, fluxSetter, fluxGetter, ["mgFlux"])
            _setStateFromOverlaps(
                aSource, aDest, adjointFluxSetter, adjointFluxGetter, ["adjMgFlux"]
            )
            _setStateFromOverlaps(
                aSource, aDest, paramSetter, paramGetter, self.blockParamNames
            )

            # If requested, the reaction rates will be calculated based on the
            # mapped neutron flux and the XS library.
            if self.calcReactionRates:
                for b in aDest:
                    globalFluxInterface.calcReactionRates(
                        b, destReactor.core.p.keff, destReactor.core.lib
                    )


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
    blockHeightInCm = block.getHeight()
    for overlappingBlock, overlappingHeightInCm in overlappingBlockInfo:
        for nucName, numberDensity in overlappingBlock.getNumberDensities().items():
            totalDensities[nucName] = (
                totalDensities.get(nucName, 0.0)
                + numberDensity * overlappingHeightInCm / blockHeightInCm
            )

    block.clearNumberDensities()
    block.setNumberDensities(totalDensities)


def _setStateFromOverlaps(
    sourceAssembly, destinationAssembly, setter, getter, paramNames=None
):
    r"""
    Set state info on a assembly based on a source assembly with a different axial mesh

    This solves an averaging equation from the source to the destination.

    .. math::
        <P> = \frac{\int_{z_1}^{z_2} P(z) dz}{\int_{z_1}^{z_2} dz}

    which can be solved piecewise for z-coordinates along the source blocks.

    For volume-integrated params (like block power), one must note that the piecewise
    integrals have the fraction of overlapping source height in them, not the overlapping
    height itself.

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
        List of param names to set/get. Ok to skip if getter does not use param names.

    Notes
    -----
    setter and getter are meant to be generated with particular state info (e.g. mgFlux or params).

    See Also
    --------
    _setNumberDensitiesFromOverlaps : does this but does smarter caching for number densities.
    """
    block = destinationAssembly[0]
    volumeIntegratedFlags = [
        block.p.paramDefs[paramName].atLocation(
            parameters.ParamLocation.VOLUME_INTEGRATED
        )
        for paramName in paramNames
    ]

    for destinationBlock, bottomMeshPoint in destinationAssembly.getBlocksAndZ(
        returnBottomZ=True
    ):
        destBlockHeightInCm = destinationBlock.getHeight()
        topMeshPoint = bottomMeshPoint + destBlockHeightInCm
        overlappingBlockInfo = sourceAssembly.getBlocksBetweenElevations(
            bottomMeshPoint, topMeshPoint
        )
        if overlappingBlockInfo:
            for overlappingSourceBlock, overlappingHeightInCm in overlappingBlockInfo:
                sourceBlockHeightInCm = overlappingSourceBlock.getHeight()
                existingVals = getter(destinationBlock, paramNames)
                sourceValOnOverlapper = getter(overlappingSourceBlock, paramNames)
                if sourceValOnOverlapper is None:
                    # could be b.p.adjMgFlux before it's set.
                    continue

                integrationFactors = []
                for volIntFlag in volumeIntegratedFlags:
                    # make array with terms to properly handle volume-integrated params.
                    # these need fractional contributions.
                    if volIntFlag:
                        # sum up fractions of the source into the dest
                        integrationFactors.append(
                            overlappingHeightInCm / sourceBlockHeightInCm
                        )
                    else:
                        # average the source onto the dest
                        integrationFactors.append(
                            overlappingHeightInCm / destBlockHeightInCm
                        )
                if len(volumeIntegratedFlags) == 1:
                    # hack for multigroup valued flux/adjoint
                    integrationFactors = integrationFactors[0]
                else:
                    integrationFactors = numpy.array(integrationFactors)

                incrementalValue = sourceValOnOverlapper * integrationFactors
                if existingVals is None:
                    # deal with adding a vector to None before flux exists.
                    setter(destinationBlock, incrementalValue, paramNames)
                else:
                    setter(
                        destinationBlock, existingVals + incrementalValue, paramNames
                    )
        else:
            if destinationBlock.hasFlags(Flags.FUEL):
                raise RuntimeError(
                    "A fuel block is not being mapped in the meshing routine.  This is likely serious."
                )
            else:
                runLog.warning(
                    "Block {} is not being mapped in the meshing routine".format(
                        destinationBlock
                    ),
                    single=True,
                    label="uniformMeshWarning",
                )
