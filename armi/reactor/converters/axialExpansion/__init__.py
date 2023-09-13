# Copyright 2023 TerraPower, LLC
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
"""Particles! Expand axially!."""

from armi.materials import material
from armi.reactor.flags import Flags


def getSolidComponents(b):
    """
    Return list of components in the block that have solid material.

    Notes
    -----
    Axial expansion only needs to be applied to solid materials. We should not update
    number densities on fluid materials to account for changes in block height.
    """
    return [c for c in b if not isinstance(c.material, material.Fluid)]


def _getDefaultReferenceAssem(assems):
    """Return a default reference assembly."""
    # if assemblies are defined in blueprints, handle meshing
    # assume finest mesh is reference
    assemsByNumBlocks = sorted(
        assems,
        key=lambda a: len(a),
        reverse=True,
    )
    return assemsByNumBlocks[0] if assemsByNumBlocks else None


def makeAssemsAbleToSnapToUniformMesh(
    assems, nonUniformAssemFlags, referenceAssembly=None
):
    """Make this set of assemblies aware of the reference mesh so they can stay uniform as they axially expand."""
    if not referenceAssembly:
        referenceAssembly = _getDefaultReferenceAssem(assems)
    # make the snap lists so assems know how to expand
    nonUniformAssems = [Flags.fromStringIgnoreErrors(t) for t in nonUniformAssemFlags]
    for a in assems:
        if any(a.hasFlags(f) for f in nonUniformAssems):
            continue
        a.makeAxialSnapList(referenceAssembly)
