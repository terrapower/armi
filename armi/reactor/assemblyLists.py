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

r"""
Module containing :py:class:`AssemblyList` and related classes.

Assembly Lists are core-like objects that store collections of Assemblies. They were
originally developed to serve as things like spent-fuel pools and the like, where
spatial location of Assemblies need not be quite as precise.

Presently, the :py:class:`armi.reactor.reactors.Core` constructs a pair of these as
`self.sfp` and `self.cfp` (charged-fuel pool). We are in the process of removing these
as instance attributes of the ``Core``, and moving them into sibling systems on the root
:py:class:`armi.reactor.reactors.Reactor` object.
"""
import abc
import itertools

from armi import runLog
from armi.utils import units
from armi.reactor import grids
from armi.reactor import composites
from armi.reactor.flags import Flags


class AutoFiller(abc.ABC):
    """
    Class for governing automatic insertion of Assemblies when a specific Composite
    location isn't requested.

    This is kept separate from the ``AssemblyList`` class itself to promote composition
    over inheritance; reasonable implementations of auto-fill strategies will have their
    own state, which subclasses of ``AssemblyList`` should not have to manage.
    """

    def getNextLocation(self, a) -> grids.LocationBase:
        """
        Return the next automatic location.
        """

    def assemblyAdded(self, a):
        """
        Register that an assembly has been added.

        This allows an ``AutoFiller`` to be notified that an assembly has been added
        manually.
        """


class RowMajorAutoFiller(AutoFiller):
    """
    :py:class:`AutoFiller` implementation for filling a "rectangular" grid of
    Assemblies.

    This fills the :py:class:`armi.reactor.grids.Grid` of the associated
    :py:class:`AssemblyList` by filling subsequent rows with ``nMajor`` assemblies
    before moving to the next row.
    """

    def __init__(self, aList, nMajor):
        self._nMajor = nMajor
        self._aList = aList

    def getNextLocation(self, _a):
        filledLocations = {a.spatialLocator for a in self._aList}
        grid = self._aList.spatialGrid

        for idx in itertools.count():
            j = idx // self._nMajor
            i = idx % self._nMajor
            loc = grid[i, j, 0]
            if loc not in filledLocations:
                return loc

    def assemblyAdded(self, a):
        """
        Do nothing.

        A more optimal implementation would cache things that would be affected by this.
        """


class AssemblyList(composites.Composite):
    """
    A quasi-arbitrary collection of Assemblies.

    The AssemblyList is similar to a Core, in that it is designed to store Assembly
    objects. Unlike the Core, they have far fewer convenience functions, and permit
    looser control over where assemblies actually live.
    """

    def __init__(self, name, parent=None):

        composites.Composite.__init__(self, name)
        self.parent = parent
        # make a Cartesian assembly rack by default. Anything that really cares about
        # the layout should specify one manually or in Blueprints
        self.spatialGrid = grids.CartesianGrid.fromRectangle(50.0, 50.0)

        self._filler = RowMajorAutoFiller(self, 10)

    @property
    def r(self):
        # This needs to be here until we remove the dependency of Reactor upon
        # AssemblyLists
        from armi.reactor import reactors

        return self.getAncestor(fn=lambda x: isinstance(x, reactors.Reactor))

    def __repr__(self):
        return "<AssemblyList object: {0}>".format(self.name)

    def add(self, assem, loc=None):
        """
        Add an Assembly to the list.

        Parameters
        ----------
        assem : Assembly
            The Assembly to add to the list

        loc : LocationBase, optional
            If provided, the assembly is inserted at that location, similarly to how a
            Core would function. If it is not provided, the locator on the Assembly
            object will be used. If the Assembly's locator belongs to
            ``self.spatialGrid``, the Assembly's existing locator will not be used.
            This is unlike the Core, which would try to use the same indices, but move
            the locator to the Core's grid. If no locator is passed, or if the
            Assembly's locator is not in the AssemblyList's grid, then the Assembly will
            be automatically located in the grid using the associated ``AutoFiller``
            object.
        """

        if loc is not None and loc.grid is not self.spatialGrid:
            raise ValueError(
                "An assembly cannot be added to {} using a spatial locator "
                "from another grid".format(self)
            )

        locProvided = loc is not None or (
            assem.spatialLocator is not None
            and assem.spatialLocator.grid is self.spatialGrid
        )

        if locProvided:
            loc = loc or assem.spatialLocator
        else:
            loc = self._filler.getNextLocation(assem)

        super().add(assem)
        assem.spatialLocator = loc
        self._filler.assemblyAdded(assem)

    def getAssembly(self, name):
        """
        Get a specific Assembly by name.
        """
        for a in self.getChildren():
            if a.getName() == name:
                return a

    def count(self):
        if not self.getChildren():
            return
        runLog.important("Count:")
        totCount = 0
        thisTimeCount = 0
        a = self.getChildren()[0]
        lastTime = a.getAge() / units.DAYS_PER_YEAR + a.p.chargeTime

        for a in self.getChildren():
            thisTime = a.getAge() / units.DAYS_PER_YEAR + a.p.chargeTime

            if thisTime != lastTime:
                runLog.important(
                    "Number of assemblies moved at t={0:6.2f}: {1:04d}. Cumulative: {2:04d}".format(
                        lastTime, thisTimeCount, totCount
                    )
                )
                lastTime = thisTime
                thisTimeCount = 0
            totCount += 1
            thisTimeCount += 1


