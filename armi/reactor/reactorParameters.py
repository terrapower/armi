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
Reactor parameter definitions
"""
import numpy

from armi.utils import units
from armi.reactor import parameters
from armi.reactor.parameters import ParamLocation
from armi.reactor import geometry


def defineReactorParameters():
    pDefs = parameters.ParameterDefinitionCollection()

    pDefs.add(
        parameters.Parameter(
            "rdIterNum",
            units="int",
            description="Number of region-density equilibrium iterations",
            location=ParamLocation.AVERAGE,
            saveToDB=True,
            default=parameters.NoDefault,
            setter=parameters.NoDefault,
            categories=set(),
        )
    )

    with pDefs.createBuilder(location=ParamLocation.AVERAGE, default=0.0) as pb:
        pb.defParam(
            "cycle",
            units="int",
            description="current cycle of the simulation",
            default=0,
        )

        pb.defParam(
            "cycleLength",
            units="EFP days",
            description="The cycle length of the reactor while power is being produced",
        )

        pb.defParam(
            "availabilityFactor",
            units="fraction",
            description="Availability factor of the plant. This is the fraction of the time that "
            "the plant is operating.",
            default=1.0,
        )

        pb.defParam(
            "capacityFactor",
            units="fraction",
            description="The fraction of power produced by the plant this cycle over the "
            "full-power, 100% uptime potential of the plant.",
            default=1.0,
        )

        pb.defParam("lcoe", units="$/kWh", description="Levelised cost of electricity")

        pb.defParam(
            "time",
            units="yr",
            description="time of reactor life from BOL to current time node",
            categories=["depletion"],
        )

        pb.defParam("timeNode", units="", description="timeNode", default=0)

    with pDefs.createBuilder(
        location=ParamLocation.AVERAGE, default=0.0, categories=["economics"]
    ) as pb:

        pb.defParam(
            "eFeedMT",
            units="MT",
            description="Total feed material required in reactor economics",
        )

        pb.defParam(
            "eFissile",
            units="MT",
            description="Fissile mass required in reactor economics",
        )

        pb.defParam(
            "eFuelCycleCost",
            units="$/MT",
            description="Cost of fuel cycle in an equilibrium-mode in reactor economics",
        )

        pb.defParam(
            "eFuelCycleCostRate",
            units="$/year",
            description="Rate of fuel cycle cost in an equilibrium mode in reactor economics",
        )

        pb.defParam(
            "eProduct",
            units="MT",
            description="Total mass of manufactured fuel in reactor economics",
        )

        pb.defParam(
            "eSWU",
            units="kgSWU",
            description="Separative work units in reactor economics",
        )

        pb.defParam(
            "eTailsMT", units="MT", description="Depleted Uranium in reactor economics"
        )
    return pDefs


def defineCoreParameters():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder() as pb:

        def detailedNucKeys(self, value):
            if value is None or isinstance(value, numpy.ndarray):
                self._p_detailedNucKeys = value
            else:
                self._p_detailedNucKeys = numpy.array(value)

        pb.defParam(
            "detailedNucKeys",
            setter=detailedNucKeys,
            units="ZZZAAA (ZZZ atomic number, AAA mass number, + 100 * m for metastable states",
            description="Nuclide vector keys, used to map densities in b.p.detailedNDens and a.p.detailedNDens",
            saveToDB=True,
            default=None,
        )

    with pDefs.createBuilder(location=ParamLocation.CENTROID) as pb:

        pb.defParam(
            "orientation",
            units="degrees",
            description=(
                "Triple representing rotations counterclockwise around each spatial axis. For example, "
                "a hex assembly rotated by 1/6th has orientation (0,0,60.0)"
            ),
            default=None,
        )

    with pDefs.createBuilder(location=ParamLocation.AVERAGE, default=0.0) as pb:

        pb.defParam("currentPercentExpanded", units="", description="")

        pb.defParam(
            "maxAssemNum", units=None, description="maximum assembly number", default=0
        )

        pb.defParam(
            "numAssembliesFabricated",
            units="",
            description="numAssembliesFabricated",
            default=0,
        )

        pb.defParam(
            "numAssembliesInSFP", units="", description="numAssembliesInSFP", default=0
        )

        pb.defParam("numMoves", units="", description="numMoves", default=0)

        pb.defParam("timingDepletion", units="", description="timingDepletion")

        pb.defParam("timingDif3d", units="", description="timingDif3d")

        pb.defParam("timingDistribute", units="", description="timingDistribute")

        pb.defParam("timingMc2", units="", description="timingMc2")

        pb.defParam("timingSubchan", units="", description="timingSubchan")

    with pDefs.createBuilder(default=0.0, location="N/A") as pb:

        pb.defParam(
            "breedingRatio2",
            units="N/A",
            description="Ratio of fissile Burned and discharged to fissile discharged",
            saveToDB=False,
        )

        pb.defParam(
            "crWorthRequiredPrimary",
            units="$",
            description="The total worth in $ required for primary control rods to shutdown reactor accounting for uncertainties and margins",
        )

        pb.defParam(
            "crWorthRequiredSecondary",
            units="$",
            description="The total worth in $ required for secondary control rods to shutdown reactor accounting for uncertainties and margins",
        )

        pb.defParam(
            "critSearchSlope", units=None, description="Critical keff search slope"
        )

        pb.defParam(
            "directPertKeff",
            units=None,
            description="K-eff is computed for the perturbed case with a direct calculation",
        )

        pb.defParam(
            "distortionReactivity",
            units="pcm",
            description="The reactivity effect of the current distortions",
            default=None,
        )

        pb.defParam(
            "doublingTime",
            units="EFPY",
            description="The time it takes to produce enough spent fuel to fuel a daughter reactor",
        )

        pb.defParam("fissileMass", units="g", description="Fissile mass of the reactor")

        pb.defParam(
            "heavyMetalMass", units="g", description="Heavy Metal mass of the reactor"
        )

        pb.defParam(
            "innerMatrixIndex",
            units=None,
            description="The item index of the inner matrix in an optimization case",
        )

        pb.defParam("keffUnc", units=None, description="Uncontrolled keff")

        pb.defParam(
            "lastKeff",
            units=None,
            description="Previously calculated Keff for potential keff convergence",
        )

        pb.defParam(
            "loadPadDpaAvg",
            units="dpa",
            description="The highest average dpa in any load pad",
        )

        pb.defParam(
            "loadPadDpaPeak", units="dpa", description="The peak dpa in any load pad"
        )

        pb.defParam("maxcladFCCI", units="", description="", default=0.0)

        pb.defParam(
            "maxCladulof",
            units=units.DEGC,
            description="Max Clading Temperature in Unprotected Loss of Flow (ULOF) transient",
        )

        pb.defParam(
            "maxCladulohs",
            units=units.DEGC,
            description="Max Clading Temperature in Unprotected Loss of Heat Sink (ULOHS) transient",
        )

        pb.defParam(
            "maxCladutop",
            units=units.DEGC,
            description="Max Clading Temperature in Unprotected Transient Overpower (UTOP) transient",
        )

        pb.defParam(
            "maxCladptop",
            units=units.DEGC,
            description="Max Clading Temperature in protected Transient Overpower (PTOP) transient",
        )

        pb.defParam(
            "maxCladlockrotor",
            units=units.DEGC,
            description="Max Clading Temperature in lock rotor transient",
        )
        pb.defParam(
            "maxCladplohs",
            units=units.DEGC,
            description="Max Clading Temperature in protected loss of heat sink (PLOHS) transient",
        )
        pb.defParam(
            "maxCladplof",
            units=units.DEGC,
            description="Max Clading Temperature in protected loss of flow (PLOF) transient",
        )
        pb.defParam(
            "maxCladplof2pump",
            units=units.DEGC,
            description="Max Clading Temperature in protected loss of 2 primary pumps (PLOF2pump) transient",
        )

        pb.defParam(
            "maxCladoscillation",
            units=units.DEGC,
            description="Max Clading Temperature in oscillation-driven transient",
        )
        pb.defParam(
            "maxFueloscillation",
            units=units.DEGC,
            description="Max Fuel Temperature in oscillation-driven transient",
        )

        pb.defParam(
            "maxCladpowerdefect",
            units=units.DEGC,
            description="Max Clading Temperature in powerdefect transient",
        )
        pb.defParam(
            "maxFuelpowerdefect",
            units=units.DEGC,
            description="Max Fuel Temperature in powerdefect transient",
        )

        pb.defParam(
            "maxCladsteadystate",
            units=units.DEGC,
            description="Max Clading Temperature in steady state transient",
        )

        pb.defParam(
            "maxDPA",
            units="dpa",
            description="Maximum DPA based on pin-level max if it exists, block level max otherwise",
        )

        pb.defParam("maxFuelulof", units=units.DEGC, description="maxFuelulof")

        pb.defParam("maxFuelulohs", units=units.DEGC, description="maxFuelulohs")

        pb.defParam("maxFuelutop", units=units.DEGC, description="maxFuelutop")

        pb.defParam(
            "maxFuelptop",
            units=units.DEGC,
            description="Max Clading Temperature in protected Transient Overpower (PTOP) transient",
        )

        pb.defParam(
            "maxFuellockrotor",
            units=units.DEGC,
            description="Max Clading Temperature in lock rotor transient",
        )
        pb.defParam(
            "maxFuelplohs",
            units=units.DEGC,
            description="Max Clading Temperature in protected loss of heat sink (PLOHS) transient",
        )
        pb.defParam(
            "maxFuelplof",
            units=units.DEGC,
            description="Max Clading Temperature in protected loss of flow (PLOF) transient",
        )
        pb.defParam(
            "maxFuelplof2pump",
            units=units.DEGC,
            description="Max Clading Temperature in protected loss of 2 primary pumps (PLOF2pump) transient",
        )
        pb.defParam("maxGridDpa", units="dpa", description="Grid plate max dpa")

        pb.defParam(
            "maxProcessMemoryInMB",
            units="MB",
            description="Maximum memory used by an ARMI process",
        )

        pb.defParam(
            "maxTH2SigmaCladIDT",
            units=units.DEGC,
            description="Max 2-sigma temperature of the inner-diameter of the cladding",
            default=0.0,
            categories=["block-max"],
        )

        pb.defParam(
            "maxTranPCT",
            units=units.DEGC,
            description="Max Peak Clading Temperature of transients",
        )

        pb.defParam(
            "minProcessMemoryInMB",
            units="MB",
            description="Minimum memory used by an ARMI process",
        )

        pb.defParam(
            "minutesSinceStart",
            units="min",
            description="Run time since the beginning of the calculation",
        )

        pb.defParam(
            "outsideFuelRing",
            units="int",
            description="The ring with the fraction of flux that best meets the target",
        )

        pb.defParam(
            "outsideFuelRingFluxFr",
            units=None,
            description="Ratio of the flux in a ring to the total reactor fuel flux",
        )

        pb.defParam(
            "peakGridDpaAt60Years",
            units="dpa",
            description="Grid plate peak dpa after 60 years irradiation",
        )

        pb.defParam(
            "topInitiator",
            units="$",
            description="Worth in $ of most valuable rod in critical position",
        )

        pb.defParam(
            "totalIntrinsicSource",
            units="neutrons/s",
            description="Full core intrinsic neutron source from spontaneous fissions before a decay period",
        )

        pb.defParam(
            "totalIntrinsicSourceDecayed",
            units="neutrons/s",
            description="Full core intrinsic source from spontaneous fissions after a decay period",
        )

    with pDefs.createBuilder(
        location=ParamLocation.AVERAGE, default=0.0, categories=["thermal hydraulics"]
    ) as pb:

        pb.defParam(
            "assemblyPumpHead",
            units="Pa",
            description="Pressure drop for the max power assembly in zone",
        )

        pb.defParam(
            "CoreAvgTOut",
            units=units.DEGC,
            description="Core average outlet temperature",
        )

        pb.defParam("CoreMdot", units="kg/s", description="Mass flow rate of full core")

        pb.defParam(
            "outletTempIdeal",
            units=units.DEGC,
            description="Average outlet tempeture loop through all assemblies after doing TH",
        )

        pb.defParam(
            "SCMaxDilationPressure",
            units="Pa",
            description="The maximum dilation pressure in the core",
        )

        pb.defParam(
            "SCorificeEfficiency",
            units=None,
            description="Ratio of total flow rate for the optimized orificing scheme to total flow rate for an ideal orificing scheme",
        )

        pb.defParam(
            "SCovercoolingRatio",
            units=None,
            description="Ratio of the max flow rate to the average flow rate",
        )

        pb.defParam(
            "THmaxDeltaPPump",
            units="Pa",
            description="The maximum pumping pressure rise required to pump the given mass flow rate through the rod bundle",
        )

        pb.defParam(
            "THmaxDilationPressure", units="", description="THmaxDilationPressure"
        )

        pb.defParam(
            "THoutletTempIdeal",
            units=units.DEGC,
            description="Average outlet temperature loop through all assemblies after doing TH",
        )

        pb.defParam("vesselTemp", units=units.DEGC, description="vessel temperature")

        pb.defParam(
            "LMDT",
            units=units.DEGC,
            description="Log mean temperature difference in heat exchanger",
        )

        pb.defParam(
            "peakTemperature",
            units=units.DEGC,
            description="peak temperature anywhere in the reactor",
        )

    with pDefs.createBuilder(
        location=ParamLocation.AVERAGE, default=0.0, categories=["neutronics"]
    ) as pb:

        pb.defParam(
            "maxdetailedDpaPeak",
            units="dpa",
            description="Highest peak dpa of any block in the problem",
        )

        pb.defParam(
            "maxFlux", units="n/cm^2/s", description="Max neutron flux in the core"
        )

        pb.defParam(
            "adjWeightedFisSrc",
            units="1/cm^2/s^2",
            description="Volume-integrated adjoint flux weighted fission source",
        )

        pb.defParam(
            "maxDetailedDpaThisCycle",
            units="dpa",
            description="Max increase in dpa this cycle (only defined at EOC)",
        )

        pb.defParam(
            "dpaFullWidthHalfMax",
            units="cm",
            description="Full width at half max of the detailedDpa distribution",
        )

        pb.defParam(
            "elevationOfACLP3Cycles",
            units="cm",
            description="minimum axial location of the ACLP for 3 cycles at peak dose",
        )

        pb.defParam(
            "elevationOfACLP7Cycles",
            units="cm",
            description="minimum axial location of the ACLP for 7 cycles at peak dose",
        )

        pb.defParam(
            "maxpercentBu",
            units="%FIMA",
            description="Max percent burnup on any block in the problem",
        )

        pb.defParam("rxSwing", units="pcm", description="Reactivity swing")

        pb.defParam(
            "maxBuF",
            units="%",
            description="Maximum burnup seen in any feed assemblies",
        )

        pb.defParam(
            "maxBuI",
            units="%",
            description="Maximum burnup seen in any igniter assemblies",
        )

        pb.defParam("keff", units=None, description="Global multiplication factor")

        pb.defParam(
            "partisnKeff",
            units=None,
            description="Global multiplication factor from PARTISN transport calculation",
        )

        pb.defParam(
            "peakKeff", units=None, description="Maximum keff in the simulation"
        )

        pb.defParam(
            "fastFluxFrAvg", units=None, description="Fast flux fraction average"
        )

        pb.defParam(
            "leakageFracTotal", units=None, description="Total leakage fraction"
        )

        pb.defParam(
            "leakageFracPlanar", units=None, description="Leakage fraction in planar"
        )

        pb.defParam(
            "leakageFracAxial",
            units=None,
            description="Leakage fraction in axial direction",
        )

        pb.defParam(
            "maxpdens",
            units="W/cm^3",
            description="Maximum avg. volumetric power density of all blocks",
        )

        pb.defParam(
            "maxPD",
            units="MW/m^2",
            description="Maximum areal power density of all assemblies",
        )

        pb.defParam(
            "jumpRing",
            units=None,
            description=(
                "Radial ring number where bred-up fuel assemblies shuffle jump from the low power to the "
                "high power region."
            ),
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        categories=["reactivity coefficients"],
    ) as pb:

        pb.defParam("axial", units="cents/K", description="Axial expansion coefficient")

        pb.defParam("doppler", units="cents/K", description="Doppler coefficient")

        pb.defParam(
            "dopplerConst", units="cents * K^(n-1)", description="Doppler constant"
        )

        pb.defParam(
            "fuelDensity", units="cents/K", description="Fuel temperature coefficient"
        )

        pb.defParam(
            "coolantDensity",
            units="cents/K",
            description="Coolant temperature coefficient",
        )

        pb.defParam(
            "totalCoolantDensity",
            units="cents/K",
            description="Coolant temperature coefficient weighted to include bond and interstitial effects",
        )

        pb.defParam(
            "cladDensity", units="cents/K", description="Clad temperature coefficient"
        )

        pb.defParam(
            "structureDensity",
            units="cents/K",
            description="Structure temperature coefficient",
        )

        pb.defParam(
            "Voideddoppler", units="cents/K", description="Voided Doppler coefficient"
        )

        pb.defParam(
            "VoideddopplerConst",
            units="cents * K^(n-1)",
            description="Voided Doppler constant",
        )

        pb.defParam("voidWorth", units="$", description="Coolant void worth")

        pb.defParam("voidedKeff", units=None, description="Voided keff")

        pb.defParam(
            "radialHT9",
            units="cents/K",
            description="Radial expansion coefficient when driven by thermal expansion of HT9.",
        )

        pb.defParam(
            "radialSS316",
            units="cents/K",
            description="Radial expansion coefficient when driven by thermal expansion of SS316.",
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        categories=["reactivity coefficients", "kinetics"],
    ) as pb:

        pb.defParam(
            "beta", units=None, description="Effective delayed neutron fraction"
        )

        pb.defParam(
            "betaComponents",
            units=None,
            description="Group-wise delayed neutron component",
            default=None,
        )

        pb.defParam(
            "betaDecayConstants",
            units="1/s",
            description="Group-wise decay constant for precursor",
            default=None,
        )

        pb.defParam(
            "promptNeutronGenerationTime",
            units="s",
            description="Prompt neutron generation time",
        )

        pb.defParam(
            "promptNeutronLifetime", units="s", description="Prompt neutron lifetime"
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        categories=["reactivity coefficients", "core wide"],
    ) as pb:
        # CORE WIDE REACTIVITY COEFFICIENTS
        pb.defParam(
            "rxFuelAxialExpansionCoeffPerTemp",
            units="dk/kk'-K",
            description="Fuel Axial Expansion Coefficient",
        )

        pb.defParam(
            "rxGridPlateRadialExpansionCoeffPerTemp",
            units="dk/kk'-K",
            description="Grid Plate Radial Expansion Coefficient",
        )

        pb.defParam(
            "rxAclpRadialExpansionCoeffPerTemp",
            units="dk/kk'-K",
            description="ACLP Radial Expansion Coefficient",
        )

        pb.defParam(
            "rxControlRodDrivelineExpansionCoeffPerTemp",
            units="dk/kk'-K",
            description="control rod driveline expansion coefficient",
        )

        pb.defParam(
            "rxCoreWideCoolantVoidWorth",
            units="dk/kk'",
            description="Core-Wide Coolant Void Worth",
        )

        pb.defParam(
            "rxSpatiallyDependentCoolantVoidWorth",
            units="dk/kk'",
            description="Spatially-Dependent Coolant Void Worth",
        )

        # FUEL COEFFICIENTS
        pb.defParam(
            "rxFuelDensityCoeffPerTemp",
            units="dk/kk'-K",
            description="Fuel Density Coefficient",
        )

        pb.defParam(
            "rxFuelDopplerCoeffPerTemp",
            units="dk/kk'-K",
            description="Fuel Doppler Coefficient",
        )

        pb.defParam(
            "rxFuelDopplerConstant",
            units="dk/kk' K**(n-1)",
            description="Fuel Doppler Constant",
        )

        pb.defParam(
            "rxFuelVoidedDopplerCoeffPerTemp",
            units="dk/kk'-K",
            description="Fuel Voided-Coolant Doppler Coefficient",
        )

        pb.defParam(
            "rxFuelVoidedDopplerConstant",
            units="dk/kk' K**(n-1)",
            description="Fuel Voided-Coolant Doppler Constant",
        )

        pb.defParam(
            "rxFuelTemperatureCoeffPerTemp",
            units="dk/kk'-K",
            description="Fuel Temperature Coefficient",
        )

        pb.defParam(
            "rxFuelVoidedTemperatureCoeffPerTemp",
            units="dk/kk'-K",
            description="Fuel Voided-Coolant Temperature Coefficient",
        )

        # CLAD COEFFICIENTS
        pb.defParam(
            "rxCladDensityCoeffPerTemp",
            units="dk/kk'-K",
            description="Clad Density Coefficient",
        )

        pb.defParam(
            "rxCladDopplerCoeffPerTemp",
            units="dk/kk'-K",
            description="Clad Doppler Coefficient",
        )

        pb.defParam(
            "rxCladDopplerConstant",
            units="dk/kk' K**(n-1)",
            description="Clad Doppler Constant",
        )

        pb.defParam(
            "rxCladTemperatureCoeffPerTemp",
            units="dk/kk'-K",
            description="Clad Temperature Coefficient",
        )

        # STRUCTURE COEFFICIENTS
        pb.defParam(
            "rxStructureDensityCoeffPerTemp",
            units="dk/kk'-K",
            description="Structure Density Coefficient",
        )

        pb.defParam(
            "rxStructureDopplerCoeffPerTemp",
            units="dk/kk'-K",
            description="Structure Doppler Coefficient",
        )

        pb.defParam(
            "rxStructureDopplerConstant",
            units="dk/kk' K**(n-1)",
            description="Structure Doppler Constant",
        )

        pb.defParam(
            "rxStructureTemperatureCoeffPerTemp",
            units="dk/kk'-K",
            description="Structure Temperature Coefficient",
        )

        # COOLANT COEFFICIENTS
        pb.defParam(
            "rxCoolantDensityCoeffPerTemp",
            units="dk/kk'-K",
            description="Coolant Density Coefficient",
        )

        pb.defParam(
            "rxCoolantTemperatureCoeffPerTemp",
            units="dk/kk'-K",
            description="Coolant Temperature Coefficient",
        )

    with pDefs.createBuilder(
        location=ParamLocation.AVERAGE, categories=["equilibrium"]
    ) as pb:

        pb.defParam("boecKeff", units=None, description="BOEC Keff", default=0.0)

        pb.defParam(
            "cyclics",
            units="int",
            description=(
                "The number of cyclic mode equilibrium-cycle "
                "iterations that have occurred so far"
            ),
            default=0,
        )

        pb.defParam(
            "maxCyclicNErr",
            units=None,
            description="Maximum relative number density error",
            default=0.0,
        )

    with pDefs.createBuilder(
        location=ParamLocation.AVERAGE, categories=["equilibrium"]
    ) as pb:

        pb.defParam(
            "breedingRatio",
            units="N/A",
            description="Breeding ratio of the reactor",
            default=0.0,
        )

        pb.defParam("ConvRatioCore", units="?", description="?")

        pb.defParam("absPerFisCore", units="?", description="?")

        pb.defParam(
            "axialExpansionPercent",
            units="%",
            description="Percent of axial growth of fuel blocks",
            default=0.0,
        )

        pb.defParam("corePow", units="?", description="?")

        pb.defParam("coupledIteration", units="?", description="?", default=0)

        pb.defParam("fisFrac", units="?", description="?")

        pb.defParam("fisRateCore", units="?", description="?")

        pb.defParam(
            "maxcladWastage",
            units="microns",
            description="Maximum clad wastage in any block in the core",
            default=0.0,
            categories=["block-max"],
        )

        pb.defParam(
            "maxdilationTotal",
            units="?",
            description="?",
            default=0.0,
            categories=["block-max"],
        )

        pb.defParam(
            "maxresidence",
            units="?",
            description="?",
            default=0.0,
            categories=["block-max"],
        )

        pb.defParam("medAbsCore", units="?", description="?")

        pb.defParam("medFluxCore", units="?", description="?")

        pb.defParam("medSrcCore", units="?", description="?")

        pb.defParam("pkFlux", units="?", description="?")

        pb.defParam(
            "power",
            units="W",
            description="Rated thermal power of the reactor core. Corresponds to the "
            "nuclear power generated in the core.",
        )

        pb.defParam(
            "powerDecay",
            units="W",
            description="Decay power from decaying radionuclides",
        )

    return pDefs
