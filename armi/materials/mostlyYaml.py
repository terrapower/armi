# Copyright 2026 TerraPower, LLC
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
A collection of materials that are mostly purely defined in matProps YAML files.

This file exists to wrap pure matProps YAML files so they become full-fledged versions of ``armi.materials.Material``.
The wrappers below are designed so new matProps material objects can be created on the fly, as needed.
"""

import os

# handle pathing to materials files
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_RESOURCES_DIR = os.path.join(_THIS_DIR, "..", "resources", "materials")
