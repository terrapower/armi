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
Reactor objects represent the highest level in the hierarchy of structures that compose the system
to be modeled. Core objects represent collections of assemblies.
"""
from typing import Optional
import copy

from armi import materials
from armi import runLog
from armi.reactor import composites
from armi.reactor import reactorParameters
from armi.reactor.excoreStructure import ExcoreStructure
from armi.reactor.core import Core
from armi.reactor.systemLayoutInput import SystemLayoutInput
from armi.settings.fwSettings.globalSettings import (
    CONF_GEOM_FILE,
    CONF_MATERIAL_NAMESPACE_ORDER,
    CONF_SORT_REACTOR,
)
from armi.utils import directoryChangers


class Reactor(composites.Composite):
    """
    Top level of the composite structure, potentially representing all components in a reactor.

    This class contains the core and any ex-core structures that are to be represented in the ARMI
    model. Historically, the ``Reactor`` contained only the core. To support better representation
    of ex-core structures, the old ``Reactor`` functionality was moved to the newer `Core` class,
    which has a ``Reactor`` parent.

    .. impl:: The user-specified reactor.
        :id: I_ARMI_R
        :implements: R_ARMI_R

        The :py:class:`Reactor <armi.reactor.reactors.Reactor>` is the top level of the composite
        structure, which can represent all components within a reactor core. The reactor contains a
        :py:class:`Core <armi.reactor.reactors.Core>`, which contains a collection of
        :py:class:`Assembly <armi.reactor.assemblies.Assembly>` objects arranged in a hexagonal or
        Cartesian grid. Each Assembly consists of a stack of
        :py:class:`Block <armi.reactor.blocks.Block>` objects, which are each composed of one or
        more :py:class:`Component <armi.reactor.components.component.Component>` objects. Each
        :py:class:`Interface <armi.interfaces.Interface>` is able to interact with the reactor and
        its child :py:class:`Composites <armi.reactor.composites.Composite>` by retrieving data from
        it or writing new data to it. This is the main medium through which input information and
        the output of physics calculations is exchanged between interfaces and written to an ARMI
        database.
    """

    pDefs = reactorParameters.defineReactorParameters()

    def __init__(self, name, blueprints):
        composites.Composite.__init__(self, "R-{}".format(name))
        self.o = None
        self.spatialGrid = None
        self.spatialLocator = None
        self.p.maxAssemNum = 0
        self.p.cycle = 0
        self.core = None
        self.excore = {}
        self.blueprints = blueprints

    def __getstate__(self):
        """Applies a settings and parent to the reactor and components."""
        state = composites.Composite.__getstate__(self)
        state["o"] = None
        return state

    def __setstate__(self, state):
        composites.Composite.__setstate__(self, state)

    def __deepcopy__(self, memo):
        memo[id(self)] = newR = self.__class__.__new__(self.__class__)
        newR.__setstate__(copy.deepcopy(self.__getstate__(), memo))
        newR.name = self.name + "-copy"
        return newR

    def __repr__(self):
        return "<{}: {} id:{}>".format(self.__class__.__name__, self.name, id(self))

    @property
    def sfp(self):
        """TODO: For backwards compatibility, give the reactor an sfp property."""
        return self.excore.get("sfp", None)

    @sfp.setter
    def sfp(self, newSfp):
        """TODO: For backwards compatibility, give the reactor an sfp property."""
        self.excore["sfp"] = newSfp

    def add(self, container):
        composites.Composite.add(self, container)
        cores = [c for c in self.getChildren(deep=True) if isinstance(c, Core)]
        if cores:
            if len(cores) != 1:
                raise ValueError(
                    "Only 1 core may be specified at this time. Please adjust input. "
                    f"{len(cores)} cores found."
                )
            self.core = cores[0]

        if isinstance(container, ExcoreStructure):
            nomen = container.name.replace(" ", "").lower()
            if nomen == "spentfuelpool":
                # special case
                nomen = "sfp"
            self.excore[nomen] = container

    def incrementAssemNum(self):
        """
        Increase the max assembly number by one and returns the current value.

        Notes
        -----
        The "max assembly number" is not currently used in the Reactor. So the idea is that we
        return the current number, then iterate it for the next assembly.

        Obviously, this method will be unused for non-assembly-based reactors.

        Returns
        -------
        int
            The new max Assembly number.
        """
        val = int(self.p.maxAssemNum)
        self.p.maxAssemNum += 1
        return val

    def normalizeNames(self):
        """
        Renumber and rename all the Assemblies and Blocks.

        This method normalizes the names in the Core then the SFP.

        Returns
        -------
        int
            The new max Assembly number.
        """
        self.p.maxAssemNum = 0

        ind = self.core.normalizeNames(self.p.maxAssemNum)
        self.p.maxAssemNum = ind

        ind = self.sfp.normalizeNames(self.p.maxAssemNum)
        self.p.maxAssemNum = ind

        return ind


def loadFromCs(cs) -> Reactor:
    """
    Load a Reactor based on the input settings.

    Parameters
    ----------
    cs: Settings
        A relevant settings object

    Returns
    -------
    Reactor
        Reactor loaded from settings file
    """
    from armi.reactor import blueprints

    bp = blueprints.loadFromCs(cs)
    return factory(cs, bp)


def factory(cs, bp, geom: Optional[SystemLayoutInput] = None) -> Reactor:
    """Build a reactor from input settings, blueprints and geometry."""
    from armi.reactor import blueprints

    runLog.header("=========== Constructing Reactor and Verifying Inputs ===========")
    # just before reactor construction, update the material "registry" with user settings,
    # if it is set. Often it is set by the application.
    if cs[CONF_MATERIAL_NAMESPACE_ORDER]:
        materials.setMaterialNamespaceOrder(cs[CONF_MATERIAL_NAMESPACE_ORDER])
    r = Reactor(cs.caseTitle, bp)

    if cs[CONF_GEOM_FILE]:
        blueprints.migrate(bp, cs)

    # TODO: JOHN, is this necessary? Maybe not all reactors need SFPs?
    if not any(structure.typ == "sfp" for structure in bp.systemDesigns.values()):
        bp.addDefaultSFP()

    with directoryChangers.DirectoryChanger(cs.inputDirectory, dumpOnException=False):
        # always construct the core first (for assembly serial number purposes)
        if not bp.systemDesigns:
            raise ValueError(
                "The input must define a `core` system, but does not. Update inputs"
            )

        for structure in bp.systemDesigns:
            bpGeom = geom if structure.name.lower() == "core" else None
            structure.construct(cs, bp, r, geom=bpGeom)

    runLog.debug(f"Reactor: {r}")

    # return a Reactor object
    if cs[CONF_SORT_REACTOR]:
        r.sort()
    else:
        runLog.warning(
            "DeprecationWarning: This Reactor is not being sorted on blueprint read. "
            f"Due to the setting {CONF_SORT_REACTOR}, this Reactor is unsorted. "
            "But this feature is temporary and will be removed by 2024."
        )

    return r
