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
Contains constant strings used in some warnings.

Notes
-----
This may be a good place to use https://docs.python.org/3/library/gettext.html 
"""

from armi.localization import warn_when_root, warn, warn_once


@warn_when_root
def Mc2Writer_NoFuelTemperatureSpecifiedInSettingsUsing_defaults_inK(defaults):
    return (
        "No fuel/struct/coolant temperatures specified in settings. "
        "Using Defaults: {} K".format(",".join(defaults))
    )


@warn_when_root
def LatticePhysicsWriter_Nuclide_name_FoundMultipleTimes(nuclideName):
    return "Nuclide `{}' was found multiple times.".format(nuclideName)


@warn
def Operator_executionScriptDiffersFromArmiLocation(actualLocation):
    return (
        "True executing script is in {0}. "
        "This differs from armiLocation setting".format(actualLocation)
    )


@warn
def nucDir_BadNuclideName(name):
    return "Bad nuclide name: {}".format(name)


@warn_when_root
def nuclide_NuclideLabelDoesNotMatchNuclideLabel(nuclide, label, xsID):
    return "The label {} (xsID:{}) for nuclide {}, does not match the nucDirectory label.".format(
        label, xsID, nuclide
    )


@warn
def physics_NoExecutableFound(codeName, expectedPath):
    return "Could not find executable with name `{}' at `{}'".format(
        codeName, expectedPath
    )


@warn
def physics_NoExecutabelNamed_name_Found(codeName, version):
    return "Could not find an executable with name `{}' (version {})".format(
        codeName, version
    )


@warn_once
def distortionInterface_HexErrorPotentiallyGreaterThanTenPercent(t, D):
    return (
        "Calculated dilation values for a hex duct with {}mm inner flat-to-flat and "
        "{}mm wall thickness may deviate from FEA by more than 10% at 600 DPA.".format(
            D, t
        )
    )


@warn_once
def distortionInterface_HexErrorPotentiallyGreaterThanFivePercent(t, D):
    return (
        "Calculated dilation values for a hex duct with {}mm inner flat-to-flat and "
        "{}mm wall thickness may deviate from FEA by more than 5% at 600 DPA.".format(
            D, t
        )
    )


@warn
def ccl_failedImport():
    return (
        "Failed to import `ccl`, will be unable to submit jobs or monitor job progress"
    )


@warn
def rxCoeffs_noAssembliesToModifyForSasCoefficient(coefficientName, zoneName):
    return 'No assemblies to modify for SAS "{}" coefficient of zone "{}". Check zone definitions.'.format(
        coefficientName, zoneName
    )


@warn_once
def serpentWriter_DumpedNuclides(dumpedDensities, writer):
    return (
        "{} nuclides were dropped from {} SERPENT writer.\nDensity of all dropped nuclides: {} "
        "[atoms/barn/cm]".format(
            len(dumpedDensities), writer.block, sum(dumpedDensities)
        )
    )
