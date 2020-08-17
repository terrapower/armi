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

import numpy

from armi.utils.units import getGroupStructure
from armi.utils.densityTools import calculateNumberDensity
from armi.reactor import composites
from armi.reactor import blocks
from armi.reactor.flags import Flags
from armi.reactor.composites import ArmiObject
from armi.reactor.components import ZeroMassComponent, PositiveOrNegativeVolumeComponent
from armi.physics.neutronics.fissionProductModel.lumpedFissionProduct import (
    expandFissionProducts,
)

from armi.reactor import batchParameters

SMALL_NUMBER = 1e-24


class Batch(blocks.Block):
    """
    Batch represents a 0-D mass of nuclides to be depleted it keeps track of nuclides and integral 
    flux. It does not keep track of volume.

    Everything in a batch should have one lumped fission product collection and one
    lumped fission product collection or not use lumped fission products.
    """

    pDefs = batchParameters.getBatchParameterDefinitions()

    def __init__(self, name="Batch", cs=None):
        """
        Builds a new ARMI batch

        Parameters
        ----------
        name : str, optional
            The name of this batch
        """

        ArmiObject.__init__(self, name)
        self.crossSectionTable = None

    def __repr__(self):
        return "<Batch {type} {name}>".format(type=self.getType(), name=self.getName())

    def add(self, c):
        """
        Add a new child.

        Children in batch objects have different parents.

        Parameters
        ----------
        obj : armiObject
        """
        if c in self:
            raise RuntimeError(
                "Cannot add {0} because it has already been added to {1}.".format(
                    c, self
                )
            )
        self._children.append(c)

    def getMgFlux(self):
        return composites.Composite.getMgFlux(self)

    def getIntegratedMgFlux(self, adjoint=False, gamma=False):
        return composites.Composite.getIntegratedMgFlux(
            self, adjoint=adjoint, gamma=gamma
        )

    def addMass(self, nucName, mass, density=None, lumpedFissionProducts=None):
        """
        Adds mass to batch.

        Parameters
        ----------
        nucName : str
            nuclide name -- e.g. 'U235'
        mass : float
            mass in grams of the nuclide to be added
        density : float
            density in grams per cc of the nuclide
        lumpedFissionProducts : LumpedFissionProductCollection
            the LumpedFissionProductCollection
        """
        if density is None:
            density = self.p.targetDensity
        if mass != 0:
            if "FP" not in nucName:
                self.add(makeMassAdditionComponent(nucName, mass, density))
            elif "FP" in nucName and lumpedFissionProducts:
                masses = {}
                lfp = lumpedFissionProducts[nucName]
                for nb, mFrac in lfp.getMassFracs().items():
                    masses[nb.name] = mFrac * mass
                self.addMasses(masses, density=density)
            else:
                raise AttributeError(
                    "nucName: {} , mass {} has no lumpedFissionProduct -- {} -- defined".format(
                        nucName, mass, lumpedFissionProducts
                    )
                )

    def addMasses(self, masses, density=None, lumpedFissionProducts=None):
        """
        Adds a vector of masses to batch

        Parameters
        ----------
        masses : Dict
            a dictionary of masses (g) indexed by nucNames (string)
        """
        if density is None:
            density = self.p.targetDensity
        composites.Composite.addMasses(
            self, masses, density=density, lumpedFissionProducts=lumpedFissionProducts
        )

    def setTargetDensity(self, density):
        """
        Parameters
        ----------
        density : float
            target density of the mass addition components
        """
        self.p.targetDensity = density
        self.updateMassAdditionComponents(density)

    def updateMassAdditionComponents(self, density):
        """
        Parameters
        ----------
        density : float
            target density of the mass addition components
        """
        for c in self.getMassAdditionComponents():
            nucNames = list(c.getNuclides())
            if len(nucNames) != 1:
                raise AssertionError(
                    "This mass addition component is not a mass addition component because it has multiple nuclides"
                )
            mass = c.getMass()
            newVolume = mass / density
            c.p.numberDensities[nucNames[0]] = calculateNumberDensity(
                nucNames[0], mass, newVolume
            )
            c.setVolume(newVolume)

    def getMassAdditionComponents(self):
        return self.getChildrenWithFlags(
            typeSpec=Flags.BATCHMASSADDITION, exactMatch=False
        )

    def setNumberDensity(self, *args, **kwargs):
        """
        Raises not implemented error because setNumberDensity does not really apply for batch 
        objects -- its an over constrained problem.
        """
        raise NotImplementedError

    def setMasses(self, masses, density=None, lumpedFissionProducts=None):
        """
        Set multiple masses at once

        Parameters
        ----------
        masses : dict
            dictionary of masses in grams indexed by their nucNames
        density : float
            target density in g/cc
        lumpedFissionProducts : lumpedFissionProductCollection
        """
        newMasses = {}
        nucNames = self.getNuclides().union(masses.keys())
        initialMasses = self.getMasses()
        for nucName in nucNames:
            newMass = masses.get(nucName, 0) - initialMasses.get(nucName, 0)
            if newMass != 0:
                newMasses[nucName] = newMass
        try:
            composites.Composite.addMasses(
                self,
                newMasses,
                density=density,
                lumpedFissionProducts=lumpedFissionProducts,
            )
        except Exception as ee:
            raise AttributeError(
                str(ee) + "\n    setMasses in batch {} failed"
                "\n    masses vector {}"
                "\n    lumpedFissionProduct {} self.getLumpedFissionProductIfNecessary {}".format(
                    self,
                    masses,
                    lumpedFissionProducts,
                    self.getLumpedFissionProductsIfNecessary(nuclides=masses.keys()),
                )
            )

    def setMass(self, nucName, mass, density=None, lumpedFissionProducts=None):
        """
        Set the mass of a defined nuclide to the defined mass

        Parameters
        ----------
        nucName : string
            armi nuclide name (e.g. U235)
        mass : float
            this is a dictionary of masses in grams
        """
        additionalMass = mass - self.getMass(nucName)
        self.addMass(
            nucName,
            additionalMass,
            density=density,
            lumpedFissionProducts=lumpedFissionProducts,
        )

    def getVolume(self, excludeMassAdditionComponents=False):
        """Returns volume in cm^3."""
        volume = blocks.Block.getVolume(self)
        if excludeMassAdditionComponents:
            volume -= sum([c.getVolume() for c in self.getMassAdditionComponents()])
        return volume

    def setIntegratedMgFlux(self, integratedMgFlux):
        """
        Sets the integrated flux to the provided vector.

        Parameters
        ----------
        integratedMgFlux : numpy array
            array of integrated flux in different energy bins (n-cm/s)
        """
        self.addIntegratedMgFlux(integratedMgFlux - self.getIntegratedMgFlux())

    def addIntegratedMgFlux(self, mgFlux):

        if not isinstance(mgFlux, numpy.ndarray):
            if isinstance(mgFlux, list):
                mgFlux = numpy.array(mgFlux)
            else:
                raise TypeError("mgFlux is not a numpy.array or list")

        self.add(makeMgFluxBlock(mgFlux))

    def copy(self, newBatchName=None):
        """
        This method returns a batch that will return the same values of mass,
        mgFlux. The mgFlux are held on the block level, this block
        is composed of a single component with the and mass
        as self.

        Parameters
        ---------
        newBatchName : str

        Return
        ------
        newBatch : Batch
        """

        if newBatchName is None:
            newBatchName = self.name + "Copy"
        newBatch = Batch(name=newBatchName)
        newBatch.setTargetDensity(self.p.targetDensity)
        newBatch.addIntegratedMgFlux(self.getIntegratedMgFlux())
        lfps = self.getLumpedFissionProductsIfNecessary(nuclides=["LFP35"])
        masses = expandFissionProducts(self.getMasses(), lfps)
        newBatch.addMasses(masses)
        newBatch.setLumpedFissionProducts(lfps)
        newBatch.crossSectionTable = self.getCrossSectionTable()

        return newBatch

    def __deepcopy__(self, memo):
        """
        Set custom deep-copy behavior.

        We detach the recursive links to the parent and the reactor to prevent blocks
        carrying large independent copies of stale reactors in memory. If you make a new block,
        you must add it to an assembly and a reactor.
        """
        return self.copy(newBatchName=self.name)

    def getReactionRates(self, nucName):
        """
        get reaction rates for (n,gamma), (n,fission), (n,2n), (n,alpha), (n,proton) reactions

        Parameters
        ----------
        nucName : str
            nuclide name -- e.g. 'U235'

        Returns
        -------
        rxnRates : dict
            dictionary of reaction rates (rxn/s) for nG, nF, n2n, nA and nP
        """
        rxnRates = {"nG": 0, "nF": 0, "n2n": 0, "nA": 0, "nP": 0, "n3n": 0}

        for armiObject in self.getChildren():
            for rxName, val in armiObject.getReactionRates(nucName).items():
                rxnRates[rxName] += val

        return rxnRates


