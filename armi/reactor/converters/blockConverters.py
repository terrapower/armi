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
Convert block geometry from one to another, etc.
"""
import copy
import math

import numpy
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge
from matplotlib.collections import PatchCollection

from armi.reactor import blocks
from armi.reactor import grids
from armi.reactor import components
from armi.reactor.flags import Flags
from armi.utils import hexagon
from armi import runLog

SIN60 = math.sin(math.radians(60.0))


class BlockConverter:
    """Converts a block."""

    def __init__(self, sourceBlock, quiet=False):
        """
        Parameters
        ----------
        sourceBlock : :py:class:`armi.reactor.blocks.Block`
            An ARMI Block object to convert.
        quite : boolean, optional
            If True, less information is output in the runLog.
        """
        self._quiet = quiet
        self._sourceBlock = sourceBlock
        self.convertedBlock = None  # the new block that is created.

    def dissolveComponentIntoComponent(self, soluteName, solventName, minID=0.0):
        """
        Make a new block that homogenized one component into another while conserving number of atoms.

        Parameters
        ----------
        soluteName : str
            The name of the solute component in _sourceBlock
        solventName : str
            The name of the solvent component in _sourceBlock
        minID : float
            The minimum hot temperature diameter allowed for the solvent.
            This is useful for forcing components to not overlap.

        Warning
        -------
        Nuclides merged into another component will be the temperature of the new component as temperature
        is stored on the component level. In the solute and solvent are the same temperature this is not an issue.
        Converted blocks that have dissolved components should avoid having their temperatures changed.
        This is because the component being merged into retains its old thermal expansion properties and
        may not be consistent with how the components would behave independently. For this reason it is
        recommended that these blocks be made right before the physics calculation of interest and be immediately
        discarded. Attaching them to the reactor is not recommended.
        """
        if not self._quiet:
            runLog.extra(
                "Homogenizing the {} component into the {} component in block {}".format(
                    soluteName, solventName, self._sourceBlock
                )
            )
        # break up dimension links since we will be messing with this block's components
        newBlock = copy.deepcopy(self._sourceBlock)
        # cannot pass components directly since the new block will have new components
        solute = newBlock.getComponentByName(soluteName)
        solvent = newBlock.getComponentByName(solventName)
        self._checkInputs(soluteName, solventName, solute, solvent)

        soluteLinks = solute.getLinkedComponents()
        # the area about to be added by the dimension change can be different than the simple area of the
        # merged component due to void gaps between components
        oldArea = solvent.getArea()
        runLog.debug("removing {}".format(solute))
        # skip recomputation of area fractions because the blocks still have 0 height at this stage and derived
        # shape volume computations will fail
        newBlock.remove(solute, recomputeAreaFractions=False)
        self._sourceBlock = newBlock

        # adjust new shape area.
        if solvent.__class__ is components.DerivedShape:
            pass  # If it's coolant, the auto-fill area system gets it. coolant has no links
        else:
            soluteID, soluteOD = (
                solute.getDimension("id", cold=False),
                solute.getDimension("od", cold=False),
            )
            if solvent.getDimension("id", cold=False) > soluteID:
                runLog.debug(
                    "Decreasing ID of {} to accommodate {}.".format(solvent, solute)
                )
                solvent.setDimension("id", soluteID, cold=False)
            if solvent.getDimension("od", cold=False) < soluteOD:
                runLog.debug(
                    "Increasing OD of {} to accommodate {}.".format(solvent, solute)
                )
                solvent.setDimension("od", soluteOD, cold=False)
            if solvent.getDimension("id", cold=False) < minID:
                runLog.debug(
                    "Updating the ID of {} the the specified min ID: {}.".format(
                        solvent, minID
                    )
                )
                solvent.setDimension("id", minID, cold=False)

            if soluteLinks:
                self.restablishLinks(solute, solvent, soluteLinks)
            self._verifyExpansion(solute, solvent)

        solvent.changeNDensByFactor(oldArea / solvent.getArea())
        solute.mergeNuclidesInto(solvent)

    def _checkInputs(self, soluteName, solventName, solute, solvent):
        if solute is None or solvent is None:
            raise ValueError(
                "Block {} must have a {} component and a {} component to homogenize.".format(
                    self._sourceBlock, soluteName, solventName
                )
            )
        if not (
            isinstance(solvent, components.DerivedShape)
            or all(isinstance(c, components.Circle) for c in (solute, solvent))
        ):
            raise ValueError(
                "Components are not of compatible shape to be merged "
                "solute: {}, solvent: {}".format(solute, solvent)
            )
        if solute.getArea() <= 0 or solvent.getArea() <= 0:
            raise ValueError(
                "Cannot merge components if either have negative area. "
                "{} area: {}, {} area : {}".format(
                    solute, solvent, solute.getArea(), solvent.getArea()
                )
            )

    def restablishLinks(self, solute, solvent, soluteLinks):
        runLog.extra(
            "Solute is linked to component(s) {} and these links will be reestablished.".format(
                soluteLinks
            )
        )
        for linkedC in soluteLinks:
            if linkedC in solvent.getLinkedComponents():
                if not linkedC.containsVoidMaterial():
                    raise ValueError(
                        "Non-Void component {} was linked to solute and solvent {} in converted block {}. "
                        "Please dissolve this separately.".format(
                            linkedC, solvent, self._sourceBlock
                        )
                    )
                runLog.extra(
                    "Removing void component {} in converted block {}."
                    "".format(linkedC, self._sourceBlock)
                )
                self._sourceBlock.remove(linkedC)
            else:
                dims = linkedC.getDimensionNamesLinkedTo(solute)
                runLog.extra(
                    "Linking component {} in converted block {} to solvent {}."
                    "".format(linkedC, self._sourceBlock, solvent)
                )
                for dimToChange, dimOfOther in dims:
                    linkedC.setLink(dimToChange, solvent, dimOfOther)

    def _verifyExpansion(self, solute, solvent):
        validComponents = (
            c for c in self._sourceBlock if not isinstance(c, components.DerivedShape)
        )
        for c in sorted(validComponents):
            if (
                not isinstance(c, components.Circle)
                or c is solvent
                or c.containsVoidMaterial()
            ):
                continue
            if c.isEncapsulatedBy(solvent):
                raise ValueError(
                    "There is a non void component {} in the location where component {} was expanded "
                    "to absorb component solute {}. solvent dims {}, {} comp dims {} {}.".format(
                        c, solvent, solute, solvent.p.id, solvent.p.od, c.p.id, c.p.od
                    )
                )
            if c.getArea() < 0.0:
                runLog.warning(
                    "Component {} still has negative area after {} was dissolved into {}"
                    "".format(c, solute, solvent),
                    single=True,
                )

    def convert(self):
        raise NotImplementedError


class ComponentMerger(BlockConverter):
    """For a provided block, merged the solute component into the solvent component."""

    def __init__(self, sourceBlock, soluteName, solventName, quiet=False):
        """
        Parameters
        ----------
        sourceBlock : :py:class:`armi.reactor.blocks.Block`
            An ARMI Block object to convert.
        soluteName : str
            The name of the solute component in _sourceBlock
        solventName : str
            The name of the solvent component in _sourceBlock
        quite : boolean, optional
            If True, less information is output in the runLog.
        """
        BlockConverter.__init__(self, sourceBlock, quiet=quiet)
        self.soluteName = soluteName
        self.solventName = solventName

    def convert(self):
        """Return a block with the solute merged into the solvent."""
        self.dissolveComponentIntoComponent(self.soluteName, self.solventName)
        return self._sourceBlock


class MultipleComponentMerger(BlockConverter):
    """
    Dissolves multiple components and checks validity at end.

    Doesn't run _verifyExpansion until the end so that the order the components are dissolved in
    does not cause a failure. For example if two liners are dissolved into the clad and the farthest
    liner was dissolved first, this would normally cause a ValueError in _verifyExpansion since the
    clad would be completely expanded over a non void component.

    This could be implemented on the regular ComponentMerger, as the Flags system has enough power
    in the type specification arguments to things like ``getComponents()``, ``hasFlags()``, etc., to
    do single and multiple components with the same code.
    """

    def __init__(
        self, sourceBlock, soluteNames, solventName, specifiedMinID=0.0, quiet=False
    ):
        """
        Parameters
        ----------
        sourceBlock : :py:class:`armi.reactor.blocks.Block`
            An ARMI Block object to convert.
        soluteNames : list
            List of str names of the solute components in _sourceBlock
        solventName : str
            The name of the solvent component in _sourceBlock
        minID : float
            The minimum hot temperature diameter allowed for the solvent.
            This is useful for forcing components to not overlap.
        quite : boolean, optional
            If True, less information is output in the runLog.
        """
        BlockConverter.__init__(self, sourceBlock, quiet=quiet)
        self.soluteNames = soluteNames
        self.solventName = solventName
        self.specifiedMinID = specifiedMinID

    def _verifyExpansion(self, solute, solvent):
        """Wait until all components are dissolved to check this."""
        pass

    def convert(self):
        """Return a block with the solute merged into the solvent."""
        for soluteName in self.soluteNames:
            self.dissolveComponentIntoComponent(
                soluteName, self.solventName, minID=self.specifiedMinID
            )
        solvent = self._sourceBlock.getComponentByName(self.solventName)
        BlockConverter._verifyExpansion(self, self.soluteNames, solvent)
        return self._sourceBlock


class BlockAvgToCylConverter(BlockConverter):
    """
    Convert a block and driver block into a block made of a concentric circles using
    block (homogenized) composition.

    Notes
    -----
    This converter is intended for use in building 1-dimensional models of a set of block.
    numInternalRings controls the number of rings to use for the source block, while the
    numExternalRings controls the number of rings for the driver fuel block.  The number
    of blocks to in each ring grows by 6 for each ring in hex geometry and 8 for each ring
    in Cartesian.

    This converter is opinionated in that it uses a spatial grid to determine how many
    blocks to add based on the type of the ``sourceBlock``. For example, if the ``sourceBlock``
    is a HexBlock then a HexGrid will be used. If the ``sourceBlock`` is a CartesianBlock
    then a CartesianGrid without an offset will be used.

    See Also
    --------
    HexComponentsToCylConverter: This converter is more useful if the pin lattice is in a
    hex lattice.
    """

    def __init__(
        self,
        sourceBlock,
        driverFuelBlock=None,
        numInternalRings=1,
        numExternalRings=None,
        quiet=False,
    ):

        BlockConverter.__init__(self, sourceBlock, quiet=quiet)
        self._driverFuelBlock = driverFuelBlock
        self._numExternalRings = numExternalRings
        self.convertedBlock = blocks.ThRZBlock(
            name=sourceBlock.name + "-cyl", height=sourceBlock.getHeight()
        )
        self.convertedBlock.setLumpedFissionProducts(
            sourceBlock.getLumpedFissionProductCollection()
        )
        self._numInternalRings = numInternalRings

    def convert(self):
        """Return a block converted into cylindrical geometry, possibly with other block types surrounding it."""
        self._addBlockRings(
            self._sourceBlock, self._sourceBlock.getType(), self._numInternalRings, 1
        )
        self._addDriverFuelRings()
        return self.convertedBlock

    def _addBlockRings(
        self, blockToAdd, blockName, numRingsToAdd, firstRing, mainComponent=None
    ):
        """Add a homogenous block ring to the converted block."""
        runLog.info(
            "Converting representative block {} to its equivalent cylindrical model".format(
                self._sourceBlock
            )
        )

        innerDiam = (
            self.convertedBlock[-1].getDimension("od")
            if len(self.convertedBlock)
            else 0.0
        )

        if mainComponent is not None:
            newCompProps = mainComponent.material
            tempInput = tempHot = mainComponent.temperatureInC
        else:  # no component specified so just use block vals
            newCompProps = (
                "Custom"  # this component shouldn't change temperature anyway
            )
            tempInput = tempHot = blockToAdd.getAverageTempInC()

        if isinstance(blockToAdd, blocks.HexBlock):
            grid = grids.HexGrid.fromPitch(1.0)
        elif isinstance(blockToAdd, blocks.CartesianBlock):
            grid = grids.CartesianGrid.fromRectangle(1.0, 1.0)
        else:
            raise ValueError(
                f"The `sourceBlock` of type {type(blockToAdd)} is not supported in {self}."
            )

        for ringNum in range(firstRing, firstRing + numRingsToAdd):
            numFuelBlocksInRing = grid.getPositionsInRing(ringNum)
            assert numFuelBlocksInRing is not None
            fuelBlockTotalArea = numFuelBlocksInRing * blockToAdd.getArea()
            driverOuterDiam = getOuterDiamFromIDAndArea(innerDiam, fuelBlockTotalArea)
            driverRing = components.Circle(
                blockName,
                newCompProps,
                tempInput,
                tempHot,
                od=driverOuterDiam,
                id=innerDiam,
                mult=1,
            )
            driverRing.setNumberDensities(blockToAdd.getNumberDensities())
            self.convertedBlock.add(driverRing)
            innerDiam = driverOuterDiam

    def _addDriverFuelRings(self):
        """
        Add driver fuel blocks as the outer-most surrounding ring.

        Notes
        -----
        This is intended to be used to drive non-fuel compositions, DU, etc.
        """
        if self._driverFuelBlock is None:
            return
        if not self._driverFuelBlock.isFuel():
            raise ValueError(
                "Driver block {} must be fuel".format(self._driverFuelBlock)
            )
        if self._numExternalRings < 0:
            raise ValueError(
                "Number of fuel rings is set to {}, but must be a positive integer.".format(
                    self._numExternalRings
                )
            )

        blockName = self._driverFuelBlock.getType() + " driver"
        fuel = self._driverFuelBlock.getChildrenWithFlags(Flags.FUEL)[
            0
        ]  # used for mat properties and temperature

        self._addBlockRings(
            self._driverFuelBlock,
            blockName,
            self._numExternalRings,
            self._numInternalRings + 1,
            mainComponent=fuel,
        )

    def plotConvertedBlock(self, fName=None):
        """Render an image of the converted block."""
        runLog.extra(
            "Plotting equivalent cylindrical block of {}".format(self._sourceBlock)
        )
        fig, ax = plt.subplots()
        fig.patch.set_visible(False)
        ax.patch.set_visible(False)
        ax.axis("off")
        patches = []
        colors = []
        for circleComp in self.convertedBlock:
            innerR, outerR = (
                circleComp.getDimension("id") / 2.0,
                circleComp.getDimension("od") / 2.0,
            )
            runLog.debug(
                "Plotting {:40s} with {:10.3f} {:10.3f} ".format(
                    circleComp, innerR, outerR
                )
            )
            circle = Wedge((0.0, 0.0), outerR, 0, 360.0, outerR - innerR)
            patches.append(circle)
            colors.append(circleComp.density())
        colorMap = matplotlib.cm
        p = PatchCollection(patches, alpha=1.0, linewidths=0.1, cmap=colorMap.YlGn)
        p.set_array(numpy.array(colors))
        ax.add_collection(p)
        ax.autoscale_view(True, True, True)
        ax.set_aspect("equal")
        fig.tight_layout()
        if fName:
            plt.savefig(fName)
        else:
            plt.show()
        return fName


class HexComponentsToCylConverter(BlockAvgToCylConverter):
    """
    Converts a hexagon full of pins into a circle full of concentric circles.

    Notes
    -----
    This is intended to capture heterogeneous effects while generating cross sections in
    MCC3. The resulting 1D cylindrical block will not be used in subsequent core
    calculations.

    Repeated pins/coolant rings will be built, followed by the non-pins like
    duct/intercoolant pinComponentsRing1 | coolant | pinComponentsRing2 | coolant | ... |
    nonpins ...

    This converter expects the ``sourceBlock`` and ``driverFuelBlock`` to defined and for
    the ``sourceBlock`` to have a spatial grid defined. Additionally, both the ``sourceBlock``
    and ``driverFuelBlock`` must be instances of HexBlocks.
    """

    def __init__(
        self,
        sourceBlock,
        driverFuelBlock=None,
        numExternalRings=None,
        mergeIntoClad=None,
        quiet=False,
    ):
        BlockAvgToCylConverter.__init__(
            self,
            sourceBlock,
            driverFuelBlock=driverFuelBlock,
            numExternalRings=numExternalRings,
            quiet=quiet,
        )
        if not isinstance(sourceBlock, blocks.HexBlock):
            raise TypeError(
                "Block {} is not hexagonal and cannot be converted to an equivalent cylinder".format(
                    sourceBlock
                )
            )

        if sourceBlock.spatialGrid is None:
            raise ValueError(
                f"{sourceBlock} has no spatial grid attribute, therefore "
                f"the block conversion with {self.__class__.__name__} cannot proceed."
            )

        if driverFuelBlock is not None:
            if not isinstance(driverFuelBlock, blocks.HexBlock):
                raise TypeError(
                    "Block {} is not hexagonal and cannot be converted to an equivalent cylinder".format(
                        driverFuelBlock
                    )
                )

        self.pinPitch = sourceBlock.getPinPitch()
        self.mergeIntoClad = mergeIntoClad or []
        self.interRingComponent = sourceBlock.getComponent(Flags.COOLANT, exact=True)
        self._remainingCoolantFillArea = self.interRingComponent.getArea()
        if not self.interRingComponent:
            raise ValueError(
                "Block {} cannot be converted to rings without a `coolant` component".format(
                    sourceBlock
                )
            )

    def convert(self):
        """Perform the conversion."""
        runLog.info(
            "Converting representative block {} to its equivalent cylindrical model".format(
                self._sourceBlock
            )
        )
        self._dissolveComponents()
        numRings = self._sourceBlock.spatialGrid.getMinimumRings(
            self._sourceBlock.getNumPins()
        )
        pinComponents, nonPins = self._classifyComponents()
        self._buildFirstRing(pinComponents)
        for ring in range(2, numRings + 1):
            self._buildNthRing(pinComponents, ring)
        self._buildNonPinRings(nonPins)
        self._addDriverFuelRings()
        return self.convertedBlock

    def _dissolveComponents(self):
        # always merge wire into coolant.
        self.dissolveComponentIntoComponent("wire", "coolant")
        # update coolant area to fill in wire area that was left behind.
        self.interRingComponent = self._sourceBlock.getComponent(
            Flags.COOLANT, exact=True
        )
        self._remainingCoolantFillArea = self.interRingComponent.getArea()

        # do user-input merges
        for componentName in self.mergeIntoClad:
            self.dissolveComponentIntoComponent(componentName, "clad")

    def _classifyComponents(self):
        """
        Figure out which components are in each pin ring and which are not.

        Assumption is that anything with multiplicity equal to numPins is a pin (clad, wire, bond, etc.)
        Non-pins will include things like coolant, duct, interduct, whatever else.
        """
        pinComponents, nonPins = [], []

        for c in self._sourceBlock:
            if (
                self._sourceBlock.getNumComponents(c.p.flags)
                == self._sourceBlock.getNumPins()
            ):
                pinComponents.append(c)
            elif (
                c.name != "coolant"
            ):  #  coolant is addressed in self.interRingComponent
                nonPins.append(c)

        return list(sorted(pinComponents)), nonPins

    def _buildFirstRing(self, pinComponents):
        """Add first ring of components to new block."""
        newComps = copy.deepcopy(pinComponents)
        for c in newComps:
            c.setName(c.name + " 1")
            c.setDimension("mult", 1.0)  # first ring will have dims of 1 pin
            self.convertedBlock.add(c)

    def _buildNthRing(self, pinComponents, ringNum):  # pylint: disable=too-many-locals
        """
        Build nth ring of pins and add them to block.

        Each n-th ring is preceded with a circle of coolant between the previous ring and this one.
        Since we blended the wire and coolant, the area of this area is supposed to include the wire area.

        This will be a fuel (or control) meat surrounded on both sides by clad, bond, liner, etc. layers.
        """
        numPinsInRing = self._sourceBlock.spatialGrid.getPositionsInRing(ringNum)
        pinRadii = [c.getDimension("od") / 2.0 for c in pinComponents]
        bigRingRadii = radiiFromRingOfRods(
            self.pinPitch * (ringNum - 1), numPinsInRing, pinRadii
        )
        nameSuffix = " {}".format(ringNum)

        coolantOD = bigRingRadii[0] * 2.0
        self._addCoolantRing(coolantOD, nameSuffix)
        innerDiameter = coolantOD

        compsToTransformIntoRings = pinComponents[::-1] + pinComponents[1:]
        for i, (bcs, bigRingRadius) in enumerate(
            zip(compsToTransformIntoRings, bigRingRadii[1:])
        ):
            outerDiameter = bigRingRadius * 2.0
            name = bcs.name + nameSuffix + str(i)
            bigComponent = self._addSolidMaterialRing(
                bcs, innerDiameter, outerDiameter, name
            )
            self.convertedBlock.add(bigComponent)
            innerDiameter = outerDiameter

    def _buildNonPinRings(self, nonPins):
        """
        Throw each non-pin component on as an individual outer circle.

        Also needs to add final coolant layer between the outer pins and the non-pins.
        Will crash if there are things that are not circles or hexes.
        """

        # fill in the last ring of coolant using the rest
        coolInnerDiam = self.convertedBlock[-1].getDimension("od")
        coolantOD = getOuterDiamFromIDAndArea(
            coolInnerDiam, self._remainingCoolantFillArea
        )
        self._addCoolantRing(coolantOD, " outer")

        innerDiameter = coolantOD
        for i, hexagon in enumerate(sorted(nonPins)):
            outerDiam = getOuterDiamFromIDAndArea(
                innerDiameter, hexagon.getArea()
            )  # conserve area of hex.
            name = hexagon.name + " {}".format(i)
            circularHexagon = self._addSolidMaterialRing(
                hexagon, innerDiameter, outerDiam, name
            )
            self.convertedBlock.add(circularHexagon)
            innerDiameter = outerDiam

    @staticmethod
    def _addSolidMaterialRing(baseComponent, innerDiameter, outDiameter, name):
        circle = components.Circle(
            name,
            baseComponent.material,
            baseComponent.temperatureInC,
            baseComponent.temperatureInC,
            id=innerDiameter,
            od=outDiameter,
            mult=1,
        )
        circle.setNumberDensities(baseComponent.getNumberDensities())
        return circle

    def _addCoolantRing(self, coolantOD, nameSuffix):
        innerDiam = self.convertedBlock[-1].getDimension("od")
        irc = self.interRingComponent
        interRing = components.Circle(
            irc.name + nameSuffix,
            irc.material,
            irc.temperatureInC,
            irc.temperatureInC,
            od=coolantOD,
            id=innerDiam,
            mult=1,
        )
        interRing.setNumberDensities(irc.getNumberDensities())
        self.convertedBlock.add(interRing)
        self._remainingCoolantFillArea -= interRing.getArea()


def getOuterDiamFromIDAndArea(ID, area):
    """Return the outer diameter of an annulus with given inner diameter (ID) and area."""
    return math.sqrt(ID ** 2.0 + 4.0 * area / math.pi)  # from A = pi *(d ** 2)/4.0


def radiiFromHexPitches(pitches):
    """Return list of radii for equivalent-area circles from list of from hexagon flat-to-flat pitches."""
    return [x * math.sqrt(SIN60 / math.pi) for x in pitches]


def radiiFromHexSides(sideLengths):
    """Return list of radii for equivalent-area circles from list of from hexagon side lengths."""
    return [x * math.sqrt(3.0 * SIN60 / math.pi) for x in sideLengths]


def radiiFromRingOfRods(distToRodCenter, numRods, rodRadii, layout="hexagon"):
    """
    Return list of radii from ring of rods.

    Parameters
    ----------
    distToRodCenter : float
        Distance from center of assembly to center of pin.
    numRods : int
        Number of rods in the ring of rods
    rodRadii : list
        Radii from smallest to largest. Outer radius becomes inner radius of next component.

    Returns
    -------
    radiiList : list
        List of radii from inner to outer. Components are added on both sides.

    Notes
    -----
    There are two assumptions when making circles:
    1) the rings are concentric about the radToRodCenter;
    2) the ring area of the fuel rods are distributed to the inside and outside rings with the same thickness.
    thicknessOnEachSide (t) is calculated as follows:
    r1 = inner rad that thickness is added to on inside
    r2 = outer rad that thickness is added to on outside
    radToRodCenter = (r1 + r2) / 2.0 due to being concentric;
    Total Area = Area of annulus 1 + Area of annulus 2
    Area of annulus 1 = pi * r1 ** 2       -  pi * (r1 - t) ** 2
    Area of annulus 2 = pi * (r2 + t) ** 2 -  pi * r2 ** 2
    Solving for thicknessOnEachSide(t):
    t = Total Area  / (4 * pi * radToRodCenter)
    """
    if layout == "polygon":
        alpha = 2.0 * math.pi / float(numRods)
        radToRodCenter = distToRodCenter * math.sqrt(math.sin(alpha) / alpha)
    elif layout == "hexagon":
        if numRods % 6:
            raise ValueError("numRods ({}) must be a multiple of 6.".format(numRods))
        sideLengthOfBigHex = distToRodCenter  # for equilateral triangle
        radToRodCenter = radiiFromHexSides([sideLengthOfBigHex])[0]
    else:
        raise ValueError("Invalid layout {}".format(layout))

    radiiFromRodCenter = []
    rLast = bigRLast = 0.0
    for rodRadius in rodRadii:
        area = math.pi * (rodRadius ** 2.0 - rLast ** 2.0) * float(numRods)
        thicknessOnEachSide = area / (4 * math.pi * radToRodCenter)
        distFromCenterComp = bigRLast + thicknessOnEachSide
        radiiFromRodCenter.append(radToRodCenter + distFromCenterComp)
        radiiFromRodCenter.append(
            radToRodCenter - distFromCenterComp
        )  # build thickness on both sides
        rLast, bigRLast = rodRadius, distFromCenterComp

    return sorted(radiiFromRodCenter)
