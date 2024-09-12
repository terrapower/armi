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

        # TODO: JOHN This is a nonsense placeholder.
        self.spatialGrid = grids.CartesianGrid.fromRectangle(50.0, 50.0)

    @property
    def r(self):
        from armi.reactor import reactors

        return self.getAncestor(fn=lambda x: isinstance(x, reactors.Reactor))

    def __repr__(self):
        return "<{}: {} id:{}>".format(self.__class__.__name__, self.name, id(self))
