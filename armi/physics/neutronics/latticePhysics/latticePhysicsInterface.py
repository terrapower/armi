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
Lattice Physics Interface

Parent classes for codes responsible for generating broad-group cross sections
"""
import os
import shutil

from armi import nuclearDataIO
from armi import interfaces, runLog
from armi.localization import messages
from armi.utils import codeTiming
from armi.physics import neutronics
from armi.physics.neutronics.const import CONF_CROSS_SECTION

LATTICE_PHYSICS = "latticePhysics"


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
        # Geometry options available through the lattice physics interfaces
        self._ZERO_DIMENSIONAL_GEOM = "0D"
        self._ONE_DIMENSIONAL_GEOM = "1D"
        self._TWO_DIMENSIONAL_GEOM = "2D"
        self._SLAB_MODEL = " slab"
        self._CYLINDER_MODEL = " cylinder"
        self._HEX_MODEL = " hex"
        self._burnupTolerance = self.cs["tolerateBurnupChange"]
        self._oldXsIdsAndBurnup = {}
        self.executablePath = self._getExecutablePath()
        self.executableRoot = os.path.dirname(self.executablePath)
        self.includeGammaXS = neutronics.gammaTransportIsRequested(
            cs
        ) or neutronics.gammaXsAreRequested(cs)

    def _getExecutablePath(self):
        raise NotImplementedError

    @codeTiming.timed
    def interactBOC(self, cycle=0):
        """
        Run the lattice physics code if ``genXS`` is set and update burnup groups.

        Generate new cross sections based off the case settings and the current state of the reactor.

        Notes
        -----
        :py:meth:`armi.physics.fuelCycle.fuelHandlers.FuelHandler.interactBOC` also calls this if the
        ``runLatticePhysicsBeforeShuffling``setting is True.
        This happens because branch searches may need XS.
        """
        self.updateXSLibrary(cycle)

    def updateXSLibrary(self, cycle):
        """
        Update the current XS library, either by creating or reloading one.

        Parameters
        ----------
        cycle : int
            The cycle that is being processed. Used to name the library.

        See Also
        --------
        computeCrossSections : run lattice physics on the current reactor state no matter weather needed or not.
        """
        runLog.important("Preparing XS for cycle {}".format(cycle))
        representativeBlocks, xsIds = self._getBlocksAndXsIds()
        if self._newLibraryShouldBeCreated(cycle, representativeBlocks, xsIds):
            if self.cs["clearXS"]:
                self.clearXS()
            self.computeCrossSections(
                blockList=representativeBlocks, xsLibrarySuffix=self._getSuffix(cycle)
            )
            self._renameExistingLibrariesForCycle(cycle)
        else:
            self.readExistingXSLibraries(cycle)

        self._checkInputs()

    def _renameExistingLibrariesForCycle(self, cycle):
        """Copy the existing neutron and/or gamma libraries into cycle-dependent files."""
        shutil.copy(neutronics.ISOTXS, nuclearDataIO.getExpectedISOTXSFileName(cycle))
        if self.includeGammaXS:
            shutil.copy(
                neutronics.GAMISO,
                nuclearDataIO.getExpectedGAMISOFileName(
                    cycle=cycle, suffix=self._getSuffix(cycle)
                ),
            )
            shutil.copy(
                neutronics.PMATRX,
                nuclearDataIO.getExpectedPMATRXFileName(
                    cycle=cycle, suffix=self._getSuffix(cycle)
                ),
            )

    def _checkInputs(self):
        pass

    def readExistingXSLibraries(self, cycle):
        raise NotImplementedError

    def makeCycleXSFilesAsBaseFiles(self, cycle):
        raise NotImplementedError

    def _copyLibraryFilesForCycle(self, cycle, libFiles):
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
            "Gamma cross sections not implemented in {}".format(self.cs["xsKernel"])
        )

    def _writeGammaBinaries(self, lib, gamisoFileName, pmatrxFileName):
        raise NotImplementedError(
            "Gamma cross sections not implemented in {}".format(self.cs["xsKernel"])
        )

    def _getSuffix(self, cycle):  # pylint: disable=unused-argument, no-self-use
        return ""

    def interactCoupled(self, iteration):
        """
        Runs on secondary coupled iterations.

        After a coupled iteration, the cross sections need to be regenerated.
        This will bring in the spectral effects of changes in densities, as well as changes in
        Doppler.

        Parameters
        ----------
        iteration : int
            This is unused since cross sections are generated on a per-cycle basis.
        """
        self.r.core.lib = None
        self.updateXSLibrary(self.r.p.cycle)

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

        See Also
        --------
        :py:meth:`terrapower.physics.neutronics.mc2.mc2Writers.Mc2V2Writer.write`
        :py:meth:`armi.physics.neutronics.latticePhysics.serpentWriters.SerpentWriter.write`
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

            #. genXS setting is turned on
            #. We are beyond any requested skipCycles (restart cycles)
            #. The blocks have changed burnup beyond the burnup threshold
            #. Lattice physics kernel (e.g. MC2) hasn't already been executed for this cycle
            (possible if it runs during fuel handling)

        """
        executeXSGen = bool(self.cs["genXS"] and cycle >= self.cs["skipCycles"])
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
                runLog.warning(
                    "Even though XS generation is not activated, new XS {0} are needed. "
                    "Perhaps a booster came in.".format(missing)
                )
            elif missing:
                runLog.important(
                    "New XS sets {0} will be generated for this cycle".format(missing)
                )
            else:
                runLog.important(
                    "No new XS needed for this cycle. {0} exist. Skipping".format(
                        self.r.core.lib.xsIDs
                    )
                )
                executeXSGen = False  # no newXs

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
                messages.latticePhysics_SkippingXsGen_BuChangedLessThanTolerance(
                    self._burnupTolerance
                )
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
