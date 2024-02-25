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

"""Homogenized mixture material."""

from armi import materials


class _Mixture(materials.Material):
    """
    Homogenized mixture of materials.

    :meta public:

    .. warning:: This class is meant to be used for homogenized block models for neutronics and other
       physics solvers.

    Notes
    -----
    This material class can be used to represent a homognized mixture of materials within a block.
    This would be done for performance reasons. It allows ARMI to avoid copying and carrying around
    the detailed, explicit representation of components within a block to be used in a physics solver
    when that solver only needs to know the homogenized number density within a block.

    See Also
    --------
    armi.reactor.blocks.HexBlock.createHomogenizedCopy
    """
