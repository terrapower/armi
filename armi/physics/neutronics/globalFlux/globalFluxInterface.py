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
The Global flux interface provide a base class for all neutronics tools that compute the neutron and/or photon flux.
"""
import math
import os

from matplotlib import pyplot
from matplotlib.collections import PolyCollection
import numpy
import scipy.integrate

import armi
from armi import runLog
from armi import interfaces
from armi.utils import units
from armi.utils import codeTiming
from armi.reactor import geometry
from armi.reactor.converters import uniformMesh
from armi.reactor.converters import geometryConverters
from armi.reactor import assemblies
from armi.localization import exceptions
from armi.reactor.flags import Flags
from armi.utils import pathTools
from armi.physics import neutronics

ORDER = interfaces.STACK_ORDER.FLUX


# pylint: disable=too-many-public-methods
class GlobalFluxInterface(interfaces.Interface):
    r"""
    A general abstract interface for global flux calculating modules.

    Should be subclassed
    """

    name = None  # make sure to set this in subclasses
    function = "globalFlux"
    _ENERGY_BALANCE_REL_TOL = 1e-5

    def __init__(self, r, cs):
        interfaces.Interface.__init__(self, r, cs)
        if self.cs["nCycles"] > 1000:
            self.cycleFmt = "04d"  # produce ig0001.inp
        else:
            self.cycleFmt = "03d"  # produce ig001.inp

        if self.cs["burnSteps"] > 10:
            self.nodeFmt = "03d"  # produce ig001_001.inp
        else:
            self.nodeFmt = "1d"  # produce ig001_1.inp.
        self._bocKeff = None  # for tracking rxSwing
        self.geomConverters = {}
        self._outputFilesNamesToRetrieve = []
        self.meshLookup = None
        self.iMax = 0
        self.jMax = 0
        self.kMax = 0

    def getHistoryParams(self):
        """Return parameters that will be added to assembly versus time history printouts."""
        return ["detailedDpa", "detailedDpaPeak", "detailedDpaPeakRate"]

    def interactBOC(self, cycle=None):
        self.r.core.p.rxSwing = 0.0  # zero out rxSwing until EOC.
        self.r.core.p.maxDetailedDpaThisCycle = 0.0  # zero out cumulative params
        self.r.core.p.dpaFullWidthHalfMax = 0.0
        self.r.core.p.elevationOfACLP3Cycles = 0.0
        self.r.core.p.elevationOfACLP7Cycles = 0.0
        for b in self.r.core.getBlocks():
            b.p.detailedDpaThisCycle = 0.0
            b.p.newDPA = 0.0

    def interactEOC(self, cycle=None):
        if self._bocKeff is not None:
            self.r.core.p.rxSwing = (
                (self.r.core.p.keff - self._bocKeff)
                / self._bocKeff
                * units.ABS_REACTIVITY_TO_PCM
            )

    def _checkEnergyBalance(self):
        """Check that there is energy balance between the power generated and the specified power is the system."""
        powerGenerated = (
            self.r.core.calcTotalParam(
                "power", calcBasedOnFullObj=False, generationNum=2
            )
            / units.WATTS_PER_MW
        )
        specifiedPower = (
            self.r.core.p.power / units.WATTS_PER_MW / self.r.core.p.powerMultiplier
        )

        if not math.isclose(
            powerGenerated, specifiedPower, rel_tol=self._ENERGY_BALANCE_REL_TOL
        ):
            raise ValueError(
                "The power generated in {} is {} MW, but the user specified power is {} MW.\n"
                "This indicates a software bug. Please report to the developers.".format(
                    self.r.core, powerGenerated, specifiedPower
                )
            )

    def getIOFileNames(self, cycle, node, coupledIter=None, additionalLabel=""):
        """
        Return the input and output file names for this run.

        Parameters
        ----------
        cycle : int
            The cycle number
        node : int
            The burn node number (e.g. 0 for BOC, 1 for MOC, etc.)
        coupledIter : int, optional
            Coupled iteration number (for tightly-coupled cases)
        additionalLabel : str, optional
            An optional tag to the file names to differentiate them
            from another case.

        Returns
        -------
        inName : str
            Input file name
        outName : str
            Output file name
        stdName : str
            Standard output file name
        """
        timeId = (
            "{0:" + self.cycleFmt + "}_{1:" + self.nodeFmt + "}"
        )  # build names with proper number of zeros
        if coupledIter is not None:
            timeId += "_{0:03d}".format(coupledIter)

        inName = (
            self.cs.caseTitle
            + timeId.format(cycle, node)
            + "{}.{}.inp".format(additionalLabel, self.name)
        )
        outName = (
            self.cs.caseTitle
            + timeId.format(cycle, node)
            + "{}.{}.out".format(additionalLabel, self.name)
        )
        stdName = outName.strip(".out") + ".stdout"

        return inName, outName, stdName

    @codeTiming.timed
    def retrieveOutputFiles(self, runPath):
        """
        Copy interesting output files from local disks to shared network disk.

        Run this if you want copies of the local output files.
        This copies output from the runPath to the current working directory,
        which is generally the shared network drive.

        See Also
        --------
        specifyOutputFilesToRetrieve : says which ones to copy back.
        armi.utils.directoryChangers.DirectoryChanger.retrieveFiles : should be used instead of this.

        Notes
        -----
        This could be done in a separate thread to let processing continue while I/O spins.

        """
        for sourceName, destinationName in self._outputFilesNamesToRetrieve:
            workingFileName = os.path.join(runPath, sourceName)
            pathTools.copyOrWarn("output file", workingFileName, destinationName)

    def addNewOutputFileToRetrieve(self, sourceName, destinationName=None):
        """
        Add a new file to the list of files that will be copied to the shared drive after a run.

        These should be names only, not paths.

        Parameters
        ----------
        sourceName : str
            The name of the file in the source location, e.g. `FT06`

        destinationName : str or None
            The name of the file in the destination location, e.g. `caseName.dif3d.out`

        See Also
        --------
        armi.utils.directoryChangers.DirectoryChanger.retrieveFiles : should be used instead of this.
        """
        if destinationName is None:
            # no name change
            destinationName = sourceName
        runLog.debug(
            "Adding output file {} to list of files to retrieve".format(sourceName)
        )
        self._outputFilesNamesToRetrieve.append((sourceName, destinationName))

    # pylint: disable=unused-argument; They're used in subclasses
    def specifyOutputFilesToRetrieve(self, inName, outName):
        """
        determines which output files will be retrieved from the run directory

        Notes
        -----
        This just resets the list at every run. The real work is done in the subclass methods.

        See Also
        --------
        terrapower.physics.neutronics.dif3d.dif3dInterface.Dif3dInterface.specifyOutputFilesToRetrieve

        """
        runLog.debug(
            "Clearing out files to retrieve: {}".format(
                self._outputFilesNamesToRetrieve
            )
        )
        self._outputFilesNamesToRetrieve = []

    def calculateKeff(
        self,
        inf,
        outf,
        genXS="",
        baseList=None,
        forceSerial=False,
        xsLibrarySuffix="",
        updateArmi=False,
        outputsToCopyBack="",
    ):
        r"""
        Run neutronics calculation and return keff

        Handles some XS generation stuff as well, optionally. Usefull when you
        just need to know keff of the current state (like in rx coeffs, CR worth)

        Parameters
        ----------
        inf : str
            input file name
        outf : str
            a dif3d/rebus output file name that will be generated
        genXS : str
            type of particle you want MC**2 to regenerate cross sections for allowed values
            of genXS setting.
        baseList : list
            MC**2 bases to generate (QA, QAF) if you want a partial MC**2 run
        forceSerial : bool
            forces the MC**2 runs to run on a single processor
        xsLibrarySuffix : str
            will get appended to the library name ISOTXS.
        updateArmi : bool, optional
            If true, will update the ARMI state (reactor, assems, blocks) with the
            results of the neutronics run. Defaults to False so
            flux distributions used in weighting blocks for XS don't get mixed up.
        outputsToCopyBack : str, optional
            Copy a subset of files back to the main path in fastPath cases. Takes
            time but good for debugging/restarts.

        Returns
        -------
        rebOut : a Rebus_Output class containing neutronics output information

        See Also
        --------
        calculateFlux : does this but handles lots of other bookkeeping stuff that
            is important during a main operator loop.

        """
        xsGroupManager = self.getInterface("xsGroups")
        xsLibName = {neutronics.ISOTXS: neutronics.ISOTXS + xsLibrarySuffix}
        runLog.info(
            "Calculating keff in {} using XS Library: {}.".format(
                os.getcwd(), xsLibName
            )
        )

        if genXS:
            # this boolean is specifically not taken from the gui. This ensures that
            # cross-sections are not generated unless they are specifically needed.
            if xsGroupManager.enabled():  # might be disabled during Doppler, etc.
                xsGroupManager.createRepresentativeBlocks()
            lattice = self.o.getInterface(function="latticePhysics")
            lattice.computeCrossSections(
                baseList=baseList,
                forceSerial=forceSerial,
                xsLibrarySuffix=xsLibrarySuffix,
            )

        _runPath, rebOut = self.run(
            inf,
            outf,
            branchNum=armi.MPI_RANK,
            libNames=xsLibName,
            updateArmi=updateArmi,
            outputsToCopyBack=outputsToCopyBack,
        )
        self._undoGeometryTransformations()
        runLog.info("Got keff= {}".format(rebOut.getKeff()))
        return rebOut

    def calculateKeffFiniteDifference(self):
        raise NotImplementedError

    def calculateFlux(self, cycle, node):
        raise NotImplementedError

    def run(
        self,
        inName,
        outName,
        path=None,
        branchNum=None,
        libNames=None,
        outputsToCopyBack="",
        updateArmi=False,
    ):
        raise NotImplementedError

    @codeTiming.timed
    def _performGeometryTransformations(self, makePlots=False):
        """
        Apply geometry conversions to make reactor work in neutronics

        There are two conditions where things must happen:

        1. If you are doing finite-difference, you need to add the edge assemblies (fast).
           For this, we just modify the reactor in place

        2. If you are doing detailed axial expansion, you need to average out the axial mesh (slow!)
           For this we need to create a whole copy of the reactor and use that.

        In both cases, we need to undo the modifications between reading the output
        and applying the result to the data model.

        See Also
        --------
        _undoGeometryTransformations
        """
        if any(self.geomConverters):
            raise exceptions.StateError(
                "The reactor has been transformed, but not restored to the original.\n"
                + "Geometry converter is set to {} \n.".format(self.geomConverters)
                + "This is a programming error and requires further investigation."
            )
        neutronicsReactor = self.r
        if self.cs["detailedAxialExpansion"]:
            converter = self.geomConverters.get("axial")
            if not converter:
                converter = uniformMesh.UniformMeshGeometryConverter(self.cs)
                neutronicsReactor = converter.convert(self.r)
                if makePlots:
                    converter.plotConvertedReactor()
                self.geomConverters["axial"] = converter

        if self.edgeAssembliesAreNeeded():
            converter = self.geomConverters.get(
                "edgeAssems", geometryConverters.EdgeAssemblyChanger()
            )
            converter.addEdgeAssemblies(neutronicsReactor.core)
            self.geomConverters["edgeAssems"] = converter

        self.r = neutronicsReactor

    @codeTiming.timed
    def _undoGeometryTransformations(self, paramsToScaleSubset=None):
        """
        Restore original data model state and/or apply results to it.

        Notes
        -----
        These transformations occur in the opposite order than that which they were applied in.
        Otherwise, the uniform mesh guy would try to add info to assem's on the source reactor
        that don't exist.

        See Also
        --------
        _performGeometryTransformations
        """
        geomConverter = self.geomConverters.get("edgeAssems")
        if geomConverter:
            geomConverter.scaleParamsRelatedToSymmetry(
                self.r, paramsToScaleSubset=paramsToScaleSubset
            )
            geomConverter.removeEdgeAssemblies(self.r.core)

        meshConverter = self.geomConverters.get("axial")
        if meshConverter:
            meshConverter.applyStateToOriginal()
            self.r = meshConverter._sourceReactor  # pylint: disable=protected-access;

        nAssemsBeforeConversion = [
            converter.getAssemblyModuleCounter()
            for converter in (geomConverter, meshConverter)
            if converter is not None
        ]
        if nAssemsBeforeConversion:
            assemblies.setAssemNumCounter(min(nAssemsBeforeConversion))

        self.geomConverters = (
            {}
        )  # clear the converters in case this function gets called twice

    def edgeAssembliesAreNeeded(self):
        """
        True if edge assemblies are needed in this calculation

        We only need them in finite difference cases that are not full core.
        """
        return (
            "FD" in self.cs["neutronicsKernel"]
            and self.r.core.symmetry == geometry.THIRD_CORE + geometry.PERIODIC
            and self.r.core.p.geomType == geometry.HEX
        )

    def clearFlux(self):
        """
        Delete flux on all blocks. Needed to prevent stale flux when partially reloading.
        """
        for b in self.r.core.getBlocks():
            b.p.mgFlux = []
            b.p.adjMgFlux = []
            b.p.mgFluxGamma = []
            b.p.extSrc = []

    def buildBlockMeshLookup(self, useWholeHexNodalOrdering=False, plotMesh=False):
        r"""
        Build a lookup table between finite difference mesh points and blocks.

        Notes
        -----
        This method builds a dictionary. blockLookup[(i,j,k)] = block that's in i,j,k.
        They start at 1, following loc.containsWhichFDMEshPointsThird

        WARNING: When useWholeHexNodalOrdering = True, this function will give wrong neighbors
        when the 120-degree symmetry line "edge assemblies" are present. Be careful!

        These mesh indices should start at 1, just like DIF3D. DIFNT switches to 0 based indexing though.

        Parameters
        ----------
        useWholeHexNodalOrdering : bool, optional
            If True, ijList will contain the (i,j) = (ring,pos) indices of hex assemblies.
                Thus, the axial block locations will be looked up based on which assembly contains them.
                This is used by fluxRecon.computePinMGFluxAndPower to map nodal surface data from NHFLUX
                to ARMI blocks (in terms of axial divisions).
            If False, ijList will contain the triangular FD mesh indices from loc.containsWhichFDMeshPoints,
                which do NOT correspond to whole hex assemblies. This was how buildBlockMeshLookup always worked
                before the useWholeHexNodalOrdering option was added.

        plotMesh : bool, optional
            If true, will print a pdf of the mesh.

        Returns
        -------
        meshLookup : 3-D array of block objects
            b = meshLookup[i,j,k] is the ARMI block object that contains the finite difference mesh node indexed
                by i, j, and k. Here (i,j) is the index pair in ijList and k is the axial index.

        (iMax,jMax,kMax) : tuple
            These are the maximum values of the finite difference mesh indices i, j, and k. Here k is the axial index,
                while i and j can be different hex/triangular indexing systems.

        See Also
        --------
        fluxRecon.computePinMGFluxAndPower
        HexLocation.containsWhichFDMeshPoints

        Raises
        -----
        ValueError
            When blocks are not found.
        RuntimeError
            When not all blocks are looped over.
        """

        # find mesh dimensions while we're at it
        if self.meshLookup:
            return self.meshLookup, (self.iMax, self.jMax, self.kMax)
        runLog.extra("Building new block-mesh lookup")

        meshLookup = {}
        iMax = jMax = kMax = 0
        allBlocks = set(self.r.core.getBlocks())
        for a in self.r.core.getAssemblies():
            # get i and j.
            loc = a.getLocationObject()
            # ijList represents (ring,pos) whole-hex ordering
            if useWholeHexNodalOrdering:
                # dummy initialization (this will contain only ONE pair of indices if useWholeHexNodalOrdering = True)
                ijList = [(-1, -1)]
                # whole-hex indices: (i,j) = (ring,pos)
                ijList[0] = a.spatialLocator.getRingPos()
                # ijList represents triangle subdivision ordering (this was how buildBlockMeshLookup always worked
                # before the useWholeHexNodalOrdering option was added.)
            else:
                ijList = loc.containsWhichFDMeshPoints(
                    resolution=self.cs["numberMeshPerEdge"],
                    fullCore=self.r.core.isFullCore,
                )

            for k, zTop in enumerate(
                self.r.core.p.axialMesh[1:]
            ):  # skip the first entry, which is 0
                # one block may cover several axial mesh points
                k += 1  # shift to start at 1
                b = a.getBlockAtElevation(zTop)
                if b is None:
                    raise ValueError("No block found in {} at {}".format(a, zTop))
                for i, j in ijList:
                    if i > iMax:
                        iMax = i
                    if j > jMax:
                        jMax = j
                    if k > kMax:
                        kMax = k
                    meshLookup[i, j, k] = b

                if b in allBlocks:
                    allBlocks.remove(b)

        if allBlocks:
            runLog.error(
                "Not all blocks were put into the lookup. Missing are: {0}".format(
                    allBlocks
                )
            )
            raise RuntimeError(
                "Not all blocks were put into the lookup. Try increasing "
                "number of axial mesh points near missing blocks"
            )

        if plotMesh:
            plotMeshLookup(meshLookup, 2, "mesh.pdf")

        if not useWholeHexNodalOrdering and self.r.core.isFullCore:
            # pylint: disable=no-member; only implemented in DIFNT actually
            meshLookup, (iMax, jMax) = self.shiftLookupFullCore(meshLookup)
            if plotMesh:
                plotMeshLookup(meshLookup, 2, "meshPostShift.pdf")

        return meshLookup, (iMax, jMax, kMax)

    def _renormalizeNeutronFluxByBlock(self, renormalizationCorePower):
        """
        Normalize the neutron flux within each block to meet the renormalization power.
        
        Parameters
        ----------
        renormalizationCorePower: float
            Specified power to renormalize the neutron flux for using the isotopic energy
            generation rates on the cross section libraries (in Watts)
            
        See Also
        --------
        getTotalEnergyGenerationConstants
        """
        # The multi-group flux is volume integrated, so J/cm * n-cm/s gives units of Watts
        currentCorePower = sum(
            [
                numpy.dot(
                    b.getTotalEnergyGenerationConstants(), b.getIntegratedMgFlux()
                )
                for b in self.r.core.getBlocks()
            ]
        )
        powerRatio = renormalizationCorePower / currentCorePower
        runLog.info(
            "Renormalizing the neutron flux in {:<s} by a factor of {:<8.5e}, "
            "which is derived from the current core power of {:<8.5e} W and "
            "desired power of {:<8.5e} W".format(
                self.r.core, powerRatio, currentCorePower, renormalizationCorePower
            )
        )
        for b in self.r.core.getBlocks():
            b.p.mgFlux *= powerRatio
            b.p.flux *= powerRatio
            b.p.fluxPeak *= powerRatio
            b.p.power *= powerRatio
            b.p.pdens = b.p.power / b.getVolume()

    def _updateDerivedParams(self):
        """Computes some params that are derived directly from flux and power parameters."""
        for maxParamKey in ["percentBu", "pdens"]:
            maxVal = self.r.core.getMaxBlockParam(maxParamKey, Flags.FUEL)
            if maxVal != 0.0:
                self.r.core.p["max" + maxParamKey] = maxVal

        maxFlux = self.r.core.getMaxBlockParam("flux")
        self.r.core.p.maxFlux = maxFlux

        conversion = units.CM2_PER_M2 / units.WATTS_PER_MW
        for a in self.r.core:
            area = a.getArea()
            for b in a:
                b.p.arealPd = b.p.power / area * conversion
            a.p.arealPd = a.calcTotalParam("arealPd")
        self.r.core.p.maxPD = self.r.core.getMaxParam("arealPd")

    def updateDpaRate(self, blockList=None):
        """
        Update state parameters that can be known right after the flux is computed

        See Also
        --------
        updateFluenceAndDpa : uses values computed here to update cumulative dpa

        """
        if blockList is None:
            blockList = self.r.core.getBlocks()
        hasDPA = False
        for b in blockList:
            xs = b.getDpaXs()
            if not xs:
                continue
            hasDPA = True
            flux = b.getMgFlux()  # n/cm^2/s
            dpaPerSecond = computeDpaRate(flux, xs)
            b.p.detailedDpaPeakRate = dpaPerSecond * b.getBurnupPeakingFactor()
            b.p.detailedDpaRate = dpaPerSecond

        if not hasDPA:
            return
        self.r.core.p.peakGridDpaAt60Years = (
            self.r.core.getMaxBlockParam(
                "detailedDpaPeakRate", typeSpec=Flags.GRID_PLATE, absolute=False
            )
            * 60.0
            * units.SECONDS_PER_YEAR
        )
        # also update maxes at this point (since this runs at every timenode, not just those w/ depletion steps)
        self.updateMaxDpaParams()

    def updateMaxDpaParams(self):
        """
        Update params that track the peak dpa.

        Only consider fuel because CRs, etc. aren't always reset.
        """
        maxDpa = self.r.core.getMaxBlockParam("detailedDpaPeak", Flags.FUEL)
        self.r.core.p.maxdetailedDpaPeak = maxDpa
        self.r.core.p.maxDPA = maxDpa

        # add grid plate max
        maxGridDose = self.r.core.getMaxBlockParam("detailedDpaPeak", Flags.GRID_PLATE)
        self.r.core.p.maxGridDpa = maxGridDose

    def updateFluenceAndDpa(self, stepTimeInSeconds, blockList=None):
        r"""
        updates the fast fluence and the DPA of the blocklist

        The dpa rate from the previous timestep is used to compute the dpa here.

        There are several items of interest computed here, including:
            * detailedDpa: The average DPA of a block
            * detailedDpaPeak: The peak dpa of a block, considering axial and radial peaking
                The peaking is based either on a user-provided peaking factor (computed in a
                pin reconstructed rotation study) or the nodal flux peaking factors
            * dpaPeakFromFluence: fast fluence * fluence conversion factor (old and inaccurate). Used to be dpaPeak

        Parameters
        ----------
        stepTimeInSeconds : float
            Time in seconds that the cycle ran at the current mgFlux

        blockList : list, optional
            blocks to be updated. Defaults to all blocks in core

        See Also
        --------
        updateDpaRate : updates the DPA rate used here to compute actual dpa
        """
        blockList = blockList or self.r.core.getBlocks()

        if not blockList[0].p.fluxPeak:
            runLog.warning(
                "no fluxPeak parameter on this model. Peak DPA will be equal to average DPA. "
                "Perhaps you are not running a nodal approximation."
            )

        for b in blockList:
            burnupPeakingFactor = b.getBurnupPeakingFactor()
            b.p.residence += stepTimeInSeconds / units.SECONDS_PER_DAY
            b.p.fluence += b.p.flux * stepTimeInSeconds
            b.p.fastFluence += b.p.flux * stepTimeInSeconds * b.p.fastFluxFr
            b.p.fastFluencePeak += b.p.fluxPeak * stepTimeInSeconds * b.p.fastFluxFr

            # update detailed DPA based on dpa rate computed at LAST timestep.
            dpaRateThisStep = b.p.detailedDpaRate
            newDpaThisStep = dpaRateThisStep * stepTimeInSeconds
            newDPAPeak = newDpaThisStep * burnupPeakingFactor
            # track incremental increase for duct distortion interface (and eq)
            b.p.newDPA = newDpaThisStep
            b.p.newDPAPeak = newDPAPeak
            # use = here instead of += because we need the param system to notice the change for syncronization.
            b.p.detailedDpa = b.p.detailedDpa + newDpaThisStep
            # add assembly peaking
            b.p.detailedDpaPeak = b.p.detailedDpaPeak + newDPAPeak
            b.p.detailedDpaThisCycle = b.p.detailedDpaThisCycle + newDpaThisStep

            if self.cs["dpaPerFluence"]:
                # do the less rigorous fluence -> DPA conversion if the user gave a factor.
                b.p.dpaPeakFromFluence = b.p.fastFluencePeak * self.cs["dpaPerFluence"]

            # also set the burnup peaking. Requires burnup to be up-to-date
            # (this should run AFTER burnup has been updated)
            b.p.percentBuPeak = b.p.percentBu * burnupPeakingFactor

        for a in self.r.core.getAssemblies():
            a.p.daysSinceLastMove += stepTimeInSeconds / units.SECONDS_PER_DAY

        self.updateMaxDpaParams()
        self.updateCycleDoseParams()
        self.updateLoadpadDose()

    def updateCycleDoseParams(self):
        r"""Updates reactor params based on the amount of dose (detailedDpa) accrued this cycle
        Params updated include:

        maxDetailedDpaThisCycle
        dpaFullWidthHalfMax
        elevationOfACLP3Cycles
        elevationOfACLP7Cycles

        These parameters are left as zeroes at BOC because no dose has been accumulated yet.
        """

        if self.r.p.timeNode > 0:

            maxDetailedDpaThisCycle = 0.0
            peakDoseAssem = None
            for a in self.r.core:
                if a.getMaxParam("detailedDpaThisCycle") > maxDetailedDpaThisCycle:
                    maxDetailedDpaThisCycle = a.getMaxParam("detailedDpaThisCycle")
                    peakDoseAssem = a
            self.r.core.p.maxDetailedDpaThisCycle = maxDetailedDpaThisCycle

            doseHalfMaxHeights = peakDoseAssem.getElevationsMatchingParamValue(
                "detailedDpaThisCycle", maxDetailedDpaThisCycle / 2.0
            )
            if len(doseHalfMaxHeights) != 2:
                runLog.warning(
                    "Something strange with detailedDpaThisCycle shape in {}, "
                    "non-2 number of values matching {}".format(
                        peakDoseAssem, maxDetailedDpaThisCycle / 2.0
                    )
                )
            else:
                self.r.core.p.dpaFullWidthHalfMax = (
                    doseHalfMaxHeights[1] - doseHalfMaxHeights[0]
                )

            aclpDoseLimit = self.cs["aclpDoseLimit"]
            aclpDoseLimit3 = (
                aclpDoseLimit / 3.0 * self.r.p.timeNode / self.cs["burnSteps"]
            )
            aclpLocations3 = peakDoseAssem.getElevationsMatchingParamValue(
                "detailedDpaThisCycle", aclpDoseLimit3
            )
            if len(aclpLocations3) != 2:
                runLog.warning(
                    "Something strange with detailedDpaThisCycle shape in {}"
                    ", non-2 number of values matching {}".format(
                        peakDoseAssem, aclpDoseLimit / 3.0
                    )
                )
            else:
                self.r.core.p.elevationOfACLP3Cycles = aclpLocations3[1]

            aclpDoseLimit7 = (
                aclpDoseLimit / 7.0 * self.r.p.timeNode / self.cs["burnSteps"]
            )
            aclpLocations7 = peakDoseAssem.getElevationsMatchingParamValue(
                "detailedDpaThisCycle", aclpDoseLimit7
            )
            if len(aclpLocations7) != 2:
                runLog.warning(
                    "Something strange with detailedDpaThisCycle shape in {}, "
                    "non-2 number of values matching {}".format(
                        peakDoseAssem, aclpDoseLimit / 7.0
                    )
                )
            else:
                self.r.core.p.elevationOfACLP7Cycles = aclpLocations7[1]

    def updateLoadpadDose(self):
        """
        Summarize the dose in DPA of the above-core load pad.

        This sets the following reactor params:

        * loadPadDpaPeak : the peak dpa in any load pad
        * loadPadDpaAvg : the highest average dpa in any load pad

        .. warning:: This only makes sense for cores with load
            pads on their assemblies.

        See Also
        --------
        _calcLoadPadDose : computes the load pad dose

        """
        peakPeak, peakAvg = self._calcLoadPadDose()
        if peakPeak is None:
            return
        self.o.r.core.p.loadPadDpaAvg = peakAvg[0]
        self.o.r.core.p.loadPadDpaPeak = peakPeak[0]
        str_ = [
            "Above-core load pad (ACLP) summary. It starts at {0} cm above the "
            "bottom of the grid plate".format(self.cs["loadPadElevation"])
        ]
        str_.append(
            "The peak ACLP dose is     {0} DPA in {1}".format(peakPeak[0], peakPeak[1])
        )
        str_.append(
            "The max avg. ACLP dose is {0} DPA in {1}".format(peakAvg[0], peakAvg[1])
        )
        runLog.info("\n".join(str_))

    def _calcLoadPadDose(self):
        r"""
        Determines some dose information on the load pads if they exist.

        Expects a few settings to be present in cs
            loadPadElevation : float
                The bottom of the load pad's elevation in cm above the bottom of
                the (upper) grid plate.
            loadPadLength : float
                The axial length of the load pad to average over

        This builds axial splines over the assemblies and then integrates them
        over the load pad.

        The assumptions are that detailedDpa is the average, defined in the center
        and detailedDpaPeak is the peak, also defined in the center of blocks.

        Parameters
        ----------
        core  : armi.reactor.reactors.Core
        cs : armi.settings.caseSettings.Settings

        Returns
        -------
        peakPeak : tuple
            A (peakValue, peakAssem) tuple
        peakAvg : tuple
            a (avgValue, avgAssem) tuple

        See Also
        --------
        writeLoadPadDoseSummary : prints out the dose
        Assembly.getParamValuesAtZ : gets the parameters at any arbitrary z point

        """
        loadPadBottom = self.cs["loadPadElevation"]
        loadPadLength = self.cs["loadPadLength"]
        if not loadPadBottom or not loadPadLength:
            # no load pad dose requested
            return None, None

        peakPeak = (0.0, None)
        peakAvg = (0.0, None)
        loadPadTop = loadPadBottom + loadPadLength

        zrange = numpy.linspace(loadPadBottom, loadPadTop, 100)
        for a in self.o.r.core.getAssemblies(Flags.FUEL):
            # scan over the load pad to find the peak dpa
            # no caching.
            peakDose = max(
                a.getParamValuesAtZ("detailedDpaPeak", zrange, fillValue="extrapolate")
            )
            # restrict to fuel because control assemblies go nuts in dpa.
            integrand = a.getParamOfZFunction("detailedDpa", fillValue="extrapolate")
            returns = scipy.integrate.quad(integrand, loadPadBottom, loadPadTop)
            avgDose = (
                float(returns[0]) / loadPadLength
            )  # convert to float in case it's an ndarray

            # track max doses
            if peakDose > peakPeak[0]:
                peakPeak = (peakDose, a)
            if avgDose > peakAvg[0]:
                peakAvg = (avgDose, a)

        return peakPeak, peakAvg


def plotMeshLookup(meshLookup, myK=2, fName="meshPlot.pdf"):
    """Plots the mesh lookup in one slab."""
    allIJ = []
    # side length is 1.0
    h = -math.sqrt(3.0) / 2.0  # pylint: disable=invalid-name
    colors = []
    for (i, j, k), b in meshLookup.items():

        if k == myK and (i, j) not in allIJ:
            allIJ.append((i, j))
            colors.append(b.parent.getNum())

    verts = []
    for i, j in allIJ:
        b = meshLookup[i, j, myK]
        x, y = getXY120(i, j)

        if i % 2:
            # even hex 2,4, etc.
            p1 = (x - h / 2.0, y - h / 2.0)
            p2 = (x + h / 2.0, y - h / 2.0)
            p3 = (x, y + h / 2.0)
        else:
            # upside down triangle here.
            p1 = (x, y - h / 2.0)
            p2 = (x - h / 2.0, y + h / 2.0)
            p3 = (x + h / 2.0, y + h / 2.0)
        verts.append((p1, p2, p3))

    coll = PolyCollection(
        verts,
        cmap=pyplot.cm.jet,  # pylint: disable=no-member
        linewidths=0.1,
        facecolors="white",
        array=numpy.array(colors),
    )

    fig, ax = pyplot.subplots(figsize=(16, 16))  # make it proper sized
    ax.add_collection(coll)
    for i, j in allIJ:
        b = meshLookup[i, j, myK]
        x, y = getXY120(i, j)
        ring, pos = b.parent.spatialLocator.getRingPos()
        ax.text(
            x,
            y,
            "{0}\n({1},{2})\nloc: ({3},{4})".format(b.parent.getNum(), i, j, ring, pos),
            fontsize=1.5,
            horizontalalignment="center",
            verticalalignment="center",
        )
    ax.autoscale_view()

    # Add a colorbar for the PolyCollection
    # fig.colorbar(coll, ax=ax)
    fig.savefig(fName)
    pyplot.close(fig)


def getXY120(i, j):
    """
    Get xy coords for i,j indices in fig 2.4 DIF3D manual.

    Assumes triangleside length 1.0
    """
    height = math.sqrt(3) / 2.0
    y = j * height
    x = -0.5 * j + 0.5 * i
    return x, y


def computeDpaRate(mgFlux, dpaXs):
    r"""
    Compute the DPA rate incurred by exposure of a certain flux spectrum

    Parameters
    ----------
    mgFlux : list
        multigroup neutron flux in #/cm^2/s

    dpaXs : list
        DPA cross section in barns to convolute with flux to determine DPA rate

    Returns
    -------
    dpaPerSecond : float
        The dpa/s in this material due to this flux

    Notes
    -----
    Displacements calculated by displacement XS
    Displacement rate = flux * nHT9 * barn  [in #/cm^3/s]
                      = [#/cm^2/s] * [1/cm^3] * [barn]
                      = [#/cm^5/s] * [barn] * 1e-24 [cm^2/barn]
                      = [#/cm^3/s]

    DPA rate = displacement density rate / (number of atoms/cc)
             = dr [#/cm^3/s] / (nHT9)  [1/cm^3]
             = flux * barn * 1e-24 ::


                flux * N * xs
    DPA / s=  -----------------  = flux * xs
                     N

    nHT9 cancels out. It's in the macroscopic XS and in the original number of atoms.

    Raises
    ------
    RuntimeError
       Negative dpa rate. 

    """
    displacements = 0.0
    if len(mgFlux) != len(dpaXs):
        runLog.warning(
            "Multigroup flux of length {} is incompatible with dpa cross section of length {};"
            "dpa rate will be set do 0.0".format(len(mgFlux), len(dpaXs)),
            single=True,
        )
        return displacements
    for flux, barns in zip(mgFlux, dpaXs):
        displacements += flux * barns
    dpaPerSecond = displacements * units.CM2_PER_BARN

    if dpaPerSecond < 0:
        runLog.warning(
            "Negative DPA rate calculated at {}".format(dpaPerSecond),
            single=True,
            label="negativeDpaPerSecond",
        )
        # ensure physical meaning of dpaPerSecond, it is likely just slighly negative
        if dpaPerSecond < -1.0e-10:
            raise RuntimeError(
                "Calculated DPA rate is substantially negative at {}".format(
                    dpaPerSecond
                )
            )
        dpaPerSecond = 0.0

    return dpaPerSecond
