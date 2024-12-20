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

"""This file contains tools for common tasks in parsing in python strings into non-string values."""

import ast
import copy

from dateutil import parser


def tryLiteralEval(source):
    try:
        source = ast.literal_eval(source)
    except (ValueError, SyntaxError):
        pass

    return source


# the following dict helps avoid the need for an eval() statement
# Is there no better way to go 'bool' -> bool !?
_str_types = {
    tp.__name__: tp
    for tp in (type(None), bool, int, complex, float, str, bytes, list, tuple, dict)
}
_type_strs = {v: k for k, v in _str_types.items()}


# python's matching truth evaluations of Nones in different primitive types
# str's and unicodes omitted because parseValue denies their use.
_none_types = {
    type(None): None,
    bool: False,
    int: 0,
    complex: 0j,
    float: 0.0,
    list: [],
    tuple: (),
    dict: {},
}


def _numericSpecialBehavior(source, rt):
    try:
        return rt(source), True  # convert, report success
    except (ValueError, TypeError):
        return source, False  # fail, report failure


def parseValue(source, requestedType, allowNone=False, matchingNonetype=True):
    """Tries parse a python value, expecting input to be the right type or a string."""
    # misuse prevention
    if requestedType is str:
        raise TypeError(
            "Unreliable and unnecessary to use parseValue for strs and unicodes. "
            "Given parameters are {}, {}, {}.".format(source, requestedType, allowNone)
        )

    # evaluation and special evaluation for numbers
    evaluated_source, skip_instance_check = tryLiteralEval(source), False
    if requestedType in [int, float, complex]:
        evaluated_source, skip_instance_check = _numericSpecialBehavior(
            evaluated_source, requestedType
        )

    # none logic
    if allowNone and not evaluated_source:
        if matchingNonetype:
            return copy.deepcopy(_none_types[requestedType])
        else:
            return evaluated_source

    # assert everything went well
    if not skip_instance_check and not isinstance(evaluated_source, requestedType):
        msg = "Could not parse {} from source {}."
        if allowNone:
            msg += " Nor could None be parsed from source."
        raise ValueError(msg.format(requestedType, evaluated_source))

    return evaluated_source


# -----------------------------------


def datetimeFromStr(string):
    """Converts an arbitrary string to a datetime object."""
    return parser.parse(string)