def makeMgFluxBlock(mgFlux):
    """
    Parameters
    ----------
    mgFlux : numpy array
        volume integrated neutron flux n-cm/s in each energy group

    Returns
    -------
    b : block
        a block with and integrated flux equal to the defined mgFlux vector
    """
    c = ZeroMassComponent("batchFluxAdditionComponent", "Void", 0.0, 0.0, volume=0.0)
    b = blocks.Block("batchFluxAdditionBlock")
    b.add(c)
    b.p.mgFlux = mgFlux
    return b


def makeMassAdditionComponent(nucName, mass, density):
    """
    Parameters
    ----------
    nucName : string
        armi nuclide name (e.g. U235)
    mass : float
        this is a dictionary of masses in grams
    density : float
        this is the target density of this component

    Returns
    -------
    c : component
        a component with a mass equal to mass of the nuclide, nucName, with
        the density equal to the defined density
    """

    volume = mass / density
    c = PositiveOrNegativeVolumeComponent(
        "batchMassAdditionComponent", "Custom", 0.0, 0.0, volume=volume
    )
    c.setMass(nucName, mass)
    return c


def makeEmptyBatch(name, cs=None):
    """
    Parameters
    ----------
    name : str

    cs : settings

    Return
    ------
    aB : batch
        a batch that is pretty much empty, but will not crash methods that are assumed to be populated
    """
    if cs is None:
        mgFlux = numpy.array([SMALL_NUMBER] * 45)
    else:
        mgFlux = numpy.array(
            [SMALL_NUMBER for _ in getGroupStructure(cs["groupStructure"])]
        )

    aB = Batch(name=name)
    aB.addMass("HE4", SMALL_NUMBER)
    aB.setIntegratedMgFlux(mgFlux)
    return aB


