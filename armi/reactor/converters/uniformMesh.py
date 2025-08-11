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


.. warning::
    This procedure can cause numerical diffusion in some cases. For example,
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

import collections
import copy
import glob
import re
import typing
from timeit import default_timer as timer

import numpy as np

import armi
from armi import runLog
from armi.physics.neutronics.globalFlux import RX_ABS_MICRO_LABELS, RX_PARAM_NAMES
from armi.reactor import grids, parameters
from armi.reactor.converters.geometryConverters import GeometryConverter
from armi.reactor.flags import Flags
from armi.reactor.reactors import Core, Reactor
from armi.settings.fwSettings.globalSettings import CONF_UNIFORM_MESH_MINIMUM_SIZE
from armi.utils import iterables, plotting
from armi.utils.mathematics import average1DWithinTolerance

if typing.TYPE_CHECKING:
    from armi.reactor.blocks import Block

HEAVY_METAL_PARAMS = ["molesHmBOL", "massHmBOL"]


def converterFactory(globalFluxOptions):
    if globalFluxOptions.photons:
        return GammaUniformMeshConverter(globalFluxOptions.cs)
    else:
        return NeutronicsUniformMeshConverter(
            globalFluxOptions.cs,
            calcReactionRates=globalFluxOptions.calcReactionRatesOnMeshConversion,
        )


