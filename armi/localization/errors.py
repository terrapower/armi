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
Specialized and specific error messages.

Note that some of these are plugin-specific and will be removed.
"""

from armi.localization.exceptions import RangeError, InvalidSelectionError


def physics_MissingExecutable(root, name, version):
    return IOError(
        "Could not find executable for `{}' version `{}' in the root `{}'".format(
            name, version if version else "*", root
        )
    )


def mc2Interface_MissingInputFile(path):
    return IOError("Could not find input file `{}'".format(path))


def Mc2Writer_NegativeTemperature(value):
    return RangeError("Temperature in the block [K]", value, lower=0.0)


def Mc2Writer_CannotCreateMc2InputFor_n_Groups(nn):
    return Exception("Cannot generate MC**2 inputs for {} groups.".format(nn))


def nuclides_TooManyOrTooFew_number_MatchesForNuclide_name(number, name):
    return Exception("Too many or too few ({}) matches for {}" "".format(number, name))


def general_single_TooManyOrTooFewMatchesFor(matchedObjects):
    return Exception(
        "Expected single match, but got {} matches:\n  {}".format(
            len(matchedObjects), "\n  ".join(str(mo) for mo in matchedObjects)
        )
    )


def Nuclide_NameAlreadExists(name, nuclide):
    return Exception("Nuclide name {} is already in use {}".format(name, nuclide))


def Transmutation_InvalidReactionTypeUse(rxnType, possibleTypes):
    return InvalidSelectionError("transmutation reaction", rxnType, possibleTypes)


def DecayMode_InvalidDecayModeUse(mode, decTypes):
    return InvalidSelectionError("decay mode", mode, decTypes)


def serpentWriter_InvalidTemperature_OutOfBounds(
    materialName, currentTemperature, lowTemp, highTemp
):
    return RangeError(
        "material `{}` temperature [K]".format(materialName),
        currentTemperature,
        lower=lowTemp,
        upper=highTemp,
    )


def serpentWriter_CannotWriteNuclide_NeedOptions(
    nuclide, block, givenTemp, givenLibrarySuffix
):
    return Exception(
        "Unable to write nuclide {} of block {} without either temperature "
        "or the library identifier. Given temp: {} and suffix: {}".format(
            nuclide.getSerpentId(), block, givenTemp, givenLibrarySuffix
        )
    )


def serpentInspector_InputError(errorMessageOnLine, specificMessage, suggestion=""):
    return Exception(
        "{}: {}. {}".format(errorMessageOnLine, specificMessage, suggestion)
    )


def serpentInspector_NoHomogenizedUniverseFound(resultsFile):
    return Exception(
        "No homogenized universe was found in results file {}".format(resultsFile)
    )


def serpentReader_NoB1Values(resultsFile, inputFile):
    return Exception(
        "NoB1XS: Cannot get critical spectrum cross sections from results file {}. "
        "\nMake sure {} has `set fum` option active".format(resultsFile, inputFile)
    )


def serpentWriter_MicroGroupShorterThanBroadGroup(writer, lenMicro, lenBroad):
    return Exception(
        "BadMicroGroup: Microgroup structure for SERPENT xsID {} must be greater than {} elements. "
        "Currently is {}".format(writer.xsId, lenBroad, lenMicro)
    )
