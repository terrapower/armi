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

""""
Lattice Physics Interface.

Parent classes for codes responsible for generating broad-group cross sections
"""
import os
import shutil

from armi import nuclearDataIO
from armi import interfaces, runLog
from armi.utils import codeTiming
from armi.physics import neutronics
from armi.physics.neutronics.const import CONF_CROSS_SECTION
from armi.physics.neutronics.settings import (
    CONF_GEN_XS,
    CONF_CLEAR_XS,
    CONF_TOLERATE_BURNUP_CHANGE,
    CONF_XS_KERNEL,
    CONF_LATTICE_PHYSICS_FREQUENCY,
)
from armi.utils.customExceptions import important
from armi.physics.neutronics import LatticePhysicsFrequency


LATTICE_PHYSICS = "latticePhysics"


@important
def SkippingXsGen_BuChangedLessThanTolerance(tolerance):
    return "Skipping XS Generation this cycle because median block burnups changes less than {}%".format(
        tolerance
    )


def setBlockNeutronVelocities(r, neutronVelocities):
    """
    Set the ``mgNeutronVelocity`` parameter for each block using the ``neutronVelocities`` dictionary data.

    Parameters
    ----------
    neutronVelocities : dict
        Dictionary that is keyed with the ``representativeBlock`` XS IDs with values of multigroup neutron
        velocity data computed by MC2.

    Raises
    ------
    ValueError
        Multi-group neutron velocities was not computed during the cross section calculation.
    """
    for b in r.core.getBlocks():
        xsID = b.getMicroSuffix()
        if xsID not in neutronVelocities:
            raise ValueError(
                "Cannot assign multi-group neutron velocity to {} because it does not exist in "
                "the neutron velocities dictionary with keys: {}. The XS library does not contain "
                "data for the {} xsid.".format(b, neutronVelocities.keys(), xsID)
            )
        b.p.mgNeutronVelocity = neutronVelocities[b.getMicroSuffix()]