class UniformMeshGenerator:
    """
    This class generates a common axial mesh to for the uniform mesh converter to use. The
    generation algorithm starts with the simple ``average1DWithinTolerance`` utility function
    to compute a representative "average" of the assembly meshes in the reactor. It then modifies
    that mesh to more faithfully represent important material boundaries of fuel and control
    absorber material.

    The decusping feature is controlled with the case setting ``uniformMeshMinimumSize``. If no
    value is provided for this setting, the uniform mesh generator will skip the decusping step
    and just provide the result of ``_computeAverageAxialMesh``.
    """

    def __init__(self, r, minimumMeshSize=None):
        """
        Initialize an object to generate an appropriate common axial mesh to use for uniform mesh conversion.

        Parameters
        ----------
        r : :py:class:`Reactor <armi.reactor.reactors.Reactor>` object.
            Reactor for which a common mesh is generated
        minimumMeshSize : float, optional
            Minimum allowed separation between axial mesh points in cm
            If no minimum mesh size is provided, no "decusping" is performed
        """
        self._sourceReactor = r
        self.minimumMeshSize = minimumMeshSize
        self._commonMesh = None

    def generateCommonMesh(self):
        """
        Generate a common axial mesh to use.

        .. impl:: Try to preserve the boundaries of fuel and control material.
            :id: I_ARMI_UMC_NON_UNIFORM
            :implements: R_ARMI_UMC_NON_UNIFORM

            A core-wide mesh is computed via ``_computeAverageAxialMesh`` which
            operates by first collecting all the mesh points for every assembly
            (``allMeshes``) and then averaging them together using
            ``average1DWithinTolerance``. An attempt to preserve fuel and control
            material boundaries is accomplished by moving fuel region boundaries
            to accommodate control rod boundaries. Note this behavior only occurs
            by calling ``_decuspAxialMesh`` which is dependent on ``minimumMeshSize``
            being defined (this is controlled by the ``uniformMeshMinimumSize`` setting).

        .. impl:: Produce a mesh with a size no smaller than a user-specified value.
            :id: I_ARMI_UMC_MIN_MESH
            :implements: R_ARMI_UMC_MIN_MESH

            If a minimum mesh size ``minimumMeshSize`` is provided, calls
            ``_decuspAxialMesh`` on the core-wide mesh to maintain that minimum size
            while still attempting to honor fuel and control material boundaries. Relies
            ultimately on ``_filterMesh`` to remove mesh points that violate the minimum
            size. Note that ``_filterMesh`` will always respect the minimum mesh size,
            even if this means losing a mesh point that represents a fuel or control
            material boundary.

        Notes
        -----
        Attempts to reduce the effect of fuel and control rod absorber smearing
        ("cusping" effect) by keeping important material boundaries in the common mesh.
        """
        self._computeAverageAxialMesh()
        if self.minimumMeshSize is not None:
            self._decuspAxialMesh()

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

        Averaging all the assembly meshes that have the same number of points can be undesirable
        in certain corner cases because no preference is assigned based on assembly type. For
        example: if the reflector assemblies have the same number of mesh points as the fuel
        assemblies but the size of the blocks is slightly different, the reflector mesh can influence
        the uniform mesh and effectively pull it away from the fuel mesh boundaries, potentially
        resulting in smearing (i.e., homogenization) of fuel with non-fuel materials. This is an
        undesirable outcome. In the future, it may be advantageous to determine a better way of
        sorting and prioritizing assembly meshes for generating the uniform mesh.
        """
        src = self._sourceReactor
        refAssem = src.core.refAssem

        refNumPoints = len(src.core.findAllAxialMeshPoints([refAssem])[1:])
        allMeshes = []
        for a in src.core:
            # Get the mesh points of the assembly, neglecting the first coordinate
            # (typically zero).
            aMesh = src.core.findAllAxialMeshPoints([a])[1:]
            if len(aMesh) == refNumPoints:
                allMeshes.append(aMesh)

        averageMesh = average1DWithinTolerance(np.array(allMeshes))
        self._commonMesh = np.array(averageMesh)

    def _decuspAxialMesh(self):
        """
        Preserve control rod material boundaries to reduce control rod cusping effect.

        Notes
        -----
        Uniform mesh conversion can lead to axial smearing of control assembly material, which causes
        a pronounced control rod "cusping" affect in the differential rod worth. This function
        modifies the uniform mesh to honor fuel and control rod material boundaries while avoiding excessively
        small mesh sizes.

        If adding control rod material boundaries to the mesh creates excessively small mesh regions,
        this function will move internal fuel region boundaries to make room for the control rod boundaries.

        This function operates by filtering out mesh points that are too close together while always holding on
        to the specified "anchor" points in the mesh. The anchor points are built up progressively as the
        appropriate bottom and top boundaries of fuel and control assemblies are determined.
        """
        # filter fuel material boundaries to minimum mesh size
        filteredBottomFuel, filteredTopFuel = self._getFilteredMeshTopAndBottom(Flags.FUEL)
        materialBottoms, materialTops = self._getFilteredMeshTopAndBottom(
            Flags.CONTROL, filteredBottomFuel, filteredTopFuel
        )

        # combine the bottoms and tops into one list with bottom preference
        allMatBounds = materialBottoms + materialTops
        materialAnchors = self._filterMesh(
            allMatBounds,
            self.minimumMeshSize,
            filteredBottomFuel + filteredTopFuel,
            preference="bottom",
            warn=True,
        )

        runLog.extra(
            "Attempting to honor control and fuel material boundaries in uniform mesh "
            f"for {self} while also keeping minimum mesh size of {self.minimumMeshSize}. "
            f"Material boundaries are: {allMatBounds}"
        )

        # combine material bottom boundaries with full mesh using bottom preference
        meshWithBottoms = self._filterMesh(
            list(self._commonMesh) + materialBottoms,
            self.minimumMeshSize,
            materialBottoms,
            preference="bottom",
        )
        # combine material top boundaries with full mesh using top preference
        meshWithTops = self._filterMesh(
            list(self._commonMesh) + materialTops,
            self.minimumMeshSize,
            materialTops,
            preference="top",
        )
        # combine all mesh points using all material boundaries as anchors with top preference
        # top vs. bottom preference is somewhat arbitrary here
        combinedMesh = self._filterMesh(
            list(set(meshWithBottoms + meshWithTops)),
            self.minimumMeshSize,
            materialAnchors,
            preference="top",
        )

        self._commonMesh = np.array(combinedMesh)

    def _filterMesh(self, meshList, minimumMeshSize, anchorPoints, preference="bottom", warn=False):
        """
        Check for mesh violating the minimum mesh size and remove them if necessary.

        Parameters
        ----------
        meshList : list of float, required
            List of mesh points to be filtered by minimum mesh size
        minimumMeshSize : float, required
            Minimum allowed separation between axial mesh points in cm
        anchorPoints : list of float, required
            These mesh points will not be removed. Note that the anchor points must be separated by
            at least the ``minimumMeshSize``.
        preference : str, optional
            When neither mesh point is in the list of ``anchorPoints``, which mesh point is given preference
            ("bottom" or "top")
        warn : bool, optional
            Whether to log a warning when a mesh is removed. This is true if a
            control material boundary is removed, but otherwise it is false.
        """
        if preference == "bottom":
            meshList = sorted(list(set(meshList)))
        elif preference == "top":
            meshList = sorted(list(set(meshList)), reverse=True)
        else:
            raise ValueError(
                f"Mesh filtering preference {preference} is not an option! Preference must be either bottom or top"
            )

        while True:
            for i in range(len(meshList) - 1):
                difference = abs(meshList[i + 1] - meshList[i])
                if difference < minimumMeshSize:
                    if meshList[i] in anchorPoints and meshList[i + 1] in anchorPoints:
                        errorMsg = (
                            "Attempting to remove two anchor points!\n"
                            "The uniform mesh minimum size for decusping is smaller than the "
                            "gap between anchor points, which cannot be removed:\n"
                            f"{meshList[i]}, {meshList[i + 1]}, gap = {abs(meshList[i] - meshList[i + 1])}"
                        )
                        runLog.error(errorMsg)
                        raise ValueError(errorMsg)
                    if meshList[i + 1] in anchorPoints:
                        removeIndex = i
                    else:
                        removeIndex = i + 1

                    if warn:
                        runLog.warning(
                            f"{meshList[i + 1]} is too close to {meshList[i]}! "
                            f"Difference = {difference} is less than mesh size "
                            f"tolerance of {minimumMeshSize}. The uniform mesh will "
                            f"remove {meshList[removeIndex]}."
                        )
                    break
            else:
                return sorted(meshList)
            meshList.pop(removeIndex)

    def _getFilteredMeshTopAndBottom(self, flags, bottoms=None, tops=None):
        """
        Get the bottom and top boundaries of fuel assemblies and filter them based on the ``minimumMeshSize``.

        Parameters
        ----------
        flags : armi.reactor.flags.Flags
            The assembly and block flags for which to preserve material boundaries
            ``getAssemblies()`` and ``getBlocks()`` are both called with the default, ``exact=False``
        bottoms : list[float], optional
            Mesh "anchors" for material bottom boundaries
        tops : list[float], optional
            Mesh "anchors" for material top boundaries

        Returns
        -------
        filteredBottoms : the bottom of assembly materials, filtered to a minimum separation of
            ``minimumMeshSize`` with preference for the lowest bounds
        filteredTops : the top of assembly materials, filtered to a minimum separation of
            ``minimumMeshSize`` with preference for the top bounds
        """

        def firstBlockBottom(a, flags):
            return a.getFirstBlock(flags).p.zbottom

        def lastBlockTop(a, flags):
            return a.getBlocks(flags)[-1].p.ztop

        filteredBoundaries = dict()
        for meshList, preference, meshGetter, extreme in [
            (bottoms, "bottom", firstBlockBottom, min),
            (tops, "top", lastBlockTop, max),
        ]:
            matBoundaries = set(meshList) if meshList is not None else set()
            for a in self._sourceReactor.core.getAssemblies(flags):
                matBoundaries.add(meshGetter(a, flags))
            anchors = meshList if meshList is not None else [extreme(matBoundaries)]
            filteredBoundaries[preference] = self._filterMesh(
                matBoundaries, self.minimumMeshSize, anchors, preference=preference
            )

        return filteredBoundaries["bottom"], filteredBoundaries["top"]


class UniformMeshGeometryConverter(GeometryConverter):
    """
    This geometry converter can be used to change the axial mesh structure of the
    reactor core.

    Notes
    -----
    There are several staticmethods available on this class that allow for:

        - Creation of a new reactor without applying a new uniform axial mesh. See:
          `<UniformMeshGeometryConverter.initNewReactor>`
        - Creation of a new assembly with a new axial mesh applied. See:
          `<UniformMeshGeometryConverter.makeAssemWithUniformMesh>`
        - Resetting the parameter state of an assembly back to the defaults for the
          provided block parameters. See:
          `<UniformMeshGeometryConverter.clearStateOnAssemblies>`
        - Mapping number densities and block parameters between one assembly to
          another. See: `<UniformMeshGeometryConverter.setAssemblyStateFromOverlaps>`

    This class is meant to be extended for specific physics calculations that require a
    uniform mesh. The child types of this class should define custom
    `reactorParamsToMap` and `blockParamsToMap` attributes, and the
    `_setParamsToUpdate` method to specify the precise parameters that need to be
    mapped in each direction between the non-uniform and uniform mesh assemblies. The
    definitions should avoid mapping block parameters in both directions because the
    mapping process will cause numerical diffusion. The behavior of
    `setAssemblyStateFromOverlaps` is dependent on the direction in which the mapping
    is being applied to prevent the numerical diffusion problem.

    - "in" is used when mapping parameters into the uniform assembly
      from the non-uniform assembly.
    - "out" is used when mapping parameters from the uniform assembly back
      to the non-uniform assembly.

    .. warning::
        If a parameter is calculated by a physics solver while the reactor is in its
        converted (uniform mesh) state, that parameter *must* be included in the list
        of `reactorParamNames` or `blockParamNames` to be mapped back to the non-uniform
        reactor; otherwise, it will be lost. These lists are defined through the
        `_setParamsToUpdate` method, which uses the `reactorParamMappingCategories` and
        `blockParamMappingCategories` attributes and applies custom logic to create a list of
        parameters to be mapped in each direction.
    """

    reactorParamMappingCategories = {
        "in": [],
        "out": [],
    }
    blockParamMappingCategories = {
        "in": [],
        "out": [],
    }
    _TEMP_STORAGE_NAME_SUFFIX = "-TEMP"

    def __init__(self, cs=None):
        GeometryConverter.__init__(self, cs)
        self._uniformMesh = None
        self.calcReactionRates = False
        self.includePinCoordinates = False

        self.paramMapper = None

        # These dictionaries represent back-up data from the source reactor
        # that can be recovered if the data is not being brought back from
        # the uniform mesh reactor when ``applyStateToOriginal`` to called.
        # This prevents clearing out data on the original reactor that should
        # be preserved since no changes were applied.
        self._cachedReactorCoreParamData = {}

        self._nonUniformMeshFlags = None
        self._hasNonUniformAssems = None
        self._nonUniformAssemStorage = set()
        self._minimumMeshSize = None

        if cs is not None:
            self._nonUniformMeshFlags = [Flags.fromStringIgnoreErrors(f) for f in cs["nonUniformAssemFlags"]]
            self._hasNonUniformAssems = any(self._nonUniformMeshFlags)
            self._minimumMeshSize = cs[CONF_UNIFORM_MESH_MINIMUM_SIZE]

    def convert(self, r=None):
        """
        Create a new reactor core with a uniform mesh.

        .. impl:: Make a copy of the reactor where the new core has a uniform axial mesh.
            :id: I_ARMI_UMC
            :implements: R_ARMI_UMC

            Given a source Reactor, ``r``, as input and when ``_hasNonUniformAssems`` is ``False``,
            a new Reactor is created in ``initNewReactor``. This new Reactor contains copies of select
            information from the input source Reactor (e.g., Operator, Blueprints, cycle, timeNode, etc).
            The uniform mesh to be applied to the new Reactor is calculated in ``_generateUniformMesh``
            (see :need:`I_ARMI_UMC_NON_UNIFORM` and :need:`I_ARMI_UMC_MIN_MESH`). New assemblies with this
            uniform mesh are created in ``_buildAllUniformAssemblies`` and added to the new Reactor.
            Core-level parameters are then mapped from the source Reactor to the new Reactor in
            ``_mapStateFromReactorToOther``. Finally, the core-wide axial mesh is updated on the new Reactor
            via ``updateAxialMesh``.


        .. impl:: Map select parameters from composites on the original mesh to the new mesh.
            :id: I_ARMI_UMC_PARAM_FORWARD
            :implements: R_ARMI_UMC_PARAM_FORWARD

            In ``_mapStateFromReactorToOther``, Core-level parameters are mapped from the source Reactor
            to the new Reactor. If requested, block-level parameters can be mapped using an averaging
            equation as described in ``setAssemblyStateFromOverlaps``.
        """
        if r is None:
            raise ValueError(f"No reactor provided in {self}")

        completeStartTime = timer()
        self._sourceReactor = r
        self._setParamsToUpdate("in")

        # Here we are taking a short cut to homogenizing the core by only focusing on the
        # core assemblies that need to be homogenized. This will have a large speed up
        # since we don't have to create an entirely new reactor perform the data mapping.
        if self._hasNonUniformAssems:
            runLog.extra(
                f"Replacing non-uniform assemblies in reactor {r}, "
                "with assemblies whose axial mesh is uniform with "
                f"the core's reference assembly mesh: {r.core.refAssem.getAxialMesh()}"
            )
            self.convReactor = self._sourceReactor
            self.convReactor.core.updateAxialMesh()
            for assem in self.convReactor.core.getAssemblies(self._nonUniformMeshFlags):
                homogAssem = self.makeAssemWithUniformMesh(
                    assem,
                    self.convReactor.core.p.axialMesh[1:],
                    paramMapper=self.paramMapper,
                    includePinCoordinates=self.includePinCoordinates,
                )
                homogAssem.spatialLocator = assem.spatialLocator

                # Remove this assembly from the core and add it to the temporary storage
                # so that it can be replaced with the homogenized assembly. Note that we
                # do not call `removeAssembly()` because this will delete the core
                # assembly from existence rather than only stripping its spatialLocator.
                if assem.spatialLocator in self.convReactor.core.childrenByLocator:
                    self.convReactor.core.childrenByLocator.pop(assem.spatialLocator)
                self.convReactor.core.remove(assem)
                self.convReactor.core.assembliesByName.pop(assem.getName(), None)
                for b in assem:
                    self.convReactor.core.blocksByName.pop(b.getName(), None)

                assem.setName(assem.getName() + self._TEMP_STORAGE_NAME_SUFFIX)
                self._nonUniformAssemStorage.add(assem)
                self.convReactor.core.add(homogAssem)
        else:
            runLog.extra(f"Building copy of {r} with a uniform axial mesh.")
            self.convReactor = self.initNewReactor(r, self._cs)
            self._generateUniformMesh(minimumMeshSize=self._minimumMeshSize)
            self._buildAllUniformAssemblies()
            self._mapStateFromReactorToOther(self._sourceReactor, self.convReactor, mapBlockParams=False)
            self._newAssembliesAdded = self.convReactor.core.getAssemblies()

        self.convReactor.core.updateAxialMesh()
        self._checkConversion()
        completeEndTime = timer()
        runLog.extra(f"Reactor core conversion time: {completeEndTime - completeStartTime} seconds")

    def _generateUniformMesh(self, minimumMeshSize):
        """
        Generate a common axial mesh to use for uniform mesh conversion.

        Parameters
        ----------
        minimumMeshSize : float, required
            Minimum allowed separation between axial mesh points in cm
        """
        generator = UniformMeshGenerator(self._sourceReactor, minimumMeshSize=minimumMeshSize)
        generator.generateCommonMesh()
        self._uniformMesh = generator._commonMesh

    @staticmethod
    def initNewReactor(sourceReactor, cs):
        """Build a new, yet empty, reactor with the same settings as sourceReactor.

        Parameters
        ----------
        sourceReactor : :py:class:`Reactor <armi.reactor.reactors.Reactor>`
            original reactor object to be copied
        cs: Setting
            Complete settings object
        """
        # developer note: deepcopy on the blueprint object ensures that all relevant blueprints
        # attributes are set. Simply calling blueprints.loadFromCs() just initializes
        # a blueprints object and may not set all necessary attributes. E.g., some
        # attributes are set when assemblies are added in coreDesign.construct(), however
        # since we skip that here, they never get set; therefore the need for the deepcopy.
        bp = copy.deepcopy(sourceReactor.blueprints)
        newReactor = Reactor(sourceReactor.name, bp)
        coreDesign = bp.systemDesigns["core"]

        coreDesign.construct(cs, bp, newReactor, loadComps=False)
        newReactor.p.cycle = sourceReactor.p.cycle
        newReactor.p.timeNode = sourceReactor.p.timeNode
        newReactor.p.maxAssemNum = sourceReactor.p.maxAssemNum
        newReactor.core.p.coupledIteration = sourceReactor.core.p.coupledIteration
        newReactor.core.lib = sourceReactor.core.lib
        newReactor.core.setPitchUniform(sourceReactor.core.getAssemblyPitch())
        newReactor.o = sourceReactor.o  # This is needed later for geometry transformation

        # check if the sourceReactor has been modified from the blueprints
        if sourceReactor.core.isFullCore and not newReactor.core.isFullCore:
            _geometryConverter = newReactor.core.growToFullCore(cs)

        return newReactor

    def applyStateToOriginal(self):
        """
        Apply the state of the converted reactor back to the original reactor,
        mapping number densities and block parameters.

        .. impl:: Map select parameters from composites on the new mesh to the original mesh.
            :id: I_ARMI_UMC_PARAM_BACKWARD
            :implements: R_ARMI_UMC_PARAM_BACKWARD

            To ensure that the parameters on the original Reactor are from the converted Reactor,
            the first step is to clear the Reactor-level parameters on the original Reactor
            (see ``_clearStateOnReactor``). ``_mapStateFromReactorToOther`` is then called
            to map Core-level parameters and, optionally, averaged Block-level parameters
            (see :need:`I_ARMI_UMC_PARAM_FORWARD`).
        """
        runLog.extra(f"Applying uniform neutronics results from {self.convReactor} to {self._sourceReactor}")
        completeStartTime = timer()

        # map the block parameters back to the non-uniform assembly
        self._setParamsToUpdate("out")

        # If we have non-uniform mesh assemblies then we need to apply a
        # different approach to undo the geometry transformations on an
        # assembly by assembly basis.
        if self._hasNonUniformAssems:
            for assem in self._sourceReactor.core.getAssemblies(self._nonUniformMeshFlags):
                for storedAssem in self._nonUniformAssemStorage:
                    if storedAssem.getName() == assem.getName() + self._TEMP_STORAGE_NAME_SUFFIX:
                        self.setAssemblyStateFromOverlaps(
                            assem,
                            storedAssem,
                            self.paramMapper,
                            mapNumberDensities=False,
                            calcReactionRates=self.calcReactionRates,
                        )

                        # Remove the stored assembly from the temporary storage list
                        # and replace the current assembly with it.
                        storedAssem.spatialLocator = assem.spatialLocator
                        storedAssem.setName(assem.getName())
                        self._nonUniformAssemStorage.remove(storedAssem)
                        self._sourceReactor.core.removeAssembly(assem, discharge=False)
                        self._sourceReactor.core.add(storedAssem)
                        break
                else:
                    runLog.error(
                        f"No assembly matching name {assem.getName()} "
                        f"was found in the temporary storage list. {assem} "
                        "will persist as an axially unified assembly. "
                        "This is likely not intended."
                    )

            self._sourceReactor.core.updateAxialMesh()
        else:
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
        runLog.extra(f"Parameter remapping time: {completeEndTime - completeStartTime} seconds")

    @staticmethod
    def makeAssemWithUniformMesh(
        sourceAssem,
        newMesh,
        paramMapper=None,
        mapNumberDensities=True,
        includePinCoordinates=False,
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
        paramMapper : ParamMapper
            Object that contains list of parameters to be mapped and has methods for mapping
        mapNumberDensities : bool, optional
            If True, number densities will be mapped from the source assembly to the new assembly.
            This is True by default, but this can be set to False to only map block-level parameters if
            the names are provided in `blockParamNames`. It can be useful to set this to False in circumstances
            where the ``setNumberDensitiesFromOverlaps`` does not conserve mass and for some edge cases.
            This can show up in specific instances with moving meshes (i.e., control rods) in some applications.
            In those cases, the mapping of number densities can be treated independent of this more general
            implementation.

        See Also
        --------
        setAssemblyStateFromOverlaps
            This can be used to reverse the number density and parameter mappings
            between two assemblies.
        """
        newAssem = UniformMeshGeometryConverter._createNewAssembly(sourceAssem)
        newAssem.p.assemNum = sourceAssem.p.assemNum
        runLog.debug(f"Creating a uniform mesh of {newAssem}")
        bottom = 0.0

        def checkPriorityFlags(b):
            """
            Check that a block has the flags that are prioritized for uniform mesh conversion.

            Also check that it's not different type of block that is a superset of the
            priority flags, like "Flags.FUEL | Flags.PLENUM"
            """
            priorityFlags = [Flags.FUEL, Flags.CONTROL, Flags.SHIELD | Flags.RADIAL]
            return b.hasFlags(priorityFlags) and not b.hasFlags(Flags.PLENUM)

        for topMeshPoint in newMesh:
            overlappingBlockInfo = sourceAssem.getBlocksBetweenElevations(bottom, topMeshPoint)
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
            #     appears for blocks with FUEL, CONTROL, or SHIELD|RADIAL flags in this domain.
            #     2. Determine the single XS type that represents the largest fraction
            #     of the total height of FUEL, CONTROL, or SHIELD|RADIAL cross sections.
            #     3. Use the first block of the majority XS type as the source block.
            #     4. If none of the special block types are present(fuelOrAbsorber == False),
            #     use the xs type that represents the largest fraction of the destination block.
            typeHeight = collections.defaultdict(float)
            blocks = [b for b, _h in overlappingBlockInfo]
            fuelOrAbsorber = any(checkPriorityFlags(b) for b in blocks)
            for b, h in overlappingBlockInfo:
                if checkPriorityFlags(b) or not fuelOrAbsorber:
                    typeHeight[b.p.xsType] += h

            sourceBlock = None
            # xsType is the one with the majority of overlap
            xsType = next(k for k, v in typeHeight.items() if v == max(typeHeight.values()))
            for b in blocks:
                if checkPriorityFlags(b) or not fuelOrAbsorber:
                    if b.p.xsType == xsType:
                        sourceBlock = b
                        break

            if len(typeHeight) > 1:
                if sourceBlock:
                    totalHeight = sum(typeHeight.values())
                    runLog.debug(
                        f"Multiple XS types exist between {bottom} and {topMeshPoint}. "
                        f"Using the XS type from the largest region, {xsType}"
                    )
                    for xs, h in typeHeight.items():
                        heightFrac = h / totalHeight
                        runLog.debug(f"XSType {xs}: {heightFrac:.4f}")

            block = sourceBlock.createHomogenizedCopy(includePinCoordinates)
            block.p.xsType = xsType
            block.setHeight(topMeshPoint - bottom)
            block.p.axMesh = 1
            newAssem.add(block)
            bottom = topMeshPoint

        newAssem.reestablishBlockOrder()
        newAssem.calculateZCoords()

        UniformMeshGeometryConverter.setAssemblyStateFromOverlaps(
            sourceAssem,
            newAssem,
            paramMapper,
            mapNumberDensities,
        )
        return newAssem

    @staticmethod
    def setAssemblyStateFromOverlaps(
        sourceAssembly,
        destinationAssembly,
        paramMapper,
        mapNumberDensities=False,
        calcReactionRates=False,
    ):
        r"""
        Set state data (i.e., number densities and block-level parameters) on a assembly based on a source
        assembly with a different axial mesh.

        This solves an averaging equation from the source to the destination.

        .. math::
            <P> = \frac{\int_{z_1}^{z_2} P(z) dz}{\int_{z_1}^{z_2} dz}

        which can be solved piecewise for z-coordinates along the source blocks.

        Notes
        -----
        * If the parameter is volume integrated (e.g., flux, linear power)
          then calculate the fractional contribution from the source block.
        * If the parameter is not volume integrated (e.g., volumetric reaction rate)
          then calculate the fraction contribution on the destination block.
          This smears the parameter over the destination block.

        Parameters
        ----------
        sourceAssembly : Assembly
            assem that has the state
        destinationAssembly : Assembly
            assem that has is getting the state from sourceAssembly
        paramMapper : ParamMapper
            Object that contains list of parameters to be mapped and has methods for mapping
        mapNumberDensities : bool, optional
            If True, number densities will be mapped from the source assembly to the destination assembly.
            This is True by default, but this can be set to False to only map block-level parameters if
            the names are provided in `blockParamNames`. It can be useful to set this to False in circumstances
            where the ``setNumberDensitiesFromOverlaps`` does not conserve mass and for some edge cases.
            This can show up in specific instances with moving meshes (i.e., control rods) in some applications.
            In those cases, the mapping of number densities can be treated independent of this more general
            implementation.
        calcReactionRates : bool, optional
            If True, the neutron reaction rates will be calculated on each block within the destination
            assembly. Note that this will skip the reaction rate calculations for a block if it does
            not contain a valid multi-group flux.

        See Also
        --------
        setNumberDensitiesFromOverlaps : does this but does smarter caching for number densities.
        """
        for destBlock in destinationAssembly:
            zLower = destBlock.p.zbottom
            zUpper = destBlock.p.ztop
            destinationBlockHeight = destBlock.getHeight()
            # Determine which blocks in the uniform mesh source assembly are
            # within the lower and upper bounds of the destination block.
            sourceBlocksInfo = sourceAssembly.getBlocksBetweenElevations(zLower, zUpper)

            if abs(zUpper - zLower) < 1e-6 and not sourceBlocksInfo:
                continue
            elif not sourceBlocksInfo:
                raise ValueError(
                    "An error occurred when attempting to map to the "
                    f"results from {sourceAssembly} to {destinationAssembly}. "
                    f"No blocks in {sourceAssembly} exist between the axial "
                    f"elevations of {zLower:<12.5f} cm and {zUpper:<12.5f} cm. "
                    "This a major bug in the uniform mesh converter that should "
                    "be reported to the developers."
                )

            if mapNumberDensities:
                setNumberDensitiesFromOverlaps(destBlock, sourceBlocksInfo)

            # Iterate over each of the blocks that were found in the uniform mesh
            # source assembly within the lower and upper bounds of the destination
            # block and perform the parameter mapping.
            if paramMapper is not None:
                updatedDestVals = collections.defaultdict(float)
                for sourceBlock, sourceBlockOverlapHeight in sourceBlocksInfo:
                    sourceBlockVals = paramMapper.paramGetter(
                        sourceBlock,
                        paramMapper.blockParamNames,
                    )
                    sourceBlockHeight = sourceBlock.getHeight()

                    for paramName, sourceBlockVal in zip(paramMapper.blockParamNames, sourceBlockVals):
                        if sourceBlockVal is None:
                            continue
                        if paramMapper.isPeak[paramName]:
                            updatedDestVals[paramName] = max(sourceBlockVal, updatedDestVals[paramName])
                        else:
                            if paramMapper.isVolIntegrated[paramName]:
                                denominator = sourceBlockHeight
                            else:
                                denominator = destinationBlockHeight
                            integrationFactor = sourceBlockOverlapHeight / denominator
                            updatedDestVals[paramName] += sourceBlockVal * integrationFactor

                paramMapper.paramSetter(destBlock, updatedDestVals.values(), updatedDestVals.keys())

        # If requested, the reaction rates will be calculated based on the
        # mapped neutron flux and the XS library.
        if calcReactionRates:
            if paramMapper is None:
                runLog.warning(
                    f"Reaction rates requested for {destinationAssembly}, but no ParamMapper "
                    "was provided to setAssemblyStateFromOverlaps(). Reaction rates calculated "
                    "will reflect the intended result without new parameter values being mapped in."
                )
            core = sourceAssembly.getAncestor(lambda c: isinstance(c, Core))
            if core is not None:
                UniformMeshGeometryConverter._calculateReactionRates(
                    lib=core.lib, keff=core.p.keff, assem=destinationAssembly
                )
            else:
                runLog.warning(
                    f"Reaction rates requested for {destinationAssembly}, but no core object "
                    "exists. This calculation will be skipped.",
                    single=True,
                    label="Block reaction rate calculation skipped due to insufficient multi-group flux data.",
                )

    def clearStateOnAssemblies(assems, blockParamNames=None, cache=True):
        """
        Clears the parameter state of blocks for a list of assemblies.

        Parameters
        ----------
        assems : List[`Assembly <armi.reactor.assemblies.Assembly>`]
            List of assembly objects.
        blockParamNames : List[str], optional
            A list of block parameter names to clear on the given assemblies.
        cache : bool
            If True, the block parameters that were cleared are stored
            and returned as a dictionary of ``{b: {param1: val1, param2: val2}, b2: {...}, ...}``
        """
        if blockParamNames is None:
            blockParamNames = []

        cachedBlockParamData = collections.defaultdict(dict)

        if not assems:
            return cachedBlockParamData

        blocks = []
        for a in assems:
            blocks.extend(a)
        firstBlock = blocks[0]
        for paramName in blockParamNames:
            defaultValue = firstBlock.p.pDefs[paramName].default
            for b in blocks:
                if cache:
                    cachedBlockParamData[b][paramName] = b.p[paramName]
                b.p[paramName] = defaultValue

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
        existingFiles = glob.glob(f"{self.convReactor.core.name}AssemblyTypes" + "*" + ".png")
        # This loops over the existing files for the assembly types outputs
        # and makes a unique integer value so that plots are not overwritten. The
        # regular expression here captures the first integer as AssemblyTypesX and
        # then ensures that the numbering in the next enumeration below is 1 above that.
        for f in existingFiles:
            newStart = int(re.search(r"\d+", f).group())
            if newStart > start:
                start = newStart
        for plotNum, assemBatch in enumerate(iterables.chunk(assemsToPlot, 6), start=start + 1):
            assemPlotName = f"{self.convReactor.core.name}AssemblyTypes{plotNum}-rank{armi.MPI_RANK}.png"
            plotting.plotAssemblyTypes(
                assemBatch,
                assemPlotName,
                maxAssems=6,
                showBlockAxMesh=True,
            )

    def reset(self):
        """Clear out stored attributes and reset the global assembly number."""
        self._cachedReactorCoreParamData = {}
        super().reset()

    def _setParamsToUpdate(self, direction):
        """
        Activate conversion of the specified parameters.

        Notes
        -----
        The parameters mapped into and out of the uniform mesh will vary depending on
        the physics kernel using the uniform mesh. The parameters to be mapped in each
        direction are defined as a class attribute. New options can be created by extending
        the base class with different class attributes for parameters to map, and applying
        special modifications to these categorized lists with the `_setParamsToUpdate` method.

        This base class `_setParamsToUpdate()` method should not be called, so this raises a
        NotImplementedError.

        Parameters
        ----------
        direction : str
            "in" or "out". The direction of mapping; "in" to the uniform mesh assembly, or "out" of it.
            Different parameters are mapped in each direction.

        Raises
        ------
        NotImplementedError
        """
        raise NotImplementedError

    def _checkConversion(self):
        """Perform checks to ensure conversion occurred properly."""
        pass

    @staticmethod
    def _createNewAssembly(sourceAssembly):
        a = sourceAssembly.__class__(sourceAssembly.getType())
        a.spatialGrid = grids.AxialGrid.fromNCells(len(sourceAssembly))
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
            f"Creating new assemblies from {self._sourceReactor.core} with a uniform mesh of {self._uniformMesh}"
        )
        for sourceAssem in self._sourceReactor.core:
            newAssem = self.makeAssemWithUniformMesh(
                sourceAssem,
                self._uniformMesh,
                paramMapper=self.paramMapper,
                includePinCoordinates=self.includePinCoordinates,
            )
            src = sourceAssem.spatialLocator
            newLoc = self.convReactor.core.spatialGrid[src.i, src.j, 0]
            self.convReactor.core.add(newAssem, newLoc)

    def _clearStateOnReactor(self, reactor, cache):
        """
        Delete existing state that will be updated so they don't increment.

        The summations should start at zero but will happen for all overlaps.
        """
        runLog.debug("Clearing params from source reactor that will be converted.")
        for rp in self.paramMapper.reactorParamNames:
            if cache:
                self._cachedReactorCoreParamData[rp] = reactor.core.p[rp]
            reactor.core.p[rp] = 0.0

    def _mapStateFromReactorToOther(self, sourceReactor, destReactor, mapNumberDensities=False, mapBlockParams=True):
        """
        Map parameters from one reactor to another.

        Notes
        -----
        This is a basic parameter mapping routine that can be used by most sub-classes.
        If special mapping logic is required, this method can be defined on sub-classes as necessary.
        """
        # Map reactor core parameters
        for paramName in self.paramMapper.reactorParamNames:
            # Check if the source reactor has a value assigned for this
            # parameter and if so, then apply it. Otherwise, revert back to
            # the original value.
            if sourceReactor.core.p[paramName] is not None or paramName not in self._cachedReactorCoreParamData:
                val = sourceReactor.core.p[paramName]
            else:
                val = self._cachedReactorCoreParamData[paramName]
            destReactor.core.p[paramName] = val

        if mapBlockParams:
            # Map block parameters
            for aSource in sourceReactor.core:
                aDest = destReactor.core.getAssemblyByName(aSource.getName())
                UniformMeshGeometryConverter.setAssemblyStateFromOverlaps(
                    aSource,
                    aDest,
                    self.paramMapper,
                    mapNumberDensities,
                    calcReactionRates=False,
                )

            # If requested, the reaction rates will be calculated based on the
            # mapped neutron flux and the XS library.
            if self.calcReactionRates:
                self._calculateReactionRatesEfficient(destReactor.core, sourceReactor.core.p.keff)

        # Clear the cached data after it has been mapped to prevent issues with
        # holding on to block data long-term.
        self._cachedReactorCoreParamData = {}

    @staticmethod
    def _calculateReactionRatesEfficient(core, keff):
        """
        First, sort blocks into groups by XS type. Then, we just need to grab micros for each XS type once.

        Iterate over list of blocks with the given XS type; calculate reaction rates for these blocks
        """
        xsTypeGroups = collections.defaultdict(list)
        for b in core.iterBlocks():
            xsTypeGroups[b.getMicroSuffix()].append(b)

        for xsID, blockList in xsTypeGroups.items():
            nucSet = set()
            for b in blockList:
                nucSet.update(nuc for nuc, ndens in b.getNumberDensities().items() if ndens > 0.0)
            xsNucDict = {nuc: core.lib.getNuclide(nuc, xsID) for nuc in nucSet}
            UniformMeshGeometryConverter._calcReactionRatesBlockList(blockList, keff, xsNucDict)

    @staticmethod
    def _calculateReactionRates(lib, keff, assem):
        """
        Calculates the neutron reaction rates on the given assembly.

        Notes
        -----
        If a block in the assembly does not contain any multi-group flux
        than the reaction rate calculation for this block will be skipped.
        """
        from armi.physics.neutronics.globalFlux import globalFluxInterface

        for b in assem:
            # Checks if the block has a multi-group flux defined and if it
            # does not then this will skip the reaction rate calculation. This
            # is captured by the TypeError, due to a `NoneType` divide by float
            # error.
            try:
                b.getMgFlux()
            except TypeError:
                continue
            globalFluxInterface.calcReactionRates(b, keff, lib)

    @staticmethod
    def _calcReactionRatesBlockList(objList, keff, xsNucDict):
        r"""
        Compute 1-group reaction rates for the objects in objList (usually a block).

        :meta public:

        .. impl:: Return the reaction rates for a given ArmiObject
            :id: I_ARMI_FLUX_RX_RATES_BY_XS_ID
            :implements: R_ARMI_FLUX_RX_RATES

            This is an alternative implementation of :need:`I_ARMI_FLUX_RX_RATES` that
            is more efficient when computing reaction rates for a large set of blocks
            that share a common set of microscopic cross sections.

            For more detail on the reation rate calculations, see :need:`I_ARMI_FLUX_RX_RATES`.

        Parameters
        ----------
        objList : List[Block]
            The list of objects to compute reaction rates on. Notionally this could be upgraded to be
            any kind of ArmiObject but with params defined as they are it currently is only
            implemented for a block.

        keff : float
            The keff of the core. This is required to get the neutron production rate correct
            via the neutron balance statement (since nuSigF has a 1/keff term).

        xsNucDict: Dict[str, XSNuclide]
            Microscopic cross sections to use in computing the reaction rates. Keys are
            nuclide names (e.g., "U235") and values are the associated XSNuclide objects
            from the cross section library, which contain the microscopic cross section
            data for a given nuclide in the current cross section group.
        """
        for obj in objList:
            rate = collections.defaultdict(float)

            numberDensities = obj.getNumberDensities()
            try:
                mgFlux = np.array(obj.getMgFlux())
            except TypeError:
                continue

            for nucName, numberDensity in numberDensities.items():
                if numberDensity == 0.0:
                    continue
                nucRate = collections.defaultdict(float)

                micros = xsNucDict[nucName].micros

                # absorption is fission + capture (no n2n here)
                for name in RX_ABS_MICRO_LABELS:
                    volumetricRR = numberDensity * mgFlux.dot(micros[name])
                    nucRate["rateAbs"] += volumetricRR
                    if name != "fission":
                        nucRate["rateCap"] += volumetricRR
                    else:
                        nucRate["rateFis"] += volumetricRR
                        # scale nu by keff.
                        nusigmaF = micros["fission"] * micros.neutronsPerFission
                        nucRate["rateProdFis"] += numberDensity * mgFlux.dot(nusigmaF) / keff

                nucRate["rateProdN2n"] += 2.0 * numberDensity * mgFlux.dot(micros.n2n)

                for rx in RX_PARAM_NAMES:
                    if nucRate[rx]:
                        rate[rx] += nucRate[rx]

            for paramName in RX_PARAM_NAMES:
                obj.p[paramName] = rate[paramName]  # put in #/cm^3/s

            if rate["rateFis"] > 0.0:
                fuelVolFrac = obj.getComponentAreaFrac(Flags.FUEL)
                obj.p.fisDens = np.nan if fuelVolFrac == 0 else rate["rateFis"] / fuelVolFrac
                obj.p.fisDensHom = rate["rateFis"]
            else:
                obj.p.fisDens = 0.0
                obj.p.fisDensHom = 0.0

    def updateReactionRates(self):
        """
        Update reaction rates on converted assemblies.

        Notes
        -----
        In some cases, we may want to read flux into a converted reactor from a
        pre-existing physics output instead of mapping it in from the pre-conversion
        source reactor. This method can be called after reading that flux in to
        calculate updated reaction rates derived from that flux.
        """
        if self._hasNonUniformAssems:
            for assem in self.convReactor.core.getAssemblies(self._nonUniformMeshFlags):
                self._calculateReactionRates(self.convReactor.core.lib, self.convReactor.core.p.keff, assem)
        else:
            self._calculateReactionRatesEfficient(self.convReactor.core, self.convReactor.core.p.keff)


