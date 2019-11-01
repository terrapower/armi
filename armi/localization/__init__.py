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
The localization package is a rarely-used minor attempt to provide language localization.

.. warning:: The ARMI project is likely going to phase this out. If the project decides
    to introduce better support for localization, a more standard approach should be used (e.g.
    one based on https://docs.python.org/3/library/gettext.html). Thus, it is recommended
    to not extend usage of this module at this time.
"""
import armi
import armi.runLog as runLog

_message_counts = {}


def count_calls(func):
    r"""Do not use this decorator directly.

    Decorator to count the number of calls to a method
    """
    _message_counts[func] = 0

    def decorated(*args, **kwargs):
        r"""decorated method"""
        _message_counts[func] += 1
        return func(*args, **kwargs)

    return decorated


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
        if armi.MPI_RANK == 0:
            func(*args, **kwargs)

    return decorated


def _message_once(func):
    r"""Do not use this decorator directly.

    Decorator to have message only appear once.
    """
    func2 = count_calls(func)

    def decorated(*args, **kwargs):
        r"""decorated method"""
        if _message_counts[func] == 0:
            func2(*args, **kwargs)

    return decorated


def info_once(func):
    r"""Decorator to have message only appear once."""
    return _message_once(info(func))


def warn_once(func):
    r"""Decorates a method to produce a single warning message."""
    return _message_once(warn(func))


def warn_when_root(func):
    r"""Decorates a method to produce a warning message only on the root node."""
    return _message_when_root(warn(func))


def warn_once_when_root(func):
    r"""Decorates a method to produce a single warning message from the root node."""
    return _message_once(warn_when_root(func))
