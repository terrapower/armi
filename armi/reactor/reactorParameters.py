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
Reactor parameter definitions.
"""
import numpy

from armi.utils import units
from armi.reactor import parameters
from armi.reactor.parameters import ParamLocation


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
            units="days",
            description="Length of the cycle, including outage time described by availabilityFactor",
        )

        pb.defParam("stepLength", units="days", description="Length of current step")

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
            description="Time of reactor life from BOL to current time node",
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
            "eSWU",
            units="kgSWU",
            description="Separative work units in reactor economics",
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

        pb.defParam("numMoves", units="", description="numMoves", default=0)

    with pDefs.createBuilder(location="N/A", categories=["control rods"]) as pb:

        pb.defParam(
            "crMostValuablePrimaryRodLocation",
            default="",
            units=None,
            saveToDB=True,
            description=(
                "Core assembly location for the most valuable primary control rod."
            ),
        )
        pb.defParam(
            "crMostValuableSecondaryRodLocation",
            default="",
            units=None,
            saveToDB=True,
            description=(
                "Core assembly location for the most valuable secondary control rod."
            ),
        )
        pb.defParam(
            "crWorthRequiredPrimary",
            default=0.0,
            units="pcm",
            saveToDB=True,
            description="Worth requirement for the primary control rods in the reactor core to achieve safe shutdown.",
        )
        pb.defParam(
            "crWorthRequiredSecondary",
            default=0.0,
            units="pcm",
            saveToDB=True,
            description="Worth requirement for the secondary control rods in the reactor core to achieve safe shutdown.",
        )
        pb.defParam(
            "crTransientOverpowerWorth",
            default=0.0,
            units="pcm",
            saveToDB=True,
            description=(
                "Reactivity worth introduced by removal of the highest worth primary "
                "control rod from the core, starting from its critical position"
            ),
        )

    with pDefs.createBuilder() as pb:

        pb.defParam(
            "axialMesh",
            units="cm",
            description="Global axial mesh of the reactor core from bottom to top.",
            default=None,
            location=ParamLocation.TOP,
        )

    with pDefs.createBuilder(default=0.0, location="N/A") as pb:

        pb.defParam(
            "referenceBlockAxialMesh",
            units="cm",
            description="The axial block boundaries that assemblies should conform to in a uniform mesh case.",
            default=None,
        )

        pb.defParam(
            "critSearchSlope", units=None, description="Critical keff search slope"
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
            "keffUnc",
            units=None,
            saveToDB=True,
            default=0.0,
            description=(
                "Uncontrolled k-effective for the reactor core (with control rods fully removed).."
            ),
        )

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
            "maxDPA",
            units="dpa",
            description="Maximum DPA based on pin-level max if it exists, block level max otherwise",
        )

        pb.defParam("maxGridDpa", units="dpa", description="Grid plate max dpa")

        pb.defParam(
            "maxProcessMemoryInMB",
            units="MB",
            description="Maximum memory used by an ARMI process",
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

    with pDefs.createBuilder(
        location=ParamLocation.AVERAGE, default=0.0, categories=["neutronics"]
    ) as pb:

        pb.defParam(
            "power",
            units="W",
            description="Thermal power of the reactor core. Corresponds to the "
            "nuclear power generated in the core.",
        )

        pb.defParam(
            "powerDecay",
            units="W",
            description="Decay power from decaying radionuclides",
        )

        pb.defParam("medAbsCore", units="?", description="?")

        pb.defParam("medFluxCore", units="?", description="?")

        pb.defParam("medSrcCore", units="?", description="?")

        pb.defParam("pkFlux", units="?", description="?")

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
            "beta",
            units=None,
            description="Effective delayed neutron fraction",
            default=None,
        )

        pb.defParam(
            "betaComponents",
            units=None,
            description="Group-wise delayed neutron fractions.",
            default=None,
        )

        pb.defParam(
            "betaDecayConstants",
            units="1/s",
            description="Group-wise precursor decay constants",
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

        pb.defParam("coupledIteration", units="?", description="?", default=0)

        pb.defParam("fisFrac", units="?", description="?")

        pb.defParam("fisRateCore", units="?", description="?")

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

    return pDefs