class LatticePhysicsInterface(interfaces.Interface):
    """Class for interacting with lattice physics codes."""

    function = LATTICE_PHYSICS

    def __init__(self, r, cs):
        interfaces.Interface.__init__(self, r, cs)

        # Set to True by default, but should be disabled when perturbed cross sections are generated.
        self._updateBlockNeutronVelocities = True
        self._burnupTolerance = self.cs[CONF_TOLERATE_BURNUP_CHANGE]
        self._oldXsIdsAndBurnup = {}
        self.executablePath = self._getExecutablePath()
        self.executableRoot = os.path.dirname(self.executablePath)
        self.includeGammaXS = neutronics.gammaTransportIsRequested(
            cs
        ) or neutronics.gammaXsAreRequested(cs)
        self._latticePhysicsFrequency = LatticePhysicsFrequency[
            self.cs[CONF_LATTICE_PHYSICS_FREQUENCY]
        ]

    def _getExecutablePath(self):
        raise NotImplementedError

    @codeTiming.timed
    def interactBOL(self, cycle=0):
        """
        Run the lattice physics code if ``genXS`` is set and update burnup groups.

        Generate new cross sections based off the case settings and the current state
        of the reactor if the lattice physics frequency is BOL.
        """
        if self._latticePhysicsFrequency == LatticePhysicsFrequency.BOL:
            self.updateXSLibrary(cycle)

    @codeTiming.timed
    def interactBOC(self, cycle=0):
        """
        Run the lattice physics code if ``genXS`` is set and update burnup groups.

        Generate new cross sections based off the case settings and the current state
        of the reactor if the lattice physics frequency is BOC.

        Notes
        -----
        :py:meth:`armi.physics.fuelCycle.fuelHandlerInterface.FuelHandlerInterface.interactBOC`
        also calls this if the ``runLatticePhysicsBeforeShuffling``setting is True.
        This happens because branch searches may need XS.
        """
        if self._latticePhysicsFrequency == LatticePhysicsFrequency.BOC:
            self.updateXSLibrary(cycle)

    def updateXSLibrary(self, cycle, node=None):
        """
        Update the current XS library, either by creating or reloading one.

        Parameters
        ----------
        cycle : int
            The cycle that is being processed. Used to name the library.
        node : int, optional
            The node that is being processed. Used to name the library.

        See Also
        --------
        computeCrossSections : run lattice physics on the current reactor state no matter weather needed or not.
        """
        runLog.important("Preparing XS for cycle {}".format(cycle))
        representativeBlocks, xsIds = self._getBlocksAndXsIds()
        if self._newLibraryShouldBeCreated(cycle, representativeBlocks, xsIds):
            if self.cs[CONF_CLEAR_XS]:
                self.clearXS()
            self.computeCrossSections(
                blockList=representativeBlocks, xsLibrarySuffix=self._getSuffix(cycle)
            )
            self._renameExistingLibrariesForStatepoint(cycle, node)
        else:
            self.readExistingXSLibraries(cycle, node)

        self._checkInputs()

    def _renameExistingLibrariesForStatepoint(self, cycle, node):
        """Copy the existing neutron and/or gamma libraries into cycle-dependent files."""
        shutil.copy(
            neutronics.ISOTXS, nuclearDataIO.getExpectedISOTXSFileName(cycle, node)
        )
        if self.includeGammaXS:
            shutil.copy(
                neutronics.GAMISO,
                nuclearDataIO.getExpectedGAMISOFileName(
                    cycle=cycle, node=node, suffix=self._getSuffix(cycle)
                ),
            )
            shutil.copy(
                neutronics.PMATRX,
                nuclearDataIO.getExpectedPMATRXFileName(
                    cycle=cycle, node=node, suffix=self._getSuffix(cycle)
                ),
            )

    def _checkInputs(self):
        pass

    def readExistingXSLibraries(self, cycle, node):
        raise NotImplementedError

    def makeCycleXSFilesAsBaseFiles(self, cycle, node):
        raise NotImplementedError

    @staticmethod
    def _copyLibraryFilesForCycle(cycle, libFiles):
        runLog.extra("Current library files: {}".format(libFiles))
        for baseName, cycleName in libFiles.items():
            if not os.path.exists(cycleName):
                if not os.path.exists(baseName):
                    raise ValueError(
                        "Neither {} nor {} libraries exist. Either the "
                        "current cycle library for cycle {} should exist "
                        "or a base library is required to continue.".format(
                            cycleName, baseName, cycle
                        )
                    )
                runLog.info(
                    "Existing library {} for cycle {} does not exist. "
                    "The active library is {}".format(cycleName, cycle, baseName)
                )
            else:
                runLog.info("Using {} as an active library".format(baseName))
                if cycleName != baseName:
                    shutil.copy(cycleName, baseName)

    def _readGammaBinaries(self, lib, gamisoFileName, pmatrxFileName):
        raise NotImplementedError(
            "Gamma cross sections not implemented in {}".format(self.cs[CONF_XS_KERNEL])
        )

    def _writeGammaBinaries(self, lib, gamisoFileName, pmatrxFileName):
        raise NotImplementedError(
            "Gamma cross sections not implemented in {}".format(self.cs[CONF_XS_KERNEL])
        )

    def _getSuffix(self, cycle):  # pylint: disable=unused-argument, no-self-use
        return ""

    def interactEveryNode(self, cycle=None, node=None):
        """
        Run the lattice physics code if ``genXS`` is set and update burnup groups.

        Generate new cross sections based off the case settings and the current state
        of the reactor if the lattice physics frequency is at least everyNode.
        """
        if self._latticePhysicsFrequency >= LatticePhysicsFrequency.everyNode:
            self.r.core.lib = None
            self.updateXSLibrary(self.r.p.cycle, self.r.p.timeNode)

    def interactCoupled(self, iteration):
        """
        Runs on coupled iterations to generate cross sections that are updated with the temperature state.

        Notes
        -----
        This accounts for changes in cross section data due to temperature changes, which are important
        for cross section resonance effects and accurately characterizing Doppler constant and coefficient
        evaluations. For Standard and Equilibrium run types, this coupling iteration is limited to when the
        time node is equal to zero. The validity of this assumption lies in the expectation that these runs
        have consistent power, flow, and temperature conditions at all time nodes. For Snapshot run types,
        this assumption, in general, is invalidated as the requested reactor state may sufficiently differ
        from what exists on the database and where tight coupling is needed to capture temperature effects.

        .. warning::

            For Standard and Equilibrium run types, if the reactor power, flow, and/or temperature state
            is expected to vary over the lifetime of the simulation, as could be the case with
            :ref:`detailed cycle histories <cycle-history>`, a custom subclass should be considered.

        Parameters
        ----------
        iteration : int
            This is unused since cross sections are generated on a per-cycle basis.
        """
        # always run for snapshots to account for temp effect of different flow or power statepoint
        targetFrequency = (
            LatticePhysicsFrequency.firstCoupledIteration
            if iteration == 0
            else LatticePhysicsFrequency.all
        )
        if self._latticePhysicsFrequency >= targetFrequency:
            self.r.core.lib = None
            self.updateXSLibrary(self.r.p.cycle, self.r.p.timeNode)

    def clearXS(self):
        raise NotImplementedError

    def interactEOC(self, cycle=None):
        """
        Interact at the end of a cycle.

        Force updating cross sections at the start of the next cycle.
        """
        self.r.core.lib = None

    def computeCrossSections(
        self, baseList=None, forceSerial=False, xsLibrarySuffix="", blockList=None
    ):
        """
        Prepare a batch of inputs, execute them, and store results on reactor library.

        Parameters
        ----------
        baseList : list
            a user-specified set of bases that will be run instead of calculating all of them
        forceSerial : bool, optional
            Will run on 1 processor in sequence instead of on many in parallel
            Useful for optimization/batch runs where every processor is on a different branch
        xsLibrarySuffix : str, optional
            A book-keeping suffix used in Doppler calculations
        blockList : list, optional
            List of blocks for which to generate cross sections.
            If None, representative blocks will be determined
        """
        self.r.core.lib = self._generateXsLibrary(
            baseList, forceSerial, xsLibrarySuffix, blockList
        )

    def _generateXsLibrary(
        self,
        baseList,
        forceSerial,
        xsLibrarySuffix,
        blockList,
        writers=None,
        purgeFP=True,
    ):
        raise NotImplementedError

    def _executeLatticePhysicsCalculation(self, returnedFromWriters, forceSerial):
        raise NotImplementedError

    def generateLatticePhysicsInputs(
        self, baseList, xsLibrarySuffix, blockList, xsWriters=None
    ):
        """
        Write input files for the generation of cross section libraries.

        Parameters
        ----------
        baseList : list
            A list of cross-section id strings (e.g. AA, BC) that will be generated. Default: all in reactor
        xsLibrarySuffix : str
            A suffix added to the end of the XS file names such as 'voided' for voided XS. Default: Empty
        blockList : list
            The blocks to write inputs for.
        xsWriters : list, optional
            The specified writers to write the input files

        Returns
        -------
        returnedFromWriters: list
            A list of what this specific writer instance returns for each representative block.
            It is the responsibility of the subclassed interface to implement.
            In many cases, it is the executing agent.
        """
        returnedFromWriters = []
        baseList = set(baseList or [])
        representativeBlocks = blockList or self.getRepresentativeBlocks()
        for repBlock in representativeBlocks:
            xsId = repBlock.getMicroSuffix()
            if not baseList or xsId in baseList:
                # write the step number to the info log
                runLog.info(
                    "Creating input writer(s) for {0} with {1:65s} BU (%FIMA): {2:10.2f}".format(
                        xsId, repBlock, repBlock.p.percentBu
                    )
                )
                writers = self.getWriters(repBlock, xsLibrarySuffix, xsWriters)
                for writer in writers:
                    fromWriter = writer.write()
                    returnedFromWriters.append(fromWriter)

        return returnedFromWriters

    def getWriters(self, representativeBlock, xsLibrarySuffix, writers=None):
        """
        Return valid lattice physics writer subclass(es).

        Parameters
        ----------
        representativeBlock : Block
            A representative block object that can be created from a block collection.
        xsLibrarySuffix : str
            A suffix added to the end of the XS file names such as 'voided' for voided XS. Default: Empty
        writers : list of lattice physics writer objects, optional
            If the writers are known, they can be provided and constructed.

        Returns
        -------
        writers : list
            A list of writers for the provided representative block.
        """
        xsID = representativeBlock.getMicroSuffix()
        if writers:
            # Construct the writers that are provided
            writers = [
                w(
                    representativeBlock,
                    r=self.r,
                    externalCodeInterface=self,
                    xsLibrarySuffix=xsLibrarySuffix,
                )
                for w in writers
            ]
        else:
            geom = self.cs[CONF_CROSS_SECTION][xsID].geometry
            writers = self._getGeomDependentWriters(
                representativeBlock, xsID, geom, xsLibrarySuffix
            )
        return writers

    def _getGeomDependentWriters(
        self, representativeBlock, xsID, geom, xsLibrarySuffix
    ):
        raise NotImplementedError

    def getReader(self):
        raise NotImplementedError

    def _newLibraryShouldBeCreated(self, cycle, representativeBlockList, xsIDs):
        """
        Determines whether the cross section generator should be executed at this cycle.

        Criteria include:

        #. CONF_GEN_XS setting is turned on
        #. We are beyond any requested skipCycles (restart cycles)
        #. The blocks have changed burnup beyond the burnup threshold
        #. Lattice physics kernel (e.g. MC2) hasn't already been executed for this cycle
           (possible if it runs during fuel handling)

        """
        executeXSGen = bool(self.cs[CONF_GEN_XS] and cycle >= self.cs["skipCycles"])
        idsChangedBurnup = self._checkBurnupThresholds(representativeBlockList)
        if executeXSGen and not idsChangedBurnup:
            executeXSGen = False

        if self.r.core._lib is not None:  # pylint: disable=protected-access
            # justification=r.core.lib property can raise exception or load pre-generated
            # ISOTXS, but the interface should have responsibilty of loading
            # XS's have already generated for this cycle (maybe during fuel management). Should we update due to
            # changes that occurred during fuel management?
            missing = set(xsIDs) - set(self.r.core.lib.xsIDs)
            if missing and not executeXSGen:
                runLog.info(
                    f"Although a XS library {self.r.core._lib} exists on {self.r.core}, "
                    f"there are missing XS IDs {missing} required. The XS generation on cycle {cycle} "
                    f"is not enabled, but will be run to generate these missing cross sections."
                )
                executeXSGen = True
            elif missing:
                runLog.info(
                    f"Although a XS library {self.r.core._lib} exists on {self.r.core}, "
                    f"there are missing XS IDs {missing} required. These will be generated "
                    f"on cycle {cycle}."
                )
                executeXSGen = True
            else:
                runLog.info(
                    f"A XS library {self.r.core._lib} exists on {self.r.core} and contains "
                    f"the required XS data for XS IDs {self.r.core.lib.xsIDs}. The generation "
                    "of XS will be skipped."
                )
                executeXSGen = False

        if executeXSGen:
            runLog.info(
                f"Cross sections will be generated on cycle {cycle} for the "
                f"following XS IDs: {xsIDs}"
            )
        else:
            runLog.info(
                f"Cross sections will not be generated on cycle {cycle}. The "
                f"setting `{CONF_GEN_XS}` is {self.cs[CONF_GEN_XS]} and `skipCycles` "
                f"is {self.cs['skipCycles']}"
            )

        return executeXSGen

    def _checkBurnupThresholds(self, blockList):
        """
        Check to see if burnup has changed meaningfully.

        If there are, then the xs sets should be regenerated.
        Otherwise then go ahead and skip xs generation.

        This is motivated by the idea that during very long explicit equilibrium runs,
        it might save time to turn off xs generation at a certain point.

        Parameters
        ----------
        blockList: iterable
            List of all blocks to examine

        Returns
        -------
        idsChangedBurnup: bool
            flag regarding whether or not burnup changed substantially

        """
        idsChangedBurnup = True
        if self._burnupTolerance > 0:
            idsChangedBurnup = False
            for b in blockList:
                xsID = b.getMicroSuffix()

                if xsID not in self._oldXsIdsAndBurnup:
                    # Looks like a new ID was found that was not in the old ID's
                    # have to regenerate the cross-sections this time around
                    self._oldXsIdsAndBurnup[xsID] = b.p.percentBu
                    idsChangedBurnup = True
                else:
                    # The id was found.  Now it is time to compare the burnups to determine
                    # if there has been enough meaningful change between the runs
                    buOld = self._oldXsIdsAndBurnup[xsID]
                    buNow = b.p.percentBu

                    if abs(buOld - buNow) > self._burnupTolerance:
                        idsChangedBurnup = True
                        # update the oldXs burnup to be the about to be newly generated xsBurnup
                        self._oldXsIdsAndBurnup[xsID] = buNow

                        runLog.important(
                            "Burnup has changed in xsID {} from {} to {}. "
                            "Recalculating Cross-sections".format(xsID, buOld, buNow)
                        )

            if not idsChangedBurnup:
                SkippingXsGen_BuChangedLessThanTolerance(self._burnupTolerance)

        return idsChangedBurnup

    def _getProcessesPerNode(self):
        raise NotImplementedError

    def getRepresentativeBlocks(self):
        """Return a list of all blocks in the problem."""
        xsGroupManager = self.getInterface("xsGroups")
        return xsGroupManager.representativeBlocks.values()  # OrderedDict

    def _getBlocksAndXsIds(self):
        """Return blocks and their xsIds."""
        blocks = self.getRepresentativeBlocks()
        return blocks, [b.getMicroSuffix() for b in blocks]

    def updatePhysicsCouplingControl(self):
        """
        Disable XS update in equilibrium cases after a while.

        Notes
        -----
        This is only relevant for equilibrium cases. We have to turn
        off XS updates after several cyclics or else the number densities
        will never converge.
        """
        if self.r.core.p.cyclics >= self.cs["numCyclicsBeforeStoppingXS"]:
            self.enabled(False)
            runLog.important(
                "Disabling {} because numCyclics={}".format(self, self.r.core.p.cyclics)
            )