class SpentFuelPool(AssemblyList):
    """A place to put assemblies when they've been discharged. Can tell you inventory stats, etc."""

    def report(self):
        title = "{0} Report".format(self.name)
        runLog.important("-" * len(title))
        runLog.important(title)
        runLog.important("-" * len(title))
        totFis = 0.0
        for a in self.getChildren():
            runLog.important(
                "{assembly:15s} discharged at t={dTime:10f} after {residence:10f} yrs. It entered at cycle: {cycle}. "
                "It has {fiss:10f} kg (x {mult}) fissile and peak BU={bu:.2f} %.".format(
                    assembly=a,
                    dTime=a.p.dischargeTime,
                    residence=(a.p.dischargeTime - a.p.chargeTime),
                    cycle=a.p.chargeCycle,
                    fiss=a.getFissileMass() * a.p.multiplicity,
                    bu=a.getMaxParam("percentBu"),
                    mult=a.p.multiplicity,
                )
            )
            totFis += a.getFissileMass() * a.p.multiplicity / 1000  # convert to kg
        runLog.important(
            "Total full-core fissile inventory of {0} is {1:.4E} MT".format(
                self, totFis / 1000.0
            )
        )


class ChargedFuelPool(AssemblyList):
    """A place to put boosters so you can see how much you added. Can tell you inventory stats, etc."""

    def report(self):
        title = "{0} Report".format(self.name)
        runLog.important("-" * len(title))
        runLog.important(title)
        runLog.important("-" * len(title))
        totFis = 0.0
        runLog.important(
            "{assembly:15s} {dTime:10s} {cycle:3s} {bu:5s} {fiss:13s} {cum:13s}".format(
                assembly="Assem. Name",
                dTime="Charge Time",
                cycle="Charge cyc",
                bu="BU",
                fiss="kg fis (full core)",
                cum="Cumulative fis (full, MT)",
            )
        )
        for a in self.getChildren():
            totFis += a.p.chargeFis * a.p.multiplicity / 1000.0
            runLog.important(
                "{assembly:15s} {dTime:10f} {cycle:3f} {bu:5.2f} {fiss:13.4f} {cum:13.4f}".format(
                    assembly=a,
                    dTime=a.p.chargeTime,
                    cycle=a.p.chargeCycle,
                    fiss=a.p.chargeFis,
                    bu=a.p.chargeBu,
                    cum=totFis,
                )
            )
        runLog.important(
            "Total full core fissile inventory of {0} is {1:.4E} MT".format(
                self, totFis
            )
        )