def moveMassFromFirstBatchToSecondBatch(donorBatch, receiverBatch):
    """
    Moves mass from one batch to another.

    Parameters
    ----------
    donorBatch : batch
        this batch donates its mass

    receiverBatch : batch
        this batch receives the donorBatch's mass

    Returns
    -------
    donorBatch : batch
        this should be essentially empty

    receiverBatch : batch
        this now has the mass from the donor batch
    """
    for nucName, mass in donorBatch.getMasses().items():
        if mass >= SMALL_NUMBER:
            receiverBatch.addMass(nucName, mass)
            donorBatch.removeMass(nucName, mass)

    return donorBatch, receiverBatch


def calculateBatchAverageDensity(aB, excludeMassAdditionComponent=False):
    """
    Parameters
    ----------
    aB : batch object

    excludeMassAdditionComponent : bool
        if this is True, exclude mass addition components for the density
        calculation

    Return
    ------
    density : float
        density in grams / centimeters cubed
    """
    mass = aB.getMass()
    volume = aB.getVolume()

    if excludeMassAdditionComponent:
        for c in aB.getMassAdditionComponents():
            mass -= c.getMass()
            volume -= c.getVolume()
    try:
        density = mass / volume
    except ZeroDivisionError as ee:
        try:
            assert mass == 0
            assert volume == 0
        except AssertionError:
            raise ee
        density = 0

    return density
