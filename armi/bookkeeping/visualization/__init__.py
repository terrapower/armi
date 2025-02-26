# Copyright 2020 TerraPower, LLC
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
The Visualization package contains functionality and entry points for producing files
amenable to visualization of ARMI run results.

This could theoretically support all sorts of visualization file formats, but for now,
only VTK files are supported. VTK was selected because it has wide support from vis
tools, while being a simple-enough format that quality pure-Python libraries exist to
produce them. Other formats (e.g., SILO) tend to require more system-dependent binary
dependencies, so optional support for them may be added later.
"""

from armi import plugins  # noqa: F401
from armi.bookkeeping.visualization.entryPoint import VisFileEntryPoint  # noqa: F401
