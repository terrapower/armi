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
The package matProps is a material library capable of computing material property quantities.

The package uses resource files (YAML) to define Material objects with Property Function attributes.
This package does not include any material data files. The user may create their own data files to
use with matProps by passing a path in mat_props.load_all(path). ARMI does come with a set of
material data files at armi.testing.materials that are useful examples of how these YAML files are
structured.
"""
