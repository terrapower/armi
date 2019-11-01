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
Contains constant strings

If necessary, in the future, it will also contain translations.

DO NOT use imports or calculated strings... everything in this file
should be constant.

Notes
-----
This may be a good place to use https://docs.python.org/3/library/gettext.html 
"""
# username is a "constant" for a user.
from getpass import getuser

Operator_CaseTitle = "Case Title:"
Operator_TypeOfRun = "Run Type:"
Operator_NumProcessors = "Number of Processors:"
Operator_WorkingDirectory = "Working Directory:"
Operator_CurrentUser = "Current User:"
Operator_PythonInterperter = "Python Interpreter:"
Operator_ArmiCodebase = "ARMI Location:"
Operator_MasterMachine = "Master Machine:"
Operator_Date = "Date and Time:"
Operator_CaseDescription = "Case Description:"

RangeError_Expected_parameter_ToBe = "Expected {} to be "
RangeError_Between_lower_And_upper = "between {} and {}, "
RangeError_LessThan_upper = "less than {}, "
RangeError_GreaterThan_lower = "greater than {}, "
RangeError_UnderspecifiedRangeError = "Underspecified RangeError"
RangeError_ButTheValueWas_value = "but the value was {}."

SCIENTIFIC_PATTERN = r"[+-]?\d*\.\d+[eEdD][+-]\d+"
"""
Matches:
* code:` 1.23e10`
* code:`-1.23Ee10`
* code:`+1.23d10`
* code:`  .23D10`
* code:` 1.23e-10`
* code:` 1.23e+1`
"""

FLOATING_PATTERN = r"[+-]?\d+\.*\d*"
"""
Matches 1, 100, 1.0, -1.2, +12.234
"""

DECIMAL_PATTERN = r"[+-]?\d*\.\d+"
"""matches .1, 1.213423, -23.2342, +.023
"""
