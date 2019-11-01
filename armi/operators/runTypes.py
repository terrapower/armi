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
Constants defining the different supported run types.

These were moved here to better structure the dependencies within this
package. Dependencies should be organized in a tree-like structure, with
``__init__.py`` living at the top. These will likely need to be extended by plugins in
the near future.
"""


class RunTypes:
    """All available values of the ``runType`` setting that determine which Operator to use."""

    STANDARD = "Standard"
    SNAPSHOTS = "Snapshots"
    EQUILIBRIUM = "Equilibrium"