class NeutronicsUniformMeshConverter(UniformMeshGeometryConverter):
    """
    A uniform mesh converter that specifically maps neutronics parameters.

    Notes
    -----
    This uniform mesh converter is intended for setting up an eigenvalue
    (fission-source) neutronics solve. There are no block parameters that need
    to be mapped in for a basic eigenvalue calculation, just number densities.
    The results of the calculation are mapped out (i.e., back to the non-uniform
    mesh). The results mapped out include things like flux, power, and reaction
    rates.

    .. warning::
        If a parameter is calculated by a physics solver while the reactor is in its
        converted (uniform mesh) state, that parameter *must* be included in the list
        of `reactorParamNames` or `blockParamNames` to be mapped back to the non-uniform
        reactor; otherwise, it will be lost. These lists are defined through the
        `_setParamsToUpdate` method, which uses the `reactorParamMappingCategories` and
        `blockParamMappingCategories` attributes and applies custom logic to create a list of
        parameters to be mapped in each direction.
    """

    reactorParamMappingCategories = {
        "in": [parameters.Category.neutronics],
        "out": [parameters.Category.neutronics],
    }
    blockParamMappingCategories = {
        "in": [],
        "out": [
            parameters.Category.detailedAxialExpansion,
            parameters.Category.multiGroupQuantities,
            parameters.Category.pinQuantities,
        ],
    }

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

    def _setParamsToUpdate(self, direction):
        """
        Activate conversion of the specified parameters.

        Notes
        -----
        For the fission-source neutronics calculation, there are no block parameters
        that need to be mapped in. This function applies additional filters to the
        list of categories defined in `blockParamMappingCategories[out]` to avoid mapping
        out cumulative parameters like DPA or burnup. These parameters should not
        exist on the neutronics uniform mesh assembly anyway, but this filtering
        provides an added layer of safety to prevent data from being inadvertently
        overwritten.

        Parameters
        ----------
        direction : str
            "in" or "out". The direction of mapping; "in" to the uniform mesh assembly, or "out" of it.
            Different parameters are mapped in each direction.
        """
        reactorParamNames = []
        blockParamNames = []

        for category in self.reactorParamMappingCategories[direction]:
            reactorParamNames.extend(self._sourceReactor.core.p.paramDefs.inCategory(category).names)
        b = self._sourceReactor.core.getFirstBlock()
        excludedCategories = [parameters.Category.gamma]
        if direction == "out":
            excludedCategories.append(parameters.Category.cumulative)
            excludedCategories.append(parameters.Category.cumulativeOverCycle)
        excludedParamNames = []
        for category in excludedCategories:
            excludedParamNames.extend(b.p.paramDefs.inCategory(category).names)
        for category in self.blockParamMappingCategories[direction]:
            blockParamNames.extend(
                [name for name in b.p.paramDefs.inCategory(category).names if name not in excludedParamNames]
            )
        if direction == "in":
            # initial heavy metal masses are needed to calculate burnup in MWd/kg
            blockParamNames.extend(HEAVY_METAL_PARAMS)

        # remove any duplicates (from parameters that have multiple categories)
        blockParamNames = list(set(blockParamNames))
        self.paramMapper = ParamMapper(reactorParamNames, blockParamNames, b)


