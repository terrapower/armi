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
from armi.physics import neutronics
from armi.physics import executers

ORDER = interfaces.STACK_ORDER.FLUX


# pylint: disable=too-many-public-methods
class GlobalFluxInterface(interfaces.Interface):
    """
    A general abstract interface for global flux-calculating modules.

    Should be subclassed by more specific implementations.
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

    def getHistoryParams(self):
        """Return parameters that will be added to assembly versus time history printouts."""
        return ["detailedDpa", "detailedDpaPeak", "detailedDpaPeakRate"]

    def interactBOC(self, cycle=None):
        interfaces.Interface.interactBOC(self, cycle)
        self.r.core.p.rxSwing = 0.0  # zero out rxSwing until EOC.
        self.r.core.p.maxDetailedDpaThisCycle = 0.0  # zero out cumulative params
        self.r.core.p.dpaFullWidthHalfMax = 0.0
        self.r.core.p.elevationOfACLP3Cycles = 0.0
        self.r.core.p.elevationOfACLP7Cycles = 0.0
        for b in self.r.core.getBlocks():
            b.p.detailedDpaThisCycle = 0.0
            b.p.newDPA = 0.0

    def interactEveryNode(self, cycle, node):
        """
        Calculate flux, power, and keff for this cycle and node.

        Flux, power, and keff are generally calculated at every timestep to ensure flux 
        is up to date with the reactor state.
        """
        interfaces.Interface.interactEveryNode(self, cycle, node)

        if self.r.p.timeNode == 0:
            self._bocKeff = self.r.core.p.keff  # track boc keff for rxSwing param.

    def interactCoupled(self, iteration):
        """Runs during a tightly-coupled physics iteration to updated the flux and power."""
        interfaces.Interface.interactCoupled(self, iteration)
        if self.r.p.timeNode == 0:
            self._bocKeff = self.r.core.p.keff  # track boc keff for rxSwing param.

    def interactEOC(self, cycle=None):
        interfaces.Interface.interactEOC(self, cycle)
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
            self.r.core.p.power / units.WATTS_PER_MW / self.r.core.powerMultiplier
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

    def calculateKeff(self, label="keff"):
        """
        Runs neutronics tool and returns keff without applying it to the reactor
        
        Used for things like direct-eigenvalue reactivity coefficients and CR worth iterations.
        For anything more complicated than getting keff, clients should
        call ``getExecuter`` to build their case. 
        """
        raise NotImplementedError()


class GlobalFluxInterfaceUsingExecuters(GlobalFluxInterface):
    """
    A global flux interface that makes use of the ARMI Executer system to run.

    Using Executers is optional but seems to allow easy interoperability between
    the myriad global flux solvers in the world.

    If a new global flux solver does not fit easily into the Executer pattern, then
    it will be best to just start from the base GlobalFluxInterface rather than
    trying to adjust the Executer pattern to fit.

    Notes
    -----
    This points library users to the Executer object, which is intended to
    provide commonly-used structure useful for many global flux plugins.
    """

    def interactEveryNode(self, cycle, node):
        """
        Calculate flux, power, and keff for this cycle and node.

        Flux, power, and keff are generally calculated at every timestep to ensure flux 
        is up to date with the reactor state.
        """
        executer = self.getExecuter(label=f"{self.cs.caseTitle}-flux-c{cycle}n{node}")
        executer.run()
        GlobalFluxInterface.interactEveryNode(self, cycle, node)

    def interactCoupled(self, iteration):
        """Runs during a tightly-coupled physics iteration to updated the flux and power."""
        executer = self.getExecuter(
            label=f"c{self.r.p.cycle}n{self.r.p.timeNode}i{iteration}"
        )
        executer.run()

        GlobalFluxInterface.interactCoupled(self, iteration)

    def getOptionsCls(self):
        """
        Get a blank options object.
        
        Subclass this to allow generic updating of options.
        """
        return GlobalFluxOptions

    def getExecuterCls(self):
        return GlobalFluxExecuter

    def getExecuterOptions(self, label=None):
        """
        Get an executer options object populated from current user settings and reactor.
        
        If you want to set settings more deliberately (e.g. to specify a cross section
        library rather than use an auto-derived name), use ``getOptionsCls`` and build 
        your own.
        """
        opts = self.getOptionsCls()(label)
        opts.fromUserSettings(self.cs)
        opts.fromReactor(self.r)
        return opts

    def getExecuter(self, options=None, label=None):
        """
        Get executer object for performing custom client calcs
        
        This allows plugins to update options in a somewhat generic 
        way. For example, reactivity coefficients plugin may want to
        request adjoint flux.
        """
        if options and label:
            raise ValueError(
                f"Cannot supply a label (`{label}`) and options at the same time. "
                "Apply label to options object first."
            )
        opts = options or self.getExecuterOptions(label)
        executer = self.getExecuterCls()(options=opts, reactor=self.r)
        return executer

    def calculateKeff(self, label="keff"):
        """
        Run global flux with current user options and just return keff without applying it.
        
        Used for things like direct-eigenvalue reactivity coefficients and CR worth iterations.
        """
        executer = self.getExecuter(label=label)
        executer.options.applyResultsToReactor = False
        output = executer.run()
        return output.getKeff()


class GlobalFluxOptions(executers.ExecutionOptions):
    """Data structure representing common options in Global Flux Solvers"""

    def __init__(self, label=None):
        executers.ExecutionOptions.__init__(self, label)
        self.real = True
        self.adjoint = False
        self.neutrons = True
        self.photons = None
        self.boundaryConditions = {}
        self.epsFissionSourceAvg = None
        self.epsFissionSourcePoint = None
        self.epsEigenvalue = None
        self.maxOuters = None
        # can happen in eig if Fredholm Alternative satisfied
        self.includeFixedSource = False
        self.eigenvalueProblem = True
        self.kernelName = None
        self.isRestart = None
        self.energyDepoCalcMethodStep = None  # for gamma transport/normalization
        self.detailedAxialExpansion = None
        self.boundaries = None
        self.xsKernel = None

        self.dpaPerFluence = None
        self.aclpDoseLimit = None
        self.burnSteps = None
        self.loadPadElevation = None
        self.loadPadLength = None

        self.geomType = None
        self.symmetry = None

    def fromUserSettings(self, cs):
        """
        Map user input settings from cs to a set of specific global flux options.

        This is not required; these options can alternatively be set programmatically.
        """
        self.kernelName = cs["neutronicsKernel"]
        self.isRestart = cs["restartNeutronics"]
        self.adjoint = neutronics.adjointCalculationRequested(cs)
        self.real = neutronics.realCalculationRequested(cs)
        self.detailedAxialExpansion = cs["detailedAxialExpansion"]
        self.eigenvalueProblem = cs["eigenProb"]

        # dose/dpa specific (should be separate subclass?)
        self.dpaPerFluence = cs["dpaPerFluence"]
        self.aclpDoseLimit = cs["aclpDoseLimit"]
        self.burnSteps = cs["burnSteps"]
        self.loadPadElevation = cs["loadPadElevation"]
        self.loadPadLength = cs["loadPadLength"]
        self.boundaries = cs["boundaries"]
        self.xsKernel = cs["xsKernel"]

    def fromReactor(self, reactor):
        self.geomType = reactor.core.geomType
        self.symmetry = reactor.core.symmetry


class GlobalFluxExecuter(executers.DefaultExecuter):
    """
    A short-lived object that  coordinates the prep, execution, and processing of a flux solve

    There are many forms of global flux solves:

    * Eigenvalue/Fixed source
    * Adjoint/real
    * Diffusion/PN/SN/MC
    * Finite difference/nodal

    There are also many reasons someone might need a flux solve:

    * Update multigroup flux and power on reactor and compute keff
    * Just compute keff in a temporary perturbed state
    * Just compute flux and adjoint flux on a state to

    There may also be some required transformations when a flux solve is done:

    * Add/remove edge assemblies
    * Apply a uniform axial mesh

    There are also I/O performance complexities, including running on fast local paths
    and copying certain user-defined files back to the working directory on error
    or completion. Given all these options and possible needs for information from
    global flux, this class provides a unified interface to everything.
    """

    def __init__(self, options, reactor):
        executers.DefaultExecuter.__init__(self, options, reactor)
        self.geomConverters = {}

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
        if self.options.detailedAxialExpansion:
            converter = self.geomConverters.get("axial")
            if not converter:
                converter = uniformMesh.UniformMeshGeometryConverter(None)
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
    def _undoGeometryTransformations(self):
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
                self.r, paramsToScaleSubset=self.options.paramsToScaleSubset
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

        # clear the converters in case this function gets called twice
        self.geomConverters = {}

    def edgeAssembliesAreNeeded(self):
        """
        True if edge assemblies are needed in this calculation

        We only need them in finite difference cases that are not full core.
        """
        return (
            "FD" in self.options.kernelName
            and self.options.symmetry == geometry.THIRD_CORE + geometry.PERIODIC
            and self.options.geomType == geometry.HEX
        )


class GlobalFluxResultMapper(interfaces.OutputReader):
    """
    A short-lived class that maps neutronics output data to a reactor mode.
    
    Neutronics results can come from a file or a pipe or in memory. 
    This is always subclassed for specific neutronics runs but contains
    some generic methods that are universally useful for 
    any global flux calculation. These are mostly along the lines of
    information that can be derived from other information, like 
    dpa rate coming from dpa deltas and cycle length. 
    """

    def getKeff(self):
        raise NotImplementedError()

    def clearFlux(self):
        """
        Delete flux on all blocks. Needed to prevent stale flux when partially reloading.
        """
        for b in self.r.core.getBlocks():
            b.p.mgFlux = []
            b.p.adjMgFlux = []
            b.p.mgFluxGamma = []
            b.p.extSrc = []

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

    def updateAssemblyLevelParams(self, excludedBlockTypes=None):
        for a in self.r.core.getAssemblies():
            if excludedBlockTypes is None:
                excludedBlockTypes = []
            totalAbs = 0.0  # for calculating assembly average k-inf
            totalSrc = 0.0
            for b in a:
                if b.getType() in excludedBlockTypes:
                    continue
                totalAbs += b.p.rateAbs
                totalSrc += b.p.rateProdNet

            a.p.maxPercentBu = a.getMaxParam("percentBu")
            a.p.maxDpaPeak = a.getMaxParam("detailedDpaPeak")
            a.p.timeToLimit = a.getMinParam("timeToLimit", Flags.FUEL)
            a.p.buLimit = a.getMaxParam("buLimit")

            # self.p.kgFis = self.getFissileMass()
            if totalAbs > 0:
                a.p.kInf = totalSrc / totalAbs  # assembly average k-inf.


class DoseResultsMapper(GlobalFluxResultMapper):
    """
    Updates fluence and dpa when time shifts.

    Often called after a depletion step.

    Notes
    -----
    We attempted to make this a set of stateless functions but the requirement of various
    options made it more of a data passing task than we liked. So it's just a lightweight
    and ephemeral results mapper.
    """

    def __init__(self, depletionSeconds, options):
        self.success = False
        self.options = options
        self.r = None
        self.depletionSeconds = depletionSeconds

    def apply(self, reactor):
        runLog.extra("Updating fluence and dpa on reactor based on depletion step.")
        self.r = reactor
        self.updateFluenceAndDpa(self.depletionSeconds)

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

            if self.options.dpaPerFluence:
                # do the less rigorous fluence -> DPA conversion if the user gave a factor.
                b.p.dpaPeakFromFluence = (
                    b.p.fastFluencePeak * self.options.dpaPerFluence
                )

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

            aclpDoseLimit = self.options.aclpDoseLimit
            aclpDoseLimit3 = (
                aclpDoseLimit / 3.0 * self.r.p.timeNode / self.options.burnSteps
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
                aclpDoseLimit / 7.0 * self.r.p.timeNode / self.options.burnSteps
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
        self.r.core.p.loadPadDpaAvg = peakAvg[0]
        self.r.core.p.loadPadDpaPeak = peakPeak[0]
        str_ = [
            "Above-core load pad (ACLP) summary. It starts at {0} cm above the "
            "bottom of the grid plate".format(self.options.loadPadElevation)
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
        loadPadBottom = self.options.loadPadElevation
        loadPadLength = self.options.loadPadLength
        if not loadPadBottom or not loadPadLength:
            # no load pad dose requested
            return None, None

        peakPeak = (0.0, None)
        peakAvg = (0.0, None)
        loadPadTop = loadPadBottom + loadPadLength

        zrange = numpy.linspace(loadPadBottom, loadPadTop, 100)
        for a in self.r.core.getAssemblies(Flags.FUEL):
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
