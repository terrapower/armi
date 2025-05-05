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

"""Reactor parameter definitions."""
from armi.reactor import parameters
from armi.reactor.parameters import ParamLocation
from armi.utils import units


def defineReactorParameters():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder(location=ParamLocation.AVERAGE, default=0.0) as pb:
        pb.defParam(
            "cycle",
            units=units.UNITLESS,
            description="Current cycle of the simulation (integer)",
            default=0,
        )

        pb.defParam(
            "cycleLength",
            units=units.DAYS,
            description="Length of the cycle, including outage time described by availabilityFactor",
        )

        pb.defParam(
            "stepLength", units=units.DAYS, description="Length of current step"
        )

        pb.defParam(
            "availabilityFactor",
            units=units.UNITLESS,
            description="Availability factor of the plant. This is the fraction of the time that "
            "the plant is operating.",
            default=1.0,
        )

        pb.defParam(
            "capacityFactor",
            units=units.UNITLESS,
            description="The fraction of power produced by the plant this cycle over the "
            "full-power, 100% uptime potential of the plant.",
            default=1.0,
        )

        pb.defParam(
            "time",
            units=units.YEARS,
            description="Time of reactor life from BOL to current time node",
            categories=["depletion"],
        )

        pb.defParam(
            "timeNode", units=units.UNITLESS, description="Integer timeNode", default=0
        )

        pb.defParam(
            "maxAssemNum",
            units=units.UNITLESS,
            description="Max number of assemblies created so far in the Reactor (integer)",
            default=0,
        )

    return pDefs