class GammaUniformMeshConverter(UniformMeshGeometryConverter):
    """
    A uniform mesh converter that specifically maps gamma parameters.

    Notes
    -----
    This uniform mesh converter is intended for setting up a fixed-source gamma transport solve.
    Some block parameters from the neutronics solve, such as `b.p.mgFlux`, may need to be mapped
    into the uniform mesh reactor so that the gamma source can be calculated by the ARMI plugin
    performing gamma transport. Parameters that are updated with gamma transport results, such
    as `powerGenerated`, `powerNeutron`, and `powerGamma`, need to be mapped back to the
    non-uniform reactor.

    .. warning::
        If a parameter is calculated by a physics solver while the reactor is in its
        converted (uniform mesh) state, that parameter *must* be included in the list
        of `reactorParamNames` or `blockParamNames` to be mapped back to the non-uniform
        reactor; otherwise, it will be lost. These lists are defined through the
        `_setParamsToUpdate` method, which uses the `reactorParamMappingCategories` and
        `blockParamMappingCategories` attributes and applies custom logic to create a list of
        parameters to be mapped in each direction.
    """

    reactorParamMappingCategories = {
        "in": [parameters.Category.neutronics],
        "out": [parameters.Category.neutronics],
    }
    blockParamMappingCategories = {
        "in": [
            parameters.Category.multiGroupQuantities,
        ],
        "out": [
            parameters.Category.gamma,
            parameters.Category.neutronics,
        ],
    }

    def _setParamsToUpdate(self, direction):
        """
        Activate conversion of the specified parameters.

        Notes
        -----
        For gamma transport, only a small subset of neutronics parameters need to be
        mapped out. The set is defined in this method. There are conditions on the
        output blockParamMappingCategories: only non-cumulative, gamma parameters are mapped out.
        This avoids numerical diffusion of cumulative parameters or those created by the
        initial eigenvalue neutronics solve from being mapped in both directions by the
        mesh converter for the fixed-source gamma run.

        Parameters
        ----------
        direction : str
            "in" or "out". The direction of mapping; "in" to the uniform mesh assembly, or "out" of it.
            Different parameters are mapped in each direction.
        """
        reactorParamNames = []
        blockParamNames = []

        for category in self.reactorParamMappingCategories[direction]:
            reactorParamNames.extend(self._sourceReactor.core.p.paramDefs.inCategory(category).names)
        b = self._sourceReactor.core.getFirstBlock()
        if direction == "out":
            excludeList = (
                b.p.paramDefs.inCategory(parameters.Category.cumulative).names
                + b.p.paramDefs.inCategory(parameters.Category.cumulativeOverCycle).names
            )
        else:
            excludeList = b.p.paramDefs.inCategory(parameters.Category.gamma).names
        for category in self.blockParamMappingCategories[direction]:
            blockParamNames.extend(
                [name for name in b.p.paramDefs.inCategory(category).names if name not in excludeList]
            )

        # remove any duplicates (from parameters that have multiple categories)
        blockParamNames = list(set(blockParamNames))
        self.paramMapper = ParamMapper(reactorParamNames, blockParamNames, b)


