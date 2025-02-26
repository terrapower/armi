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


class ParameterDefinitionError(Exception):
    """Exception raised due to a programming error.

    Programming errors include:

    * Attempting to create two parameters with the same name.
    * Attempting to create a parameter outside of a :py:class:`ParameterFactory`
      ``with`` statement.

    """

    def __init__(self, message):
        Exception.__init__(
            self,
            "This is a programming error, and needs to be addressed by the developer encountering it:\n" + message,
        )


class ParameterError(Exception):
    """Exception raised due to a usage error.

    Usage errors include:

    * Attempting to get the value of a parameter that has not been defined a value, and
      has no default.
    * Attempting to set the value of a parameter that cannot be set through
      ``setParam``.

    """


class UnknownParameterError(ParameterError):
    """Exception raised due to a usage error.

    Usage errors include:

    * Attempting to set the value of a parameter that has no definition and no rename

    """
