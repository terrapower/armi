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
Globally accessible exception definitions for better granularity on exception behavior and exception handling behavior
"""
from armi.localization import strings
from inspect import stack, getframeinfo


class RangeError(Exception):
    r"""Exception for when a parameter is out of an acceptable range"""

    def __init__(self, parameter, value, lower=None, upper=None):
        self.parameter = parameter
        self.value = value
        self.lower = lower
        self.upper = upper
        message = strings.RangeError_Expected_parameter_ToBe.format(parameter)

        if lower and upper:
            message += strings.RangeError_Between_lower_And_upper.format(lower, upper)
        elif upper:
            message += strings.RangeError_LessThan_upper.format(upper)
        elif lower:
            message += strings.RangeError_GreaterThan_lower.format(lower)
        else:
            raise ValueError(strings.RangeError_UnderspecifiedRangeError)

        message += strings.RangeError_ButTheValueWas_value.format(value)
        Exception.__init__(self, message)


class SymmetryError(Exception):
    """Exception to raise when a symmetry condition is violated."""


class InvalidSelectionError(Exception):
    """Exception raised when an invalid value was provided when there is a finite set of valid options."""

    def __init__(self, optionsName, selection, optionValues):
        self.optionsName = optionsName
        self.selection = selection
        self.optionValues = optionValues
        Exception.__init__(
            self,
            "Value of {} is {}, but should be one of: {}".format(
                self.optionsName, self.selection, ", ".join(self.optionValues)
            ),
        )


class CcccRecordError(Exception):
    """An error which occurs while reading or writing a CCCC record."""

    pass


class OverConfiguredError(RuntimeError):
    """An error that occurs when ARMI is configure()'d more than once."""

    def __init__(self, context):
        RuntimeError.__init__(
            self,
            "Multiple calls to armi.configure() are not allowed. "
            "Previous call from:\n{}".format(context),
        )


class ReactivityCoefficientNonExistentComponentsInRepresentativeBlock(Exception):
    """
    An error that can occur when getting Doppler or Temperature reactivity coefficients within the core.

    Notes
    -----
    This can occur when the requested component modification is applied to the core, but the representative blocks
    within the core do not represented the requested component. For example, if all the representative blocks
    are generated from fuel and a request to generate the Doppler coefficient for the grid plate is made it is likely
    that the fuel regions of the core do not have a grid plate component. Since no grid plate is represented by the
    cross section groupings, the effect on the cross sections cannot be evaluated.
    """

    pass


class XSLibraryError(Exception):
    """An error which occurs while merging XSLibrary objects."""

    pass


class XSGenerationError(Exception):
    """An error which occurs while merging XSLibrary objects."""

    pass


class IsotxsError(Exception):
    """An error which occurs while reading, writing, or combining ISOTXS files."""

    pass


class GamisoError(Exception):
    """An error which occurs while reading, writing, or combining GAMISO files."""

    pass


class CompxsError(Exception):
    """An error which occures while reading, writing, or combining COMPXS files."""

    pass


class PmatrxError(Exception):
    """An error which occurs while reading, writing, or combining PMATRX files."""

    pass


class RMFluxPartisnError(Exception):
    """An error which occurs while reading, writing, or combining RMFLUX files."""

    pass


class RZMFlxPartisnError(Exception):
    """An error which occurs while reading, writing, or combining RZMFLX files."""

    pass


class StateError(Exception):
    """An error that occurs due to an action or method being invalid due to the state of the object."""

    pass


class DeprecationError(Exception):
    """An error that occurs after a specific date"""

    pass


class ConsistencyError(ValueError):
    """Error raised when inputs are not consistent."""

    pass


class NegativeComponentArea(Exception):
    pass


class NegativeComponentVolume(Exception):
    pass


class RunLogPromptCancel(Exception):
    """An error that occurs when the user submits a cancel on a runLog prompt which allows for cancellation"""

    pass


