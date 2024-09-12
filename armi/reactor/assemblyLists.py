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
Module containing :py:class:`AssemblyList` and related classes.

Assembly Lists are core-like objects that store collections of Assemblies. They were
originally developed to serve as things like spent-fuel pools and the like, where
spatial location of Assemblies need not be quite as precise.

Presently, the :py:class:`armi.reactor.reactors.Core` constructs a spent fuel pool
`self.sfp`. We are in the process of removing these as instance attributes of the
``Core``, and moving them into sibling systems on the root
:py:class:`armi.reactor.reactors.Reactor` object.
"""
import itertools

from armi.reactor import grids
from armi.reactor.excoreStructure import ExcoreStructure


class AssemblyList(ExcoreStructure):
    """
    A quasi-arbitrary collection of Assemblies.

    The AssemblyList is similar to a Core, in that it is designed to store Assembly objects. Unlike
    the Core, they have far fewer convenience functions, and permit looser control over where
    assemblies actually live.
    """

    def __init__(self, name, parent=None):
        ExcoreStructure.__init__(self, name)
        self.parent = parent
        self._nMajor = 10  # TODO: JOHN Bad name and default

        # TODO: JOHN: Where does this get reset?
        # make a Cartesian assembly rack by default. Anything that really cares about the layout
        # should specify one manually or in Blueprints
        self.spatialGrid = grids.CartesianGrid.fromRectangle(50.0, 50.0)

    def add(self, assem, loc=None):
        """
        Add an Assembly to the list.

        Parameters
        ----------
        assem : Assembly
            The Assembly to add to the list
        loc : LocationBase, optional
            If provided, the assembly is inserted at that location. If it is not provided, the
            locator on the Assembly object will be used. If the Assembly's locator belongs to
            ``self.spatialGrid``, the Assembly's existing locator will not be used. This is unlike
            the Core, which would try to use the same indices, but move the locator to the Core's
            grid. With a locator, the associated ``AutoFiller`` will be used.
        """
        if loc is not None and loc.grid is not self.spatialGrid:
            raise ValueError(
                f"An assembly cannot be added to {self} using a spatial locator from another grid."
            )

        locProvided = loc is not None or (
            assem.spatialLocator is not None
            and assem.spatialLocator.grid is self.spatialGrid
        )

        if locProvided:
            loc = loc or assem.spatialLocator
        else:
            loc = self.getNextLocation()

        super().add(assem, loc)

    def getAssembly(self, name):
        """Get a specific Assembly by name."""
        for a in self.getChildren():
            if a.getName() == name:
                return a

        return None

    def getNextLocation(self):
        """TODO: JOHN.

        Control automatic insertion of Assemblies when a specific Composite location isn't requested.

        This fills the :py:class:`armi.reactor.grids.Grid` of the associated
        :py:class:`AssemblyList` by filling subsequent rows with ``nMajor`` assemblies before moving to
        the next row.

        assumes rectangular grid
        """
        filledLocations = {a.spatialLocator for a in self}
        grid = self.spatialGrid

        for idx in itertools.count():
            j = idx // self._nMajor  # TODO: JOHN - bad name - "_numColums"
            i = idx % self._nMajor
            loc = grid[i, j, 0]
            if loc not in filledLocations:
                return loc

        return None


class SpentFuelPool(AssemblyList):
    """A place to put assemblies when they've been discharged. Can tell you inventory stats, etc."""

    def add(self, assem, loc=None):
        """
        Add an Assembly to the list.

        Parameters
        ----------
        assem : Assembly
            The Assembly to add to the list
        loc : LocationBase, optional
            If provided, the assembly is inserted at that location. If it is not provided, the
            locator on the Assembly object will be used. If the Assembly's locator belongs to
            ``self.spatialGrid``, the Assembly's existing locator will not be used. This is unlike
            the Core, which would try to use the same indices, but move the locator to the Core's
            grid. With a locator, the associated ``AutoFiller`` will be used.
        """
        # If the assembly added has a negative ID, that is a placeholder, fix it.
        if assem.p.assemNum < 0:
            # update the assembly count in the Reactor
            newNum = self.r.incrementAssemNum()
            assem.renumber(newNum)

        super().add(assem, loc)

    def normalizeNames(self, startIndex=0):
        """
        Renumber and rename all the Assemblies and Blocks.

        Parameters
        ----------
        startIndex : int, optional
            The default is to start counting at zero. But if you are renumbering assemblies across
            the entire Reactor, you may want to start at a different number.

        Returns
        -------
        int
            The new max Assembly number.
        """
        ind = startIndex
        for a in self.getChildren():
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

        return int
