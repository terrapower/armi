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

r"""
Converts microscopic cross sections to macroscopic cross sections by multiplying by number density.

.. math::

    \Sigma_i = N_i \sigma_i

"""
from armi import context, interfaces, mpiActions, runLog
from armi.nuclearDataIO import xsCollections
from armi.physics.neutronics.settings import CONF_MINIMUM_NUCLIDE_DENSITY
from armi.utils import getBurnSteps, iterables


class MacroXSGenerator(mpiActions.MpiAction):
    """An action that can make macroscopic cross sections, even in parallel."""

    def __init__(
        self,
        blocks,
        lib,
        buildScatterMatrix,
        libType,
        minimumNuclideDensity=0.0,
    ):
        mpiActions.MpiAction.__init__(self)
        self.buildScatterMatrix = buildScatterMatrix
        self.libType = libType
        self.lib = lib
        self.blocks = blocks
        self.minimumNuclideDensity = minimumNuclideDensity

    def __reduce__(self):
        # Prevent blocks and lib from being broadcast by passing None to ctor. Although lib must be
        # broadcast, we need to do it explicitly to correctly deal with the default lib=None
        # argument in buildMacros(), which utilizes this action. Default arguments make things more
        # complicated.
        return (
            MacroXSGenerator,
            (
                None,
                None,
                self.buildScatterMatrix,
                self.libType,
                self.minimumNuclideDensity,
            ),
        )

    def invokeHook(self):
        # logic here gets messy due to all the default arguments in the calling method. There exists
        # a large number of permutations to be handled.
        if context.MPI_RANK == 0:
            allBlocks = self.blocks
            if allBlocks is None:
                allBlocks = self.r.core.getBlocks()

            lib = self.lib or self.r.core.lib
        else:
            allBlocks = []
            lib = None

        mc = xsCollections.MacroscopicCrossSectionCreator(
            self.buildScatterMatrix, self.minimumNuclideDensity
        )

        if context.MPI_SIZE > 1:
            myBlocks = _scatterList(allBlocks)

            lib = context.MPI_COMM.bcast(lib, root=0)

            myMacros = [
                mc.createMacrosFromMicros(lib, b, libType=self.libType)
                for b in myBlocks
            ]

            allMacros = _gatherList(myMacros)

        else:
            allMacros = [
                mc.createMacrosFromMicros(lib, b, libType=self.libType)
                for b in allBlocks
            ]

        if context.MPI_RANK == 0:
            for b, macro in zip(allBlocks, allMacros):
                b.macros = macro


class MacroXSGenerationInterface(interfaces.Interface):
    """
    Builds macroscopic cross sections on all Blocks.

    Warning
    -------
    This probably shouldn't be an interface since it has no interactXYZ methods. It should probably
    be converted to an MpiAction.
    """

    name = "macroXsGen"

    def __init__(self, r, cs):
        interfaces.Interface.__init__(self, r, cs)
        self.macrosLastBuiltAt = None
        self.minimumNuclideDensity = cs[CONF_MINIMUM_NUCLIDE_DENSITY]

    def buildMacros(
        self,
        lib=None,
        bListSome=None,
        buildScatterMatrix=True,
        libType="micros",
    ):
        """
        Builds block-level macroscopic cross sections for making diffusion equation matrices.

        This will use MPI if armi.context.MPI_SIZE > 1

        Builds G-vectors of the basic XS
        ('nGamma','fission','nalph','np','n2n','nd','nt') Builds GxG matrices
        for scatter matrices

        .. impl:: Build macroscopic cross sections for blocks.
            :id: I_ARMI_MACRO_XS
            :implements: R_ARMI_MACRO_XS

            This method builds macroscopic cross sections for a user-specified
            set of blocks using a specified microscopic neutron or gamma cross
            section library. If no blocks are specified, cross sections are
            calculated for all blocks in the core. If no library is specified,
            the existing r.core.lib is used. The basic arithmetic involved in
            generating macroscopic cross sections consists of multiplying
            isotopic number densities by isotopic microscopic cross sections and
            summing over all isotopes in a composition. The calculation is
            implemented in :py:func:`computeMacroscopicGroupConstants
            <armi.nuclearDataIO.xsCollections.computeMacroscopicGroupConstants>`.
            This method uses an :py:class:`mpiAction
            <armi.mpiActions.MpiAction>` to distribute the work of calculating
            macroscopic cross sections across the worker processes.

        Parameters
        ----------
        lib : library object , optional
            If lib is specified, then buildMacros will build macro XS using
            micro XS data from lib. If lib = None, then buildMacros will use the
            existing library self.r.core.lib. If that does not exist, then
            buildMacros will use a new nuclearDataIO.ISOTXS object.

        buildScatterMatrix : Boolean, optional
            If True, all macro XS will be built, including the time-consuming
            scatter matrix. If False, only the macro XS that are needed for
            fluxRecon.computePinMGFluxAndPower will be built. These include
            'transport', 'fission', and a few others. No ng x ng matrices (such
            as 'scatter' or 'chi') will be built. Essentially, this option saves
            huge runtime for the fluxRecon module.

        libType : str, optional
            The block attribute containing the desired microscopic XS for this
            block: either "micros" for neutron XS or "gammaXS" for gamma XS.
        """
        cycle = self.r.p.cycle
        burnSteps = getBurnSteps(self.cs)
        self.macrosLastBuiltAt = (
            sum([burnSteps[i] + 1 for i in range(cycle)]) + self.r.p.timeNode
        )

        runLog.important("Building macro XS")
        xsGen = MacroXSGenerator(
            bListSome,
            lib,
            buildScatterMatrix,
            libType,
            self.minimumNuclideDensity,
        )
        xsGen.broadcast()
        xsGen.invoke(self.o, self.r, self.cs)


def _scatterList(lst):
    """Helper functions for mpi communication."""
    if context.MPI_RANK == 0:
        chunked = iterables.split(lst, context.MPI_SIZE)
    else:
        chunked = None
    return context.MPI_COMM.scatter(chunked, root=0)


def _gatherList(localList):
    """Helper functions for mpi communication."""
    globalList = context.MPI_COMM.gather(localList, root=0)
    if context.MPI_RANK == 0:
        globalList = iterables.flatten(globalList)
    return globalList
