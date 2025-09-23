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

"""Code that needs to be executed before most ARMI components are safe to import."""

from armi.nucDirectory import nuclideBases  # noqa: E402

# Nuclide bases get built explicitly here to have better determinism about when they get instantiated. The burn chain is
# not applied at this point, but only after input is read. Nuclides need to be built super early because some
# import-time code needs them to function. Namely, Block parameter collection uses them to create number density params.
nuclideBases.factory()
