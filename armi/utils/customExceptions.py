# Copyright 2021 TerraPower, LLC
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
Globally accessible exception definitions for better granularity on exception behavior and exception handling behavior
"""
from armi import runLog
from inspect import stack, getframeinfo


def info(func):
    r"""Decorator to write to current log, using the info method"""

    def decorated(*args, **kwargs):
        r"""decorated method"""
        runLog.info(func(*args, **kwargs))

    return decorated


def important(func):
    r"""Decorator to write to current log, using the inportant method"""

    def decorated(*args, **kwargs):
        r"""decorated method"""
        runLog.important(func(*args, **kwargs))

    return decorated


def warn(func):
    r"""Decorates a method to produce a repeatable warning message."""

    def decorated(*args, **kwargs):
        r"""decorated method"""
        runLog.warning(func(*args, **kwargs))

    return decorated


def _message_when_root(func):
    r"""Do not use this decorator."""

    def decorated(*args, **kwargs):
        from armi import MPI_RANK

        if MPI_RANK == 0:
            func(*args, **kwargs)

    return decorated


def warn_when_root(func):
    r"""Decorates a method to produce a warning message only on the root node."""
    return _message_when_root(warn(func))


# ---------------------------------------------------


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


class InvalidSettingsFileError(SettingException):
    """Not a valid settings file"""

    def __init__(self, path, customMsgEnd=""):
        msg = "Attempted to load an invalid settings file from: {}. ".format(path)
        msg += customMsgEnd

        SettingException.__init__(self, msg)


class NonexistentSettingsFileError(SettingException):
    """Settings file does not exist"""

    def __init__(self, path):
        SettingException.__init__(
            self, "Attempted to load settings file, cannot locate file: {}".format(path)
        )