def defineCoreParameters():
    pDefs = parameters.ParameterDefinitionCollection()

    with pDefs.createBuilder(location=ParamLocation.CENTROID) as pb:
        pb.defParam(
            "orientation",
            units=units.DEGREES,
            description=(
                "Triple representing rotations counterclockwise around each spatial axis. For "
                "example, a hex assembly rotated by 1/6th has orientation (0,0,60.0)"
            ),
            default=None,
        )

    with pDefs.createBuilder(location=ParamLocation.AVERAGE, default=0.0) as pb:
        pb.defParam(
            "maxAssemNum",
            units=units.UNITLESS,
            description="Maximum assembly number",
            default=0,
        )

        pb.defParam("numMoves", units=units.UNITLESS, description="numMoves", default=0)

    with pDefs.createBuilder(location="N/A", categories=["control rods"]) as pb:
        pb.defParam(
            "crMostValuablePrimaryRodLocation",
            default="",
            units=units.UNITLESS,
            saveToDB=True,
            description=(
                "Core assembly location for the most valuable primary control rod."
            ),
        )
        pb.defParam(
            "crMostValuableSecondaryRodLocation",
            default="",
            units=units.UNITLESS,
            saveToDB=True,
            description=(
                "Core assembly location for the most valuable secondary control rod."
            ),
        )
        pb.defParam(
            "crTransientOverpowerWorth",
            default=0.0,
            units=units.PCM,
            saveToDB=True,
            description=(
                "Reactivity worth introduced by removal of the highest worth primary control rod "
                "from the core, starting from its critical position"
            ),
        )

    with pDefs.createBuilder() as pb:
        pb.defParam(
            "axialMesh",
            units=units.CM,
            description="Global axial mesh of the reactor core from bottom to top.",
            default=None,
            location=ParamLocation.TOP,
        )

    with pDefs.createBuilder(default=0.0, location="N/A") as pb:
        pb.defParam(
            "referenceBlockAxialMesh",
            units=units.CM,
            description=(
                "The axial block boundaries that assemblies should conform to in a "
                "uniform mesh case."
            ),
            default=None,
        )

        pb.defParam(
            "fissileMass", units=units.GRAMS, description="Fissile mass of the reactor"
        )

        pb.defParam(
            "heavyMetalMass",
            units=units.GRAMS,
            description="Heavy Metal mass of the reactor",
        )

        pb.defParam(
            "keffUnc",
            units=units.UNITLESS,
            saveToDB=True,
            default=0.0,
            description="Uncontrolled k-effective for the reactor core (with control rods fully removed).",
        )

        pb.defParam(
            "maxDPA",
            units=units.DPA,
            description="Maximum DPA based on pin-level max if it exists, block level max otherwise",
        )

        pb.defParam("maxGridDpa", units=units.DPA, description="Grid plate max dpa")

        pb.defParam(
            "maxProcessMemoryInMB",
            units=units.MB,
            description="Maximum memory used by an ARMI process",
        )

        pb.defParam(
            "minProcessMemoryInMB",
            units=units.MB,
            description="Minimum memory used by an ARMI process",
        )

        pb.defParam(
            "minutesSinceStart",
            units=units.MINUTES,
            description="Run time since the beginning of the calculation",
        )

        pb.defParam(
            "peakGridDpaAt60Years",
            units=units.DPA,
            description="Grid plate peak dpa after 60 years irradiation",
        )

    with pDefs.createBuilder(
        location=ParamLocation.AVERAGE, default=0.0, categories=["thermal hydraulics"]
    ) as pb:

        pb.defParam(
            "THmaxDeltaPPump",
            units=units.PASCALS,
            description="The maximum pumping pressure rise required to pump the given mass flow "
            + "rate through the rod bundle",
        )

        pb.defParam(
            "THmaxDilationPressure",
            units=units.PASCALS,
            description="THmaxDilationPressure",
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
            units=units.WATTS,
            description="Thermal power of the reactor core. Corresponds to the "
            "nuclear power generated in the core.",
        )

        pb.defParam(
            "powerDensity",
            units=f"{units.WATTS}/{units.GRAMS}",
            description="BOL Power density of the reactor core, in units of Watts per"
            "grams of Heavy Metal Mass. After the BOL, the power parameter will be set, "
            "and this will entirely overridden by that.",
        )

        pb.defParam(
            "medAbsCore",
            units=units.EV,
            description="Median energy of neutrons absorbed in the core",
        )

        pb.defParam(
            "medFluxCore",
            units=units.EV,
            description="Median energy of neutrons in the core",
        )

        pb.defParam(
            "medSrcCore",
            units=units.EV,
            description="Median energy of source neutrons in the core?",
        )

        pb.defParam(
            "pkFlux",
            units=f"n/{units.CM}^2/{units.SECONDS}",
            description="Peak flux in the core",
        )

        pb.defParam(
            "maxdetailedDpaPeak",
            units=units.DPA,
            description="Highest peak dpa of any block in the problem",
        )

        pb.defParam(
            "maxFlux",
            units=f"n/{units.CM}^2/{units.SECONDS}",
            description="Max neutron flux in the core",
        )

        pb.defParam(
            "maxDetailedDpaThisCycle",
            units=units.DPA,
            description="Max increase in dpa this cycle (only defined at EOC)",
        )

        pb.defParam(
            "dpaFullWidthHalfMax",
            units=units.CM,
            description="Full width at half max of the detailedDpa distribution",
        )

        pb.defParam(
            "elevationOfACLP3Cycles",
            units=units.CM,
            description="minimum axial location of the ACLP for 3 cycles at peak dose",
        )

        pb.defParam(
            "elevationOfACLP7Cycles",
            units=units.CM,
            description="minimum axial location of the ACLP for 7 cycles at peak dose",
        )

        pb.defParam(
            "maxpercentBu",
            units=units.PERCENT_FIMA,
            description="Max percent burnup on any block in the problem",
        )

        pb.defParam("rxSwing", units=units.PCM, description="Reactivity swing")

        pb.defParam(
            "maxBuF",
            units=units.PERCENT,
            description="Maximum burnup seen in any feed assemblies",
        )

        pb.defParam(
            "maxBuI",
            units=units.PERCENT,
            description="Maximum burnup seen in any igniter assemblies",
        )

        pb.defParam(
            "keff", units=units.UNITLESS, description="Global multiplication factor"
        )

        pb.defParam(
            "peakKeff",
            units=units.UNITLESS,
            description="Maximum keff in the simulation",
        )

        pb.defParam(
            "fastFluxFrAvg",
            units=units.UNITLESS,
            description="Fast flux fraction average",
        )

        pb.defParam(
            "leakageFracTotal",
            units=units.UNITLESS,
            description="Total leakage fraction",
        )

        pb.defParam(
            "leakageFracPlanar",
            units=units.UNITLESS,
            description="Leakage fraction in planar",
        )

        pb.defParam(
            "leakageFracAxial",
            units=units.UNITLESS,
            description="Leakage fraction in axial direction",
        )

        pb.defParam(
            "maxpdens",
            units=f"{units.WATTS}/{units.CM}^3",
            description="Maximum avg. volumetric power density of all blocks",
        )

        pb.defParam(
            "maxPD",
            units=f"{units.MW}/{units.METERS}^2",
            description="Maximum areal power density of all assemblies",
        )

        pb.defParam(
            "jumpRing",
            units=units.UNITLESS,
            description=(
                "Radial ring number where bred-up fuel assemblies shuffle jump from the low power "
                "to the high power region."
            ),
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        categories=["reactivity coefficients", "kinetics"],
    ) as pb:

        pb.defParam(
            "beta",
            units=units.UNITLESS,
            description="Effective delayed neutron fraction",
            default=None,
        )

        pb.defParam(
            "betaComponents",
            units=units.UNITLESS,
            description="Group-wise delayed neutron fractions",
            default=None,
        )

        pb.defParam(
            "betaDecayConstants",
            units=f"1/{units.SECONDS}",
            description="Group-wise precursor decay constants",
            default=None,
        )

    with pDefs.createBuilder(
        default=0.0,
        location=ParamLocation.AVERAGE,
        categories=["reactivity coefficients", "core wide"],
    ) as pb:
        # CORE WIDE REACTIVITY COEFFICIENTS
        pb.defParam(
            "rxFuelAxialExpansionCoeffPerTemp",
            units=f"{units.REACTIVITY}/{units.DEGK}",
            description="Fuel Axial Expansion Coefficient",
        )

        pb.defParam(
            "rxGridPlateRadialExpansionCoeffPerTemp",
            units=f"{units.REACTIVITY}/{units.DEGK}",
            description="Grid Plate Radial Expansion Coefficient",
        )

    with pDefs.createBuilder(
        location=ParamLocation.AVERAGE, categories=["equilibrium"]
    ) as pb:

        pb.defParam(
            "cyclics",
            units=units.UNITLESS,
            description=(
                "The integer number of cyclic mode equilibrium-cycle "
                "iterations that have occurred so far"
            ),
            default=0,
        )

    with pDefs.createBuilder(
        location=ParamLocation.AVERAGE, categories=["equilibrium"]
    ) as pb:

        pb.defParam(
            "ConvRatioCore",
            units=units.UNITLESS,
            description="Conversion ratio of the core",
        )

        pb.defParam(
            "absPerFisCore",
            units=units.UNITLESS,
            description="absorptions per fission in core",
        )

        pb.defParam(
            "axialExpansionPercent",
            units=units.PERCENT,
            description="Percent of axial growth of fuel blocks",
            default=0.0,
        )

        pb.defParam(
            "coupledIteration",
            units=units.UNITLESS,
            description="Pre-defined number of tightly coupled iterations.",
            default=0,
        )

        pb.defParam(
            "fisFrac",
            units=units.UNITLESS,
            description="Percent of fissions in fertile nuclides",
        )

        pb.defParam(
            "fisRateCore",
            units=units.UNITLESS,
            description="peak/average fission rate in core",
        )

    return pDefs


def makeParametersReadOnly(r):
    """Convert all the parameters in a Reactor to read-only.

    This method is pretty simple. It goes through all the children of a Reactor object,
    recursively, and converts the parameters to read-only mode. This will affect the Core, but also
    any Spent Fuel Pools or other high-level reactor systems.

    Parameters
    ----------
    r : Reactor
        Full reactor object, to be modified.

    Notes
    -----
    Once you make one Reactor read-only, you cannot make it writeable again.
    """
    r.p.readOnly = True
    for child in r.iterChildren(deep=True):
        child.p.readOnly = True
