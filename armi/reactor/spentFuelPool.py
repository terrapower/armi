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
"""A nuclear reactor frequently has storage pools (or 'ponds') for spent fuel.

This file implements a simple/default representation of such as an ARMI "system". ARMI systems, like the core are grids
filled with ArmiObjects. This module also includes some helper tools to aid transferring spent fuel assemblies from the
core to the SFP.
"""

import itertools

from armi.reactor.excoreStructure import ExcoreStructure


class SpentFuelPool(ExcoreStructure):
    """The Spent Fuel Pool (SFP) is a place to store discharged assemblies.

    This class is a core-like system object, so it has a spatial grid that Assemblies can fit in.

    .. impl:: The user-specified spent fuel pool.
        :id: I_ARMI_SFP
        :implements: R_ARMI_SFP

        The SpentFuelPool is a composite structure meant to represent storage ponds for used fuel
        assemblies. As a data structure, it is little more than a container for ``Assembly``
        objects. It should be able to easily support adding or removing ``Assembly`` objects. And at
        every time node the current state of the SFP will be written to the database.
    """

    def __init__(self, name, parent=None):
        ExcoreStructure.__init__(self, name)
        self.parent = parent
        self.spatialGrid = None
        self.numColumns = None

    def add(self, assem, loc=None):
        """
        Add an Assembly to the list.

        Parameters
        ----------
        assem : Assembly
            The Assembly to add to the spent fuel pool
        loc : LocationBase, optional
            If provided, the assembly is inserted at this location.
            If it is not provided, the locator on the Assembly object will be used.
            If the Assembly's loc belongs to ``self.spatialGrid``, it will not be used.
        """
        if loc is not None and loc.grid is not self.spatialGrid:
            raise ValueError(f"An assembly cannot be added to {self} using a spatial locator from another grid.")

        if self.numColumns is None:
            self._updateNumberOfColumns()

        # If the assembly added has a negative ID, that is a placeholder, fix it.
        if assem.p.assemNum < 0:
            newNum = self.r.incrementAssemNum()
            assem.renumber(newNum)

        # Make sure the location of the new assembly is valid
        locProvided = loc is not None or (
            assem.spatialLocator is not None and assem.spatialLocator.grid is self.spatialGrid
        )
        if locProvided:
            loc = loc or assem.spatialLocator
        else:
            loc = self._getNextLocation()

        # orient the blocks to match this grid
        assem.orientBlocks(parentSpatialGrid=self.spatialGrid)

        super().add(assem, loc)

    def getAssembly(self, name):
        """Get a specific assembly by name."""
        for a in self:
            if a.getName() == name:
                return a

        return None

    def _updateNumberOfColumns(self):
        """Determine the number of columns in the spatial grid."""
        locs = self.spatialGrid.items()
        self.numColumns = len(set([ll[0][0] for ll in locs]))

    def _getNextLocation(self):
        """Helper method to allow each discharged assembly to be easily dropped into the SFP.

        The logic here is that we assume that the SFP is a rectangular-ish grid, with a set number of columns per row.
        So when you add an Assembly here, if you don't provide a location, the grid is filled in a col/row order with
        whatever grid cell is found open first.
        """
        filledLocations = {a.spatialLocator for a in self}
        grid = self.spatialGrid

        for idx in itertools.count():
            j = idx // self.numColumns
            i = idx % self.numColumns
            loc = grid[i, j, 0]
            if loc not in filledLocations:
                return loc

        return None

    def normalizeNames(self, startIndex=0):
        """
        Renumber and rename all the Assemblies and Blocks.

        Parameters
        ----------
        startIndex : int, optional
            The default is to start counting at zero. But if you are renumbering assemblies across the entire Reactor,
            you may want to start at a different number.

        Returns
        -------
        int
            The new max Assembly number.
        """
        ind = startIndex
        for a in self:
            oldName = a.getName()
            newName = a.makeNameFromAssemNum(ind)
            if oldName == newName:
                ind += 1
                continue

            a.p.assemNum = ind
            a.setName(newName)

            for b in a:
                axialIndex = int(b.name.split("-")[-1])
                b.name = b.makeName(ind, axialIndex)

            ind += 1

        return ind
