# Copyright 2024 TerraPower, LLC
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
"""TODO: JOHN."""

from armi.reactor import grids
from armi.reactor.composites import Composite


class ExcoreStructure(Composite):
    """TODO: JOHN.

    An ex-core structure is expected to:

    - be a child of the Reactor,
    - have a grid associated with it,
    - contain a hierarchical set of ArmiObjects.
    """

    def __init__(self, name, parent=None):
        Composite.__init__(self, name)
        self.parent = parent

        # TODO: JOHN UGH
        self.spatialGrid = grids.CartesianGrid.fromRectangle(50.0, 50.0)

    def __repr__(self):
        return "<{}: {} id:{}>".format(self.__class__.__name__, self.name, id(self))

    @property
    def r(self):
        return self.getAncestor(fn=lambda x: x.__class__.__name__ == "Reactor")

    def add(self, obj, loc):
        """TODO: JOHN: Add one new child."""
        if loc.grid is not self.spatialGrid:
            raise ValueError(
                f"An Composite cannot be added to {self} using a spatial locator from another grid."
            )

        # If an assembly is added and it has a negative ID, that is a placeholder, fix it.
        if "assemNum" in obj.p and obj.p.assemNum < 0:
            # update the assembly count in the Reactor
            newNum = self.r.incrementAssemNum()
            obj.renumber(newNum)

        obj.spatialLocator = loc
        super().add(obj)