class RunLogPromptUnresolvable(Exception):
    """
    An error that occurs when the current mode enum in armi.__init__ suggests the user cannot be communicated with from
    the current process.
    """

    pass


# ---------------------------------------------------
def raiseImportError(msg):
    raise ImportError(msg)


class InputError(Exception):
    """AN error found in an ARMI input file."""

    def __init__(self, msg):
        self.msg = msg
        self.caller = getframeinfo(stack()[1][0])

    def __str__(self):
        # Check if the call site is sensible enough to warrant printing. For now making the wild assumption that cython
        # will wrap the fake stack filename in <>
        callSiteIsFake = self.caller.filename.startswith(
            "<"
        ) and self.caller.filename.endswith(">")
        if callSiteIsFake:
            return self.msg
        else:
            return (
                self.caller.filename + ":" + str(self.caller.lineno) + " - " + self.msg
            )

    @property
    def isFixable(self):
        raise NotImplementedError

    def fix(self, case):
        raise NotImplementedError


# ---------------------------------------------------


class InputInspectionRequired(Exception):
    """An error that occurs when some inputs have brought up concerns and the user is running in a non-interactive mode to respond"""

    pass


class InputInspectionDiscontinued(Exception):
    """An error that occurs when something interrupts the process of input inspection with the intent of not proceeding"""

    pass


class InputInspectionMalformed(Exception):
    """An error that occurs when the process of input inspection did not resolve all issues in the first pass"""

    pass


# ---------------------------------------------------


class SettingException(Exception):
    """Standardize behavior of setting-family errors"""

    def __init__(self, msg):
        Exception.__init__(self, msg)


class InvalidSettingsStopProcess(SettingException):
    """Exception raised when setting file contains invalid settings and user aborts or process is uninteractive"""

    def __init__(self, reader):
        msg = "Input settings file {}".format(reader.inputPath)
        if reader.liveVersion != reader.inputVersion:
            msg += (
                '\n\twas made with version "{0}" which differs from the current version "{1}." '
                'Either create the input file with the "{1}", or switch to a development version of ARMI.'
                "".format(reader.inputVersion, reader.liveVersion)
            )
        if reader.invalidSettings:
            msg += (
                "\n\tcontains the following {} invalid settings:\n\t\t"
                "{}"
                "".format(
                    len(reader.invalidSettings), "\n\t\t".join(reader.invalidSettings)
                )
            )
        SettingException.__init__(self, msg)


class NonexistentSetting(SettingException):
    """Exception raised when a non existent setting is asked for"""

    def __init__(self, setting):
        SettingException.__init__(
            self, "Attempted to locate non-existent setting {}.".format(setting)
        )


class SettingNameCollision(SettingException):
    """Exception raise when a setting has already been given the same case-insensitive name"""


class NonexistentSettingsFileError(SettingException):
    """Settings file does not exist"""

    def __init__(self, path):
        SettingException.__init__(
            self, "Attempted to load settings file, cannot locate file: {}".format(path)
        )


class InvalidSettingsFileError(SettingException):
    """Not a valid xml or settings file"""

    def __init__(self, path, customMsgEnd=""):
        msg = "Attempted to load an invalid settings file from: {}. ".format(path)
        msg += customMsgEnd

        SettingException.__init__(self, msg)


class InvalidSettingsFileContentsError(SettingException):
    """Some setting doesn't obey the system"""

    def __init__(self, path, lastSetting=None, exact_message=None):
        msg = "Settings file {} read in as well formed XML, but disobeys settings system.".format(
            path
        )
        if lastSetting:
            msg += " The last setting attempted was `{0}`".format(lastSetting)
        if exact_message:
            msg += "\n{}".format(exact_message)

        SettingException.__init__(self, msg)


# ---------------------------------------------------


class NoDataModelInDatabaseException(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)


class ComponentLinkingFailure(Exception):
    pass


class SynchronizationError(Exception):
    pass