class ParamMapper:
    """
    Utility for parameter setters/getters that can be used when
    transferring data from one assembly to another during the mesh
    conversion process. Stores some data like parameter defaults and
    properties to save effort of accessing paramDefs many times for
    the same data.
    """

    def __init__(self, reactorParamNames: list[str], blockParamNames: list[str], b: "Block"):
        """
        Initialize the list of parameter defaults.

        The ParameterDefinitionCollection lookup is very slow, so this we do it once
        and store it as a hashed list.
        """
        self.paramDefaults = {paramName: b.p.pDefs[paramName].default for paramName in blockParamNames}

        # Determine which parameters are volume integrated
        self.isVolIntegrated = {
            paramName: b.p.paramDefs[paramName].atLocation(parameters.ParamLocation.VOLUME_INTEGRATED)
            for paramName in blockParamNames
        }
        # determine which parameters are peak/max
        # Unfortunately, these parameters don't tell you WHERE in the block the peak
        # value occurs. So when mapping block parameters in setAssemblyStateFromOverlaps(),
        # we will just grab the maximum value over all of the source blocks. This effectively
        # assumes that all of the source blocks overlap 100% with the destination block,
        # although this is rarely actually the case.
        self.isPeak = {
            paramName: b.p.paramDefs[paramName].atLocation(parameters.ParamLocation.MAX)
            for paramName in blockParamNames
        }

        self.reactorParamNames = reactorParamNames
        self.blockParamNames = blockParamNames

    def paramSetter(self, block: "Block", vals: list, paramNames: list[str]):
        """Sets block parameter data."""
        for paramName, val in zip(paramNames, vals):
            # Skip setting None values.
            if val is None:
                continue

            if isinstance(val, (tuple, list, np.ndarray)):
                self._arrayParamSetter(block, [val], [paramName])
            else:
                self._scalarParamSetter(block, [val], [paramName])

    def paramGetter(self, block: "Block", paramNames: list[str]):
        """Returns block parameter values as an array in the order of the parameter names given."""
        paramVals = []
        symmetryFactor = block.getSymmetryFactor()
        for paramName in paramNames:
            multiplier = self.getFactorSymmetry(paramName, symmetryFactor)
            val = block.p[paramName]
            # list-like should be treated as a numpy array
            if val is None:
                paramVals.append(val)
            elif isinstance(val, (tuple, list, np.ndarray)):
                paramVals.append(np.array(val) * multiplier if len(val) > 0 else None)
            else:
                paramVals.append(val * multiplier)

        return np.array(paramVals, dtype=object)

    def _scalarParamSetter(self, block: "Block", vals: list, paramNames: list[str]):
        """Assigns a set of float/integer/string values to a given set of parameters on a block."""
        symmetryFactor = block.getSymmetryFactor()
        for paramName, val in zip(paramNames, vals):
            if val is None:
                block.p[paramName] = val
            else:
                block.p[paramName] = val / self.getFactorSymmetry(paramName, symmetryFactor)

    def _arrayParamSetter(self, block: "Block", arrayVals: list, paramNames: list[str]):
        """Assigns a set of list/array values to a given set of parameters on a block."""
        symmetryFactor = block.getSymmetryFactor()
        for paramName, vals in zip(paramNames, arrayVals):
            if vals is None:
                continue
            block.p[paramName] = np.array(vals) / self.getFactorSymmetry(paramName, symmetryFactor)

    def getFactorSymmetry(self, paramName: str, symmetryFactor: int):
        """Returns the symmetry factor if the parameter is volume integrated, returns 1 otherwise."""
        if self.isVolIntegrated[paramName]:
            return symmetryFactor
        else:
            return 1


def setNumberDensitiesFromOverlaps(block, overlappingBlockInfo):
    r"""
    Set number densities on a block based on overlapping blocks.

    A conservation of number of atoms technique is used to map the non-uniform number densities onto the uniform
    neutronics mesh. When the number density of a height :math:`H` neutronics mesh block :math:`N^{\prime}` is
    being computed from one or more blocks in the ARMI mesh with number densities :math:`N_i` and
    heights :math:`h_i`, the following formula is used:

    .. math::

        N^{\prime} =  \sum_i N_i \frac{h_i}{H}
    """
    totalDensities = collections.defaultdict(float)
    block.clearNumberDensities()
    blockHeightInCm = block.getHeight()
    for overlappingBlock, overlappingHeightInCm in overlappingBlockInfo:
        heightScaling = overlappingHeightInCm / blockHeightInCm
        for nucName, numberDensity in overlappingBlock.getNumberDensities().items():
            totalDensities[nucName] += numberDensity * heightScaling
    block.setNumberDensities(dict(totalDensities))
    # Set the volume of each component in the block to `None` so that the
    # volume of each component is recomputed.
    for c in block:
        c.p.volume = None
