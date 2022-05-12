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
An abstract class for interfaces between ARMI and programs that simulate transmutation and decay.
"""
import collections

from armi import interfaces
from armi.nucDirectory import nuclideBases
from armi.nuclearDataIO import xsLibraries
from armi.physics.neutronics.isotopicDepletion.crossSectionTable import (
    CrossSectionTable,
)
from armi.reactor import composites
from armi.reactor.flags import Flags


def isDepletable(obj: composites.ArmiObject):
    """
    Return True if obj or any child is flagged as DEPLETABLE.

    The DEPLETABLE flag is automatically set to true if any composition contains
    nuclides that are in the active nuclides list, unless flags are specifically
    set and DEPLETABLE is left out.

    This is often interpreted by depletion plugins as indicating which parts of the
    problem to apply depletion to. Analysts may want to turn on and off depletion
    in certain problems.

    For example, sometimes they want the control rods to deplete
    to figure out how often to replace them. But in conceptual design, they may want to just
    leave them as they are as an approximation.

    .. warning:: The ``DEPLETABLE`` flag is automatically added to compositions that have
        active nuclides. If you explicitly define any flags at all, you must also
        manually include ``DEPLETABLE`` or else the objects will silently not deplete.

    Notes
    -----
    The auto-flagging of ``DEPLETABLE`` happens in the construction of blueprints
    rather than in a plugin hook because the reactor is not available at the time
    the plugin hook runs.

    See Also
    --------
    armi.reactor.blueprints.componentBlueprint._insertDepletableNuclideKeys
    """

    return obj.hasFlags(Flags.DEPLETABLE) or obj.containsAtLeastOneChildWithFlags(
        Flags.DEPLETABLE
    )


class AbstractIsotopicDepleter:
    r"""
    Interact with a depletion code

    This interface and subClasses deplete under a flux defined outside this
    interface

    The depletion in this analysis only depends on the flux, material vectors,
    nuclear data and countinuous source and loss objects.

    The depleters derived from this abstract class use all the fission products
    armi can handle -- i.e. do not form lumped fission products.

    _depleteByName contains a ARMI objects to deplete keyed by name.
    """
    name = None
    function = "depletion"

    def __init__(self, r=None, cs=None, o=None):
        self.r = r
        self.cs = cs
        self.o = o

        # ARMI objects to deplete keyed by name
        # order is important for consistency in iterating through objects
        # cinder interface input format is very dependent on object order
        self._depleteByName = collections.OrderedDict()

        self.efpdToBurn = None
        self.allNuclidesInProblem = r.blueprints.allNuclidesInProblem if r else []

    def addToDeplete(self, armiObj):
        """Add the oject to the group of objects to be depleted."""
        self._depleteByName[armiObj.getName()] = armiObj

    def setToDeplete(self, armiObjects):
        """Change the group of objects to deplete to the specified group."""
        listOfTuples = [(obj.getName(), obj) for obj in armiObjects]
        self._depleteByName = collections.OrderedDict(listOfTuples)

    def getToDeplete(self):
        """Return objects to be depleted."""
        return list(self._depleteByName.values())

    def run(self):
        r"""
        Submit depletion case with external solver to the cluster.

        In addition to running the physics kernel, this method calls the waitForJob method
        to wait for it job to finish

        comm = MPI.COMM_SELF.Spawn(sys.executable,args=['cpi.py'],maxprocs=5)
        """
        raise NotImplementedError


def makeXsecTable(
    compositeName,
    xsType,
    mgFlux,
    isotxs,
    headerFormat="$ xsecs for {}",
    tableFormat="\n{mcnpId} {nG:.5e} {nF:.5e} {n2n:.5e} {n3n:.5e} {nA:.5e} {nP:.5e}",
):
    """
    Make a cross section table for depletion physics input decks.

    Parameters
    ----------
    armiObject: armiObject
        an armi object --  batch or block --
        with a .p.xsType and a getMgFlux method
    activeNuclides: list
        a list of the nucNames of active isotopes
    isotxs: isotxs object
    headerFormat: string (optional)
        this is the format in which the elements of the header with be returned
        -- i.e. if you use a .format() call with  the case name you'll return a
        formatted list of string elements
    tableFormat: string (optional)
        this is the format in which the elements of the table with be returned
        -- i.e. if you use a .format() call with mcnpId, nG, nF, n2n, n3n, nA,
        and nP you'll get the format you want. If you use a .format() call with  the case name you'll return a
        formatted list of string elements

    Results
    -------
    output: list
        a list of string elements that together make a xsec card

    See Also
    --------
    crossSectionTable.makeCrossSectionTable
        Makes a table for arbitrary ArmiObjects
    """
    xsTable = CrossSectionTable()

    if not xsType or not sum(mgFlux) > 0:
        return []
    xsTable.setName(compositeName)
    totalFlux = sum(mgFlux)

    for nucLabel, nuc in isotxs.items():
        if xsType != xsLibraries.getSuffixFromNuclideLabel(nucLabel):
            continue
        nucName = nuc.name
        nb = nuclideBases.byName[nucName]
        if isinstance(
            nb, (nuclideBases.LumpNuclideBase, nuclideBases.DummyNuclideBase)
        ):
            continue
        microMultiGroupXS = isotxs[nucLabel].micros
        if not isinstance(nb, nuclideBases.NaturalNuclideBase):
            xsTable.addMultiGroupXS(nucName, microMultiGroupXS, mgFlux, totalFlux)
    return xsTable.getXsecTable(headerFormat=headerFormat, tableFormat=tableFormat)


class AbstractIsotopicDepletionReader(interfaces.OutputReader):
    r"""
    Read number density output produced by the isotopic depletion
    """

    def read(self):
        r"""
        read a isotopic depletion Output File and applies results to armi objects in the ToDepletion attribute
        """
        raise NotImplementedError


class Csrc:
    """
    Writes a continuous source term card in a depletion interface.

    Notes
    -----
    The chemical vector is a dictionary of chemicals and their removal rate
    constant -- this works like a decay constant.

    The isotopic vector is used to make a source material in continuous source definitions.

    This is also the base class for continuous loss cards.
    """

    def __init__(self):
        self._chemicalVector = {}
        self._isotopicVector = {}
        self.defaultVector = {"0": 0}

    def setChemicalVector(self, chemicalVector):
        self._chemicalVector = chemicalVector

    def getChemicalVector(self):
        return self._chemicalVector

    def write(self):
        """
        return a list of lines to write for a csrc card
        """
        raise NotImplementedError
